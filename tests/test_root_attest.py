import pytest

from hardware_ref.attest import build_bundle, workload_measurement
from hardware_ref.clock import SimClock
from hardware_ref.keys import SignatureError, verify_object
from hardware_ref.root import ManufacturerCA, RollbackRefused, SiliconRoot, golden_registers
from hardware_ref.system import CPU_FW, GPU_FW, OLD_CPU_FW, build_node


def test_measurement_registers_only_extend():
    ca = ManufacturerCA("v")
    chip = SiliconRoot("cpu-tee", "S", ca)
    chip.boot(CPU_FW)
    before = list(chip.registers)
    chip.extend(3, "extra", b"x")
    assert chip.registers[3] != before[3] and chip.registers[0] == before[0]
    with pytest.raises(IndexError):
        chip.extend(99, "bad", b"")


def test_golden_registers_match_a_clean_boot():
    ca = ManufacturerCA("v")
    chip = SiliconRoot("cpu-tee", "S", ca)
    chip.boot(CPU_FW)
    assert [r.hex() for r in chip.registers] == golden_registers(CPU_FW)
    chip.boot(CPU_FW.tampered())
    assert [r.hex() for r in chip.registers] != golden_registers(CPU_FW)


def test_dice_alias_key_is_bound_to_measurement():
    """Same chip, different firmware ⇒ different alias key; same firmware twice ⇒ same key."""
    ca = ManufacturerCA("v")
    chip = SiliconRoot("cpu-tee", "S", ca)
    chip.boot(CPU_FW)
    k1 = chip.alias_cert["payload"]["subject_pub"]
    chip.boot(CPU_FW)
    assert chip.alias_cert["payload"]["subject_pub"] == k1
    chip.boot(CPU_FW.tampered())
    assert chip.alias_cert["payload"]["subject_pub"] != k1
    # and the ROM-issued certificate records the measurement the key came from
    assert chip.alias_cert["payload"]["fw_digest"] == CPU_FW.tampered().digest


def test_two_chips_never_share_keys():
    ca = ManufacturerCA("v")
    a, b = SiliconRoot("cpu-tee", "A", ca), SiliconRoot("cpu-tee", "B", ca)
    a.boot(CPU_FW)
    b.boot(CPU_FW)
    assert a.device_id != b.device_id
    assert a.alias_cert["payload"]["subject_pub"] != b.alias_cert["payload"]["subject_pub"]


def test_anti_rollback_fuse_moves_forward_only():
    ca = ManufacturerCA("v")
    chip = SiliconRoot("cpu-tee", "S", ca)
    chip.boot(OLD_CPU_FW)
    assert chip.fused_svn == 1
    chip.boot(CPU_FW)
    assert chip.fused_svn == 3
    with pytest.raises(RollbackRefused):
        chip.boot(OLD_CPU_FW)
    assert chip.fused_svn == 3
    unfused = SiliconRoot("cpu-tee", "U", ca, rollback_protection=False)
    unfused.boot(CPU_FW)
    unfused.boot(OLD_CPU_FW)  # allowed on this chip; the verifier has to catch it


def test_quote_signature_and_certificate_chain():
    node = build_node()
    nonce = node.verifier.issue_nonce()
    ev = node.cpu.quote(nonce)
    assert verify_object(ev["device_cert"], node.cpu_vendor.public)
    assert ev["report"]["nonce"] == nonce
    assert node.verifier.appraise(ev) == []
    ev["report"]["svn"] = 99
    assert "report.signature" in node.verifier.appraise(ev)


def test_verify_node_issues_token_bound_to_measurement():
    node = build_node()
    res = node.attest()
    assert res.accepted and res.token is not None
    assert verify_object(res.token, node.verifier.public)
    p = res.token["payload"]
    assert p["measurement"] == workload_measurement(CPU_FW.digest, GPU_FW.digest) == node.measurement
    assert p["expires_at"] - p["issued_at"] == node.verifier.token_ttl
    assert set(p["devices"]) == {"cpu-tee", "gpu"}


def test_every_attestation_failure_mode_has_a_reason_code():
    node = build_node()
    nonce = node.verifier.issue_nonce()
    bundle = build_bundle(node.cpu, node.gpu, nonce)
    # mutate a copy per failure mode
    import copy

    b = copy.deepcopy(bundle)
    b["cpu"]["report"]["registers"][0] = "00" * 32
    assert node.verifier.verify_node(b).reasons  # signature over report now fails → not accepted
    assert node.verifier.verify_node(bundle).reasons == ["nonce.replayed"]  # consumed by the failed attempt
    assert node.verifier.verify_node({"nonce": "x"}).reasons == ["bundle.malformed"]


def test_reference_values_and_revocations_require_governance_signature():
    node = build_node()
    from hardware_ref.keys import SigningKey, sign_object

    rogue = sign_object(SigningKey.generate(), {"type": "revocation-list", "issuer": "governance-root", "device_ids": []})
    with pytest.raises(SignatureError):
        node.verifier.load_revocations(rogue)
    with pytest.raises(ValueError):
        node.verifier.load_reference_values(node.governance.revocations([]))  # wrong document type


def test_nonces_are_single_use_and_expire():
    clock = SimClock()
    node = build_node(clock=clock)
    n1 = node.verifier.issue_nonce()
    assert node.verifier.verify_node(build_bundle(node.cpu, node.gpu, n1)).accepted
    assert node.verifier.verify_node(build_bundle(node.cpu, node.gpu, n1)).reasons == ["nonce.replayed"]
    n2 = node.verifier.issue_nonce()
    clock.advance(node.verifier.nonce_ttl + 1)
    assert "nonce.expired" in node.verifier.verify_node(build_bundle(node.cpu, node.gpu, n2)).reasons
