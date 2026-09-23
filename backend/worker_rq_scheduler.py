"""Bound scheduler takeover latency without changing job or heartbeat lifetimes."""
from rq import SimpleWorker

SCHEDULER_RECOVERY_INTERVAL_SECONDS = 30


class BoundedSchedulerWorker(SimpleWorker):
    """Keep RQ's NX lock ownership and normal maintenance-based recovery."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('maintenance_interval', SCHEDULER_RECOVERY_INTERVAL_SECONDS)
        super().__init__(*args, **kwargs)

    @property
    def dequeue_timeout(self):
        # Maintenance is checked between blocking dequeues. Its shorter interval
        # alone cannot help while the default 405-second dequeue is still waiting.
        return min(super().dequeue_timeout, SCHEDULER_RECOVERY_INTERVAL_SECONDS)
