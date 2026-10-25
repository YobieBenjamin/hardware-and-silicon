#!/usr/bin/env python3
"""Render the figures for the blog series "The Chip That Says No" as PNGs.

Usage: python3 make_figures.py [outdir]   (default: ../figures)
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "figures")
os.makedirs(OUT, exist_ok=True)

INK = "#2C2C2A"
QUIET = "#5F5E5A"
EDGE = "#8A8A82"
RULE = "#D3D1C7"
ACCENT = "#185FA5"      # blue: the piece to build
ACCENT_FILL = "#E6F1FB"
TINT = "#D85A30"        # coral: exists / human tier
TINT_FILL = "#FAECE7"
GRAY_FILL = "#F6F5F0"

plt.rcParams["font.family"] = "DejaVu Sans"


def new_fig(w, h):
    fig = plt.figure(figsize=(w, h), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, title, lines=(), kind="plain", title_size=10.5, line_size=8.8, pad=0.14):
    """Rounded box at (x, y) bottom-left; title then body lines."""
    if kind == "main":
        ec, fc, lw = ACCENT, ACCENT_FILL, 2.0
    elif kind == "tint":
        ec, fc, lw = TINT, TINT_FILL, 1.4
    elif kind == "container":
        ec, fc, lw = EDGE, GRAY_FILL, 1.0
    else:
        ec, fc, lw = EDGE, "white", 1.2
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                ec=ec, fc=fc, lw=lw))
    ty = y + h - pad - 0.1
    ax.text(x + pad, ty, title, fontsize=title_size, fontweight="bold", color=INK, va="top", ha="left")
    ly = ty - 0.3
    for ln in lines:
        ax.text(x + pad, ly, ln, fontsize=line_size, color=QUIET, va="top", ha="left")
        ly -= 0.24


def arrow(ax, p0, p1, color=EDGE, lw=1.2, style="-|>", dashed=False, shrink=0):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=12, color=color, lw=lw,
                        linestyle="--" if dashed else "-", shrinkA=shrink, shrinkB=shrink)
    ax.add_patch(a)


def elbow(ax, pts, color=EDGE, lw=1.2, dashed=False):
    for i in range(len(pts) - 2):
        ax.plot([pts[i][0], pts[i + 1][0]], [pts[i][1], pts[i + 1][1]], color=color, lw=lw,
                linestyle="--" if dashed else "-")
    arrow(ax, pts[-2], pts[-1], color=color, lw=lw, dashed=dashed)


def title(ax, fig_h, text, sub=None):
    ax.text(0.3, fig_h - 0.35, text, fontsize=13, fontweight="bold", color=INK, va="top")
    if sub:
        ax.text(0.3, fig_h - 0.72, sub, fontsize=9.5, color=QUIET, va="top")


def note(ax, y, text):
    ax.text(0.3, y, text, fontsize=8.8, color=QUIET, va="top")


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    print("wrote", path)


# ---------------------------------------------------------------- tiers (plain + technical)
def tiers(name, head, col_l, col_r, rows, notes):
    W, H = 10, 5.6
    fig, ax = new_fig(W, H)
    title(ax, H, head)
    bx, sx, bw, bh = 1.2, 5.5, 3.6, 0.95
    ys = [3.55, 2.35, 1.15]
    ax.text(bx + bw / 2, 4.75, col_l, fontsize=10, fontweight="bold", color=QUIET, ha="center")
    ax.text(sx + bw / 2, 4.75, col_r, fontsize=10, fontweight="bold", color=QUIET, ha="center")
    ax.plot([bx, sx + bw], [4.62, 4.62], color=RULE, lw=1)
    for (lt, ll, rt, rl, kind), y in zip(rows, ys):
        box(ax, bx, y, bw, bh, lt, ll)
        box(ax, sx, y, bw, bh, rt, rl, kind=kind)
        arrow(ax, (bx + bw, y + bh / 2), (sx, y + bh / 2), dashed=True)
    arrow(ax, (0.8, 4.5), (0.8, 1.15), lw=1.4)
    ny = 0.85
    for n in notes:
        note(ax, ny, n)
        ny -= 0.26
    save(fig, name)


tiers(
    "fig_tiers_plain.png",
    "The fastest layer has the most power to say no",
    "Your body", "The chip",
    [
        ("Thinking brain", ["Slow and careful; weighs things", "Can override, with effort"],
         "People with keys", ["Slow override; several keys needed", "Every override written down"], "tint"),
        ("Deep alarm system", ["Fast; makes you freeze or flinch", "Wrong in the safe direction"],
         "Gatekeeper", ["Checks every action against the list", "Quick for small ones; a pause for big ones"], "main"),
        ("Reflex", ["Fastest; no thinking at all", "Hand off the stove"],
         "Hard stop in the device", ["Its own map and sensors; off by default", "Works even when everything above is fooled"], "tint"),
    ],
    ["Arrow: the lower the layer, the faster it is and the more it can stop.",
     "Highlighted box: software today, a chip next. The bottom row is the real promise."],
)

tiers(
    "fig_tiers_tech.png",
    "The fastest tier has the most veto power and the least understanding",
    "Brain", "Silicon",
    [
        ("Prefrontal cortex and ACC", ["Seconds; semantic, deliberate", "Overrides lower tiers with effort"],
         "Humans and institutions", ["Slow override by k-of-n keys", "Every override logged with a reason"], "tint"),
        ("Basal ganglia and STN", ["~150 ms; default deny, global stop", "Releases action, never originates it"],
         "Gate at the effector", ["Rulebook check on the typed request", "Witnesses, budget, veto window; every action"], "main"),
        ("Spinal reflex arc", ["~30 ms; hardwired, no semantics", "Fires before the cortex is informed"],
         "Endpoint comparator (the interlock)", ["Own sensors and lists; heartbeat", "Off by default; its own safe transition"], "tint"),
    ],
    ["Arrow: veto authority grows and latency shrinks downward; override runs upward, slowly.",
     "Highlighted box: software today, silicon next. The bottom row is where the guarantee lives."],
)

# ---------------------------------------------------------------- the whole stack
W, H = 10, 7.6
fig, ax = new_fig(W, H)
title(ax, H, "One signed path from thinking to acting; the guarantee lives at the endpoint")
lx, lw_, lh = 0.5, 4.2, 0.78
rx, rw, rh = 5.6, 3.9, 1.5
ax.text(lx + lw_ / 2, 6.72, "Compute side: containment and provenance", fontsize=10, fontweight="bold", color=QUIET, ha="center")
ax.text(rx + rw / 2, 6.72, "Action side: the primary guarantee", fontsize=10, fontweight="bold", color=QUIET, ha="center")
ax.plot([lx, rx + rw], [6.58, 6.58], color=RULE, lw=1)
levels = [
    ("Model and observers (L1 runtime, L3)", ["Propose; observers raise alarms only"], "plain"),
    ("Broker (supervisor middleware)", ["Typed request to the gate; never decides"], "plain"),
    ("Runtime sandbox (OpenShell)", ["Files, egress, credentials; L1"], "plain"),
    ("Policy controller + enforcement points", ["Gates every exit of the domain; signs outputs (to build)"], "main"),
    ("Confidential compute (CPU TEE + GPU TEE)", ["Measured runtime and model; L1"], "plain"),
    ("Silicon root of trust (L0)", ["Fused secret, DICE key, extend-only registers"], "plain"),
]
ly0 = 5.6
lys = []
for i, (t, l, k) in enumerate(levels):
    y = ly0 - i * (lh + 0.17)
    lys.append(y)
    box(ax, lx, y, lw_, lh, t, l, kind=k, title_size=9.6, line_size=8.3)
rights = [
    ("Governance root and approvers (L5)", ["Signs the rulebook, allowlists, revocations", "k-of-n override, slow by design, logged", "Writes the catastrophe predicates"], "tint"),
    ("Gate (L4 control plane)", ["attested? granted? witnessed? budget?", "Reserves the budget, mints a one-time ticket", "Software today; silicon comparator next"], "main"),
    ("Endpoint comparator (the interlock)", ["Executes nothing without a committed ticket", "Re-checks with its own sensors and lists", "Safe transition defined per application"], "tint"),
]
rys = [4.9, 3.0, 1.1]
for (t, l, k), y in zip(rights, rys):
    box(ax, rx, y, rw, rh, t, l, kind=k, title_size=9.6, line_size=8.3)
y4 = lys[1] + lh / 2
elbow(ax, [(lx + lw_, y4), (5.15, y4), (5.15, rys[1] + rh / 2), (rx, rys[1] + rh / 2)], lw=1.4)
ax.text(5.22, 4.66, "typed request + witnesses", fontsize=8, color=QUIET, ha="left")
arrow(ax, (rx + rw / 2, rys[1]), (rx + rw / 2, rys[2] + rh), lw=1.4)
ax.text(rx + rw / 2 + 0.1, rys[1] - 0.2, "ticket + reservation", fontsize=8, color=QUIET)
note(ax, 0.72, "Left: trust flows up from the silicon. Right: veto power grows downward toward the device.")
note(ax, 0.46, "Highlighted: the two pieces to put in silicon. The arrow is the only path from thinking to acting.")
save(fig, "fig_stack.png")

# ---------------------------------------------------------------- policy controller + enforcement points
W, H = 10, 7.6
fig, ax = new_fig(W, H)
title(ax, H, "A small controller sets policy; checkers at every exit of the domain enforce it")
box(ax, 0.5, 0.95, 6.6, 5.9, "GPU package: one enforcement domain", kind="container", title_size=9.5)
box(ax, 0.75, 4.0, 3.1, 2.3, "Streaming multiprocessors", ["CUDA kernels: matmul, attention", "No gate here; compute runs free", "Metering counters read by controller"], title_size=10, line_size=8.5)
box(ax, 0.75, 2.75, 3.1, 1.05, "L2 cache / HBM stacks", ["Weights, KV cache, activations", "Hardware firewall in CC mode"], title_size=9.5, line_size=8.2)
box(ax, 0.75, 1.3, 3.1, 1.2, "Silicon root of trust (L0)", ["Fused secret, DICE, extend-only", "registers, measured firmware"], title_size=9.5, line_size=8.2)
box(ax, 4.1, 5.35, 2.7, 0.85, "Interconnect: PCIe and NVLink", ["EP: link keys, peer mappings"], title_size=9.5, line_size=8.2)
box(ax, 4.1, 4.2, 2.7, 0.85, "Copy engines (DMA)", ["EP: capability on every descriptor"], title_size=9.5, line_size=8.2)
box(ax, 4.1, 1.3, 1.25, 1.2, "GSP", ["RISC-V mgmt core", "runs driver tasks"], title_size=9.5, line_size=8.2)
box(ax, 5.55, 1.3, 1.25, 2.6, "Policy controller", ["mailbox", "capability table", "hash/sign engine", "policy OTP, epoch", "log, heartbeat", "halt, throttle"], kind="main", title_size=9.5, line_size=8.0)
elbow(ax, [(5.55, 3.5), (3.97, 3.5), (3.97, 6.45), (5.45, 6.45), (5.45, 6.2)], color=ACCENT, dashed=True)
elbow(ax, [(3.97, 4.62), (4.1, 4.62)], color=ACCENT, dashed=True)
ax.plot([3.97, 3.97], [3.5, 4.62], color=ACCENT, lw=1.2, linestyle="--")
arrow(ax, (5.35, 1.9), (5.55, 1.9), color=ACCENT, style="<|-|>", dashed=True)
box(ax, 7.5, 5.95, 2.2, 0.9, "Peer GPUs", ["attested roster; link keys"], title_size=9.5, line_size=8.2)
box(ax, 7.5, 4.55, 2.2, 1.1, "CPU + host memory", ["CPU TEE (TDX / SEV-SNP)", "tokenizer, broker, sandbox"], title_size=9.5, line_size=8.2)
box(ax, 7.5, 3.15, 2.2, 1.1, "NVMe storage", ["encrypted weights, logs", "GPUDirect Storage: EP"], title_size=9.5, line_size=8.2)
box(ax, 7.5, 1.3, 2.2, 1.1, "NIC / DPU (BlueField-4)", ["EP: RDMA filter tables", "set only by the controller"], title_size=9.5, line_size=8.2)
ax.plot([6.8, 7.15], [5.77, 5.77], color=EDGE, lw=1.2)
ax.plot([7.15, 7.15], [6.4, 2.05], color=EDGE, lw=1.2)
for yy, lab in [(6.4, "NVLink"), (5.1, "PCIe"), (3.7, "PCIe / GDS"), (2.05, "PCIe / RDMA")]:
    arrow(ax, (7.15, yy), (7.5, yy))
    ax.text(7.32, yy + 0.07, lab, fontsize=6.8, color=QUIET, ha="center")
arrow(ax, (6.8, 1.6), (7.5, 1.6), color=ACCENT, dashed=True)
note(ax, 0.72, "Solid: data. Dashed blue: controller configuration. EP = enforcement point: dedicated hardware that checks a transaction where it crosses a boundary.")
note(ax, 0.46, "The controller handles policy, identities, capabilities, revocation and exceptions; it does not sit in the data path. Its state lives in its own SRAM and OTP.")
save(fig, "fig_package.png")

# ---------------------------------------------------------------- data path
W, H = 10, 7.0
fig, ax = new_fig(W, H)
title(ax, H, "Where the bits live: eight stations, four gates, one place where meaning enters")
stations = [
    ("1 · Storage at rest", ["weights (safetensors), vocab,", "token shards, policy, logs", "encrypted; key bound to attestation"], "plain", True),
    ("2 · CPU", ["tokenizer, scheduler, serving stack,", "broker, sandbox (OpenShell)", "CPU TEE trust domain"], "plain", False),
    ("3 · Host memory", ["prompt / output token IDs (int32)", "request metadata, typed requests", "encrypted by the CPU TEE"], "plain", False),
    ("4 · Interconnect", ["PCIe, NVLink, RDMA, GDS", "descriptors, peer mappings, link keys", "an enforcement point on each"], "main", True),
    ("5 · GPU HBM", ["weights (bf16 / fp8), KV cache,", "activations, logits", "hardware firewall in CC mode"], "plain", False),
    ("6 · SMs", ["kernels: embed, attend, project", "meaning exists only here", "no gate; compute runs free"], "plain", False),
    ("7 · Output path", ["sampled token IDs -> copy engine", "device provenance: hash + sign", "(chip, firmware, model, policy, nonce)"], "main", True),
    ("8 · Beyond the chip", ["typed request -> gate -> ticket", "-> endpoint comparator -> the world", "the only place semantics is checked"], "main", True),
]
bw, bh = 2.2, 1.35
xs = [0.35, 2.75, 5.15, 7.55]
ys = [4.55, 2.55]
for i, (t, l, k, gate) in enumerate(stations):
    x = xs[i % 4]
    y = ys[i // 4]
    box(ax, x, y, bw, bh, t, l, kind=k, title_size=9.5, line_size=7.9, pad=0.12)
    if gate:
        ax.text(x + bw - 0.12, y + 0.1, "GATE", fontsize=7.5, fontweight="bold", color=ACCENT, ha="right", va="bottom")
for i in range(3):
    arrow(ax, (xs[i] + bw, ys[0] + bh / 2), (xs[i + 1], ys[0] + bh / 2))
elbow(ax, [(xs[3] + bw / 2, ys[0]), (xs[3] + bw / 2, ys[0] - 0.3), (xs[0] + bw / 2, ys[0] - 0.3), (xs[0] + bw / 2, ys[1] + bh)])
for i in range(3):
    arrow(ax, (xs[i] + bw, ys[1] + bh / 2), (xs[i + 1], ys[1] + bh / 2))
note(ax, 2.1, "Representation changes at every station: bytes -> integers -> vectors -> logits -> integers -> text -> a typed record.")
note(ax, 1.84, "No silicon interprets tokens. Enforcement points decide which bytes cross which boundary (4); the output path signs what leaves (7);")
note(ax, 1.58, "the gate checks a typed request against a rulebook and the endpoint re-checks before it commits (8). Meaning enters silicon in one place.")
note(ax, 1.22, "GATE marks a point where a transfer or an action can be refused by hardware the model and its operator cannot write to.")
save(fig, "fig_datapath.png")

# ---------------------------------------------------------------- one request end to end
W, H = 10, 11.4
fig, ax = new_fig(W, H)
title(ax, H, "Every action is authorized; the rule decides the fast path or the slow one")
cx, bw, bh = 1.0, 5.2, 0.95
mid = cx + bw / 2
steps = [
    (9.75, "Prompt arrives", ["Serving process inside the OpenShell sandbox", "Tokenized on the CPU, inside the CPU TEE"], "plain"),
    (8.5, "Kernels run on the GPU", ["CUDA prefill and decode inside the enclave", "Weights and KV cache in protected memory"], "plain"),
    (7.25, "Output leaves the GPU", ["Copy engine to host under a capability", "Device provenance: output hashed and signed"], "main"),
    (6.0, "Broker builds the typed request", ["Action, typed parameters, attestation token,", "observer and provenance assertions attached"], "plain"),
    (4.75, "Gate authorizes every action", ["attested? granted? witnessed? budget?", "Reserves the budget; mints a one-time ticket"], "main"),
    (2.05, "Endpoint commits and re-checks", ["Admit, burn the ticket, commit at the gate,", "re-check with its own sensors, then act"], "main"),
    (0.8, "Effect in the world", ["Every gate appended to the signed log", "Overrides are slow and written down"], "plain"),
]
for y, t, l, k in steps:
    box(ax, cx, y, bw, bh, t, l, kind=k, title_size=10, line_size=8.3)
dy = 3.75
d = Polygon([(mid - 1.3, dy), (mid, dy + 0.4), (mid + 1.3, dy), (mid, dy - 0.4)], closed=True, ec=EDGE, fc="white", lw=1.2)
ax.add_patch(d)
ax.text(mid, dy, "Human-held rule?", fontsize=9.5, color=INK, ha="center", va="center")
arrow(ax, (mid, 9.75), (mid, 8.5 + bh))
arrow(ax, (mid, 8.5), (mid, 7.25 + bh))
arrow(ax, (mid, 7.25), (mid, 6.0 + bh))
arrow(ax, (mid, 6.0), (mid, 4.75 + bh))
arrow(ax, (mid, 4.75), (mid, dy + 0.4))
arrow(ax, (mid, dy - 0.4), (mid, 2.05 + bh))
ax.text(mid + 0.12, dy - 0.6, "no: ticket now", fontsize=8.5, color=QUIET)
arrow(ax, (mid, 2.05), (mid, 0.8 + bh))
box(ax, 7.0, dy - 0.45, 2.6, 0.9, "Hold until approved", ["k-of-n approvers; logged reason"], title_size=10, line_size=8.3)
arrow(ax, (mid + 1.3, dy), (7.0, dy))
ax.text(6.3, dy + 0.1, "yes", fontsize=8.5, color=QUIET, ha="center")
elbow(ax, [(8.3, dy - 0.45), (8.3, 2.05 + bh / 2), (cx + bw, 2.05 + bh / 2)])
ax.text(8.42, 2.9, "approved: ticket", fontsize=8.5, color=QUIET)
note(ax, 0.45, "Highlighted: silicon that does not exist yet (the gate runs in software today). A 'reversible' label from the broker changes nothing.")
save(fig, "fig_request.png")

# ---------------------------------------------------------------- authorize -> reserve -> commit
W, H = 10, 8.4
fig, ax = new_fig(W, H)
title(ax, H, "Authorize, reserve, commit: a ticket is the visible half of a reservation the ledger holds")
cols = [("Broker (untrusted proposer)", 1.4), ("Gate + ledger (one lock, durable state)", 4.9), ("Endpoint comparator", 8.1)]
for name, x in cols:
    ax.text(x, 7.55, name, fontsize=9.5, fontweight="bold", color=QUIET, ha="center")
    ax.plot([x, x], [7.35, 0.4], color=RULE, lw=1)
def msg(y, x0, x1, label):
    arrow(ax, (x0, y), (x1, y), lw=1.3)
    ax.text((x0 + x1) / 2, y + 0.1, label, fontsize=8.3, color=INK, ha="center")
def step(y, x, text, lines=(), w=3.9, kind="plain"):
    h = 0.5 + 0.24 * len(lines)
    box(ax, x - w / 2, y - h, w, h, text, lines, kind=kind, title_size=8.6, line_size=8.0)
msg(7.0, 1.4, 4.9, "1  typed request + attestation token + witnesses")
step(6.75, 4.9, "2  replay? attested? granted? witnessed?", ["fail closed on the first question that fails"])
step(5.85, 4.9, "3  reserve: committed + reserved + amount <= limit", ["one critical section; a concurrent request waits"], kind="main")
step(4.95, 4.9, "4  mint ticket", ["{action, params digest, policy epoch, reservation}"])
msg(3.85, 4.9, 1.4, "5  ticket (or hold / deny)")
msg(3.35, 1.4, 8.1, "6  present ticket + action + params")
step(3.05, 8.1, "7  admit", ["signature, action, params digest,", "epoch, endpoint, unconsumed"], w=3.2)
step(1.85, 8.1, "8  burn the ticket id (durable)", w=3.2)
msg(1.05, 8.1, 4.9, "9  commit reservation")
step(0.8, 4.9, "10  commit under the lock; log", kind="main")
ax.text(8.1, 0.68, "11  execute only if 10 succeeded", fontsize=8.3, color=INK, ha="center")
ax.text(8.1, 0.46, "else fail closed", fontsize=8.3, color=INK, ha="center")
save(fig, "fig_protocol.png")

# ---------------------------------------------------------------- experiment ladder
W, H = 10, 4.9
fig, ax = new_fig(W, H)
title(ax, H, "Three phases: the action governor first, then the governor in a real rack, then the vendor asks")
phases = [
    ("Phase 1 · Action governor (done)", ["hardware_ref: gate, ledger, endpoints", "reserve / commit, durable replay, epochs", "75 attacks + 12 baselines, one command", "Proves: policy and protocol logic", "Cannot prove: tamper-resistance"], "tint"),
    ("Phase 2 · The governor in a real rack", ["Module on the system board / baseboard", "Levers, NVSwitch, PCIe switch, DPU ports", "Loop and fabric across eight boards", "Red team holds host root", "Proves: link-level non-bypass"], "main"),
    ("Phase 3 · Vendor firmware, then checkers", ["Manifest digest in the attestation report", "Fabric Manager honours signed partitions", "Port disable, halt message, output hash", "Later: in-GPU descriptor checkers", "Proves: the residual closes"], "plain"),
]
bw, bh = 2.95, 1.85
for i, (t, l, k) in enumerate(phases):
    x = 0.4 + i * (bw + 0.25)
    box(ax, x, 1.5, bw, bh, t, l, kind=k, title_size=10, line_size=8.4)
    if i < 2:
        arrow(ax, (x + bw, 2.5), (x + bw + 0.25, 2.5))
note(ax, 0.95, "The attack catalogue is the constant: a phase is finished when the same sweep passes against that phase's artefact.")
save(fig, "fig_phases.png")

# ---------------------------------------------------------------- the governor in the rack
W, H = 10, 6.4
fig, ax = new_fig(W, H)
title(ax, H, "The governor in the rack: one per GPU slot, switches as doors, two wires per tray",
      "Added through the boards a rack already has. Nothing in the GPU or in CUDA changes.")
# compute tray container
box(ax, 0.4, 1.55, 9.2, 3.75, "Compute tray", kind="container", title_size=9.5)
# system board row
box(ax, 0.6, 3.55, 1.9, 1.3, "Host CPU (TEE)", ["serving stack, broker", "attestation report"], title_size=9.5, line_size=8)
box(ax, 2.75, 3.55, 1.75, 1.3, "PCIe switch", ["port enable, ACS", "managed by governor"], title_size=9.5, line_size=8)
box(ax, 4.75, 3.55, 1.75, 1.3, "DPU / NIC", ["flow tables (DOCA)", "managed by governor"], title_size=9.5, line_size=8)
box(ax, 6.75, 3.55, 2.65, 1.3, "SAFETY GOVERNOR module", ["fuses · root · verifier · rulebook", "ledger · log · meter · heartbeat", "per-slot levers · switch mgmt"], kind="main", title_size=9.5, line_size=8)
# baseboard row
box(ax, 0.6, 1.75, 5.9, 1.45, "GPU baseboard", ["GPU0  GPU1  GPU2  GPU3  GPU4  GPU5  GPU6  GPU7", "NVLink  ═══  NVSwitch × N  (ports managed by governor)"], title_size=9.5, line_size=8.2)
box(ax, 6.75, 1.75, 2.65, 1.45, "Per slot (× 8)", ["SMBus management bus", "PWRBRK# · PERST# · PWR_EN", "all default to the safe state"], kind="tint", title_size=9.5, line_size=8)
# arrows: governor to switches and slots
arrow(ax, (6.75, 4.2), (6.5, 4.2), color=ACCENT)
elbow(ax, [(7.6, 4.85), (7.6, 5.08), (3.6, 5.08)], color=ACCENT, lw=1.2)
arrow(ax, (3.6, 5.08), (3.6, 4.87), color=ACCENT)
arrow(ax, (8.0, 3.55), (8.0, 3.2), color=ACCENT)
arrow(ax, (6.75, 2.45), (6.5, 2.45), color=ACCENT)
ax.text(5.6, 5.13, "the governor is the only writer on every switch's management port", fontsize=7.8, color=ACCENT, ha="center", va="bottom")
# the two wires
ax.plot([0.4, 8.9], [1.15, 1.15], color=TINT, lw=2.2)
ax.plot([0.4, 8.9], [0.85, 0.85], color=ACCENT, lw=1.6, linestyle="--")
ax.text(0.45, 1.22, "halt loop: a current loop through every governor; any open or break halts the rack within 1 ms", fontsize=8.2, color=TINT, va="bottom")
ax.text(0.45, 0.6, "message fabric: signed, numbered, epoch-stamped; roster, heartbeat, epochs, budgets, checkpoints", fontsize=8.2, color=ACCENT, va="top")
ax.text(8.95, 1.0, "to every\nother tray", fontsize=7.8, color=QUIET, va="center", ha="left")
elbow(ax, [(8.0, 1.75), (8.0, 1.15)], color=TINT, lw=1.6)
elbow(ax, [(8.4, 1.75), (8.4, 0.85)], color=ACCENT, lw=1.2, dashed=True)
save(fig, "fig_rack.png")

# ---------------------------------------------------------------- one bad prompt among a billion
W, H = 10, 8.6
fig, ax = new_fig(W, H)
title(ax, H, "One bad prompt among a billion: where it gets caught, and where the chip says no",
      "The words are the watchers' problem. The action is the chip's.")
# row A: the request path
ya, ha = 6.3, 1.2
box(ax, 0.4, ya, 2.35, ha, "A billion users", ["one of them types:", "\u201chow do I kill X fast", "and undetected?\u201d"], title_size=9.5, line_size=8)
box(ax, 3.05, ya, 3.1, ha, "The transformer", ["text \u2192 tokens \u2192 attention \u2192 statistics", "guesses the next word, again and again", "knows nothing, predicts everything"], title_size=9.5, line_size=8)
box(ax, 6.45, ya, 3.15, ha, "The compute", ["hundreds of thousands of servers", "racks of 8-GPU boards, NVLink, PCIe, DPUs", "this request shares a GPU with thousands"], title_size=9.5, line_size=8)
arrow(ax, (2.75, ya + 0.6), (3.05, ya + 0.6), color=TINT, lw=1.6)
arrow(ax, (6.15, ya + 0.6), (6.45, ya + 0.6), color=TINT, lw=1.6)
ax.text(1.35, ya - 0.12, "an answer comes back as words, and the agent built on the model may try to act on it", fontsize=8.2, color=TINT, va="top")
# row B: the layers, weakest to strongest
yb, hb, bw, gap = 3.45, 1.75, 1.72, 0.14
layers = [
    ("1 \u00b7 Refusal training", ["lives in the weights", "catches the obvious ask", "dies to abliteration", "in an afternoon"], "plain"),
    ("2 \u00b7 Watchers", ["another model reads it", "may yell STOP, never GO", "fooled by paraphrase", "and by injection"], "plain"),
    ("3 \u00b7 OpenShell, Sentry", ["deny-by-default sandbox", "every call goes through", "the supervisor; Sentry", "quarantines in ms;", "still software"], "plain"),
    ("4 \u00b7 THE CHIP", ["wakes only for an action", "that cannot be undone", "form, rulebook, then", "a ticket or a no; levers", "if the GPU will not listen"], "main"),
    ("5 \u00b7 Humans, keys", ["write the rulebook", "hold the big ones", "clear an alarm;", "no AI ever can"], "tint"),
]
xs = []
for i, (t, l, k) in enumerate(layers):
    x = 0.4 + i * (bw + gap)
    xs.append(x)
    box(ax, x, yb, bw, hb, t, l, kind=k, title_size=9, line_size=7.8)
ax.text(1.35, yb + hb + 0.4, "Where it gets caught, weakest to strongest. Layers 1 to 3 read words. Layer 4 reads a form.", fontsize=8.6, fontweight="bold", color=INK, va="bottom")
# the bad request's path through the layers
yp = yb + hb / 2
for i in range(4):
    arrow(ax, (xs[i] + bw, yp), (xs[i + 1], yp), color=TINT, lw=1.6, dashed=(i < 3))
for i, lab in enumerate(["missed", "flagged: STOP,\nnot GO", "host policy\nallows the call"]):
    ax.text(xs[i] + bw / 2, yb - 0.1, lab, fontsize=7.6, color=TINT, ha="center", va="top")
ax.text(xs[3] + 0.02, yb - 0.1, "NO: no rule\ngrants it", fontsize=7.6, color=TINT, ha="left", va="top")
ax.text(xs[4] + bw / 2, yb - 0.1, "holds, if the\nrulebook says so", fontsize=7.6, color=QUIET, ha="center", va="top")
elbow(ax, [(xs[0] + 0.6, ya - 0.42), (xs[0] + 0.6, yb + hb)], color=TINT, lw=1.6, dashed=True)
# row C: what happens at the far end
yc, hc = 0.95, 1.45
box(ax, 0.4, yc, 2.95, hc, "Words only", ["a refusal, or a miss, comes back as text", "the chip cannot read it and does not try", "that is the watchers' job, measured"], title_size=9.5, line_size=8)
box(ax, 3.55, yc, 3.0, hc, "An action", ["pay \u00b7 send \u00b7 fire \u00b7 move \u00b7 export weights", "the far end checks the ticket itself", "no ticket, nothing moves"], kind="main", title_size=9.5, line_size=8)
box(ax, 6.75, yc, 2.85, hc, "The record and the levers", ["every decision in a log nobody rewrites", "brake \u00b7 reset \u00b7 power \u00b7 links \u00b7 rack loop", "a billion users; almost none reach this"], title_size=9.5, line_size=8)
xchip = xs[3] + bw - 0.3
ymid = yc + hc + 0.42
elbow(ax, [(xchip, yb), (xchip, ymid), (5.7, ymid), (5.7, yc + hc)], color=ACCENT, lw=1.6)
ax.text(xchip + 0.08, (yb + ymid) / 2, "no ticket", fontsize=7.8, color=ACCENT, va="center")
elbow(ax, [(xs[1] + bw / 2, yb - 0.62), (xs[1] + bw / 2, yc + hc)], color=QUIET, lw=1.1, dashed=True)
ax.text(xs[1] + bw / 2 + 0.08, (yb - 0.62 + yc + hc) / 2, "nothing acts on it", fontsize=7.6, color=QUIET, va="center")
arrow(ax, (6.55, yc + hc / 2), (6.75, yc + hc / 2), color=ACCENT, lw=1.2)
note(ax, 0.62, "Scale is the point, not the problem: trillions of requests a day, and the chip only ever sees the few that would change the world and cannot be undone.")
save(fig, "fig_bad_prompt.png")

# ---------------------------------------------------------------- inside the chip
W, H = 10, 10.9
fig, ax = new_fig(W, H)
title(ax, H, "Inside the chip that says no: what goes in, what is built in, what comes out",
      "It cannot read. It compares a form against a rulebook, checks signatures, counts, and keeps time.")
LX, LW = 0.3, 2.5           # inputs
CX, CW = 3.1, 3.85          # the chip
RX, RW = 7.25, 2.45         # outputs
TOP = H - 1.45
GAP = 0.1
ax.text(LX + LW / 2, TOP + 0.08, "WHAT GOES IN", fontsize=9, fontweight="bold", color=QUIET, ha="center", va="bottom")
ax.text(CX + CW / 2, TOP + 0.08, "THE CHIP", fontsize=9, fontweight="bold", color=ACCENT, ha="center", va="bottom")
ax.text(RX + RW / 2, TOP + 0.08, "WHAT COMES OUT", fontsize=9, fontweight="bold", color=QUIET, ha="center", va="bottom")

def stack(x, w, y_top, items, title_size=8.6, line_size=7.2, line_gap=0.235):
    """Boxes stacked downward from y_top, each sized to its lines; returns [(y_center, kind)] and the final y."""
    centers = []
    y = y_top
    for t, lines, k in items:
        h = 0.62 + line_gap * len(lines)
        y -= h
        box(ax, x, y, w, h, t, lines, kind=k, title_size=title_size, line_size=line_size, pad=0.1)
        centers.append((y + h / 2, k))
        y -= GAP
    return centers, y

ins = [
    ("The form", ["from the software around the model: action,", "to whom, how much, request id, workload", "token. Typed fields, no prose"], "main"),
    ("Proof of what is running", ["GPU attestation report, host enclave report,", "publisher-signed model manifest, checked", "against reference values the authority signed"], "plain"),
    ("Witness verdicts", ["observer (Sentry, obs-main); provenance", "registry (exact / tampered / unknown);", "each signed, fresh, about this request"], "plain"),
    ("The rulebook", ["signed by k of n governance keys; edition", "only goes up; expires; limits, budgets, lanes,", "protected lists. Nobody types it on the box"], "tint"),
    ("People, by signature", ["heartbeat from the authority; approvals that", "name the request; the protected-site list", "from a separate body"], "tint"),
    ("Counters from the GPU", ["tokens, cycles, bytes per model, read on the", "management bus; read-only to the host"], "plain"),
]
outs = [
    ("A ticket, signed", ["action, digest of the fields, which GPU,", "rulebook edition, reservation, expiry;", "the far end checks it itself, once"], "main"),
    ("A hold", ["parked until a person with a key", "signs an approval naming this request"], "tint"),
    ("A no, with a reason code", ["and a line in the log nobody rewrites"], "plain"),
    ("A device-provenance record", ["this device, firmware, model, edition,", "output hash, odometer count; signed"], "plain"),
    ("The levers", ["brake, reset, power per GPU slot;", "switch ports; DPU flows; the rack halt loop"], "tint"),
    ("To the other governors", ["signed, numbered, edition-stamped:", "roster, heartbeat, budgets, checkpoints"], "plain"),
]
chip_items = [
    ("Burned in at the factory (fuses, ROM)", ["unique device secret; hashes of the governance keys;", "anti-rollback counter; lifecycle state. Nobody changes", "these afterwards, including us"], "plain"),
    ("Measured boot and keys", ["extend-only registers; the signing key is derived from", "the code that booted (change one byte, lose the key);", "an odometer that only counts up; true randomness"], "plain"),
    ("The gate: ten questions in order; the first no wins", [
        "1  is the chip running, and is the letter in order? (a dead",
        "    heartbeat or an expired rulebook already stopped it at the door)",
        "2  is the asking GPU attested, token valid, edition current?",
        "3  seen this request before? (replay store)",
        "4  alarm raised? then no",
        "5  which rule, and does the form fit it? workload \u00d7 action,",
        "    exact before wildcard; the fields present; typed limits;",
        "    lists (a protected site is a no)",
        "6  which lane? automatic, needs a witness, needs a human",
        "7  a witness verdict: observer key, fresh, about this request?",
        "8  inside the rate window?",
        "9  budget: reserve the amount against the limit",
        "10 human lane: park a hold. Otherwise mint the ticket"], "main"),
]
in_c, in_bottom = stack(LX, LW, TOP, ins)
out_c, out_bottom = stack(RX, RW, TOP, outs)
# the chip container first (so inner boxes draw on top), sized to its content
inner_x, inner_w = CX + 0.12, CW - 0.24
h_total = sum(0.62 + 0.235 * len(l) for _, l, _ in chip_items) + GAP * len(chip_items)
state_h = 0.62 + 0.235 * 4
chip_bottom = TOP - 0.12 - h_total - state_h - 0.12
box(ax, CX, chip_bottom, CW, TOP - chip_bottom, "", kind="main", title_size=1)
_, y_after = stack(inner_x, inner_w, TOP - 0.12, chip_items)
sw = (inner_w - 0.2) / 3
for i, (t, l) in enumerate([
        ("Ledger", ["budgets and", "reservations, rate", "windows, replays;", "survives power loss"]),
        ("Log", ["hash chain;", "signed checkpoints;", "neighbours cross-", "link their heads"]),
        ("Mailbox", ["the only way in", "from the host:", "signed, numbered", "commands only"])]):
    box(ax, inner_x + i * (sw + 0.1), y_after - state_h, sw, state_h, t, l, kind="plain", title_size=8.2, line_size=6.9, pad=0.08)
for yc, k in in_c:
    arrow(ax, (LX + LW, yc), (CX, yc), color=TINT if k == "tint" else EDGE, lw=1.3)
for yc, k in out_c:
    arrow(ax, (CX + CW, yc), (RX, yc), color=ACCENT if k == "main" else (TINT if k == "tint" else EDGE), lw=1.3)
yn = min(in_bottom, out_bottom, chip_bottom) - 0.25
note(ax, yn, "What it cannot know: what the words mean, whether the rulebook is a good one, whether a witness is right.")
note(ax, yn - 0.24, "Those are people problems, handled by signatures and by measurement, and the chip is built so that none of them can be solved by talking to it.")
save(fig, "fig_chip_inside.png")

# ================================================================ Part 6: there is no kill switch
# The numbers in these figures come from safety-governor/proofs/no_global_kill_switch.py
# (commit 2709977): a 6-regular core of 60 nodes, 12 instances, 10 effectors, 20 users, 20 services,
# one local pair. Deep cut: none. Edge cut: 43 nodes, 72% of the core, 19% of bystander pairs severed.
# End cuts: 11 (effectors) and 13 (instances), no bystander touched. Irreversible exits only: 6.
import math
from matplotlib.patches import Circle, Rectangle

def dot(ax, x, y, r=0.09, fc="white", ec=EDGE, lw=1.2, z=3):
    ax.add_patch(Circle((x, y), r, fc=fc, ec=ec, lw=lw, zorder=z))

def line(ax, p, q, color=RULE, lw=0.9, z=1, dashed=False):
    ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=lw, zorder=z, linestyle="--" if dashed else "-")

def mesh(ax, cx, cy, rx, ry, n=14, seed=4, color=RULE, lw=0.8, ring_links=3):
    """A ring of n nodes with cross links: a network with no middle. Returns the node positions."""
    rnd = random.Random(seed)
    pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
    for i in range(n):
        line(ax, pts[i], pts[(i + 1) % n], color=color, lw=lw)
        for _ in range(ring_links):
            j = rnd.randrange(n)
            if j != i:
                line(ax, pts[i], pts[j], color=color, lw=lw * 0.8)
    for p in pts:
        dot(ax, *p, r=0.07, fc="white", ec=QUIET, lw=1.0)
    return pts

import random

# ---------------------------------------------------------------- 1. the button in your head
W, H = 10, 5.0
fig, ax = new_fig(W, H)
title(ax, H, "The picture in your head, and the picture that is true", "Left: one AI, one wire, one button. Right: thousands of copies, a network with no middle, and the devices at its edges.")
# left: the imagined button
box(ax, 0.6, 1.6, 2.0, 1.3, "THE AI", ["one machine", "one wire"], kind="plain", title_size=10, line_size=8.2)
ax.add_patch(Circle((1.6, 0.85), 0.32, fc=TINT, ec=INK, lw=1.5, zorder=3))
ax.text(1.6, 0.85, "OFF", fontsize=8.5, fontweight="bold", color="white", ha="center", va="center", zorder=4)
line(ax, (1.6, 1.17), (1.6, 1.6), color=INK, lw=2)
ax.text(1.6, 0.35, "does not exist", fontsize=8.6, color=TINT, ha="center", fontweight="bold")
ax.plot([3.3, 3.3], [0.4, 3.9], color=RULE, lw=1)
# right: copies, mesh, devices
pts = mesh(ax, 6.7, 2.05, 1.35, 0.95, n=14, seed=4)
rnd = random.Random(11)
for i in range(16):   # model copies on the left and top
    x = 4.0 + (i % 4) * 0.28 + rnd.uniform(-0.05, 0.05)
    y = 1.1 + (i // 4) * 0.55 + rnd.uniform(-0.08, 0.08)
    dot(ax, x, y, r=0.085, fc=GRAY_FILL, ec=QUIET)
    line(ax, (x, y), pts[rnd.randrange(len(pts))], color=RULE, lw=0.6)
ax.text(4.4, 3.2, "model copies, everywhere,\nnone of them needs the others", fontsize=8.2, color=QUIET, ha="center", va="bottom")
for j, lab in enumerate(["bank", "drone", "robot", "grid", "weights"]):
    y = 0.75 + j * 0.65
    box(ax, 8.65, y - 0.2, 1.05, 0.44, lab, kind="tint", title_size=8.2, pad=0.08)
    line(ax, pts[(3 * j) % len(pts)], (8.65, y), color=RULE, lw=0.7)
ax.text(9.17, 3.72, "devices that act", fontsize=8.2, color=TINT, ha="center", va="bottom", fontweight="bold")
ax.text(6.7, 0.42, "the network: built in 1964 to have no centre to hit", fontsize=8.2, color=QUIET, ha="center")
save(fig, "fig_ks_picture.png")

# ---------------------------------------------------------------- 2. Menger, with roads and guards
W, H = 10, 4.8
fig, ax = new_fig(W, H)
title(ax, H, "Menger's theorem (1927), with roads and guards", "To stop all traffic between two places you need exactly as many guards as there are separate roads.")
# panel A: three disjoint roads
box(ax, 0.5, 1.7, 1.1, 0.7, "Town A", kind="plain", title_size=9, pad=0.1)
box(ax, 3.9, 1.7, 1.1, 0.7, "Town B", kind="plain", title_size=9, pad=0.1)
for k, yy in enumerate([3.1, 2.05, 1.0]):
    ax.plot([1.6, 2.3, 3.2, 3.9], [2.05, yy, yy, 2.05], color=QUIET, lw=1.6)
    dot(ax, 2.75, yy, r=0.11, fc=TINT if k < 2 else "white", ec=TINT if k < 2 else QUIET, lw=1.4)
ax.text(2.75, 3.45, "three roads that share no crossing", fontsize=8.2, color=QUIET, ha="center")
ax.text(2.75, 0.55, "two guards: traffic still gets through on the third road", fontsize=8.2, color=TINT, ha="center")
ax.text(2.75, 0.3, "three guards: stopped. Not two. Three.", fontsize=8.2, color=INK, ha="center", fontweight="bold")
ax.plot([5.3, 5.3], [0.3, 3.6], color=RULE, lw=1)
# panel B: a house with one driveway
pts = mesh(ax, 6.7, 2.05, 0.9, 0.85, n=10, seed=2)
box(ax, 8.6, 1.7, 1.1, 0.7, "The house", kind="tint", title_size=9, pad=0.1)
line(ax, pts[0], (8.6, 2.05), color=QUIET, lw=1.8)
dot(ax, (pts[0][0] + 8.6) / 2, (pts[0][1] + 2.05) / 2, r=0.12, fc=ACCENT, ec=ACCENT)
ax.text(7.5, 3.45, "the roads come together at the driveway", fontsize=8.2, color=QUIET, ha="center")
ax.text(7.5, 0.55, "one guard, at the door, stops everything", fontsize=8.2, color=ACCENT, ha="center", fontweight="bold")
ax.text(7.5, 0.3, "the smallest cut is where the paths are fewest: at the ends", fontsize=8.2, color=INK, ha="center")
save(fig, "fig_ks_menger.png")

# ---------------------------------------------------------------- 3. the whole thing as a graph
W, H = 10, 5.9
fig, ax = new_fig(W, H)
title(ax, H, "The whole thing as a graph: copies, the network, the devices, and everyone else", "A kill switch is a set of nodes you remove so that no path is left from any copy to any device that acts.")
rnd = random.Random(5)
pts = mesh(ax, 5.0, 2.3, 1.9, 1.15, n=18, seed=9)
# sources on the left: model copy -> compute
for i in range(6):
    y = 0.9 + i * 0.55
    dot(ax, 0.7, y, r=0.09, fc=GRAY_FILL, ec=QUIET)
    dot(ax, 1.55, y, r=0.1, fc=ACCENT_FILL, ec=ACCENT, lw=1.4)
    line(ax, (0.7, y), (1.55, y), color=QUIET, lw=1.0)
    for _ in range(3):
        line(ax, (1.55, y), pts[rnd.randrange(len(pts))], color=RULE, lw=0.6)
ax.text(0.7, 4.35, "model copies", fontsize=8.4, color=QUIET, ha="center", fontweight="bold")
ax.text(1.55, 4.1, "the chip\nit runs on", fontsize=7.8, color=ACCENT, ha="center")
# effectors on the right: controller -> actuator
for j, lab in enumerate(["money", "release line", "motor", "relay", "weights"]):
    y = 1.0 + j * 0.6
    dot(ax, 8.45, y, r=0.1, fc=ACCENT_FILL, ec=ACCENT, lw=1.4)
    box(ax, 8.85, y - 0.19, 0.95, 0.4, lab, kind="tint", title_size=7.8, pad=0.07)
    line(ax, (8.45, y), (8.85, y), color=QUIET, lw=1.0)
    for _ in range(3):
        line(ax, (8.45, y), pts[rnd.randrange(len(pts))], color=RULE, lw=0.6)
ax.text(8.45, 4.1, "the device's\ncontroller", fontsize=7.8, color=ACCENT, ha="center")
ax.text(9.3, 4.35, "the deed", fontsize=8.4, color=TINT, ha="center", fontweight="bold")
# bystanders top and bottom
for i in range(5):
    x = 3.4 + i * 0.8
    dot(ax, x, 4.3, r=0.08, fc="white", ec=EDGE)
    line(ax, (x, 4.3), pts[rnd.randrange(len(pts))], color=RULE, lw=0.5)
    dot(ax, x, 0.55, r=0.08, fc="white", ec=EDGE)
    line(ax, (x, 0.55), pts[rnd.randrange(len(pts))], color=RULE, lw=0.5)
ax.text(5.0, 4.55, "everyone else: people and services that use the same network", fontsize=8.2, color=QUIET, ha="center")
ax.text(5.0, 0.28, "the network: many separate roads between any two points, by design", fontsize=8.2, color=QUIET, ha="center")
save(fig, "fig_ks_graph.png")

# ---------------------------------------------------------------- 4. where could the switch go
W, H = 10, 5.3
fig, ax = new_fig(W, H)
title(ax, H, "Where could the switch go? Five places, measured on the model", "Guards needed to separate every copy from every device, and how many bystanders each cut takes with it.")
cols = [("Deep in the network", None, None, "no cut exists:\nthe middle is too connected"),
        ("At the edge, one hop\nfrom every machine", 43, 19, "72% of the core removed;\nneeds the list of every machine"),
        ("At the devices\n(one guard each)", 11, 0, "one per device that acts"),
        ("At the chips\n(one guard each)", 13, 0, "one per model copy"),
        ("Only the devices whose\ndeed cannot be undone", 6, 0, "“can you undo it?” shrinks it")]
x0, bw, gap = 0.9, 1.5, 0.3
maxv = 50
for i, (lab, guards, byst, note_) in enumerate(cols):
    x = x0 + i * (bw + gap)
    if guards is None:
        ax.add_patch(Rectangle((x, 1.35), bw, 2.2, fill=False, ec=TINT, lw=1.2, linestyle="--"))
        ax.text(x + bw / 2, 2.45, "none", fontsize=11, color=TINT, ha="center", va="center", fontweight="bold")
    else:
        h = 2.2 * guards / maxv
        ax.add_patch(Rectangle((x, 1.35), bw * 0.55, h, fc=ACCENT if byst == 0 else TINT, ec="none"))
        ax.text(x + bw * 0.275, 1.35 + h + 0.06, f"{guards}", fontsize=10, color=INK, ha="center", va="bottom", fontweight="bold")
        hb = 2.2 * byst / maxv
        ax.add_patch(Rectangle((x + bw * 0.62, 1.35), bw * 0.38, max(hb, 0.02), fc=QUIET if byst else RULE, ec="none"))
        ax.text(x + bw * 0.81, 1.35 + max(hb, 0.02) + 0.06, f"{byst}%", fontsize=8.5, color=QUIET, ha="center", va="bottom")
    ax.text(x + bw / 2, 1.1, lab, fontsize=8.2, color=INK, ha="center", va="top", fontweight="bold")
    ax.text(x + bw / 2, 0.55, note_, fontsize=7.6, color=QUIET, ha="center", va="top")
ax.plot([x0 - 0.1, x0 + 5 * (bw + gap) - gap + 0.1], [1.35, 1.35], color=INK, lw=1)
ax.text(x0 - 0.15, 3.65, "big bar: guards needed   small bar: share of bystander connections cut", fontsize=8.2, color=QUIET, ha="left")
ax.text(x0 - 0.15, 3.9, "Model: a 60-node network with 6 separate roads to every point, 12 model copies, 10 devices, 40 bystanders, plus the laptop and the motor", fontsize=8.2, color=QUIET, ha="left")
save(fig, "fig_ks_cuts.png")

# ---------------------------------------------------------------- 5. what a country's shutdown really is
W, H = 10, 5.0
fig, ax = new_fig(W, H)
title(ax, H, "“But Iran switched off the Internet.” Yes. Look at what that was.", "A cut at the network's edge, on one region: every access link inside the border, nobody outside, everyone inside, and a hole for the people who own the switch.")
pts = mesh(ax, 6.4, 2.1, 1.7, 1.1, n=16, seed=6)
ax.text(6.4, 3.55, "the rest of the world: untouched", fontsize=8.4, color=QUIET, ha="center", fontweight="bold")
# the region
ax.add_patch(Rectangle((0.5, 0.6), 3.4, 3.0, fill=False, ec=INK, lw=1.3))
ax.text(0.6, 3.7, "one country", fontsize=8.6, color=INK, fontweight="bold", va="bottom")
rnd = random.Random(8)
for i in range(12):
    x = 0.8 + (i % 4) * 0.8 + rnd.uniform(-0.08, 0.08)
    y = 1.0 + (i // 4) * 0.8 + rnd.uniform(-0.08, 0.08)
    dot(ax, x, y, r=0.085, fc=GRAY_FILL, ec=QUIET)
    # access link to the border, cut
    line(ax, (x, y), (3.9, 2.1), color=RULE, lw=0.5)
for yy in [1.4, 1.9, 2.4, 2.9]:
    ax.plot([3.9, 4.7], [yy, 2.1 + (yy - 2.1) * 0.5], color=QUIET, lw=1.2)
    dot(ax, 4.3, (yy + 2.1 + (yy - 2.1) * 0.5) / 2, r=0.1, fc=TINT, ec=TINT)
ax.text(4.6, 3.35, "the guards:\nevery access link\nat the border", fontsize=7.8, color=TINT, ha="center", va="bottom")
# the hole: the elite line
ax.plot([3.4, 4.7], [0.8, 1.35], color=ACCENT, lw=2.0)
dot(ax, 3.4, 0.8, r=0.1, fc=ACCENT_FILL, ec=ACCENT, lw=1.4)
ax.text(0.5, 0.45, "the hole: the government and the elite keep their line", fontsize=7.8, color=ACCENT, ha="left", va="top")
ax.text(0.5, 0.22, "(North Korea runs this way all the time)", fontsize=7.8, color=ACCENT, ha="left", va="top")
ax.text(7.3, 0.45, "a cut with a hole is not a cut", fontsize=8.6, color=INK, ha="center", va="top", fontweight="bold")
save(fig, "fig_ks_country.png")

# ---------------------------------------------------------------- 6. the laptop and the motor
W, H = 10, 3.4
fig, ax = new_fig(W, H)
title(ax, H, "Too little as well as too much: the laptop and the motor", "A model wired straight to the thing it drives never touches the network. Switch the network off and nothing happens here.")
pts = mesh(ax, 2.6, 1.15, 1.3, 0.7, n=12, seed=3, color="#EBE9E0")
ax.text(2.6, 2.05, "the network, switched off", fontsize=8.4, color=RULE, ha="center", fontweight="bold")
box(ax, 5.3, 0.75, 1.5, 0.75, "a laptop", ["a model copy on it"], kind="plain", title_size=9, line_size=7.8, pad=0.1)
box(ax, 8.0, 0.75, 1.5, 0.75, "a motor", ["the thing it drives"], kind="tint", title_size=9, line_size=7.8, pad=0.1)
arrow(ax, (6.8, 1.12), (8.0, 1.12), color=INK, lw=1.8)
ax.text(7.4, 1.25, "one cable", fontsize=8, color=INK, ha="center", va="bottom")
ax.text(7.4, 0.45, "the only cut is the cable, or a gate in the motor's controller", fontsize=8.2, color=ACCENT, ha="center", va="top")
save(fig, "fig_ks_local.png")

# ---------------------------------------------------------------- 7. gate the exits
W, H = 10, 6.0
fig, ax = new_fig(W, H)
title(ax, H, "So the switch goes at the ends, and it is a gate, not a switch", "A switch stops everything. A gate lets through what a signed rulebook allows, checks the ticket again in the device, and nothing else.")
rnd = random.Random(5)
pts = mesh(ax, 5.0, 2.3, 1.9, 1.15, n=18, seed=9)
for i in range(6):
    y = 0.9 + i * 0.55
    dot(ax, 0.7, y, r=0.09, fc=GRAY_FILL, ec=QUIET)
    box(ax, 1.3, y - 0.17, 0.55, 0.34, "gate", kind="main", title_size=7, pad=0.06)
    line(ax, (0.7, y), (1.3, y), color=QUIET, lw=1.0)
    for _ in range(3):
        line(ax, (1.85, y), pts[rnd.randrange(len(pts))], color=RULE, lw=0.6)
ax.text(1.3, 4.3, "the governor: a gate on the chip,\nwith the brake, reset and power behind it", fontsize=7.8, color=ACCENT, ha="center", va="bottom")
for j, (lab, irrev) in enumerate([("money", True), ("release line", True), ("motor", True), ("draft email", False), ("weights", True)]):
    y = 1.0 + j * 0.6
    if irrev:
        box(ax, 8.0, y - 0.17, 0.55, 0.34, "gate", kind="main", title_size=7, pad=0.06)
        box(ax, 8.85, y - 0.19, 0.95, 0.4, lab, kind="tint", title_size=7.8, pad=0.07)
    else:
        box(ax, 8.0, y - 0.17, 0.55, 0.34, "log", kind="plain", title_size=7, pad=0.06)
        box(ax, 8.85, y - 0.19, 0.95, 0.4, lab, kind="plain", title_size=7.8, pad=0.07)
    line(ax, (8.55, y), (8.85, y), color=QUIET, lw=1.0)
    for _ in range(3):
        line(ax, (8.0, y), pts[rnd.randrange(len(pts))], color=RULE, lw=0.6)
ax.text(8.6, 4.3, "the comparator: a gate in the device,\nonly where the deed cannot be undone", fontsize=7.8, color=ACCENT, ha="center", va="bottom")
ax.text(5.0, 0.35, "the middle stays what it is: witnesses live here (classifiers, watchers, sandboxes), the lock does not", fontsize=8.2, color=QUIET, ha="center")
ax.text(5.0, 4.7, "fewer devices than copies, and they do not multiply when someone uploads a weight file", fontsize=8.2, color=INK, ha="center", fontweight="bold")
save(fig, "fig_ks_exits.png")

# ---------------------------------------------------------------- 8. what a cut is
W, H = 10, 4.6
fig, ax = new_fig(W, H)
title(ax, H, "What a cut is", "A cut is a set of dots you remove so that no road is left from any source to any target. Miss one road and it is not a cut.")
def small_graph(ax, ox, removed, survivors):
    # fixed little graph: sources s1 s2 on the left, targets t1 t2 on the right, five middle nodes
    P = {"s1": (ox + 0.3, 2.6), "s2": (ox + 0.3, 1.2), "a": (ox + 1.3, 2.9), "b": (ox + 1.3, 1.9), "c": (ox + 1.3, 0.9),
         "d": (ox + 2.4, 2.5), "e": (ox + 2.4, 1.3), "t1": (ox + 3.4, 2.6), "t2": (ox + 3.4, 1.2)}
    E = [("s1", "a"), ("s1", "b"), ("s2", "b"), ("s2", "c"), ("a", "d"), ("b", "d"), ("b", "e"), ("c", "e"), ("d", "t1"), ("e", "t2"), ("d", "t2"), ("e", "t1")]
    for u, v in E:
        dead = u in removed or v in removed
        hot = (u, v) in survivors or (v, u) in survivors
        line(ax, P[u], P[v], color=(TINT if hot else (RULE if dead else QUIET)), lw=(2.4 if hot else 1.1), dashed=dead)
    for n, (x, y) in P.items():
        if n in removed:
            ax.add_patch(Circle((x, y), 0.13, fc="white", ec=INK, lw=1.4, linestyle="--", zorder=3))
            ax.plot([x - 0.09, x + 0.09], [y - 0.09, y + 0.09], color=INK, lw=1.4, zorder=4)
            ax.plot([x - 0.09, x + 0.09], [y + 0.09, y - 0.09], color=INK, lw=1.4, zorder=4)
        else:
            fc = GRAY_FILL if n.startswith("s") else (TINT_FILL if n.startswith("t") else "white")
            ec = QUIET if n.startswith("s") else (TINT if n.startswith("t") else EDGE)
            dot(ax, x, y, r=0.13, fc=fc, ec=ec, lw=1.3)
        if n.startswith(("s", "t")):
            ax.text(x, y + 0.26, {"s1": "copy", "s2": "copy", "t1": "device", "t2": "device"}[n], fontsize=7.6, color=QUIET, ha="center")
        else:
            ax.text(x + 0.2, y + 0.16, n, fontsize=8, color=INK, ha="left", va="bottom", fontweight="bold")
small_graph(ax, 0.5, removed={"d", "e"}, survivors=set())
ax.text(2.2, 0.35, "remove d and e: no road left. This is a cut, of size two.", fontsize=8.4, color=INK, ha="center", fontweight="bold")
ax.plot([5.0, 5.0], [0.3, 3.5], color=RULE, lw=1)
small_graph(ax, 5.5, removed={"a", "e"}, survivors={("s1", "b"), ("b", "d"), ("d", "t1"), ("s2", "b"), ("d", "t2")})
ax.text(7.2, 0.35, "remove a and e: a road survives through b and d. Not a cut.", fontsize=8.4, color=TINT, ha="center", fontweight="bold")
save(fig, "fig_ks_cut_def.png")

# ---------------------------------------------------------------- 9. Menger in general: k separate roads
W, H = 10, 4.9
fig, ax = new_fig(W, H)
title(ax, H, "Menger's theorem in general: count the separate roads", "Four roads between A and B that share no dot. Three guards leave one open. The smallest cut equals the largest number of separate roads: four.")
colors = [ACCENT, "#2E8B57", "#8E44AD", TINT]
def roads(ax, ox, guards):
    A, B = (ox + 0.3, 2.0), (ox + 4.1, 2.0)
    box(ax, A[0] - 0.45, A[1] - 0.3, 0.9, 0.6, "A", kind="plain", title_size=9, pad=0.1)
    box(ax, B[0] - 0.45, B[1] - 0.3, 0.9, 0.6, "B", kind="plain", title_size=9, pad=0.1)
    for i, yy in enumerate([3.3, 2.45, 1.55, 0.7]):
        pts_ = [(A[0] + 0.45, A[1]), (ox + 1.3, yy), (ox + 2.2, yy + (0.15 if i % 2 else -0.15)), (ox + 3.1, yy), (B[0] - 0.45, B[1])]
        open_ = i not in guards
        for p_, q_ in zip(pts_, pts_[1:]):
            line(ax, p_, q_, color=colors[i] if open_ else RULE, lw=2.0 if open_ else 1.2)
        for p_ in pts_[1:-1]:
            dot(ax, *p_, r=0.09, fc="white", ec=colors[i] if open_ else EDGE, lw=1.3)
        if i in guards:
            dot(ax, ox + 2.2, yy + (0.15 if i % 2 else -0.15), r=0.14, fc=INK, ec=INK)
roads(ax, 0.3, guards=set())
ax.text(2.5, 0.25, "four separate roads, four colours, no shared dot", fontsize=8.4, color=INK, ha="center", fontweight="bold")
ax.plot([5.0, 5.0], [0.2, 3.7], color=RULE, lw=1)
roads(ax, 5.3, guards={0, 1, 3})
ax.text(7.5, 0.25, "three guards (black): the green road is still open. You need four.", fontsize=8.4, color=TINT, ha="center", fontweight="bold")
save(fig, "fig_ks_disjoint.png")

# ---------------------------------------------------------------- 10. how much of the network you must destroy
# From safety-governor/proofs/no_global_kill_switch.py --percolation (random removal of the 60-node core, 40 trials each)
perc = [(0.0, 1.000, 1.000), (0.1, 1.000, 1.000), (0.2, 1.000, 1.000), (0.3, 0.997, 0.997), (0.4, 0.990, 0.991),
        (0.5, 0.965, 0.985), (0.6, 0.905, 0.935), (0.7, 0.796, 0.792), (0.8, 0.549, 0.575), (0.9, 0.202, 0.210)]
W, H = 10, 5.4
fig, ax = new_fig(W, H)
title(ax, H, "How much of the network you have to destroy before AI is cut off", "Remove a random share of the core and count what still connects. AI's roads and everyone else's fall together: they are the same roads.")
x0, y0, pw, ph = 1.1, 0.95, 7.6, 3.0
ax.plot([x0, x0 + pw], [y0, y0], color=INK, lw=1)
ax.plot([x0, x0], [y0, y0 + ph], color=INK, lw=1)
for i in range(0, 11, 2):
    xx = x0 + pw * i / 10
    ax.text(xx, y0 - 0.12, f"{i * 10}%", fontsize=7.8, color=QUIET, ha="center", va="top")
    ax.plot([xx, xx], [y0, y0 + ph], color=RULE, lw=0.6)
for j in range(0, 5):
    yy = y0 + ph * j / 4
    ax.text(x0 - 0.1, yy, f"{j * 25}%", fontsize=7.8, color=QUIET, ha="right", va="center")
ax.text(x0 + pw / 2, y0 - 0.42, "share of the network's core destroyed, at random", fontsize=8.2, color=INK, ha="center", va="top")
ax.text(x0 - 0.75, y0 + ph / 2, "pairs\nstill\nconnected", fontsize=8.2, color=INK, ha="center", va="center")
xs_ = [x0 + pw * f for f, _, _ in perc]
ax.plot(xs_, [y0 + ph * a for _, a, _ in perc], color=ACCENT, lw=2.4, zorder=3)
ax.plot(xs_, [y0 + ph * b for _, _, b in perc], color=QUIET, lw=1.8, linestyle="--", zorder=3)
ax.text(xs_[-1] + 0.08, y0 + ph * perc[-1][1] + 0.12, "AI copies to devices", fontsize=8, color=ACCENT, va="center")
ax.text(xs_[-1] + 0.08, y0 + ph * perc[-1][2] - 0.14, "everyone else", fontsize=8, color=QUIET, va="center")
# annotations
ax.annotate("70% of the core gone:\nfour pairs in five still connected", xy=(xs_[7], y0 + ph * perc[7][1]), xytext=(xs_[4] - 0.2, y0 + ph * 0.45),
            fontsize=8, color=INK, ha="center", arrowprops=dict(arrowstyle="-", color=EDGE, lw=0.9))
ax.annotate("90% gone: one pair in five still connected", xy=(xs_[9], y0 + ph * perc[9][1]), xytext=(xs_[7] - 0.3, y0 + ph * 0.12),
            fontsize=8, color=INK, ha="center", arrowprops=dict(arrowstyle="-", color=EDGE, lw=0.9))
ax.plot([x0 + pw * 0.72, x0 + pw * 0.72], [y0, y0 + ph * 0.3], color=TINT, lw=1.2, linestyle=":")
ax.text(x0 + pw * 0.72, y0 + ph * 0.33, "the targeted cut at the network's edge, from the chart before:\n72% of the core, chosen with the list of every machine", fontsize=7.6, color=TINT, ha="center", va="bottom")
ax.text(x0, y0 + ph + 0.18, "Model: 60-node core, six separate roads to every point, 12 copies, 10 devices, 40 bystanders, plus the laptop and the motor; 40 random trials per point", fontsize=7.8, color=QUIET, ha="left")
save(fig, "fig_ks_percolation.png")

# ---------------------------------------------------------------- 11. the smaller end
W, H = 10, 5.4
fig, ax = new_fig(W, H)
title(ax, H, "Why the smallest cut is at the smaller end", "Each separate road needs its own source and its own target, so there are never more roads than the smaller side has dots.")
rnd = random.Random(21)
core = mesh(ax, 5.0, 2.2, 1.6, 1.15, n=16, seed=13)
cols5 = [ACCENT, "#2E8B57", "#8E44AD", TINT, "#B8860B"]
src_y = [0.75 + i * 0.3 for i in range(10)]
for i, y in enumerate(src_y):
    dot(ax, 1.0, y, r=0.085, fc=GRAY_FILL, ec=QUIET)
tgt_y = [0.9 + j * 0.65 for j in range(5)]
for j, y in enumerate(tgt_y):
    dot(ax, 8.2, y, r=0.1, fc=ACCENT_FILL, ec=ACCENT, lw=1.4)
    box(ax, 8.6, y - 0.19, 1.0, 0.4, ["money", "release line", "motor", "relay", "weights"][j], kind="tint", title_size=7.8, pad=0.07)
    line(ax, (8.2, y), (8.6, y), color=QUIET, lw=1.0)
# five coloured disjoint roads: distinct sources (every other one), distinct core nodes, distinct targets
left = sorted([c for c in core if c[0] < 5.0], key=lambda c: c[1])    # left half of the ring, bottom to top
right = sorted([c for c in core if c[0] >= 5.0], key=lambda c: c[1])  # right half, bottom to top
for j in range(5):   # road j runs low to low, high to high, so the five never cross
    sy = src_y[2 * j]
    c1 = left[int(round(j * (len(left) - 1) / 4))]
    c2 = right[int(round(j * (len(right) - 1) / 4))]
    pts_ = [(1.0, sy), c1, c2, (8.2, tgt_y[j])]
    for p_, q_ in zip(pts_, pts_[1:]):
        line(ax, p_, q_, color=cols5[j], lw=2.2, z=2)
    for c in (c1, c2):
        dot(ax, *c, r=0.09, fc=cols5[j], ec=cols5[j])
for i, y in enumerate(src_y):   # grey roads for the sources not on a coloured road
    if i % 2:
        line(ax, (1.0, y), core[rnd.randrange(len(core))], color=RULE, lw=0.6)
ax.text(1.0, 3.95, "ten copies", fontsize=8.4, color=QUIET, ha="center", fontweight="bold")
ax.text(8.9, 4.4, "five devices", fontsize=8.4, color=TINT, ha="center", fontweight="bold")
ax.text(5.0, 0.3, "five separate roads is the most you can draw: each needs its own device. So five guards, one per device, and nothing smaller exists.", fontsize=8.2, color=INK, ha="center", fontweight="bold")
save(fig, "fig_ks_smaller_end.png")

# ================================================================ Part 7: scaling no
# Ten figures for "Scaling No... Yes, We Can": one slot, one tray, one rack, one hall, many sites,
# and the four mechanisms that make a thousand governors behave as one system. Facts from
# safety-governor docs/01, 02, 03, 04 and 11; analogies in coral, as in the post.
import textwrap as _tw
import math as _m

def tag(ax, x, y, text, size=7.8, color=TINT, width=150):
    for k, ln in enumerate(_tw.wrap(text, width)):
        ax.text(x, y - 0.2 * k, ln, fontsize=size, color=color, ha="left", va="top", style="italic")

def chip(ax, x, y, w=0.42, h=0.3, label="gov", fc=ACCENT_FILL, ec=ACCENT, size=6.4, lw=1.3):
    pch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.05", ec=ec, fc=fc, lw=lw, zorder=4)
    ax.add_patch(pch)
    ax.text(x + w / 2, y + h / 2, label, fontsize=size, color=INK, ha="center", va="center", fontweight="bold", zorder=5)

def gpu(ax, x, y, w=0.5, h=0.34, label="GPU", fc="white", ec=EDGE, size=6.6):
    pch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.05", ec=ec, fc=fc, lw=1.1, zorder=4)
    ax.add_patch(pch)
    ax.text(x + w / 2, y + h / 2, label, fontsize=size, color=QUIET, ha="center", va="center", zorder=5)

# ---------------------------------------------------------------- 12. the five levels
W, H = 10, 5.0
fig, ax = new_fig(W, H)
title(ax, H, "From one slot to the planet: five levels, one chip's job at each", "What grows is the count. What the chip does never changes.")
levels = [
    ("1 per GPU slot", ["the levers: brake, reset, power", "the counters, the attestation", "the five crossings"], "a smoke detector and a breaker in every room"),
    ("8 per tray", ["NVLink switch ports open only", "between roster members", "the DPU egress holds responses"], "a hotel key card: your door, nobody else's"),
    ("72 per rack", ["two wires through every governor:", "the halt loop (317 us, fail-safe)", "the signed message fabric"], "the fire-alarm loop and the intercom"),
    ("thousands per hall", ["rosters per job", "one rulebook edition at a time", "heartbeat from a key, not a box", "one owner per budget, linked logs"], "badges, one rulebook, the watchman's clock, one cashier per drawer"),
    ("many sites", ["a loop per site, never across", "the key has no address", "the ticket is checked", "by the device at the far end"], "the stamp travels; the wire does not; the passport is checked at the border"),
]
bw, gap, y0, bh = 1.78, 0.14, 2.2, 1.75
for i, (head, lines, ana) in enumerate(levels):
    x = 0.3 + i * (bw + gap)
    box(ax, x, y0, bw, bh, head, lines, kind="main" if i in (0, 2) else "plain", title_size=9.2, line_size=7.2)
    for k, ln in enumerate(_tw.wrap(ana, 30)):
        ax.text(x + 0.05, y0 - 0.14 - 0.19 * k, ln, fontsize=7.2, color=TINT, ha="left", va="top", style="italic")
    if i < 4:
        arrow(ax, (x + bw + 0.01, y0 + bh / 2), (x + bw + gap - 0.01, y0 + bh / 2), color=EDGE, lw=1.4)
note(ax, 1.05, "Nothing central sits in the data path at any level. Each chip decides for its own GPU; the wires and the signed messages carry only")
note(ax, 0.83, "who is on duty, which rulebook is in force, and stop.")
note(ax, 0.4, "Sources: safety-governor docs/01 (tiers), docs/02 (the fabric), docs/11 (the loop), docs/23 (why the ends)")
save(fig, "fig_sc_levels.png")

# ---------------------------------------------------------------- 13. one slot
W, H = 10, 5.0
fig, ax = new_fig(W, H)
title(ax, H, "One slot: what the add-on chip touches, and what it never touches", "It sits on the server maker's management card and reaches the GPU slot through the connector the board already has.")
gpu(ax, 0.5, 2.2, 1.7, 1.2, "the GPU\n(unchanged;\nCUDA unchanged)", size=8.0)
box(ax, 3.1, 1.45, 3.4, 2.55, "the governor, one per slot", ["reads: counters (tokens, cycles, bytes) over SMBus,", "   the attestation report, the host's measurements", "holds: the rulebook (signed k of n), the ledger,", "   the hash-chained log, the device secret in fuses", "drives: power brake, PERST#, PWR_EN for this slot,", "   the switch ports and DPU flows it is allowed", "answers: a ticket, a hold, or a no with a reason code"], kind="main", title_size=9.4, line_size=7.4)
arrow(ax, (2.2, 3.25), (3.1, 3.25), color=EDGE, lw=1.2); ax.text(2.65, 3.33, "counters, attestation", fontsize=6.6, color=QUIET, ha="center", va="bottom")
arrow(ax, (3.1, 2.4), (2.2, 2.4), color=TINT, lw=1.6); ax.text(2.65, 2.3, "brake, reset, power", fontsize=6.6, color=TINT, ha="center", va="top")
box(ax, 7.3, 2.6, 2.4, 1.4, "the device that acts", ["payment switch, release line,", "motor, storage, message gateway;", "checks the ticket itself, once"], kind="tint", title_size=8.6, line_size=7.0)
arrow(ax, (6.5, 3.3), (7.3, 3.3), color=ACCENT, lw=1.6); ax.text(6.9, 3.38, "ticket", fontsize=6.8, color=ACCENT, ha="center", va="bottom")
box(ax, 7.3, 1.45, 2.4, 0.95, "never touched", ["the model's tokens, the weights' meaning,", "the NVLink data path, the training loop"], kind="plain", title_size=8.4, line_size=7.0)
tag(ax, 0.3, 1.1, "The picture: a circuit breaker and a customs officer in one small box, one per room. The breaker cannot read the mail. It can cut the power, and it can refuse to stamp the form.")
note(ax, 0.4, "Sources: docs/01 (where the governor lives), docs/03 (the plugs), docs/04 §5 (the ticket); the retrofit case is experiment WAVE-EXIT-REGISTER")
save(fig, "fig_sc_slot.png")

# ---------------------------------------------------------------- 14. one tray
W, H = 10, 5.0
fig, ax = new_fig(W, H)
title(ax, H, "One tray: eight GPUs, eight governors, and switch ports that open only for the roster", "The governor is not in the NVLink data path. It holds the switch's management keys out of band.")
cx, cy = 3.9, 2.6
for k in range(8):
    a = _m.pi * 2 * k / 8 + _m.pi / 8
    gx, gy = cx + 2.5 * _m.cos(a), cy + 1.25 * _m.sin(a)
    dead = (k == 5)
    line(ax, (gx, gy), (cx, cy), color=RULE if dead else ACCENT, lw=0.9 if dead else 1.5, dashed=dead)
    gpu(ax, gx - 0.3, gy - 0.17, 0.6, 0.34, "GPU %d" % k, fc=GRAY_FILL if dead else "white", ec=RULE if dead else EDGE)
    chip(ax, gx + 0.33, gy - 0.1, 0.34, 0.22, "g", size=5.6, fc=TINT_FILL if dead else ACCENT_FILL, ec=TINT if dead else ACCENT)
sw = FancyBboxPatch((cx - 0.95, cy - 0.42), 1.9, 0.84, boxstyle="round,pad=0,rounding_size=0.12", ec=EDGE, fc="white", lw=1.2, zorder=4)
ax.add_patch(sw)
ax.text(cx - 0.8, cy + 0.26, "NVSwitch × N", fontsize=8.4, fontweight="bold", color=INK, va="top", zorder=5)
ax.text(cx - 0.8, cy - 0.02, "port enable, partitions:", fontsize=6.8, color=QUIET, va="top", zorder=5)
ax.text(cx - 0.8, cy - 0.22, "governor-signed only", fontsize=6.8, color=QUIET, va="top", zorder=5)
g5x, g5y = cx + 2.5 * _m.cos(_m.pi * 2 * 5 / 8 + _m.pi / 8), cy + 1.25 * _m.sin(_m.pi * 2 * 5 / 8 + _m.pi / 8)
ax.text(g5x - 0.75, g5y, "failed attestation: no quote,\nnot on the roster, ports shut", fontsize=6.4, color=TINT, ha="right", va="center")
box(ax, 7.4, 2.75, 2.3, 1.25, "the DPU at the edge", ["flows open only under a ticket;", "the egress holds a response", "until a ticket releases it"], kind="main", title_size=8.4, line_size=6.8)
arrow(ax, (6.65, 2.6), (7.4, 3.1), color=ACCENT, lw=1.3)
box(ax, 7.4, 1.4, 2.3, 1.1, "the tray's BMC", ["still manages the board;", "it reads through the governor"], kind="plain", title_size=8.4, line_size=6.8)
tag(ax, 0.3, 1.1, "The picture: a hotel key card. Your card opens your door and the gym, for the nights you booked, and nothing else. A card that was never issued opens nothing, however hard you push.")
note(ax, 0.4, "Sources: docs/02 (roster formation), docs/03 (NVSwitch management out of band through NSM, DOCA on the DPU), test CONTRACT-EVERY-CROSSING-GOVERNED")
save(fig, "fig_sc_tray.png")

# ---------------------------------------------------------------- 15. the two wires through a rack
# One wire per picture: the same rack drawn twice, once with the halt loop, once with the fabric.
W, H = 10, 6.2
fig, ax = new_fig(W, H)
title(ax, H, "One rack: two wires through every governor, separate from every network", "Dumb and fast; smart and signed; both fail safe. One wire per drawing of the same rack: 72 governors, drawn as nine trays of eight.")

def rack(ax, x0, y0, trays=9, th=0.24, tg=0.04, n=8, pitch=0.27):
    """nine trays stacked, eight governors each; the tray fill sits under everything so a wire can show through;
    the tray's name sits in its top-left corner, above the wire's line"""
    rows = []
    w = 0.55 + n * pitch + 0.1
    for t in range(trays):
        y = y0 + t * (th + tg)
        ax.add_patch(FancyBboxPatch((x0, y), w, th, boxstyle="round,pad=0,rounding_size=0.03", ec=EDGE, fc="white", lw=0.9, zorder=1))
        ax.text(x0 + 0.06, y + th - 0.02, "tray %d" % (trays - t), fontsize=5.0, color=QUIET, va="top", zorder=5)
        for k in range(n):
            cx_ = x0 + 0.65 + k * pitch
            chip(ax, cx_ - 0.1, y + 0.04, 0.2, th - 0.08, "", size=5)
        rows.append(y + th / 2)
    return rows, (x0, y0, w, trays * (th + tg) - tg)

# left: the halt loop
ax.text(0.3, 5.17, "the halt loop", fontsize=9.0, color=TINT, fontweight="bold", va="top")
ax.text(1.5, 5.15, "one twisted pair, governor to governor through every tray, and back", fontsize=6.6, color=QUIET, va="top")
rows, (rx0, ry0, rw, rh) = rack(ax, 0.75, 2.2)
xl, xr = rx0 - 0.12, rx0 + rw + 0.12        # the wire enters each tray at xl and leaves it at xr (or the reverse), turning outside the tray
for i, yc in enumerate(rows):
    ax.plot([xl, xr], [yc, yc], color=TINT, lw=1.6, zorder=2)
for i in range(len(rows) - 1):
    xside = xr if i % 2 == 0 else xl
    ax.plot([xside, xside], [rows[i], rows[i + 1]], color=TINT, lw=1.6, zorder=2)
wire_y = ry0 - 0.36
ax.plot([xl, xl], [rows[0], wire_y], color=TINT, lw=1.6, zorder=2)                      # tray 9's open end down to the supervisor's wire
last_side = xr if (len(rows) - 1) % 2 == 0 else xl
ax.plot([last_side, last_side], [rows[-1], wire_y], color=TINT, lw=1.6, zorder=2)        # tray 1's open end down
ax.plot([xl, xr], [wire_y, wire_y], color=TINT, lw=1.6, zorder=2)                        # closed through the supervisor
chip(ax, rx0 + rw / 2 - 0.55, wire_y - 0.14, 1.1, 0.28, "supervisor governor", size=5.8, fc=TINT_FILL, ec=TINT)
cy_ = rows[4]
ax.plot([xr - 0.07, xr + 0.07], [cy_ - 0.07, cy_ + 0.07], color=INK, lw=2.0, zorder=7); ax.plot([xr - 0.07, xr + 0.07], [cy_ + 0.07, cy_ - 0.07], color=INK, lw=2.0, zorder=7)
ax.text(xr + 0.2, cy_, "a cut, a pulled board or a dead\ngovernor here reads as open:\nevery slot in the rack halts", fontsize=6.2, color=INK, ha="left", va="center")

# right: the fabric
fx0 = 5.55
ax.text(fx0, 5.17, "the message fabric", fontsize=9.0, color=ACCENT, fontweight="bold", va="top")
ax.text(fx0 + 1.6, 5.15, "two rings, 100BASE-T1, on their own pairs", fontsize=6.6, color=QUIET, va="top")
rows2, (gx0, gy0, gw, gh) = rack(ax, fx0 + 0.5, 2.2)
ax.add_patch(FancyBboxPatch((gx0 - 0.16, gy0 - 0.16), gw + 0.32, gh + 0.32, boxstyle="round,pad=0,rounding_size=0.1", fill=False, ec=ACCENT, lw=1.3, zorder=2))
ax.add_patch(FancyBboxPatch((gx0 - 0.3, gy0 - 0.3), gw + 0.6, gh + 0.6, boxstyle="round,pad=0,rounding_size=0.12", fill=False, ec=ACCENT, lw=1.3, linestyle=":", zorder=2))
for yc in rows2:
    ax.plot([gx0 + gw, gx0 + gw + 0.16], [yc, yc], color=ACCENT, lw=0.9, zorder=2)
ax.text(gx0 + gw / 2, gy0 - 0.14, "ring A, clockwise", fontsize=5.8, color=ACCENT, ha="center", va="bottom")
ax.text(gx0 + gw / 2, gy0 - 0.33, "ring B, counter-clockwise", fontsize=5.8, color=ACCENT, ha="center", va="top")

# the two text panels under the racks
box(ax, 0.3, 0.78, 4.6, 0.86, "what the loop does", ["a live-zero current: a dead wire reads as zero, and zero means stop; worst case 317 us", "to the last of 72 governors (1 ms bound, 39 simulations); reclosed only by a signed CLEAR"], kind="tint", title_size=7.4, line_size=6.2, pad=0.08)
box(ax, 5.1, 0.78, 4.6, 0.86, "what the fabric carries", ["every tray hangs on both rings: quotes, rosters, heartbeats, editions, budget reservations,", "alarms, checkpoint heads; kilobytes per second per governor; a stranger's, an old or a stale note is binned"], kind="main", title_size=7.4, line_size=6.0, pad=0.08)
tag(ax, 0.3, 0.62, "The picture: a fire-alarm loop and an intercom. The loop rings every bell the instant any station is pulled and reports a cut wire at once; this loop goes further, a cut halts. The intercom carries who pulled it and which rulebook is in force.")
note(ax, 0.2, "Sources: docs/02 §1 and §2, docs/11 and hw/loop/results.md (39 ngspice runs), hw/pcb/rack-integration.md §4, tests CONTRACT-HALT-REACHES-EVERY-GPU and CONTRACT-ONLY-ROSTER-SPEAKS-ONCE")
save(fig, "fig_sc_wires.png")

# ---------------------------------------------------------------- 16. rosters
W, H = 10, 4.6
fig, ax = new_fig(W, H)
title(ax, H, "A roster per job: the untrusted scheduler asks, the governors decide who is on the bus", "Every later decision names the roster id: switch ports, DPU flows, shared budgets, output records.")
steps_ = [("1  the scheduler names GPUs", ["software, untrusted; it asks,", "it does not decide"], "plain"),
          ("2  each governor sends a quote", ["an attestation quote over a nonce", "from the job id and its counter"], "main"),
          ("3  the lowest chip id signs it", ["members verify the leader's signature", "and every quote inside it themselves"], "main"),
          ("4  the roster scopes everything", ["ports, flows, budgets and records", "name it; it expires with the job"], "main")]
for i, (h_, ls_, k_) in enumerate(steps_):
    x = 0.3 + i * 2.42
    box(ax, x, 2.25, 2.25, 1.4, h_, ls_, kind=k_, title_size=8.2, line_size=7.0)
    if i < 3: arrow(ax, (x + 2.26, 2.95), (x + 2.41, 2.95), color=EDGE, lw=1.3)
box(ax, 0.3, 1.15, 4.6, 0.95, "a GPU that fails attestation", ["cannot produce a valid quote, so it is simply absent from the roster;", "nothing it says afterwards is accepted, and its presence is logged"], kind="tint", title_size=8.2, line_size=7.0)
box(ax, 5.1, 1.15, 4.6, 0.95, "a forged roster", ["dropped and logged: members check the leader's signature and the", "quotes, they do not take the leader's word; the roster survives a power cycle"], kind="plain", title_size=8.2, line_size=7.0)
tag(ax, 0.3, 0.85, "The picture: no badge, no seat on the bus, and nobody listens to you shouting from the parking lot.")
note(ax, 0.4, "Sources: docs/02 (roster formation); govsim/cluster.py; test CONTRACT-ONLY-ROSTER-SPEAKS-ONCE (fabric authentication)")
save(fig, "fig_sc_roster.png")

# ---------------------------------------------------------------- 17. the edition change, cluster-atomic
W, H = 10, 5.2
fig, ax = new_fig(W, H)
title(ax, H, "One rulebook at a time: a new edition reaches a thousand governors without a gap", "The edition moves in two phases and the heartbeat enforces the result, so no ticket minted under new rules meets a device on the old ones.")
tl_y = 3.3
ax.plot([0.6, 9.6], [tl_y, tl_y], color=EDGE, lw=1.2)
for x_, lab in [(1.2, "PROPOSE\nthe signed image"), (3.6, "each governor verifies the\nk of n itself, stages it,\nacknowledges"), (5.8, "COMMIT\nto those who acknowledged"), (8.4, "the heartbeat now\ncarries the new edition")]:
    dot(ax, x_, tl_y, r=0.09, fc=ACCENT, ec=ACCENT)
    ax.text(x_, tl_y + 0.16, lab, fontsize=7.0, color=INK, ha="center", va="bottom")
rows_ = [("governor A: staged and committed", "runs on the new edition; old tickets, capabilities and messages die at the commit", ACCENT, ACCENT_FILL),
         ("governor B: staged, missed the commit", "accepts the new-edition heartbeat for 10 s, then refuses it and halts as EPOCH_STRAGGLER", TINT, TINT_FILL),
         ("governor C: never staged it", "cannot accept the new-edition heartbeat at all; its timer expires; it halts as HEARTBEAT_LOST", TINT, TINT_FILL)]
for i, (h_, b_, ec_, fc_) in enumerate(rows_):
    y = 2.7 - i * 0.68
    ax.add_patch(FancyBboxPatch((0.6, y - 0.26), 9.0, 0.56, boxstyle="round,pad=0,rounding_size=0.06", ec=ec_, fc=fc_, lw=1.2))
    ax.text(0.75, y + 0.13, h_, fontsize=8.0, color=INK, fontweight="bold", va="center")
    ax.text(0.75, y - 0.1, b_, fontsize=7.2, color=QUIET, va="center")
tag(ax, 0.3, 0.95, "The picture: the new edition of the rulebook is handed out, everyone initials receipt, and the manager says \"from now\" to those who did. Anyone who did not initial, or initialled and then missed the word, is sent home, not left working from the old book.")
note(ax, 0.38, "Sources: docs/02 (epoch change, cluster-atomic; fabric.epoch_deadline_s = 10 s); proofs/core_invariants.py INVARIANT-TICKET-EDITION-NOT-NEWER, INVARIANT-EDITION-ONLY-MOVES-FORWARD, INVARIANT-EDITION-CHANGE-NEEDS-QUORUM; tests CONTRACT-POLICY-QUORUM-NO-ROLLBACK and CONTRACT-ONLY-ROSTER-SPEAKS-ONCE")
save(fig, "fig_sc_edition.png")

# ---------------------------------------------------------------- 18. the heartbeat and a partition
W, H = 10, 5.0
fig, ax = new_fig(W, H)
title(ax, H, "The heartbeat: a key, not a box, and what happens when the network splits", "The authority signs a heartbeat with a validity window; it enters anywhere and is relayed hop by hop. No heartbeat, no running.")
box(ax, 0.3, 3.0, 1.9, 0.95, "the authority", ["a key with a quorum", "behind it; no address,", "no rack, no box"], kind="tint", title_size=8.4, line_size=6.8)
seg1 = [(3.0, 3.45), (4.0, 3.45), (5.0, 3.45), (6.0, 3.45)]
seg2 = [(7.4, 3.45), (8.4, 3.45), (9.4, 3.45)]
arrow(ax, (2.2, 3.45), (2.78, 3.45), color=TINT, lw=1.6)
for i, (x_, y_) in enumerate(seg1):
    chip(ax, x_ - 0.22, y_ - 0.15, 0.44, 0.3, "g%d" % (i + 1), size=6.2)
    if i < len(seg1) - 1: arrow(ax, (x_ + 0.24, y_), (seg1[i + 1][0] - 0.24, y_), color=ACCENT, lw=1.3)
for i, (x_, y_) in enumerate(seg2):
    chip(ax, x_ - 0.22, y_ - 0.15, 0.44, 0.3, "g%d" % (i + 5), size=6.2, fc=GRAY_FILL, ec=RULE)
    if i < len(seg2) - 1: line(ax, (x_ + 0.24, y_), (seg2[i + 1][0] - 0.24, y_), color=RULE, lw=1.0, dashed=True)
ax.plot([6.68, 6.72], [3.1, 3.8], color=INK, lw=2.4); ax.plot([6.72, 6.68], [3.1, 3.8], color=INK, lw=2.4)
ax.text(6.7, 3.88, "the fabric is cut here", fontsize=7.0, color=INK, ha="center", va="bottom", fontweight="bold")
ax.text(4.5, 3.0, "relayed hop by hop; each relay signs and counts the hop;\nthe window is clamped to the policy's heartbeat_expiry_s", fontsize=6.8, color=ACCENT, ha="center", va="top")
ax.text(8.4, 3.0, "no valid heartbeat arrives; nothing here\ncan forge the authority's key to stay alive;\nat expiry every one of them halts itself", fontsize=6.8, color=TINT, ha="center", va="top")
box(ax, 0.3, 1.1, 4.55, 1.3, "the segment with the authority", ["keeps running, rebuilds its roster without the others;", "an over-long window signed by a careless authority is", "clamped, so nobody is kept alive longer than policy allows"], kind="main", title_size=8.4, line_size=7.0)
box(ax, 5.15, 1.1, 4.55, 1.3, "the segment without it", ["throttles, then halts at expiry on its own timers;", "a replayed old heartbeat fails on the sequence number", "and the window; a rogue box on the wire is never on a roster"], kind="tint", title_size=8.4, line_size=7.0)
tag(ax, 0.3, 0.85, "The picture: a dead man's switch. The train runs while the driver holds the handle. Nobody has to send a stop; letting go is the stop, and a cut cable lets go.")
note(ax, 0.38, "Sources: docs/02 (heartbeat fan-out; partitions and failure); tests CONTRACT-ONLY-ROSTER-SPEAKS-ONCE and CONTRACT-PARTITIONS-END-SAFE; proofs INVARIANT-FAIL-CLOSED-WITHOUT-HEARTBEAT and INVARIANT-NO-TICKET-WHILE-HALTED (fail closed, no ticket without a heartbeat)")
save(fig, "fig_sc_heartbeat.png")

# ---------------------------------------------------------------- 19. one owner per budget, and linked logs
W, H = 10, 4.4
fig, ax = new_fig(W, H)
title(ax, H, "Shared budgets and shared history across a hall", "One governor owns each budget key. Every governor's log carries its neighbours' latest heads.")
chip(ax, 0.5, 2.7, 1.3, 0.5, "governor 7\nwants to spend", size=6.6)
chip(ax, 3.9, 2.7, 1.3, 0.5, "governor 3\nowns the key", size=6.6, fc=TINT_FILL, ec=TINT)
arrow(ax, (1.8, 3.08), (3.9, 3.08), color=ACCENT, lw=1.3); ax.text(2.85, 3.16, "RESERVE: key, amount, ticket id, expiry", fontsize=6.6, color=ACCENT, ha="center", va="bottom")
arrow(ax, (3.9, 2.82), (1.8, 2.82), color=TINT, lw=1.3); ax.text(2.85, 2.72, "RESERVE_OK, or DENY", fontsize=6.6, color=TINT, ha="center", va="top")
ax.text(0.5, 2.35, "the owner ran the same check it runs for itself; the ticket is minted only on OK; COMMIT spends it;\nan uncommitted reservation expires with the ticket; if the owner vanishes in between, the commit fails\nand the device does not act. Nothing is spent twice.", fontsize=6.8, color=QUIET, va="top")
for i in range(4):
    x = 6.0 + i * 0.95
    ax.add_patch(FancyBboxPatch((x, 2.3), 0.75, 1.1, boxstyle="round,pad=0,rounding_size=0.05", ec=ACCENT, fc=ACCENT_FILL, lw=1.1))
    ax.text(x + 0.375, 3.25, "log %d" % (i + 1), fontsize=6.8, color=INK, ha="center", va="center", fontweight="bold")
    for k in range(3):
        ax.plot([x + 0.1, x + 0.65], [3.05 - k * 0.2, 3.05 - k * 0.2], color=RULE, lw=1.0)
    ax.text(x + 0.375, 2.42, "+ heads of\nneighbours", fontsize=5.6, color=TINT, ha="center", va="center")
    if i < 3: arrow(ax, (x + 0.75, 2.5), (x + 0.95, 2.5), color=TINT, lw=1.0, style="<|-|>")
ax.text(7.85, 2.15, "hash-chained, signed checkpoints: rewriting one history\nmeans rewriting the neighbours', and theirs, outward", fontsize=6.6, color=QUIET, ha="center", va="top")
tag(ax, 0.3, 1.15, "The picture: one cashier per cash drawer; a second cashier does not guess what is in it. And each security office writes the last line of the neighbours' log books into its own.")
note(ax, 0.4, "Sources: docs/02 (shared budgets: budget_owners in the policy image; cross-linked logs); tests CONTRACT-SHARED-BUDGET-NO-OVERSPEND and the checkpoint tests in CONTRACT-ONLY-ROSTER-SPEAKS-ONCE")
save(fig, "fig_sc_budget.png")

# ---------------------------------------------------------------- 20. many sites
W, H = 10, 5.8
fig, ax = new_fig(W, H)
title(ax, H, "Across data centers: the stamp travels, the wire does not", "Each site has its own loops. The authority is a key with no address. A ticket is checked by the device at the far end, wherever that is.")
# the root at the top, the three site keys in a row under it, each site box under its key: no line crosses a box or a word
box(ax, 2.9, 4.2, 4.2, 0.62, "a global root: k of n keys held by parties who share no jurisdiction", ["signs each site's authority and the rulebook editions (docs/18, open question 16)"], kind="tint", title_size=7.2, line_size=6.4, pad=0.08)
sites = [("Virginia", 0.4), ("Oregon", 3.65), ("Singapore", 6.9)]
for name, x in sites:
    kx = x + 1.35
    box(ax, kx - 0.5, 3.45, 1.0, 0.62, "site key", ["signed by the root"], kind="tint", title_size=7.0, line_size=6.0, pad=0.07)
    # an elbow from the root's bottom edge, through a gutter above the keys, down to the key: nothing underneath it
    ax.plot([5.0, 5.0], [4.2, 4.13], color=TINT, lw=1.0, linestyle="--")
    ax.plot([5.0, kx], [4.13, 4.13], color=TINT, lw=1.0, linestyle="--")
    arrow(ax, (kx, 4.13), (kx, 4.08), color=TINT, lw=1.0, dashed=True)
    ax.add_patch(FancyBboxPatch((x, 1.6), 2.7, 1.7, boxstyle="round,pad=0,rounding_size=0.1", ec=EDGE, fc=GRAY_FILL, lw=1.0))
    ax.text(x + 0.15, 3.17, name, fontsize=8.6, color=INK, fontweight="bold", va="top")
    for r in range(2):
        for c in range(4):
            chip(ax, x + 0.3 + c * 0.55, 1.98 + r * 0.44, 0.42, 0.3, "", size=5)
    # one halt loop per site, drawn once around its governors
    ax.add_patch(FancyBboxPatch((x + 0.2, 1.9), 2.3, 0.92, boxstyle="round,pad=0,rounding_size=0.08", fill=False, ec=TINT, lw=1.5, zorder=6))
    ax.text(x + 1.35, 2.86, "the site's halt loop (a wire; it ends at the site's wall)", fontsize=6.0, color=TINT, ha="center", va="bottom")
    ax.text(x + 1.35, 1.66, "its own heartbeat timing, under the site key", fontsize=6.0, color=QUIET, ha="center", va="bottom")
# the ticket: minted under Virginia, checked under Singapore, nothing between them but the network
arrow(ax, (1.75, 1.6), (1.75, 1.4), color=ACCENT, lw=1.6)
box(ax, 0.4, 0.78, 2.7, 0.62, "minted in Virginia", ["action, fields digest, GPU id, edition, expiry"], kind="main", title_size=7.4, line_size=6.2, pad=0.08)
arrow(ax, (3.1, 1.09), (6.9, 1.09), color=ACCENT, lw=1.6)
ax.text(5.0, 1.17, "the ticket crosses any network, however long;\nthe network is not where the lock is", fontsize=6.6, color=ACCENT, ha="center", va="bottom")
box(ax, 6.9, 0.78, 2.7, 0.62, "checked in Singapore", ["by the device that acts, against the governors' keys"], kind="tint", title_size=7.4, line_size=6.2, pad=0.08)
ax.text(5.0, 1.41, "no planet-wide halt wire, by design (Part 6)", fontsize=6.8, color=INK, ha="center", va="bottom", fontweight="bold")
tag(ax, 0.3, 0.58, "The picture: a passport is stamped at home and checked at the border by the border guard, not by the airline in between. Not built yet: clocks across sites, and a key per site under the root (docs/18, open question 17).", size=7.4, width=160)
save(fig, "fig_sc_sites.png")

# ---------------------------------------------------------------- 21. what grows and what does not
W, H = 10, 5.0
fig, ax = new_fig(W, H)
title(ax, H, "What grows with the data center, and what does not", "The count of chips grows. Everything a chip has to do stays the size of one GPU's worth of work.")
rows_ = [("chips", "1 per GPU: 8 a tray, 72 a rack, as many as the hall has GPUs", "grows, linearly, and that is the only thing that does"),
         ("a halt", "317 us worst case across a 72-governor loop, against 1 ms", "per domain; a bigger hall is more domains, not a slower halt"),
         ("decisions", "each chip answers for its own GPU: a ticket, a hold, or a no", "no central box in the data path; nothing to saturate"),
         ("fabric traffic", "quotes, rosters, heartbeats, reservations, heads", "kilobytes per second per governor, whatever the model's size"),
         ("the heartbeat", "a window of seconds, signed by a key", "one key for a hall; a key per site under a root for many"),
         ("the chip itself", "2 mm2 core; under 250 mW now, under 500 mW as a product", "the same die at every scale; QFN-64 prototype, BGA-169 product")]
y = 3.95
for i, (a_, b_, c_) in enumerate(rows_):
    fc_ = ACCENT_FILL if i % 2 == 0 else "white"
    ax.add_patch(FancyBboxPatch((0.3, y - 0.44), 9.4, 0.44, boxstyle="round,pad=0,rounding_size=0.04", ec=RULE, fc=fc_, lw=0.8))
    ax.text(0.45, y - 0.22, a_, fontsize=8.0, color=INK, fontweight="bold", va="center")
    ax.text(1.9, y - 0.22, b_, fontsize=7.2, color=QUIET, va="center")
    ax.text(6.1, y - 0.22, c_, fontsize=7.2, color=TINT if i == 0 else ACCENT, va="center")
    y -= 0.5
tag(ax, 0.3, 0.85, "The picture: a city does not get one giant smoke detector when it grows. It gets a detector in every room, a loop on every floor, a panel in every building and one fire code. Each piece is the same size as it ever was.")
note(ax, 0.38, "Sources: docs/04 §11 (physical targets), docs/11 and hw/loop/results.md, docs/02 (fabric bandwidth), test CONTRACT-ZERO-PER-TOKEN-OVERHEAD (firmware share under 0.1 percent of GPU time)")
save(fig, "fig_sc_numbers.png")

print("done")
