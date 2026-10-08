# A Multi-Layer Approach to AI Safety

*Yobie Benjamin · 7 October 2026*

*And why the layer that matters is silicon.*

Two posts ago I made a simple argument: an invisible stamp on AI text is not a safety plan, because the thing people fear is not a paragraph but an action. The companion post went inside OpenAI's watermark and showed exactly what it can and cannot do. This post is about what we do instead.

The short version: safety has to be layered, every layer above the chip is a witness, and the only layer that can be the lock is the one built into silicon. For the models that matter, that silicon is NVIDIA's. The design has to fit CUDA, the GPU's own attestation, and the BlueField data-processing units that now sit on the only path into the model, or it is a design for a world that doesn't exist.

Everything described here runs today as a self-validating reference implementation at [github.com/YobieBenjamin/hardware-and-silicon](https://github.com/YobieBenjamin/hardware-and-silicon). One command, 37 tests, 66 attacks, under a minute.

## Why one layer is never enough

Start with where safety is usually put: inside the model. Safety training teaches a model to refuse. It is real, and it is thin. The refusal behavior of a transformer lives mostly along one direction in its activation space; subtract that direction from the weights and the model answers everything. People call it abliteration, it takes an afternoon on a consumer GPU, and thousands of abliterated models are on Hugging Face right now. Anything that lives inside a weight file lives at the mercy of whoever holds the file.

The next idea is a second model that watches the first. But the judge is a transformer too. It falls for the same prompt injections, it can be abliterated the same way, and it runs as a process that the operator can patch or kill. A judge is a witness. It can keep a gate shut. It can never be the gate.

Watermarks are narrower still. A watermark says which vendor's model wrote these exact words, unchanged, and only the vendor can check. It says nothing about the thousands of unmarked models, and nothing about actions.

So no single layer works, and that is fine, because the layers fail in different ways. A sensor that is fooled by paraphrase, a watcher that is fooled by injection, and a chip that cannot be fooled by either make a system that is stronger than any of its parts, as long as the chip is where the decision is made.

## The layer model

| Layer | What it does | Where it lives | On NVIDIA's platform |
|---|---|---|---|
| **5 · Governance root** | Signs the rulebook, the list of approved firmware, and revocations. Separate from the chip vendor on purpose. | hardware-and-silicon | Policy authority's keys; OpenShell's policy prover checks the derived network rules |
| **4 · Control plane** | Default-deny gate on the only path out: attestation check, rulebook, witnesses, budget, human holds, one-time tickets, tamper-evident audit | hardware-and-silicon | OpenShell supervisor middleware today; a DOCA application on BlueField-4 next; an I/O-stage block in the GPU eventually |
| **3 · Observers** | Fast, cheap early-warning verdicts about a specific request, signed, consumed as witnesses | [safety](https://github.com/YobieBenjamin/safety) | Sentry on BlueField-4 is the required witness; our observer is the optional second |
| **2 · Provenance** | Watermark, hardened detector, retrieval, signed registry; emits a signed provenance verdict | [Watermark](https://github.com/YobieBenjamin/Watermark) | Runs beside the vendor's sampler; its verdict is a witness the gate can require |
| **1 · Model and runtime** | The model, CUDA, the serving stack | NVIDIA | Treated as untrusted. Nothing here is allowed to decide anything. |
| **0 · Silicon root of trust** | Fused device secret, anti-rollback counter, extend-only measurement registers, DICE key derivation, quote engine | hardware-and-silicon | The GPU's confidential-computing attestation and the DPU's own root of trust, bound together |

Three repositories, three lanes, and the only coupling between them is a signed message format documented in [docs/LANES.md](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/docs/LANES.md). Each lane can be deployed, replaced or ignored without the others breaking.

## Layer 2: a sensor, not a lock

The watermark study is written up in two posts in the [Watermark](https://github.com/YobieBenjamin/Watermark/tree/main/blog) repository, so here is only the conclusion. Against copy-paste and every formatting trick, a hardened detector catches 100 percent. Against a 50-percent rewrite it catches 20 percent, and a paraphrase by any unmarked model drives that to zero. Retrieval and a signed registry recover a lot, but only for text the vendor indexed and signed at generation time.

That is exactly what a sensor is: useful when it fires, silent when it can't. In our architecture it emits a signed assertion, `{registry, content_digest, status: exact | tampered | unknown}`, and nothing else. A rule in the rulebook can require that assertion before an outgoing message is allowed. The sensor never opens the gate by itself.

## Layer 3: a small view from biology

The observer lane started as a small study of a question from outside computer science: how do living systems stay safe when the thing making decisions can't be trusted to be right?

The answer biology gives is layered, and it separates the alarm from the muscle. Your spinal reflex pulls your hand off a hot stove before the signal reaches the brain. The fast pathway through the amygdala reacts to a threat before the slow cortex has finished recognizing it. The innate immune system responds to a broad pattern in minutes; the adaptive system takes days to build a precise response. In every case the early warning is fast, cheap, pattern-based and often wrong, and the system tolerates the errors because the warning does not act on its own. It raises the threshold for everything downstream.

That is the design of the observer lane. An observer watches the stream of requests an agent makes and emits a signed verdict about one specific request: a risk score, a set of flags, a short expiry. It is deliberately simple. It does not understand the request the way a judge model would; it looks for the shape of trouble, the way an immune system looks for a pattern on a cell wall. It can fire early. It can fire wrongly. And the gate treats it exactly as biology treats a reflex: a required signature on consequential actions, never the thing that moves the arm.

The interface is the only hard part, and it is fixed: `{type, observer, subject = hash of the request, risk, flags, issued_at, expires_at}`, signed under a key the control plane anchors. The control plane ships with a stand-in observer so it can be tested without the safety repository at all. That lane was always meant to be a small window. The big one is below.

## Layers 0, 4 and 5: the control plane, and the chip under it

This is the lane that matters, and it is the one we built out first. The design rule is that the model is never the one who decides. The sequence for every consequential action is:

1. **Prove the compute.** The chip that is about to act has measured the code it booted into extend-only registers, derived its signing key from that measurement (DICE: different code, different key), and signed a quote with a fresh nonce. A verifier checks the vendor chain, the measurement against a signed allowlist, the anti-rollback counter, and the binding between the CPU's quote and the GPU's. Pass, and it issues a five-minute token naming the firmware fingerprint.
2. **Consult the rulebook.** Signed by the governance root, default deny, rules granted to a *fingerprint* rather than a device: this exact code may transfer up to this amount, in this currency, to this pattern of accounts, this many times a minute. No rule, no path. There is no rule for exporting weights.
3. **Collect the witnesses.** The rule names them: an observer verdict under a risk limit, a provenance verdict for outgoing text, both or neither. Each must be fresh, signed by an anchored key, and about this exact request.
4. **Check the budget, hold for a human if required, then issue a ticket.** A one-time signed ticket, good for 60 seconds, bound to a hash of the exact action and its parameters. The endpoint that moves the money verifies the ticket itself. Change the amount after the ticket was issued and the hash breaks. Present it twice and the second is refused.
5. **Write it down where nobody can erase it.** Every decision goes into a hash chain with a signature on every entry and periodic signed Merkle checkpoints, the Certificate Transparency construction. Edit, delete, reorder or truncate the log and the break is provable with a few dozen bytes.

We attack all of it. The catalogue has 66 attacks and 10 legitimate baselines, every one named for the layer it hits:

| Layer | Attacks | What they try |
|---|---|---|
| Chip and attestation | 11 | patched firmware, firmware that lies about its measurement, rollback, cloned and revoked chips, replayed and foreign nonces, a swapped GPU |
| Governance | 3 | forged allowlist, forged rulebook, a rulebook that is not default-deny |
| Control plane | 21 | missing, forged, expired and wrong-workload tokens; ungranted actions including weight export; parameter tricks; rate bursts; replays; executing a held action; forged, mis-bound, replayed and late approvals |
| Witness interfaces | 10 | missing, forged, stale and re-targeted observer and provenance verdicts |
| Tickets | 6 | no ticket, replayed, re-parameterized, re-targeted, forged, expired |
| Audit trail | 8 | edited, deleted, reordered, truncated, forged checkpoint, rewritten history, fake inclusion proof |
| NVIDIA path | 13 | unattested and stale sandboxes, drift quarantine, repeated-denial quarantine, cross-sandbox ticket replay, dual-witness logic in every failure direction |

All 66 are blocked with the reason code the design predicts, and all 10 baselines go through. A gate that denied everything would pass every attack and be worthless.

## Why NVIDIA, and only NVIDIA

Frontier models are trained and served on NVIDIA GPUs through CUDA. Other accelerators exist. None of them is where the risk is, so none of them is what a safety design has to fit. The good news is that NVIDIA has already built most of the lower floors.

- **The GPU can prove what it is running.** Since Hopper, NVIDIA's data-center GPUs ship a confidential-computing mode: the GPU measures its firmware, attests it with a device-unique key endorsed by NVIDIA, and encrypts the traffic between the CPU enclave and the GPU. That is our Layer 0 quote, in real silicon, today. Our verifier is written to the same roles (RFC 9334) and binds the GPU's evidence inside the CPU's.
- **There is a chip on the only path into the model.** On 28 September 2026 NVIDIA announced the Open Agent Safety Platform: OpenShell, an open-source runtime that sandboxes every agent and routes all of its traffic through a policy-enforcing supervisor, and Sentry, a reference design on BlueField-4 DPUs that watches from separate hardware, out of band, and can quarantine an agent in milliseconds. On Vera Rubin systems that DPU sits on the node's only path to the model. That is where our Layer 4 gate wants to live, and our stack already runs as OpenShell supervisor middleware with Sentry as its required witness, OpenShell's network policy derived from our signed rulebook, and the audit trail exported in NVIDIA's OCSF format.
- **CUDA is the runtime, and the runtime is untrusted.** We do not put any enforcement in CUDA, in drivers, or in anything the operator can patch. The model, its kernels and its serving stack are Layer 1: watched, measured, never trusted to decide. The enforcement sits below them in the GPU's attestation and beside them in the DPU, where the model cannot reach.

NVIDIA's own five principles for the platform read like our design notes: policy verifiable before the agent runs; enforcement out of band; the path to the model as the control point; an agent's authority scaled to how visible its reasoning is; and labs, enterprises and hardware makers each owning a layer. We own the layer between the policy and the wire.

## What only silicon gives

Our software blocks every logical attack in the catalogue. It cannot give five properties, and they are the reason the chip exists.

1. **Keys that cannot be extracted.** In Python the device secret is a private attribute. In silicon it is a fuse array feeding a key engine with no read port, so it never exists in memory a debugger, a DMA engine or a cold-boot attack can reach.
2. **No path around the gate.** The ticket check becomes a comparator on the wire itself, in front of the network card, the PCIe port, the NVLink egress. There is no function to call with no ticket, because there is no wire that carries a request past the comparator.
3. **Logic that cannot be patched.** Boot code in ROM, extend-only registers with no write port, a version counter in fuses. The operator can hold the chip in reset. The operator cannot make it lie.
4. **Fail closed by physics.** Lose attestation and the accelerator's I/O stays gated, not because a daemon decided to deny but because the comparator has nothing to match.
5. **Tamper evidence that survives the host.** The audit log's head hash and size live in a register the chip owns. Wipe every disk, and the chip still reports that it signed a checkpoint at a log size you no longer have.

## Clues to the silicon design

The comprehensive design is the next post, and I want it to land as a design, not a sketch, so this section is deliberately a set of clues.

- **The chokepoint is I/O, not compute.** A model can think whatever it likes inside the GPU. Nothing it thinks matters until bytes leave: over NVLink to another GPU, over PCIe to the host, over the network. Those are the wires the comparator sits on. Gating kernel launches would be the wrong place; gating egress is the right one.
- **Three placements, in order of ambition.** First the DPU, programmed with DOCA, beside Sentry, because the hardware ships and the chokepoint is already there. Second a board-level safety controller between the GPU's egress and the rest of the system, which also covers GPU-to-GPU traffic. Third an I/O-stage block inside the GPU itself, next to the attestation root it already has. Each placement gives properties the one before cannot.
- **Weights never leave without a ticket.** The copy engines that move data off the GPU are the natural place to require a ticket for any transfer that touches the weight region. Exfiltration of a model is the action a frontier lab fears most, and it is the easiest to describe as a rule: there is no rule for it.
- **The gate is a lookup table and a comparator, not a processor.** A rulebook entry is a fingerprint, an action class, a few typed limits and a rate. That is content-addressable memory and a handful of comparators, which is why the latency budget is nanoseconds, not milliseconds, and why it can sit on the data path at all.
- **The log head is a register.** One register holding the current chain hash, one holding the size, both updated only by the audit block itself, both readable by anyone. Checkpoints are signed from inside the chip with the DICE-derived key.
- **The same 66 attacks are the acceptance test.** Every phase of the design, from the formal state machines to the FPGA emulation, is finished when the same sweep passes against that phase's artifact. The catalogue is the constant.

## The roadmap

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Functional reference: every block as software, every attack as a test, message formats fixed | Done |
| 2 | Formal specification: state machines for the root, the gate and the log; invariants written down (no ticket without a token, no allow without a rule, log head only moves forward) and model-checked against the code | Next |
| 3 | The silicon design: block diagram, interfaces, the lookup-table and comparator micro-architecture, key and fuse map, latency and area estimates for the three placements, written for NVIDIA's platform | The comprehensive post |
| 4 | Emulation: the Layer 4 block on an FPGA, driven by this same harness over a real PCIe or Ethernet path | After 3 |

## The point

Watermarks tell you who wrote the text. Watchers tell you something looks wrong. Neither can stop anything, and they were never going to, because they live above the model, in software the model's owner can change. The layer that stops things has to live below the model, in silicon that proves what it runs, gates what it touches, and records what it did where no one can erase it. On NVIDIA's platform most of that silicon already exists. The next post is the design for the part that doesn't.

## Run it yourself

```bash
git clone https://github.com/YobieBenjamin/hardware-and-silicon
cd hardware-and-silicon && ./run.sh    # 37 tests, 66-attack sweep, report
```

*Sources: NVIDIA Technical Blog, "NVIDIA Open Agent Safety Platform: A Reference for Continuous In-Silicon Agent Monitoring" and "Add Runtime Controls to AI Agents with NVIDIA OpenShell" (28 September 2026); NVIDIA Confidential Computing documentation; RFC 9334 (Remote Attestation Procedures architecture); RFC 6962 (Certificate Transparency); the TCG DICE specifications. This post is documentation under CC BY-NC 4.0; the code is under the PolyForm Noncommercial License 1.0.0; attribution required, commercial use by separate license (see [LICENSING.md](https://github.com/YobieBenjamin/safety/blob/main/LICENSING.md)).*
