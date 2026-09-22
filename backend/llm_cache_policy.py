"""Task-local candidate-cache exclusion for bounded quality repair calls."""
from contextlib import contextmanager
from contextvars import ContextVar

_repair_cache = ContextVar('llm_quality_repair_cache', default=None)


def repair_cache_scope_active():
    return _repair_cache.get() is not None


def candidate_cache_read_allowed(layer):
    counters = _repair_cache.get()
    if counters is None:
        return True
    key = 'step_cache_reads_skipped' if layer == 'step' else 'raw_cache_reads_skipped'
    counters[key] = counters.get(key, 0) + 1
    return False


@contextmanager
def fresh_repair_candidate(counters):
    """Never reuse an unverified draft as a new quality repair opportunity.

    Only this repair call tree bypasses reads, including exact/semantic raw cache.
    Valid preceding graph nodes and concurrent requests keep their normal caches.
    Writes remain raw candidates; they do not certify quality acceptance.
    """
    token = _repair_cache.set(counters)
    try:
        yield
    finally:
        _repair_cache.reset(token)
