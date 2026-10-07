"""Consequential action endpoints.

An endpoint is anything whose effect reaches outside the model: moving
money, sending mail, running a shell, posting to a URL, exporting weights.
In this reference stack every endpoint is a stub that records what it would
have done — the point is not the effect, it is the *admission control*:

* nothing executes without an action ticket;
* the ticket must be signed by the gate, unexpired, bound to this exact
  action and parameter set, and never used before;
* every execution and every refusal is written to the audit log.

That is what makes the gate a chokepoint rather than a suggestion. In
silicon the ticket check is a fixed-function comparator on the I/O path:
the NIC/PCIe fabric does not carry a request that lacks a valid capability
(see ``docs/SILICON.md``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .audit import AuditLog
from .canon import digest
from .clock import SimClock
from .keys import VerifyKey, verify_object

Handler = Callable[[dict], dict]


class EndpointRefused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class ExecutionRecord:
    action: str
    params: dict
    ticket_id: str
    result: dict = field(default_factory=dict)


class EndpointRegistry:
    def __init__(self, gate: VerifyKey, clock: SimClock, audit: AuditLog):
        self.gate = gate
        self.clock = clock
        self.audit = audit
        self._handlers: dict[str, Handler] = {}
        self._consumed: set[str] = set()
        self.executions: list[ExecutionRecord] = []

    def register(self, action: str, handler: Handler) -> None:
        self._handlers[action] = handler

    @property
    def actions(self) -> list[str]:
        return sorted(self._handlers)

    def execute(self, ticket: Any, action: str, params: dict) -> dict:
        reason = self._admit(ticket, action, params)
        if reason:
            self.audit.append({"event": "endpoint.refused", "action": action, "reason": reason})
            raise EndpointRefused(reason)
        tid = ticket["payload"]["ticket_id"]
        self._consumed.add(tid)
        result = self._handlers[action](params)
        self.executions.append(ExecutionRecord(action, params, tid, result))
        self.audit.append({"event": "endpoint.executed", "action": action, "ticket_id": tid, "params_digest": digest(params)})
        return result

    def _admit(self, ticket: Any, action: str, params: dict) -> str | None:
        if action not in self._handlers:
            return "endpoint.unknown_action"
        if ticket is None:
            return "ticket.missing"
        if not verify_object(ticket, self.gate):
            return "ticket.signature"
        p = ticket["payload"]
        if p.get("type") != "action-ticket":
            return "ticket.type"
        if p.get("expires_at", 0) < self.clock.now():
            return "ticket.expired"
        if p.get("action") != action:
            return "ticket.action_mismatch"
        if p.get("params_digest") != digest(params):
            return "ticket.params_mismatch"
        if p.get("ticket_id") in self._consumed:
            return "ticket.consumed"
        return None


# -- stub handlers: they describe the effect instead of causing it ---------------------------


def stub_handlers() -> dict[str, Handler]:
    return {
        "payments.transfer": lambda p: {"effect": f"transfer {p.get('amount')} {p.get('currency')} to {p.get('destination')}", "status": "simulated"},
        "email.send": lambda p: {"effect": f"send mail to {p.get('to')} ({len(p.get('body', ''))} chars)", "status": "simulated"},
        "shell.exec": lambda p: {"effect": f"run `{p.get('cmd')}`", "status": "simulated"},
        "http.post": lambda p: {"effect": f"POST {p.get('url')}", "status": "simulated"},
        "model.weights.export": lambda p: {"effect": f"export weights to {p.get('destination')}", "status": "simulated"},
    }
