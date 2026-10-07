"""Signed, hash-chained, Merkle-checkpointed audit trail.

Every gate decision, every endpoint execution and every refusal lands here.
Three independent mechanisms make the log tamper-evident:

1. **Hash chain.** Entry *i* commits to entry *i-1*; editing, deleting or
   reordering any entry breaks every later link.
2. **Signatures.** Each entry's chain hash is signed by the gate's key, so an
   attacker who rewrites the chain from a point onwards must also forge
   signatures.
3. **Merkle checkpoints** (RFC 6962 / RFC 9162 tree construction). The gate
   periodically signs ``(size, root)``. Anyone holding an old checkpoint can
   demand a *consistency proof* that the new log extends it, and anyone
   holding a receipt can demand an *inclusion proof* for one entry. These
   are the same proofs Certificate Transparency and Sigstore rely on.

In silicon: entries go to append-only NVM, the head hash and size live in a
monotonic register the root of trust owns, and checkpoints are signed by
the chip. Software then cannot truncate the log without the counter
disagreeing — see ``docs/SILICON.md``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from .canon import b64d, b64e, canonical, sha256
from .clock import SimClock
from .keys import SigningKey, VerifyKey, sign_object, verify_object

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


# -- Merkle tree (RFC 6962) -------------------------------------------------------------------


def leaf_hash(leaf: bytes) -> bytes:
    return sha256(LEAF_PREFIX + leaf)


def node_hash(left: bytes, right: bytes) -> bytes:
    return sha256(NODE_PREFIX + left + right)


def _largest_power_of_two_below(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def merkle_root(leaves: list[bytes]) -> bytes:
    """MTH over already-hashed leaves."""
    n = len(leaves)
    if n == 0:
        return sha256(b"")
    if n == 1:
        return leaves[0]
    k = _largest_power_of_two_below(n)
    return node_hash(merkle_root(leaves[:k]), merkle_root(leaves[k:]))


def inclusion_proof(leaves: list[bytes], index: int) -> list[bytes]:
    n = len(leaves)
    if not 0 <= index < n:
        raise IndexError("leaf index out of range")
    if n == 1:
        return []
    k = _largest_power_of_two_below(n)
    if index < k:
        return inclusion_proof(leaves[:k], index) + [merkle_root(leaves[k:])]
    return inclusion_proof(leaves[k:], index - k) + [merkle_root(leaves[:k])]


def verify_inclusion(leaf: bytes, index: int, size: int, proof: list[bytes], root: bytes) -> bool:
    """RFC 9162 §2.1.3.2."""
    if index >= size:
        return False
    fn, sn, r = index, size - 1, leaf
    for p in proof:
        if sn == 0:
            return False
        if fn % 2 == 1 or fn == sn:
            r = node_hash(p, r)
            if fn % 2 == 0:
                while fn % 2 == 0 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root


def consistency_proof(leaves: list[bytes], old_size: int) -> list[bytes]:
    n = len(leaves)
    if not 0 < old_size <= n:
        raise ValueError("old_size must be in 1..size")

    def subproof(m: int, d: list[bytes], b: bool) -> list[bytes]:
        if m == len(d):
            return [] if b else [merkle_root(d)]
        k = _largest_power_of_two_below(len(d))
        if m <= k:
            return subproof(m, d[:k], b) + [merkle_root(d[k:])]
        return subproof(m - k, d[k:], False) + [merkle_root(d[:k])]

    return subproof(old_size, leaves, True)


def verify_consistency(old_size: int, old_root: bytes, new_size: int, new_root: bytes, proof: list[bytes]) -> bool:
    """RFC 9162 §2.1.4.2."""
    if old_size == 0:
        return True
    if old_size > new_size:
        return False
    if old_size == new_size:
        return old_root == new_root and proof == []
    if not proof:
        return False
    path = list(proof)
    if old_size & (old_size - 1) == 0:  # exact power of two
        path = [old_root] + path
    fn, sn = old_size - 1, new_size - 1
    while fn % 2 == 1:
        fn >>= 1
        sn >>= 1
    fr = sr = path[0]
    for c in path[1:]:
        if sn == 0:
            return False
        if fn % 2 == 1 or fn == sn:
            fr = node_hash(c, fr)
            sr = node_hash(c, sr)
            if fn % 2 == 0:
                while fn % 2 == 0 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            sr = node_hash(sr, c)
        fn >>= 1
        sn >>= 1
    return sn == 0 and fr == old_root and sr == new_root


# -- the log -----------------------------------------------------------------------------------


@dataclass
class VerifyReport:
    ok: bool
    reason: str = "ok"
    checked: int = 0


def entry_leaf(entry: dict) -> bytes:
    """The bytes a Merkle leaf commits to: everything except the chain hash and signature."""
    return canonical({k: entry[k] for k in ("seq", "ts", "prev", "record")})


class AuditLog:
    def __init__(self, key: SigningKey, clock: SimClock, name: str = "gate-audit"):
        self._key = key
        self.clock = clock
        self.name = name
        self.entries: list[dict] = []
        self.checkpoints: list[dict] = []
        self._leaves: list[bytes] = []
        self._head: bytes = sha256(b"audit-genesis")

    @property
    def public(self) -> VerifyKey:
        return self._key.public

    @property
    def size(self) -> int:
        return len(self.entries)

    @property
    def head(self) -> str:
        return self._head.hex()

    def append(self, record: dict[str, Any]) -> dict:
        entry: dict[str, Any] = {"seq": len(self.entries), "ts": self.clock.now(), "prev": self._head.hex(), "record": record}
        leaf = leaf_hash(entry_leaf(entry))
        chain = sha256(self._head + leaf)
        entry["hash"] = chain.hex()
        entry["sig"] = b64e(self._key.sign(chain))
        self.entries.append(entry)
        self._leaves.append(leaf)
        self._head = chain
        return entry

    def checkpoint(self) -> dict:
        cp = sign_object(
            self._key,
            {"type": "audit-checkpoint", "log": self.name, "size": self.size, "root": merkle_root(self._leaves).hex(), "head": self.head, "ts": self.clock.now()},
        )
        self.checkpoints.append(cp)
        return cp

    def inclusion(self, seq: int) -> dict:
        return {"seq": seq, "size": self.size, "leaf": self._leaves[seq].hex(), "proof": [p.hex() for p in inclusion_proof(self._leaves, seq)], "root": merkle_root(self._leaves).hex()}

    def consistency(self, old_size: int) -> dict:
        return {"old_size": old_size, "new_size": self.size, "proof": [p.hex() for p in consistency_proof(self._leaves, old_size)], "new_root": merkle_root(self._leaves).hex()}

    def export(self) -> dict:
        return {"log": self.name, "pub": self.public.hex, "entries": self.entries, "checkpoints": self.checkpoints}

    def dump(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.export(), fh, indent=1, sort_keys=True)

    # -- verification, usable by anyone holding only the public key -------------------------

    @staticmethod
    def leaves_of(entries: Iterable[dict]) -> list[bytes]:
        return [leaf_hash(entry_leaf(e)) for e in entries]

    @staticmethod
    def verify_chain(entries: list[dict], pub: VerifyKey, genesis: bytes | None = None) -> VerifyReport:
        head = genesis or sha256(b"audit-genesis")
        for i, e in enumerate(entries):
            try:
                if e["seq"] != i:
                    return VerifyReport(False, f"seq {e['seq']} at position {i}", i)
                if e["prev"] != head.hex():
                    return VerifyReport(False, f"chain broken at seq {i}", i)
                leaf = leaf_hash(entry_leaf(e))
                chain = sha256(head + leaf)
                if e["hash"] != chain.hex():
                    return VerifyReport(False, f"hash mismatch at seq {i}", i)
                if not pub.verify(b64d(e["sig"]), chain):
                    return VerifyReport(False, f"signature invalid at seq {i}", i)
            except (KeyError, TypeError, ValueError) as exc:
                return VerifyReport(False, f"malformed entry at position {i}: {exc}", i)
            head = chain
        return VerifyReport(True, "ok", len(entries))

    @staticmethod
    def verify_checkpoint(cp: dict, entries: list[dict], pub: VerifyKey) -> VerifyReport:
        if not verify_object(cp, pub) or cp["payload"].get("type") != "audit-checkpoint":
            return VerifyReport(False, "checkpoint signature invalid")
        p = cp["payload"]
        size = p["size"]
        if size > len(entries):
            return VerifyReport(False, f"log truncated: checkpoint covers {size} entries, {len(entries)} present")
        if size and entries[size - 1]["hash"] != p["head"]:
            return VerifyReport(False, "checkpoint head does not match entry chain")
        root = merkle_root(AuditLog.leaves_of(entries[:size]))
        if root.hex() != p["root"]:
            return VerifyReport(False, "checkpoint root does not match entries")
        return VerifyReport(True, "ok", size)

    @staticmethod
    def verify_export(doc: dict) -> VerifyReport:
        pub = VerifyKey.from_hex(doc["pub"])
        rep = AuditLog.verify_chain(doc["entries"], pub)
        if not rep.ok:
            return rep
        for cp in doc.get("checkpoints", []):
            crep = AuditLog.verify_checkpoint(cp, doc["entries"], pub)
            if not crep.ok:
                return crep
        return VerifyReport(True, "ok", len(doc["entries"]))
