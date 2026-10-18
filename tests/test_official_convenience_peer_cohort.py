"""Official convenience-store evidence is a candidate lead, not a valuation multiple."""

from datetime import date


TODAY = date(2026, 10, 9)
MASTER = [
    {"stock_id": "2912", "stock_name": "統一超", "type": "twse", "date": "2026-10-09"},
    {"stock_id": "5903", "stock_name": "全家", "type": "tpex", "date": "2026-10-09"},
]


def chain(code, name, *, segment="零售通路"):
    return (f'<h3>個體公司所屬產業鏈</h3><h4><b>{code}&nbsp;{name}</b>所屬產業鏈如下:</h4>'
            f'<h4><span>►</span>&nbsp;<a href="introduce.php?ic=V000">貿易百貨</a>&nbsp;&gt;&nbsp;{segment}</h4>').encode()


def test_official_chain_and_issuer_profiles_yield_only_a_dated_candidate(monkeypatch):
    from data_fetch.market_sources import official_convenience_peer_cohort as cohort

    pages = {
        cohort.CHAIN_URLS["2912"]: chain("2912", "統一超"),
        cohort.CHAIN_URLS["5903"]: chain("5903", "全家"),
        cohort.PROFILE_URLS["2912"]: '<tr><th>公司名稱</th><td>統一超商股份有限公司</td></tr><tr><th>主要業務</th><td>超級商店之經營；煙酒、家庭用品之零售</td></tr>'.encode(),
        cohort.PROFILE_URLS["5903"]: '<tr><td>公司全名</td><td>全家便利商店股份有限公司</td></tr><tr><td>公司代號</td><td>5903</td></tr>'.encode(),
    }
    monkeypatch.setattr(cohort, "sync_get", lambda url, **_kw: type("Response", (), {"content": pages[url]})())
    monkeypatch.setattr(cohort, "shared_fetch", lambda _key, fetch, **_kw: (fetch(), {"stale": False, "cache_hit": False}))

    result = cohort.get_official_convenience_candidates("2912.TW", MASTER, today=TODAY)
    assert result["status"] == "success"
    assert [item["ticker"] for item in result["candidates"]] == ["5903.TWO"]
    candidate = result["candidates"][0]
    assert candidate["business_comparability_verified_current"] is False
    assert candidate["comparison_status"] == "official_convenience_candidate"
    assert candidate["master_observed_at"] == "2026-10-09"
    assert candidate["chain_response_sha256"]["2912"]
    assert candidate["chain_response_sha256"]["5903"]
    assert candidate["profile_response_sha256"]["2912"]
    assert candidate["profile_response_sha256"]["5903"]
    assert cohort.get_official_convenience_candidates("1605.TW", MASTER, today=TODAY)["candidates"] == []


def test_official_candidate_fails_closed_on_changed_chain_profile_or_stock_identity(monkeypatch):
    from data_fetch.market_sources import official_convenience_peer_cohort as cohort

    valid = {
        cohort.CHAIN_URLS["2912"]: chain("2912", "統一超"),
        cohort.CHAIN_URLS["5903"]: chain("5903", "全家"),
        cohort.PROFILE_URLS["2912"]: '<tr><th>公司名稱</th><td>統一超商股份有限公司</td></tr><tr><th>主要業務</th><td>超級商店之經營</td></tr>'.encode(),
        cohort.PROFILE_URLS["5903"]: '<tr><td>公司全名</td><td>全家便利商店股份有限公司</td></tr><tr><td>公司代號</td><td>5903</td></tr>'.encode(),
    }
    monkeypatch.setattr(cohort, "shared_fetch", lambda _key, fetch, **_kw: (fetch(), {"stale": False, "cache_hit": False}))
    for url, bad in (
        (cohort.CHAIN_URLS["2912"], chain("9999", "統一超")),
        (cohort.CHAIN_URLS["5903"], chain("5903", "全家", segment="百貨公司")),
        (cohort.PROFILE_URLS["2912"], '<tr><th>公司名稱</th><td>別家公司</td></tr>'.encode()),
        (cohort.PROFILE_URLS["5903"], '<tr><td>公司代號</td><td>5904</td></tr>'.encode()),
    ):
        pages = {**valid, url: bad}
        monkeypatch.setattr(cohort, "sync_get", lambda request_url, **_kw: type("Response", (), {"content": pages[request_url]})())
        assert cohort.get_official_convenience_candidates("2912.TW", MASTER, today=TODAY)["candidates"] == []
    for rows in (
        [{**MASTER[0], "date": "2026-09-01"}, MASTER[1]],
        [MASTER[0], {**MASTER[1], "stock_name": "別家公司"}],
        [MASTER[0], {**MASTER[1], "type": "twse"}],
        [MASTER[0], MASTER[1], {**MASTER[1], "stock_name": "另一家"}],
    ):
        assert cohort.get_official_convenience_candidates("2912.TW", rows, today=TODAY)["candidates"] == []


def test_candidate_is_attempted_before_coarse_retail_candidates_without_valuation(monkeypatch):
    from data_fetch.market_sources import peers
    from stock_snapshot.peers_valuation import _peer_comparison

    candidate = {"name": "全家", "ticker": "5903.TWO", "comparison_status": "official_convenience_candidate",
                 "business_comparability_verified_current": False}
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: MASTER)
    monkeypatch.setattr(peers, "resolve_legacy_peer_candidates", lambda *_a, **_kw: (
        [{"name": f"零售 {code}", "ticker": f"{code}.TW", "comparison_status": "industry_candidate_only"}
         for code in range(2900, 2912)], {"selection_status": "selected"}))
    monkeypatch.setattr(peers, "get_official_convenience_candidates", lambda *_a, **_kw: {
        "candidates": [candidate], "status": "success"})

    class Stock:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            return {"symbol": self.symbol, "quoteType": "EQUITY", "industry": "Department Stores",
                    "trailingPE": 23.75, "priceToBook": 4.72,
                    "grossMargins": 0.35, "operatingMargins": 0.04, "profitMargins": 0.02,
                    "returnOnEquity": 0.19, "priceToSalesTrailing12Months": 0.8}

    monkeypatch.setattr(peers.yf, "Ticker", Stock)
    monkeypatch.setattr(peers, "_annual_asset_turnover", lambda stock, *, today: (
        {"value": 1.3532, "observed_at": "2025-12-31"} if stock.symbol == "5903.TWO" else None))
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        "2912.TW", "統一超", "Consumer Defensive", "Grocery Stores", {})
    assert result["peers"][0]["ticker"] == "5903.TWO"
    assert result["peers"][0]["pe_ttm"] == 23.75
    assert result["peers"][0]["business_comparability_verified_current"] is False
    assert result["peers"][0]["asset_turnover"] == 1.3532
    assert result["peers"][0]["metrics_status"] == "complete"
    assert result["audit"]["official_convenience_candidate_status"] == "success"
    assert result["audit"]["candidate_attempt_count"] <= 10
    summary = _peer_comparison({"ticker": "2912.TW", "company_name": "統一超",
                                "dynamic_peer_metrics": result["peers"]})["summary"]
    assert summary["peer_count"] == 0
    assert summary["peer_pe_median"] is None


def test_stale_or_corrupt_page_receipt_cannot_supply_a_candidate(monkeypatch):
    from data_fetch.market_sources import official_convenience_peer_cohort as cohort

    for evidence, meta in (
        ({"chain_response_sha256": {"2912": "0" * 64, "5903": "1" * 64},
          "profile_response_sha256": {"2912": "2" * 64, "5903": "3" * 64}}, {"stale": True}),
        ({"chain_response_sha256": {"2912": "not-a-hash"}, "profile_response_sha256": {}},
         {"stale": False}),
    ):
        monkeypatch.setattr(cohort, "shared_fetch", lambda *_a, **_kw: (evidence, meta))
        result = cohort.get_official_convenience_candidates("2912.TW", MASTER, today=TODAY)
        assert result == {"candidates": [], "status": "official_pages_unavailable"}
