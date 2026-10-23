# The Chip That Says No

By Yobie Benjamin · yobie AT ieee DOT org · linkedin.com/in/yobie · October 13, 2026 · Part 3 of 4: the silicon design, the action side

> [Parts 1](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/02-the-chip-that-says-no-1-plain-english.md) and [2](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/03-the-chip-that-says-no-2-with-the-technical-detail.md) made the argument. [The first post in this repository](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/01-a-multi-layer-approach-to-ai-safety.md) laid out the layer model and shipped the reference stack. This post and the next are the design that post promised. This one is the action side: the contract, where the walls are, what a chip can and cannot know, where the bits live, and the gate, the ticket and the comparator that make up the primary guarantee. [Part 4](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/05-the-chip-that-says-no-4-the-governor-in-the-rack.md) is the compute side: the root of trust, confidential compute, provenance, and the Safety Governor, a chip that sits in the rack beside every GPU. A chip designer went through my first draft and corrected it in seven places. His corrections are built into both posts, and the biggest of them changed the shape of the design. The promise is narrower than my first draft claimed, and stronger, because it is a security contract at the point of action rather than a promise about a chip. I will keep the technical depth, and I will explain every piece of it with something you can picture. Every product, paper and standard I name is linked where I name it, and the links were checked on the day of posting.

## Where we are

The argument from Parts 1 and 2, in four lines:

1. The guard cannot be another AI. A guard must be tamperproof, always invoked, and small enough to verify. A model fails all three tests.
2. Prevention lives at the point of action. A cluster of GPUs can think anything. The catastrophe cannot happen until one wire goes high. Guard the wire, not the crowd.
3. Every action goes through the gate. How hard the gate looks, and how long it pauses, depends on what the action can do.
4. Any model may raise STOP. No model may clear it. Alarms are cheap when wrong. Clearing one takes a fixed rule or a human key.

The layer model from the first post, which the rest of this design is placed on. Think of it as the floors of a building, from the basement up:

| Layer | What it does | Where it lives |
| --- | --- | --- |
| 5 · Governance root | Signs the rulebook, the list of approved firmware and the revocations. Separate from the chip vendor on purpose | [this repo](https://github.com/YobieBenjamin/hardware-and-silicon) ([`attest.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/attest.py)) |
| 4 · Control plane | The default-deny gate on the only way out: attestation check, rulebook, witnesses, budget, human holds, one-time tickets, audit trail | this repo ([`gate.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/gate.py), [`ledger.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/ledger.py), [`endpoints.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/endpoints.py), [`audit.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/audit.py)) |
| 3 · Observers | Fast, cheap early-warning verdicts about one request, signed, used as witnesses | [`autonomic-graph-regulation`](https://github.com/YobieBenjamin/autonomic-graph-regulation); [NVIDIA Sentry](https://nvidianews.nvidia.com/news/open-agent-safety-platform) |
| 2 · Provenance | Watermark, hardened detector, signed registry; emits a signed verdict about where text came from | [`Watermark`](https://github.com/YobieBenjamin/Watermark) |
| 1 · Model and runtime | The model, CUDA, the serving stack, the sandbox | NVIDIA; treated as untrusted |
| 0 · Silicon root of trust | A secret fused into the chip, a counter that only counts up, measurement registers that can only be added to, a key derived from what booted, a quote engine | this repo ([`root.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/root.py)); the GPU's and the DPU's own roots |

And the crosswalk to the brain tiers of Parts 1 and 2, so the two vocabularies stay in step:

| Brain tier (Parts 1 and 2) | This design | Repo module |
| --- | --- | --- |
| Reflex: fastest, dumbest, cannot be talked out of its job | The endpoint comparator: the ticket check inside the device that acts | [`endpoints.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/endpoints.py) |
| Deep alarm system: default deny, fast global stop | The Layer 4 gate | [`gate.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/gate.py), [`ledger.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/ledger.py) |
| Thinking brain: slow, deliberate, overrides with effort | The governance root and the approvers (Layer 5) | [`attest.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/attest.py), approvals in [`gate.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/gate.py) |
| Senses and alarms: may raise, never clear | The observer and provenance lanes (Layers 3 and 2) | [`assertions.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/assertions.py), [`oasp.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/oasp.py) |

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
| **A · DPU on the node's path** ([BlueField-4](https://www.nvidia.com/en-us/networking/products/data-processing-unit/) with [DOCA](https://developer.nvidia.com/networking/doca), beside [NVIDIA Sentry](https://developer.nvidia.com/blog/nvidia-open-agent-safety-platform-a-reference-for-continuous-in-silicon-agent-monitoring/)) | Enforce policy on every packet and storage request that crosses that path; own root of trust; isolated from the host | Other paths bypass it: PCIe peer-to-peer and NVLink between GPUs are not on the DPU's path |
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
| 1 · Storage at rest | Weights, tokenizer vocabulary, training-data shards, policy images, logs | Encrypted files; weights as [safetensors](https://github.com/safetensors/safetensors) in bf16 or fp8; data as token shards | Keys released only to a verified loader | Yes: decryption bound to attestation (L0) |
| 2 · CPU | Tokenizer, scheduler, serving stack ([vLLM](https://github.com/vllm-project/vllm), [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM), [SGLang](https://github.com/sgl-project/sglang)), broker, [OpenShell](https://github.com/NVIDIA/OpenShell) sandbox | Text in; int32 token IDs out; typed requests | CPU TEE (Intel TDX, [AMD SEV-SNP](https://www.amd.com/en/developer/sev.html), [Arm CCA](https://www.arm.com/architecture/security-features/arm-confidential-compute-architecture)) | No gate on compute; the broker proposes, the gate decides |
| 3 · Host memory | Prompt and output token IDs, request metadata, KV-cache spill | int32 arrays, structs | Encrypted by the CPU TEE; the hypervisor cannot read it | No |
| 4 · Interconnect | PCIe to host, NIC and NVMe; NVLink to peers; [RDMA](https://docs.nvidia.com/cuda/gpudirect-rdma/) across nodes; [GPUDirect Storage](https://docs.nvidia.com/gpudirect-storage/) | DMA descriptors, thread-initiated peer loads and stores, link frames | Each link is a boundary crossing | Yes: an enforcement point on each kind of crossing |
| 5 · GPU HBM | Weights, KV cache, activations, logits | bf16 / fp8 tensors; paged KV blocks | GPU TEE: hardware firewall, host cannot read | No; the firewall is the protection |
| 6 · Streaming multiprocessors | Embedding lookup, attention, projections, sampling | Vectors and logits in registers and shared memory | Inside the GPU TEE | No. Compute runs free. |
| 7 · Output path | Sampled token IDs leaving the GPU | int32 IDs per decode step | Crosses from the GPU TEE to the CPU TEE | Yes: device provenance (hash and sign) |
| 8 · Beyond the chip | Typed request to the gate; ticket to the endpoint; endpoint to the world | Signed records | The endpoint's own trust domain | Yes: the gate, then the comparator |

A TEE, for the record, is a trusted execution environment: a locked room inside a processor where the code and data are shielded from everything else on the machine, including the operating system.

Three things in this table carry the design.

The model's thinking (stations 5 and 6) is untouched. No gate sits in the kernel path. That is what keeps the design compatible with trillions of tokens: the hardware's work grows with boundary crossings and actions, not with compute.

Station 4 is where the second review point lands. A copy engine moves data using a work order the hardware processes one at a time. A permission check on a work order is the same kind of operation as an IOMMU lookup, the check every server already does when a device touches memory. But a CUDA kernel can also [read and write a neighboring GPU's memory directly](https://docs.nvidia.com/cuda/cuda-programming-guide/index.html), with ordinary loads and stores over NVLink, once peer access is turned on (the programming guide's section on peer-to-peer memory access). Those never see a work order. So the enforcement for station 4 is not one checker but several, each at the hardware point the traffic actually passes (the enforcement-point table, below), and any path with no checker is shut by policy rather than assumed safe.

Training data has a station too. During training, the shards moved into GPU memory pass the same enforcement points as everything else, so the controller can record which dataset a model was trained from, and that record travels with the model's fingerprint.

## The action side: the primary guarantee

### The authorization protocol

In Part 2 the permission was a concert ticket. Here is the whole box office.

My first draft bound an action to a form and checked it twice. That is necessary and not enough. Four failures survive a signed, bound, single-use ticket on its own:

- A valid ticket can be reused after a restart, if the record of its use was only in memory.
- Two requests arriving at the same time can both pass a shared budget check, if checking and reserving are separate steps.
- The recipient on the ticket can differ from the recipient at execution, if the binding covers the action but not every field and the destination.
- A ticket can stay good after the rules that issued it have changed.

So authorization is a transaction in three coordinated steps. This is how [`gate.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/gate.py), [`ledger.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/ledger.py) and [`endpoints.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/endpoints.py) implement it today:

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

**What it is.** The Layer 4 control plane: a default-deny rulebook signed by the governance root, keyed on the software fingerprint (what code is running, never which chip), with typed limits, witness requirements, rate limits, budgets and human holds. It is software today ([`gate.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/gate.py)). In silicon it is a content-addressable memory plus comparators: a rulebook entry is a fingerprint, an action class, a few typed limits and a rate. That is why the latency budget is nanoseconds and why it can sit on the data path at all.

**Theory.** If every path to an endpoint passes through the gate, and the gate's rulebook can only be changed by the governance root, then the model's power is bounded by the rulebook rather than by the model's manners. Claim: for any model, no action reaches an endpoint without a ticket the gate minted under a rule the governance root signed.

**Every action is authorized.** The rule's `requirement.mode` decides the lane: `auto` (verification and limits are enough; microseconds), `observer` (a fresh Layer 3 verdict under a risk ceiling is required), or `human` (the request is held until an approver signs). That is airport security again. What the traveler says about himself changes nothing. A `risk_class: reversible` field in the request, or a `requirement: auto` field, is ignored, because the rulebook picks the rule from the fingerprint, the action and the limited fields, and from nothing else. The [catalogue](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/attacks.py) has an attack for exactly that (`TX.risk_label_ignored`): a 25,000 dollar payment labeled reversible is held like any other.

**Witnesses, in the direction biology allows.** Observers (the [`autonomic-graph-regulation`](https://github.com/YobieBenjamin/autonomic-graph-regulation) repo's early-warning lane; [NVIDIA Sentry](https://nvidianews.nvidia.com/news/open-agent-safety-platform) on the DPU) and the provenance registry (the [`Watermark`](https://github.com/YobieBenjamin/Watermark) repo) emit signed verdicts about one request hash with short expiries. The gate consumes them. It never computes them. A verdict can keep the gate shut. It cannot open it. The novelty check from my first draft belongs here too, as a witness: a request whose fields fall outside everything seen before is a good extra reason to stop. It is not a guarantee against dangers nobody listed. Familiar values can form a dangerous combination, and unfamiliar values can be harmless. The review was right that the first draft leaned on it too hard.

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

## Where this goes next

The action side is the guarantee, and it is the half that exists today: the gate, the ledger and the comparator run in the reference stack, and the five demonstrations my colleague asked for are its tests. [Part 4](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/05-the-chip-that-says-no-4-the-governor-in-the-rack.md) is the other half: what keeps the model in its box and makes its outputs traceable, how the layers talk to each other, one request walked end to end, and the Safety Governor, the chip that pairs with each NVIDIA GPU through the rack's own boards and needs nothing from NVIDIA's silicon to do its job. It ends with the experiment program and the honest list of what none of this solves.

## Further reading

Every link below was checked on the day of posting. The ones behind a publisher's paywall are given as DOIs, which resolve to the paper's page even when the site blocks scripts.

- J. P. Anderson, [*Computer Security Technology Planning Study*](https://csrc.nist.gov/files/pubs/conference/1998/10/08/proceedings-of-the-21st-nissc-1998/final/docs/early-cs-papers/ande72.pdf), US Air Force ESD-TR-73-51 (1972). The reference-monitor concept.
- [IEC 61508](https://webstore.iec.ch/en/publication/5515) and [IEC 61511](https://webstore.iec.ch/en/publication/5527), functional safety of safety instrumented systems.
- D. Dalrymple et al., [*Towards Guaranteed Safe AI*](https://arxiv.org/abs/2405.06624) (2024). The safety specification, the world model and the verifier are separate, and reliable checking does not remove assumptions about the world.
- [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-programming-guide/index.html), the section on peer-to-peer memory access: direct loads and stores into another GPU's memory, the fact that moved my colleague's second correction.
- [*NVIDIA Secure AI with Blackwell and Hopper GPUs*](https://docs.nvidia.com/nvidia-secure-ai-with-blackwell-and-hopper-gpus-whitepaper.pdf), white paper WP-12554-001 v1.3 (August 2025). Confidential computing on the GPU, bounce buffers, TDISP/IDE.
- [GPUDirect RDMA](https://docs.nvidia.com/cuda/gpudirect-rdma/) and [GPUDirect Storage](https://docs.nvidia.com/gpudirect-storage/) documentation; [safetensors](https://github.com/safetensors/safetensors); [vLLM](https://github.com/vllm-project/vllm), [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM), [SGLang](https://github.com/sgl-project/sglang).
- [AMD SEV](https://www.amd.com/en/developer/sev.html) and [Arm CCA](https://www.arm.com/architecture/security-features/arm-confidential-compute-architecture), the CPU-side enclaves.
- This repository: [`docs/CHIP_DESIGN.md`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/docs/CHIP_DESIGN.md), the design as a specification, with the message formats as appendices; [`docs/PROTOTYPING.md`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/docs/PROTOTYPING.md), the experiment program; [`docs/REVIEW-2026-10.md`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/docs/REVIEW-2026-10.md), the review and what changed; the code: [`gate.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/gate.py), [`ledger.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/ledger.py), [`endpoints.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/endpoints.py), [`attacks.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/attacks.py).
- The companion lanes: [`autonomic-graph-regulation`](https://github.com/YobieBenjamin/autonomic-graph-regulation) (observers) and [`Watermark`](https://github.com/YobieBenjamin/Watermark) (provenance).

## Run it yourself

```
git clone https://github.com/YobieBenjamin/hardware-and-silicon
cd hardware-and-silicon && ./run.sh    # 56 tests, 75 attacks, 12 baselines, under a minute
```

If anyone wants to collaborate on any phase of this, I am here: yobie AT ieee DOT org.

---

*Licensing and IP: this post is © 2026 Yobie Benjamin. Documentation and posts are under CC BY-NC 4.0; the project's code is under the PolyForm Noncommercial License 1.0.0. Attribution required; commercial use requires a separate written license (see [LICENSING.md](https://github.com/YobieBenjamin/autonomic-graph-regulation/blob/main/LICENSING.md)). This is independent work and is not affiliated with, sponsored by, or endorsed by any company named in it; NVIDIA, OpenShell, Sentry, BlueField and DOCA are trademarks of NVIDIA Corporation.*
