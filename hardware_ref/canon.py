"""Canonical bytes, digests and encodings shared by every layer.

Everything that is signed, measured or chained in this stack goes through
``canonical()`` first, so two parties that agree on a JSON object agree on
its bytes. In silicon this is the role of a fixed serialisation format
(a CBOR/DER encoder in ROM); here it is sorted-key, separator-free JSON.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


def canonical(obj: Any) -> bytes:
    """Deterministic JSON encoding: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(obj: Any) -> str:
    """Hex SHA-256 of the canonical encoding of ``obj``."""
    return sha256_hex(canonical(obj))


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def short(hex_or_text: str, n: int = 12) -> str:
    """Abbreviate a hex digest for logs and reports."""
    return hex_or_text[:n] + "…" if len(hex_or_text) > n else hex_or_text
