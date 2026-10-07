# Silicon

All of these layers end up in silicon. This document says where each piece of
the software reference goes, which guarantees exist *only* once it is there,
and what the path from this repo to a theoretical chip design looks like. The
chip design itself is a later phase; this is the map it will be drawn on.

## 1. Module → block

| Software (this repo) | Silicon block | Why it has to be hardware |
|---|---|---|
| `SiliconRoot.__uds` | **OTP / eFuse unique device secret**, readable only by the key-derivation engine, never by any bus master | a secret software can read is a secret software can copy; the entire identity chain hangs on this one property |
| `SiliconRoot.__fused_svn` | **anti-rollback fuse counter** (monotonic, one-way) | a counter in flash can be rewound; a blown fuse cannot |
| `registers[]`, `extend()` | **measurement registers** with an extend-only datapath (hash engine + register file, no write port) | "PCRs" are useful precisely because there is no instruction that sets them |
| `boot()` → CDI → alias key | **DICE engine**: ROM-resident first-stage loader, HMAC/HKDF, Ed25519/ECDSA keygen; UDS erased from any accessible latch after the CDI is derived | the key that signs a quote must be *derived from the measurement of what booted*, by code that cannot be patched (ROM) |
| `quote()` | **attestation signer**: in-block signature over `{registers, svn, nonce, user_data}`; private key never leaves the block | firmware that cannot touch the alias key cannot forge a report it did not boot into |
| `random_nonce()`, `SimClock` | **TRNG** and a **monotonic time counter** owned by the root | freshness is meaningless if software supplies the nonce or the clock |
| `AttestationVerifier` | mostly a **service** run by the governance root; optionally an **on-package verifier** that holds the governance public keys in ROM and refuses to release the accelerator from reset until the composite evidence verifies | an on-package verifier turns "the fleet checks you" into "you do not run until checked" |
| `GovernanceRoot` public key | **ROM-anchored public key(s)** with a fuse-indexed revocation bitmap | the policy authority must be unchangeable by the operator |
| `PolicyGate` | **policy engine on the I/O path**: a CAM keyed on (measurement, action), typed comparators for constraints, hardware rate-limit counters, a hold register that only an approver-signed message clears | in software the gate is a process the operator can stop; on the fabric it is the only path |
| `EndpointRegistry` ticket check | **capability comparator** in front of each consequential interface (NIC, PCIe root port, storage controller): no DMA descriptor or packet leaves without a valid, unconsumed ticket bound to its digest | makes the gate a chokepoint by construction, in the spirit of CHERI capabilities and IOMMU permission tables |
| `AuditLog` | **append-only log**: entries to NVM through a hash-chain engine; head hash + size in a root-owned monotonic register; checkpoints signed by the attestation signer | truncation becomes a counter disagreement the chip itself reports |
| Observer / provenance assertion checks | **signature verification units** with anchor-key slots loaded from the signed policy image | witness verdicts must be checked by something the model cannot patch |
| `canonical()` | **fixed serialisation encoder** (CBOR/COSE in ROM rather than JSON) | two parties that agree on a message must agree on its bytes, without a parser that can be confused |

## 2. What only silicon gives

The software reference blocks every *logical* attack in the catalogue. These
properties are not available to it at all and are the reason the chip exists:

1. **Non-extractability.** The UDS and the alias private key never exist in
   addressable memory. No debugger, no DMA, no cold boot.
2. **Non-bypassability.** The gate is on the only physical path to the
   consequential interfaces. There is no `endpoint.execute(ticket=None)` to call
   because there is no wire that carries the request around the comparator.
3. **Non-patchability.** The ROM loader, the extend-only datapath, the fuse
   counter and the comparator are not software. The operator can hold the chip
   in reset; the operator cannot make it lie.
4. **Fail-closed by physics.** Lose attestation and the accelerator's I/O
   stays gated, not because a daemon chose to deny but because the capability
   comparator has nothing to match.
5. **Tamper evidence that survives the host.** Audit head and size live in the
   root's register, so a host that wipes storage still leaves a chip that says
   "I signed a checkpoint at size 10,412 and you are showing me 9,800."

## 3. Interoperating with NVIDIA GPUs

The accelerator is not ours to redesign, so the design has three placement
options for the Layer 4 block, in increasing order of integration:

| Placement | Where the gate sits | Pros | Cons |
|---|---|---|---|
| **A. DPU / SmartNIC** — *NVIDIA's placement* | **BlueField-4** on each Vera Rubin compute tray, on the node's only path to the model, programmed with **DOCA** — exactly where NVIDIA's Sentry runs | ships today; sees every packet and every storage request; has its own root of trust; isolated from the host; NVIDIA already puts the watchdog and the kill switch here, so the Layer 4 block is a DOCA application beside Sentry rather than new hardware; enabling it is a software update on Vera + BlueField-4 systems | PCIe peer-to-peer and NVLink paths between accelerators are not on the DPU's path; needs IOMMU policy to close them |
| **B. Board-level safety controller** | discrete chip on the carrier between the GPU's PCIe/NVLink egress and the root complex | nothing leaves the GPU without passing it, including P2P; independent silicon with independent custody | custom board; bandwidth and latency budget on the hot path; needs the GPU's CC mode to exclude the host from GPU memory so the gate is not bypassed through memory |
| **C. In-GPU IP block** | inside the accelerator's I/O stage, next to the existing attestation root | strongest: every egress is gated and the measurement is the GPU's own | requires the vendor |

The reference is written to be placement-agnostic: evidence, tokens, tickets
and audit records are messages, and a message format does not care whether the
comparator is on a DPU, a carrier board or a die. Placement A is first because
NVIDIA's Open Agent Safety Platform has already made the DPU the chokepoint
(`docs/NVIDIA.md`); B and C remain the path to the properties a DPU cannot give
(P2P/NVLink egress, in-die measurement).

The GPU-side attestation this repo models (`device_class="gpu"`, evidence
bound inside the TEE quote) is the H100-class confidential-computing flow in
miniature: GPU firmware measured, report signed by a device key chained to the
vendor CA, nonce supplied by the verifier, binding to the TEE established by
the TEE's own quote.

## 4. Lanes in silicon

The other two lanes get hardware homes too, and the interfaces in
`docs/LANES.md` are where they attach:

- **Layer 2 (provenance)** becomes a **watermark engine in the sampling
  stage** of the accelerator's output path, plus a registry signer. Its
  provenance assertion is a message the Layer 4 comparator can check with a
  fused registry key.
- **Layer 3 (observers)** become **probe heads** with access to activations and
  the pending action, running on isolated compute with their own measurement,
  signing verdicts with keys the Layer 4 block anchors. "Observers warn before
  the model acts" becomes "the egress gate does not open until the observer
  block has signed."

Both stay separate designs; silicon changes where they live, not what they
owe each other.

## 5. Roadmap to the theoretical chip

| Phase | Deliverable | Status |
|---|---|---|
| 1 | **Functional reference** (this repo): every block as software, every attack as a test, message formats fixed | done — `./run.sh` |
| 2 | **Formal specification**: state machines for the root (reset → measured → quoted), the gate (request → decision → ticket → consumed) and the log (append → checkpoint → prove); message formats moved from JSON to CBOR/COSE; invariants written down (no ticket without token; no allow without rule; head hash monotone) and model-checked against the software | next |
| 3 | **Theoretical silicon design**: block diagram with interfaces (AXI/PCIe/NVLink attach points), the CAM and comparator microarchitecture, key-slot and fuse map, area/latency/power estimates for placements A/B/C, and the test plan that re-runs this catalogue against an RTL simulation | the "theoretical hardware (silicon-based solution)" phase |
| 4 | **Emulation**: the Layer 4 block as a DOCA application on BlueField-4 beside Sentry (placement A), then on an FPGA on a carrier (placement B), this same harness driving it over a real PCIe/Ethernet path | after 3 |

The catalogue is the constant across all four phases. A phase is finished when
`hwctl sweep` passes against that phase's artefact.

## 6. Honest boundaries

- This repo cannot demonstrate any of §2. It demonstrates the *logic* the
  silicon must implement and gives the silicon a test it must pass.
- The vendor's root (device certificates, GPU firmware measurement) is
  modelled, not owned. Placement C requires the vendor; A and B do not.
- The governance root is a key with custody rules, not a chip; it will stay a
  key. What silicon gives it is an unchangeable place to be *trusted from*.
