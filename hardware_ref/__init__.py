"""hardware_ref: reference stack for the hardware lane of a layered AI-safety architecture.

Layer 0 silicon root of trust · attestation verifier · Layer 4 control plane
(policy gate, transactional reservations and one-time action tickets, durable
state, policy epochs) · signed, Merkle-checkpointed audit trail · attack
harness. See README.md.
"""

__version__ = "0.2.0"
