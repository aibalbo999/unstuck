"""Source-only security leads retain original claims and every quality gate."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import time
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from data_fetch.market_sources.security_related_peer_cohort import TARGET, SHORT, verified_candidates
from data_fetch.market_sources.peer_recovery import industry_comparability
from thermal_peer_source_refresh import _usable_metrics, _merge_segment_peer_source


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TARGET or not isinstance(data, dict) or data.get('ticker') != TARGET
            or str(data.get('company_name') or '').split('/')[0].strip() not in {SHORT, '中興保全科技股份有限公司'}
            or industry_comparability(data.get('industry'), 'Security & Protection Services') != 'business_industry_matched'
            or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quoteType', 'quote_type'))
            or not isinstance(data.get('dynamic_peer_metrics'), list)):
        raise HTTPException(status_code=400, detail='保全同業來源刷新須有一致的中保科股票身分、業務分類及原指標清單')
    identity = data.get('company_identity')
    if identity is not None:
        if (not isinstance(identity, dict) or identity.get('ticker') not in (None, '', TARGET)
                or (identity.get('stock_id') not in (None, '')
                    and (type(identity['stock_id']) not in (str, int) or str(identity['stock_id']) != '9917'))
                or identity.get('official_name') not in (None, '', SHORT, '中興保全科技股份有限公司')
                or identity.get('instrument_type') not in (None, '', 'EQUITY')):
            raise HTTPException(status_code=400, detail='原公司身分與中保科來源不一致')


def _validate_payload(data, value, audits, ticker):
    from report_source_refresh import _timestamp
    validate_context(data, ticker)
    today = datetime.now(ZoneInfo('Asia/Taipei')).date()
    if not verified_candidates(value, ticker, today=today):
        raise ValueError('security_related_originals_unverified')
    if any(industry_comparability(data['industry'], row.get('reported_industry')) != 'business_industry_matched' for row in value):
        raise ValueError('security_fine_industry_unverified')
    usable = sum(_usable_metrics(row, today) for row in value)
    if not usable or not isinstance(audits, list) or len(audits) != 1:
        raise ValueError('security_metric_observation_missing')
    audit = audits[0]
    if (not isinstance(audit, dict) or audit.get('source') != 'dynamic_peer_metrics'
            or audit.get('provider') != 'FinMind/yfinance' or audit.get('ticker') != ticker
            or not isinstance(audit.get('fetch_id'), str) or not audit['fetch_id']
            or not isinstance(audit.get('operation_id'), str) or not audit['operation_id']
            or type(audit.get('record_count')) is not int or audit['record_count'] != usable
            or type(audit.get('usable_count')) is not int or audit['usable_count'] != usable
            or audit.get('stale') is not False):
        raise ValueError('security_metric_observation_identity_or_count_invalid')
    partial = any(row['metrics_status'] != 'complete' for row in value)
    if (audit.get('coverage_status') != ('partial' if partial else 'success')
            or audit.get('quality_status') != ('partial_metrics' if partial else 'usable')
            or audit.get('status') != ('degraded_enrichment' if partial else 'success')):
        raise ValueError('security_metric_observation_quality_invalid')
    stamp = _timestamp(audit)
    if stamp is None or not 0 <= time.time() - stamp < 1800:
        raise ValueError('security_metric_observation_expired')
    if not verified_candidates(value, ticker, today=today):
        raise ValueError('security_originals_expired_during_validation')


def guard_result(result, data, ticker):
    validate_context(data, ticker)
    try:
        if (result.source != 'dynamic_peer_metrics' or result.provider != 'FinMind/yfinance'
                or not isinstance(result.audit, dict) or result.status != result.audit.get('status')):
            raise ValueError('security_metric_result_identity_invalid')
        _validate_payload(data, result.value, [result.audit], ticker)
    except (ValueError, TypeError, KeyError, OverflowError):
        audit = deepcopy(result.audit) if isinstance(result.audit, dict) else {}
        audit.update(source='dynamic_peer_metrics', status='error', record_count=0, usable_count=0,
            error_kind='security_peer_source_unverified', message='保全相關公司原件、指標或憑據未通過核對；保留原快照。')
        return replace(result, status='error', value=[], audit=audit)
    return result


def merge_source(old_data, old_audits, value, audits, ticker):
    validate_context(old_data, ticker)
    try:
        _validate_payload(old_data, value, audits, ticker)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise HTTPException(status_code=502, detail='保全相關公司原件、指標或憑據未通過核對；原快照保持') from exc
    return _merge_segment_peer_source(old_data, old_audits, value, audits, ticker,
        validate_context=validate_context, verify_candidates=verified_candidates)
