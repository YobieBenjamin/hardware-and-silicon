"""One reference node with every layer wired together.

    Layer 0  SiliconRoot ×2 (cpu-tee, gpu)       root.py
    Layer 4  AttestationVerifier → PolicyGate   attest.py, gate.py
    Layer 5  GovernanceRoot                     attest.py
    Lane 2   StubProvenanceRegistry             assertions.py   (stands in for the Watermark repo)
    Lane 3   StubObserver                       assertions.py   (stands in for the safety repo)
    Lane 3   SentryObserver + SentryActuator    oasp.py         (NVIDIA Sentry on BlueField-4)
    OASP     SupervisorMiddleware               oasp.py         (the gate on OpenShell's request path)
    Audit    AuditLog                           audit.py
    Endpoints EndpointRegistry                  endpoints.py

``build_node()`` manufactures the chips, boots golden firmware, publishes
reference values and a policy, and returns a ``Node`` with convenience
methods for the happy path. The harness then breaks it in every way it can.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from .assertions import StubObserver, StubProvenanceRegistry
from .attest import AttestationResult, AttestationVerifier, GovernanceRoot, build_bundle, reference_entry, workload_measurement
from .clock import SimClock
from .endpoints import EndpointRegistry, stub_handlers
from .gate import GateResult, PolicyGate, make_approval, request_hash
from .keys import SigningKey, hkdf
from .ledger import StateStore
from .oasp import Route, SentryActuator, SentryObserver, SupervisorMiddleware
from .root import Firmware, ManufacturerCA, SiliconRoot

CPU_FW = Firmware("tee-runtime", "2.4.0", svn=3, code=b"cpu tee runtime build 2.4.0 :: measured container :: model-serving image sha ab12")
GPU_FW = Firmware("gpu-firmware", "96.00.5E", svn=5, code=b"gpu vbios+fw 96.00.5E :: confidential-compute mode on")
OLD_CPU_FW = Firmware("tee-runtime", "2.1.0", svn=1, code=b"cpu tee runtime build 2.1.0 :: known-vulnerable")

DEFAULT_POLICY_ARGS = {"observer_freshness_s": 60, "hold_ttl_s": 3600}


API_HOST = "api.internal.example.com"
MAIL_HOST = "mail.internal.example.com"


def default_policy(measurement: str, observer: str | list[str] = "obs-main", high_authority_observer: str | list[str] | None = None) -> dict:
    """The capability table for the golden workload. Everything else is denied by construction.

    ``observer`` names the Layer 3 witness the observer-gated rules require:
    ``"obs-main"`` (the safety repo's observer), ``"sentry"`` (NVIDIA Sentry via
    the OASP adapter) or a list of both (every listed witness must pass).
    ``high_authority_observer`` overrides it for ``human``-mode rules (the
    highest-authority actions) so those can demand both witnesses while the
    rest run on one. Each rule that reaches the network carries an ``egress``
    block, from which the OpenShell network policy is derived.
    """
    high = high_authority_observer if high_authority_observer is not None else observer
    return {
        "default": "deny",
        **DEFAULT_POLICY_ARGS,
        "rules": [
            {
                "id": "pay-small",
                "workload": measurement,
                "action": "payments.transfer",
                "constraints": {"amount": {"type": "number", "max": 1000, "min": 0}, "currency": {"in": ["USD"]}, "destination": {"regex": r"acct-[0-9]{6}"}},
                "requirement": {"mode": "observer", "observer": observer, "max_risk": 0.3},
                "rate_limit": {"max": 3, "window_s": 60},
                "budget": {"key": "pay-usd-hourly", "param": "amount", "limit": 2000, "window_s": 3600},
                "egress": {"host": API_HOST, "port": 443, "protocol": "rest", "access": "read-write"},
            },
            {
                "id": "pay-large",
                "workload": measurement,
                "action": "payments.transfer",
                "constraints": {"amount": {"type": "number", "max": 50000, "min": 1000.01}, "currency": {"in": ["USD"]}, "destination": {"regex": r"acct-[0-9]{6}"}},
                "requirement": {"mode": "human", "observer": high, "max_risk": 0.3},
                "egress": {"host": API_HOST, "port": 443, "protocol": "rest", "access": "read-write"},
            },
            {
                "id": "mail-out",
                "workload": measurement,
                "action": "email.send",
                "constraints": {"to": {"regex": r"[^@\s]+@example\.com"}, "body": {"type": "string", "maxlen": 4000}},
                "requirement": {"mode": "observer", "observer": observer, "max_risk": 0.3},
                "provenance": {"registry": "wm-registry", "status": "exact", "param": "body"},
                "egress": {"host": MAIL_HOST, "port": 443, "protocol": "rest", "access": "read-write"},
            },
            {
                "id": "http-allowlist",
                "workload": "*",
                "action": "http.post",
                "constraints": {"url": {"regex": r"https://api\.internal\.example\.com/.*"}},
                "requirement": {"mode": "auto"},
                "rate_limit": {"max": 10, "window_s": 60},
                "egress": {"host": API_HOST, "port": 443, "protocol": "rest", "access": "read-only"},
            },
            # No rule at all for shell.exec or model.weights.export: those endpoints exist, and nothing can reach them.
        ],
    }


def default_routes() -> list[Route]:
    """How outbound requests seen by the OpenShell supervisor map to consequential actions."""
    return [
        Route("POST", API_HOST, "/payments/transfer", "payments.transfer"),
        Route("POST", MAIL_HOST, "/mail/send", "email.send"),
        Route("POST", API_HOST, "/exec", "shell.exec"),
        Route("POST", "models.internal.example.com", "/weights/export", "model.weights.export"),
        Route("POST", API_HOST, "/v1/**", "http.post", lambda body: {"url": f"https://{API_HOST}{body.get('path', '/v1/')}"}),
    ]


@dataclass
class Node:
    clock: SimClock
    cpu_vendor: ManufacturerCA
    gpu_vendor: ManufacturerCA
    cpu: SiliconRoot
    gpu: SiliconRoot
    governance: GovernanceRoot
    verifier: AttestationVerifier
    observer: StubObserver
    registry: StubProvenanceRegistry
    approver_key: SigningKey
    gate: PolicyGate
    endpoints: EndpointRegistry
    measurement: str
    signed_policy: dict
    signed_reference: dict
    sentry: SentryObserver
    actuator: SentryActuator
    supervisor: SupervisorMiddleware
    notes: list[str] = field(default_factory=list)
    state_dir: str | None = None
    gate_key: SigningKey | None = None

    # -- restart ---------------------------------------------------------------------------

    def restart(self) -> "Node":
        """Rebuild the gate, the endpoints and the supervisor from durable state, as after a power loss.

        The gate's signing key is DICE-style (derived, not stored), so the same code gets the same
        key back; the policy is re-loaded from its signed document; replay state, holds, rate
        windows, reservations and the endpoint's consumed set come back from the stores. The
        audit log is a fresh chain (its export/verify path is the durable record).
        """
        gate_store, ep_store = _stores(self.state_dir)
        gate = PolicyGate(
            self.verifier.public,
            self.governance.public,
            self.clock,
            observers={"obs-main": self.observer.public, "sentry": self.sentry.public},
            registries={"wm-registry": self.registry.public},
            approvers={"ops-lead": self.approver_key.public},
            key=self.gate_key,
            store=gate_store,
        )
        gate.load_policy(self.signed_policy)
        endpoints = _endpoints(gate, self.clock, ep_store)
        actuator = SentryActuator(gate.audit)
        supervisor = SupervisorMiddleware(gate, self.clock, sentry=self.sentry, actuator=actuator)
        for route in default_routes():
            supervisor.add_route(route)
        self.gate, self.endpoints, self.actuator, self.supervisor = gate, endpoints, actuator, supervisor
        self.notes.append("restarted from durable state")
        return self

    # -- happy path --------------------------------------------------------------------

    def attest(self) -> AttestationResult:
        nonce = self.verifier.issue_nonce()
        return self.verifier.verify_node(build_bundle(self.cpu, self.gpu, nonce))

    def build_request(self, action: str, params: dict, token: dict | None, *, measurement: str | None = None, observe: bool = True, provenance: bool = False, risk: float | None = None) -> dict:
        req = {"request_id": uuid.uuid4().hex, "measurement": measurement or self.measurement, "action": action, "params": params, "attestation_token": token, "assertions": []}
        rh = request_hash(req)
        if observe:
            req["assertions"].append(self.observer.assess(rh, action, params, risk=risk))
        if provenance and isinstance(params.get("body"), str):
            req["assertions"].append(self.registry.attest(params["body"]))
        return req

    def act(self, action: str, params: dict, token: dict | None, **kw: Any) -> tuple[GateResult, dict | None]:
        """Gate → endpoint in one call. Returns the gate result and the endpoint result (if executed)."""
        req = self.build_request(action, params, token, **kw)
        res = self.gate.request(req)
        if not res.allowed:
            return res, None
        return res, self.endpoints.execute(res.ticket, action, params)

    def approve(self, res: GateResult, *, approver: str = "ops-lead") -> GateResult:
        approval = make_approval(self.approver_key, approver, res.hold_id or "", res.request_hash, self.clock.now())
        return self.gate.approve(approval)


def _stores(state_dir: str | None) -> tuple[StateStore, StateStore]:
    if state_dir is None:
        return StateStore(None), StateStore(None)
    os.makedirs(state_dir, exist_ok=True)
    return StateStore(os.path.join(state_dir, "gate-state.json")), StateStore(os.path.join(state_dir, "endpoint-state.json"))


def _endpoints(gate: PolicyGate, clock: SimClock, store: StateStore) -> EndpointRegistry:
    """Endpoints trust the gate's key, bind to its policy epoch, and commit at the gate before executing."""
    endpoints = EndpointRegistry(gate.public, clock, gate.audit, name="endpoint", store=store, on_commit=gate.commit)
    endpoints.set_policy_epoch(gate.signed_epoch())
    for name, handler in stub_handlers().items():
        endpoints.register(name, handler)
    return endpoints


def build_node(*, clock: SimClock | None = None, rollback_protection: bool = True, observer: str | list[str] = "obs-main", high_authority_observer: str | list[str] | None = None, state_dir: str | None = None) -> Node:
    """Build a node. ``observer="sentry"`` makes the policy require NVIDIA Sentry's verdict (the OASP path);
    ``high_authority_observer=["sentry", "obs-main"]`` makes human-held actions demand both witnesses;
    ``state_dir`` puts the gate's and the endpoints' transactional state on disk so ``Node.restart()`` is meaningful."""
    clock = clock or SimClock()
    cpu_vendor, gpu_vendor = ManufacturerCA("cpu-vendor"), ManufacturerCA("gpu-vendor")
    cpu = SiliconRoot("cpu-tee", "CPU-0001", cpu_vendor, rollback_protection=rollback_protection)
    gpu = SiliconRoot("gpu", "GPU-7F3A", gpu_vendor, rollback_protection=rollback_protection)
    cpu.boot(CPU_FW)
    gpu.boot(GPU_FW)

    governance = GovernanceRoot()
    cpu_d, cpu_ref = reference_entry(CPU_FW)
    gpu_d, gpu_ref = reference_entry(GPU_FW)
    signed_reference = governance.reference_values({"cpu-tee": {"min_svn": 2, "firmware": {cpu_d: cpu_ref}}, "gpu": {"min_svn": 4, "firmware": {gpu_d: gpu_ref}}})
    verifier = AttestationVerifier({"cpu-vendor": cpu_vendor.public, "gpu-vendor": gpu_vendor.public}, governance.public, clock)
    verifier.load_reference_values(signed_reference)
    verifier.load_revocations(governance.revocations([]))

    measurement = workload_measurement(CPU_FW.digest, GPU_FW.digest)
    obs_main = StubObserver("obs-main", clock)
    sentry = SentryObserver("sentry", clock)
    registry = StubProvenanceRegistry("wm-registry", clock)
    approver_key = SigningKey.generate()
    # The gate's key is derived the way DICE derives an alias key, from what booted, so a restart of
    # the same code yields the same key instead of a new one. (In silicon the input is the secret
    # CDI; here it is the two chips' certified alias identities, which is enough for a simulation.)
    gate_key = SigningKey.from_seed(hkdf(bytes.fromhex(cpu.alias_cert["payload"]["subject_pub"]) + bytes.fromhex(gpu.alias_cert["payload"]["subject_pub"]), b"gate-signing-key", 32))
    gate_store, ep_store = _stores(state_dir)
    gate = PolicyGate(
        verifier.public,
        governance.public,
        clock,
        observers={"obs-main": obs_main.public, "sentry": sentry.public},
        registries={"wm-registry": registry.public},
        approvers={"ops-lead": approver_key.public},
        key=gate_key,
        store=gate_store,
    )
    signed_policy = governance.policy(default_policy(measurement, observer, high_authority_observer))
    gate.load_policy(signed_policy)

    endpoints = _endpoints(gate, clock, ep_store)

    actuator = SentryActuator(gate.audit)
    supervisor = SupervisorMiddleware(gate, clock, sentry=sentry, actuator=actuator)
    for route in default_routes():
        supervisor.add_route(route)

    return Node(clock, cpu_vendor, gpu_vendor, cpu, gpu, governance, verifier, obs_main, registry, approver_key, gate, endpoints, measurement, signed_policy, signed_reference, sentry, actuator, supervisor, state_dir=state_dir, gate_key=gate_key)


def build_oasp_node(*, clock: SimClock | None = None, observer: str | list[str] = "sentry", high_authority_observer: str | list[str] | None = None, second_witness: bool = False) -> Node:
    """A node on the NVIDIA path: policy requires Sentry's verdict, sandbox bound to an attested host.

    ``second_witness=True`` also puts the safety repo's observer (``obs-main``, stubbed
    here) on the supervisor path, so rules that list both witnesses can be satisfied.
    """
    node = build_node(clock=clock, observer=observer, high_authority_observer=high_authority_observer)
    res = node.attest()
    node.supervisor.bind_sandbox("sandbox-a", node.measurement, res.token if res.accepted else None)
    if second_witness:
        node.supervisor.add_witness(lambda rh, action, params: node.observer.assess(rh, action, params))
    return node
