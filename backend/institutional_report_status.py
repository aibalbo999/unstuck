"""View-only institutional acquisition diagnosis from a saved report.

No provider calls, calendar lookups, admission recomputation or wall-clock upgrade.
The target is the saved price session, not the civil date on which a user opens it.
Evidence presence describes the saved record; it does not verify source bytes.
"""
from datetime import date, datetime

from mapping_fields import safe_mapping_dict
from market_evidence_policy import RECHECK_TIME, TZ, acquisition_phase
from institutional_report_identity import bind_saved_identity
from institutional_report_sources import collect_saved_sources, failure_details, sdk_covers, source_diagnostics


def _map(value):
    return safe_mapping_dict(value) or {}


def _text(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def _day(value):
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) else None
    except ValueError:
        return None


def _time(value):
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
        return parsed.astimezone(TZ) if parsed and parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _stamp(value):
    parsed = _time(value)
    return parsed.isoformat() if parsed else None


def _rows(value):
    return [_map(row) for row in value if _map(row)] if isinstance(value, (list, tuple)) else []


_DESCRIPTIONS = {
    'query_blocked': ('查詢受阻／未完成', '此行情交易日的查詢記錄為失敗或不可用；保留的舊回應不能當作本次成功查詢。冷卻或逾時的細項以保存證據為準。'),
    'no_current_rows': ('查詢成功，保存結果無當日列', '保存的查詢涵蓋行情交易日，但該次回應無當日列；不能證明官方尚未發布，也不能推定零交易。'),
    'cached_no_current_rows': ('沿用無當日列的快取回應', '此處沿用先前無當日列的快取，未證明本次重新查詢成功；不能證明官方尚未發布。'),
    'security_absent': ('回應未列此證券', '保存的當日回應未列此證券；不推定零交易、停牌或官方尚未發布。'),
    'query_window_mismatch': ('查詢範圍未涵蓋行情交易日', '保存的查詢起迄範圍未涵蓋行情交易日，且未記錄該日官方查詢；應查核日期規劃，不能解釋成等待發布。'),
    'available_provisional': ('已有當日列，未達內部採用條件', '保存資料已有行情交易日的法人列，但原始取得時間早於內部重查界線；報告晚存或現在已過界線都不會升級舊回應。'),
    'available_requires_verification': ('已有當日列，仍待來源核驗', '日期對齊不等於已通過來源或品質核驗；採用狀態仍依既有 gate。'),
    'recorded_admission_passed': ('保存的來源採用檢查通過', '此為保存的來源採用結果，不代表目前重新核驗或可執行交易。'),
    'cache_expired': ('擷取快取在保存檢查時已失效', '保存的新鮮度記錄顯示擷取快取失效；保留原取得時間，不把快取讀取當成新的來源回應。'),
    'evidence_time_conflict': ('證據時間超出快照邊界', '取得時間晚於保存的資料截止時間，不能用來證明較早分析時已可取得。'),
    'insufficient_evidence': ('保存證據不足以判斷', '缺少可對應市場、行情交易日或查詢結果的保存證據；不猜測發布時間或查詢原因。'),
}


def build_institutional_report_status(context):
    """Return independent acquisition/admission/snapshot states; never mutate input."""
    context = _map(context)
    data = _map(context.get('data'))
    inst = _map(data.get('institutional_trading'))
    if not inst:
        return {}
    target = _day(_map(data.get('daily_market_data')).get('as_of'))
    observed = _day(inst.get('latest_date'))
    audits = _rows(data.get('source_audit') or context.get('source_audit'))
    audit = next((row for row in reversed(audits) if row.get('source') == 'institutional_trading'), {})
    primary = _map(audit.get('primary_acquisition'))
    sources = collect_saved_sources(inst, audit, target)
    slots = sources['slots']
    selected_sdk = sources['selected_sdk']
    provenance = selected_sdk['record']
    query = _map(provenance.get('query'))
    query_start = _day(query.get('start_date'))
    query_end = _day(query.get('end_date'))
    recovery = sources['recovery']
    current = slots['current']['record']
    proof = _map(current.get('raw_evidence'))
    official = slots['latest']['record']
    binding = bind_saved_identity(context, data, inst, audit, primary, sources, target)
    ticker, market = binding['ticker'], binding['market']
    latest_proof = _map(official.get('raw_evidence')) if official.get('date') == target else {}
    official_failures = [slots[name] for name in ('current', 'latest')
                         if binding[name + '_bound'] and slots[name]['outcome'] == 'failed']
    # Failure is preserved across both official slots. Prefer a recorded error
    # for the concise notice; the ledger below retains every slot and outcome.
    official_slot = (next((slot for slot in official_failures if failure_details(slot['record'])['error_kind']), official_failures[0])
                     if official_failures else slots['current'] if slots['current']['presence'] != 'absent' else slots['latest'])
    official_evidence = official_slot['record']
    official_proof = _map(official_evidence.get('raw_evidence'))
    primary_at = _stamp(provenance.get('retrieved_at'))
    official_at = _stamp(official_proof.get('retrieved_at'))
    current_at = _stamp(proof.get('retrieved_at'))
    refreshed_at = _stamp(context.get('snapshot_refreshed_at'))
    saved_at = _stamp(context.get('generated_at'))
    cutoff = refreshed_at or _stamp(data.get('analysis_input_cutoff')) or saved_at
    limitations = list(binding['limitations'])
    wrong_primary_window = bool(target and ((query_end and query_end < target) or (query_start and query_start > target)
                                            or (query_start and query_end and query_start > query_end)))
    if wrong_primary_window:
        limitations.append('primary_query_window_mismatch')
    if not primary_at:
        limitations.append('primary_raw_retrieval_time_missing')
    if not cutoff:
        limitations.append('snapshot_time_boundary_missing')
    ledger = source_diagnostics(sources)
    receipt_times = [_stamp(row['retrieved_at']) for row in ledger]
    time_conflict = bool(cutoff and any(_time(stamp) > _time(cutoff) for stamp in receipt_times if stamp))
    if time_conflict:
        limitations.append('receipt_after_snapshot_cutoff')
    error = failure_details(official_evidence)['error_kind']
    sdk_failures = [slots[name] for name in ('primary', 'archive') if binding['sdk_bounds'][name]
                    and sdk_covers(slots[name]['record'], target) and slots[name]['outcome'] == 'failed']
    attempt = sources['attempt']
    meta_failed = bool(binding['attempt_bound'] and attempt['failed'])
    primary_error = attempt['error_kind']
    if not primary_error:
        primary_error = next((failure_details(slot['record'])['error_kind'] for slot in sdk_failures if failure_details(slot['record'])['error_kind']), '')
    primary_failure_status = attempt['status'] or (failure_details(sdk_failures[0]['record'])['status'] if sdk_failures else '')
    blocked = bool(official_failures or sdk_failures or meta_failed)
    cached = official_evidence.get('cache_hit') is True
    dated_response = bool(binding['current_bound'] and current_at and slots['current']['outcome'] == 'observed')
    primary_response = bool(binding['primary_bound'] and selected_sdk['outcome'] == 'observed'
                            and primary_at and sdk_covers(provenance, target) and not meta_failed)
    latest_response = bool(binding['latest_bound'] and slots['latest']['outcome'] == 'observed')
    current_rows = primary_response or (dated_response and current.get('status') == 'available') or latest_response
    # Failure wins over retained raw bytes and over a successful SDK fallback.
    if binding['invalid']:
        query_status = 'unknown'
    elif blocked:
        query_status = 'query_blocked'
    elif target and observed == target and current_rows:
        query_status = 'current_rows'
    elif dated_response and current.get('status') == 'valid_empty':
        query_status = 'cached_no_current_rows' if cached else 'no_current_rows'
    elif dated_response and current.get('status') == 'security_absent':
        query_status = 'security_absent'
    elif binding['primary_bound'] and wrong_primary_window and not current:
        query_status = 'query_window_mismatch'
    elif primary_response and observed and observed < target:
        query_status = 'cached_no_current_rows' if primary.get('cache_hit') is True else 'no_current_rows'
    else:
        query_status = 'unknown'
    freshness = _map(_map(data.get('source_freshness') or context.get('source_freshness')).get('institutional_trading'))
    # Generic stale/is_fresh also includes pre-cutoff admission. Only fetch age
    # or the original cache receipt can establish an expired acquisition cache.
    expired = freshness.get('fetch_is_fresh') is False or primary.get('stale') is True or current.get('stale') is True
    cache_status = 'expired' if expired else 'reused' if cached or primary.get('cache_hit') is True else 'not_recorded_as_reused'
    admission = _map(inst.get('latest_session_admission'))
    admitted = admission.get('eligible') is True
    provisional = False
    if target and observed == target:
        # An empty official response cannot date current rows supplied by the SDK.
        current_row_receipt = current_at if dated_response and current.get('status') == 'available' else _stamp(latest_proof.get('retrieved_at')) if latest_response else None
        original_at = current_row_receipt or (primary_at if primary_response else None)
        provisional = bool(original_at and acquisition_phase(target, _time(original_at)) == 'provisional')
    if market == 'unknown' or not target or binding['invalid']:
        status = 'insufficient_evidence'
    elif time_conflict:
        status = 'evidence_time_conflict'
    elif query_status == 'query_blocked':
        status = query_status
    elif expired:
        status = 'cache_expired'
    elif query_status == 'current_rows':
        status = 'available_provisional' if provisional else 'recorded_admission_passed' if admitted else 'available_requires_verification'
    else:
        status = query_status if query_status in _DESCRIPTIONS else 'insufficient_evidence'
    if refreshed_at:
        snapshot_status = 'sources_refreshed_without_analysis' if context.get('refreshed_without_analysis_rerun') is True else 'refreshed_snapshot'
    else:
        snapshot_status = 'saved_unrefreshed' if saved_at else 'unknown'
    label, summary = _DESCRIPTIONS[status]
    evidence = {
        'primary_source': _text(inst.get('source')), 'query_start_date': query_start, 'query_end_date': query_end,
        'expected_completed_session': _day(primary.get('expected_completed_session') or audit.get('expected_completed_session')),
        'official_source': _text(official_evidence.get('source') or official_evidence.get('market') or (recovery.get('provider') if official_slot['name'] == 'current' else None)),
        'official_query_date': _day(official_evidence.get('date')), 'official_result': _text(official_evidence.get('status')),
        'official_error_kind': error, 'primary_error_kind': primary_error,
        'primary_failure_status': primary_failure_status,
        'official_cache_hit': official_evidence.get('cache_hit') if isinstance(official_evidence.get('cache_hit'), bool) else None,
        'official_source_url': _text(official_evidence.get('source_url') or official_proof.get('source_url')),
        'raw_response_sha256': _text(official_proof.get('raw_response_sha256')),
        'raw_evidence_scope': 'saved_metadata_only; original bytes not reverified by this projection',
    }
    return {
        'schema_version': 1, 'status': status, 'label': label, 'summary': summary,
        'query_status': query_status, 'cache_status': cache_status, 'snapshot_status': snapshot_status,
        'ticker': ticker, 'market': market, 'price_date': target, 'institutional_date': observed,
        'primary_retrieved_at': primary_at, 'official_retrieved_at': official_at,
        'price_retrieved_at': _stamp(data.get('market_data_fetched_at') or _map(_map(data.get('source_freshness')).get('market_data')).get('fetched_at')),
        'analysis_input_cutoff': _stamp(data.get('analysis_input_cutoff')), 'report_saved_at': saved_at,
        'snapshot_refreshed_at': refreshed_at, 'conclusion_generated_at': _stamp(context.get('conclusion_generated_at')),
        'recorded_admission_eligible': admitted, 'recorded_admission_reason': _text(admission.get('reason')),
        'official_publication_status': 'unknown', 'limitations': limitations, **evidence,
        'identity_binding': 'unknown' if binding['invalid'] else 'bound_saved_metadata',
        'identity_limitations': binding['limitations'],
        'primary_evidence_origin': selected_sdk['name'] if selected_sdk['presence'] != 'absent' else None,
        'official_evidence_origin': official_slot['name'] if official_slot['presence'] != 'absent' else None,
        'source_records': ledger,
        'primary_attempt': attempt,
        'policy_note': f'{RECHECK_TIME.isoformat(timespec="minutes")}（Asia/Taipei）為內部保守重查界線，非官方發布 SLA；時間經過不會自動升級保存資料。',
    }


def institutional_status_checks(status):
    """One set of labels for HTML UI and Markdown summary/download."""
    if not status:
        return []

    def clock(key):
        value = status.get(key)
        parsed = _time(value)
        return parsed.strftime('%Y-%m-%d %H:%M:%S') + ' +08:00' if parsed else '未記錄／時區未確認'

    snapshot_label = {
        'saved_unrefreshed': '保存快照，未記錄來源刷新；此頁沒有重新查詢來源',
        'sources_refreshed_without_analysis': '來源快照曾刷新，原分析未重跑',
        'refreshed_snapshot': '快照記錄有刷新時間；分析是否重跑須另核',
        'unknown': '保存或刷新時間未確認',
    }[status['snapshot_status']]
    cache_label = {'expired': '已失效', 'reused': '沿用快取', 'not_recorded_as_reused': '未記錄沿用快取'}[status['cache_status']]
    identity_note = ('；身分綁定未確認：' + '、'.join(status['identity_limitations'])) if status['identity_binding'] == 'unknown' else ''
    return [
        ('法人資料狀態', f"{status['label']}；{status['summary']}"),
        ('行情／法人日期', f"{status['market']}；行情 {status['price_date'] or '未記錄'}；法人 {status['institutional_date'] or '未記錄'}"),
        ('原始擷取時間（台北）', f"行情 {clock('price_retrieved_at')}；法人主來源 {clock('primary_retrieved_at')}；法人官方回應 {clock('official_retrieved_at')}（快取命中不代表重新擷取）"),
        ('報告保存與刷新（台北）', f"保存 {clock('report_saved_at')}；資料截止 {clock('analysis_input_cutoff')}；來源刷新 {clock('snapshot_refreshed_at')}；{snapshot_label}"),
        ('法人判斷證據', f"主來源 {status['primary_source'] or '未記錄'}；查詢起迄 {status['query_start_date'] or '未記錄'}～{status['query_end_date'] or '未記錄'}；官方 {status['official_source'] or '未記錄'}／{status['official_query_date'] or '未記錄'}／{status['official_result'] or '未記錄'}；錯誤 {status['official_error_kind'] or status['primary_error_kind'] or status['primary_failure_status'] or '未記錄'}；擷取快取 {cache_label}；只解讀保存紀錄，未重驗原件{identity_note}"),
        ('法人採用政策', status['policy_note']),
    ]
