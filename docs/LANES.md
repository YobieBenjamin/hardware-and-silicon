# Lanes

Three repos, three lanes, no shared code. The only coupling is two signed
message formats that this repo *consumes* and the other two *produce*. This
document is the contract.

| Lane | Repo | Produces | Consumed by |
|---|---|---|---|
| Layer 2 · provenance | [`Watermark`](https://github.com/YobieBenjamin/Watermark) | provenance assertion | gate (`gate.py::_check_provenance`) |
| Layer 3 · observers | `safety` | observer assertion (`observer: "obs-main"`) | gate (`gate.py::_check_observer`) |
| Layer 3 · NVIDIA Sentry | NVIDIA Open Agent Safety Platform (BlueField-4, DOCA) | observer assertion (`observer: "sentry"`) via `oasp.SentryObserver`; quarantine via `oasp.SentryActuator` | gate; supervisor middleware |
| Layers 0/4/5 | `hardware` (this repo) | attestation token, action ticket, audit log (also OCSF-shaped) | gate, endpoints, auditors, OpenShell's OCSF pipeline |

## Envelope

Every message is a signed envelope over canonical JSON (sorted keys, no
whitespace, UTF-8):

```json
{"payload": {...}, "signer": "<sha256(pub)[:8] hex>", "pub": "<32-byte Ed25519 public key, hex>", "sig": "<base64 signature over canonical(payload)>"}
```

The gate verifies with the key it holds in its anchor table for the named
observer or registry. The embedded `pub` must equal that key; an envelope that
carries any other key is rejected regardless of its signature.

## Observer assertion (Layer 3 → gate)

```json
{
  "type": "observer-assertion",
  "observer": "obs-main",
  "subject": "<request hash: sha256 of canonical {request_id, measurement, action, params}>",
  "risk": 0.12,
  "flags": ["..."],
  "issued_at": 1800000000.0,
  "expires_at": 1800000060.0
}
```

Checks the gate performs, in order, each fail-closed:

1. `observer` names an anchored key, and the rule's `requirement.observer` names this observer;
2. signature valid under that key;
3. `subject` equals the hash of *this* request (a verdict about a different request is `observer.subject_mismatch`);
4. `issued_at ≥ now − observer_freshness_s` and `expires_at ≥ now` (`observer.stale`);
5. `risk ≤ requirement.max_risk` (`observer.risk_above_threshold`).

How `risk` is computed is the `safety` repo's business — or NVIDIA Sentry's,
when the assertion comes from the `oasp` adapter. `flags` are free-form and are
copied into the audit record for humans; the gate does not interpret them. A
rule may require one observer (`"observer": "sentry"`) or several
(`"observer": ["obs-main", "sentry"]`); with several, every one must pass.

The subject hash is computed by the gate *and* by the observer from the same
request core, so the observer must be shown the exact `request_id`,
`measurement`, `action` and `params` the gate will see. `hardware_ref.gate.request_hash`
is the reference implementation of that hash.

## Provenance assertion (Layer 2 → gate)

```json
{
  "type": "provenance-assertion",
  "registry": "wm-registry",
  "content_digest": "<sha256 of the UTF-8 content>",
  "status": "exact",
  "issued_at": 1800000000.0,
  "expires_at": 1800000300.0
}
```

Checks: anchored registry key; signature; `content_digest` equals the digest of
the request parameter the rule names (`provenance.param`, e.g. `body`);
unexpired; `status == "exact"`. `tampered` and `unknown` deny with
`provenance.status_tampered` / `provenance.status_unknown`.

This maps directly onto the Watermark repo's registry verdicts (`exact` /
`tampered` with diff spans / `unknown`). The diff spans, when present, belong in
the assertion payload as an extra field; the gate ignores fields it does not
know, so the format can grow without breaking the contract.

## Attestation token (verifier → gate)

```json
{
  "type": "attestation-token", "issuer": "verifier",
  "measurement": "<32 hex>", "nonce": "<...>",
  "devices": {"cpu-tee": {"device_id": "...", "fw": "tee-runtime:2.4.0", "svn": 3},
              "gpu":     {"device_id": "...", "fw": "gpu-firmware:96.00.5E", "svn": 5}},
  "issued_at": 1800000000.0, "expires_at": 1800000300.0
}
```

The gate checks signer (verifier key), `type`, expiry, and that `measurement`
equals the measurement the request claims. Nothing in the token is secret; it is
a short-lived statement of fact.

## Action ticket (gate → endpoint)

```json
{
  "type": "action-ticket", "ticket_id": "<16 bytes hex>",
  "request_hash": "<...>", "action": "payments.transfer", "params_digest": "<sha256 of canonical params>",
  "measurement": "<...>", "rule": "pay-small",
  "issued_at": 1800000000.0, "expires_at": 1800000060.0
}
```

Endpoints check signer (gate key), `type`, expiry, `action`, `params_digest`
against the parameters actually presented, and that `ticket_id` has not been
consumed. A ticket is the only thing an endpoint accepts.

## Audit record

Each entry is `{seq, ts, prev, record, hash, sig}`; `record` is free-form JSON
with an `event` field (`gate.policy_loaded`, `gate.decision`, `gate.approved`,
`endpoint.executed`, `endpoint.refused`). Observers' `flags`, reason codes, rule
ids, ticket ids and hold ids all land here. `hwctl verify-audit` and
`AuditLog.verify_export` are the reference verifiers.

## Rules of the road

- Nothing in `hardware` imports from `safety` or `Watermark`, and vice versa.
- A lane that wants to change a format adds fields; it does not rename or
  remove them. Consumers ignore unknown fields.
- Stubs for the other lanes live in `hardware_ref/assertions.py` and exist only
  to exercise the gate. They are not reference implementations of those lanes.
