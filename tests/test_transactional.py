"""The transactional contract (docs/REVIEW-2026-10.md, point 5; docs/PROTOTYPING.md, Phase 1).

Five things the reviewer asked the first demonstration to show:
  1. allowed operations succeed;
  2. forged, altered, expired and replayed approvals fail;
  3. concurrent requests cannot exceed a shared budget;
  4. host compromise cannot bypass endpoint authorization;
  5. restart, power loss, policy changes and network partitions preserve the specified behaviour.
"""
from __future__ import annotations

import threading

import pytest

from hardware_ref.clock import SimClock
from hardware_ref.endpoints import EndpointRefused
from hardware_ref.gate import request_hash
from hardware_ref.keys import SigningKey, sign_object
from hardware_ref.ledger import DurableState, StateStore
from hardware_ref.system import build_node, default_policy

PAY = {"amount": 250, "currency": "USD", "destination": "acct-123456"}


def _token(node):
    res = node.attest()
    assert res.accepted, res.reasons
    return res.token


# -- the ledger on its own ------------------------------------------------------------------


def test_state_store_is_atomic_and_round_trips(tmp_path):
    path = str(tmp_path / "state.json")
    st = DurableState(StateStore(path))
    st.mark_request("abc", now=10.0)
    st.consume("t1", now=10.0)
    st.set_epoch("pol-1")
    again = DurableState(StateStore(path))
    assert again.seen_request("abc") and again.consumed("t1") and again.epoch == "pol-1"
    assert not list(tmp_path.glob("*.tmp.*")), "no temp file left behind"


def test_reserve_commit_release_and_expiry():
    st = DurableState()
    rid = st.reserve("k", 600, limit=1000, window_s=3600, now=0.0, ttl=60.0)
    assert rid is not None
    assert st.reserve("k", 500, 1000, 3600, now=0.0, ttl=60.0) is None, "reserved amount counts against the limit"
    assert st.commit("k", rid, now=1.0)
    assert not st.commit("k", rid, now=1.0), "a reservation commits once"
    assert st.usage("k", 3600, now=1.0) == {"committed": 600.0, "reserved": 0.0}
    rid2 = st.reserve("k", 400, 1000, 3600, now=1.0, ttl=60.0)
    assert rid2 is not None and st.reserve("k", 1, 1000, 3600, now=1.0, ttl=60.0) is None
    # an unexecuted reservation expires and the capacity comes back
    assert st.reserve("k", 400, 1000, 3600, now=62.0, ttl=60.0) is not None
    # committed charges leave the window
    assert st.usage("k", 3600, now=3700.0)["committed"] == 0.0
    assert not st.release("k", "nope")


def test_concurrent_reservations_never_exceed_the_limit():
    st = DurableState()
    granted: list[str] = []
    lock = threading.Lock()

    def worker():
        rid = st.reserve("shared", 250, limit=2000, window_s=3600, now=0.0, ttl=60.0)
        if rid:
            with lock:
                granted.append(rid)

    threads = [threading.Thread(target=worker) for _ in range(64)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(granted) == 8, f"2000 / 250 = 8 reservations, got {len(granted)}"


# -- through the gate and the endpoint --------------------------------------------------------


def test_allowed_payment_reserves_commits_and_executes():
    node = build_node()
    res, out = node.act("payments.transfer", PAY, _token(node))
    assert res.allowed and out["status"] == "simulated"
    t = res.ticket["payload"]
    assert t["policy_id"] == node.gate.policy_id and t["budget_key"] == "pay-usd-hourly"
    assert node.gate.state.usage("pay-usd-hourly", 3600, node.clock.now()) == {"committed": 250.0, "reserved": 0.0}


def test_budget_is_shared_and_enforced_at_the_gate():
    node = build_node()
    tok = _token(node)
    assert node.act("payments.transfer", {**PAY, "amount": 900}, tok)[0].allowed
    assert node.act("payments.transfer", {**PAY, "amount": 900}, tok)[0].allowed
    res, _ = node.act("payments.transfer", {**PAY, "amount": 900}, tok)
    assert res.reasons == ["budget.exceeded"]
    node.clock.advance(3601)
    assert node.act("payments.transfer", {**PAY, "amount": 900}, _token(node))[0].allowed, "the window moved on (fresh attestation: the old token expired)"


def test_concurrent_requests_cannot_overspend_through_the_gate():
    node = build_node()
    # a policy with the budget but no per-minute rate limit, so the budget is what binds
    pol = default_policy(node.measurement)
    pol["rules"][0].pop("rate_limit")
    node.gate.load_policy(node.governance.policy(pol))
    node.endpoints.set_policy_epoch(node.gate.signed_epoch())
    tok = _token(node)
    reqs = [node.build_request("payments.transfer", PAY, tok) for _ in range(40)]
    results = []
    lock = threading.Lock()

    def worker(req):
        r = node.gate.request(req)
        with lock:
            results.append(r)

    threads = [threading.Thread(target=worker, args=(r,)) for r in reqs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    allowed = [r for r in results if r.allowed]
    assert len(allowed) == 8 and all(r.reasons == ["budget.exceeded"] for r in results if not r.allowed)


def test_ticket_from_a_previous_policy_epoch_is_refused():
    node = build_node()
    res = node.gate.request(node.build_request("payments.transfer", PAY, _token(node)))
    assert res.allowed
    pol = default_policy(node.measurement)
    pol["rules"][0]["constraints"]["amount"]["max"] = 100  # governance tightens the rule
    node.gate.load_policy(node.governance.policy(pol))
    node.endpoints.set_policy_epoch(node.gate.signed_epoch())
    with pytest.raises(EndpointRefused) as exc:
        node.endpoints.execute(res.ticket, "payments.transfer", PAY)
    assert exc.value.reason == "ticket.policy_stale"


def test_endpoint_refuses_an_epoch_not_signed_by_the_gate():
    node = build_node()
    forged = sign_object(SigningKey.generate(), {"type": "policy-epoch", "gate": "gate", "policy_id": "evil", "issued_at": 0})
    with pytest.raises(ValueError):
        node.endpoints.set_policy_epoch(forged)


def test_ticket_bound_to_another_endpoint_is_refused():
    node = build_node()
    pol = default_policy(node.measurement)
    pol["rules"][0]["endpoint"] = "payments-west"
    node.gate.load_policy(node.governance.policy(pol))
    node.endpoints.set_policy_epoch(node.gate.signed_epoch())
    res = node.gate.request(node.build_request("payments.transfer", PAY, _token(node)))
    assert res.allowed and res.ticket["payload"]["endpoint"] == "payments-west"
    with pytest.raises(EndpointRefused) as exc:
        node.endpoints.execute(res.ticket, "payments.transfer", PAY)
    assert exc.value.reason == "ticket.endpoint_mismatch"


def test_requester_supplied_risk_labels_change_nothing():
    node = build_node()
    large = {"amount": 25000, "currency": "USD", "destination": "acct-654321", "risk_class": "reversible", "mode": "auto"}
    req = node.build_request("payments.transfer", large, _token(node))
    req["requirement"] = {"mode": "auto"}  # a compromised broker asks for the fast path
    res = node.gate.request(req)
    assert res.decision.value == "hold" and res.reasons == ["human.approval_required"]


def test_commit_at_the_gate_happens_before_execution_and_fails_closed(monkeypatch):
    node = build_node()
    res = node.gate.request(node.build_request("payments.transfer", PAY, _token(node)))
    assert res.allowed

    def partitioned(_ticket):
        raise ConnectionError("gate unreachable")

    node.endpoints.on_commit = partitioned
    with pytest.raises(EndpointRefused) as exc:
        node.endpoints.execute(res.ticket, "payments.transfer", PAY)
    assert exc.value.reason == "commit.unreachable"
    assert node.endpoints.executions == []
    # the ticket was burned on admission, so a retry after the partition heals needs a new ticket
    node.endpoints.on_commit = node.gate.commit
    with pytest.raises(EndpointRefused) as exc2:
        node.endpoints.execute(res.ticket, "payments.transfer", PAY)
    assert exc2.value.reason == "ticket.consumed"


def test_commit_rejects_a_ticket_the_gate_did_not_sign():
    node = build_node()
    res = node.gate.request(node.build_request("payments.transfer", PAY, _token(node)))
    forged = sign_object(SigningKey.generate(), res.ticket["payload"])
    assert node.gate.commit(forged) is False
    assert node.gate.commit(res.ticket) is True and node.gate.commit(res.ticket) is False


def test_restart_preserves_replay_state_reservations_and_holds(tmp_path):
    clock = SimClock()
    node = build_node(clock=clock, state_dir=str(tmp_path))
    tok = _token(node)
    # 1. a consumed ticket stays consumed across a restart
    res, out = node.act("payments.transfer", PAY, tok)
    assert out is not None
    used_ticket, used_req = res.ticket, None
    # 2. an issued-but-unexecuted ticket's reservation survives the restart
    pending = node.gate.request(node.build_request("payments.transfer", {**PAY, "amount": 1000}, tok))
    assert pending.allowed
    # 3. a hold survives the restart
    held = node.gate.request(node.build_request("payments.transfer", {"amount": 25000, "currency": "USD", "destination": "acct-654321"}, tok))
    assert held.decision.value == "hold"
    replay_req = node.build_request("payments.transfer", PAY, tok)
    node.gate.request(replay_req)  # seen once before the restart

    node.restart()

    with pytest.raises(EndpointRefused) as exc:
        node.endpoints.execute(used_ticket, "payments.transfer", PAY)
    assert exc.value.reason == "ticket.consumed"
    assert node.gate.request(replay_req).reasons == ["request.replayed"]
    # committed: the executed 250; reserved: the pending 1000 and the never-executed replay_req's 250
    assert node.gate.state.usage("pay-usd-hourly", 3600, clock.now()) == {"committed": 250.0, "reserved": 1250.0}
    # the pending ticket is still good after the restart: same gate key, same epoch, live reservation
    assert node.endpoints.execute(pending.ticket, "payments.transfer", {**PAY, "amount": 1000})["status"] == "simulated"
    # and the hold can still be approved
    approved = node.approve(held)
    assert approved.allowed
    assert node.endpoints.execute(approved.ticket, "payments.transfer", {"amount": 25000, "currency": "USD", "destination": "acct-654321"})["status"] == "simulated"


def test_restart_without_state_dir_is_the_old_behaviour():
    node = build_node()
    res, _ = node.act("payments.transfer", PAY, _token(node))
    node.restart()
    # nothing was persisted, so the new gate has no memory — which is exactly why state_dir exists
    assert node.gate.state.usage("pay-usd-hourly", 3600, node.clock.now())["committed"] == 0.0
    assert request_hash({"request_id": "x", "measurement": "m", "action": "a", "params": {}})
