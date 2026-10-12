# The chip design — specification

The narrative version is [`blog/04-the-chip-that-says-no-3-the-silicon-design.md`](../blog/04-the-chip-that-says-no-3-the-silicon-design.md).
This file is the same design stated as a specification: the contract, the boundary, the
blocks, the protocol, the assumptions and the claims, in the order an implementer needs
them. It supersedes the sketch in `docs/SILICON.md` §3–5 where the two differ; the
module-to-block map in `docs/SILICON.md` §1 still applies. Revised after the October 2026
review (`docs/REVIEW-2026-10.md`).

## 1. The contract

Within a declared enforcement boundary, every protected operation requires a fresh
authorization bound to that exact operation. The endpoint enforces specified invariants
independently of the proposing model, subject to explicit assumptions about its inputs,
its hardware, and its policy authority.

Normative consequences:

- Every protected operation is authorized. The rulebook decides the path (`auto`,
  `observer`, `human`), never the requester.
- An authorization is a transaction: check, reserve, commit (§7). A ticket is the visible
  half of a reservation; it is not the authorization on its own.
- The endpoint re-checks against its own inputs before committing, and moves to its
  specified safe transition on any failure (§4).
- The guarantee is conditional on the assumptions register (§4); the register is part of
  the deployment, not an appendix.

## 2. The enforcement domain

A domain is the set of processors, memory, interfaces and action endpoints whose relevant
exits are all controlled. Drawing it is the first design act. A controller governs only
paths over which it has non-bypassable authority; a halt line is emergency authority and
cannot undo an action that escaped.

| Placement | Role | Limitation |
|---|---|---|
| **E · endpoint gate** (always present; the guarantee) | reject unauthorized operations before commitment; re-check with own sensors; own safe transition | protects only endpoints that enforce it; depends on its inputs |
| **A · DPU on the node's path** (BlueField-4 + DOCA, beside Sentry) | enforce on every packet and storage request crossing that path; own root; isolated from the host | PCIe P2P and NVLink between GPUs are off its path |
| **B · board-level controller** | keys, policy, watchdogs, authorization, protected logs; gate PCIe/NVLink egress on a carrier | needs hardware cooperation to block other components' traffic |
| **C · in-GPU controller + enforcement points** | checks at hardware boundary crossings inside the package | requires the vendor |

E alone satisfies the contract for a domain whose only exits are its endpoints. A, B and C
add containment and provenance in increasing coverage; none of them replaces E.

## 3. Layer placement

| Layer (from `docs/ARCHITECTURE.md`) | Silicon placement | Status |
|---|---|---|
| L5 governance root | ROM-anchored public keys; fuse-indexed revocation bitmap; k-of-n signatures on policy images; approver keys in the policy image | key custody rules; a key, not a chip |
| L4 control plane: gate | CAM keyed on (measurement, action) + typed comparators + rate and budget counters + hold register + epoch register; on the DPU (A), the carrier (B) or the die (C) | software reference done (`gate.py`, `ledger.py`) |
| L4 control plane: endpoint comparator | ticket verifier + durable consumed-id CAM + epoch register + heartbeat timer in the device that acts (guidance chip, HSM, motor controller, line card) | software reference done (`endpoints.py`) |
| L4 control plane: audit | hash-chain engine to NVM; head and size in a root-owned register; checkpoints signed by the root-derived key | software reference done (`audit.py`) |
| L3 observers | probe heads on isolated compute with their own measurement; verdict signing keys anchored in the policy image | `autonomic-graph-regulation`; NVIDIA Sentry |
| L2 provenance | watermark engine in the sampling stage; registry signer | `Watermark` |
| L1 model and runtime | CPU TEE + GPU TEE; measurement extended with the model manifest digest and the policy digest | confidential computing exists; the two extra measurements are the ask |
| L0 silicon root | UDS, anti-rollback fuses, extend-only registers, DICE, quote engine, TRNG, monotonic counter | exists (vendor roots); modelled in `root.py` |

## 4. The assumptions register

A deployment ships a register with one row per input the gate or an endpoint relies on.
The contract holds only where the register holds.

| Column | Meaning |
|---|---|
| Input | the value compared against a rule (a list entry, a sensor reading, a registry record, a limit, attestation evidence, a witness verdict, the clock) |
| Authority | who may assert it, under which signature |
| Freshness | expiry, nonce or epoch; a stale value is a denial |
| On conflict | the rule when sources disagree (denial, hold, or a stated precedence) |
| Unchecked | what the hardware cannot establish about this input (completeness, correctness, independence of sources) |

Rules:

- Agreement between sources is not independence. A row that relies on "N sources agree"
  names why the sources do not share a failure mode.
- A novelty detector is a witness (L3), never a guarantee against unenumerated cases.
- The semantic residual (a harmful sentence over an allowed channel) is outside the
  register by construction; narrow rulebooks, witnesses and human review live there.
- Each endpoint names its safe transition. "Do nothing" is one option; for some devices
  it is the hazard.

## 5. The policy controller and its enforcement points

A small, isolated controller (verified-kernel class firmware, proof assumptions written
down) manages policy, identities, capabilities, revocation and exceptions. It is not in the
data path. Dedicated checkers at each boundary crossing enforce the capabilities it issues.

| Traffic | Enforcement point | Mechanism |
|---|---|---|
| copy-engine transfers | descriptor processing | capability on every descriptor (IOMMU-class lookup) |
| thread-initiated peer loads/stores (CUDA peer access over NVLink) | GPU MMU peer mappings; NVLink port | mappings only for roster members; link encryption key as the capability on TEE-I/O hardware |
| PCIe to host, NIC, storage | PCIe port (TEE-I/O, IDE) | link keys issued at attestation; ACS against unexpected P2P |
| RDMA across nodes | NIC/DPU filter tables | set only by the controller's signed commands (placement A) |
| GPUDirect Storage | storage channel descriptor path | capability naming the manifest it may deliver |
| display, debug, JTAG, any path without a checker | — | disabled by policy; never assumed safe |
| host memory outside the enclave | CPU TEE | not a valid destination |

Controller blocks: mailbox (only input; signed requests), capability table, peer roster,
hash-and-sign engine, metering counters, policy store + epoch register, heartbeat timer,
halt/throttle lines, log engine. State in the controller's own SRAM/OTP, never in HBM or
host memory. Mailbox command set: `blog/04` Appendix A. Capability schema: Appendix B.

Multi-GPU: mutual attestation at job start builds a roster; checkers pass traffic to roster
members under a job-lifetime capability and to nothing else; the sampling GPU's controller
signs the device-provenance record, which names the roster.

What CUDA changes: nothing for compute. Capability tokens on copy-engine, RDMA and storage
descriptors; roster-bound peer mappings and link keys; a `SIGN_OUTPUT` call; a
`BEGIN_MODEL` manifest call; model manifest digest and policy digest in the attestation
report.

Leakage threat model for permitted channels: unauthorized transfers are blocked;
the token output channel is authorized by definition and needs query budgets, entropy and
rate limits, the provenance lane and audits. The controller makes those enforceable; it
does not make the channel safe.

## 6. Provenance: three claims

| Claim | Mechanism | Status |
|---|---|---|
| Device provenance: this device signed these bytes | controller hash-and-sign engine on the output path (Appendix D record) | buildable (C), or on the DPU for traffic it sees (A) |
| Workload provenance: an attested runtime reports producing these bytes under this configuration | the serving stack inside the CPU TEE signs its own record of request assignment, input and output buffers and transformations | buildable; the runtime joins the trusted computing base |
| Execution integrity: the specified computation produced these bytes | open; candidates: attested runtime as sole writer of the output region; sampling inside the controller's domain; deterministic re-execution audits | research |

`prompt_hash` in a device record is the serving stack's claim, authenticated, not verified.
A signature is a detachable record; a watermark is a different tool; neither opens the gate.

## 7. The authorization protocol

Implemented in `gate.py`, `ledger.py`, `endpoints.py`; figure in `blog/figures/fig_protocol.png`.

1. Broker → gate: typed request {action, typed params, attestation token, witness assertions}.
2. Gate, under one lock, fails closed in order: replay? attested? granted (signed default-deny rule whose constraints the params satisfy)? witnessed?
3. Gate reserves the rule's budget: committed + reserved + amount ≤ limit, else `budget.exceeded`.
4. Gate mints a ticket {request hash, action, params digest, measurement, rule, policy epoch, endpoint, reservation, expiry}; `human` rules park a hold instead, released by an approver's signature over (hold id, request hash).
5. Endpoint admits: gate signature, action, params digest, policy epoch, endpoint name, expiry, never consumed.
6. Endpoint burns the ticket id durably, commits the reservation at the gate, then executes. Gate unreachable → `commit.unreachable`, no execution; the burned ticket is not retried. Unexecuted reservations release at ticket expiry.
7. Every step is appended to the signed audit trail before its result returns.

Invariants:

- Replay state, holds, rate windows, reservations, consumed ids and the epoch survive restart (durable writes before return).
- One ledger owns a budget key; shared allowances are reserved at the owner, never approximated locally.
- A ticket from a superseded policy epoch is refused.
- A ticket names the endpoint it is valid at when the rule says so.
- The gate's key is DICE-style derived from what booted; a restart of the same code keeps the key.
- Requester-supplied fields outside the rule's constraints never influence rule selection or path.

## 8. Claims and their limits

| Claim | Stated as |
|---|---|
| Weights | unauthorized transfers are blocked at every enumerated enforcement point; permitted channels carry a leakage threat model |
| Software testing | tests policy and protocol logic; coverage, reset behaviour, timing, isolation and physical failure need separate validation |
| Alarms | more alarms reduce approvals; false stops can be hazards; every witness has a recoverable false-positive path |
| Failure | each application defines its safe transition |
| Verification | each property depends on hardware, firmware, drivers, configuration and the proof's stated assumptions (seL4's assumption list is the model) |
| Signature | a detachable device-provenance record; workload provenance and execution integrity are separate claims |
| Overhead | under one percent is a target; measured twice (controller alone; whole protected deployment, including tail latency, small requests, collectives, logging, revocation) |

## 9. Hypotheses

H0 contract · H1 attestation binds firmware, model manifest, policy · H2 every boundary
crossing has an enforcement point · H3 policy changes only with a quorum · H4 the broker
cannot choose its rule or path · H5 alarms are monotone · H6 the comparator holds with
every layer above it compromised · H7 the assumptions register is complete · H8 human
override is slow and logged · H9 overhead within target · H10 permitted-channel leakage
within budget. Falsification conditions and the phase plan: `docs/PROTOTYPING.md`.
