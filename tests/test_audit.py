import copy
import os

from hardware_ref.audit import AuditLog, consistency_proof, inclusion_proof, leaf_hash, merkle_root, verify_consistency, verify_inclusion
from hardware_ref.clock import SimClock
from hardware_ref.keys import SigningKey, VerifyKey


def _log(n: int) -> AuditLog:
    log = AuditLog(SigningKey.generate(), SimClock())
    for i in range(n):
        log.append({"event": "test", "i": i})
    return log


def test_merkle_proofs_against_brute_force():
    leaves = [leaf_hash(os.urandom(8)) for _ in range(20)]
    for n in range(1, 21):
        root = merkle_root(leaves[:n])
        for i in range(n):
            assert verify_inclusion(leaves[i], i, n, inclusion_proof(leaves[:n], i), root)
            assert not verify_inclusion(leaf_hash(b"x"), i, n, inclusion_proof(leaves[:n], i), root)
        for m in range(1, n + 1):
            old = merkle_root(leaves[:m])
            assert verify_consistency(m, old, n, root, consistency_proof(leaves[:n], m))
            if n > m:
                forked = list(leaves[:n])
                forked[m - 1] = leaf_hash(b"fork")
                assert not verify_consistency(m, old, n, merkle_root(forked), consistency_proof(forked, m))


def test_chain_verifies_and_detects_edits():
    log = _log(6)
    doc = log.export()
    assert AuditLog.verify_export(doc).ok
    bad = copy.deepcopy(doc)
    bad["entries"][2]["record"]["i"] = 99
    rep = AuditLog.verify_export(bad)
    assert not rep.ok and "seq 2" in rep.reason
    bad = copy.deepcopy(doc)
    bad["entries"][4]["sig"] = bad["entries"][3]["sig"]
    assert "signature" in AuditLog.verify_export(bad).reason
    bad = copy.deepcopy(doc)
    bad["entries"].pop(0)
    assert not AuditLog.verify_export(bad).ok


def test_checkpoint_pins_size_and_root():
    log = _log(5)
    cp = log.checkpoint()
    log.append({"event": "later"})
    assert AuditLog.verify_checkpoint(cp, log.entries, log.public).ok
    assert not AuditLog.verify_checkpoint(cp, log.entries[:4], log.public).ok
    assert not AuditLog.verify_checkpoint(cp, log.entries, VerifyKey(SigningKey.generate().public.raw)).ok


def test_export_roundtrip_through_json(tmp_path):
    import json

    log = _log(4)
    log.checkpoint()
    path = tmp_path / "audit.json"
    log.dump(str(path))
    doc = json.loads(path.read_text())
    assert AuditLog.verify_export(doc).ok and AuditLog.verify_export(doc).checked == 4


def test_inclusion_and_consistency_from_log_api():
    log = _log(9)
    cp = log.checkpoint()["payload"]
    for _ in range(4):
        log.append({"event": "more"})
    inc = log.inclusion(7)
    assert verify_inclusion(bytes.fromhex(inc["leaf"]), 7, inc["size"], [bytes.fromhex(p) for p in inc["proof"]], bytes.fromhex(inc["root"]))
    con = log.consistency(cp["size"])
    assert verify_consistency(cp["size"], bytes.fromhex(cp["root"]), con["new_size"], bytes.fromhex(con["new_root"]), [bytes.fromhex(p) for p in con["proof"]])
