# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Yobie Benjamin. Noncommercial use only; see NOTICE and LICENSING.md.
"""Regression tests for the adversarial feature and function audit of 26 October 2026 (audit 2, team A), reference
stack. Each was an attack that worked on the code the audit read: one ticket producing effects at two endpoints, a NaN
reservation poisoning a shared budget, and a budgeted rule that charges an unbounded amount. Each now fails."""
import math

from hardware_ref.ledger import DurableState, StateStore
from hardware_ref.policy import validate_policy
from hardware_ref.system import _endpoints, build_node


def test_one_ticket_produces_at_most_one_effect_across_endpoints():
    """endpoints.py:139 accepts a ticket with no endpoint field at any registry; the default rules carry no endpoint
    (system.py:64-98), gate.commit returns True for a ticket with no reservation (gate.py:421-423), and each registry
    keeps its own consumed set. govsim fixed this as F29; the reference stack, the 'protocol' the governor implements,
    did not."""
    node = build_node()
    tok = node.attest().token
    res, out1 = node.act("http.post", {"url": "https://api.internal.example.com/v1/x"}, tok, observe=False)
    assert res.allowed and out1 is not None
    second = _endpoints(node.gate, node.clock, StateStore(None))          # a second device that serves the same action
    executed_twice = True
    try:
        second.execute(res.ticket, "http.post", {"url": "https://api.internal.example.com/v1/x"})
    except Exception:
        executed_twice = False
    assert not executed_twice, "one ticket produced two effects at two endpoints"


def test_a_nan_amount_cannot_poison_a_shared_budget():
    """ledger.py:182-189 has no finite check (govsim's F03 fix is absent here); gate.py:389 lets NaN through because
    NaN < 0 is False. One NaN reservation makes every later 'committed + reserved + amount > limit' false."""
    st = DurableState()
    rid = st.reserve("k", math.nan, limit=1000, window_s=3600, now=0.0, ttl=60.0)
    big = st.reserve("k", 10**9, limit=1000, window_s=3600, now=1.0, ttl=60.0)
    assert rid is None and big is None, "after one NaN reservation the 1,000 limit admitted 1,000,000,000"


def test_a_budgeted_rule_must_bound_the_amount_it_charges():
    """validate_policy accepts a budget whose param has no type or max constraint, which is what lets NaN reach the ledger."""
    pol = {"default": "deny", "observer_freshness_s": 30, "hold_ttl_s": 600,
           "rules": [{"id": "r", "workload": "*", "action": "payments.transfer", "constraints": {},
                      "requirement": {"mode": "auto"},
                      "budget": {"key": "k", "param": "amount", "limit": 1000, "window_s": 3600}}]}
    try:
        validate_policy(pol)
        accepted = True
    except Exception:
        accepted = False
    assert not accepted, "a rule that charges an unconstrained, untyped amount against a budget was accepted"
