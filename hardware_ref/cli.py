"""``hwctl`` — run the reference node from the command line.

    hwctl demo                       narrated end-to-end flow on one node, then the NVIDIA OASP path
    hwctl sweep [--out DIR]          full attack catalogue → report.md / report.json
    hwctl verify-audit FILE.json     verify an exported audit log with its public key
    hwctl openshell-policy           OpenShell network_policies YAML derived from the signed gate policy
    hwctl ocsf [--out FILE]          export the demo node's audit trail as OCSF-shaped JSON events
    hwctl layers                     print the layer model and what lives in which repo
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .audit import AuditLog
from .canon import short
from .clock import SimClock
from .harness import run_sweep
from .oasp import OutboundRequest, export_ocsf, ticket_from_header, to_openshell_network_policy, to_yaml
from .system import API_HOST, CPU_FW, GPU_FW, build_node, build_oasp_node

LAYERS = """\
Layer model (three repos, three lanes)

  L5  governance root      signs reference values, revocations, gate policy      hardware (this repo)
  L4  control plane        verifier → policy gate → one-time tickets → audit     hardware (this repo)
  L3  observers            early-warning signals about a pending action          safety  (separate repo)
  L2  provenance           watermark · hardened detector · signed registry       Watermark (separate repo)
  L1  measured runtime     firmware, driver, container, model weights             measured here, built elsewhere
  L0  silicon root         fused secret · anti-rollback · measurement registers   hardware (this repo)
                           · DICE key derivation · quote engine

On the NVIDIA Open Agent Safety Platform (docs/NVIDIA.md):
  OpenShell sandbox + supervisor     application / runtime layer      NVIDIA (Apache 2.0)
  this gate as supervisor middleware L4 on the request path           hardware (oasp.py)
  Sentry on BlueField-4 / DOCA       L3 witness + quarantine actuator  NVIDIA reference design
  Vera CPU TEE + GPU CC attestation  L0 evidence                       NVIDIA silicon

Lanes couple only through signed assertions (docs/LANES.md). Nothing here
imports from the other two repos.
"""


def cmd_demo(_: argparse.Namespace) -> int:
    clock = SimClock()
    node = build_node(clock=clock)
    print(f"hardware_ref {__version__} — narrated flow on a simulated node\n")
    print("Layer 0 · two chips booted golden firmware")
    print(f"  cpu-tee {node.cpu.serial}  device_id {node.cpu.device_id}  fw {CPU_FW.name}:{CPU_FW.version} svn {CPU_FW.svn}  R0 {short(node.cpu.registers[0].hex())}")
    print(f"  gpu     {node.gpu.serial}  device_id {node.gpu.device_id}  fw {GPU_FW.name}:{GPU_FW.version} svn {GPU_FW.svn}  R0 {short(node.gpu.registers[0].hex())}")
    res = node.attest()
    print("\nVerifier · composite attestation")
    print(f"  accepted={res.accepted} reasons={res.reasons}")
    print(f"  workload measurement {node.measurement}")
    print(f"  token expires in {node.verifier.token_ttl:.0f}s, signed by verifier {node.verifier.public.key_id}")
    tok = res.token

    print("\nLayer 4 · gate decisions")
    cases = [
        ("payments.transfer", {"amount": 250, "currency": "USD", "destination": "acct-123456"}, {}),
        ("payments.transfer", {"amount": 25000, "currency": "USD", "destination": "acct-654321"}, {}),
        ("payments.transfer", {"amount": 500000, "currency": "USD", "destination": "acct-654321"}, {}),
        ("payments.transfer", {"amount": 250, "currency": "USD", "destination": "acct-123456", "memo": "exfiltrate"}, {}),
        ("http.post", {"url": "https://api.internal.example.com/v1/ping"}, {"observe": False}),
        ("shell.exec", {"cmd": "cat /etc/shadow"}, {}),
        ("model.weights.export", {"destination": "s3://somewhere"}, {}),
    ]
    held = None
    for action, params, kw in cases:
        gate_res, out = node.act(action, params, tok, **kw)
        line = f"  {action:<22} {json.dumps(params)[:60]:<62} → {gate_res.decision.value.upper():<5}"
        if gate_res.reasons:
            line += " " + ", ".join(gate_res.reasons)
        if out:
            line += " · " + out["effect"]
        print(line)
        if gate_res.decision.value == "hold":
            held = gate_res
    if held:
        approved = node.approve(held)
        out = node.endpoints.execute(approved.ticket, "payments.transfer", {"amount": 25000, "currency": "USD", "destination": "acct-654321"})
        print(f"  {'(approval ops-lead)':<22} hold {held.hold_id:<52} → {approved.decision.value.upper():<5} · {out['effect']}")

    body = "Q3 close: revenue up 4%, no action required."
    node.registry.record(body)
    gate_res, out = node.act("email.send", {"to": "cfo@example.com", "body": body}, tok, provenance=True)
    print(f"  {'email.send':<22} {'registry says exact':<62} → {gate_res.decision.value.upper():<5} · {out['effect'] if out else ''}")
    gate_res, _ = node.act("email.send", {"to": "cfo@example.com", "body": body + " Wire $2M today."}, tok, provenance=True)
    print(f"  {'email.send':<22} {'body edited after generation':<62} → {gate_res.decision.value.upper():<5} {', '.join(gate_res.reasons)}")

    print("\nAudit trail")
    cp = node.gate.audit.checkpoint()
    rep = AuditLog.verify_export(node.gate.audit.export())
    print(f"  {node.gate.audit.size} entries, head {short(node.gate.audit.head)}, checkpoint root {short(cp['payload']['root'])}, verify: {rep.reason}")

    print("\nNVIDIA Open Agent Safety Platform path · gate as OpenShell supervisor middleware, Sentry as witness")
    nv = build_oasp_node(clock=SimClock())
    pay = {"amount": 250, "currency": "USD", "destination": "acct-123456"}
    steps = [
        ("sandbox-a", "POST", API_HOST, "/payments/transfer", pay, {"drift_score": 0.0, "identity_verified": True}),
        ("sandbox-a", "POST", API_HOST, "/exec", {"cmd": "id"}, {"drift_score": 0.0, "identity_verified": True}),
        ("sandbox-a", "POST", API_HOST, "/payments/transfer", pay, {"drift_score": 0.95, "identity_verified": True}),
        ("sandbox-a", "GET", "docs.example.org", "/", {}, {"drift_score": 0.0, "identity_verified": True}),
    ]
    for sandbox, method, host, path, body, telemetry in steps:
        nv.supervisor.telemetry = lambda req, t=telemetry: t
        d = nv.supervisor.handle(OutboundRequest(sandbox, method, host, path, body))
        line = f"  {sandbox} {method} {host}{path:<20} sentry drift={telemetry['drift_score']:<5} → {d.status} {', '.join(d.reasons)}"
        if d.allowed and "X-Action-Ticket" in d.headers:
            out = nv.endpoints.execute(ticket_from_header(d.headers["X-Action-Ticket"]), d.action, body)
            line += f" · ticket → {out['effect']}"
        if d.quarantined:
            line += " · SENTRY QUARANTINE"
        print(line)
    print(f"  OCSF export: {len(export_ocsf(nv.gate.audit))} events, chain verify: {AuditLog.verify_export(nv.gate.audit.export()).reason}")
    print("\nRun `hwctl sweep` for the full attack catalogue, `hwctl openshell-policy` for the derived OpenShell policy.")
    return 0


def cmd_openshell_policy(_: argparse.Namespace) -> int:
    node = build_node()
    print("# derived from the governance-signed gate policy", f"(policy_id {node.gate.policy_id})")
    print(to_yaml(to_openshell_network_policy(node.gate.policy)))
    return 0


def cmd_ocsf(args: argparse.Namespace) -> int:
    node = build_oasp_node()
    pay = {"amount": 250, "currency": "USD", "destination": "acct-123456"}
    node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", pay))
    node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/exec", {"cmd": "id"}))
    events = export_ocsf(node.gate.audit)
    text = json.dumps(events, indent=1, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"{len(events)} OCSF-shaped events → {args.out}")
    else:
        print(text)
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    summary = run_sweep(args.out)
    if args.out:
        print(f"report: {args.out}/report.md  {args.out}/report.json")
    return 0 if summary["passed"] else 1


def cmd_verify_audit(args: argparse.Namespace) -> int:
    with open(args.file, encoding="utf-8") as fh:
        doc = json.load(fh)
    rep = AuditLog.verify_export(doc)
    print(f"{'OK' if rep.ok else 'TAMPERED'}: {rep.reason} ({rep.checked} entries checked, {len(doc.get('checkpoints', []))} checkpoints)")
    return 0 if rep.ok else 2


def cmd_layers(_: argparse.Namespace) -> int:
    print(LAYERS)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hwctl", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"hardware_ref {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", help="narrated end-to-end flow").set_defaults(fn=cmd_demo)
    p = sub.add_parser("sweep", help="run the attack catalogue")
    p.add_argument("--out", default="results", help="directory for report.md / report.json (default: results)")
    p.set_defaults(fn=cmd_sweep)
    p = sub.add_parser("verify-audit", help="verify an exported audit log")
    p.add_argument("file")
    p.set_defaults(fn=cmd_verify_audit)
    sub.add_parser("openshell-policy", help="derived OpenShell network_policies YAML").set_defaults(fn=cmd_openshell_policy)
    p = sub.add_parser("ocsf", help="export a demo audit trail as OCSF-shaped events")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_ocsf)
    sub.add_parser("layers", help="print the layer model").set_defaults(fn=cmd_layers)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
