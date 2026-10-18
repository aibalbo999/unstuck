"""Merge only fresh, source-backed thermal candidate metrics into a saved report."""
from copy import deepcopy
from datetime import date, datetime
import math
import time
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from data_fetch.market_sources.official_thermal_peer_cohort import TARGET, verified_thermal_candidates
from data_fetch.market_sources.peers import PEER_METRIC_FIELDS


def validate_thermal_refresh_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TARGET or not isinstance(data, dict) or data.get('ticker') != TARGET
            or str(data.get('company_name') or '').split('/')[0].strip() not in {'雙鴻', '雙鴻科技股份有限公司'}
            or instrument_type(data) != 'EQUITY'
            or any(data.get(key) not in (None, '', 'EQUITY') for key in ('instrument_type', 'quoteType', 'quote_type'))
            or not isinstance(data.get('dynamic_peer_metrics'), list)):
        raise HTTPException(status_code=400, detail='此同業來源刷新須有一致的雙鴻股票身分及原指標清單')


def _usable_metrics(record, today):
    available, missing = [], []
    for key in PEER_METRIC_FIELDS:
        number = record.get(key)
        if number is None:
            missing.append(key)
        elif type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError('invalid numeric metric')
        else:
            available.append(key)
    status = 'complete' if not missing else 'partial' if available else 'unavailable'
    if record.get('metrics_status') != status or record.get('missing_metrics') != missing:
        raise ValueError('metric availability mismatch')
    provenance = record.get('metric_sources')
    if not isinstance(provenance, dict) or set(provenance) != set(available):
        raise ValueError('metric provenance missing')
    for field, entry in provenance.items():
        if not isinstance(entry, dict) or not isinstance(entry.get('provider'), str) or not entry['provider']:
            raise ValueError('metric provider missing')
        observed = entry.get('observed_at')
        if observed is not None and date.fromisoformat(observed) > today:
            raise ValueError('future metric observation')
        if field == 'asset_turnover' and (observed is None
                or entry.get('basis') != 'annual_revenue / same_date_year_end_assets'):
            raise ValueError('unverified asset-turnover period')
    return bool(available)


def merge_thermal_peer_source(old_data, old_audits, value, audits, ticker):
    from report_source_refresh import _timestamp, _reassess_original_freshness
    validate_thermal_refresh_context(old_data, ticker)
    today = datetime.now(ZoneInfo('Asia/Taipei')).date()
    try:
        if not verified_thermal_candidates(value, ticker, today=today):
            raise ValueError('thermal membership originals unverified')
        usable = sum(_usable_metrics(row, today) for row in value)
        if usable == 0 or not isinstance(audits, list) or not audits:
            raise ValueError('no acquired metric evidence')
        for audit in audits:
            if (not isinstance(audit, dict) or audit.get('source') != 'dynamic_peer_metrics'
                    or audit.get('provider') != 'FinMind/yfinance' or not audit.get('fetch_id')
                    or audit.get('status') not in {'success', 'degraded_enrichment'}
                    or type(audit.get('record_count')) is not int or audit['record_count'] != usable
                    or type(audit.get('usable_count')) is not int or audit['usable_count'] != usable
                    or audit.get('stale') is not False):
                raise ValueError('metric acquisition audit mismatch')
            stamp = _timestamp(audit)
            if stamp is None or not 0 <= time.time() - stamp < 1800:
                raise ValueError('metric acquisition expired')
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise HTTPException(status_code=502, detail='同業指標、原件或取得憑據未通過核對；原快照保持') from exc
    merged = deepcopy(old_data)
    merged['dynamic_peer_metrics'] = deepcopy(value)
    merged['source_audit'] = [deepcopy(row) for row in old_audits
                              if row.get('source') != 'dynamic_peer_metrics'] + deepcopy(audits)
    _reassess_original_freshness(merged, ticker, 'dynamic_peer_metrics', audits)
    return merged
