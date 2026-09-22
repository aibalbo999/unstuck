"""Bounded RQ observations in two read-only pipelines, without registry cleanup."""
from analysis_job_execution_state import timestamp
from analysis_job_payload_values import _iso_timestamp
from mapping_fields import safe_text
import time


def _text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else safe_text(value)


def inspect_job_registries(task_queue, jobs):
    jobs = list(jobs)[:50]
    observed = _iso_timestamp(time.time())
    unknown = {str(row.get('job_id')): {'state': 'unknown', 'checked_at': observed,
                'reason': 'registry_unavailable'} for row in jobs}
    try:
        connection = getattr(task_queue, 'redis', None)
        if connection is None:
            connection = getattr(getattr(task_queue, 'queue', None), 'connection', None)
        if connection is None:
            return unknown
        from rq.job import Job
        from rq.registry import ScheduledJobRegistry, StartedJobRegistry, DeferredJobRegistry, FailedJobRegistry, FinishedJobRegistry
        from rq import Queue

        ids = [('report-rerun:' if str(row.get('pipeline_id', '')).startswith('rerun:') else 'analysis:') + str(row.get('job_id')) for row in jobs]
        with connection.pipeline(transaction=False) as pipe:
            for task_id in ids:
                pipe.hmget(Job.key_for(task_id), 'status', 'origin', 'last_heartbeat')
            hashes = pipe.execute()
        classes = [('scheduled', ScheduledJobRegistry), ('started', StartedJobRegistry),
                   ('deferred', DeferredJobRegistry), ('failed', FailedJobRegistry), ('finished', FinishedJobRegistry)]
        with connection.pipeline(transaction=False) as pipe:
            for task_id, fields in zip(ids, hashes):
                origin = _text(fields[1])
                for _, cls in classes:
                    pipe.zscore(cls(name=origin or 'default', connection=connection).key, task_id)
                pipe.lpos(Queue(name=origin or 'default', connection=connection).key, task_id)
            memberships = pipe.execute()
        result = {}
        for index, (row, fields) in enumerate(zip(jobs, hashes)):
            job_status, origin, heartbeat = map(_text, fields)
            values = memberships[index * 6:index * 6 + 6]
            states = [name for (name, _), score in zip(classes, values[:5]) if score is not None]
            if values[5] is not None:
                states.append('queued')
            state = states[0] if len(states) == 1 else 'conflict' if states else 'missing'
            result[str(row.get('job_id'))] = {
                'state': state, 'job_status': job_status or None, 'memberships': states,
                'queue': origin or None, 'checked_at': observed,
                'scheduled_at': _iso_timestamp(values[0]) if 'scheduled' in states else None,
                'heartbeat_at': _iso_timestamp(timestamp(heartbeat)),
            }
        return result
    except Exception:
        return unknown  # No exception message, Redis URL, job arguments, or credential metadata.
