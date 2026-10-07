"""A simulated clock.

Every freshness check in the stack (nonce TTL, token expiry, assertion
staleness, ticket lifetime, rate-limit windows) reads this clock, so tests
and the attack harness can move time forward deterministically instead of
sleeping. In silicon the equivalent is a monotonic counter the root of trust
owns and software cannot wind back.
"""
from __future__ import annotations

import time


class SimClock:
    def __init__(self, start: float = 1_800_000_000.0):
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("a monotonic clock cannot move backwards")
        self._now += float(seconds)
        return self._now


class WallClock:
    """Real time, for the CLI demo."""

    def now(self) -> float:
        return time.time()

    def advance(self, seconds: float) -> float:  # pragma: no cover - interactive only
        time.sleep(seconds)
        return self.now()
