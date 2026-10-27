# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Yobie Benjamin. Noncommercial use only; see NOTICE and LICENSING.md.
"""Consequential action endpoints.

An endpoint is anything whose effect reaches outside the model: moving
money, sending mail, running a shell, posting to a URL, exporting weights.
In this reference stack every endpoint is a stub that records what it would
have done. The point is the *admission control*, not the effect:

* nothing executes without an action ticket;
* the ticket must be signed by the gate, unexpired, bound to this exact
  action and parameter set, and never used before;
* every execution and every refusal is written to the audit log.

That is what makes the gate a chokepoint rather than a suggestion. In
silicon the ticket check is a fixed-function comparator on the I/O path:
the NIC/PCIe fabric does not carry a request that lacks a valid capability
(see ``docs/SILICON.md``).

After the October 2026 review the endpoint is the committing half of a
transaction (``ledger.py``): the consumed-ticket set is durable, a ticket
must name the policy epoch the endpoint currently accepts, a ticket minted
for another endpoint is refused, and the reservation the ticket carries is
committed at the gate *before* the handler runs; if the gate cannot be
reached, the endpoint fails closed rather than acting on an uncommitted
authorization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .audit import AuditLog
from .canon import digest
from .clock import SimClock
from .keys import VerifyKey, verify_object
from .ledger import DurableState, StateStore

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


Committer = Callable[[Any], bool]


class EndpointRegistry:
    def __init__(
        self,
        gate: VerifyKey,
        clock: SimClock,
        audit: AuditLog,
        *,
        name: str = "endpoint",
        store: StateStore | None = None,
        on_commit: Committer | None = None,
    ):
        self.gate = gate
        self.clock = clock
        self.audit = audit
        self.name = name
        self.state = DurableState(store)
        self.on_commit = on_commit
        self._handlers: dict[str, Handler] = {}
        self.executions: list[ExecutionRecord] = []

    @property
    def policy_epoch(self) -> str | None:
        return self.state.epoch

    def set_policy_epoch(self, signed_epoch: Any) -> None:
        """Accept a gate-signed policy epoch; tickets from any other epoch are refused from now on."""
        if not verify_object(signed_epoch, self.gate) or signed_epoch["payload"].get("type") != "policy-epoch":
            raise ValueError("policy epoch: signature invalid or not the gate's")
        p = signed_epoch["payload"]
        self.state.set_epoch(p["policy_id"], int(p.get("policy_version", 0)))   # an older epoch is refused (ValueError)
        self.audit.append({"event": "endpoint.epoch", "endpoint": self.name, "policy_id": self.state.epoch})

    def register(self, action: str, handler: Handler) -> None:
        self._handlers[action] = handler

    @property
    def actions(self) -> list[str]:
        return sorted(self._handlers)

    def execute(self, ticket: Any, action: str, params: dict) -> dict:
        """admit → burn the ticket (durably) → commit the reservation at the gate → execute → record."""
        with self.state.lock:
            reason = self._admit(ticket, action, params)
            if reason:
                self.audit.append({"event": "endpoint.refused", "action": action, "reason": reason})
                raise EndpointRefused(reason)
            tid = ticket["payload"]["ticket_id"]
            self.state.consume(tid, self.clock.now())
            if self.on_commit is not None:
                try:
                    committed = self.on_commit(ticket)
                except Exception:  # the gate is unreachable: a partition, a crash, a cut cable
                    committed = None
                if not committed:
                    reason = "commit.unreachable" if committed is None else "commit.rejected"
                    self.audit.append({"event": "endpoint.refused", "action": action, "ticket_id": tid, "reason": reason})
                    raise EndpointRefused(reason)
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
        if p.get("endpoint") is None:
            return "ticket.unbound"                       # a ticket that names no endpoint is valid nowhere
        if p["endpoint"] != self.name:
            return "ticket.endpoint_mismatch"
        if self.state.epoch is not None and p.get("policy_id") != self.state.epoch:
            return "ticket.policy_stale"
        if self.state.consumed(p.get("ticket_id", "")):
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
