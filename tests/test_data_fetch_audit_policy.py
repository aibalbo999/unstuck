import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_trust import (  # noqa: E402
    AUDIT_STATUS_DEGRADED_ENRICHMENT,
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
)


def test_cache_audit_policy_classifies_fresh_degraded_and_unavailable_sources():
    from data_fetch.audit_policy import _cache_audit_message, _cache_audit_status

    assert _cache_audit_status("market_data", stale=False, record_count=0) == AUDIT_STATUS_SKIPPED_FRESH_CACHE
    assert _cache_audit_status("recent_catalysts", stale=True, record_count=2) == AUDIT_STATUS_DEGRADED_ENRICHMENT
    assert _cache_audit_status("financial_statements", stale=True, record_count=0) == AUDIT_STATUS_UNAVAILABLE

    assert "新鮮度門檻" in _cache_audit_message(stale=False, record_count=0)
    assert "降級補充資料" in _cache_audit_message(stale=True, record_count=2)
    assert "等待重新抓取" in _cache_audit_message(stale=True, record_count=0)


def test_full_fetch_audit_policy_records_success_and_missing_optional_sources():
    from data_fetch.audit_policy import _append_full_fetch_audit

    data = {
        "ticker": "2330.TW",
        "current_price": 100,
        "years": ["2025"],
        "revenue_history": [10],
        "net_income_history": [2],
        "peer_discovery_results": [{"symbol": "2454.TW"}],
    }

    audited = _append_full_fetch_audit(
        data,
        "2330.TW",
        "yfinance",
        started_at_epoch=100.0,
        fetched_at_epoch=101.0,
        skip_optional_http=False,
    )
    entries = {entry["source"]: entry for entry in audited["source_audit"]}

    assert entries["market_data"]["status"] == AUDIT_STATUS_SUCCESS
    assert entries["financial_statements"]["status"] == AUDIT_STATUS_SUCCESS
    assert entries["monthly_revenue"]["status"] == AUDIT_STATUS_UNAVAILABLE
    assert entries["monthly_revenue"]["message"] == "非台股或 FinMind 月營收暫無可用資料"
    assert entries["peer_discovery"]["status"] == AUDIT_STATUS_SUCCESS
    assert audited["data_trust"]["status"] in {"fresh", "partial", "error"}
