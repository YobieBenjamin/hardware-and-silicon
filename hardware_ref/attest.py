"""Layer 5 (governance root) and the attestation verifier.

Roles follow the IETF RATS architecture (RFC 9334):

* **Attester** — the chips in ``root.py`` produce *evidence* (signed quotes).
* **Verifier** — ``AttestationVerifier`` appraises evidence against
  *reference values* and *endorsements* and issues *attestation results*.
* **Relying party** — the Layer 4 gate (``gate.py``) consumes the result as
  a short-lived signed token and never looks at raw evidence.

Layer 5 is the governance root: the key that signs reference values,
revocation lists and the gate's policy. It is deliberately *not* the silicon
vendor — the party that says which firmware may run a consequential
workload is not the party that sold the chip.

Verification order (each step fails closed with a reason code)::

    nonce fresh & unused → device cert chains to a known vendor → alias cert
    signed by the device key → report signed by the alias key → report
    registers match the alias cert's measurement (no lying firmware) → device
    not revoked → measurement in the reference allowlist → svn ≥ min_svn →
    (composite) same nonce on both chips and GPU quote bound inside CPU quote.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .canon import digest, sha256
from .clock import SimClock
from .keys import SigningKey, VerifyKey, require_signed, random_nonce, sign_object, verify_object
from .root import ZERO, Firmware, evidence_digest, golden_registers


class GovernanceRoot:
    """Layer 5: the policy authority's root key."""

    def __init__(self, name: str = "governance-root"):
        self.name = name
        self._key = SigningKey.generate()

    @property
    def public(self) -> VerifyKey:
        return self._key.public

    def sign(self, kind: str, body: dict) -> dict:
        return sign_object(self._key, {"type": kind, "issuer": self.name, **body})

    def reference_values(self, classes: dict[str, dict]) -> dict:
        """``classes`` = {device_class: {"min_svn": int, "firmware": {digest: {"name","version","registers"}}}}."""
        return self.sign("reference-values", {"classes": classes})

    def revocations(self, device_ids: list[str]) -> dict:
        return self.sign("revocation-list", {"device_ids": sorted(device_ids)})

    def policy(self, policy_body: dict) -> dict:
        return self.sign("gate-policy", {"policy": policy_body})


def reference_entry(firmware: Firmware) -> tuple[str, dict]:
    """Golden entry for one firmware image."""
    return firmware.digest, {"name": firmware.name, "version": firmware.version, "registers": golden_registers(firmware)}


@dataclass
class AttestationResult:
    accepted: bool
    reasons: list[str] = field(default_factory=list)
    token: dict | None = None
    claims: dict = field(default_factory=dict)


def workload_measurement(cpu_fw_digest: str, gpu_fw_digest: str) -> str:
    """Identity of *what is running*: the pair of measurements, independent of which physical chips."""
    return digest({"cpu": cpu_fw_digest, "gpu": gpu_fw_digest})[:32]


class AttestationVerifier:
    def __init__(
        self,
        vendor_anchors: dict[str, VerifyKey],
        governance: VerifyKey,
        clock: SimClock,
        *,
        nonce_ttl: float = 120.0,
        token_ttl: float = 300.0,
        name: str = "verifier",
    ):
        self.name = name
        self.vendor_anchors = dict(vendor_anchors)
        self.governance = governance
        self.clock = clock
        self.nonce_ttl = nonce_ttl
        self.token_ttl = token_ttl
        self._key = SigningKey.generate()
        self._nonces: dict[str, float] = {}
        self._used: set[str] = set()
        self.reference: dict = {}
        self.revoked: set[str] = set()

    @property
    def public(self) -> VerifyKey:
        return self._key.public

    # -- configuration, all of it signed by the governance root --------------------------

    def load_reference_values(self, signed: dict) -> None:
        payload = require_signed(signed, self.governance, "reference values")
        if payload.get("type") != "reference-values":
            raise ValueError("not a reference-values document")
        self.reference = payload["classes"]

    def load_revocations(self, signed: dict) -> None:
        payload = require_signed(signed, self.governance, "revocation list")
        if payload.get("type") != "revocation-list":
            raise ValueError("not a revocation list")
        self.revoked = set(payload["device_ids"])

    # -- nonces -------------------------------------------------------------------------

    def issue_nonce(self) -> str:
        nonce = random_nonce()
        self._nonces[nonce] = self.clock.now() + self.nonce_ttl
        return nonce

    def _check_nonce(self, nonce: Any) -> str | None:
        if nonce not in self._nonces:
            return "nonce.unknown"
        if nonce in self._used:
            return "nonce.replayed"
        if self.clock.now() > self._nonces[nonce]:
            return "nonce.expired"
        return None

    # -- single-chip appraisal ----------------------------------------------------------

    def appraise(self, evidence: Any, expected_nonce: str | None = None, *, check_nonce_table: bool = True) -> list[str]:
        """Return reason codes; empty list means the evidence is good.

        ``check_nonce_table=False`` is used by the composite path, which checks and
        consumes the nonce once for the whole bundle.
        """
        reasons: list[str] = []
        if not isinstance(evidence, dict) or not all(k in evidence for k in ("report", "report_sig", "alias_cert", "device_cert")):
            return ["evidence.malformed"]
        report = evidence["report"]
        if not isinstance(report, dict) or report.get("type") != "attestation-report":
            return ["evidence.malformed"]

        # 1. device certificate chains to a vendor we know
        dev = evidence["device_cert"]
        issuer = dev.get("payload", {}).get("issuer") if isinstance(dev, dict) else None
        anchor = self.vendor_anchors.get(issuer)
        if anchor is None or not verify_object(dev, anchor):
            reasons.append("device_cert.untrusted")
            return reasons
        dev_p = dev["payload"]
        if dev_p.get("type") != "device-id-cert" or dev_p.get("device_class") != report.get("device_class"):
            reasons.append("device_cert.mismatch")
            return reasons
        device_pub = VerifyKey.from_hex(dev_p["subject_pub"])

        # 2. alias certificate issued by that device's ROM key
        alias = evidence["alias_cert"]
        if not verify_object(alias, device_pub) or alias["payload"].get("type") != "alias-cert":
            reasons.append("alias_cert.invalid")
            return reasons
        alias_p = alias["payload"]
        if alias_p.get("device_id") != report.get("device_id") or device_pub.key_id != report.get("device_id"):
            reasons.append("alias_cert.device_mismatch")
            return reasons
        alias_pub = VerifyKey.from_hex(alias_p["subject_pub"])

        # 3. report signed by the alias key, and the signed report is the one we were handed
        sig = evidence["report_sig"]
        if not verify_object(sig, alias_pub) or digest(sig["payload"]) != digest(report):
            reasons.append("report.signature")
            return reasons

        # 4. nonce
        if check_nonce_table:
            nonce_reason = self._check_nonce(report.get("nonce"))
            if nonce_reason:
                reasons.append(nonce_reason)
        if expected_nonce is not None and report.get("nonce") != expected_nonce:
            reasons.append("nonce.mismatch")

        # 5. the report's measurement must be the one the alias key was derived from.
        #    Register 0 is H(ZERO ‖ H(code)); recompute it from the digest the ROM certified
        #    instead of trusting whatever the firmware wrote in the report.
        regs = report.get("registers") or []
        fw_digest = alias_p.get("fw_digest")
        if alias_p.get("svn") != report.get("svn") or alias_p.get("fw_version") != report.get("fw_version"):
            reasons.append("report.firmware_claims")
        expected_r0 = sha256(ZERO + bytes.fromhex(fw_digest)).hex() if fw_digest else None
        if not regs or expected_r0 is None or regs[0] != expected_r0:
            reasons.append("report.registers_vs_cert")

        # 6. revocation
        if report.get("device_id") in self.revoked:
            reasons.append("device.revoked")

        # 7. reference values for this class
        cls = self.reference.get(report.get("device_class"))
        if cls is None:
            reasons.append("class.unknown")
        else:
            golden = cls.get("firmware", {}).get(fw_digest)
            if golden is None:
                reasons.append("firmware.unknown")
            elif golden.get("registers") != regs:
                reasons.append("registers.mismatch")
            if report.get("svn", -1) < cls.get("min_svn", 0):
                reasons.append("svn.below_minimum")
        return reasons

    # -- composite appraisal (CPU TEE + accelerator) ------------------------------------

    def verify_node(self, bundle: Any) -> AttestationResult:
        """Appraise a two-chip node and, on success, issue an attestation token.

        ``bundle`` = {"nonce": n, "cpu": evidence, "gpu": evidence}. The CPU quote
        must carry ``digest(gpu report)`` in its user data: the TEE vouches that
        *this* accelerator is the one attached to it, so an attacker cannot pair a
        clean CPU quote with a quote from some other, unmodified GPU.
        """
        reasons: list[str] = []
        if not isinstance(bundle, dict) or "cpu" not in bundle or "gpu" not in bundle:
            return AttestationResult(False, ["bundle.malformed"])
        nonce = bundle.get("nonce")
        nonce_reason = self._check_nonce(nonce)
        if nonce_reason:
            reasons.append(nonce_reason)
        # consume the nonce on first use, success or failure — a replay of a failed attempt is still a replay
        if nonce in self._nonces:
            self._used.add(nonce)
        reasons += [f"cpu.{r}" for r in self.appraise(bundle["cpu"], expected_nonce=nonce, check_nonce_table=False)]
        reasons += [f"gpu.{r}" for r in self.appraise(bundle["gpu"], expected_nonce=nonce, check_nonce_table=False)]
        if not reasons:
            cpu_report, gpu_report = bundle["cpu"]["report"], bundle["gpu"]["report"]
            if cpu_report.get("device_class") != "cpu-tee" or gpu_report.get("device_class") != "gpu":
                reasons.append("bundle.classes")
            bound = cpu_report.get("user_data", {}).get("gpu_evidence")
            if bound != evidence_digest(bundle["gpu"]):
                reasons.append("binding.gpu_not_bound_to_cpu")
        if reasons:
            return AttestationResult(False, sorted(set(reasons)))

        cpu_p, gpu_p = bundle["cpu"]["alias_cert"]["payload"], bundle["gpu"]["alias_cert"]["payload"]
        measurement = workload_measurement(cpu_p["fw_digest"], gpu_p["fw_digest"])
        now = self.clock.now()
        claims = {
            "measurement": measurement,
            "devices": {
                "cpu-tee": {"device_id": cpu_p["device_id"], "fw": f"{cpu_p['fw_name']}:{cpu_p['fw_version']}", "svn": cpu_p["svn"]},
                "gpu": {"device_id": gpu_p["device_id"], "fw": f"{gpu_p['fw_name']}:{gpu_p['fw_version']}", "svn": gpu_p["svn"]},
            },
            "nonce": nonce,
        }
        token = sign_object(
            self._key,
            {
                "type": "attestation-token",
                "issuer": self.name,
                "issued_at": now,
                "expires_at": now + self.token_ttl,
                **claims,
            },
        )
        return AttestationResult(True, [], token, claims)


def build_bundle(cpu, gpu, nonce: str) -> dict:
    """The attester-side composition: quote the GPU, then quote the CPU with the GPU quote bound in."""
    gpu_ev = gpu.quote(nonce)
    cpu_ev = cpu.quote(nonce, user_data={"gpu_evidence": evidence_digest(gpu_ev)})
    return {"nonce": nonce, "cpu": cpu_ev, "gpu": gpu_ev}
