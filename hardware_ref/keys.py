"""Keys, signatures and key derivation.

Ed25519 everywhere. The TCG DICE specification permits Ed25519 for layered
device identities; production silicon more often ships ECDSA P-256/P-384
(TPM, SEV-SNP, NVIDIA H100 attestation), which changes the curve and
nothing about the architecture.

A *signed object* is the one envelope format every layer exchanges::

    {"payload": {...}, "signer": <key id>, "pub": <hex public key>, "sig": <b64>}

The signature is over ``canonical(payload)``. Verification never trusts the
embedded ``pub`` on its own: callers pass the public key they expect (a
trust anchor), and ``verify_object`` rejects an envelope whose embedded key
does not match it. The embedded key is a hint for lookups, not a source of
trust.
"""
from __future__ import annotations

import hmac
import secrets
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .canon import b64d, b64e, canonical, sha256


class SignatureError(Exception):
    """Raised when an envelope fails verification and the caller asked to raise."""


def hkdf(ikm: bytes, info: bytes, length: int = 32, salt: bytes = b"") -> bytes:
    """HKDF-SHA256. In silicon this is the key-derivation engine fed by the fused secret."""
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, "sha256").digest()


class VerifyKey:
    """An Ed25519 public key with a stable identifier."""

    def __init__(self, raw: bytes):
        if len(raw) != 32:
            raise ValueError("Ed25519 public keys are 32 bytes")
        self.raw = raw
        self._key = Ed25519PublicKey.from_public_bytes(raw)

    @classmethod
    def from_hex(cls, text: str) -> "VerifyKey":
        return cls(bytes.fromhex(text))

    @property
    def hex(self) -> str:
        return self.raw.hex()

    @property
    def key_id(self) -> str:
        return sha256(self.raw)[:8].hex()

    def verify(self, signature: bytes, message: bytes) -> bool:
        try:
            self._key.verify(signature, message)
            return True
        except InvalidSignature:
            return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, VerifyKey) and other.raw == self.raw

    def __hash__(self) -> int:
        return hash(self.raw)

    def __repr__(self) -> str:
        return f"VerifyKey({self.key_id})"


class SigningKey:
    """An Ed25519 private key. ``from_seed`` makes DICE-style deterministic derivation possible."""

    def __init__(self, private: Ed25519PrivateKey):
        self._key = private
        self.public = VerifyKey(private.public_key().public_bytes_raw())

    @classmethod
    def generate(cls) -> "SigningKey":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_seed(cls, seed: bytes) -> "SigningKey":
        if len(seed) != 32:
            raise ValueError("seed must be 32 bytes")
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    @property
    def key_id(self) -> str:
        return self.public.key_id

    def sign(self, message: bytes) -> bytes:
        return self._key.sign(message)


def sign_object(key: SigningKey, payload: Mapping[str, Any]) -> dict:
    """Wrap ``payload`` in a signed envelope."""
    payload = dict(payload)
    return {
        "payload": payload,
        "signer": key.key_id,
        "pub": key.public.hex,
        "sig": b64e(key.sign(canonical(payload))),
    }


def verify_object(envelope: Any, expected: VerifyKey | None = None) -> bool:
    """Check an envelope's signature.

    If ``expected`` is given, the embedded public key must equal it; an envelope
    carrying a different key is rejected even if its signature is internally
    valid — that is exactly the forged-key attack a trust anchor exists to stop.
    """
    if not isinstance(envelope, Mapping):
        return False
    for field in ("payload", "signer", "pub", "sig"):
        if field not in envelope:
            return False
    try:
        pub = VerifyKey.from_hex(envelope["pub"])
    except (ValueError, TypeError):
        return False
    if expected is not None and pub != expected:
        return False
    if envelope["signer"] != pub.key_id:
        return False
    try:
        return pub.verify(b64d(envelope["sig"]), canonical(envelope["payload"]))
    except (ValueError, TypeError):
        return False


def require_signed(envelope: Any, expected: VerifyKey | None, what: str) -> dict:
    """``verify_object`` that raises; returns the payload."""
    if not verify_object(envelope, expected):
        raise SignatureError(f"{what}: signature invalid or signer not trusted")
    return envelope["payload"]


def random_nonce(nbytes: int = 32) -> str:
    """Hardware RNG stand-in."""
    return secrets.token_hex(nbytes)
