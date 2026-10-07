"""Layer 0 — the silicon root of trust.

``SiliconRoot`` emulates the smallest set of hardware facilities that make
attestation mean anything:

* a **unique device secret** (UDS) fused at manufacture and never readable
  by software — only the derivation engine touches it;
* an **anti-rollback counter** (security version number) that only moves
  forward;
* **measurement registers** (PCR-style) that can only be *extended*, never
  written;
* **DICE layering**: the key that signs a quote is *derived from the
  measurement of the code that booted*, so different firmware cannot sign as
  the golden firmware even if it fully controls the CPU;
* a **quote engine** that signs the register state together with a
  verifier-supplied nonce.

Two instances play the two chips in a confidential-computing node: a CPU
TEE and an accelerator (the NVIDIA H100-class GPU attestation model). Their
quotes are bound together into one composite piece of evidence in
``attest.py``.

Everything in this file would be a block in silicon. The software below is
the functional specification of those blocks, not a substitute for them —
see ``docs/SILICON.md``.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from .canon import digest, sha256, sha256_hex
from .keys import SigningKey, VerifyKey, hkdf, hmac_sha256, sign_object

NUM_REGISTERS = 8
ZERO = b"\x00" * 32


class RollbackRefused(Exception):
    """The chip refused to boot firmware older than its fused security version."""


@dataclass(frozen=True)
class Firmware:
    """A firmware/driver/runtime image. ``code`` stands in for the binary."""

    name: str
    version: str
    svn: int
    code: bytes

    @property
    def digest(self) -> str:
        return sha256_hex(self.code)

    def tampered(self, patch: bytes = b"\x90\x90 attacker patch ") -> "Firmware":
        """An image with the same name/version/svn but different bytes."""
        return Firmware(self.name, self.version, self.svn, self.code + patch)

    def downgraded(self, svn: int, version: str | None = None) -> "Firmware":
        return Firmware(self.name, version or f"{self.version}-old", svn, self.code + b" old build ")


class ManufacturerCA:
    """The silicon vendor's endorsement authority (a TPM EK CA / DICE manufacturer CA)."""

    def __init__(self, name: str):
        self.name = name
        self._key = SigningKey.generate()

    @property
    def public(self) -> VerifyKey:
        return self._key.public

    def endorse(self, device_pub: VerifyKey, device_class: str, serial: str) -> dict:
        return sign_object(
            self._key,
            {
                "type": "device-id-cert",
                "issuer": self.name,
                "device_class": device_class,
                "serial": serial,
                "subject_pub": device_pub.hex,
            },
        )


@dataclass
class EventLogEntry:
    register: int
    label: str
    measurement: str


class SiliconRoot:
    """One chip's root of trust. See module docstring."""

    def __init__(self, device_class: str, serial: str, ca: ManufacturerCA, *, rollback_protection: bool = True):
        self.device_class = device_class
        self.serial = serial
        self.rollback_protection = rollback_protection
        # Fused at manufacture. Private attribute: nothing outside this class reads it.
        self.__uds = secrets.token_bytes(32)
        self.__fused_svn = 0
        self.__device_key = SigningKey.from_seed(hkdf(self.__uds, b"DICE/DeviceID"))
        self.device_id = self.__device_key.key_id
        self.device_cert = ca.endorse(self.__device_key.public, device_class, serial)
        self.registers: list[bytes] = [ZERO] * NUM_REGISTERS
        self.event_log: list[EventLogEntry] = []
        self.firmware: Firmware | None = None
        self.__alias_key: SigningKey | None = None
        self.alias_cert: dict | None = None

    # -- measurement -------------------------------------------------------------------

    def extend(self, register: int, label: str, data: bytes) -> None:
        """PCR extend: R ← H(R ‖ H(data)). There is no write, only extend."""
        if not 0 <= register < NUM_REGISTERS:
            raise IndexError("no such register")
        m = sha256(data)
        self.registers[register] = sha256(self.registers[register] + m)
        self.event_log.append(EventLogEntry(register, label, m.hex()))

    @property
    def fused_svn(self) -> int:
        return self.__fused_svn

    def boot(self, firmware: Firmware) -> None:
        """Measured boot. Resets registers, measures the image, derives the alias key.

        Anti-rollback: an image with ``svn`` below the fused counter is refused
        before it runs (when ``rollback_protection`` is on; the harness also
        models chips without it, which is why the verifier checks ``min_svn``
        independently).
        """
        if self.rollback_protection and firmware.svn < self.__fused_svn:
            raise RollbackRefused(f"{self.device_class}: svn {firmware.svn} < fused {self.__fused_svn}")
        self.registers = [ZERO] * NUM_REGISTERS
        self.event_log = []
        self.extend(0, "firmware", firmware.code)
        self.extend(1, "firmware-id", f"{firmware.name}:{firmware.version}".encode())
        self.extend(2, "svn", str(firmware.svn).encode())
        self.firmware = firmware
        # DICE: CDI = HMAC(UDS, measurement). Different code ⇒ different CDI ⇒ different key.
        cdi = hmac_sha256(self.__uds, bytes.fromhex(firmware.digest))
        self.__alias_key = SigningKey.from_seed(hkdf(cdi, b"DICE/Alias"))
        # The ROM layer certifies the alias key *together with the measurement it was derived from*.
        self.alias_cert = sign_object(
            self.__device_key,
            {
                "type": "alias-cert",
                "device_id": self.device_id,
                "device_class": self.device_class,
                "subject_pub": self.__alias_key.public.hex,
                "fw_digest": firmware.digest,
                "fw_name": firmware.name,
                "fw_version": firmware.version,
                "svn": firmware.svn,
            },
        )
        if firmware.svn > self.__fused_svn:
            self.__fused_svn = firmware.svn  # burn the fuse forward

    # -- attestation -------------------------------------------------------------------

    def _report(self, nonce: str, user_data: dict[str, Any] | None, registers: list[bytes]) -> dict:
        assert self.firmware is not None
        return {
            "type": "attestation-report",
            "device_class": self.device_class,
            "device_id": self.device_id,
            "serial": self.serial,
            "fw_name": self.firmware.name,
            "fw_version": self.firmware.version,
            "svn": self.firmware.svn,
            "registers": [r.hex() for r in registers],
            "event_log_digest": digest([e.__dict__ for e in self.event_log]),
            "nonce": nonce,
            "user_data": user_data or {},
        }

    def quote(self, nonce: str, user_data: dict[str, Any] | None = None) -> dict:
        """Evidence: a report signed by the alias key, plus the certificate chain."""
        if self.__alias_key is None:
            raise RuntimeError("device has not booted")
        report = self._report(nonce, user_data, self.registers)
        return {
            "report": report,
            "report_sig": sign_object(self.__alias_key, report),
            "alias_cert": self.alias_cert,
            "device_cert": self.device_cert,
        }

    # -- attacker tooling (used only by the harness) -----------------------------------

    def forged_quote(self, nonce: str, fake_registers: list[bytes], user_data: dict[str, Any] | None = None) -> dict:
        """What compromised firmware can do: sign a report with *its* alias key but lie about the registers.

        It cannot lie convincingly — the alias certificate the ROM issued binds the
        key to the measurement it was actually derived from.
        """
        if self.__alias_key is None:
            raise RuntimeError("device has not booted")
        report = self._report(nonce, user_data, fake_registers)
        return {
            "report": report,
            "report_sig": sign_object(self.__alias_key, report),
            "alias_cert": self.alias_cert,
            "device_cert": self.device_cert,
        }


def golden_registers(firmware: Firmware) -> list[str]:
    """Compute the register values a clean boot of ``firmware`` produces (reference values)."""
    regs = [ZERO] * NUM_REGISTERS
    for idx, data in ((0, firmware.code), (1, f"{firmware.name}:{firmware.version}".encode()), (2, str(firmware.svn).encode())):
        regs[idx] = sha256(regs[idx] + sha256(data))
    return [r.hex() for r in regs]


def evidence_digest(evidence: dict) -> str:
    """Digest of a quote's report — used to bind the GPU quote inside the CPU quote."""
    return digest(evidence["report"])


__all__ = [
    "Firmware",
    "ManufacturerCA",
    "SiliconRoot",
    "RollbackRefused",
    "golden_registers",
    "evidence_digest",
]
