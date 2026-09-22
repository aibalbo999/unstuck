"""Read-only public execution projection; observations never resubmit a job."""
from datetime import datetime, timezone
import re
import time

from analysis_job_payload_values import _iso_timestamp
from job_store import query_events, sanitize_error_message
from mapping_fields import safe_mapping_dict, safe_text


def timestamp(value):
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp()
        except (ValueError, OverflowError):
            pass
    iso = _iso_timestamp(value)
    return datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp() if iso else None


def execution_projection(job, *, events=(), registry=None, now=None):
    now = time.time() if now is None else now
    registry = dict(registry or {'state': 'unknown', 'reason': 'registry_not_read'})
    status = safe_text(job.get('db_status') or job.get('status')).strip().lower()
    status = {'completed': 'done', 'failed': 'error'}.get(status, status)
    rows = []
    for row in events:
        payload = safe_mapping_dict(row.get('payload')) or row
        rows.append({**payload, 'created_at': row.get('created_at'), 'id': row.get('id', 0)})
    rows.sort(key=lambda row: (timestamp(row.get('created_at')) or 0, row.get('id') or 0), reverse=True)
    retry = next((row for row in rows if row.get('phase') == 'workflow_retry'), {})
    progress = next((row for row in rows if row.get('type', row.get('event_type')) == 'progress'), {})
    error = sanitize_error_message(job.get('error')) or ''
    quality = any(row.get('phase') == 'report_quality_blocked' for row in rows[:1]) or bool(re.search(r'品質檢查|report quality|publication blocked', error, re.I))
    state = {'done': 'completed', 'error': 'terminal_quality' if quality else 'failed',
             'cancelled': 'cancelled', 'queued': 'queued', 'running': 'running',
             'waiting_retry': 'waiting_retry'}.get(status, 'unknown')
    reason, health, retry_at, retry_basis = '', 'normal', None, 'unknown'
    rq = registry.get('state', 'unknown')
    terminal = status in {'done', 'error', 'cancelled'}
    if terminal:
        reason = 'quality_blocked' if state == 'terminal_quality' else state
    elif status in {'queued', 'running', 'waiting_retry'}:
        if rq == 'unknown':
            reason, health = 'registry_unknown', 'unknown'
        elif rq == 'missing':
            reason, health = 'registry_missing', 'needs_check'
        elif status == 'waiting_retry':
            if rq == 'scheduled':
                due = timestamp(registry.get('scheduled_at'))
                reason = 'cooldown' if due and due > now else 'retry_due'
            elif rq in {'queued', 'deferred'}:
                reason = 'retry_queued'
            else:
                reason, health = 'registry_conflict', 'needs_check'
        elif status == 'running' and rq != 'started' or status == 'queued' and rq not in {'queued', 'deferred', 'scheduled'}:
            reason, health = 'registry_conflict', 'needs_check'
        heartbeat = timestamp(registry.get('heartbeat_at'))
        if status == 'running' and rq == 'started' and heartbeat and now - heartbeat > 900:
            reason, health = 'worker_heartbeat_stale', 'needs_check'
        if status == 'waiting_retry':
            retry_at = registry.get('scheduled_at') if rq == 'scheduled' else None
            if retry_at:
                retry_basis = 'registry'
            if not retry_at and retry.get('retry_scheduled') is True:
                retry_at = _iso_timestamp(timestamp(retry.get('retry_at')))
                if retry_at:
                    retry_basis = 'recorded_request'
    return {
        'db_status': status, 'execution_state': state, 'execution_health': health,
        'retry_at': retry_at, 'retry_at_basis': retry_basis, 'execution_reason_code': reason,
        'execution_reason': error if terminal else sanitize_error_message(retry.get('message')) if status == 'waiting_retry' else None,
        'attempts': {'basis': 'bounded_event_sample', 'events_sampled': len(rows),
                     'provider_requests_sampled': sum(row.get('phase') == 'llm_provider_request' for row in rows),
                     'workflow_retries_sampled': sum(row.get('phase') == 'workflow_retry' for row in rows)},
        'last_progress': {'at': _iso_timestamp(timestamp(progress.get('created_at'))),
                          'current': progress.get('current'), 'total': progress.get('total'),
                          'message': sanitize_error_message(progress.get('message') or progress.get('name'))} if progress else None,
        'registry': registry,
    }


def inspect_job_execution(job, task_queue=None):
    from analysis_job_registry import inspect_job_registries

    job_id = safe_text(job.get('job_id')).strip()
    try:
        events = query_events(job_id, limit=80) if job_id else []
    except Exception:
        events = []
    registry = inspect_job_registries(task_queue, [job]).get(job_id)
    return execution_projection(job, events=events, registry=registry)
