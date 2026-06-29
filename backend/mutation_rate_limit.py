"""In-memory rate limiting for mutation endpoints."""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import defaultdict, deque
from typing import Iterable

from fastapi import HTTPException, Request


_LOCK = threading.Lock()
_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)


def check_mutation_rate_limit(
    request: Request,
    supplied_tokens: Iterable[str],
    *,
    max_requests: int,
    window_seconds: int,
) -> None:
    if max_requests <= 0 or window_seconds <= 0:
        return
    now = time.time()
    key = _rate_limit_key(request, supplied_tokens)
    with _LOCK:
        attempts = _ATTEMPTS[key]
        cutoff = now - window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if len(attempts) >= max_requests:
            retry_after = max(1, int(math.ceil(attempts[0] + window_seconds - now)))
            raise HTTPException(
                status_code=429,
                detail="Mutation endpoint rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        attempts.append(now)


def reset_mutation_rate_limiter_for_tests() -> None:
    with _LOCK:
        _ATTEMPTS.clear()


def _rate_limit_key(request: Request, supplied_tokens: Iterable[str]) -> str:
    client = getattr(request, "client", None)
    host = str(getattr(client, "host", "") or "unknown")
    token = next((str(item).strip() for item in supplied_tokens if str(item).strip()), "missing")
    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"{host}:{fingerprint}"
