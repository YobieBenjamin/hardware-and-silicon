# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Yobie Benjamin. Noncommercial use only; see NOTICE and LICENSING.md.
"""The NVIDIA Open Agent Safety Platform path: supervisor middleware, policy translation, Sentry, OCSF export."""
from hardware_ref.audit import AuditLog
from hardware_ref.clock import SimClock
from hardware_ref.oasp import OutboundRequest, export_ocsf, granted_hosts, ticket_from_header, to_openshell_network_policy, to_yaml
from hardware_ref.policy import validate_policy
from hardware_ref.system import API_HOST, build_node, build_oasp_node, default_policy

PAY = {"amount": 250, "currency": "USD", "destination": "acct-123456"}


def test_supervised_request_gets_a_ticket_the_endpoint_accepts():
    node = build_oasp_node()
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", PAY))
    assert d.allowed and d.status == 200 and d.gate.rule_id == "pay-small"
    ticket = ticket_from_header(d.headers["X-Action-Ticket"])
    assert node.endpoints.execute(ticket, "payments.transfer", PAY)["status"] == "simulated"


def test_hold_surfaces_as_202_with_hold_id():
    node = build_oasp_node()
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", {**PAY, "amount": 20000}))
    assert not d.allowed and d.status == 202 and d.headers["X-Hold-Id"] == d.gate.hold_id
    approved = node.approve(d.gate)
    assert approved.allowed


def test_quarantine_blocks_everything_until_released():
    node = build_oasp_node()
    node.supervisor.telemetry = lambda req: {"drift_score": 0.95, "identity_verified": True}
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", PAY))
    assert d.quarantined and node.actuator.is_quarantined("sandbox-a")
    node.supervisor.telemetry = lambda req: {"drift_score": 0.0, "identity_verified": True}
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "GET", "docs.example.org", "/", {}))
    assert d.status == 403 and d.reasons == ["sandbox.quarantined"]
    node.actuator.release("sandbox-a", "ops-lead")
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", PAY))
    assert d.allowed
    events = [e["record"]["event"] for e in node.gate.audit.entries]
    assert "sentry.quarantine" in events and "sentry.release" in events


def test_drift_window_slides():
    clock = SimClock()
    node = build_oasp_node(clock=clock)
    for _ in range(4):
        node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/exec", {"cmd": "id"}))
    assert not node.actuator.is_quarantined("sandbox-a")
    clock.advance(node.supervisor.drift.window_s + 1)
    node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/exec", {"cmd": "id"}))
    assert not node.actuator.is_quarantined("sandbox-a")  # old denials aged out


def test_both_observers_can_be_required():
    node = build_node(observer=["obs-main", "sentry"])
    tok = node.attest().token
    # the generic path attaches only obs-main → sentry missing
    res = node.gate.request(node.build_request("payments.transfer", PAY, tok))
    assert res.reasons == ["observer.missing"]
    req = node.build_request("payments.transfer", PAY, tok)
    from hardware_ref.gate import request_hash

    req["assertions"].append(node.sentry.assess(request_hash(req), {"drift_score": 0.0}))
    assert node.gate.request(req).allowed


def test_policy_translation_matches_gate_egress():
    pol = validate_policy(default_policy("m"))
    doc = to_openshell_network_policy(pol)
    hosts = {ep["host"] for v in doc["network_policies"].values() for ep in v["endpoints"]}
    assert hosts == granted_hosts(pol) == {API_HOST, "mail.internal.example.com"}
    assert doc["network_policies"]["http_allowlist"]["endpoints"][0]["access"] == "read-only"
    text = to_yaml(doc)
    assert text.startswith("network_policies:") and "enforcement: enforce" in text and "- path: /usr/bin/curl" in text


def test_ocsf_export_keeps_chain_evidence():
    node = build_oasp_node()
    node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/exec", {"cmd": "id"}))
    events = export_ocsf(node.gate.audit)
    assert all({"category_uid", "class_uid", "activity_id", "severity_id", "time", "metadata", "unmapped"} <= set(e) for e in events)
    deny = events[-1]
    assert deny["status"] == "Failure" and deny["unmapped"]["hash"] == node.gate.audit.entries[-1]["hash"]
    assert AuditLog.verify_export(node.gate.audit.export()).ok


def test_second_witness_on_the_supervisor_path():
    node = build_oasp_node(observer=["sentry", "obs-main"])
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", PAY))
    assert d.reasons == ["observer.missing"]  # safety lane absent → fail closed
    node.supervisor.add_witness(lambda rh, action, params: node.observer.assess(rh, action, params))
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", PAY))
    assert d.allowed


def test_high_authority_rules_can_demand_both_witnesses():
    node = build_oasp_node(high_authority_observer=["sentry", "obs-main"])
    assert node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", PAY)).allowed
    large = {**PAY, "amount": 25000}
    assert node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", large)).reasons == ["observer.missing"]
    node.supervisor.add_witness(lambda rh, action, params: node.observer.assess(rh, action, params))
    assert node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", large)).status == 202


# -- OpenShell's shipped middleware contract (allow or deny, one reason code, no hold) --------------


def test_openshell_reason_codes_follow_the_grammar():
    from hardware_ref.oasp import OPENSHELL_REASON_RE, openshell_reason_code

    for ours in ["sandbox.quarantined", "attestation.missing", "attestation.expired", "observer.missing", "observer.risk_above_threshold",
                 "provenance.status_tampered", "human.approval_required", "policy.no_rule", "budget.exceeded", "Ticket-Replay", "9lives", ""]:
        assert OPENSHELL_REASON_RE.match(openshell_reason_code(ours)), ours
    assert openshell_reason_code("attestation.missing") == "attestation_missing"
    assert len(openshell_reason_code("x" * 200)) == 64


def test_openshell_sees_only_the_code_never_our_text():
    from hardware_ref.oasp import to_openshell

    node = build_oasp_node()
    node.supervisor.refresh_token("sandbox-a", None)  # host never attested
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", PAY))
    r = to_openshell(d)
    assert not r.allow and r.reason_code == "attestation_missing" and r.header_changes == []
    err = r.sandbox_error()
    assert set(err) == {"error", "detail", "policy", "middleware", "reason_code"} and err["error"] == "middleware_denied"
    assert all(v != "attestation.missing" for v in err.values())  # the dotted form, like any free text of ours, never reaches the sandbox


def test_openshell_allow_carries_the_ticket_as_a_header_change():
    from hardware_ref.oasp import to_openshell

    node = build_oasp_node()
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", PAY))
    r = to_openshell(d)
    assert r.allow and r.reason_code is None
    assert [c["name"] for c in r.header_changes] == ["X-Action-Ticket"] and r.header_changes[0]["write"] == "overwrite"
    assert node.endpoints.execute(ticket_from_header(r.header_changes[0]["value"]), "payments.transfer", PAY)["status"] == "simulated"


def test_hold_is_a_denial_on_openshell_and_the_approved_retry_gets_the_ticket_once():
    from hardware_ref.gate import make_approval
    from hardware_ref.oasp import HOLD_PENDING, to_openshell

    node = build_oasp_node()
    big = {**PAY, "amount": 20000}
    req = OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", big)
    first = node.supervisor.handle(req)
    assert to_openshell(first).reason_code == HOLD_PENDING and to_openshell(first).sandbox_error()["reason_code"] == HOLD_PENDING
    hold_id = first.gate.hold_id
    # asking again while held does not open a second hold
    again = node.supervisor.handle(req)
    assert to_openshell(again).reason_code == HOLD_PENDING and again.headers["X-Hold-Id"] == hold_id and len(node.gate.state.holds) == 1
    # another sandbox on the same attested host sending the same request is held separately, never handed this sandbox's outcome
    node.supervisor.bind_sandbox("sandbox-b", node.measurement, node.supervisor._sandboxes["sandbox-a"]["token"])
    other = node.supervisor.handle(OutboundRequest("sandbox-b", "POST", API_HOST, "/payments/transfer", big))
    assert to_openshell(other).reason_code == HOLD_PENDING and other.gate.hold_id != hold_id
    # the approval arrives out of band, through the middleware, which parks the ticket for sandbox-a's retry
    approval = make_approval(node.approver_key, "ops-lead", hold_id, first.gate.request_hash, node.clock.now())
    assert node.supervisor.approve(approval).allowed
    retry_b = node.supervisor.handle(OutboundRequest("sandbox-b", "POST", API_HOST, "/payments/transfer", big))
    assert to_openshell(retry_b).reason_code == HOLD_PENDING  # sandbox-b is still waiting on its own hold
    retry = node.supervisor.handle(req)
    r = to_openshell(retry)
    assert r.allow and [c["name"] for c in r.header_changes] == ["X-Action-Ticket"]
    ticket = ticket_from_header(r.header_changes[0]["value"])
    assert node.endpoints.execute(ticket, "payments.transfer", big)["status"] == "simulated"
    # the parked ticket is consumed: a third try is a fresh hold, not a replay
    third = node.supervisor.handle(req)
    assert to_openshell(third).reason_code == HOLD_PENDING and third.gate.hold_id not in (None, hold_id)
    events = [e["record"]["event"] for e in node.gate.audit.entries]
    assert "supervisor.retry_after_approval" in events


def test_openshell_quarantine_code_and_findings_count_only():
    from hardware_ref.oasp import to_openshell

    node = build_oasp_node()
    node.supervisor.telemetry = lambda req: {"drift_score": 0.95, "identity_verified": True}
    d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", PAY))
    r = to_openshell(d)
    assert not r.allow and r.findings == len(d.reasons) >= 1 and r.metadata["quarantined"] is True
    d2 = node.supervisor.handle(OutboundRequest("sandbox-a", "GET", "docs.example.org", "/", {}))
    assert to_openshell(d2).reason_code == "sandbox_quarantined"
