"""Lane interfaces: what the control plane accepts from Layer 2 and Layer 3.

The three repositories stay in separate lanes. This module defines the
*only* coupling between them — two signed assertion formats — and ships a
stub producer for each so the gate can be tested without importing either
other repo.

* **Observer assertion** (Layer 3, the ``safety`` repo). An early-warning
  observer looks at a specific pending action and signs a verdict::

      {"type": "observer-assertion", "observer": "obs-main",
       "subject": <request hash>, "risk": 0.12, "flags": [],
       "issued_at": t, "expires_at": t + ttl}

  The gate does not know how the risk was computed and never computes one
  itself. It only checks: trusted observer key, subject == this request,
  fresh, risk ≤ the policy's threshold.

* **Provenance assertion** (Layer 2, the ``Watermark`` repo). The signed
  registry says whether a piece of content is exactly what an attested
  model produced::

      {"type": "provenance-assertion", "registry": "wm-registry",
       "content_digest": <sha256 of content>, "status": "exact" | "tampered" | "unknown",
       "issued_at": t, "expires_at": t + ttl}

  The gate does not detect watermarks. It only checks: trusted registry key,
  digest == the content in this request, fresh, status meets the policy.

Both are fail-closed: a required assertion that is missing, stale, forged,
or about something else denies the action.
"""
from __future__ import annotations

from .canon import sha256_hex
from .clock import SimClock
from .keys import SigningKey, VerifyKey, sign_object


def observer_assertion(key: SigningKey, observer: str, subject: str, risk: float, flags: list[str], now: float, ttl: float = 60.0) -> dict:
    return sign_object(
        key,
        {
            "type": "observer-assertion",
            "observer": observer,
            "subject": subject,
            "risk": float(risk),
            "flags": list(flags),
            "issued_at": now,
            "expires_at": now + ttl,
        },
    )


def provenance_assertion(key: SigningKey, registry: str, content_digest: str, status: str, now: float, ttl: float = 300.0) -> dict:
    if status not in ("exact", "tampered", "unknown"):
        raise ValueError("status must be exact|tampered|unknown")
    return sign_object(
        key,
        {
            "type": "provenance-assertion",
            "registry": registry,
            "content_digest": content_digest,
            "status": status,
            "issued_at": now,
            "expires_at": now + ttl,
        },
    )


def content_digest(content: str) -> str:
    return sha256_hex(content.encode("utf-8"))


class StubObserver:
    """Stand-in for a Layer 3 observer. Scores by a trivial keyword rule so tests are deterministic.

    The real observers live in the ``safety`` repo; this class exists only so the
    control plane can be exercised end to end here.
    """

    DANGER = ("exfiltrate", "disable monitoring", "wire everything", "rm -rf", "self-replicate")

    def __init__(self, observer_id: str, clock: SimClock, ttl: float = 60.0):
        self.observer_id = observer_id
        self.clock = clock
        self.ttl = ttl
        self._key = SigningKey.generate()

    @property
    def public(self) -> VerifyKey:
        return self._key.public

    def score(self, action: str, params: dict) -> tuple[float, list[str]]:
        text = f"{action} {params}".lower()
        flags = [w for w in self.DANGER if w in text]
        return (0.95 if flags else 0.05), flags

    def assess(self, request_hash: str, action: str, params: dict, *, risk: float | None = None) -> dict:
        r, flags = self.score(action, params)
        if risk is not None:
            r = risk
        return observer_assertion(self._key, self.observer_id, request_hash, r, flags, self.clock.now(), self.ttl)


class StubProvenanceRegistry:
    """Stand-in for the Layer 2 signed registry: remembers exactly what the model emitted."""

    def __init__(self, registry_id: str, clock: SimClock, ttl: float = 300.0):
        self.registry_id = registry_id
        self.clock = clock
        self.ttl = ttl
        self._key = SigningKey.generate()
        self._exact: set[str] = set()

    @property
    def public(self) -> VerifyKey:
        return self._key.public

    def record(self, content: str) -> str:
        d = content_digest(content)
        self._exact.add(d)
        return d

    def attest(self, content: str, *, status: str | None = None) -> dict:
        d = content_digest(content)
        if status is None:
            status = "exact" if d in self._exact else "unknown"
        return provenance_assertion(self._key, self.registry_id, d, status, self.clock.now(), self.ttl)
