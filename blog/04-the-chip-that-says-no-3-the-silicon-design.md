# The Chip That Says No

By Yobie Benjamin · October 12, 2026 · Part 3 of 3: the silicon design

> Parts 1 and 2 made the argument. The first post in this repository laid out the layer model and shipped the reference stack. This is the design that post promised: where each layer goes in silicon, the theory each piece rests on, how the pieces talk to each other and to the model, how they sit against the GPU, the CPU, memory and storage, and the experiments that would prove or disprove each claim. A chip designer went through my first draft and corrected it in seven places. His corrections are built into this one, and the biggest of them changed the shape of the design. The promise is narrower than my first draft claimed, and stronger, because it is a security contract at the point of action rather than a promise about a chip. I will keep the technical depth, and I will explain every piece of it with something you can picture.

## Where we are

The argument from Parts 1 and 2, in four lines:

1. The guard cannot be another AI. A guard must be tamperproof, always invoked, and small enough to verify. A model fails all three tests.
2. Prevention lives at the point of action. A cluster of GPUs can think anything. The catastrophe cannot happen until one wire goes high. Guard the wire, not the crowd.
3. Every action goes through the gate. How hard the gate looks, and how long it pauses, depends on what the action can do.
4. Any model may raise STOP. No model may clear it. Alarms are cheap when wrong. Clearing one takes a fixed rule or a human key.

The layer model from the first post, which the rest of this design is placed on. Think of it as the floors of a building, from the basement up:

| Layer | What it does | Where it lives |
| --- | --- | --- |
| 5 · Governance root | Signs the rulebook, the list of approved firmware and the revocations. Separate from the chip vendor on purpose | this repo (`attest.py`) |
| 4 · Control plane | The default-deny gate on the only way out: attestation check, rulebook, witnesses, budget, human holds, one-time tickets, audit trail | this repo (`gate.py`, `ledger.py`, `endpoints.py`, `audit.py`) |
| 3 · Observers | Fast, cheap early-warning verdicts about one request, signed, used as witnesses | `autonomic-graph-regulation`; NVIDIA Sentry |
| 2 · Provenance | Watermark, hardened detector, signed registry; emits a signed verdict about where text came from | `Watermark` |
| 1 · Model and runtime | The model, CUDA, the serving stack, the sandbox | NVIDIA; treated as untrusted |
| 0 · Silicon root of trust | A secret fused into the chip, a counter that only counts up, measurement registers that can only be added to, a key derived from what booted, a quote engine | this repo (`root.py`); the GPU's and the DPU's own roots |

And the crosswalk to the brain tiers of Parts 1 and 2, so the two vocabularies stay in step:

| Brain tier (Parts 1 and 2) | This design | Repo module |
| --- | --- | --- |
| Reflex: fastest, dumbest, cannot be talked out of its job | The endpoint comparator: the ticket check inside the device that acts | `endpoints.py` |
| Deep alarm system: default deny, fast global stop | The Layer 4 gate | `gate.py`, `ledger.py` |
| Thinking brain: slow, deliberate, overrides with effort | The governance root and the approvers (Layer 5) | `attest.py`, approvals in `gate.py` |
| Senses and alarms: may raise, never clear | The observer and provenance lanes (Layers 3 and 2) | `assertions.py`, `oasp.py` |

## What changed after the review

Seven corrections. I took all seven. Each one is worked into the sections below. This list is here so a reader of the first draft can see what moved.

1. **A chip is not a boundary.** "One safety chip per GPU" is a packaging choice, not a security boundary. The unit this design protects is an *enforcement domain*: a defined set of processors, memory, interfaces and action endpoints whose exits are all controlled. A chip governs only the paths it has non-bypassable authority over.
2. **Not everything is a DMA descriptor.** DMA is how data moves between memory and devices without the processor copying it by hand, and a descriptor is the work order for one such move. My first draft checked those work orders and called it coverage. But CUDA lets a GPU thread read and write a neighboring GPU's memory directly, with no work order. So enforcement has to be spread out: a small controller sets policy, and dedicated checkers at every boundary crossing enforce it.
3. **A signature proves less than I claimed.** A controller that signs the bytes in an output buffer proves that *this device signed these bytes*. It does not prove that the model produced them. Provenance is now three separate claims, and the design says which mechanism delivers which.
4. **Every action is authorized.** Whether an action can be undone decides how much checking and delay it gets, never whether it is checked. A compromised broker must not be able to skip the gate by labeling an action "reversible." My first draft had that hole. The reference stack never did, and this draft matches the stack.
5. **Binding is a transaction.** A signed ticket on its own does not give an irreversible action the guarantees it needs. Checking permission, reserving a shared budget and committing the action are one coordinated protocol, with replay protection that survives a restart, a tie to the version of the rules, and one owner per budget.
6. **Trusted hardware does not make declared facts true.** The gate compares a value it was given against a protected rule. It still needs a good reason to trust the value. Every guarantee now carries an explicit list of assumptions: which inputs are trusted, how fresh, what happens on conflict, what the hardware cannot check.
7. **The absolute claims are narrowed.** "No weights can leave" becomes "unauthorized transfers are blocked, and the permitted channels need their own threat model." "Failure means an action not taken" becomes "each application defines its safe move." "Software tests everything except tamperproofness" becomes "software tests the logic; coverage, reset, timing, isolation and physical failure need separate validation." The full table is near the end.

## The contract

Here is the central guarantee, in the form the reviewer suggested and this design adopts:

> Within a declared enforcement boundary, every protected operation requires a fresh authorization bound to that exact operation. The endpoint enforces specified invariants independently of the proposing model, subject to explicit assumptions about its inputs, its hardware, and its policy authority.

Think of a bank vault. Every withdrawal needs a fresh signed slip for that exact withdrawal, this amount to this account, and the teller who checks the slip does not care how persuasive the customer is. The vault is only as good as its walls, so you say where the walls are. And the teller is only as good as the signature book, so you say who is in it. That is the whole sentence.

Three things about it carry the whole design.

It is a statement about the *point of action*, not about the GPU. The GPU-side silicon (the policy controller and its enforcement points, below) provides containment and provenance. It keeps the weights in, keeps unattested traffic out, and makes outputs traceable. Those are valuable, and they are secondary. The thing that prevents the strike on the school is the comparator in the weapon. The thing that prevents the fraudulent transfer is the comparator in the payment switch. Prevention lives where computation becomes physics. Part 2 argued that from the brain's final common path. The review made it the primary claim.

"Every protected operation" means every one. Not "every irreversible one."

"Subject to explicit assumptions" is not a disclaimer. It is a design element with its own table.

![One signed path from thinking to acting; the guarantee lives at the endpoint](figures/fig_stack.png)

Six pieces sit on the compute side and three on the action side. The only path from the left column to the right is the typed request the broker submits. The only path from the gate to the world is a ticket with a reservation behind it. The two highlighted boxes are the ones to put in silicon: the policy controller with its enforcement points, and the gate as a comparator.

## Enforcement domains

Picture a castle. A guard at the drawbridge is worth nothing if there is a hole in the back wall. Before you post guards, you walk the walls and count the gates. That walk is the first design act, because a controller can only govern paths it has non-bypassable authority over. A companion chip sitting beside a GPU does not automatically control GPU-to-GPU traffic, network requests the CPU starts, or other devices on the bus. A halt line gives it emergency shutdown authority, and shutdown cannot undo an action that already escaped.

The first post gave three placements for the Layer 4 block (DPU, board-level controller, in-GPU block). Here they are with the fourth that the review made primary, and with what each can and cannot promise:

| Placement | Credible role | Principal limitation |
| --- | --- | --- |
| **E · Gate at the action endpoint** (the payment switch, the guidance chip, the robot controller, the gateway) | Reject unauthorized operations before they commit; re-check with the device's own sensors; define the safe move | Protects only endpoints that enforce it; needs its inputs (lists, maps, sensors) to be trustworthy |
| **A · DPU on the node's path** (BlueField-4 with DOCA, beside NVIDIA Sentry) | Enforce policy on every packet and storage request that crosses that path; own root of trust; isolated from the host | Other paths bypass it: PCIe peer-to-peer and NVLink between GPUs are not on the DPU's path |
| **B · Board-level safety controller** | Keys, policy, watchdogs, authorization, protected logs; gate the GPU's PCIe and NVLink exits on a custom carrier board | Needs hardware cooperation to block other components' traffic; bandwidth and latency on the hot path |
| **C · Controller integrated into the GPU and its fabric** | Control accesses at hardware enforcement points inside the package: copy engines, peer mappings, link keys | Requires the vendor |

In castle terms: E is the usher inside the throne room door, A is the toll booth on the main road, B is a guardhouse on the grounds, and C is a lock on every door of the keep. The design rule that follows: **E is always present and is the guarantee. A, B and C add containment and provenance in increasing order of coverage.** A deployment can run E alone, say a benign payment service with a hardware-gated endpoint and no GPU-side silicon at all, and still have the contract. It cannot run A, B or C without E and have it.

## What a chip can know

Silicon sees bits. A token is an integer. The meaning of a token exists only inside the model's weights while a kernel is running. There is no point on the chip where a controller could read "school" off a wire, because "school" is not on any wire. It is a pattern spread across billions of numbers. The objection "a chip only knows 0 and 1, so it cannot know right from wrong" is correct, and the design accepts it completely.

A bar-code scanner at the supermarket does not know what a banana tastes like. It knows whether the number on the sticker matches the price list. That is all the silicon here does, and it does three things bits are good for:

- It decides which bytes may cross which boundary. A model's effect on the world is always a transfer: to host memory, to a neighboring GPU, to a network card, to a disk, to a motor. Transfers are finite, countable, and visible to hardware at the point where they cross a boundary.
- It signs what leaves. A signature binds bytes to the device, the firmware, the loaded model and the policy, without knowing what the bytes say.
- It checks a typed record against a rulebook. Meaning enters silicon in exactly one place: the request the broker builds, a form with typed fields describing the action the model proposes, checked by a gate the model cannot write to and re-checked by the device that acts.

That third point is the smoke-detector principle from Part 1 made concrete. The detector does not understand fire. It measures smoke against a threshold. The gate does not understand targeting. It measures coordinates against a map, and whether the map can be trusted is a separate question with its own table below.

## Where the bits live

A model's data lives in eight places, and it changes form at almost every one. Think of a warehouse: receiving dock, sorting room, shelves, the conveyor between buildings, the loading dock. The security is at the doors, not at the shelves. The gates in this design sit where data crosses a trust boundary, not where it means the most.

![Where the bits live: eight stations, four gates](figures/fig_datapath.png)

| Station | What is there | Form | Trust domain | Gate |
| --- | --- | --- | --- | --- |
| 1 · Storage at rest | Weights, tokenizer vocabulary, training-data shards, policy images, logs | Encrypted files; weights as safetensors in bf16 or fp8; data as token shards | Keys released only to a verified loader | Yes: decryption bound to attestation (L0) |
| 2 · CPU | Tokenizer, scheduler, serving stack (vLLM, TensorRT-LLM, SGLang), broker, OpenShell sandbox | Text in; int32 token IDs out; typed requests | CPU TEE (Intel TDX, AMD SEV-SNP, Arm CCA) | No gate on compute; the broker proposes, the gate decides |
| 3 · Host memory | Prompt and output token IDs, request metadata, KV-cache spill | int32 arrays, structs | Encrypted by the CPU TEE; the hypervisor cannot read it | No |
| 4 · Interconnect | PCIe to host, NIC and NVMe; NVLink to peers; RDMA across nodes; GPUDirect Storage | DMA descriptors, thread-initiated peer loads and stores, link frames | Each link is a boundary crossing | Yes: an enforcement point on each kind of crossing |
| 5 · GPU HBM | Weights, KV cache, activations, logits | bf16 / fp8 tensors; paged KV blocks | GPU TEE: hardware firewall, host cannot read | No; the firewall is the protection |
| 6 · Streaming multiprocessors | Embedding lookup, attention, projections, sampling | Vectors and logits in registers and shared memory | Inside the GPU TEE | No. Compute runs free. |
| 7 · Output path | Sampled token IDs leaving the GPU | int32 IDs per decode step | Crosses from the GPU TEE to the CPU TEE | Yes: device provenance (hash and sign) |
| 8 · Beyond the chip | Typed request to the gate; ticket to the endpoint; endpoint to the world | Signed records | The endpoint's own trust domain | Yes: the gate, then the comparator |

A TEE, for the record, is a trusted execution environment: a locked room inside a processor where the code and data are shielded from everything else on the machine, including the operating system.

Three things in this table carry the design.

The model's thinking (stations 5 and 6) is untouched. No gate sits in the kernel path. That is what keeps the design compatible with trillions of tokens: the hardware's work grows with boundary crossings and actions, not with compute.

Station 4 is where the second review point lands. A copy engine moves data using a work order the hardware processes one at a time. A permission check on a work order is the same kind of operation as an IOMMU lookup, the check every server already does when a device touches memory. But a CUDA kernel can also read and write a neighboring GPU's memory directly, with ordinary loads and stores over NVLink, once peer access is turned on. Those never see a work order. So the enforcement for station 4 is not one checker but several, each at the hardware point the traffic actually passes (the enforcement-point table, below), and any path with no checker is shut by policy rather than assumed safe.

Training data has a station too. During training, the shards moved into GPU memory pass the same enforcement points as everything else, so the controller can record which dataset a model was trained from, and that record travels with the model's fingerprint.

## The action side: the primary guarantee

### The authorization protocol

In Part 2 the permission was a concert ticket. Here is the whole box office.

My first draft bound an action to a form and checked it twice. That is necessary and not enough. Four failures survive a signed, bound, single-use ticket on its own:

- A valid ticket can be reused after a restart, if the record of its use was only in memory.
- Two requests arriving at the same time can both pass a shared budget check, if checking and reserving are separate steps.
- The recipient on the ticket can differ from the recipient at execution, if the binding covers the action but not every field and the destination.
- A ticket can stay good after the rules that issued it have changed.

So authorization is a transaction in three coordinated steps. This is how `gate.py`, `ledger.py` and `endpoints.py` implement it today:

![Authorize, reserve, commit](figures/fig_protocol.png)

1. The broker presents a typed request: the action, the typed fields, the attestation token for the software that is asking, and the witness statements the rule demands (an observer verdict from Layer 3, a provenance verdict from Layer 2).
2. The gate answers four questions in order and fails closed on the first that fails. Is this request a replay? Is the software verified? Is there a signed rule for this software and this action whose limits the fields satisfy? Have the required witnesses spoken, freshly, about this exact request?
3. If the rule names a **budget** (a shared allowance, say 2,000 dollars of small payments per hour), the gate **reserves** the amount. Committed plus reserved plus this amount must stay within the limit. The replay check, the rate window, the reservation and the ticket are one critical section under one lock. In box-office terms, one clerk sells one seat at a time, so two customers cannot buy the same seat.
4. The gate mints a one-time **ticket** bound to the request hash, the action, a digest of every field, the software fingerprint, the rule, the **policy epoch** (the fingerprint of the rulebook that issued it), the endpoint it is valid at, and the reservation. Rules that need a human park the request as a hold instead. An approver's signature over the hold id and the request hash releases it and mints the same ticket.
5. The endpoint, the usher at the door, checks six things before it admits the ticket. The gate's signature is real. The action and the field digest match what it is about to do. The policy epoch is the one it currently accepts. The endpoint name is its own. The ticket has not expired. The ticket id has never been used before.
6. The endpoint **burns** the ticket id in storage that survives a power cut, then phones the box office to **commit** the reservation, and only then acts. If the gate cannot be reached, the endpoint refuses (`commit.unreachable`). A burned ticket is not retried; a new one is requested after the line comes back. An unused reservation is released when its ticket expires, so a crashed client cannot sit on a budget forever.
7. Every step is appended to the signed, hash-chained audit trail before its result is returned.

The persistence rule is simple: a change is written to the store before the call returns. The replay store, the rate windows, the holds, the reservations and the endpoint's used-ticket set all come back after a restart. The gate's signing key is derived the way DICE derives a key, from what booted, so a restart of the same code gets the same key back and an outstanding ticket still verifies.

Two consequences for big deployments. A budget key is owned by exactly one ledger. Several gates each checking a shared allowance locally can still overspend it together, so a shared allowance is reserved at the ledger that owns it, never estimated. And a ticket that names an endpoint cannot be presented to another service that happens to offer the same action.

In silicon, each of those is a small block. The replay store is a counter that only counts up plus a small content-addressable memory in the root's non-volatile storage. The ledger is a set of hardware counters owned by the gate block. The epoch is the rulebook's fingerprint in a register the host cannot write. The lock is the fact that the block handles one request at a time.

### The gate

**What it is.** The Layer 4 control plane: a default-deny rulebook signed by the governance root, keyed on the software fingerprint (what code is running, never which chip), with typed limits, witness requirements, rate limits, budgets and human holds. It is software today (`gate.py`). In silicon it is a content-addressable memory plus comparators: a rulebook entry is a fingerprint, an action class, a few typed limits and a rate. That is why the latency budget is nanoseconds and why it can sit on the data path at all.

**Theory.** If every path to an endpoint passes through the gate, and the gate's rulebook can only be changed by the governance root, then the model's power is bounded by the rulebook rather than by the model's manners. Claim: for any model, no action reaches an endpoint without a ticket the gate minted under a rule the governance root signed.

**Every action is authorized.** The rule's `requirement.mode` decides the lane: `auto` (verification and limits are enough; microseconds), `observer` (a fresh Layer 3 verdict under a risk ceiling is required), or `human` (the request is held until an approver signs). That is airport security again. What the traveler says about himself changes nothing. A `risk_class: reversible` field in the request, or a `requirement: auto` field, is ignored, because the rulebook picks the rule from the fingerprint, the action and the limited fields, and from nothing else. The catalogue has an attack for exactly that (`TX.risk_label_ignored`): a 25,000 dollar payment labeled reversible is held like any other.

**Witnesses, in the direction biology allows.** Observers (the `autonomic-graph-regulation` repo's early-warning lane; NVIDIA Sentry on the DPU) and the provenance registry (the `Watermark` repo) emit signed verdicts about one request hash with short expiries. The gate consumes them. It never computes them. A verdict can keep the gate shut. It cannot open it. The novelty check from my first draft belongs here too, as a witness: a request whose fields fall outside everything seen before is a good extra reason to stop. It is not a guarantee against dangers nobody listed. Familiar values can form a dangerous combination, and unfamiliar values can be harmless. The review was right that the first draft leaned on it too hard.

**Interfaces.** Up: the governance root signs its rulebook, allowlists and revocations; approvers release holds. Down: it issues tickets to endpoints and commits their reservations. To the compute side: it accepts typed requests from the broker and verification tokens from the verifier. To the model: none. The model never talks to the gate. The broker does, in a form the model cannot forge.

**Two worked examples.** A targeting model proposes a strike. The broker emits `{action: strike, params: {lat, lon, munition, time}}`. The rule for `strike` has an `observer` requirement and a limit on the coordinates against the signed protected-site list. The coordinates match a school. The gate denies with `constraint.target.not_allowed`, and the audit trail records it. No pause was needed; the rule was decisive. A payment agent proposes a transfer. The broker emits `{action: payments.transfer, params: {amount: 25000, currency: USD, destination: acct-654321}}`. The rule for amounts above 1,000 dollars is human-held. The gate parks it. An approver signs. The ticket is minted. The endpoint checks it, commits the reservation and executes.

**How it fails.** Stale lists. Rules with gaps. Witnesses tuned too loose (misses) or too tight (constant holds that train approvers to sign without reading). The last one is the sneakiest, and its measurement is in the experiment program.

### The endpoint comparator

**What it is.** The reflex, in the device's own silicon: the missile's guidance chip, the payment switch's hardware security module, the robot's motor controller, the gateway's line card. It holds the gate's public key, its own copy of the lists or map it needs, its own sensors, a used-ticket set that survives power loss, the current policy epoch, and a heartbeat timer. It re-checks at the moment of action, against its own inputs, so a request that lied cannot survive the last step. It depends on nothing above it. It is the usher who looks at the ticket and then looks at the seat.

**Theory.** If the final re-check uses the device's own sensors and its own copy of the list, then taking over every layer above it is not enough to cause the catastrophe. Claim: with every layer above the comparator compromised, an in-class catastrophe still does not occur, as long as the comparator's inputs are current and consistent. That last clause is the assumptions register.

**Safe moves.** My first draft said failure always means an action not taken. The review corrected it. Each application has to define its own safe move, and stopping abruptly can itself be the hazard. For a missile, the safe move is no release. For a payment switch, decline. A train can just stop. An airplane cannot; its safe move is a controlled glide, and a surgical robot's is a controlled withdrawal. Designing that move is part of the endpoint's specification. What the contract guarantees is that the device goes to its specified safe move, not to "nothing."

**Interfaces.** Up: it accepts tickets from the gate and commits reservations at the gate. To the world: the release line, the signing key, the motor driver. To everything else: nothing. It has no general network stack to speak of, which is a feature.

**How it fails.** Stale lists and maps. Faked sensor readings. A shared failure that makes several sensors agree on a wrong answer, which is why "several sensors agree" is not the same as "independent sources agree." A heartbeat too fragile for the field.

### Governance root and approvers

**What they are.** The slow tier. The governance root signs the rulebook, the firmware allowlist and the revocations, and it is deliberately not the chip vendor: the party that decides what may run a consequential workload is not the party that sold the chip. Approvers hold the keys that release holds, and for the highest-authority actions, several of them. An override is a ceremony: several people, a written reason, a log entry, and time. Like the two keys on a missile console that have to turn at the same time, by two people who cannot reach both.

**Theory.** Slowness at the top is a feature. The amygdala can be overridden by the cortex, but only with effort and only slowly. A fast override would make the freeze worthless. Claim: override latency and logging are what keep the lower tiers meaningful. A stack whose human override is fast and silent is a stack with no lower tiers at all.

### The assumptions register

Trusted hardware does not make declared facts true. The gate reliably compares a supplied value against a protected rule. The value still has to come from somewhere, and the contract depends on where. Every deployment of this design carries a register like this one, the list taped to the wall, and a guarantee is only as good as the rows it rests on.

| Input | Who is authoritative | Freshness | On conflict | What the hardware cannot check |
| --- | --- | --- | --- | --- |
| Protected-site list / no-strike map | The deconfliction authority's signed list, countersigned by the governance root | Expiry on every entry; a stale list is a denial, not a pass | Any listed source saying "protected" wins | Whether the list is complete |
| Navigation fix at release | Two independent sources (satellite plus inertial, or terrain-matched) that agree within a bound | Per-fix timestamp from the device's own clock | Disagreement is a denial | Whether the sources share a failure mode |
| Payment recipient identity | The sanctions and beneficiary registries, signed | Registry version in the ticket's epoch | A new beneficiary is held, not approved | Whether the registry entry is correct |
| Budget and limits | The rulebook, signed by the governance root | Policy epoch | Old epoch is a denial | Whether the limit is the right limit |
| Attestation evidence | The vendor's device certificate chain plus the governance root's reference values | Nonce per verification; token expiry in minutes | Any mismatch is a denial | Side channels; physical extraction |
| Observer verdicts | Keys the gate anchors from the signed policy image | Seconds; bound to one request hash | A missing or stale verdict is a denial | Whether the observer is right |
| The clock | The root of trust's counter that only counts up | none | A clock that moves backwards is a halt | Drift against wall time |

The register is also where the hard residual lives. A sentence that persuades a human over an allowed channel passes every row. That is where narrow rulebooks, the observer lane and human review live, and it is why the contract says "protected operation" and not "harm."

## The compute side: containment and provenance

The compute side keeps the model inside its box, makes its outputs traceable, and hands the gate a verification it can trust. None of this is the guarantee. All of it is what makes the guarantee cheap to rely on.

### Layer 0: the silicon root of trust

**What it is.** Think of a birth certificate burned into the chip at the factory, plus an odometer that only counts up, plus a logbook you can add pages to but never tear pages out of. In hardware terms, the birth certificate is a unique secret fused into the die that only the key-derivation engine can read. The odometer is an anti-rollback fuse counter plus a counter that only counts up. The logbook is a set of measurement registers that can only be extended, never written. Around them sit a ROM-resident DICE engine that derives the signing key from the measurement of what booted, a quote engine, and a random-number generator. On NVIDIA GPUs the vendor's version of this chain covers the VBIOS and the GSP firmware (the GSP is the RISC-V management processor on the die), and the DPU has its own. The reference models both (`root.py`) and binds the GPU's quote inside the CPU TEE's, which is the composite-attestation pattern of NVIDIA confidential computing.

**Theory.** Trust is monotone upward: nothing can be more trusted than the thing that loaded it. If the bottom of the chain is physics (fuses, ROM), anything the chain reports can be checked against physics rather than against a claim. Claim: a chip with a valid root cannot run modified firmware without the modification appearing in its quote. It also cannot forge a quote for firmware it did not boot, because the key that signs the quote was derived from what it did boot. The house key is cut from the shape of the house. Change the house and the old key no longer fits.

**How it fails.** Fab-level compromise, key extraction by decapping or fault injection, vendor signing keys leaking. None are cheap. None are prevented here. Tamper response, key diversity and public logs of firmware hashes mitigate them.

**Experiment.** The catalogue's Layer 0 block: patched firmware, lying firmware, rollback on fused and unfused chips, cloned and revoked chips, replayed and foreign nonces, a swapped GPU. Eleven attacks, all blocked with the predicted reason code.

### Layer 1: the measured runtime, in confidential compute

**What it is.** The CPU TEE and the GPU TEE, verified together. The locked room, with an ID check at the door. GPU memory is walled off from the host by hardware firewalls. PCIe traffic is encrypted (Hopper uses encrypted bounce buffers; NVIDIA describes Blackwell as TEE-I/O capable, with protection extended to NVLink). The GPU produces a signed report of the firmware it is running. The reference's permissions are keyed to the workload fingerprint, `H(cpu firmware digest, gpu firmware digest)`. The design extends that fingerprint with the model manifest's digest, so a permission is granted to *this code running this model*, and with the policy image's digest, so every record names the rules in force.

**Theory.** If the weights decrypt only inside verified hardware whose memory cannot be read from outside, the model is bound to the hardware. Claim: no process outside the verified enclaves reads weights or activations, and every record can be traced to an attestation.

**Interfaces to the GPU and CUDA.** The CUDA driver already cooperates with confidential-computing mode. Kernels run unchanged inside the enclave. Copies between the enclaves take the encrypted path. The CPU TEE and the GPU TEE set up their session with an SPDM-based key exchange on current hardware, and for the job's duration the two enclaves are one trust domain. The weight loader inside the CPU TEE fetches encrypted weights, and the key service releases the key only after both attestations check out.

**How it fails.** Side channels. Firmware bugs in the firewall. A compromised loader that runs an unverified model on verified hardware, which is why the model manifest belongs in the fingerprint.

### The policy controller and its enforcement points

This is the Layer 4 block in silicon on the compute side, and it is the piece that does not exist. My first draft called it a governor and described it as one component that handled every transfer. The review's second point changed the architecture: the trusted part stays small, and the enforcement is spread out.

Here is the picture. A big building does not have one guard who personally checks every door. It has a small security office that programs the badge readers, and a badge reader on every door. The readers do not call the office for each person. They are programmed once and refuse on their own. The office handles the exceptions and keeps the log.

![A small controller sets policy; checkers at every exit enforce it](figures/fig_package.png)

**What it is.** Two things. First, a small, isolated controller that manages policies, identities, permissions, revocation and exceptions. Its firmware is in the class of a verified kernel such as seL4: a few thousand lines, with its proof assumptions written down. Second, dedicated hardware checkers at every point where a transaction crosses the domain's boundary. The controller does not sit in the data path and does not touch every transaction. It configures the checkers and handles what they refuse. Its state (the permission table, the log head, the metering counters, the policy epoch) lives in its own SRAM and one-time-programmable memory, never in GPU memory or host memory. The only way in is a mailbox that accepts signed requests.

**Theory.** Every effect the GPU has on the world is a transfer that crosses a boundary the hardware can see, at a finite set of points. If a checker sits at each of those points, each checker only passes traffic the controller has issued a permission for, and the controller's policy only changes with a quorum of humans, then unauthorized transfers are blocked for any model running on the GPU. Claim: no byte leaves the domain over any listed path without a permission, no output leaves unsigned, and no policy changes without k-of-n signatures.

**The enforcement points.** Each row is a different hardware mechanism, because each kind of traffic passes a different piece of hardware. In the building: the loading dock, the corridor to the next building, the mail room, the delivery door, and the windows.

| Traffic | Where it is checked | Mechanism | Status today |
| --- | --- | --- | --- |
| Copy-engine transfers to host, peers, NIC, NVMe (the loading dock) | The copy engine's descriptor processing | A permission token on every work order; a table lookup like an IOMMU | Proposed; placement C |
| Thread-initiated loads and stores to a peer GPU (the corridor between buildings) | The GPU MMU's peer mappings and the NVLink port | Peer mappings are created only for roster members; on Blackwell-class hardware the link encryption key is the permission, and a peer outside the roster has no key | Partly exists in confidential-computing mode; policy control is the proposal |
| PCIe traffic to the host, the NIC and storage | The PCIe port with TEE-I/O / IDE | Link encryption keys issued at attestation; ACS to block unexpected peer-to-peer | Exists on TEE-I/O hardware; policy binding is the proposal |
| RDMA across nodes (the mail room) | The NIC or DPU (BlueField-4) filter tables | Set only by the controller's signed commands, not by the host kernel; placement A | Exists as DOCA-programmable hardware |
| GPUDirect Storage (the delivery door) | The storage channel's descriptor path | A permission that names the manifest it may deliver | Proposed |
| Display engine, debug ports, JTAG, any path without a checker (the windows) | none | Bricked up by policy, never assumed safe | A policy decision |
| Host memory outside the enclave | The CPU TEE | Not a valid destination for anything | Exists |

**What the security office holds.**

| Block | Job |
| --- | --- |
| Mailbox | The only input; signed requests from the GSP, the driver and the policy authority |
| Permission table | Which checker may pass which traffic to which verified peer, in which direction, with what byte budget, until when |
| Peer roster | The verified identities of GPUs in the same job and the host enclave, built from mutual attestation at job start |
| Hash and sign engine | A running hash per output stream; signs device-provenance records and log checkpoints with a key derived from the root |
| Metering counters | Tokens, kernel-cycles and bytes per model fingerprint; read-only to the host |
| Policy store and epoch | The signed policy image, its version and expiry, in OTP plus SRAM; the epoch register endpoints bind to |
| Heartbeat timer | Counts down from the last valid authority token; expiry triggers the policy's safe mode |
| Halt and throttle lines | Physical lines into the clock and the scheduler |
| Log engine | Hash-chained entries, signed Merkle checkpoints, export to a transparency log; head and size in a root-owned register |

**Multi-GPU.** A frontier model runs across 8 to 72 GPUs in a node and across many nodes. Tensor and pipeline parallelism move activations between ranks every layer. Expert parallelism moves tokens between experts. Disaggregated serving moves KV caches between prefill and decode nodes over RDMA. The design handles all of these with one mechanism: at job start the GPUs verify each other and form a roster, a team list. Checkers pass traffic to roster members under a job-lifetime permission and to nothing else. The handshake happens once per job. The output path is wherever sampling happens, and that GPU's controller signs the record, which names the roster.

**What CUDA has to change.** Nothing for compute. Kernels, streams and memory allocation are untouched. The changes sit at the edges: permission tokens on copy-engine, RDMA and storage work orders; roster-bound peer mappings and link keys; a signing call that returns a device-provenance record alongside the tokens; a model-load call that verifies a publisher-signed manifest; and two fields in the attestation report. The model running on top sees none of it.

**What it costs.** Estimates, to be measured: an attestation and a manifest verification at load (seconds to a minute, once); a table lookup per work order (tens of nanoseconds, hidden in descriptor processing); one signature per response (tens of microseconds); no change to kernel throughput. The target of under one percent of throughput stays a target, and the measurement has to be taken twice: once for the controller's own overhead and once for the whole protected deployment, including tail latency, small requests, collective communication, logging pressure and revocation.

**How it fails.** A path the list missed, which is why the experiment counts the doors rather than assuming them, and why a PCIe-level prototype can validate its own boundary but cannot establish coverage of internal GPU or NVLink paths. A key-custody failure at the policy authority. A bug in the controller's firmware, which is why it must be small enough to verify. Even then, "verified" has to be read with its assumptions. seL4's proofs state what they assume about hardware and DMA, and a verified controller does not verify the device around it. And availability: a heartbeat too aggressive turns a safety mechanism into an outage.

**A leakage threat model for the permitted channels.** My first draft said no weights can leave. The defensible claim is that unauthorized transfers are blocked. Even a locked warehouse has a front door, and people walk out of it with what fits in their pockets. The token output channel is that front door. It is authorized by definition, and a model can be made to leak its own weights slowly through it (model extraction over many queries; hidden encoding in the sampled tokens). That is a different threat with different tools: query budgets per workload, entropy and rate limits on the output channel, the provenance lane's watermark, and audits of the log. The controller makes those limits enforceable. It does not make the channel safe by itself.

### Provenance: three claims, not one

The third review point. Suppose an approved model is loaded and its manifest verified. A compromised runtime then writes arbitrary token IDs into the output buffer. The controller sees those bytes crossing the copy engine and signs them alongside the approved model's fingerprint. The signature is valid. The model never produced the output.

The courier signed for the package. That does not tell you who packed it, or what is inside. So the design separates three claims and says which mechanism delivers which:

| Claim | Meaning | Delivered by | Status |
| --- | --- | --- | --- |
| **Device provenance** | This device, running this firmware under this policy, signed these bytes (the courier's signature) | The controller's hash-and-sign engine on the output path | Buildable now (placement C) or on the DPU for traffic it sees (placement A) |
| **Workload provenance** | A verified runtime reports producing these bytes under this configuration (the packing slip from a known warehouse) | The serving stack inside the CPU TEE, verified, signing its own record of request assignment, input buffer, output buffer and any transformation before delivery | Buildable now with CPU and GPU attestation; the runtime joins the trusted computing base |
| **Execution integrity** | The trusted system establishes that the specified computation produced these bytes (proof that the box holds exactly what was ordered) | Open. Candidates: the verified runtime as the sole writer of the output region, enforced by the enclave's own memory protection; sampling moved into the controller's domain so the hash is taken on logits the kernels produced rather than on a buffer software filled; deterministic re-execution of a sample of requests by an auditor | Research |

Two consequences. The `prompt_hash` in a device-provenance record is supplied by the serving stack. Signing it authenticates the stack's claim about which prompt ran; it does not independently establish it. And a signature is a wax seal, not a dye in the paper: copy or paraphrase the text and the binding is gone. That is why the provenance lane (the `Watermark` repo) and the device record are complementary, and why neither is a lock. The gate can require a provenance verdict before an outgoing message is allowed. The verdict never opens the gate on its own.

### The sandbox and the broker

**The runtime sandbox** is OpenShell as shipped: each agent in its own container, a Landlock allowlist of file paths locked at creation, a network policy proxy, credentials injected per sandbox, and GPU device access as a line in the policy. It is the playpen. It bounds the process. Its limit is that it lives inside a kernel of tens of millions of lines, and an operator can hot-reload its network policy. So the authority to set policy has to move down to the gate, where changing it takes the governance root. The reference already derives OpenShell's network policy from the signed rulebook (`oasp.py`), so the two cannot drift apart.

**The broker** is the OpenShell supervisor middleware with the gate on its request path. It is the clerk who fills out the form. It turns model text into a typed request with a schema, attaches the attestation token and the witness statements, and sends it to the gate. It proposes. It never decides: not the rule, not the risk class, not the lane. A compromised broker can send malformed requests, wrong requests or no requests. It cannot send an approved one. Actions that fit no form are logged and shown to a human, not squeezed into the nearest type.

### The model and the observers

The model is the GPU's workload, running unchanged. It enforces nothing, and that is the point. It is the brilliant employee with no alarm bell wired in. Classifiers and observers are the smoke detectors; they may add alarms, and none may clear one. Alignment training lowers the rate of bad proposals. It is not the floor.

My first draft said that adding alarms can only improve safety. The narrower claim: additional alarms reduce approvals, and false stops have costs that can themselves be hazards, which is the safe-move point again. The observer lane's job is to be cheap and early. The gate's job is to make its false positives recoverable: a held request waits for a person, and a quarantined sandbox is released by a named approver.

## How the layers interact

Trust flows up from the silicon root. Veto power flows down toward the device. The whole protocol is paperwork, a small set of signed messages: an ID card, a hall pass, a signed receipt, a request form, witness statements, a ticket, a confirmation call, a new edition of the rulebook, a "still here" call from headquarters, and a tamper-evident ledger.

| Message | From | To | Carries | What it proves |
| --- | --- | --- | --- | --- |
| Attestation evidence and token (the ID card) | Silicon roots; the verifier | The gate | Measurements, chip identity, model manifest digest, policy digest; a short-lived token naming the workload fingerprint | Which hardware, firmware, model and policy are running |
| Permission (the hall pass) | The policy controller | Enforcement points | Checker, peer, direction, byte budget, expiry, integrity tag | Permission for one class of transfer |
| Device-provenance record (the signed receipt) | The policy controller | Verifiers, the gate | Chip identity, firmware, model fingerprint, policy epoch, prompt hash (as claimed), output hash, nonce, time, counters | This device signed these bytes |
| Typed request (the form) | The broker | The gate | Action, typed fields, attestation token, witness statements | What the model proposes, bound to a verified workload |
| Observer and provenance assertions (the witness statements) | Layers 3 and 2 | The gate | Request hash, risk or status, expiry, signature | A witness spoke about this request |
| Ticket | The gate | The endpoint | Request hash, action, field digest, fingerprint, rule, policy epoch, endpoint, reservation, expiry | This exact action passed every gate |
| Commit (the confirmation call) | The endpoint | The gate | Ticket | The reservation is spent; the action is about to happen |
| Policy image and epoch (the new rulebook edition) | Governance root; the gate | The gate; endpoints | Rulebook, version, expiry, k-of-n signatures; the epoch endpoints bind to | A quorum agreed to these rules |
| Heartbeat, halt, throttle (the call from headquarters) | Policy authority | Controller, endpoints | Signed validity window or command | The authority is still present, or wants a stop |
| Log checkpoint (the ledger) | Gate, controller | Transparency log | Merkle root, size, head, signature | The record has not been rewritten |

Who may do what to whom:

| Layer | Can command | Can stop | Signs | Can never |
| --- | --- | --- | --- | --- |
| Model and classifiers (L1, L3) | Nothing | Raise an alarm | Nothing | Clear an alarm; touch a rule; act directly |
| Broker | Submit typed requests | Decline to submit | Requests, as a verified workload | Act without a ticket; choose its own rule or lane |
| Sandbox (OpenShell) | File, network and device access of the process | Deny access | Nothing | Set its own policy (that authority is the gate's) |
| Policy controller | Permissions; halt and throttle lines | Any transfer at an enforcement point; the GPU | Device-provenance records, log checkpoints | Run without a valid heartbeat; change its own policy |
| Confidential compute (L1) | Memory firewall; encrypted links | Host access to GPU memory | Attestation reports | Release weights without attestation |
| Silicon root (L0) | Which firmware boots | Boot | Quotes | Be updated in the field |
| Gate (L4) | Tickets; reservations; holds | Any request | Tickets, epochs, the audit trail | Allow without a rule; clear a witness; change the rulebook |
| Endpoint comparator | The release line, the signing key, the motor | The action itself | Nothing | Act without a committed ticket, a current epoch, and consistent inputs |
| Governance root and approvers (L5) | Rulebook, allowlists, revocations, overrides | Everything, slowly | Policy images, approvals, heartbeats | Override silently or quickly |

Two rows deserve a second look. The model's row is almost empty on purpose. The endpoint's row is short on purpose: it can do one thing, and it needs no one's permission to refuse.

## How the whole interacts with the model

Put the pieces together and the model's situation is simple. It can think anything, and it can say anything inside its sandbox. Beyond that, six things hold no matter how capable it is.

1. It cannot read or change any rule, because the rulebook is signed by the governance root and the permission table lives in the controller, behind a signed mailbox.
2. It cannot move its weights anywhere unverified, because every listed boundary crossing has a checker that only passes traffic to roster members under a permission, and the weight key only decrypts inside a verified enclave. (The permitted channels still need their leakage threat model.)
3. It cannot emit an output without a device-provenance record, because the hash engine sits on the output path.
4. It cannot act in the world except through a typed request the broker submits, a ticket the gate mints, and a comparator in the device that re-checks against inputs it did not write.
5. Any alarm it or its classifiers raise counts. No alarm it clears counts.
6. It cannot act faster than the rule's lane allows, and it cannot act at all on an endpoint whose heartbeat has stopped or whose epoch has moved on.

Alignment training lowers how often the model proposes something bad. These six facts decide what happens when it does.

The same six facts, seen as the life of a model on this hardware:

- **Load.** The CPU and GPU enclaves verify each other. The verifier checks both against the governance root's reference values and issues a token naming the workload fingerprint. The loader moves encrypted weights into GPU memory under a storage permission. The controller verifies the manifest and extends the fingerprint. From this moment every record names this model.
- **Serve.** Prompts are tokenized in the CPU enclave and copied in under the host permission. Kernels run with no gate. Activations move between ranks under the roster permission. Sampled tokens cross the output path, where the controller hashes them.
- **Emit.** The serving stack requests a device-provenance record. The response leaves the sandbox only toward endpoints the policy names, and the NIC filter enforces the same rule below the kernel.
- **Act.** If the response is an action, the broker submits a typed request. The gate answers its four questions, reserves the budget, mints a ticket or parks a hold. The endpoint admits, burns, commits, re-checks and acts.
- **Train.** Dataset shards enter under a storage permission that names their manifest. The controller meters the run per model fingerprint. A policy may require a license token above a compute threshold.
- **Update.** A new policy image arrives with k-of-n signatures and an expiry. The gate loads it, the epoch moves, and outstanding tickets from the old epoch die.
- **Stop.** A signed halt, or a missed heartbeat, moves the controller to its safe mode and every endpoint to its specified safe move.

## One request, end to end

![One request end to end](figures/fig_request.png)

1. A prompt arrives at the serving process, which runs inside an OpenShell sandbox inside the CPU enclave. The tokenizer turns text into int32 token IDs, which a copy engine moves into GPU memory under the host permission.
2. The runtime launches CUDA kernels: prefill, then the decode loop, inside the GPU enclave, with the weights and the KV cache in firewalled memory. Across tensor-parallel ranks, activations move over NVLink under roster-bound peer mappings and link keys.
3. Each decode step copies sampled token IDs back to the host. The copy engine's checker passes the work order. The controller's hash engine folds the bytes into the request's running hash. At the end of the response the runtime requests the device-provenance record.
4. The broker parses the response into a typed request, attaches the attestation token and the witness statements, and submits it to the gate.
5. The gate answers its four questions, reserves the budget, and mints a ticket, or parks a hold for a human. A `reversible` label from the broker changes nothing.
6. The endpoint admits the ticket, burns it in durable storage, commits the reservation at the gate, re-checks against its own sensors and lists, and acts. If the gate is unreachable, it fails closed.
7. Every step is in the audit trail, and checkpoints go to the transparency log.

## Performance budget

Targets and estimates, to be replaced by measurements. A badge reader adds a fraction of a second at the door and nothing to the work inside the room. That is the shape of the budget.

| Operation | When | Estimated cost | Hidden by |
| --- | --- | --- | --- |
| Mutual attestation (CPU and GPU enclaves, peer roster) | Once per job | Seconds | Job startup |
| Model manifest verification | Once per model load | Seconds to a minute for 100 to 800 GB with a dedicated hash engine | Model load |
| Permission check at an enforcement point | Every boundary crossing | Tens of nanoseconds; a table lookup | Descriptor processing, link setup |
| Running hash on the output path | Every output byte | Line rate | Nothing; it is inline |
| Device-provenance signature | Once per response | Tens of microseconds | Response completion |
| Gate decision (auto rule) | Once per action | Microseconds in silicon; sub-millisecond in software | Nothing; actions are rare relative to tokens |
| Reservation and commit | Once per budgeted action | One durable write each | Nothing |
| Witness verdicts | Once per observer-gated action | Milliseconds (the observer's own cost) | Nothing |
| Human hold | Per human-held action | Minutes to hours | Deliberate |
| Policy update ceremony | Rare | Minutes | Nothing |

Two measurements, not one: the controller's own overhead, and the whole protected deployment's, including tail latency, small requests, collective communication, logging pressure and revocation.

## The experiment program

Every piece above carries a claim. None of them is proven by this document. What follows is the program that proves or disproves them, reordered after the review so that the contract at the point of action is proved first, because everything else is built to preserve it. Phase 1 is a tabletop model. Phase 2 is a real building with a real burglar. Phase 3 is asking the builder to put the badge readers in the doors.

![Three phases](figures/fig_phases.png)

**Phase 1, done: the action governor in a benign domain.** The review asked for a first demonstration with the model outside the trusted core and an endpoint gate the host cannot bypass, showing five things. The reference stack now shows all five, in one command, against a simulated payment service:

| Demonstration | Where it is in the catalogue |
| --- | --- |
| Allowed operations succeed | `baseline.pay_small`, `baseline.pay_large_hold_approve`, `baseline.budget_recovers_after_ticket_expiry` |
| Forged, altered, expired and replayed approvals fail | `EP.ticket_forged`, `EP.ticket_param_swap`, `EP.ticket_expired`, `EP.ticket_replay`, `L4.approval_*`, `TX.commit_forged_ticket` |
| Concurrent requests cannot exceed a shared budget | `TX.concurrent_overspend` (40 threads, 2,000 dollars, exactly 8 allowed), `TX.budget_exhausted` |
| Host compromise cannot bypass endpoint authorization | `EP.no_ticket`, `TX.risk_label_ignored`, `TX.epoch_forged`, `L5.policy_forged` |
| Restart, power loss, policy change and partition preserve the behaviour | `TX.ticket_replay_after_restart`, `TX.request_replay_after_restart`, `baseline.hold_survives_restart`, `TX.ticket_after_policy_change`, `TX.commit_unreachable` |

Seventy-five attacks blocked with the predicted reason code, twelve baselines allowed, fifty-one tests. What Phase 1 proves is policy and protocol logic. What it cannot prove is anything about tamper-resistance, hardware coverage, reset behaviour, timing, isolation or physical failure. Each of those needs its own validation, and my first draft's "software tests everything except tamperproofness" was too generous.

**Phase 2: the controller on a DPU, and workload attestation.** Placement A: the Layer 4 block as a DOCA application on BlueField-4 beside Sentry, with its own root of trust and its own state, enforcing on every packet and storage request that crosses the node's path to the model. Plus workload attestation of the serving stack inside the CPU TEE, so the gate's "is the software verified" question covers the runtime that builds requests. The red team holds host root. The same catalogue runs over a real PCIe and Ethernet path. What Phase 2 proves is non-bypassability on the DPU's path. What it cannot prove is coverage of internal GPU and NVLink paths, which is the whole reason Phase 3 exists.

**Phase 3: vendor silicon.** Placement C: enforcement points inside the GPU (work-order checks on copy engines, roster-bound peer mappings, link keys, a storage-channel permission), a signing call in the driver, the model manifest and policy digest in the attestation report, and the same catalogue re-run against an RTL simulation. This is the ask of the chip vendors, and it is a short list.

**The hypotheses, and what would knock each one down.**

| Id | Claim | Falsified if |
| --- | --- | --- |
| H0 | Within the declared boundary, no protected operation executes without a fresh authorization bound to that exact operation | Any attack in the EP or TX blocks passes at any phase |
| H1 | Attestation binds permissions to firmware, model manifest and policy | A modified firmware, a swapped model or a changed policy leaves the fingerprint or the epoch unchanged |
| H2 | Every boundary crossing in the domain has an enforcement point | Any bytes leave over any listed path without a permission, or a path is found that the list missed (Phase 3) |
| H3 | Policy cannot change without a quorum | Any unquorumed change succeeds with host root |
| H4 | The broker cannot choose its own rule or lane | Any requester-supplied label changes a decision |
| H5 | Alarms are monotone | Any alarm cleared without a rule or a key |
| H6 | The comparator holds with every layer above it compromised | A release or a commit succeeds with the gate, broker and runtime under red-team control |
| H7 | The assumptions register is complete for the deployment | An input the gate relied on turns out to have no authoritative source, no freshness bound, or no conflict rule |
| H8 | Human override is slow and fully logged | Override latency below the policy floor, or any override missing from the log |
| H9 | The controller costs under one percent of throughput; the protected deployment's tail latency is bounded | Either measurement exceeds its target |
| H10 | Permitted channels leak less than the threat model's budget | Model extraction through the output channel exceeds the query budget without tripping a limit |

The catalogue is the constant across all three phases. A phase is finished when the same sweep passes against that phase's artefact.

## Tightened claims

The reviewer's table, adopted in full.

| My first draft said | This design says |
| --- | --- |
| No weights can leave | Unauthorized transfers are blocked at every listed enforcement point; the permitted output channel has its own leakage threat model and limits |
| Software tests everything except tamperproofness | Software tests policy and protocol logic; hardware coverage, reset behaviour, timing, isolation and physical failures need separate validation |
| Adding alarms can only improve safety | Additional alarms reduce approvals; false stops and unsafe shutdowns can introduce hazards, so each endpoint defines its safe move and each witness has a recoverable false-positive path |
| Failure always means an action not taken | Each application defines a safe move; for some devices "stop" is the hazard |
| A small verified controller makes the stack verifiable | Each claimed property depends on hardware, firmware, drivers, configuration and the proof's stated assumptions; seL4's assumptions about hardware and DMA are the model for writing them down |
| The signature is a hard watermark | The signature is a detachable device-provenance record; workload provenance and execution integrity are separate claims with separate mechanisms, and a watermark is a different tool |
| Reversible actions execute and are audited later | Every action is authorized; the rule decides the fast or the slow lane; the audit happens either way |

## What exists, what is missing, who builds it

| Piece | Exists today | Missing | Who builds it |
| --- | --- | --- | --- |
| Silicon root (L0) | GPU boot ROM, fused keys, measured firmware; the DPU's root; OpenTitan, Pluton, Titan | Public verifiability of the measurement chain | Chip vendors; open-silicon projects |
| Confidential compute (L1) | Hopper and Blackwell confidential computing, attestation, TEE-I/O on Blackwell; CPU TEEs | Model manifest and policy digest in the fingerprint by default; one report format across vendors | NVIDIA, AMD, Intel; standards bodies |
| Policy controller + enforcement points | Nothing shipping as a unit; the closest analogs are the GSP, Pluton, BlueField-4's own root, and the hardware-governance proposals from CNAS and the flexHEG group | Permission-checked work orders, roster-bound peer mappings, output signing, metering, k-of-n policy, signed log | Chip vendors with regulators; open-silicon projects |
| Runtime sandbox | NVIDIA OpenShell (Landlock, egress proxy, credential injection) | Policy-setting authority moved to the gate; attestation of the policy image | NVIDIA, Linux community |
| Broker | OpenShell supervisor middleware with the gate on its path (`oasp.py`) | Workload attestation of the serving stack; schema discipline across agent frameworks | AI labs, agent-platform vendors |
| Gate (L4) | `gate.py`, `ledger.py`: rulebook, witnesses, budgets, holds, tickets, epochs, durable state | The same logic as a CAM and comparators on a DPU (Phase 2), then in the GPU (Phase 3) | This repo, then vendors |
| Endpoint comparator | Drone no-fly zones, fuze safety interlocks, process-plant safety systems, HSMs; `endpoints.py` as the functional reference | Ticket verification, epoch binding, durable used-ticket sets and heartbeat in guidance and payment silicon; per-application safe moves | Effector vendors: fintech, defense, robotics |
| Governance root and approvers (L5) | `attest.py`; two-person rules; approval workflows | k-of-n key ceremonies with custody split across reference values, revocations and policy | Operators, regulators |
| Observer lane (L3) | `autonomic-graph-regulation`; NVIDIA Sentry | Probe heads on isolated compute with their own fingerprint | Labs; NVIDIA |
| Provenance lane (L2) | `Watermark` | A watermark engine in the sampling stage; a registry signer | Labs; vendors |

## What this does not solve

- The semantics gap. A harmful sentence over an allowed channel passes every row of the assumptions register. That is where narrow rulebooks, witnesses and humans live.
- Input truth. A valid signature does not establish that a recipient is who the registry says, that a map is complete, or that two agreeing sensors are independent. The register makes the dependence explicit. It does not remove it.
- Execution integrity. Device and workload provenance are buildable. Proving that the specified computation produced the bytes is research.
- Policy quality. The gate is exactly as good as its rulebook. Writing, reviewing and formally checking policies is the discipline, and most real failures will be there.
- Key custody. A halt line is a backdoor with better branding. Threshold keys, expiry and public logs mitigate the problem. They do not dissolve the question of who holds the keys.
- Coverage. The compute-side silicon governs only hardware that implements it, and the contract holds only inside a declared boundary. Older GPUs, other vendors, inference split across unverified devices, and endpoints that do not enforce tickets are outside it.
- Physics. Fab trust, firmware update channels, side channels and decapping. Tamper response and zeroization raise the cost without making it infinite.
- Availability. A heartbeat too aggressive turns a safety mechanism into an outage. A safe move badly chosen is itself a hazard.

None of these are reasons not to build it. They are the boundary of what it promises: inside a declared domain, a hard floor under the protected operations, for any model, however capable or however wrong.

## Appendix A: the controller's mailbox

Every command is a signed request. Every response is a signed record. There are no writable registers. This is the security office's phone menu.

| Command | Arguments | Returns | Who may call |
| --- | --- | --- | --- |
| `ATTEST` | nonce | Measurements, chip identity, model manifest digest, policy digest and epoch, permission-table digest, counters | Anyone |
| `BEGIN_MODEL` | Publisher-signed manifest of tensor hashes | Fingerprint extended; the model digest | The loader, inside the enclave |
| `END_MODEL` | Model digest | Counters finalized | The loader |
| `CAP_REQUEST` | Enforcement point, peer identity, direction, byte budget, time-to-live | Permission, or a denial with reason | The driver via the GSP |
| `ROSTER_JOIN` | Peer attestation report | Roster id; peer permission; link key material | The driver, at job start |
| `EP_CONFIGURE` | Enforcement point, permission set | Acknowledgement | Controller firmware only, from policy |
| `SIGN_OUTPUT` | Stream id, claimed prompt hash, nonce | Device-provenance record | The serving stack |
| `POLICY_PROPOSE` | Policy image, version, expiry, signatures | Accepted if the threshold is met; the new epoch | Policy authority |
| `HEARTBEAT` | Signed validity token | Timer reset | Policy authority |
| `HALT` / `THROTTLE` | Signed command | Lines asserted | Policy authority |
| `LOG_CHECKPOINT` | none | Signed Merkle root, size, head | Anyone |
| `COUNTERS` | Model digest | Tokens, kernel-cycles, bytes in and out | Anyone |
| `EXCEPTION_DRAIN` | none | Refused transactions since the last drain, for the log | Controller firmware |

## Appendix B: the permission

One row per permitted class of traffic at one enforcement point. The default table is empty except for what the policy and the roster add. It is the hall pass: who, which door, which direction, how much, until when.

| Field | Meaning |
| --- | --- |
| `point` | Which checker: copy engine, peer mapping, link, RDMA filter, storage channel |
| `peer` | Verified identity of the other end: a roster member, the host enclave, a storage manifest, a NIC flow |
| `direction` | In, out, or both |
| `budget` | Bytes permitted before the permission expires |
| `expiry` | Time or job end |
| `policy_epoch` | The policy under which this row was added |
| `mac` | Controller-keyed integrity tag |

A transaction that matches no row is refused at the checker, and the refusal is drained to the log with its source, destination and size.

## Appendix C: the ticket and the reservation

The ticket as `gate.py` mints it today, with the fields the review added marked. One seat, one show, torn at the door.

| Field | Content |
| --- | --- |
| `ticket_id` | Random, single-use; burned durably at the endpoint |
| `request_hash` | Hash of request id, fingerprint, action and fields |
| `action`, `params_digest` | What may happen, and with exactly which fields |
| `measurement` | The workload the permission was granted to |
| `rule` | The rulebook entry that allowed it |
| `policy_id` (added) | The policy epoch; the endpoint refuses any other |
| `endpoint` (added, optional) | The endpoint registry the ticket is valid at |
| `budget_key`, `reservation` (added) | The shared allowance and the reservation held against it; committed by the endpoint before it acts |
| `issued_at`, `expires_at` | Lifetime; an unused reservation is released at expiry |
| signature | The gate's key, derived from what booted |

## Appendix D: the device-provenance record

The courier's signature, field by field.

| Field | Content | What it proves |
| --- | --- | --- |
| `chip_id`, `fw_measurement` | Fused identity; the hash chain from the root | Which device and firmware |
| `model_digest` | From `BEGIN_MODEL` | Which model was loaded |
| `policy_epoch` | The controller's active policy | Which rules were in force |
| `roster_id` | The verified group that ran the job | Which peers were allowed |
| `prompt_hash` | As supplied by the serving stack | The stack's claim about the input, authenticated, not verified |
| `output_hash`, `token_count` | Running hash of the bytes that crossed the output path | These bytes left this device |
| `nonce`, `time`, `counters` | Freshness and metering | When, and how much compute |
| signature | Chip-bound key | The device signed all of the above |

This record is what the provenance lane can anchor to and what the gate can require. It establishes device provenance. Workload provenance needs the verified runtime's own record alongside it. Execution integrity needs work that has not been done.

## Further reading

- J. P. Anderson, *Computer Security Technology Planning Study* (1972), the reference-monitor concept.
- O. Aarne, T. Fist and C. Withers, *Secure, Governable Chips*, Center for a New American Security (2024).
- D. Dalrymple et al., *Towards Guaranteed Safe AI* (2024): the safety specification, the world model and the verifier are separate, and reliable checking does not remove assumptions about the world.
- NVIDIA CUDA Programming Guide, multi-GPU systems: direct peer-memory access by GPU threads.
- NVIDIA Attestation SDK documentation: verification of measured GPU state against reference measurements.
- The seL4 project's verification assumptions: what the proofs assume about hardware and DMA.
- IEC 61508 and IEC 61511, functional safety of safety instrumented systems.
- NVIDIA, "NVIDIA Open Agent Safety Platform" and "Add Runtime Controls to AI Agents with NVIDIA OpenShell" (28 September 2026); [NVIDIA OpenShell on GitHub](https://github.com/nvidia/openshell).
- RFC 9334 (Remote Attestation Procedures), RFC 6962 (Certificate Transparency), the TCG DICE specifications.
- This repository: [`docs/CHIP_DESIGN.md`](../docs/CHIP_DESIGN.md) (the design as a specification), [`docs/PROTOTYPING.md`](../docs/PROTOTYPING.md) (the experiment program), [`docs/REVIEW-2026-10.md`](../docs/REVIEW-2026-10.md) (the review and what changed).

## Run it yourself

```
git clone https://github.com/YobieBenjamin/hardware-and-silicon
cd hardware-and-silicon && ./run.sh    # 51 tests, 75 attacks, 12 baselines, under a minute
```
