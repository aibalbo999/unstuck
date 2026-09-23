import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def test_taiwan_optional_plan_does_not_attempt_sec_or_mark_it_stale():
    from data_fetch.optional_provider_plan import collect_optional_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import FetchRequest

    data = {"ticker": "2330.TW", "quote_type": "EQUITY"}
    _, refresh = collect_optional_providers(FetchRequest.from_ticker("2330.TW"), ProviderRegistry(), data, "2330.TW")
    assert refresh["sec_edgar"] is False
    assert not any(row.get("stale") for row in data.get("source_audit", []) if row["source"] == "sec_edgar")


def test_verified_etf_financial_sources_are_not_applicable_not_failed():
    from data_fetch.audit_policy import _append_full_fetch_audit

    data = {"ticker": "0050.TW", "quote_type": "ETF", "current_price": 70}
    _append_full_fetch_audit(data, "0050.TW", "yfinance", started_at_epoch=100, fetched_at_epoch=101, skip_optional_http=True)
    audits = {row["source"]: row for row in data["source_audit"]}
    assert audits["financial_statements"]["status"] == "not_applicable"
    assert audits["monthly_revenue"]["status"] == "not_applicable"
    assert "financial_statements" not in data["data_trust"]["critical_failures"]


def test_ticker_shape_alone_does_not_exempt_financials():
    from data_fetch.audit_policy import _append_full_fetch_audit

    data = {"ticker": "0050.TW", "current_price": 70}
    _append_full_fetch_audit(data, "0050.TW", "yfinance", started_at_epoch=100, fetched_at_epoch=101, skip_optional_http=True)
    assert next(row for row in data["source_audit"] if row["source"] == "financial_statements")["status"] == "error"


def test_unavailable_etf_analysis_profile_does_not_run_company_valuation():
    from analysis_job_helpers import build_data_fetch_blocking_notice

    result = SimpleNamespace(data={"ticker": "0050.TW", "quote_type": "ETF", "current_price": 70}, data_trust={"status": "fresh"})
    notice = build_data_fetch_blocking_notice(result)
    assert notice is not None
    assert notice["reason_code"] == "instrument_analysis_profile_unavailable"


def test_trust_ignores_inapplicable_sec_observations_but_keeps_news_failure():
    from data_trust import build_data_trust

    data = {"ticker": "2330.TW", "current_price": 100, "source_audit": [
        {"source": "market_data", "status": "success", "record_count": 1},
        {"source": "sec_edgar", "status": "degraded_enrichment", "stale": True},
        {"source": "recent_catalysts", "status": "error", "stale": True},
    ]}
    trust = build_data_trust(data)
    assert not any("sec_edgar" in reason for reason in trust["reason_codes"])
    assert "optional_source_error:recent_catalysts" in trust["reason_codes"]


def test_legacy_optional_path_obeys_market_and_fund_capabilities(monkeypatch):
    import asyncio
    from data_fetch import optional_enrichment as optional
    calls = []
    async def audited(source, provider, *args, **kwargs):
        calls.append((source, provider))
        return {'value': [], 'audit': {'source': source, 'provider': provider, 'status': 'unavailable', 'record_count': 0}}
    monkeypatch.setattr(optional, 'audited_fetch_async', audited)
    monkeypatch.setattr(optional, 'cache_financial_payload', lambda *a: None)
    data = {'ticker': '0050.TW', 'quote_type': 'ETF', 'recent_catalysts': []}
    asyncio.run(optional.enrich_optional_http_async('0050', data))
    assert calls == [('recent_catalysts', 'Alternative Search')]
