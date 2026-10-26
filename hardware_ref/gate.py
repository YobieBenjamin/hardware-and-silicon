# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Yobie Benjamin. Noncommercial use only; see NOTICE and LICENSING.md.
"""Layer 4: the control plane.

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

Every decision (allow, deny, hold, approve) is appended to the signed
audit trail before the result is returned.

Since the October 2026 review (``docs/REVIEW-2026-10.md``) the gate is also
**transactional** (``ledger.py``): replay state, holds and rate windows live in
a durable store; a rule may carry a shared ``budget`` that is *reserved* when
the request is allowed and *committed* by the endpoint before it executes;
check → reserve → mint is one critical section under one lock; and every
ticket names the policy epoch that issued it. A ticket is never the whole
authorization; it is the visible half of a reservation the ledger holds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .assertions import content_digest
from .audit import AuditLog
from .canon import digest
from .clock import SimClock
from .keys import SigningKey, VerifyKey, random_nonce, require_signed, sign_object, verify_object
from .ledger import DurableState, StateStore
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


def request_auth_payload(gate_name: str, req: dict, session_pub: str) -> dict:
    """What the attested session key signs to prove the requester controls the attested compute.

    The attestation token proves that *some* approved compute produced evidence. It does not,
    on its own, prove that whoever presents it controls that compute: a copied token is a
    bearer credential. So the token names an ephemeral session public key (``session_pub``) that
    the attested workload vouched for inside its signed quote, and the gate requires every request
    to carry a signature by the matching private key over this binding. The binding names the gate
    (the audience), the exact action, parameters and request id, so a borrowed token cannot be
    spent on another gate, for another request, or by a process that does not hold the session key.
    This reuses SG's host-signed-command pattern rather than inventing a second origin guarantee.
    """
    return {
        "type": "request-auth",
        "gate": gate_name,
        "request_id": req.get("request_id"),
        "measurement": req.get("measurement"),
        "action": req.get("action"),
        "params_digest": digest(req.get("params") or {}),
        "session_pub": session_pub,
    }


def sign_request_auth(session_key: SigningKey, gate_name: str, req: dict) -> dict:
    """Sign the proof-of-possession binding for ``req`` with the attested session key."""
    return sign_object(session_key, request_auth_payload(gate_name, req, session_key.public.hex))


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
        key: SigningKey | None = None,
        store: StateStore | None = None,
    ):
        self.name = name
        self.verifier = verifier
        self.governance = governance
        self.clock = clock
        self._key = key or SigningKey.generate()
        self.audit = audit or AuditLog(self._key, clock)
        self.observers = dict(observers or {})
        self.registries = dict(registries or {})
        self.approvers = dict(approvers or {})
        self.ticket_ttl = ticket_ttl
        self.policy: dict | None = None
        self.policy_id: str | None = None
        self.policy_version: int = 0
        self.state = DurableState(store)

    @property
    def public(self) -> VerifyKey:
        return self._key.public

    # -- policy --------------------------------------------------------------------------

    def load_policy(self, signed: dict) -> None:
        """Only governance-signed, default-deny policies load. A bad policy leaves the old one in force."""
        payload = require_signed(signed, self.governance, "gate policy")
        if payload.get("type") != "gate-policy":
            raise ValueError("not a gate policy")
        version = payload.get("version")
        if not isinstance(version, int) or version < 1:
            raise ValueError("gate policy: no version")
        with self.state.lock:
            if version < self.state.data["policy_version"]:
                raise ValueError(f"gate policy: version {version} is older than the loaded version {self.state.data['policy_version']}")
            policy = validate_policy(payload["policy"])
            new_id = digest(policy)[:16]
            if version == self.state.data["policy_version"] and self.policy_id is not None and new_id != self.policy_id:
                raise ValueError(f"gate policy: a different policy under the loaded version {version}")
            self.policy, self.policy_id, self.policy_version = policy, new_id, version
            # a hold was parked under the rules of its edition; the new rules re-decide (the governor does
            # the same). Until 22 October 2026 an approval released a hold the current rules would refuse.
            stale = [h for h, rec in self.state.holds.items() if rec.get("policy_id") != new_id]
            for h in stale:
                del self.state.holds[h]
            self.state.data["policy_version"], self.state.data["signed_policy"] = version, signed
            self.state.save()
        self._log("gate.policy_loaded", policy_id=self.policy_id, version=version, rules=len(policy["rules"]), holds_dropped=len(stale))

    def signed_epoch(self) -> dict:
        """The policy epoch endpoints bind tickets to. Re-issued after every ``load_policy``."""
        if self.policy_id is None:
            raise ValueError("no policy loaded")
        return sign_object(self._key, {"type": "policy-epoch", "gate": self.name, "policy_id": self.policy_id,
                                       "policy_version": self.policy_version, "issued_at": self.clock.now()})

    # -- the decision --------------------------------------------------------------------

    def request(self, req: dict) -> GateResult:
        """One decision is one critical section: replay check, policy, witnesses, budget reservation and ticket."""
        with self.state.lock:
            return self._request(req)

    def _request(self, req: dict) -> GateResult:
        now = self.clock.now()
        try:
            rh = request_hash(req)
        except (KeyError, TypeError):
            return self._deny("", ["request.malformed"], action="?", measurement="?")
        action, measurement = req["action"], req["measurement"]
        if self.state.seen_request(rh):
            return self._deny(rh, ["request.replayed"], action=action, measurement=measurement)
        self.state.mark_request(rh, now)
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
            # The token names an attested session key; the requester must prove it holds that
            # key over this exact request, or the token is a transferable bearer credential.
            reasons += self._check_session(req, tp, measurement, action, req.get("params") or {})
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
            window = self.state.window(f"{measurement}|{action}")
            window[:] = [t for t in window if t >= now - limit["window_s"]]
            if len(window) >= limit["max"]:
                return self._deny(rh, ["rate.limit"], action=action, measurement=measurement, rule=rule["id"])
        if requirement["mode"] == "human":
            hold_id = random_nonce(8)
            self.state.holds[hold_id] = {"request_hash": rh, "core": request_core(req), "expires_at": now + self.policy["hold_ttl_s"], "rule": rule["id"], "policy_id": self.policy_id}
            self.state.save()
            self._log("gate.decision", decision="hold", request_hash=rh, action=action, measurement=measurement, rule=rule["id"], hold_id=hold_id)
            return GateResult(Decision.HOLD, ["human.approval_required"], rh, hold_id=hold_id, rule_id=rule["id"])
        return self._allow(req, rh, rule, now)

    def approve(self, approval: dict) -> GateResult:
        """Release a hold. ``approval`` is signed by a registered approver and names the hold *and* the request hash."""
        with self.state.lock:
            return self._approve(approval)

    def _approve(self, approval: dict) -> GateResult:
        now = self.clock.now()
        body = approval.get("payload", {}) if isinstance(approval, dict) else {}
        approver = body.get("approver")
        pub = self.approvers.get(approver)
        hold_id = body.get("hold_id", "")
        if pub is None or not verify_object(approval, pub) or body.get("type") != "approval":
            return self._deny(hold_id, ["approval.untrusted"], action="approve", measurement="-")
        hold = self.state.holds.get(hold_id)
        if hold is None:
            return self._deny(hold_id, ["approval.unknown_hold"], action="approve", measurement="-")
        if body.get("request_hash") != hold["request_hash"]:
            return self._deny(hold_id, ["approval.request_mismatch"], action="approve", measurement="-")
        if now > hold["expires_at"] or body.get("expires_at", now) < now:
            self.state.holds.pop(hold_id, None)
            self.state.save()
            return self._deny(hold_id, ["approval.expired"], action="approve", measurement="-")
        if hold.get("policy_id") != self.policy_id:
            self.state.holds.pop(hold_id, None)
            self.state.save()
            return self._deny(hold_id, ["approval.policy_changed"], action="approve", measurement="-")
        self.state.holds.pop(hold_id)
        self.state.save()
        core = hold["core"]
        rule = next(r for r in self.policy["rules"] if r["id"] == hold["rule"])
        self._log("gate.approved", hold_id=hold_id, approver=approver, request_hash=hold["request_hash"])
        return self._allow(core, hold["request_hash"], rule, now)

    # -- helpers -------------------------------------------------------------------------

    def _check_session(self, req: dict, tp: dict, measurement: str, action: str, params: dict) -> list[str]:
        """Possession check: the request must be signed by the ephemeral key the token names.

        ``verify_object`` only returns true when the envelope's embedded key is the session key
        AND the signature is valid, so a borrower who holds only the public token and measurement
        cannot produce a passing proof. The binding ties the signature to this gate (audience),
        this request id and these parameters, so a proof made for one gate, session or request does
        not transfer to another.
        """
        session_pub = tp.get("session_pub")
        if session_pub is None:
            return ["attestation.session_unbound"]
        try:
            session_key = VerifyKey.from_hex(session_pub)
        except (ValueError, TypeError):
            return ["attestation.session_unbound"]
        auth = req.get("request_auth")
        if auth is None:
            return ["request_auth.missing"]
        if not verify_object(auth, session_key):
            return ["request_auth.signature"]
        ap = auth.get("payload", {}) if isinstance(auth, dict) else {}
        if ap.get("type") != "request-auth":
            return ["request_auth.type"]
        if ap.get("gate") != self.name:
            return ["request_auth.audience"]
        if ap.get("session_pub") != session_pub:
            return ["request_auth.session_mismatch"]
        if (ap.get("request_id") != req.get("request_id") or ap.get("measurement") != measurement
                or ap.get("action") != action or ap.get("params_digest") != digest(params)):
            return ["request_auth.request_mismatch"]
        return []

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
        payload: dict[str, Any] = {
            "type": "action-ticket",
            "ticket_id": random_nonce(16),
            "request_hash": rh,
            "action": core["action"],
            "params_digest": digest(core["params"]),
            "measurement": core["measurement"],
            "rule": rule["id"],
            "policy_id": self.policy_id,
            "issued_at": now,
            "expires_at": now + self.ticket_ttl,
        }
        if "endpoint" in rule:
            payload["endpoint"] = rule["endpoint"]
        budget = rule.get("budget")
        if budget is not None:
            amount = core["params"].get(budget["param"])
            if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount < 0:
                return self._deny(rh, ["budget.amount_invalid"], action=core["action"], measurement=core["measurement"], rule=rule["id"])
            rid = self.state.reserve(budget["key"], float(amount), budget["limit"], budget["window_s"], now, self.ticket_ttl)
            if rid is None:
                return self._deny(rh, ["budget.exceeded"], action=core["action"], measurement=core["measurement"], rule=rule["id"])
            payload["budget_key"] = budget["key"]
            payload["reservation"] = rid
        ticket = sign_object(self._key, payload)
        self.state.window(f"{core['measurement']}|{core['action']}").append(now)
        self.state.save()
        self._log("gate.decision", decision="allow", request_hash=rh, action=core["action"], measurement=core["measurement"], rule=rule["id"], ticket_id=payload["ticket_id"], reservation=payload.get("reservation"))
        return GateResult(Decision.ALLOW, [], rh, ticket=ticket, rule_id=rule["id"])

    # -- commit / release: the endpoint's half of the transaction ------------------------

    def commit(self, ticket: Any) -> bool:
        """Commit the reservation a ticket carries. Called by the endpoint *before* it executes.

        False means the endpoint must not execute: the ticket is not the gate's, or the
        reservation is unknown, already committed, released, or expired.
        """
        with self.state.lock:
            if not verify_object(ticket, self.public) or ticket["payload"].get("type") != "action-ticket":
                self._log("gate.commit", ok=False, reason="ticket.signature")
                return False
            p = ticket["payload"]
            if p.get("policy_id") != self.policy_id:
                # the gate's own half of the freshness check: a ticket minted under an edition the gate
                # has since replaced does not commit, whatever the endpoint believes the epoch is
                self._log("gate.commit", ok=False, reason="ticket.policy_stale", ticket_id=p.get("ticket_id"))
                return False
            # Single use at the gate, whatever the endpoint believes: a ticket commits once, so one ticket cannot produce
            # effects at two endpoints that each keep their own used-ticket record (adversarial audit 2026-10-26; the
            # governor model's F29 and committed-ticket record, carried over to the reference stack).
            if self.state.consumed("commit:" + str(p.get("ticket_id"))):
                self._log("gate.commit", ok=False, reason="ticket.already_committed", ticket_id=p.get("ticket_id"))
                return False
            if "reservation" not in p:
                self.state.consume("commit:" + str(p["ticket_id"]), self.clock.now())
                self._log("gate.commit", ok=True, ticket_id=p["ticket_id"], reservation=None)
                return True  # nothing to charge; the ticket's own checks are the endpoint's job
            ok = self.state.commit(p["budget_key"], p["reservation"], self.clock.now())
            if ok:
                self.state.consume("commit:" + str(p["ticket_id"]), self.clock.now())
            self._log("gate.commit", ok=ok, ticket_id=p["ticket_id"], reservation=p["reservation"], budget=p["budget_key"])
            return ok

    def release(self, ticket: Any) -> bool:
        """Give an unexecuted reservation back early (expiry does the same thing later)."""
        with self.state.lock:
            if not verify_object(ticket, self.public):
                return False
            p = ticket["payload"]
            if "reservation" not in p:
                return False
            ok = self.state.release(p["budget_key"], p["reservation"])
            self._log("gate.release", ok=ok, ticket_id=p["ticket_id"], reservation=p["reservation"], budget=p["budget_key"])
            return ok

    def _deny(self, rh: str, reasons: list[str], *, action: str, measurement: str, rule: str | None = None) -> GateResult:
        self._log("gate.decision", decision="deny", request_hash=rh, action=action, measurement=measurement, rule=rule, reasons=reasons)
        return GateResult(Decision.DENY, reasons, rh, rule_id=rule)

    def _log(self, event: str, **fields: Any) -> None:
        self.audit.append({"event": event, "gate": self.name, "policy_id": self.policy_id, **fields})


def make_approval(key: SigningKey, approver: str, hold_id: str, request_hash: str, now: float, ttl: float = 600.0) -> dict:
    return sign_object(key, {"type": "approval", "approver": approver, "hold_id": hold_id, "request_hash": request_hash, "issued_at": now, "expires_at": now + ttl})
