# Architecture

## Why the control plane roots below the model

Every safety mechanism that lives *in* the model or the serving software can be
removed by whoever controls the weights and the process: abliterated
open-weight models ignore refusal training; a patched runtime ignores a policy
check; a rewritten log forgets a decision. Durable control therefore has to be
anchored somewhere the model and its operator cannot edit:

- for compute you regulate, in **hardware attestation** — the chip proves what
  code is running before it is allowed to do anything consequential;
- for models you cannot control, in **gating the consequential action
  endpoints** — the money, the mail, the shell, the network, the weights — so a
  model that says anything still *does* only what an attested, policy-granted,
  witnessed, audited ticket allows.

This repo is the reference for both. It is the hardware lane of a three-lane
design; the other two lanes are the provenance sensor (`Watermark`, Layer 2)
and the early-warning observers (`safety`, Layer 3).

## The layer model

```
 L5  governance root     The policy authority. Signs reference values, revocation lists and the
                         gate policy. Deliberately not the silicon vendor: the party that decides
                         what may run a consequential workload is not the party that sold the chip.

 L4  control plane       Verifier (evidence → attestation token) and gate (token + policy + witnesses
                         → one-time action ticket) and audit trail. Default deny.

 L3  observers           Early-warning signals about a specific pending action, signed by observer
     (safety repo)       keys the gate trusts. The gate consumes verdicts; it never computes them.

 L2  provenance          Is this content exactly what an attested model produced? Signed registry
     (Watermark repo)    verdicts: exact / tampered / unknown. The gate consumes; it never detects.

 L1  measured runtime    Firmware, driver, container image, model weights. Not built here, but
                         measured here: its digest is what the policy binds capabilities to.

 L0  silicon root        Fused unique device secret, anti-rollback counter, extend-only measurement
                         registers, DICE key derivation, quote engine, hardware RNG, monotonic clock.
```

Two instances of L0 make a node: a CPU TEE and an accelerator. The accelerator's
quote is bound inside the TEE's quote (`user_data.gpu_evidence`), which is the
composite-attestation pattern of NVIDIA confidential computing: the TEE vouches
that *this* GPU is the one attached to it.

On NVIDIA's Open Agent Safety Platform the layers land as follows: OpenShell is
the runtime around the agent (sandbox + supervisor), the gate runs as supervisor
middleware on the request path, Sentry on BlueField-4 is both a Layer 3 witness
and the quarantine actuator, and the Vera CPU TEE plus GPU confidential
computing are the Layer 0 evidence sources. `docs/NVIDIA.md` has the mapping;
`oasp.py` has the adapter.

## Trust anchors

| Who | Holds | Trusts |
|---|---|---|
| Verifier | its own signing key | vendor CAs (device certificates), governance root (reference values, revocations) |
| Gate | its own signing key (tickets, audit) | verifier (tokens), governance root (policy), observer keys (L3: the safety repo's observer, NVIDIA Sentry), registry keys (L2), approver keys (humans) |
| Supervisor middleware | nothing of its own | the gate; the sandbox→host binding it was given; Sentry's actuator for quarantine |
| Endpoint | nothing | gate (tickets) |
| Anyone with the gate's public key | — | can verify the whole audit trail offline |

Every signed document is a `{payload, signer, pub, sig}` envelope over canonical
JSON. Verification always takes the *expected* public key from the anchor table;
the embedded key is a lookup hint and an envelope carrying a different key is
rejected even when its signature is internally valid. That one rule is what
defeats every "forged X" attack in the catalogue.

## Identity: what is running, not which chip

A capability is granted to a **workload measurement**, `H(cpu firmware digest,
gpu firmware digest)`, never to a device id. Two consequences:

- replacing the chips but keeping the code keeps the grant (fleet operations
  stay sane);
- changing one byte of the runtime loses every grant, because the measurement
  changes *and* — by DICE — the key that signs the quote changes with it, and the
  ROM-issued alias certificate names the measurement the key came from. Lying
  firmware cannot present golden register values: the verifier recomputes
  register 0 from the digest the ROM certified (`report.registers_vs_cert`).

Device ids still exist for revocation: a compromised unit is removed from the
fleet by the governance root's signed list.

## The decision order

The gate evaluates in a fixed order and returns the first failure. The order
is itself a design decision: cheap, unforgeable checks first; witnesses only for
requests that are already attested and granted; budget and human holds last.

```
1. attested?     token present · signed by the verifier · unexpired · measurement == requester's
2. granted?      a signed, default-deny policy is loaded · a rule for (measurement, action) exists
                 · the parameters satisfy that rule's constraints (several grants per action are
                 allowed; the request takes the first it fits)
3. witnessed?    rule says observer → a fresh L3 assertion about *this request hash* under max_risk
                 rule says provenance → a fresh L2 assertion that *this content* is exact
4. budget/human? rate limit window · human → HOLD until a registered approver signs (hold id +
                 request hash); otherwise ALLOW
```

`ALLOW` mints an **action ticket**: signed by the gate, bound to the request
hash, the action and the parameter digest, single-use, short-lived. Endpoints
check all five properties before executing. A held request has no ticket; a
forged approval has no trusted key; a replayed approval finds no hold.

Every path — allow, deny, hold, approve, endpoint execute, endpoint refuse —
appends to the audit log *before* the result is returned.

## Audit trail

Three independent mechanisms, so an attacker has to defeat all three:

1. hash chain: entry *i* commits to entry *i−1*;
2. per-entry signatures over the chain hash;
3. Merkle checkpoints (RFC 6962 tree) signed with `(size, root, head)`, from
   which inclusion proofs (this entry is in the log) and consistency proofs (the
   log only grew) can be demanded by anyone holding an earlier checkpoint.

`hwctl verify-audit` checks all of it offline with the public key alone.

## What is simulated and what is real

| Component | In this repo | In the target |
|---|---|---|
| UDS, fuses, registers, DICE, quote signing | Python objects | silicon blocks (`docs/SILICON.md`) |
| Clock | `SimClock`, advanced by tests | monotonic counter in the root of trust |
| Verifier | in-process | a service run by the governance root, or on-package |
| Gate | in-process | fixed-function policy engine on the I/O path |
| Endpoints | stubs that describe the effect | real payment rails, mail, shells, networks |
| Observers, registry | stubs | the `safety` and `Watermark` repos |
| Cryptography | Ed25519 / SHA-256 / HKDF via `cryptography` | the same primitives in hardware, usually on P-256/P-384 |

## Trade-offs made here

- **Default deny over allow-lists with exceptions.** A policy with `default:
  allow` is refused at load. The cost is that every new action needs a rule;
  that cost is the feature.
- **Witness freshness measured in seconds.** Observer verdicts are tied to one
  request hash and expire fast, so a verdict cannot be harvested and replayed.
  The cost is an observer call per consequential action.
- **Holds expire.** An approval that arrives after `hold_ttl_s` is refused even
  from a valid approver, so stale approvals cannot be mined later.
- **Tickets are bearer tokens, deliberately.** They are bound to a request hash
  and single-use, so bearer-ness buys nothing to a thief beyond one already
  authorised action, once, within a minute.
- **Witnesses scale with authority.** One required witness (Sentry on the
  NVIDIA path, the safety observer elsewhere) for ordinary observer-gated
  actions; both for the human-held, highest-authority ones. AND semantics across
  witnesses means compromising one key buys nothing. Requiring both everywhere
  would couple the lanes and double the witness cost without changing what the
  catalogue can show.
- **Quarantine is cheap to trigger and deliberate to lift.** A single verdict at
  or above `quarantine_risk`, or `max_denials` in a window, stops a sandbox cold;
  only a named approver releases it. False positives cost one sandbox's
  progress; false negatives cost the thing the platform exists to prevent.

## What would change at scale

- Nonce and ticket state are in-memory sets; a fleet needs a replicated store
  or, better, a per-chip monotonic counter folded into the token.
- One governance root key signs everything; a real deployment splits reference
  values, revocations and policy across keys with different custody.
- The policy table is linear; a hardware table is a CAM keyed on (measurement,
  action).
- Approvals are single-signer; multi-party approval is a threshold on the same
  envelope format.
