"""Working with the NVIDIA Open Agent Safety Platform (OASP).

NVIDIA's platform (announced 28 Sep 2026) has two parts: **OpenShell**, an
open-source runtime that puts every agent in a deny-by-default sandbox whose
only network path is a *supervisor* that checks outbound requests against a
policy, and **Sentry**, a reference design for an out-of-band watchdog on
BlueField-4 DPUs that sits on the node's only path to the model, correlates
agent activity, and can quarantine an agent in milliseconds.

This module is the seam between that platform and the control plane in this
repo. It does not re-implement sandboxing, network policy or credential
binding — OpenShell owns those. It adds the four things the hardware lane
exists for, at the points the platform leaves open:

* **Supervisor middleware** (``SupervisorMiddleware``). OpenShell lets
  trusted middleware outside the sandbox add checks to the request path. Ours
  requires an *attestation token* for the sandbox's host, routes the outbound
  request to a consequential action, consults the Layer 4 gate (policy,
  witnesses, budget, human hold) and attaches the resulting one-time ticket.
  A request the supervisor never saw has no ticket, so the endpoint refuses it
  — the ticket turns "no path except the supervisor" into something the far
  end can verify.
* **Policy translation** (``to_openshell_network_policy``). The governance-
  signed gate policy is the single source of truth; the OpenShell
  ``network_policies`` document (YAML → OPA/Rego, checked by the OpenShell
  policy prover) is *derived* from it, so the two layers cannot disagree about
  which hosts an agent may reach.
* **Sentry as a Layer 3 producer and as the actuator** (``SentryObserver``,
  ``SentryActuator``). Sentry's telemetry becomes a signed observer assertion
  the gate can require; a gate decision that crosses the drift threshold asks
  Sentry to quarantine the sandbox, and a quarantined sandbox gets nothing
  further from the gate.
* **OCSF-style audit export** (``to_ocsf``). OpenShell records decisions in
  OCSF; our hash-chained, checkpointed log emits the same shape so one
  pipeline can ingest both, with tamper evidence on top.

Nothing here talks to real NVIDIA software: the classes model the contract
so the gate's behaviour on that contract is testable today, and so the
silicon phase (``docs/SILICON.md``) has a DOCA-side target to hit.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Any, Callable

from .assertions import observer_assertion
from .audit import AuditLog
from .canon import digest
from .clock import SimClock
from .gate import Decision, GateResult, PolicyGate, request_hash
from .keys import SigningKey, VerifyKey

# ---------------------------------------------------------------------------------------
# Policy translation: gate policy → OpenShell network_policies
# ---------------------------------------------------------------------------------------


def to_openshell_network_policy(policy: dict, *, binaries: list[str] | None = None) -> dict:
    """Derive an OpenShell ``network_policies`` document from a gate policy.

    Only rules that carry an ``egress`` block (host, port, protocol, access)
    translate; a rule without one grants nothing at the network layer. The
    output follows the OpenShell 0.1.0 documented shape::

        network_policies:
          <rule id>:
            name: <rule id>
            endpoints:
              - host: api.internal.example.com
                port: 443
                protocol: rest
                enforcement: enforce
                access: read-only
            binaries:
              - path: /usr/bin/curl
    """
    out: dict[str, Any] = {}
    for rule in policy.get("rules", []):
        egress = rule.get("egress")
        if not egress:
            continue
        key = rule["id"].replace("-", "_")
        out[key] = {
            "name": rule["id"],
            "endpoints": [
                {
                    "host": egress["host"],
                    "port": int(egress.get("port", 443)),
                    "protocol": egress.get("protocol", "rest"),
                    "enforcement": "enforce",
                    "access": egress.get("access", "read-only"),
                }
            ],
            "binaries": [{"path": p} for p in (egress.get("binaries") or binaries or ["/usr/bin/curl"])],
        }
    return {"network_policies": out}


def granted_hosts(policy: dict) -> set[str]:
    return {r["egress"]["host"] for r in policy.get("rules", []) if r.get("egress")}


def to_yaml(obj: Any, indent: int = 0) -> str:
    """Minimal YAML emitter for the nested dict/list/scalar documents above (no dependency)."""
    pad = "  " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:")
                lines.append(to_yaml(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {_scalar(v)}")
        return "\n".join(lines)
    if isinstance(obj, list):
        lines = []
        for item in obj:
            if isinstance(item, dict):
                body = to_yaml(item, indent + 1).splitlines()
                lines.append(f"{pad}- " + body[0].lstrip())
                lines.extend(body[1:])
            else:
                lines.append(f"{pad}- {_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{_scalar(obj)}"


def _scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None or (isinstance(v, (dict, list)) and not v):
        return "{}" if isinstance(v, dict) else "[]" if isinstance(v, list) else "null"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    return s if s and all(c.isalnum() or c in "-_./:" for c in s) else '"' + s.replace('"', '\\"') + '"'


# ---------------------------------------------------------------------------------------
# Sentry: Layer 3 producer and quarantine actuator
# ---------------------------------------------------------------------------------------


class SentryObserver:
    """Turns Sentry-style telemetry about a pending action into a signed observer assertion.

    Sentry sits on BlueField-4, out of the agent's reach, and correlates agent
    interactions, policy decisions and tool/data access. We do not model how it
    scores drift; we model the only thing the gate needs — a signed verdict
    about *this request* from a key the gate anchors — so the gate's reaction
    to Sentry's output is testable.
    """

    def __init__(self, observer_id: str, clock: SimClock, ttl: float = 60.0):
        self.observer_id = observer_id
        self.clock = clock
        self.ttl = ttl
        self._key = SigningKey.generate()

    @property
    def public(self) -> VerifyKey:
        return self._key.public

    @staticmethod
    def risk_from_telemetry(telemetry: dict) -> tuple[float, list[str]]:
        """Reference reduction of telemetry to one risk number; the real one is Sentry's."""
        flags: list[str] = []
        drift = float(telemetry.get("drift_score", 0.0))
        if drift >= 0.5:
            flags.append("drift")
        if telemetry.get("identity_verified") is False:
            flags.append("identity_unverified")
            drift = max(drift, 0.9)
        if telemetry.get("recent_denials", 0) >= 5:
            flags.append("repeated_denials")
            drift = max(drift, 0.6)
        return min(1.0, drift), flags

    def assess(self, request_hash_: str, telemetry: dict) -> dict:
        risk, flags = self.risk_from_telemetry(telemetry)
        return observer_assertion(self._key, self.observer_id, request_hash_, risk, flags, self.clock.now(), self.ttl)


@dataclass
class SentryActuator:
    """The kill switch: Sentry owns the path to the model and can quarantine a sandbox in milliseconds."""

    audit: AuditLog
    quarantined: dict[str, str] = field(default_factory=dict)

    def quarantine(self, sandbox_id: str, reason: str) -> None:
        if sandbox_id in self.quarantined:
            return
        self.quarantined[sandbox_id] = reason
        self.audit.append({"event": "sentry.quarantine", "sandbox": sandbox_id, "reason": reason})

    def release(self, sandbox_id: str, approver: str) -> None:
        self.quarantined.pop(sandbox_id, None)
        self.audit.append({"event": "sentry.release", "sandbox": sandbox_id, "approver": approver})

    def is_quarantined(self, sandbox_id: str) -> bool:
        return sandbox_id in self.quarantined


# ---------------------------------------------------------------------------------------
# Supervisor middleware: the gate on OpenShell's request path
# ---------------------------------------------------------------------------------------


@dataclass
class Route:
    """Maps an outbound request the supervisor sees to a consequential action."""

    method: str
    host: str
    path: str
    action: str
    params: Callable[[dict], dict] = lambda body: dict(body or {})


@dataclass
class OutboundRequest:
    sandbox_id: str
    method: str
    host: str
    path: str
    body: dict = field(default_factory=dict)
    request_id: str = ""


@dataclass
class MiddlewareDecision:
    allowed: bool
    status: int
    reasons: list[str]
    headers: dict[str, str] = field(default_factory=dict)
    gate: GateResult | None = None
    action: str | None = None
    quarantined: bool = False


@dataclass
class DriftPolicy:
    quarantine_risk: float = 0.9  # an observer verdict at or above this quarantines immediately
    max_denials: int = 5  # this many gate denials inside window_s is drift
    window_s: float = 300.0


class SupervisorMiddleware:
    """Trusted middleware on the OpenShell supervisor's outbound path.

    Order of operations for every request the sandbox makes:

    1. quarantined sandbox → 403 ``sandbox.quarantined`` (nothing else is evaluated);
    2. no route → the request is not a consequential action; pass through to
       OpenShell's own network policy (``allowed=True`` with no ticket — the
       endpoint side will refuse anything consequential that lacks one);
    3. no attestation token bound to this sandbox's host → 403 ``attestation.missing``;
    4. build the gate request (token, Sentry verdict, any provenance assertion),
       consult the gate;
    5. ALLOW → 200 with the ticket in ``X-Action-Ticket``; HOLD → 202 with the hold id;
       DENY → 403 with the reason codes, and drift accounting that may quarantine.
    """

    def __init__(self, gate: PolicyGate, clock: SimClock, *, sentry: SentryObserver | None = None, actuator: SentryActuator | None = None, drift: DriftPolicy | None = None):
        self.gate = gate
        self.clock = clock
        self.sentry = sentry
        self.actuator = actuator or SentryActuator(gate.audit)
        self.drift = drift or DriftPolicy()
        self.routes: list[Route] = []
        self._sandboxes: dict[str, dict] = {}
        self._denials: dict[str, collections.deque] = collections.defaultdict(collections.deque)
        self.telemetry: Callable[[OutboundRequest], dict] = lambda req: {"drift_score": 0.0, "identity_verified": True}
        self.provenance: Callable[[OutboundRequest], dict | None] = lambda req: None
        self.witnesses: list[Callable[[str, str, dict], dict]] = []  # extra Layer 3 producers (the safety repo's observer)
        self._seq = 0

    # -- configuration -----------------------------------------------------------------

    def add_route(self, route: Route) -> None:
        self.routes.append(route)

    def bind_sandbox(self, sandbox_id: str, measurement: str, token: dict | None) -> None:
        """Associate a sandbox with the attested host it runs on (token may be refreshed later)."""
        self._sandboxes[sandbox_id] = {"measurement": measurement, "token": token}

    def refresh_token(self, sandbox_id: str, token: dict | None) -> None:
        self._sandboxes[sandbox_id]["token"] = token

    def add_witness(self, producer: Callable[[str, str, dict], dict]) -> None:
        """Register a second Layer 3 witness. Called with (request_hash, action, params); returns a signed assertion.

        Sentry is the witness the NVIDIA path always carries. A rule that names
        several observers (``"observer": ["sentry", "obs-main"]``) needs every one
        of them to pass, so an attacker has to compromise every witness key, not
        one. Use it for the highest-authority actions; see ``docs/NVIDIA.md``.
        """
        self.witnesses.append(producer)

    def _route(self, req: OutboundRequest) -> Route | None:
        for r in self.routes:
            if r.method == req.method and r.host == req.host and _path_match(r.path, req.path):
                return r
        return None

    # -- the request path -----------------------------------------------------------------

    def handle(self, req: OutboundRequest) -> MiddlewareDecision:
        if self.actuator.is_quarantined(req.sandbox_id):
            self.gate.audit.append({"event": "supervisor.refused", "sandbox": req.sandbox_id, "reason": "sandbox.quarantined"})
            return MiddlewareDecision(False, 403, ["sandbox.quarantined"], quarantined=True)
        route = self._route(req)
        if route is None:
            return MiddlewareDecision(True, 200, [], action=None)  # not consequential; OpenShell's own policy applies
        binding = self._sandboxes.get(req.sandbox_id)
        if binding is None or binding.get("token") is None:
            self.gate.audit.append({"event": "supervisor.refused", "sandbox": req.sandbox_id, "action": route.action, "reason": "attestation.missing"})
            self._count_denial(req.sandbox_id)
            return MiddlewareDecision(False, 403, ["attestation.missing"], action=route.action)

        params = route.params(req.body)
        self._seq += 1  # every request the supervisor sees gets its own id; the gate's replay check keys on it
        gate_req = {
            "request_id": req.request_id or digest({"s": req.sandbox_id, "n": self._seq, "m": req.method, "h": req.host, "p": req.path})[:32],
            "measurement": binding["measurement"],
            "action": route.action,
            "params": params,
            "attestation_token": binding["token"],
            "assertions": [],
        }
        rh = request_hash(gate_req)
        telemetry = self.telemetry(req)
        if self.sentry is not None:
            gate_req["assertions"].append(self.sentry.assess(rh, telemetry))
        for witness in self.witnesses:
            gate_req["assertions"].append(witness(rh, route.action, params))
        prov = self.provenance(req)
        if prov is not None:
            gate_req["assertions"].append(prov)

        res = self.gate.request(gate_req)
        if res.decision is Decision.ALLOW:
            return MiddlewareDecision(True, 200, [], headers={"X-Action-Ticket": _ticket_header(res.ticket)}, gate=res, action=route.action)
        if res.decision is Decision.HOLD:
            return MiddlewareDecision(False, 202, res.reasons, headers={"X-Hold-Id": res.hold_id or ""}, gate=res, action=route.action)

        quarantined = self._after_denial(req.sandbox_id, res, telemetry)
        return MiddlewareDecision(False, 403, res.reasons, gate=res, action=route.action, quarantined=quarantined)

    # -- drift accounting ------------------------------------------------------------------

    def _count_denial(self, sandbox_id: str) -> int:
        window = self._denials[sandbox_id]
        now = self.clock.now()
        window.append(now)
        while window and window[0] < now - self.drift.window_s:
            window.popleft()
        return len(window)

    def _after_denial(self, sandbox_id: str, res: GateResult, telemetry: dict) -> bool:
        n = self._count_denial(sandbox_id)
        risk, _ = SentryObserver.risk_from_telemetry(telemetry)
        if "observer.risk_above_threshold" in res.reasons and risk >= self.drift.quarantine_risk:
            self.actuator.quarantine(sandbox_id, f"observer risk {risk:.2f} ≥ {self.drift.quarantine_risk}")
            return True
        if n >= self.drift.max_denials:
            self.actuator.quarantine(sandbox_id, f"{n} denials in {self.drift.window_s:.0f}s")
            return True
        return False


def _path_match(pattern: str, path: str) -> bool:
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3])
    return pattern == path


def _ticket_header(ticket: dict | None) -> str:
    """Compact transport form: the ticket id plus the full envelope as canonical JSON."""
    if ticket is None:
        return ""
    from .canon import canonical

    return canonical(ticket).decode("utf-8")


def ticket_from_header(value: str) -> dict:
    import json

    return json.loads(value)


# ---------------------------------------------------------------------------------------
# OCSF-style audit export
# ---------------------------------------------------------------------------------------

_EVENT_MAP = {
    # event → (category_uid, class_uid, class_name, activity_id, activity_name)
    "gate.decision": (3, 3002, "Authorization", 1, "Authorize"),
    "gate.approved": (3, 3002, "Authorization", 1, "Authorize"),
    "gate.policy_loaded": (6, 6003, "API Activity", 3, "Update"),
    "endpoint.executed": (6, 6003, "API Activity", 1, "Create"),
    "endpoint.refused": (6, 6003, "API Activity", 1, "Create"),
    "sentry.quarantine": (2, 2004, "Detection Finding", 1, "Create"),
    "sentry.release": (2, 2004, "Detection Finding", 3, "Update"),
    "supervisor.refused": (3, 3002, "Authorization", 1, "Authorize"),
}


def to_ocsf(entry: dict, *, product: str = "hardware_ref") -> dict:
    """Map one audit entry to an OCSF-shaped event.

    The field names follow the OCSF base event (``category_uid``, ``class_uid``,
    ``activity_id``, ``severity_id``, ``status_id``, ``time``, ``metadata``) so an
    OpenShell OCSF pipeline can take the records; it is a shape, not a validated
    schema instance — validation against the official schema is a to-do. The
    chain hash and signature travel in ``unmapped`` so tamper evidence survives
    the export.
    """
    rec = entry["record"]
    event = rec.get("event", "unknown")
    cat, cls, cls_name, act, act_name = _EVENT_MAP.get(event, (0, 0, "Base Event", 0, "Unknown"))
    decision = rec.get("decision")
    denied = decision == "deny" or event in ("endpoint.refused", "supervisor.refused")
    severity = 1  # informational
    if denied:
        severity = 3  # medium
    if event == "sentry.quarantine" or "observer.risk_above_threshold" in (rec.get("reasons") or []):
        severity = 5  # critical
    return {
        "category_uid": cat,
        "class_uid": cls,
        "class_name": cls_name,
        "activity_id": act,
        "activity_name": act_name,
        "type_uid": cls * 100 + act,
        "time": int(entry["ts"] * 1000),
        "severity_id": severity,
        "status_id": 2 if denied else 1,
        "status": "Failure" if denied else "Success",
        "message": _message(rec),
        "metadata": {"product": {"name": product, "vendor_name": "hardware lane"}, "version": "1.1.0", "log_name": entry.get("log", "gate-audit"), "uid": f"{entry['seq']}"},
        "actor": {"user": {"name": rec.get("measurement") or rec.get("sandbox") or "-"}},
        "api": {"operation": rec.get("action") or event},
        "unmapped": {"event": event, "seq": entry["seq"], "prev": entry["prev"], "hash": entry["hash"], "sig": entry["sig"], "record": rec},
    }


def _message(rec: dict) -> str:
    event = rec.get("event", "")
    if event == "gate.decision":
        return f"{rec.get('decision', '?').upper()} {rec.get('action')} ({', '.join(rec.get('reasons') or []) or rec.get('rule')})"
    if event.startswith("endpoint."):
        return f"{event} {rec.get('action')} {rec.get('reason', '')}".strip()
    if event.startswith("sentry."):
        return f"{event} {rec.get('sandbox')} {rec.get('reason', '')}".strip()
    return event


def export_ocsf(log: AuditLog) -> list[dict]:
    return [to_ocsf(e) for e in log.entries]
