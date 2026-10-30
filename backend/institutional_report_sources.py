"""Lossless source selection for saved institutional diagnostics.

Only absent/None records permit fallback. Invalid records remain visible. A
receipt's bytes/time are never borrowed from a different source slot, and a
same-session failure cannot be cleared by retained success metadata.
"""
from datetime import date, datetime

from mapping_fields import safe_mapping_dict


FAILURES = frozenset({'unavailable', 'failed', 'failure', 'error', 'blocked', 'timeout', 'cooldown'})


def day(value):
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) else None
    except ValueError:
        return None


def aware_time(value):
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
        return parsed if parsed and parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def failure_details(record):
    """Shared by SDK, recovery, latest and identity/request validation."""
    issues = []
    values = {}
    for key in ('status', 'error_kind'):
        raw = record.get(key)
        if raw is None:
            values[key] = ''
        elif not isinstance(raw, str):
            values[key] = ''
            issues.append(key + '_invalid')
        else:
            values[key] = raw.strip()
    return {**values, 'failed': bool(values['error_kind'] or values['status'].lower() in FAILURES),
            'issues': issues}


def _slot(name, raw, kind):
    if raw is None:
        return {'name': name, 'presence': 'absent', 'record': {}, 'outcome': 'absent', 'issues': []}
    record = safe_mapping_dict(raw)
    if not record:
        return {'name': name, 'presence': 'invalid', 'record': {}, 'outcome': 'unknown',
                'issues': [name + '_record_invalid']}
    details = failure_details(record)
    issues = [name + '_' + reason for reason in details['issues']]
    status = details['status'].lower()
    if kind == 'sdk':
        query = safe_mapping_dict(record.get('query')) or {}
        if not day(query.get('start_date')) or not day(query.get('end_date')):
            issues.append(name + '_query_dates_missing')
    if details['failed']:
        outcome = 'failed'
    else:
        valid_status = status == 'archived' if kind == 'sdk' else status in {'available', 'valid_empty', 'security_absent'} if kind == 'current' else status in {'', 'available', 'archived'}
        if not valid_status:
            issues.append(name + '_status_unknown')
        receipt = record if kind == 'sdk' else safe_mapping_dict(record.get('raw_evidence')) or {}
        if receipt.get('status') != 'archived' or (kind != 'sdk' and receipt.get('http_status') != 200):
            issues.append(name + '_receipt_unconfirmed')
        if not aware_time(receipt.get('retrieved_at')):
            issues.append(name + '_retrieval_time_missing')
        outcome = 'observed'
    return {**details, 'name': name, 'presence': 'present', 'record': record,
            'outcome': 'unknown' if issues else outcome, 'issues': issues}


def attempt_diagnostics(audit, target):
    """An attempt's session comes from attempt metadata, never retained bytes."""
    raw = audit.get('primary_acquisition')
    meta = safe_mapping_dict(raw)
    issues = ['primary_attempt_record_invalid'] if raw is not None and meta is None else []
    meta = meta or {}
    details = [failure_details(meta), failure_details({'status': audit.get('retrieval_status'), 'error_kind': audit.get('error_kind')})]
    issues.extend('primary_attempt_' + issue for detail in details for issue in detail['issues'])
    failed = any(detail['failed'] for detail in details)
    recorded_days = []
    for record in (meta, audit):
        scope = safe_mapping_dict(record.get('acquisition_scope')) or {}
        for value in (record.get('expected_completed_session'), scope.get('latest_completed_session')):
            if value is not None:
                parsed = day(value)
                if not parsed:
                    issues.append('primary_attempt_session_invalid')
                else:
                    recorded_days.append(parsed)
    if len(set(recorded_days)) > 1:
        issues.append('primary_attempt_session_conflict')
    if failed and not recorded_days:
        issues.append('primary_attempt_session_missing')
    session = recorded_days[0] if recorded_days and not issues else None
    errors = list(dict.fromkeys(detail['error_kind'] for detail in details if detail['error_kind']))
    return {'origin': 'primary_attempt', 'outcome': 'unknown' if issues else 'failed' if failed else 'not_recorded',
            'failed': failed, 'session': session, 'scope': 'current' if session == target and target else 'historical' if session else 'unknown',
            'status': next((detail['status'] for detail in details if detail['status'].lower() in FAILURES), ''),
            'error_kind': errors[0] if errors else '', 'error_kinds': errors, 'issues': list(dict.fromkeys(issues))}


def collect_saved_sources(inst, audit, target):
    """Preserve field shape before mapping conversion or choosing fallbacks."""
    primary = _slot('primary', inst.get('source_provenance'), 'sdk')
    archive_raw = inst.get('_source_record_archive')
    wrapper = safe_mapping_dict(archive_raw)
    archive = _slot('archive', (wrapper or {}).get('primary_sdk'), 'sdk')
    structural = []
    if archive_raw is not None and (wrapper is None or 'primary_sdk' not in wrapper):
        structural.append('archive_container_invalid')
        archive = _slot('archive', {}, 'sdk')
    # An invalid or failed direct record is never replaced by the archive.
    selected = primary if primary['presence'] != 'absent' else archive
    latest = _slot('latest', inst.get('latest_official_observation'), 'latest')
    recovery_raw = inst.get('official_recovery')
    if recovery_raw is None:
        recovery_raw = audit.get('official_recovery')
    recovery = safe_mapping_dict(recovery_raw)
    if recovery_raw is not None and not recovery:
        structural.append('official_recovery_invalid')
    recovery = recovery or {}
    reports = recovery.get('reports')
    matching = []
    if reports is not None:
        if not isinstance(reports, (list, tuple)):
            structural.append('official_reports_invalid')
        else:
            for raw in reports:
                row = safe_mapping_dict(raw)
                if not row or not day(row.get('date')):
                    structural.append('official_report_identity_missing')
                elif row.get('date') == target:
                    matching.append(_slot('current', raw, 'current'))
    if len(matching) > 1:
        structural.append('current_receipts_ambiguous')
    current = matching[0] if matching else _slot('current', None, 'current')
    slots = {'primary': primary, 'archive': archive, 'current': current, 'latest': latest}
    attempt = attempt_diagnostics(audit, target)
    issues = structural + [issue for slot in slots.values() for issue in slot['issues']] + attempt['issues']
    return {'slots': slots, 'selected_sdk': selected, 'recovery': recovery,
            'issues': list(dict.fromkeys(issues)), 'current_receipts': matching, 'attempt': attempt}


def sdk_covers(record, target):
    query = safe_mapping_dict(record.get('query')) or {}
    start, end = day(query.get('start_date')), day(query.get('end_date'))
    return bool(target and start and end and start <= target <= end)


def source_diagnostics(sources):
    """Small per-slot provenance ledger; does not share input containers."""
    result = []
    entries = list(sources['slots'].items()) + [(f'current[{index}]', slot) for index, slot in enumerate(sources['current_receipts'][1:], 1)]
    for name, slot in entries:
        row = slot['record']
        receipt = row if name in {'primary', 'archive'} else safe_mapping_dict(row.get('raw_evidence')) or {}
        details = failure_details(row)
        result.append({'origin': name, 'presence': slot['presence'], 'outcome': slot['outcome'],
                       'status': details['status'], 'error_kind': details['error_kind'],
                       'date': day(row.get('date')), 'retrieved_at': receipt.get('retrieved_at') if isinstance(receipt.get('retrieved_at'), str) else None,
                       'source_url': row.get('source_url') if isinstance(row.get('source_url'), str) else None,
                       'issues': list(slot['issues'])})
    return result
