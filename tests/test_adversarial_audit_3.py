"""Regression tests for adversarial function audit 3 (2026-10-26) in the reference stack.

Every ticket is bound to exactly one endpoint: the rule's own, or the gate's default. An endpoint refuses a ticket that
does not name it, and a ticket that names none is valid nowhere.
"""
import pytest

from hardware_ref.endpoints import EndpointRegistry, stub_handlers
from hardware_ref.system import build_node


def test_a_ticket_is_refused_by_an_endpoint_it_was_not_minted_for():
    node = build_node()
    token = node.attest().token
    req = node.build_request("payments.transfer", {"amount": 10, "currency": "USD", "destination": "acct-123456"}, token)
    res = node.gate.request(req)
    assert res.allowed, res
    assert res.ticket["payload"]["endpoint"] == "endpoint"
    other = EndpointRegistry(node.gate.public, node.clock, node.gate.audit, name="some-other-payment-service", on_commit=node.gate.commit)
    for n, h in stub_handlers().items():
        other.register(n, h)
    with pytest.raises(Exception):
        other.execute(res.ticket, "payments.transfer", req["params"])
    # and the endpoint it was minted for still takes it
    node.endpoints.execute(res.ticket, "payments.transfer", req["params"])
