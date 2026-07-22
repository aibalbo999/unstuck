"""Local token bucket helpers for LLM rate limiting."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    capacity: float
    refill_per_second: float
    tokens: float
    updated_at: float

    @classmethod
    def per_minute(cls, limit: int | float) -> "TokenBucket":
        capacity = max(float(limit), 1.0)
        return cls(
            capacity=capacity,
            refill_per_second=capacity / 60.0,
            tokens=capacity,
            updated_at=time.monotonic(),
        )

    def reserve(self, amount: int | float = 1) -> float:
        amount = min(max(float(amount), 1.0), self.capacity)
        now = time.monotonic()

        if now < self.updated_at:
            wait = self.updated_at - now + amount / self.refill_per_second
            self.updated_at += amount / self.refill_per_second
            return wait

        elapsed = now - self.updated_at
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated_at = now

        if self.tokens >= amount:
            self.tokens -= amount
            return 0.0

        shortage = amount - self.tokens
        wait = shortage / self.refill_per_second
        self.tokens = 0.0
        self.updated_at = now + wait
        return wait

    def peek_wait(self, amount: int | float = 1) -> float:
        amount = min(max(float(amount), 1.0), self.capacity)
        now = time.monotonic()

        if now < self.updated_at:
            return self.updated_at - now + amount / self.refill_per_second

        tokens = min(self.capacity, self.tokens + (now - self.updated_at) * self.refill_per_second)
        if tokens >= amount:
            return 0.0
        return (amount - tokens) / self.refill_per_second

    def penalize(self, seconds: float) -> None:
        self.tokens = 0.0
        self.updated_at = max(self.updated_at, time.monotonic() + max(seconds, 0.0))


__all__ = ["TokenBucket"]
