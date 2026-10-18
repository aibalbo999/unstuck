"""A dated publisher cohort can recover discovery without certifying comparability."""
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def master(day):
    return [
        {"date": day.isoformat(), "stock_id": "5314", "stock_name": "世紀*", "type": "tpex", "industry_category": "其他"},
        {"date": day.isoformat(), "stock_id": "1707", "stock_name": "葡萄王", "type": "twse", "industry_category": "生技醫療業"},
        {"date": day.isoformat(), "stock_id": "3054", "stock_name": "立萬利", "type": "twse", "industry_category": "電子通路業"},
    ]


def page(day, *, target=True, peer_name="葡萄王", title="食品生技"):
    target_row = f'<tr><td><a href="javascript:Link2Stk(\'AS5314\');">5314世紀*</a></td><td>{day:%Y/%m/%d}</td></tr>' if target else ""
    html = f'''<html><head><title>同業股價表現-生技醫療保健-{title}-台股-MoneyDJ理財網</title></head>
    <body><table id="oMainTable"><tr><th>相關公司股價表現 報酬計算日期：{day:%m/%d}</th></tr>
    <tr><td><a href="javascript:Link2Stk('AS1707');">1707{peer_name}</a></td><td>{day:%Y/%m/%d}</td></tr>
    <tr><td><a href="javascript:Link2Stk('AS3054');">3054立萬利</a></td><td>{day:%Y/%m/%d}</td></tr>
    {target_row}</table></body></html>'''
    return html.encode("big5")


def test_broad_exchange_classification_can_still_yield_dated_publisher_candidates():
    from data_fetch.market_sources.moneydj_peer_cohort import parse_cohort_page, is_moneydj_peer_record
    today = date(2026, 10, 4)
    result = parse_cohort_page(page(date(2026, 10, 2)), "5314.TWO", master(today), today=today)
    assert [row["counterparty"]["ticker"] for row in result["records"]] == ["1707.TW", "3054.TW"]
    assert result["records"][0]["business_comparability_verified"] is False
    assert result["records"][0]["numeric_comparability_verified"] is False
    assert is_moneydj_peer_record(result["records"][0], "5314.TWO", today=today)


@pytest.mark.parametrize("raw", [
    page(date(2026, 10, 2), target=False),
    page(date(2026, 9, 1)),
    page(date(2026, 10, 2), peer_name="錯誤公司"),
    page(date(2026, 10, 2), title="其他產業"),
])
def test_wrong_target_stale_identity_or_cohort_fails_closed(raw):
    from data_fetch.market_sources.moneydj_peer_cohort import CohortError, parse_cohort_page
    with pytest.raises(CohortError):
        parse_cohort_page(raw, "5314.TWO", master(date(2026, 10, 4)), today=date(2026, 10, 4))


def test_candidate_cannot_claim_business_or_numeric_comparability():
    from data_fetch.market_sources.moneydj_peer_cohort import parse_cohort_page, is_moneydj_peer_record
    from peer_relationship_evidence import is_reported_peer_record
    today = date(2026, 10, 4)
    row = parse_cohort_page(page(today), "5314.TWO", master(today), today=today)["records"][0]
    assert not is_reported_peer_record(row, "5314.TWO")
    row["business_comparability_verified"] = True
    assert not is_moneydj_peer_record(row, "5314.TWO", today=today)


def test_provider_only_attempts_matching_issuer_and_distinguishes_cache(monkeypatch):
    import time
    from data_fetch.enrichment_search_providers import MoneyDjPublishedPeerCohortProvider
    from data_fetch.market_sources import moneydj_peer_cohort, peer_recovery
    from data_fetch.types import FetchRequest
    import shared_provider_cache

    today = moneydj_peer_cohort._today()
    rows = master(today)
    observation = moneydj_peer_cohort.parse_cohort_page(page(today), "5314.TWO", rows, today=today)
    monkeypatch.setattr(peer_recovery, "load_peer_stock_master", lambda: rows)
    def fetched(*args,diagnostics,**kwargs):
        diagnostics["http_request_sent"]=True
        return observation
    monkeypatch.setattr(moneydj_peer_cohort, "fetch_published_cohort", fetched)
    calls = []

    def shared(_key, callback, **_kwargs):
        if not calls:
            calls.append(callback())
            return calls[0], {"cache_hit": False, "stale": False, "fetched_at_epoch": time.time()}
        return calls[0], {"cache_hit": True, "stale": False, "fetched_at_epoch": time.time()}

    monkeypatch.setattr(shared_provider_cache, "shared_fetch", shared)
    provider = MoneyDjPublishedPeerCohortProvider()
    assert provider.supports(FetchRequest.from_ticker("5314.TWO"))
    assert not provider.supports(FetchRequest.from_ticker("2882.TW"))
    first = provider.fetch(FetchRequest.from_ticker("5314.TWO"))
    second = provider.fetch(FetchRequest.from_ticker("5314.TWO"))
    assert (first.status, first.audit["record_count"], first.audit["http_request_sent"]) == ("success", 2, True)
    assert (second.status, second.audit["record_count"], second.audit["http_request_sent"]) == ("skipped_fresh_cache", 2, False)


def test_merge_accepts_candidate_and_preserves_unverified_scope():
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources.moneydj_peer_cohort import POLICY, parse_cohort_page
    from prompt_evidence import prompt_evidence_copy

    today = date.today()
    candidate = parse_cohort_page(page(today), "5314.TWO", master(today), today=today)["records"][0]
    data = {"ticker": "5314.TWO", "source_audit": [{"source": "peer_discovery",
             "provider": "MoneyDJ published food-biotech cohort", "selection_policy": POLICY,
             "status": "success", "record_count": 1}],
            "peer_discovery_results": [{"title": "unverified legacy", "link": "https://example.com/old"}]}
    result = _merge_optional_http_bundle(
        data, {"moneydj_peer_discovery": [candidate]}, refreshed_sources=["peer_discovery"],
    )
    assert result["peer_discovery_results"] == [candidate]
    assert result["source_audit"][-1]["status"] == "success"
    assert prompt_evidence_copy(result)["peer_discovery_results"][0]["business_comparability_verified"] is False
    assert result["source_record_archive"][0]["reason"] == "legacy_peer_relationship_unverified"


def test_published_cohort_satisfies_discovery_before_generic_search(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from data_fetch import workflow
    from data_fetch.market_sources.moneydj_peer_cohort import parse_cohort_page
    from data_fetch.types import FetchRequest, ProviderResult

    today = date.today()
    records = parse_cohort_page(page(today), "5314.TWO", master(today), today=today)["records"]
    providers = [SimpleNamespace(source="peer_discovery", name=name) for name in (
        "Alternative Search", "Yahoo Taiwan published industry ranking",
        "MoneyDJ published food-biotech cohort")]
    monkeypatch.setattr(workflow, "collect_optional_providers",
                        lambda *a, **k: (providers, {"peer_discovery": True}))
    monkeypatch.setattr(workflow, "_merge_optional_http_bundle", lambda data, *a, **k: data)
    monkeypatch.setattr(workflow, "finalize_data_trust", lambda data: None)
    monkeypatch.setattr(workflow, "cache_financial_payload", lambda *a: None)
    selected = []
    cohort_available = True

    async def fetch(_request, batch, _context):
        selected.extend(provider.name for provider in batch)
        return [ProviderResult(source="peer_discovery", provider=provider.name,
                status="success" if provider.name.startswith("MoneyDJ") and cohort_available else "unavailable",
                value=records if provider.name.startswith("MoneyDJ") and cohort_available else [],
                audit={"source": "peer_discovery", "provider": provider.name,
                       "status": "success" if provider.name.startswith("MoneyDJ") and cohort_available else "unavailable",
                       "record_count": len(records) if provider.name.startswith("MoneyDJ") and cohort_available else 0})
                for provider in batch]

    monkeypatch.setattr(workflow, "fetch_provider_results", fetch)
    request = FetchRequest.from_ticker("5314.TWO")
    asyncio.run(workflow._run_optional_provider_plan(request, None, {"ticker": "5314.TWO", "source_audit": []}))
    assert selected == ["Yahoo Taiwan published industry ranking", "MoneyDJ published food-biotech cohort"]

    selected.clear()
    cohort_available = False
    asyncio.run(workflow._run_optional_provider_plan(request, None, {"ticker": "5314.TWO", "source_audit": []}))
    assert selected == ["Yahoo Taiwan published industry ranking", "MoneyDJ published food-biotech cohort", "Alternative Search"]


def test_cached_published_candidates_must_still_be_current():
    from data_fetch.market_sources.moneydj_peer_cohort import parse_cohort_page
    from data_fetch.types import ProviderResult
    from data_fetch.workflow import _sufficient_published_peer_candidates

    today = date.today()
    records = parse_cohort_page(page(today), "5314.TWO", master(today), today=today)["records"]
    result = ProviderResult(source="peer_discovery", provider="MoneyDJ published food-biotech cohort",
                            status="skipped_fresh_cache", value=records)
    assert _sufficient_published_peer_candidates([result], "5314.TWO")
    stale = [{**record, "observed_at": "2020-01-01"} for record in records]
    result.value = stale
    assert not _sufficient_published_peer_candidates([result], "5314.TWO")
