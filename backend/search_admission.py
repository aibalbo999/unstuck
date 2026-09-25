"""Nonwaiting endpoint admission using the existing provider lock backends."""
from contextlib import contextmanager, ExitStack
import hashlib
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
