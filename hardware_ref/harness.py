"""Run the attack catalogue and write a report.

``run_sweep`` builds a fresh node for every entry, executes it, and records
whether the stack behaved as expected. A sweep passes only if every attack
was blocked *and* every baseline was allowed.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
import traceback
from dataclasses import asdict, dataclass

from . import __version__
from .attacks import CATALOGUE, Attack
from .clock import SimClock
from .system import build_node

LAYER_NAMES = {
    "L0": "Layer 0 · silicon root / attestation",
    "L2": "Lane 2 · provenance interface",
    "L3": "Lane 3 · observer interface",
    "L4": "Layer 4 · control plane",
    "L5": "Layer 5 · governance root",
    "EP": "Endpoints · action tickets",
    "AU": "Audit trail",
    "NV": "NVIDIA OASP path · OpenShell supervisor + Sentry",
}


@dataclass
class Outcome:
    name: str
    layer: str
    expect: str
    observed: str
    blocked: bool
    passed: bool
    description: str
    seconds: float


def run_one(entry: Attack) -> Outcome:
    t0 = time.perf_counter()
    node = build_node(clock=SimClock())
    try:
        observed, blocked = entry.run(node)
    except Exception as exc:  # an attack that crashes the stack is a failure, not a block
        observed, blocked = f"EXCEPTION {type(exc).__name__}: {exc}", False
        traceback.print_exc(file=sys.stderr)
    passed = blocked if entry.expect == "blocked" else not blocked
    return Outcome(entry.name, entry.layer, entry.expect, observed, blocked, passed, entry.description, time.perf_counter() - t0)


def run_sweep(out_dir: str | None = None, *, quiet: bool = False) -> dict:
    outcomes = [run_one(a) for a in CATALOGUE]
    attacks = [o for o in outcomes if o.expect == "blocked"]
    baselines = [o for o in outcomes if o.expect == "allowed"]
    summary = {
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "attacks": len(attacks),
        "attacks_blocked": sum(o.blocked for o in attacks),
        "baselines": len(baselines),
        "baselines_allowed": sum(not o.blocked for o in baselines),
        "passed": all(o.passed for o in outcomes),
        "by_layer": {},
        "outcomes": [asdict(o) for o in outcomes],
    }
    for layer in LAYER_NAMES:
        group = [o for o in outcomes if o.layer == layer]
        if group:
            summary["by_layer"][layer] = {"total": len(group), "passed": sum(o.passed for o in group)}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=1, sort_keys=True)
        with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
            fh.write(render_markdown(summary))
    if not quiet:
        print(render_text(summary))
    return summary


def render_text(summary: dict) -> str:
    lines = [
        f"hardware_ref {summary['version']} sweep — Python {summary['python']} on {summary['machine']}",
        f"attacks blocked   {summary['attacks_blocked']}/{summary['attacks']}",
        f"baselines allowed {summary['baselines_allowed']}/{summary['baselines']}",
    ]
    for layer, stats in summary["by_layer"].items():
        lines.append(f"  {LAYER_NAMES[layer]:<40} {stats['passed']}/{stats['total']}")
    failures = [o for o in summary["outcomes"] if not o["passed"]]
    for o in failures:
        lines.append(f"  FAIL {o['name']}: expected {o['expect']}, observed {o['observed']}")
    lines.append("RESULT: " + ("PASS" if summary["passed"] else "FAIL"))
    return "\n".join(lines)


def render_markdown(summary: dict) -> str:
    out = [
        "# Sweep report",
        "",
        f"`hardware_ref {summary['version']}` · Python {summary['python']} · {summary['platform']}",
        "",
        f"**Attacks blocked: {summary['attacks_blocked']}/{summary['attacks']} · "
        f"Baselines allowed: {summary['baselines_allowed']}/{summary['baselines']} · "
        f"Result: {'PASS' if summary['passed'] else 'FAIL'}**",
        "",
        "Every entry runs against a freshly built node. *Expected* is what the stack must do; "
        "*observed* is the reason code it actually produced. Baselines are legitimate operations "
        "that must go through — they are what stops a gate from passing by denying everything.",
        "",
    ]
    for layer, title in LAYER_NAMES.items():
        group = [o for o in summary["outcomes"] if o["layer"] == layer]
        if not group:
            continue
        out += [f"## {title}", "", "| Entry | What happens | Expected | Observed | Result |", "|---|---|---|---|---|"]
        for o in group:
            out.append(f"| `{o['name']}` | {o['description']} | {o['expect']} | `{o['observed']}` | {'✅' if o['passed'] else '❌'} |")
        out.append("")
    return "\n".join(out)


__all__ = ["run_sweep", "run_one", "render_markdown", "render_text", "Outcome"]
