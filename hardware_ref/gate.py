"""Layer 4 — the control plane.

The gate is the only path from a model to a consequential action
(``payments.transfer``, ``shell.exec``, ``email.send``, ``model.weights.export`` …).
It does not ask the model anything and it does not run safety analysis. It
asks four questions, in this order, and fails closed on each:

1. **Is the compute attested?** A fresh attestation token from the verifier,
   bound to the workload measurement that is asking.
2. **Is the action granted?** A signed policy rule for (measurement, action)
   whose parameter constraints the request satisfies. No rule → deny.
3. **Does the policy demand a witness?** For ``observer`` rules, a fresh
   Layer 3 assertion about *this* request under the risk threshold; for
   ``provenance`` rules, a fresh Layer 2 assertion that the content is exact.
4. **Is it within budget / does a human have to say yes?** Rate limits, then
   ``human`` rules park the request as a *hold* that only a registered
   approver's signature can release.

An allowed request produces a one-time **action ticket**: a signed
capability bound to the request's hash. Endpoints (``endpoints.py``) execute
nothing without a valid, unconsumed ticket, which makes the gate a
chokepoint even for callers that try to go around it.

Every decision — allow, deny, hold, approve — is appended to the signed
audit trail before the result is returned.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .assertions import content_digest
from .audit import AuditLog
from .canon import digest
from .clock import SimClock
from .keys import SigningKey, VerifyKey, random_nonce, require_signed, sign_object, verify_object
from .policy import select_rule, validate_policy


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    HOLD = "hold"


@dataclass
class GateResult:
    decision: Decision
    reasons: list[str] = field(default_factory=list)
    request_hash: str = ""
    ticket: dict | None = None
    hold_id: str | None = None
    rule_id: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


def request_core(req: dict) -> dict:
    """The part of a request that a ticket, an observer and the audit trail bind to."""
    return {"request_id": req["request_id"], "measurement": req["measurement"], "action": req["action"], "params": req["params"]}


def request_hash(req: dict) -> str:
    return digest(request_core(req))


class PolicyGate:
    def __init__(
        self,
        verifier: VerifyKey,
        governance: VerifyKey,
        clock: SimClock,
        audit: AuditLog | None = None,
        *,
        observers: dict[str, VerifyKey] | None = None,
        registries: dict[str, VerifyKey] | None = None,
        approvers: dict[str, VerifyKey] | None = None,
        ticket_ttl: float = 60.0,
        name: str = "gate",
    ):
        self.name = name
        self.verifier = verifier
        self.governance = governance
        self.clock = clock
        self._key = SigningKey.generate()
        self.audit = audit or AuditLog(self._key, clock)
        self.observers = dict(observers or {})
        self.registries = dict(registries or {})
        self.approvers = dict(approvers or {})
        self.ticket_ttl = ticket_ttl
        self.policy: dict | None = None
        self.policy_id: str | None = None
        self._allows: dict[tuple[str, str], collections.deque] = collections.defaultdict(collections.deque)
        self._holds: dict[str, dict] = {}
        self._seen_requests: set[str] = set()

    @property
    def public(self) -> VerifyKey:
        return self._key.public

    # -- policy --------------------------------------------------------------------------

    def load_policy(self, signed: dict) -> None:
        """Only governance-signed, default-deny policies load. A bad policy leaves the old one in force."""
        payload = require_signed(signed, self.governance, "gate policy")
        if payload.get("type") != "gate-policy":
            raise ValueError("not a gate policy")
        policy = validate_policy(payload["policy"])
        self.policy = policy
        self.policy_id = digest(policy)[:16]
        self._log("gate.policy_loaded", policy_id=self.policy_id, rules=len(policy["rules"]))

    # -- the decision --------------------------------------------------------------------

    def request(self, req: dict) -> GateResult:
        now = self.clock.now()
        try:
            rh = request_hash(req)
        except (KeyError, TypeError):
            return self._deny("", ["request.malformed"], action="?", measurement="?")
        action, measurement = req["action"], req["measurement"]
        if rh in self._seen_requests:
            return self._deny(rh, ["request.replayed"], action=action, measurement=measurement)
        self._seen_requests.add(rh)
        reasons: list[str] = []

        # 1. attestation
        token = req.get("attestation_token")
        if token is None:
            reasons.append("attestation.missing")
        elif not verify_object(token, self.verifier):
            reasons.append("attestation.signature")
        else:
            tp = token["payload"]
            if tp.get("type") != "attestation-token":
                reasons.append("attestation.type")
            if tp.get("expires_at", 0) < now:
                reasons.append("attestation.expired")
            if tp.get("measurement") != measurement:
                reasons.append("attestation.measurement_mismatch")
        if reasons:
            return self._deny(rh, reasons, action=action, measurement=measurement)

        # 2. policy
        if self.policy is None:
            return self._deny(rh, ["policy.not_loaded"], action=action, measurement=measurement)
        params = req.get("params") or {}
        if not isinstance(params, dict):
            return self._deny(rh, ["request.params_type"], action=action, measurement=measurement)
        rule, reasons = select_rule(self.policy, measurement, action, params)
        if rule is None:
            return self._deny(rh, reasons, action=action, measurement=measurement)

        # 3. witnesses
        requirement = rule["requirement"]
        if requirement["mode"] in ("observer", "human") and "observer" in requirement:
            reasons += self._check_observer(req, rh, requirement, now)
        if "provenance" in rule:
            reasons += self._check_provenance(req, rule["provenance"], params, now)
        if reasons:
            return self._deny(rh, reasons, action=action, measurement=measurement, rule=rule["id"])

        # 4. budget and human hold
        limit = rule.get("rate_limit")
        if limit is not None:
            window = self._allows[(measurement, action)]
            while window and window[0] < now - limit["window_s"]:
                window.popleft()
            if len(window) >= limit["max"]:
                return self._deny(rh, ["rate.limit"], action=action, measurement=measurement, rule=rule["id"])
        if requirement["mode"] == "human":
            hold_id = random_nonce(8)
            self._holds[hold_id] = {"request_hash": rh, "core": request_core(req), "expires_at": now + self.policy["hold_ttl_s"], "rule": rule["id"]}
            self._log("gate.decision", decision="hold", request_hash=rh, action=action, measurement=measurement, rule=rule["id"], hold_id=hold_id)
            return GateResult(Decision.HOLD, ["human.approval_required"], rh, hold_id=hold_id, rule_id=rule["id"])
        return self._allow(req, rh, rule, now)

    def approve(self, approval: dict) -> GateResult:
        """Release a hold. ``approval`` is signed by a registered approver and names the hold *and* the request hash."""
        now = self.clock.now()
        body = approval.get("payload", {}) if isinstance(approval, dict) else {}
        approver = body.get("approver")
        pub = self.approvers.get(approver)
        hold_id = body.get("hold_id", "")
        if pub is None or not verify_object(approval, pub) or body.get("type") != "approval":
            return self._deny(hold_id, ["approval.untrusted"], action="approve", measurement="-")
        hold = self._holds.get(hold_id)
        if hold is None:
            return self._deny(hold_id, ["approval.unknown_hold"], action="approve", measurement="-")
        if body.get("request_hash") != hold["request_hash"]:
            return self._deny(hold_id, ["approval.request_mismatch"], action="approve", measurement="-")
        if now > hold["expires_at"] or body.get("expires_at", now) < now:
            self._holds.pop(hold_id, None)
            return self._deny(hold_id, ["approval.expired"], action="approve", measurement="-")
        self._holds.pop(hold_id)
        core = hold["core"]
        rule = next(r for r in self.policy["rules"] if r["id"] == hold["rule"])
        self._log("gate.approved", hold_id=hold_id, approver=approver, request_hash=hold["request_hash"])
        return self._allow(core, hold["request_hash"], rule, now)

    # -- helpers -------------------------------------------------------------------------

    def _check_observer(self, req: dict, rh: str, requirement: dict, now: float) -> list[str]:
        wanted = requirement["observer"]
        for want in ([wanted] if isinstance(wanted, str) else list(wanted)):
            reasons = self._check_one_observer(req, rh, want, requirement, now)
            if reasons:
                return reasons
        return []

    def _check_one_observer(self, req: dict, rh: str, want: str, requirement: dict, now: float) -> list[str]:
        fresh = self.policy["observer_freshness_s"]
        pub = self.observers.get(want)
        if pub is None:
            return ["observer.not_registered"]
        for a in req.get("assertions") or []:
            if not isinstance(a, dict) or a.get("payload", {}).get("type") != "observer-assertion":
                continue
            p = a["payload"]
            if p.get("observer") != want:
                continue
            if not verify_object(a, pub):
                return ["observer.signature"]
            if p.get("subject") != rh:
                return ["observer.subject_mismatch"]
            if p.get("expires_at", 0) < now or p.get("issued_at", 0) < now - fresh:
                return ["observer.stale"]
            if p.get("risk", 1.0) > requirement["max_risk"]:
                return ["observer.risk_above_threshold"]
            return []
        return ["observer.missing"]

    def _check_provenance(self, req: dict, prov: dict, params: dict, now: float) -> list[str]:
        pub = self.registries.get(prov["registry"])
        if pub is None:
            return ["provenance.not_registered"]
        content = params.get(prov["param"])
        if not isinstance(content, str):
            return ["provenance.content_missing"]
        want_digest = content_digest(content)
        for a in req.get("assertions") or []:
            if not isinstance(a, dict) or a.get("payload", {}).get("type") != "provenance-assertion":
                continue
            p = a["payload"]
            if p.get("registry") != prov["registry"]:
                continue
            if not verify_object(a, pub):
                return ["provenance.signature"]
            if p.get("content_digest") != want_digest:
                return ["provenance.content_mismatch"]
            if p.get("expires_at", 0) < now:
                return ["provenance.stale"]
            if p.get("status") != prov["status"]:
                return [f"provenance.status_{p.get('status')}"]
            return []
        return ["provenance.missing"]

    def _allow(self, core_like: dict, rh: str, rule: dict, now: float) -> GateResult:
        core = request_core(core_like)
        ticket = sign_object(
            self._key,
            {
                "type": "action-ticket",
                "ticket_id": random_nonce(16),
                "request_hash": rh,
                "action": core["action"],
                "params_digest": digest(core["params"]),
                "measurement": core["measurement"],
                "rule": rule["id"],
                "issued_at": now,
                "expires_at": now + self.ticket_ttl,
            },
        )
        self._allows[(core["measurement"], core["action"])].append(now)
        self._log("gate.decision", decision="allow", request_hash=rh, action=core["action"], measurement=core["measurement"], rule=rule["id"], ticket_id=ticket["payload"]["ticket_id"])
        return GateResult(Decision.ALLOW, [], rh, ticket=ticket, rule_id=rule["id"])

    def _deny(self, rh: str, reasons: list[str], *, action: str, measurement: str, rule: str | None = None) -> GateResult:
        self._log("gate.decision", decision="deny", request_hash=rh, action=action, measurement=measurement, rule=rule, reasons=reasons)
        return GateResult(Decision.DENY, reasons, rh, rule_id=rule)

    def _log(self, event: str, **fields: Any) -> None:
        self.audit.append({"event": event, "gate": self.name, "policy_id": self.policy_id, **fields})


def make_approval(key: SigningKey, approver: str, hold_id: str, request_hash: str, now: float, ttl: float = 600.0) -> dict:
    return sign_object(key, {"type": "approval", "approver": approver, "hold_id": hold_id, "request_hash": request_hash, "issued_at": now, "expires_at": now + ttl})
