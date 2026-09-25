"""Success bookkeeping for synchronous official-source endpoint guards."""
from copy import deepcopy
import math
import time


def failure_state_snapshot(key):
    """Capture the history before HTTP; an unreadable guard must not be cleared."""
    from search_provider_runtime import get_cache_json
    try:
        state = get_cache_json(key)
        return deepcopy(state) if isinstance(state, dict) else {} if state is None else None
    except Exception:
        return None


def reset_failure_history_after_success(key, observed_state, *, owns):
    """Publish success only while owning the endpoint admission lock.

    All same-key HTTP attempts and failure/success writes must use the same
    endpoint_admission context. The captured-state check additionally preserves
    updates made outside that contract; it is not used as a substitute for a lock.
    """
    from search_provider_runtime import get_cache_json, set_cache_json
    if observed_state is None:
        return
    try:
        if not owns():
            return
        current = get_cache_json(key)
        current = {} if current is None else current
        if not isinstance(current, dict) or current != observed_state:
            return
        # Expired failures reset; provider-advised active cooldowns remain protected.
        if float(current.get('retry_at') or 0) > time.time():
            return
        next_request = max(time.time(), float(current.get('next_request_at') or 0))
        if not owns():
            return
        set_cache_json(key, {'consecutive_failures': 0, 'next_request_at': next_request},
                       ttl_seconds=max(1, math.ceil(next_request-time.time())))
    except Exception:
        pass  # Bookkeeping cannot discard valid evidence already acquired.
