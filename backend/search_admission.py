"""Endpoint admission using the existing provider lock backends."""
import asyncio
from contextlib import asynccontextmanager, contextmanager, ExitStack
import hashlib
import math
import threading

from shared_provider_cache import _process_lock

_LOCKS = tuple(threading.Lock() for _ in range(128))


@contextmanager
def endpoint_admission(key, *, timeout_seconds):
    digest = hashlib.sha256(('search:' + key).encode()).hexdigest()
    local = _LOCKS[int(digest[:8], 16) % len(_LOCKS)]
    if not local.acquire(blocking=False):
        yield None
        return
    ownership = {}
    try:
        # The lease outlives the bounded HTTP call. Redis ownership is checked
        # again before publishing state in case a process was suspended.
        with ExitStack() as stack:
            try:
                acquired = stack.enter_context(_process_lock(
                    digest, blocking_timeout=0,
                    lease_timeout=max(60, timeout_seconds + 30),
                    ownership_check=ownership))
            except Exception:
                # A missing shared guard must not produce uncontrolled requests.
                yield None
                return
            def owns():
                try:
                    return bool(acquired and ownership.get('owns', lambda: False)())
                except Exception:
                    return False
            yield owns if acquired else None
    finally:
        local.release()


@asynccontextmanager
async def async_endpoint_admission(key, *, timeout_seconds, wait_seconds=0):
    """Optionally wait a little for ownership without blocking the event loop.

    Every acquisition remains nonblocking, including the process lock. Polling
    only repeats local admission, never an HTTP request. Cancellation while
    waiting cannot release another caller's lock.
    """
    wait_seconds = float(wait_seconds)
    if not math.isfinite(wait_seconds) or wait_seconds < 0:
        raise ValueError('wait_seconds must be finite and nonnegative')
    loop = asyncio.get_running_loop()
    deadline = loop.time() + min(wait_seconds, max(0, timeout_seconds))
    while True:
        with endpoint_admission(key, timeout_seconds=timeout_seconds) as owns:
            if owns is not None:
                yield owns
                return
        remaining = deadline - loop.time()
        if remaining <= 0:
            yield None
            return
        await asyncio.sleep(min(0.025, remaining))
        if loop.time() >= deadline:
            yield None
            return
