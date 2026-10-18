"""Atomic RQ dispatch identity check and enqueue, including lost EXEC replies."""
from __future__ import annotations
from redis.exceptions import WatchError
from rq.job import Job
from rq.exceptions import NoSuchJobError


def _status(job):
    status = job.get_status(refresh=True)
    return str(getattr(status, 'value', status))


def _queued_receipt_is_confirmed(queue, job):
    """A hash alone is not evidence that an EXEC successfully pushed the task."""
    status = _status(job)
    completed_or_active = {'started', 'scheduled', 'deferred', 'finished', 'failed', 'canceled', 'stopped'}
    if status != 'queued':
        return status in completed_or_active
    connection = queue.connection
    if connection.lpos(queue.key, job.id) is not None:
        return True
    if connection.lpos(queue.intermediate_queue_key, job.id) is not None:
        return True
    # The worker can move the task between these reads. Never re-enqueue during
    # that transition; a later tick can use RQ/SQLite execution evidence.
    return _status(job) in completed_or_active


def dispatch_receipt(queue, task_id):
    try:
        job = Job.fetch(task_id, connection=queue.connection)
    except NoSuchJobError:
        return None
    if job.origin != queue.name or not _queued_receipt_is_confirmed(queue, job):
        return None
    return {'task_id': job.id, 'status': _status(job), 'args': job.args}


def enqueue_once(queue, task_id, fn, args, kwargs, *, retry, timeout):
    connection = queue.connection
    key = Job.key_for(task_id)
    expected_function = fn if isinstance(fn, str) else f'{fn.__module__}.{fn.__qualname__}'
    # RQ writes the hash and list through the supplied EXEC. WATCH protects the
    # absence check across producers; connection errors retain the SQLite intent.
    for _ in range(8):
        try:
            with connection.pipeline() as pipe:
                pipe.watch(key)
                if pipe.exists(key):
                    existing = Job.fetch(task_id, connection=pipe)
                    if (existing.func_name != expected_function or existing.args != args
                            or existing.kwargs != kwargs or existing.origin != queue.name):
                        raise ValueError('dispatch task id already belongs to different work')
                    if not _queued_receipt_is_confirmed(queue, existing):
                        raise RuntimeError('dispatch queue receipt not confirmed; retain pending intent')
                    return {'task_id': task_id, 'created': False}
                # RQ setup_dependencies owns MULTI, after all dependency WATCHes.
                queue.enqueue_call(
                    func=fn, args=args, kwargs=kwargs, job_id=task_id,
                    timeout=timeout, retry=retry, result_ttl=7 * 24 * 60 * 60,
                    failure_ttl=7 * 24 * 60 * 60, pipeline=pipe,
                )
                pipe.execute()
                return {'task_id': task_id, 'created': True}
        except WatchError:
            continue
    raise RuntimeError('dispatch enqueue contention; retry on next scheduler tick')
