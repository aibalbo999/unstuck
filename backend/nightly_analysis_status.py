"""Read-only morning readiness from new jobs, artifacts and current quality."""
from datetime import date, datetime, timedelta
from nightly_analysis_policy import TZ, START, enabled, delivery_session, session_for_acquisition, source_readiness
import nightly_analysis_store as store


def assess_report(work, job, snapshot, projected):
    reasons = []
    if job.get('status') != 'done' or not job.get('filename'):
        return {'ready': False, 'reasons': ['new_analysis_not_done']}
    if not snapshot or not projected:
        return {'ready': False, 'reasons': ['artifact_or_current_quality_missing']}
    data = snapshot.get('data') or {}
    if data.get('nightly_analysis', {}).get('job_id') != work['job_id']:
        reasons.append('report_not_bound_to_nightly_job')
    if data.get('nightly_analysis', {}).get('session_date') != work['session_date']:
        reasons.append('report_session_mismatch')
    from report_publication_identity import publication_identity
    identity = publication_identity(snapshot)
    if identity['kind'] != 'forecast' or not identity['prediction_eligible']:
        reasons.append('not_new_complete_forecast')
    completeness = projected.get('analysis_completeness') or {}
    if (completeness.get('status') not in {'complete', 'observation', 'quality_warning'}
            or completeness.get('quality_recorded') is not True
            or completeness.get('basis') != 'source_assessment'
            or completeness.get('source_status') not in {'source_bound', 'observation'}):
        reasons.append('analysis_degraded_or_incomplete')
    integrity = projected.get('snapshot_integrity') or {}
    if integrity.get('valid') is not True or integrity.get('status') in {'invalid', 'failed', 'blocked'}:
        reasons.append('snapshot_integrity_unverified')
    if projected.get('analysis_text_stale') or projected.get('decision_freshness', {}).get('status') == 'needs_rerun':
        reasons.append('analysis_text_stale')
    for key in ('report_conformance', 'content_credibility'):
        if projected.get(key, {}).get('status') not in {'passed', 'warning'}:
            reasons.append(key + '_blocked_or_unknown')
    if projected.get('evidence_exit_gate', {}).get('verdict') not in {'approved', 'caution'}:
        reasons.append('evidence_rejected_or_unknown')
    if projected.get('decision_freshness', {}).get('requires_rerun') or snapshot.get('refreshed_without_analysis_rerun'):
        reasons.append('analysis_stale_after_refresh')
    sources = source_readiness(data, work['session_date'], work['ticker'])
    reasons += sources['reason_codes']
    return {'ready': not reasons, 'reasons': reasons, 'source_evidence': sources,
            'meaning': 'completed new research with no current blocking quality issue;not a trade recommendation or validated return'}


def read_status(output_dir, session=None, now=None):
    from job_store import get_job
    from report_artifacts import ReportArtifactLocator
    from report_history_storage import storage_for_existing_output_dir
    from report_index import query_report_metadata
    now = now or datetime.now(TZ)
    session = session or session_for_acquisition(now) or delivery_session(now)
    date.fromisoformat(session)
    rows = store.read_rows(session)
    storage = storage_for_existing_output_dir(output_dir, None)
    locator = ReportArtifactLocator(storage) if storage else None
    items = []
    for row in rows:
        job = get_job(row['job_id'])
        snapshot = projected = None
        if job.get('status') == 'done' and locator:
            try:
                bundle = locator.require_bundle(job['filename'])
                snapshot = bundle.read_data_snapshot()
                reports, _ = query_report_metadata(page=1, limit=5, q=job['filename'],
                    pipeline=row['pipeline'], recommendation='all', data_trust='all',
                    include_versions=True, output_dir=output_dir, sync_metadata=False)
                projected = next((r for r in reports if r['filename'] == job['filename']), None)
            except (OSError, ValueError, KeyError):
                pass
        assessment = assess_report(row, job, snapshot, projected)
        items.append({k: row[k] for k in ('job_id','session_date','ticker','pipeline','state','attempts','last_error')} | {
            'job_status': job.get('status'), 'filename': job.get('filename'), **assessment})
    next_start = datetime.combine(now.astimezone(TZ).date(), START, TZ)
    if now >= next_start:
        next_start += timedelta(days=1)
    return {'schema_version': 'nightly-analysis-status.v1', 'enabled': enabled(), 'checked_at': now.isoformat(),
            'session_date': session, 'delivery_date': (date.fromisoformat(session)+timedelta(days=1)).isoformat(),
            'scope_count': len(rows), 'ready_count': sum(i['ready'] for i in items),
            'ready': bool(items) and all(i['ready'] for i in items), 'items': items,
            'next_clock_check': next_start.isoformat(), 'start_time': '22:35 Asia/Taipei',
            'source_recheck_boundary': '22:30 Asia/Taipei;internal policy,not exchange SLA',
            'acquisition_end_time': '07:00 next calendar day',
            'empty_scope_meaning': 'not started, closed/unknown session, or no enabled scheduled Taiwan items;not proof of readiness',
            'legacy76_touched': False}
