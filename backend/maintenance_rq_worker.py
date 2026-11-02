"""Cooperative, per-pop maintenance leases for the installed RQ SimpleWorker.

No I/O on import and no global RQ patches. This gates ordinary consumption,
not RQ's separate scheduler, startup reconciliation or a frozen canary path.
An accepted synchronous job owns its lease through execute_job cleanup; do
not automatically hand that authority to unrelated threads or asyncio tasks.
"""
from contextlib import ExitStack


DEQUEUE_POLL_SECONDS = 5


def maintenance_worker_class(base_class):
    """Wrap the caller's SimpleWorker class, keeping its non-forking lifecycle.

    RQ 1.16.2 retries timeouts inside dequeue_job_and_maintain_ttl, and stale
    IDs inside Queue.dequeue_any. Guard each underlying lpop/lmove instead of
    holding one admission across either potentially unbounded retry loop.
    """
    class MaintenanceWorker(base_class):
        maintenance_pause_reason = None

        def _release_maintenance_lease(self):
            stack = getattr(self, '_maintenance_stack', None)
            self._maintenance_stack = None
            if stack is not None:
                stack.close()

        def _maintenance_pop(self, operation):
            from maintenance_guard import admission, MaintenanceError
            from rq.worker import StopRequested
            # Another pop within dequeue_any means the previous raw ID was
            # stale. It is not authority to consume a different job after arm.
            self._release_maintenance_lease()
            # RQ retries blocking timeouts inside dequeue_any. Recheck native
            # suspension before each bounded pop, not only outside that loop.
            check = getattr(self, 'check_for_suspension', None)
            if check is not None:
                check(False)
                if getattr(self, '_stop_requested', False):
                    raise StopRequested()
            stack = ExitStack()
            self._maintenance_stack = stack
            try:
                try:
                    stack.enter_context(admission())
                except MaintenanceError as error:
                    self.maintenance_pause_reason = type(error).__name__
                    raise StopRequested() from None
                result = operation()
            except BaseException:
                self._release_maintenance_lease()
                raise
            if result is None:
                self._release_maintenance_lease()
            return result

        def dequeue_job_and_maintain_ttl(self, timeout, max_idle_time=None):
            original = self.queue_class
            owner = self
            def bounded(value):
                # None is RQ's burst/nonblocking pop, not an infinite wait.
                return None if value is None else min(value, DEQUEUE_POLL_SECONDS)
            class AdmissionQueue(original):
                @classmethod
                def lpop(cls, queue_keys, timeout, connection=None):
                    return owner._maintenance_pop(lambda: super(AdmissionQueue, cls).lpop(
                        queue_keys, bounded(timeout), connection=connection))

                @classmethod
                def lmove(cls, connection, queue_key, timeout):
                    return owner._maintenance_pop(lambda: super(AdmissionQueue, cls).lmove(
                        connection, queue_key, bounded(timeout)))

            self.queue_class = AdmissionQueue
            try:
                result = super().dequeue_job_and_maintain_ttl(timeout, max_idle_time)
            except BaseException:
                self._release_maintenance_lease()
                raise
            finally:
                self.queue_class = original
            if result is None:
                self._release_maintenance_lease()
            return result

        def execute_job(self, job, queue):
            if getattr(self, '_maintenance_stack', None) is None:
                raise RuntimeError('RQ execution requires an owned dequeue admission')
            try:
                return super().execute_job(job, queue)
            finally:
                # SimpleWorker.perform_job handles success/failure callbacks
                # and registry cleanup before returning to execute_job.
                self._release_maintenance_lease()

        def work(self, *args, **kwargs):
            from maintenance_guard import admission, MaintenanceError
            self.maintenance_pause_reason = None
            try:
                # Fail closed before bootstrap/scheduler creation when already
                # armed or unavailable. Actual dequeue always reacquires.
                with admission():
                    pass
            except MaintenanceError as error:
                self.maintenance_pause_reason = type(error).__name__
                return False
            try:
                return super().work(*args, **kwargs)
            finally:
                # Also covers interruption after dequeue but before execute,
                # and upstream work/teardown exceptions. Never send a signal.
                self._release_maintenance_lease()

    return MaintenanceWorker
