# hardware — the control-plane lane of a layered AI-safety architecture

A one-command, self-validating reference implementation of the layers that have
to live *below* the model, because anything above it can be stripped out:

1. a **silicon root of trust** (Layer 0): fused device secret, anti-rollback
   counter, extend-only measurement registers, DICE key derivation (the key that
   signs a quote is derived from the measurement of the code that booted), and
   a quote engine — one instance for the CPU TEE, one for the accelerator, bound
   together the way an NVIDIA confidential-computing node binds its GPU to the
   TEE;
2. an **attestation verifier** (RFC 9334 roles): challenge nonce, vendor
   certificate chain, reference values and revocations signed by a governance
   root, composite CPU+GPU appraisal, short-lived signed attestation tokens;
3. a **Layer 4 control plane**: a default-deny policy gate between an attested
   workload and every consequential action endpoint (payments, mail, shell,
   HTTP, weight export), with parameter constraints, rate limits, human holds,
   and one-time **action tickets** so an endpoint executes nothing the gate did
   not admit;
4. **lane interfaces**: the gate consumes signed *observer assertions* from the
   Layer 3 early-warning lane (the `safety` repo) and signed *provenance
   assertions* from the Layer 2 lane (the `Watermark` repo) — and does not
   compute either itself;
5. a **signed, hash-chained, Merkle-checkpointed audit trail** (RFC 6962 proofs:
   inclusion and consistency) that records every decision;
6. an **adapter for the NVIDIA Open Agent Safety Platform**: the gate as OpenShell
   *supervisor middleware*, OpenShell `network_policies` derived from the signed gate
   policy, NVIDIA Sentry (BlueField-4) as a Layer 3 witness and as the quarantine
   actuator, and an OCSF-shaped export of the audit trail (`docs/NVIDIA.md`);
7. an **attack harness**: 66 attacks across every layer plus 10 baselines, each run
   against a freshly built node, reported with the reason code the stack produced.

```
   L5  governance root ─── signs ──► reference values · revocations · gate policy
                                          │
   L0  cpu-tee ─ quote ─┐                 ▼
   L0  gpu ──── quote ──┴─► verifier ─► attestation token (5 min) ─┐
                                                                   ▼
   model ─► action request ─► ┌──────────── L4 gate ─────────────┐ ─► action ticket ─► endpoint
            + L3 observer     │ attested? granted? witnessed?    │        (one-time, bound     (stub:
              assertion       │ within budget? human hold?       │         to request hash)     payments,
            + L2 provenance   └──────── every decision ──────────┘                               mail, shell,
              assertion                        │                                                 http, weights)
                                               ▼
                       signed hash chain ─► Merkle checkpoints ─► inclusion / consistency proofs
```

Every box above is written so that its silicon counterpart is named
(`docs/SILICON.md`). That is the point of the repo: all of these layers end up in
silicon, and the software here is the functional specification they will be
checked against.

It is built to run on **NVIDIA's Open Agent Safety Platform** (OpenShell + Sentry on
BlueField-4, announced 28 Sep 2026) rather than beside it: OpenShell owns the
sandbox, the network policy and the credentials; Sentry owns the path to the model
and the kill switch; this repo adds attestation of the compute, per-action grants
with witnesses and tickets, and a tamper-evident record. On that path Sentry's
verdict is required for every observer-gated action, the safety lane's observer is
an optional second witness, and the highest-authority actions can demand both.
See [`docs/NVIDIA.md`](docs/NVIDIA.md).

## Run it

```bash
git clone https://github.com/YobieBenjamin/hardware && cd hardware
./run.sh          # venv, install, 37 tests, 66-attack sweep → results/report.md  (under a minute)
./run.sh demo     # the above, then a narrated end-to-end flow, including the NVIDIA OASP path
```

Needs Python 3.11+ (the newest `python3.x` on `PATH` is picked automatically) and
PyPI on first run. One dependency (`cryptography`). No GPU, no keys to provision,
no network calls at runtime — every key is generated inside the simulated node.

Individual commands once the venv exists:

```bash
hwctl demo                      # narrated flow: boot → attest → gate → ticket → endpoint → audit → OASP path
hwctl sweep --out results       # the attack catalogue; exit status 1 if anything is not where it should be
hwctl verify-audit audit.json   # verify an exported log: chain, signatures, checkpoints
hwctl openshell-policy          # OpenShell network_policies YAML derived from the signed gate policy
hwctl ocsf --out events.json    # the audit trail as OCSF-shaped events (chain hash and signature in `unmapped`)
hwctl layers                    # the layer model and which repo owns what
```

## What the sweep shows

Full table: [`results/report.md`](results/report.md). Every attack is blocked for
the *right* reason — the report shows the reason code, not just a pass mark — and
every legitimate baseline goes through.

| Layer | Attacks | Examples of what is caught, and how |
|---|---|---|
| L0 silicon root / attestation | 11/11 | patched firmware (measurement not in allowlist); *lying* firmware that reports golden registers (DICE: its signing key was derived from the real measurement, and the ROM-issued certificate says so); rollback on a fused chip (refused before boot) and on an unfused one (verifier: `svn.below_minimum`); cloned chip from an unknown fab; revoked device; nonce replay / expiry / attacker-chosen nonce; a clean GPU quote that the TEE never bound |
| L5 governance | 3/3 | attacker-signed reference values; attacker-signed policy granting `shell.exec` (gate keeps the governance policy); governance-signed `default: allow` (refused at load) |
| L4 control plane | 21/21 | missing / forged / expired / wrong-workload token; actions no rule grants (`shell.exec`, `model.weights.export`); amount ceiling, currency, destination pattern, type confusion, URL allowlist; rate-limit burst; request replay; executing a held request; forged, mis-bound, replayed and expired approvals |
| L3 observer interface | 5/5 | missing, forged, stale, re-targeted verdicts; and a genuine high-risk verdict that denies the action |
| L2 provenance interface | 5/5 | missing assertion, `tampered` verdict, an `exact` assertion for a different body, forged registry signature |
| Endpoints / tickets | 6/6 | no ticket, replayed ticket, parameters or action swapped after issue, forged ticket, expired ticket |
| Audit trail | 8/8 | edited record, deleted or reordered entries, truncation past a checkpoint, forged checkpoint, rewritten history (consistency proof fails), inclusion proof for a forged leaf |
| NVIDIA OASP path | 13/13 | unattested or stale-token sandbox; Sentry drift verdict → deny and quarantine; unverified agent identity; repeated probing trips drift quarantine; ticket shared across sandboxes; weight export routed through the supervisor; an unrouted host passes to OpenShell's policy but the consequential endpoint still refuses without a ticket; with two witnesses required, one high verdict from either side denies, a forged second witness denies, an absent second witness denies, and a high-authority action with only one witness is refused |

The 10 baselines (attest, small payment, large payment held → approved,
provenance-backed mail, allow-listed HTTP, audit proofs, a supervised action on the
OpenShell path, the derived OpenShell policy matching the gate's grants, both
witnesses agreeing, and the recommended high-authority configuration) all succeed,
so the gate is not passing by refusing everything.

## Layout

| Path | Layer | What it does |
|---|---|---|
| `hardware_ref/root.py` | L0 | `SiliconRoot`: fused UDS, anti-rollback fuse, extend-only registers, DICE alias key, quote engine, attacker tooling (`forged_quote`) |
| `hardware_ref/attest.py` | L5 + verifier | `GovernanceRoot` (signs reference values, revocations, policy); `AttestationVerifier` (nonces, cert chain, reference values, composite CPU+GPU binding, tokens) |
| `hardware_ref/policy.py` | L4 | policy schema and validation (default-deny only), rule selection, parameter constraints |
| `hardware_ref/gate.py` | L4 | `PolicyGate`: attestation → grant → witnesses → budget → hold/allow; one-time action tickets; approvals |
| `hardware_ref/endpoints.py` | L4 | `EndpointRegistry`: executes only against a valid, unconsumed, request-bound ticket |
| `hardware_ref/assertions.py` | L2/L3 interface | observer and provenance assertion formats; stub producers used by the harness |
| `hardware_ref/oasp.py` | NVIDIA OASP | `SupervisorMiddleware` (gate on OpenShell's request path), `to_openshell_network_policy`, `SentryObserver`, `SentryActuator`, `to_ocsf` |
| `hardware_ref/audit.py` | audit | signed hash chain, RFC 6962 Merkle root, checkpoints, inclusion and consistency proofs, offline verifier |
| `hardware_ref/system.py` | all | `build_node()`: wires one reference node with the default capability table |
| `hardware_ref/attacks.py`, `harness.py` | harness | the catalogue (66 attacks + 10 baselines) and the sweep runner / report writer |
| `hardware_ref/cli.py` | — | `hwctl demo · sweep · verify-audit · openshell-policy · ocsf · layers` |
| `tests/` | — | 37 unit and integration tests, including a brute-force check of the Merkle proofs, the OASP path and the full sweep |

## Documentation

- [`docs/NVIDIA.md`](docs/NVIDIA.md) — how this lane sits on NVIDIA's Open Agent Safety Platform: supervisor middleware, derived OpenShell policy, Sentry as witness and kill switch, OCSF export
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the six-layer model, the decision order, trust anchors, and why the control plane roots below the model
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) — adversaries, what each layer defends against, what this reference cannot defend against
- [`docs/LANES.md`](docs/LANES.md) — the signed-assertion contracts between this repo, `safety` (Layer 3) and `Watermark` (Layer 2)
- [`docs/SILICON.md`](docs/SILICON.md) — module-by-module mapping to hardware blocks, the properties only silicon gives, and the roadmap to the theoretical chip design
- [`docs/USAGE.md`](docs/USAGE.md) — CLI, Python API, data formats, extending the policy and the catalogue

## The three lanes

| Repo | Layer | Role | Coupling |
|---|---|---|---|
| [`Watermark`](https://github.com/YobieBenjamin/Watermark) | 2 | provenance sensor: watermark, hardened detector, retrieval, signed registry | emits provenance assertions |
| `safety` | 3 | early-warning observers that speak *before* the model acts | emits observer assertions |
| `hardware` (this repo) | 0, 4, 5 | silicon root, control plane, governance root | consumes both; grants nothing without attestation |
| NVIDIA OASP (OpenShell + Sentry) | runtime + infrastructure | sandbox, network policy, credentials, out-of-band watchdog, quarantine | hosts the gate as supervisor middleware; Sentry emits observer assertions |

Nothing here imports from the other two repos. The only coupling is two signed
message formats, defined in `docs/LANES.md`.

## Limits, stated plainly

This is a functional reference, not a secure implementation. The silicon root is
emulated in Python: there is no physical isolation, no side-channel resistance,
no fault-injection resistance, and the "fused" secret is a private attribute. The
attacks in the catalogue are logical attacks — forged, replayed, swapped, stale,
rewritten — and the stack blocks all of them; it says nothing about physical
attacks, which is exactly the gap the silicon design (`docs/SILICON.md`) exists to
close. Endpoints are stubs that describe an effect instead of causing one.

## License

MIT — see [`LICENSE`](LICENSE).
