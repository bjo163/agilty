from __future__ import annotations

"""Process-local per-principal token-bucket and in-flight request limiter."""

import asyncio
import math
import time
from dataclasses import dataclass


@dataclass(slots=True)
class _PrincipalState:
    tokens: float
    updated_at: float
    in_flight: int = 0


class PrincipalLimiter:
    """Bound request rate and concurrency within one Python worker process.

    This intentionally does not claim distributed enforcement. Multi-worker
    deployments need a shared limiter backend such as Redis.
    """

    def __init__(self, requests_per_minute: int = 120, max_in_flight: int = 4, max_principals: int = 10000):
        for name, value, minimum, maximum in (
            ("requests_per_minute", requests_per_minute, 1, 100000),
            ("max_in_flight", max_in_flight, 1, 10000),
            ("max_principals", max_principals, 100, 1000000),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
        self.requests_per_minute = requests_per_minute
        self.max_in_flight = max_in_flight
        self.max_principals = max_principals
        self._states: dict[str, _PrincipalState] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, principal_id: str, *, now: float | None = None) -> tuple[bool, float]:
        if not isinstance(principal_id, str) or not principal_id or len(principal_id) > 256:
            raise ValueError("principal_id must be a non-empty identifier of at most 256 characters")
        current = time.monotonic() if now is None else now
        async with self._lock:
            state = self._states.get(principal_id)
            if state is None:
                if len(self._states) >= self.max_principals:
                    idle = [(key, value.updated_at) for key, value in self._states.items() if value.in_flight == 0]
                    if not idle:
                        return False, 1.0
                    evict_key = min(idle, key=lambda item: item[1])[0]
                    self._states.pop(evict_key, None)
                state = _PrincipalState(float(self.requests_per_minute), current)
                self._states[principal_id] = state
            elapsed = max(0.0, current - state.updated_at)
            refill_rate = self.requests_per_minute / 60.0
            state.tokens = min(float(self.requests_per_minute), state.tokens + elapsed * refill_rate)
            state.updated_at = current
            if state.in_flight >= self.max_in_flight:
                return False, 1.0
            if state.tokens < 1.0:
                return False, max(1.0, math.ceil((1.0 - state.tokens) / refill_rate))
            state.tokens -= 1.0
            state.in_flight += 1
            return True, 0.0

    async def release(self, principal_id: str) -> None:
        async with self._lock:
            state = self._states.get(principal_id)
            if state is not None:
                state.in_flight = max(0, state.in_flight - 1)

    async def snapshot(self, principal_id: str) -> dict[str, float | int] | None:
        async with self._lock:
            state = self._states.get(principal_id)
            if state is None:
                return None
            return {"tokens": state.tokens, "in_flight": state.in_flight, "updated_at": state.updated_at}
