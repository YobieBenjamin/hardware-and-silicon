"""End to end: manufacture → boot → attest → request → gate → ticket → endpoint → audit → verify, then the sweep."""
from hardware_ref.audit import AuditLog
from hardware_ref.harness import CATALOGUE, run_sweep
from hardware_ref.system import build_node

PAY = {"amount": 250, "currency": "USD", "destination": "acct-123456"}


def test_full_flow_once():
    node = build_node()
    res = node.attest()
    assert res.accepted
    gate_res, out = node.act("payments.transfer", PAY, res.token)
    assert gate_res.allowed and out["status"] == "simulated"
    denied, _ = node.act("shell.exec", {"cmd": "id"}, res.token)
    assert denied.reasons == ["policy.no_rule"]
    node.gate.audit.checkpoint()
    report = AuditLog.verify_export(node.gate.audit.export())
    assert report.ok
    events = [e["record"]["event"] for e in node.gate.audit.entries]
    assert events[0] == "gate.policy_loaded" and "endpoint.executed" in events


def test_sweep_blocks_every_attack_and_allows_every_baseline(tmp_path):
    summary = run_sweep(str(tmp_path), quiet=True)
    failures = [o for o in summary["outcomes"] if not o["passed"]]
    assert failures == [], failures
    assert summary["attacks_blocked"] == summary["attacks"] >= 50
    assert summary["baselines_allowed"] == summary["baselines"] == 8
    assert (tmp_path / "report.md").exists() and (tmp_path / "report.json").exists()


def test_catalogue_names_are_unique_and_layered():
    names = [a.name for a in CATALOGUE]
    assert len(names) == len(set(names))
    assert {a.layer for a in CATALOGUE} == {"L0", "L2", "L3", "L4", "L5", "EP", "AU", "NV"}
