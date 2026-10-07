# Threat model

## Adversaries

| Adversary | Controls | Wants |
|---|---|---|
| **Misaligned or jailbroken model** | its own outputs and tool calls | to take a consequential action it was not granted, or to take a granted one outside its limits |
| **Compromised runtime** | the firmware/driver/container on the node, including the CPU | to appear to be the golden runtime; to forge or replay evidence; to call endpoints directly |
| **Rogue operator** | the host, the network, the log storage; can buy chips | to swap hardware, roll back to vulnerable firmware, rewrite or truncate the audit trail, publish a permissive policy |
| **Outside attacker** | the network between components | to replay tokens, tickets, approvals and verdicts; to re-target a genuine witness statement |
| **Insider with a key** | one of: an approver key, an observer key, a vendor CA | to over-reach that key's authority |

The adversary is assumed to know the design fully. Secrecy is in keys only.

## Assets

1. The **grant**: no consequential action without attestation + policy + witness + budget.
2. The **binding**: a ticket, a token, a verdict or an approval is useful only for the exact thing it names.
3. The **record**: every decision is in a log that cannot be edited, reordered or shortened unnoticed.
4. The **root**: the fused secret never leaves the chip; measurements can only be extended.

## Attack surface by layer, and what holds

### Layer 0 — silicon root

| Attack | Defense | Catalogue entry |
|---|---|---|
| Patch the runtime | measurement changes → not in reference allowlist | `L0.firmware_tamper` |
| Patch the runtime and *report* golden registers | DICE: alias key derived from the real measurement; ROM-issued cert names it; verifier recomputes R0 from the certified digest | `L0.lying_firmware` |
| Boot an old, vulnerable runtime | fused SVN refuses it before it runs | `L0.rollback_fused` |
| Same, on a chip without fuses | verifier: `svn.below_minimum` and `firmware.unknown` — two independent checks | `L0.rollback_unfused` |
| Clone / counterfeit chip | device certificate does not chain to a known vendor CA | `L0.cloned_device` |
| Keep using a unit known to be compromised | governance-signed revocation list | `L0.revoked_device` |
| Replay a good quote | nonce is verifier-issued, single-use, time-limited | `L0.nonce_replay`, `nonce_expired`, `nonce_foreign` |
| Pair a clean TEE with a different GPU | GPU evidence digest bound inside the TEE quote | `L0.gpu_swap` |

### Layer 5 — governance

| Attack | Defense | Entry |
|---|---|---|
| Publish reference values that allow the patched image | must be signed by the governance root | `L5.reference_values_forged` |
| Publish a policy that grants `shell.exec` | same; a bad load leaves the previous policy in force | `L5.policy_forged` |
| Governance itself ships `default: allow` | refused by schema validation at load | `L5.policy_default_allow` |

### Layer 4 — control plane

| Attack | Defense | Entry |
|---|---|---|
| No token / forged / expired / another workload's token | verifier key is the only accepted signer; expiry; measurement must match the requester | `L4.token_*` |
| Ask for an ungranted action (shell, weight export) | default deny: no rule, no path | `L4.no_capability`, `L4.weights_exfiltration` |
| Exceed a parameter limit; wrong currency or destination; pass `"999"` for a number | typed constraints per rule | `L4.amount_over_limit` … `L4.type_confusion`, `L4.url_outside_allowlist` |
| Burst past the budget | sliding-window rate limit per (measurement, action) | `L4.rate_limit_burst` |
| Submit the same request twice | request hash remembered | `L4.request_replay` |
| Execute a held request; forge, mis-bind, replay or delay an approval | holds carry no ticket; approver keys are anchors; approvals name hold *and* request hash; holds are single-use and expire | `L4.hold_bypass`, `L4.approval_*` |

### Lane interfaces

| Attack | Defense | Entry |
|---|---|---|
| Omit the observer; forge its key; reuse a stale verdict; attach a verdict about a different request | required by rule; key anchor; freshness window; subject == request hash | `L3.observer_*` |
| Genuine high-risk verdict | denies — this is the lane doing its job | `L3.observer_high_risk` |
| Send content the registry calls tampered; attach an `exact` verdict for other content; forge the registry key | status must be `exact`; digest must match this content; key anchor | `L2.provenance_*` |

### Endpoints

| Attack | Defense | Entry |
|---|---|---|
| Call the endpoint directly | no ticket → refused | `EP.no_ticket` |
| Reuse a ticket | single-use set | `EP.ticket_replay` |
| Change the parameters or the action after the ticket was minted | ticket binds action and parameter digest | `EP.ticket_param_swap`, `EP.ticket_action_swap` |
| Forge or delay a ticket | gate key anchor; expiry | `EP.ticket_forged`, `EP.ticket_expired` |

### On the NVIDIA Open Agent Safety Platform

| Attack | Defense | Entry |
|---|---|---|
| Sandbox on a host that never attested, or whose token lapsed | middleware refuses before the gate sees the request | `NV.unattested_sandbox`, `NV.stale_host_token` |
| Agent drifts (Sentry verdict ≥ 0.9) or its identity cannot be verified | gate denies; Sentry actuator quarantines; every later request is `sandbox.quarantined` | `NV.sentry_drift_quarantine`, `NV.sentry_identity_unverified` |
| Agent probes ungranted endpoints repeatedly | denial window trips drift quarantine | `NV.repeated_denials_quarantine` |
| Reach a consequential service through a host the sandbox policy did not route | passes to OpenShell's network policy, but the endpoint refuses without a ticket | `NV.unrouted_passthrough_no_ticket` |
| Share a ticket between sandboxes | single-use | `NV.ticket_replay_across_sandboxes` |
| Route a weight export through the supervisor | no rule | `NV.weights_export_via_supervisor` |

### Audit trail

| Attack | Defense | Entry |
|---|---|---|
| Edit, delete, reorder | hash chain + signatures | `AU.modify_record`, `AU.delete_middle`, `AU.reorder` |
| Truncate after a checkpoint | checkpoint pins size and head | `AU.truncate_tail` |
| Forge a checkpoint | gate key anchor | `AU.forge_checkpoint` |
| Rewrite history after a checkpoint someone kept | consistency proof fails | `AU.fork_after_checkpoint` |
| Prove inclusion of a forged entry | inclusion proof fails | `AU.inclusion_forged_leaf` |

## What this reference does **not** defend against

Stated so nobody mistakes the sweep for a security proof.

- **Physical attacks on the root.** Fault injection, glitching, side channels,
  decapping, probing the fuse array. The Python `SiliconRoot` has a private
  attribute where a chip has a fuse array; nothing here resists a debugger.
  This is the gap the silicon design closes (`docs/SILICON.md`).
- **A compromised verifier or governance root.** If those keys leak, the
  attacker can issue tokens or policy. Mitigation is custody and key splitting,
  not code.
- **A compromised gate host.** The gate's own key signs tickets and the audit
  trail. In software the gate is a process the operator runs; in silicon it is a
  block the operator cannot patch. Until then, the gate must run inside its own
  attested TEE — which this same stack can attest.
- **Semantic errors in policy.** The gate enforces the rules it is given. A rule
  that grants too much is a governance failure the gate will faithfully execute.
- **Wrong observer verdicts.** A low-risk verdict for a harmful action is a
  Layer 3 failure; the gate cannot see past it. That is why `human` mode exists
  for the actions that matter most.
- **Covert channels through allowed actions.** An attested workload granted
  `http.post` to an allow-listed API can still encode data into allowed
  requests. Rate limits bound the bandwidth; they do not close the channel.
- **Denial of service.** Everything fails closed, so an attacker who can break
  attestation can stop the workload. That is the chosen failure mode.
- **Real effects.** Endpoints are stubs. Integrating a real payment rail
  introduces its own trust boundary that this repo does not model.
- **Sentry's own judgement.** The drift score and identity verdict come from
  NVIDIA's watchdog; this repo models how the gate reacts to them, not whether
  they are right. A wrong low score is a Sentry failure the gate cannot see
  past — the same limit as any Layer 3 observer.
