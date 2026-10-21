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
print("done")
