# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Yobie Benjamin. Noncommercial use only; see NOTICE and LICENSING.md.
"""Transactional authorization state: durable replay protection, a serialized budget ledger, policy epochs.

Added after the October 2026 design review (``docs/REVIEW-2026-10.md``, point 5). A signed
ticket on its own does not supply transactional semantics. Four things have to hold, and they
have to keep holding across a restart, a power loss, a policy change and a network partition:

* **Replay protection that survives restart.** Request hashes and consumed ticket ids live in a
  store that is written before the result is returned, not in a Python set.
* **Reserve, then commit.** A rule may carry a ``budget`` (a shared allowance such as "2,000 USD
  of small payments per hour"). The gate *reserves* against it when it allows a request, the
  endpoint *commits* the reservation before it executes, and an unexecuted reservation is
  *released* when its ticket expires. Reserve and commit happen under one lock, so two
  concurrent requests cannot both pass a check that only one of them fits.
* **One owner per budget.** A budget key is owned by exactly one ledger. Several individually
  correct gates can still collectively overspend a shared allowance, so a shared allowance is
  never checked locally by each of them; it is reserved at the ledger that owns it.
* **Policy epochs.** A ticket names the policy version that issued it. After the governance root
  changes the policy, the endpoint refuses tickets from the old epoch.

In silicon (``docs/SILICON.md`` §1): the replay store is a monotonic counter plus a small CAM in
the root's non-volatile memory; the ledger is a set of hardware counters owned by the gate block;
the epoch is the digest of the loaded policy image, held in a register the host cannot write.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any

from .keys import random_nonce

REPLAY_TTL_S = 86_400.0  # how long a request hash / ticket id is remembered after it can no longer be useful


class StateStore:
    """A durable JSON document with atomic replacement (write temp → fsync → rename).

    ``path=None`` keeps the document in memory, which is the pre-review behaviour and is what
    most unit tests use. A real deployment points it at non-volatile storage the gate owns.
    """

    def __init__(self, path: str | None = None):
        self.path = path

    def load(self) -> dict | None:
        if self.path is None or not os.path.exists(self.path):
            return None
        with open(self.path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def save(self, doc: dict) -> None:
        if self.path is None:
            return
        tmp = f"{self.path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, sort_keys=True, separators=(",", ":"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)


class DurableState:
    """Replay store, rate-limit windows, holds, budget ledger and policy epoch, persisted together.

    Every mutating method writes the document back through the store before returning, so a
    crash after the return cannot forget the mutation. All methods take the same lock; the gate
    holds it for the whole of a decision so that *check → reserve → mint* is one critical section.
    """

    def __init__(self, store: StateStore | None = None):
        self.store = store or StateStore(None)
        self.lock = threading.RLock()
        self.data: dict[str, Any] = self.store.load() or {
            "seq": 0,
            "seen": {},        # request hash → forget-after timestamp
            "consumed": {},    # ticket id → forget-after timestamp
            "holds": {},       # hold id → hold record
            "allows": {},      # "measurement|action" → [timestamps]
            "budgets": {},     # key → {"committed": [[amount, ts], …], "reserved": {rid: {...}}}
            "epoch": None,     # policy id the endpoint currently accepts
            "epoch_version": 0,   # the policy version behind it: an epoch with a lower one is a replay
            "policy_version": 0,  # the gate's: the newest governance policy version it has loaded
            "signed_policy": None,  # the gate's: that policy document, so a restart reloads the newest one
        }
        for k, v in (("epoch_version", 0), ("policy_version", 0), ("signed_policy", None)):
            self.data.setdefault(k, v)

    # -- persistence ---------------------------------------------------------------------

    def save(self) -> None:
        self.store.save(self.data)

    def tick(self) -> int:
        """A monotonic sequence number. In silicon: a counter that only increments."""
        with self.lock:
            self.data["seq"] += 1
            return self.data["seq"]

    def purge(self, now: float) -> None:
        with self.lock:
            for bucket in ("seen", "consumed"):
                stale = [k for k, until in self.data[bucket].items() if until < now]
                for k in stale:
                    del self.data[bucket][k]

    # -- replay protection ---------------------------------------------------------------

    def seen_request(self, request_hash: str) -> bool:
        with self.lock:
            return request_hash in self.data["seen"]

    def mark_request(self, request_hash: str, now: float, ttl: float = REPLAY_TTL_S) -> None:
        with self.lock:
            self.data["seen"][request_hash] = now + ttl
            self.save()

    def consumed(self, ticket_id: str) -> bool:
        with self.lock:
            return ticket_id in self.data["consumed"]

    def consume(self, ticket_id: str, now: float, ttl: float = REPLAY_TTL_S) -> None:
        with self.lock:
            self.data["consumed"][ticket_id] = now + ttl
            self.save()

    # -- rate-limit windows and holds -----------------------------------------------------

    def window(self, key: str) -> list[float]:
        return self.data["allows"].setdefault(key, [])

    @property
    def holds(self) -> dict[str, dict]:
        return self.data["holds"]

    # -- policy epoch --------------------------------------------------------------------

    @property
    def epoch(self) -> str | None:
        return self.data.get("epoch")

    def set_epoch(self, policy_id: str, version: int = 0) -> None:
        """Move to a policy epoch. Refuses one whose policy version is below the current one, or a
        different policy under the same version: a signature proves the gate issued an epoch once,
        not that it is still the current one (an old epoch replayed resurrected revoked tickets until
        22 October 2026)."""
        with self.lock:
            cur_v, cur = self.data.get("epoch_version", 0), self.data.get("epoch")
            if version < cur_v or (version == cur_v and cur is not None and policy_id != cur):
                raise ValueError(f"policy epoch: version {version} is not newer than the current {cur_v} (a replayed epoch)")
            self.data["epoch"], self.data["epoch_version"] = policy_id, version
            self.save()

    # -- budget ledger -------------------------------------------------------------------

    def _budget(self, key: str) -> dict:
        return self.data["budgets"].setdefault(key, {"committed": [], "reserved": {}})

    def _expire_reservations(self, b: dict, now: float) -> None:
        for rid in [r for r, rec in b["reserved"].items() if rec["expires_at"] < now]:
            del b["reserved"][rid]

    def usage(self, key: str, window_s: float, now: float) -> dict[str, float]:
        """Committed amount inside the window plus everything currently reserved."""
        with self.lock:
            b = self._budget(key)
            self._expire_reservations(b, now)
            b["committed"] = [c for c in b["committed"] if c[1] >= now - window_s]
            return {
                "committed": sum(c[0] for c in b["committed"]),
                "reserved": sum(r["amount"] for r in b["reserved"].values()),
            }

    def reserve(self, key: str, amount: float, limit: float, window_s: float, now: float, ttl: float) -> str | None:
        """Hold ``amount`` against ``key`` if committed + reserved + amount stays within ``limit``.

        Returns a reservation id, or ``None`` when the budget cannot take it. Check and reserve are
        one step under the lock, which is what makes two concurrent requests unable to both pass.
        """
        with self.lock:
            use = self.usage(key, window_s, now)
            if use["committed"] + use["reserved"] + amount > limit:
                return None
            rid = random_nonce(12)
            self._budget(key)["reserved"][rid] = {"amount": amount, "expires_at": now + ttl, "reserved_at": now}
            self.save()
            return rid

    def commit(self, key: str, rid: str, now: float) -> bool:
        """Turn a live reservation into a committed charge. False if it is unknown or has expired."""
        with self.lock:
            b = self._budget(key)
            self._expire_reservations(b, now)
            rec = b["reserved"].pop(rid, None)
            if rec is None:
                return False
            b["committed"].append([rec["amount"], now])
            self.save()
            return True

    def release(self, key: str, rid: str) -> bool:
        with self.lock:
            rec = self._budget(key)["reserved"].pop(rid, None)
            if rec is None:
                return False
            self.save()
            return True
