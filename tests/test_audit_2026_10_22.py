"""Regressions for the external audit of 22 October 2026 (findings 3, 4 and 5 against this
repository, and two more of the same kind found while fixing them). Each test failed on 11eb119.

3. The gate's signing key was derived from the two alias public keys, which every quote carries.
4. An approval released a hold that the current policy would refuse.
5. A replayed, older gate-signed epoch moved the endpoint back, and the gate committed the old ticket.
5b. The gate reloaded an older governance-signed policy.
5c. An older revocation list un-revoked a device.
The common cause of 5 to 5c: a signature says who wrote a document, not that it is still current.
"""
import pytest

from hardware_ref.clock import SimClock
from hardware_ref.endpoints import EndpointRefused
from hardware_ref.gate import Decision, make_approval
from hardware_ref.keys import SigningKey, hkdf
from hardware_ref.system import build_node, default_policy

SMALL = {"amount": 50, "currency": "USD", "destination": "acct-111111"}
BIG = {"amount": 5000, "currency": "USD", "destination": "acct-111111"}


def _payments_max(node, cap):
    pol = default_policy(node.measurement)
    for r in pol["rules"]:
        if r["action"] == "payments.transfer":
            r["constraints"]["amount"]["max"] = cap
    return node.governance.policy(pol)


def _no_payments(node):
    pol = default_policy(node.measurement)
    pol["rules"] = [r for r in pol["rules"] if r["action"] != "payments.transfer"]
    return node.governance.policy(pol)


# ---------------------------------------------------------------- 3. the gate key is secret
def test_gate_key_cannot_be_computed_from_public_quotes():
    node = build_node()
    q_cpu, q_gpu = node.cpu.quote("n1"), node.gpu.quote("n2")
    public_seed = hkdf(bytes.fromhex(q_cpu["alias_cert"]["payload"]["subject_pub"]) + bytes.fromhex(q_gpu["alias_cert"]["payload"]["subject_pub"]), b"gate-signing-key", 32)
    assert SigningKey.from_seed(public_seed).public.hex != node.gate.public.hex
    for field in ("subject_pub",):
        assert node.gate.public.hex != q_cpu["alias_cert"]["payload"][field]


def test_gate_key_is_stable_across_restart_and_bound_to_the_chip(tmp_path):
    node = build_node(state_dir=str(tmp_path))
    before = node.gate.public.hex
    node.restart()
    assert node.gate.public.hex == before                       # same chip, same code: same key
    assert build_node().gate.public.hex != before                # another chip: another key


# ---------------------------------------------------------------- 4. holds do not outlive their policy
def test_old_hold_cannot_be_approved_after_the_policy_tightens():
    clock = SimClock()
    node = build_node(clock=clock)
    tok = node.attest().token
    held = node.gate.request(node.build_request("payments.transfer", BIG, tok))
    assert held.decision is Decision.HOLD
    node.gate.load_policy(_payments_max(node, 2000))
    node.endpoints.set_policy_epoch(node.gate.signed_epoch())
    assert not node.gate.request(node.build_request("payments.transfer", BIG, tok)).allowed
    out = node.gate.approve(make_approval(node.approver_key, "ops-lead", held.hold_id, held.request_hash, clock.now()))
    assert not out.allowed and out.reasons in (["approval.unknown_hold"], ["approval.policy_changed"])
    assert node.endpoints.executions == []


def test_a_hold_under_the_current_policy_still_approves():
    clock = SimClock()
    node = build_node(clock=clock)
    tok = node.attest().token
    held = node.gate.request(node.build_request("payments.transfer", BIG, tok))
    out = node.gate.approve(make_approval(node.approver_key, "ops-lead", held.hold_id, held.request_hash, clock.now()))
    assert out.allowed and node.endpoints.execute(out.ticket, "payments.transfer", BIG)["status"] == "simulated"


def test_a_hold_whose_policy_changed_is_refused_even_if_it_survived(tmp_path):
    """Belt and braces: a hold record that somehow outlived its policy (restored from disk, say) is
    checked against the current policy id at approval."""
    clock = SimClock()
    node = build_node(clock=clock)
    tok = node.attest().token
    held = node.gate.request(node.build_request("payments.transfer", BIG, tok))
    node.gate.state.holds[held.hold_id]["policy_id"] = "some-older-policy"
    out = node.gate.approve(make_approval(node.approver_key, "ops-lead", held.hold_id, held.request_hash, clock.now()))
    assert out.reasons == ["approval.policy_changed"]


# ---------------------------------------------------------------- 5. an old epoch cannot come back
def test_replayed_old_epoch_is_refused_and_the_old_ticket_stays_dead():
    node = build_node()
    tok = node.attest().token
    old_epoch = node.gate.signed_epoch()
    res = node.gate.request(node.build_request("payments.transfer", SMALL, tok))
    assert res.allowed
    node.gate.load_policy(_no_payments(node))
    node.endpoints.set_policy_epoch(node.gate.signed_epoch())
    with pytest.raises(EndpointRefused) as e:
        node.endpoints.execute(res.ticket, "payments.transfer", SMALL)
    assert e.value.reason == "ticket.policy_stale"
    with pytest.raises(ValueError):
        node.endpoints.set_policy_epoch(old_epoch)
    with pytest.raises(EndpointRefused):
        node.endpoints.execute(res.ticket, "payments.transfer", SMALL)
    assert node.endpoints.executions == []


def test_the_gate_refuses_to_commit_a_ticket_from_a_replaced_policy():
    """The second lock: even an endpoint whose epoch was set back by hand cannot get an old ticket
    committed, because the gate checks the ticket's policy against its own at commit."""
    node = build_node()
    tok = node.attest().token
    res = node.gate.request(node.build_request("payments.transfer", SMALL, tok))
    old_id = node.endpoints.policy_epoch
    node.gate.load_policy(_no_payments(node))
    node.endpoints.state.data["epoch"] = old_id                 # the endpoint is fooled, by whatever means
    assert node.gate.commit(res.ticket) is False
    with pytest.raises(EndpointRefused):
        node.endpoints.execute(res.ticket, "payments.transfer", SMALL)
    assert node.endpoints.executions == []


def test_gate_refuses_an_older_governance_policy():
    node = build_node()
    first = node.signed_policy
    node.gate.load_policy(_no_payments(node))
    with pytest.raises(ValueError):
        node.gate.load_policy(first)
    assert not node.gate.request(node.build_request("payments.transfer", SMALL, node.attest().token)).allowed


def test_gate_refuses_a_policy_without_a_version():
    node = build_node()
    from hardware_ref.keys import sign_object
    doc = sign_object(node.governance._key, {"type": "gate-policy", "issuer": node.governance.name, "policy": default_policy(node.measurement)})
    with pytest.raises(ValueError):
        node.gate.load_policy(doc)


def test_an_old_revocation_list_cannot_unrevoke_a_device():
    node = build_node()
    v = node.verifier
    old = node.governance.revocations([])
    new = node.governance.revocations(["GPU-7F3A"])
    v.load_revocations(new)
    revoked = set(v.revoked)
    with pytest.raises(ValueError):
        v.load_revocations(old)
    assert v.revoked == revoked


def test_reloading_the_same_document_is_fine_and_restart_keeps_the_newest_policy(tmp_path):
    node = build_node(state_dir=str(tmp_path))
    newest = _no_payments(node)
    node.gate.load_policy(newest)
    node.gate.load_policy(newest)                                # idempotent
    node.endpoints.set_policy_epoch(node.gate.signed_epoch())
    node.restart()                                               # must come back on the newest policy, not the boot one
    assert not node.gate.request(node.build_request("payments.transfer", SMALL, node.attest().token)).allowed
