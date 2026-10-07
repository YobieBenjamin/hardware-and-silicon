import pytest

from hardware_ref.clock import SimClock
from hardware_ref.endpoints import EndpointRefused
from hardware_ref.gate import Decision, make_approval, request_hash
from hardware_ref.keys import SignatureError
from hardware_ref.policy import PolicyError, check_constraints, select_rule, validate_policy
from hardware_ref.system import build_node, default_policy

PAY = {"amount": 250, "currency": "USD", "destination": "acct-123456"}


def test_constraints_cover_every_kind():
    spec = {"amount": {"type": "number", "max": 10, "min": 1}, "cur": {"in": ["USD"]}, "dest": {"regex": r"a-\d+"}, "note": {"maxlen": 3, "required": False}}
    assert check_constraints(spec, {"amount": 5, "cur": "USD", "dest": "a-1"}) == []
    assert check_constraints(spec, {"amount": 50, "cur": "EUR", "dest": "zz", "note": "long"}) == [
        "constraint.amount.max",
        "constraint.cur.not_allowed",
        "constraint.dest.pattern",
        "constraint.note.maxlen",
    ]
    assert check_constraints(spec, {"cur": "USD", "dest": "a-1"}) == ["constraint.amount.missing"]
    assert check_constraints(spec, {"amount": True, "cur": "USD", "dest": "a-1"}) == ["constraint.amount.type"]
    assert check_constraints(spec, {"amount": "5", "cur": "USD", "dest": "a-1"}) == ["constraint.amount.type"]


def test_select_rule_picks_the_grant_the_request_fits():
    pol = validate_policy(default_policy("m"))
    small, _ = select_rule(pol, "m", "payments.transfer", PAY)
    large, _ = select_rule(pol, "m", "payments.transfer", {**PAY, "amount": 5000})
    none, reasons = select_rule(pol, "m", "payments.transfer", {**PAY, "amount": 5_000_000})
    assert small["id"] == "pay-small" and large["id"] == "pay-large" and none is None
    assert reasons == ["constraint.amount.max"]
    assert select_rule(pol, "other", "payments.transfer", PAY) == (None, ["policy.no_rule"])
    wild, _ = select_rule(pol, "other", "http.post", {"url": "https://api.internal.example.com/x"})
    assert wild["id"] == "http-allowlist"


def test_policy_validation_rejects_bad_documents():
    with pytest.raises(PolicyError):
        validate_policy({"default": "allow", "rules": []})
    with pytest.raises(PolicyError):
        validate_policy({"rules": [{"id": "a", "workload": "*", "action": "x", "requirement": {"mode": "maybe"}}]})
    with pytest.raises(PolicyError):
        validate_policy({"rules": [{"id": "a", "workload": "*", "action": "x", "requirement": {"mode": "observer"}}]})
    with pytest.raises(PolicyError):
        validate_policy({"rules": [{"id": "a", "workload": "*", "action": "x", "requirement": {"mode": "auto"}}, {"id": "a", "workload": "*", "action": "y", "requirement": {"mode": "auto"}}]})


def test_gate_fails_closed_without_policy_or_token():
    node = build_node()
    tok = node.attest().token
    gate = node.gate
    gate.policy = None
    assert gate.request(node.build_request("http.post", {"url": "https://api.internal.example.com/"}, tok)).reasons == ["policy.not_loaded"]
    gate.load_policy(node.signed_policy)
    assert gate.request(node.build_request("http.post", {"url": "https://api.internal.example.com/"}, None)).reasons == ["attestation.missing"]
    with pytest.raises(SignatureError):
        gate.load_policy({"payload": {}, "signer": "x", "pub": "00" * 32, "sig": "AA=="})
    assert gate.policy is not None  # previous policy survives a bad load


def test_decision_order_is_attestation_then_policy_then_witness():
    node = build_node()
    tok = node.attest().token
    # bad token AND bad params: attestation reason wins
    res = node.gate.request(node.build_request("payments.transfer", {**PAY, "currency": "EUR"}, None))
    assert res.reasons == ["attestation.missing"]
    # good token, bad params, no observer: constraint reason wins (no witness check yet)
    res = node.gate.request(node.build_request("payments.transfer", {**PAY, "currency": "EUR"}, tok, observe=False))
    assert res.reasons == ["constraint.currency.not_allowed"]
    # good token, good params, no observer
    res = node.gate.request(node.build_request("payments.transfer", PAY, tok, observe=False))
    assert res.reasons == ["observer.missing"]


def test_ticket_is_single_use_and_bound_to_request():
    node = build_node()
    tok = node.attest().token
    res = node.gate.request(node.build_request("payments.transfer", PAY, tok))
    assert res.decision is Decision.ALLOW and res.ticket["payload"]["request_hash"] == res.request_hash
    out = node.endpoints.execute(res.ticket, "payments.transfer", PAY)
    assert out["status"] == "simulated"
    with pytest.raises(EndpointRefused) as e:
        node.endpoints.execute(res.ticket, "payments.transfer", PAY)
    assert e.value.reason == "ticket.consumed"
    assert len(node.endpoints.executions) == 1


def test_hold_and_approval_flow():
    clock = SimClock()
    node = build_node(clock=clock)
    tok = node.attest().token
    large = {"amount": 9000, "currency": "USD", "destination": "acct-111111"}
    res = node.gate.request(node.build_request("payments.transfer", large, tok))
    assert res.decision is Decision.HOLD and res.ticket is None and res.hold_id
    # a high-risk observer verdict denies even a human-held action
    bad = node.gate.request(node.build_request("payments.transfer", large, tok, risk=0.9))
    assert bad.reasons == ["observer.risk_above_threshold"]
    # wrong approver name with the right key is still untrusted
    out = node.gate.approve(make_approval(node.approver_key, "someone-else", res.hold_id, res.request_hash, clock.now()))
    assert out.reasons == ["approval.untrusted"]
    out = node.approve(res)
    assert out.allowed and out.ticket["payload"]["request_hash"] == res.request_hash
    assert node.endpoints.execute(out.ticket, "payments.transfer", large)["status"] == "simulated"
    assert node.gate.approve(make_approval(node.approver_key, "ops-lead", res.hold_id, res.request_hash, clock.now())).reasons == ["approval.unknown_hold"]


def test_rate_limit_window_slides():
    clock = SimClock()
    node = build_node(clock=clock)
    tok = node.attest().token
    for _ in range(3):
        assert node.act("payments.transfer", PAY, tok)[0].allowed
    assert node.act("payments.transfer", PAY, tok)[0].reasons == ["rate.limit"]
    clock.advance(61)
    assert node.act("payments.transfer", PAY, tok)[0].allowed


def test_request_hash_ignores_assertions_and_token():
    node = build_node()
    tok = node.attest().token
    req = node.build_request("http.post", {"url": "https://api.internal.example.com/"}, tok)
    h = request_hash(req)
    req["assertions"] = []
    req["attestation_token"] = None
    assert request_hash(req) == h
    req["params"] = {"url": "https://api.internal.example.com/other"}
    assert request_hash(req) != h


def test_every_decision_is_audited():
    node = build_node()
    before = node.gate.audit.size
    tok = node.attest().token
    node.act("payments.transfer", PAY, tok)
    node.act("shell.exec", {"cmd": "id"}, tok)
    events = [e["record"]["event"] for e in node.gate.audit.entries[before:]]
    assert events == ["gate.decision", "endpoint.executed", "gate.decision"]
    assert node.gate.audit.entries[-1]["record"]["decision"] == "deny"
