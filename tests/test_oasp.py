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
