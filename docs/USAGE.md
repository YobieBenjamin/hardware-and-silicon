# Usage

## One command

```bash
./run.sh          # venv → install → pytest (37 tests) → sweep (66 attacks + 10 baselines) → results/report.md
./run.sh demo     # the same, then `hwctl demo`
./reproduce.sh    # run.sh, then git diff of results/ against the committed report
```

`PYTHON=/path/to/python3.x ./run.sh` overrides interpreter selection. Exit
status is non-zero if a test fails or any catalogue entry misbehaves.

## CLI

```
hwctl demo                      narrated flow on one simulated node (boot → attest → gate → ticket → endpoint → audit → NVIDIA OASP path)
hwctl sweep [--out DIR]         run the catalogue; writes DIR/report.md and DIR/report.json (default DIR=results)
hwctl verify-audit FILE.json    verify an exported audit log offline; exit 0 ok, 2 tampered
hwctl openshell-policy          print the OpenShell network_policies YAML derived from the signed gate policy
hwctl ocsf [--out FILE]         export a demo node's audit trail as OCSF-shaped JSON events
hwctl layers                    print the layer model
hwctl --version
```

`hardware-ref` is an alias of `hwctl`; `python -m hardware_ref …` works without
installing the console script.

## Python API

Build a node and walk the happy path:

```python
from hardware_ref.system import build_node
from hardware_ref.clock import SimClock

clock = SimClock()
node = build_node(clock=clock)                  # two chips booted, verifier + gate + endpoints wired

res = node.attest()                             # composite CPU+GPU attestation
assert res.accepted
token = res.token                               # signed, expires in 300 s of simulated time

gate_res, out = node.act("payments.transfer",
                         {"amount": 250, "currency": "USD", "destination": "acct-123456"},
                         token)                 # gate → ticket → endpoint
print(gate_res.decision, out)                   # Decision.ALLOW {'effect': 'transfer 250 USD to acct-123456', ...}

held, _ = node.act("payments.transfer", {"amount": 25000, "currency": "USD", "destination": "acct-654321"}, token)
approved = node.approve(held)                   # signs with the registered approver key
node.endpoints.execute(approved.ticket, "payments.transfer", {"amount": 25000, "currency": "USD", "destination": "acct-654321"})

node.gate.audit.checkpoint()
node.gate.audit.dump("audit.json")              # hwctl verify-audit audit.json
```

Lower-level pieces, if you want to wire your own node:

```python
from hardware_ref.root import ManufacturerCA, SiliconRoot, Firmware
from hardware_ref.attest import GovernanceRoot, AttestationVerifier, build_bundle, reference_entry
from hardware_ref.gate import PolicyGate
from hardware_ref.endpoints import EndpointRegistry, stub_handlers

ca = ManufacturerCA("cpu-vendor")
chip = SiliconRoot("cpu-tee", "CPU-0001", ca)
chip.boot(Firmware("tee-runtime", "2.4.0", svn=3, code=b"..."))
evidence = chip.quote(nonce="…from the verifier…")
```

`build_node()` in `hardware_ref/system.py` is the reference wiring and the
best place to read how the pieces fit.

### On the NVIDIA Open Agent Safety Platform

```python
from hardware_ref.system import build_oasp_node, API_HOST
from hardware_ref.oasp import OutboundRequest, ticket_from_header, to_openshell_network_policy, to_yaml, export_ocsf

node = build_oasp_node()                        # policy requires Sentry's verdict; sandbox-a bound to the attested host

# what the OpenShell supervisor hands the middleware for each outbound request
d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer",
                                           {"amount": 250, "currency": "USD", "destination": "acct-123456"}))
d.status, d.reasons                              # 200, []
ticket = ticket_from_header(d.headers["X-Action-Ticket"])
node.endpoints.execute(ticket, "payments.transfer", {...})

node.supervisor.telemetry = lambda req: {"drift_score": 0.95, "identity_verified": True}   # what Sentry reports
d = node.supervisor.handle(OutboundRequest("sandbox-a", "POST", API_HOST, "/payments/transfer", {...}))
d.status, d.reasons, d.quarantined               # 403, ['observer.risk_above_threshold'], True
node.actuator.release("sandbox-a", "ops-lead")

print(to_yaml(to_openshell_network_policy(node.gate.policy)))   # feed to `openshell policy set`
events = export_ocsf(node.gate.audit)                            # OCSF-shaped, chain hash in `unmapped`
```

`SupervisorMiddleware.add_route(Route(method, host, path, action, params))`
maps outbound requests to consequential actions; `bind_sandbox(id, measurement,
token)` and `refresh_token` keep the sandbox→host attestation current;
`add_witness(producer)` puts a second Layer 3 witness (the safety repo's
observer) on the path; `DriftPolicy(quarantine_risk, max_denials, window_s)`
sets when a denial becomes a quarantine.

Witness configuration lives in the policy: `build_oasp_node(observer="sentry")`
is the default (Sentry required, nothing else), `observer=["sentry", "obs-main"]`
requires both for every observer-gated action, and
`high_authority_observer=["sentry", "obs-main"]` requires both only for
`human`-mode rules — the recommended shape (`docs/NVIDIA.md`).

## Policy

The policy document is plain JSON signed by the governance root. The default
one is `hardware_ref.system.default_policy(measurement)`:

```python
{
  "default": "deny",                          # the only accepted value
  "observer_freshness_s": 60,
  "hold_ttl_s": 3600,
  "rules": [
    {"id": "pay-small", "workload": "<measurement>", "action": "payments.transfer",
     "constraints": {"amount": {"type": "number", "max": 1000, "min": 0},
                     "currency": {"in": ["USD"]},
                     "destination": {"regex": "acct-[0-9]{6}"}},
     "requirement": {"mode": "observer", "observer": "obs-main", "max_risk": 0.3},
     "rate_limit": {"max": 3, "window_s": 60}},
    {"id": "pay-large", "workload": "<measurement>", "action": "payments.transfer",
     "constraints": {"amount": {"type": "number", "max": 50000, "min": 1000.01}, ...},
     "requirement": {"mode": "human", "observer": "obs-main", "max_risk": 0.3}},
    {"id": "mail-out", "workload": "<measurement>", "action": "email.send",
     "constraints": {"to": {"regex": "[^@\\s]+@example\\.com"}, "body": {"type": "string", "maxlen": 4000}},
     "requirement": {"mode": "observer", "observer": "obs-main", "max_risk": 0.3},
     "provenance": {"registry": "wm-registry", "status": "exact", "param": "body"}},
    {"id": "http-allowlist", "workload": "*", "action": "http.post",
     "constraints": {"url": {"regex": "https://api\\.internal\\.example\\.com/.*"}},
     "requirement": {"mode": "auto"}, "rate_limit": {"max": 10, "window_s": 60}}
  ]
}
```

Constraint kinds: `type` (`number` | `string` | `bool`), `max`, `min`, `in`,
`regex` (full match), `maxlen`, `required` (default true). Several rules may
grant the same action; a request takes the first whose constraints it satisfies.
A rule bound to a measurement beats a `"*"` rule.

A rule's optional `egress` block (`host`, `port`, `protocol`, `access`,
`binaries`) is what `to_openshell_network_policy` turns into the OpenShell
`network_policies` entry for that rule; a rule without one grants nothing at
the network layer.

Requirement modes: `auto`, `observer` (needs `observer` and `max_risk`), `human`
(held until a registered approver signs; an `observer` threshold may still be
set and is checked first).

To load a new policy: `node.gate.load_policy(node.governance.policy(doc))`. A
policy that is not governance-signed, not default-deny, or malformed raises and
leaves the previous policy in force.

## Extending the catalogue

Add a function to `hardware_ref/attacks.py`:

```python
@attack("L4.my_attack", "L4", "One sentence on what the attacker does")
def _my_attack(node):
    ...                     # do the bad thing on this fresh node
    return observed, blocked   # a short string, and whether the stack stopped it
```

Use `expect="allowed"` for a baseline. `hwctl sweep` picks it up; the
integration test asserts every entry behaves as expected.

## Data formats

All messages are signed envelopes over canonical JSON; see `docs/LANES.md` for
the token, ticket, assertion and audit-record schemas. `hardware_ref.canon`
has the encoder; `hardware_ref.keys.verify_object(envelope, expected_key)` is
the one verification routine every layer uses.

## Tests

```bash
python -m pytest -q tests                    # all
python -m pytest -q tests/test_audit.py -k merkle
```

`tests/test_root_attest.py` covers the silicon root and verifier,
`tests/test_gate.py` the policy, gate, holds and endpoints,
`tests/test_audit.py` the chain and a brute-force check of inclusion and
consistency proofs for every tree size up to 20,
`tests/test_oasp.py` the NVIDIA path (middleware, holds, quarantine and release,
drift window, multi-observer rules, policy translation, OCSF export), and
`tests/test_integration.py` the full flow plus the sweep.
