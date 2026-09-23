"""Capability exclusions and assumed values cannot be reported as acquisitions."""
from source_applicability import source_is_applicable
from report_freshness_summary import safe_bool


def source_freshness_stale(data: dict, source: str) -> bool:
    freshness = data.get('source_freshness', {}) if isinstance(data.get('source_freshness'), dict) else {}
    entry = freshness.get(source, {}) if isinstance(freshness.get(source), dict) else {}
    return safe_bool(entry.get('stale'))


def capability_audit(data, source, provider, status, stale, count, error, message):
    if not source_is_applicable(source, data):
        return provider, 'not_applicable', False, 0, '', '此市場或商品不適用此資料來源。'
    value = data.get(source)
    if source == 'pe_river_chart' and isinstance(value, dict) and value.get('valuation_basis') == 'scenario_assumption':
        return 'scenario assumption', 'degraded_enrichment', stale, 0, '', '估值倍數為情境假設，未取得歷史分位資料。'
    return provider, status, stale, count, error, message
