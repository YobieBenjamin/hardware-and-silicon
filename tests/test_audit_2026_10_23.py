# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Yobie Benjamin. Noncommercial use only; see NOTICE and LICENSING.md.
"""Regressions for the external audit of 23 October 2026 (findings F07, F08, F22 against this
repository). Each test fails against the code before the fix and passes after.

F07  The HS attestation token was a transferable bearer credential: the gate verified the token
     but never proved the requester controlled the attested compute.
F08  HS revocation rollback protection disappeared when the verifier was reconstructed: a fresh
     verifier started from an empty version floor and accepted authentic-but-superseded documents.
F22  The offline audit verifier trusted the public key inside the file and accepted a stripped
     authentic prefix with its checkpoints removed.
"""
import copy
import uuid

import pytest

from hardware_ref.attest import AttestationVerifier, build_bundle
from hardware_ref.audit import AuditLog
from hardware_ref.gate import request_auth_payload, sign_request_auth
from hardware_ref.keys import SigningKey, sign_object
from hardware_ref.ledger import StateStore
from hardware_ref.system import build_node

PAY = {"amount": 250, "currency": "USD", "destination": "acct-123456"}
URL = "https://api.internal.example.com/v1/ping"


# ---------------------------------------------------------------- F07 bearer token
def test_f07_attestation_token_is_not_a_transferable_bearer_credential():
    node = build_node()
    tok = node.attest().token                       # authentic token; carries the attested session_pub
    k1 = node.session_key                           # the private half, held only by the attested workload
    measurement = node.measurement
    session_pub = tok["payload"]["session_pub"]

    def adversary_req():
        """An otherwise-permitted automatic http.post, built from only the public token + measurement."""
        return {
            "request_id": uuid.uuid4().hex,
            "measurement": measurement,
            "action": "http.post",
            "params": {"url": URL},
            "attestation_token": tok,
            "assertions": [],
        }

    # (1) A borrower holding only the public token and measurement cannot prove possession.
    assert node.gate.request(adversary_req()).reasons == ["request_auth.missing"]

    # (2) Forging the proof with the borrower's own key, while claiming the token's session_pub, fails.
    rogue = SigningKey.generate()
    forged = adversary_req()
    forged["request_auth"] = sign_object(rogue, request_auth_payload(node.gate.name, forged, session_pub))
    assert node.gate.request(forged).reasons == ["request_auth.signature"]

    # (3) Cross-gate: a genuine proof made for a different gate (audience) does not transfer.
    other_gate = adversary_req()
    other_gate["request_auth"] = sign_request_auth(k1, "some-other-gate", other_gate)
    assert node.gate.request(other_gate).reasons == ["request_auth.audience"]

    # A request actually signed by the attested session key succeeds and executes.
    res, out = node.act("http.post", {"url": URL}, tok, observe=False)
    assert res.allowed and out["status"] == "simulated"

    # (4) Cross-session: a proof made with another attestation's session key does not transfer to this token.
    tok2 = node.attest().token
    k2 = node.session_key
    cross = adversary_req()                          # still carries the first token (session k1)
    cross["request_auth"] = sign_request_auth(k2, node.gate.name, cross)
    assert node.gate.request(cross).reasons == ["request_auth.signature"]

    # (5) Replay: resubmitting a complete, validly signed request is caught by replay protection.
    good = node.build_request("http.post", {"url": URL + "2"}, tok2, observe=False)
    assert node.gate.request(good).allowed
    assert node.gate.request(good).reasons == ["request.replayed"]


# ---------------------------------------------------------------- F08 revocation rollback on reconstruction
def test_f08_revocation_survives_verifier_reconstruction(tmp_path):
    node = build_node()
    gov = node.governance
    anchors = {"cpu-vendor": node.cpu_vendor.public, "gpu-vendor": node.gpu_vendor.public}
    store_path = str(tmp_path / "verifier-state.json")
    device = node.cpu.device_id

    # Verifier V, backed by a durable store, loads reference values and an empty revocation list.
    V = AttestationVerifier(anchors, gov.public, node.clock, store=StateStore(store_path))
    V.load_reference_values(node.signed_reference)
    L_permit = gov.revocations([])                   # authentic, permits the device
    V.load_revocations(L_permit)
    assert V.verify_node(build_bundle(node.cpu, node.gpu, V.issue_nonce())).accepted

    # Governance revokes the device; V installs the newer list.
    V.load_revocations(gov.revocations([device]))
    assert "cpu.device.revoked" in V.verify_node(build_bundle(node.cpu, node.gpu, V.issue_nonce())).reasons

    # The version floor and the active documents it names were persisted together (one atomic write).
    saved = StateStore(store_path).load()
    assert saved["high_water"]["revocation-list"][0] == 3
    assert {"reference-values", "revocation-list"} <= set(saved["active"])

    # Destroy V; reconstruct V2 from the same pinned roots and the same store.
    del V
    V2 = AttestationVerifier(anchors, gov.public, node.clock, store=StateStore(store_path))

    # The attacker replays the retained, authentic, but superseded empty list: refused by the floor.
    with pytest.raises(ValueError):
        V2.load_revocations(L_permit)

    # A different document claiming the same (current) version is also refused.
    conflict = sign_object(gov._key, {"type": "revocation-list", "issuer": gov.name, "version": 3, "device_ids": ["OTHER-DEVICE"]})
    with pytest.raises(ValueError):
        V2.load_revocations(conflict)

    # The device answers a fresh V2 challenge with genuine evidence: the revocation still holds.
    assert "cpu.device.revoked" in V2.verify_node(build_bundle(node.cpu, node.gpu, V2.issue_nonce())).reasons

    # Current documents + a device the current list does not revoke must succeed.
    V2.load_revocations(gov.revocations([]))         # genuinely newer list that un-revokes
    assert V2.verify_node(build_bundle(node.cpu, node.gpu, V2.issue_nonce())).accepted


def test_f08_verifier_freezes_when_persisted_state_cannot_be_reverified(tmp_path):
    """Power interruption / tampering: if recovery cannot establish freshness, the verifier refuses
    to appraise rather than vouch for a floor it cannot trust."""
    node = build_node()
    anchors = {"cpu-vendor": node.cpu_vendor.public, "gpu-vendor": node.gpu_vendor.public}
    store_path = str(tmp_path / "verifier-state.json")
    V = AttestationVerifier(anchors, node.governance.public, node.clock, store=StateStore(store_path))
    V.load_reference_values(node.signed_reference)
    V.load_revocations(node.governance.revocations([]))

    # A floor that names a document the store does not hold (interrupted mid-write / tampered).
    saved = StateStore(store_path).load()
    saved["high_water"]["revocation-list"] = [99, "0" * 64]
    StateStore(store_path).save(saved)

    V2 = AttestationVerifier(anchors, node.governance.public, node.clock, store=StateStore(store_path))
    assert V2.verify_node(build_bundle(node.cpu, node.gpu, V2.issue_nonce())).reasons == ["verifier.freshness_unestablished"]


# ---------------------------------------------------------------- F22 offline audit verifier
def test_f22_offline_audit_requires_a_pinned_key_and_a_retained_checkpoint():
    node = build_node()
    tok = node.attest().token
    node.act("http.post", {"url": URL}, tok, observe=False)
    node.act("payments.transfer", PAY, tok)
    log = node.gate.audit

    pinned = node.gate.public                        # pinned OUT OF BAND, not read from the file
    retained = log.checkpoint()                      # retained, authenticated minimum checkpoint
    current = copy.deepcopy(log.export())

    # Current history, and a valid append-only extension, both verify in authenticated mode.
    rep = AuditLog.verify_export(current, pub=pinned, min_checkpoint=retained)
    assert rep.ok and rep.authenticated
    node.act("http.post", {"url": URL + "x"}, tok, observe=False)
    extended = copy.deepcopy(log.export())
    rep = AuditLog.verify_export(extended, pub=pinned, min_checkpoint=retained)
    assert rep.ok and rep.authenticated

    # Attack 1: a replacement history signed with an attacker key, that key placed in doc["pub"].
    rogue = SigningKey.generate()
    forged_log = AuditLog(rogue, node.clock, name=log.name)
    for e in current["entries"]:
        forged_log.append(e["record"])
    forged_log.checkpoint()
    forged_doc = forged_log.export()
    assert forged_doc["pub"] != pinned.hex
    sc = AuditLog.verify_export(forged_doc)          # self-consistency is fooled, but says so
    assert sc.ok and not sc.authenticated
    auth = AuditLog.verify_export(forged_doc, pub=pinned, min_checkpoint=retained)
    assert not auth.ok and auth.authenticated        # pinned key verification rejects it

    # Attack 2: keep the real key and a genuine signed prefix; drop the tail and all checkpoints.
    stripped = copy.deepcopy(current)
    stripped["entries"] = stripped["entries"][:1]
    stripped["checkpoints"] = []
    sc2 = AuditLog.verify_export(stripped)           # the prefix is internally consistent
    assert sc2.ok and not sc2.authenticated
    auth2 = AuditLog.verify_export(stripped, pub=pinned, min_checkpoint=retained)
    assert not auth2.ok and auth2.authenticated      # the retained checkpoint covers more; truncation caught

    # An older authentic export (fewer entries than the retained checkpoint) is also rejected.
    older = copy.deepcopy(current)
    older["entries"] = older["entries"][:-1]
    older["checkpoints"] = []
    assert not AuditLog.verify_export(older, pub=pinned, min_checkpoint=retained).ok

    # Authenticated mode without a retained checkpoint is not accepted as authenticated history.
    assert not AuditLog.verify_export(current, pub=pinned).ok

    # Self-consistency mode is labelled explicitly as NOT authenticated.
    label = AuditLog.verify_export(current)
    assert label.ok and not label.authenticated and "NOT authenticated" in label.reason
