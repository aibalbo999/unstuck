"""Explain current quality counts without changing or diagnosing their gates."""
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from mapping_fields import safe_dict_list
from report_current_quality_item_helpers import blocker_ids


CATEGORIES = {
    'calendar_session_integrity': '交易日／輸入完整性',
    'observation_freshness': '觀測日期／時效',
    'source_evidence_gap': '來源／期間／口徑缺證',
    'consistency_guardrail': '論述與資料一致性攔截',
    'unknown': '待分類核對',
}
_GROUPS = {
    'calendar_session_integrity': {
        'v4_market_session_integrity_invalid', 'v4_market_session_integrity_unverifiable',
        'v4_market_bar_date_mismatch', 'v4_market_observation_future',
        'v4_institutional_observation_future',
        'v4_trade_reason_source_future',
    },
    'observation_freshness': {
        'v4_market_observation_stale', 'v4_market_observation_lag',
        'v4_latest_completed_session_unconfirmed', 'v4_institutional_observation_unaligned',
        'non_fresh_data_trust', 'v4_trade_reason_source_stale',
    },
    'source_evidence_gap': {
        'v4_trade_reason_source_missing', 'market_context_assessment',
        'v4_raw_fcf_period_unverified', 'v4_preserved_quote_fcf_period_unverified',
        'v4_unverified_fcf_as_catalyst', 'v4_institutional_primary_source_unverified',
        'v4_price_adjustment_basis_unknown', 'v4_volume_scope_mismatch',
        'non_approved_evidence_gate', 'missing_price_alignment_inputs',
        'v4_market_observation_missing', 'v4_market_price_missing',
        'v4_trade_reason_source_binding_unverified', 'v4_trade_reason_source_date_unverified',
    },
    'consistency_guardrail': {
        'v4_trade_reason_scope_mismatch', 'v4_event_source_scope_mismatch',
        'explicit_target_price_low_data_confidence', 'v4_bullish_sma_alignment_contradiction',
        'v4_official_raw_price_mismatch', 'v4_market_price_basis_mismatch',
        'recommendation_target_outside_scenario_range', 'hold_recommendation_extreme_target_move',
    },
}


def warning_ids(value):
    gate = value if isinstance(value, dict) else {}
    return {str(item.get('id') or 'unknown') for item in safe_dict_list(gate.get('warnings'))}


def reason_category(code):
    return next((key for key, codes in _GROUPS.items() if code in codes), 'unknown')


def _report_day(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return (stamp.replace(tzinfo=ZoneInfo('Asia/Taipei')) if stamp.tzinfo is None
                else stamp.astimezone(ZoneInfo('Asia/Taipei'))).date()
    except (TypeError, ValueError):
        return None


def explain_quality_population(rows, *, selection_basis, now=None):
    moment = now or datetime.now(ZoneInfo('Asia/Taipei'))
    if moment.tzinfo is None:
        raise ValueError('quality population clock must include a timezone')
    today = moment.astimezone(ZoneInfo('Asia/Taipei')).date()
    cohort = dict.fromkeys(('today', 'older', 'future', 'unknown'), 0)
    pipelines, warnings, categories = Counter(), Counter(), Counter()
    categories_by_cohort = {key: Counter() for key in cohort}
    reasons = {}
    for row in rows:
        day = _report_day(row.get('report_date') or row.get('date'))
        group = 'unknown' if day is None else 'today' if day == today else 'older' if day < today else 'future'
        cohort[group] += 1
        pipelines[str(row.get('pipeline_id') or 'unknown')] += 1
        gate = row.get('content_credibility') or {}
        warning_codes = warning_ids(gate)
        warnings.update(warning_codes)
        codes = blocker_ids(gate) | warning_codes
        present_categories = {reason_category(code) for code in codes}
        categories.update(present_categories)
        categories_by_cohort[group].update(present_categories)
        for code in codes:
            reasons[code] = {'category': reason_category(code), 'root_cause_status': 'not_established_by_reason_code'}
    latest = selection_basis == 'latest_per_ticker_pipeline'
    return {
        'denominator': {
            'unit': 'ticker_pipeline_latest_report' if latest else 'caller_supplied_report',
            'count': len(rows), 'selection_basis': selection_basis,
            'is_today_generation_count': False,
            'explanation': '每個股票與流程的最新版；包含較舊報告，不等於今日生成數或股票檔數。' if latest
                           else '呼叫端提供的報告集合；本函式未自行挑選最新版。',
        },
        'report_date_cohorts': {'timezone': 'Asia/Taipei', 'as_of_date': today.isoformat(),
                                'basis': 'report_date_not_data_observation_date', 'counts': cohort},
        'reports_by_pipeline': dict(sorted(pipelines.items())),
        'content_credibility_warning_counts': dict(sorted(warnings.items())),
        'reason_classification': {
            'schema': 'report_quality_reason_classification.v1',
            'count_unit': 'distinct_report_per_code_or_category', 'counts_may_overlap': True,
            'basis': 'content_credibility_reason_codes', 'does_not_establish_root_cause': True,
            'explanation': '原因可重疊；分類不證明程式錯誤或誤攔，亦不變更品質門檻。',
            'category_labels': CATEGORIES, 'reports_by_category': dict(sorted(categories.items())),
            'reports_by_category_and_cohort': {key: dict(sorted(value.items())) for key, value in categories_by_cohort.items()},
            'reasons': dict(sorted(reasons.items())),
        },
    }
