"""Undated TPEx steel-wire membership is a lead, never a valuation peer claim."""

from datetime import date


TODAY = date(2026, 10, 9)
MASTER = [
    {"stock_id": "1605", "stock_name": "華新", "type": "twse", "date": "2026-10-09"},
    {"stock_id": "2024", "stock_name": "志聯", "type": "twse", "date": "2026-10-09"},
    {"stock_id": "2033", "stock_name": "佳大", "type": "twse", "date": "2026-10-09"},
    {"stock_id": "5016", "stock_name": "松和", "type": "tpex", "date": "2026-10-09"},
]


def _pages():
    from data_fetch.market_sources import official_steel_wire_peer_cohort as cohort

    links = ''.join(f'<a href="company_basic.php?stk_code={code}" title="{name}">{name}</a>'
                    for code, name in (("1605", "華新"), ("2024", "志聯"), ("2033", "佳大"), ("5016", "松和")))
    return {
        cohort.ISSUER_URL: ('<h3>個體公司所屬產業鏈</h3><h4><b>1605&nbsp;華新</b>所屬產業鏈如下:</h4>'
                            '<h4><span>►</span>&nbsp;<a href="introduce.php?ic=Q000">鋼鐵</a>&nbsp;&gt;&nbsp;鋼線鋼纜</h4>').encode(),
        cohort.SEGMENT_URL: f'<div id="companyList_QJ00" title="鋼線鋼纜"><div class="company-list"><b>鋼線鋼纜</b>{links}</div></div>'.encode(),
    }


def test_official_segment_yields_only_current_verified_stock_identities(monkeypatch):
    from data_fetch.market_sources import official_steel_wire_peer_cohort as cohort

    pages = _pages()
    monkeypatch.setattr(cohort, "sync_get", lambda url, **_kw: type("Response", (), {"content": pages[url]})())
    monkeypatch.setattr(cohort, "shared_fetch", lambda _key, fetch, **_kw: (fetch(), {"stale": False, "cache_hit": False}))
    result = cohort.get_official_steel_wire_candidates("1605.TW", MASTER, today=TODAY)
    assert result["status"] == "success"
    assert [row["ticker"] for row in result["candidates"]] == ["2024.TW", "2033.TW", "5016.TWO"]
    assert all(row["business_comparability_verified_current"] is False for row in result["candidates"])
    assert all(row["master_observed_at"] == "2026-10-09" for row in result["candidates"])
    assert all(row["issuer_response_sha256"] and row["segment_response_sha256"] for row in result["candidates"])


def test_changed_segment_or_stale_stock_identity_does_not_supply_peer(monkeypatch):
    from data_fetch.market_sources import official_steel_wire_peer_cohort as cohort

    base = _pages()
    monkeypatch.setattr(cohort, "shared_fetch", lambda _key, fetch, **_kw: (fetch(), {"stale": False, "cache_hit": False}))
    for url, replacement in (
        (cohort.ISSUER_URL, base[cohort.ISSUER_URL].replace(b"Q000", b"V000")),
        (cohort.SEGMENT_URL, base[cohort.SEGMENT_URL].replace(b"QJ00", b"QK00")),
        (cohort.SEGMENT_URL, base[cohort.SEGMENT_URL].replace(b"5016", b"9999")),
    ):
        pages = {**base, url: replacement}
        monkeypatch.setattr(cohort, "sync_get", lambda request_url, **_kw: type("Response", (), {"content": pages[request_url]})())
        assert cohort.get_official_steel_wire_candidates("1605.TW", MASTER, today=TODAY)["candidates"] == []
    monkeypatch.setattr(cohort, "sync_get", lambda url, **_kw: type("Response", (), {"content": base[url]})())
    for rows in (
        [{**MASTER[0], "date": "2026-09-01"}, *MASTER[1:]],
        [MASTER[0], {**MASTER[1], "stock_name": "別家公司"}, *MASTER[2:]],
    ):
        result = cohort.get_official_steel_wire_candidates("1605.TW", rows, today=TODAY)
        assert result["candidates"] == []


def test_matching_desktop_and_mobile_segment_panels_are_accepted():
    from data_fetch.market_sources.official_steel_wire_peer_cohort import _segment_has_exact_cohort, SEGMENT_URL

    segment = _pages()[SEGMENT_URL]
    duplicate = segment.replace("<b>鋼線鋼纜</b>".encode(), b"")
    assert _segment_has_exact_cohort(duplicate + segment)
    assert not _segment_has_exact_cohort(duplicate + duplicate)


def test_segment_candidates_can_complete_metrics_without_automatic_valuation(monkeypatch):
    from data_fetch.market_sources import peers
    from stock_snapshot.peers_valuation import _peer_comparison

    candidates = [{"name": name, "ticker": symbol, "comparison_status": "official_segment_candidate",
                   "business_comparability_verified_current": False}
                  for name, symbol in (("志聯", "2024.TW"), ("佳大", "2033.TW"), ("松和", "5016.TWO"))]
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: MASTER)
    monkeypatch.setattr(peers, "resolve_legacy_peer_candidates", lambda *_a, **_kw: (
        [{"name": f"錯誤同業 {code}", "ticker": f"{code}.TW", "comparison_status": "industry_candidate_only"}
         for code in range(1606, 1618)], {"selection_status": "selected"}))
    monkeypatch.setattr(peers, "get_official_steel_wire_candidates", lambda *_a, **_kw: {
        "candidates": candidates, "status": "success"})

    class Stock:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            return {"symbol": self.symbol, "quoteType": "EQUITY", "industry": "Steel",
                    "trailingPE": 18.0, "priceToBook": 1.2, "priceToSalesTrailing12Months": 1.1,
                    "grossMargins": 0.15, "operatingMargins": 0.08,
                    "profitMargins": 0.07, "returnOnEquity": 0.12}

    monkeypatch.setattr(peers.yf, "Ticker", Stock)
    monkeypatch.setattr(peers, "_annual_asset_turnover", lambda stock, *, today: (
        {"value": 0.8, "observed_at": "2025-12-31"} if stock.symbol in {"2024.TW", "2033.TW", "5016.TWO"} else None))
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        "1605.TW", "華新", "Industrials", "Copper", {})
    assert [row["ticker"] for row in result["peers"]] == ["2024.TW", "2033.TW", "5016.TWO"]
    assert result["audit"]["coverage_status"] == "success"
    assert result["audit"]["candidate_attempt_count"] <= 10
    assert result["audit"]["official_steel_wire_candidate_status"] == "success"
    assert _peer_comparison({"ticker": "1605.TW", "company_name": "華新",
                             "dynamic_peer_metrics": result["peers"]})["summary"]["peer_count"] == 0
