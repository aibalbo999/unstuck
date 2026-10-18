"""Exchange-published valuation ratios supplement missing peer quote fields."""

import json
from datetime import date


TODAY = date(2026, 10, 9)


def test_official_valuation_requires_exact_market_code_and_recent_roc_date():
    from data_fetch.market_sources.official_peer_valuation import select_valuation

    roster = {
        "source_url": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
        "response_sha256": "a" * 64,
        "entries": {
            "5314": {"name": "世紀*", "date_roc": "1151008", "pe": "5.86", "pb": "4.39"},
        },
    }
    found = select_valuation(roster, "5314.TWO", today=TODAY)
    assert found["metrics"] == {"pe_ttm": 5.86, "pb": 4.39}
    assert found["observed_at"] == "2026-10-08"
    assert found["source_url"] == roster["source_url"]
    assert select_valuation(roster, "5314.TW", today=TODAY) is None
    assert select_valuation(roster, "5314.TWO", today=date(2026, 10, 17)) is None


def test_official_valuation_rejects_duplicate_codes_and_nonpositive_ratios():
    from data_fetch.market_sources.official_peer_valuation import parse_roster, select_valuation

    url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    row = {"Date": "1151008", "Code": "2330", "Name": "台積電", "PEratio": "0", "PBratio": "10.42"}
    roster = parse_roster(json.dumps([row]).encode(), ".TW")
    assert select_valuation(roster, "2330.TW", today=TODAY)["metrics"] == {"pb": 10.42}
    try:
        parse_roster(json.dumps([row, row]).encode(), ".TW")
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        assert False, "duplicate stock observations must be rejected"


def test_official_valuation_market_roster_is_shared_and_stale_cache_is_not_used(monkeypatch):
    from data_fetch.market_sources import official_peer_valuation as values

    calls = []
    def fake_shared(key, fetch, **kwargs):
        calls.append((key, kwargs))
        roster = {"source_url": values.URLS[".TWO"], "response_sha256": "b" * 64,
                  "entries": {"5314": {"name": "世紀*", "date_roc": "1151008", "pe": "5.86", "pb": "4.39"}}}
        return roster, {"cache_hit": True, "stale": False, "fetched_at_epoch": 1}
    monkeypatch.setattr(values, "shared_fetch", fake_shared)
    result = values.fetch_official_peer_valuation("5314.TWO", today=TODAY)
    assert result["metrics"]["pb"] == 4.39
    assert result["cache_hit"] is True
    assert calls[0][0].endswith(":.TWO")

    monkeypatch.setattr(values, "shared_fetch", lambda *a, **k: (fake_shared("", None)[0], {"stale": True}))
    assert values.fetch_official_peer_valuation("5314.TWO", today=TODAY)["metrics"] == {}


def test_peer_fallback_uses_complete_official_observation_before_finmind(monkeypatch):
    from data_fetch.market_sources import official_peer_valuation, peer_recovery, taiwan

    monkeypatch.setattr(official_peer_valuation, "fetch_official_peer_valuation", lambda *a, **k: {
        "status": "success", "source": official_peer_valuation.PROVIDER,
        "metrics": {"pe_ttm": 5.86, "pb": 4.39}, "observed_at": "2026-10-08",
        "metric_basis": {"pe_ttm": "exchange_reported_price_earnings_ratio",
                         "pb": "exchange_reported_price_book_ratio"}})
    monkeypatch.setattr(taiwan, "DataLoader", lambda: (_ for _ in ()).throw(AssertionError("FinMind should not run")))
    result = peer_recovery.fetch_peer_valuation_fallback("5314.TWO", today=TODAY)
    assert result["metrics"] == {"pe_ttm": 5.86, "pb": 4.39}
    assert result["source"] == official_peer_valuation.PROVIDER


def test_peer_fallback_keeps_official_pb_and_uses_finmind_for_missing_pe(monkeypatch):
    from data_fetch.market_sources import official_peer_valuation, peer_recovery, taiwan

    monkeypatch.setattr(official_peer_valuation, "fetch_official_peer_valuation", lambda *a, **k: {
        "status": "success", "source": official_peer_valuation.PROVIDER,
        "metrics": {"pb": 4.39}, "observed_at": "2026-10-08",
        "metric_basis": {"pb": "exchange_reported_price_book_ratio"}})

    class Loader:
        def taiwan_stock_per_pbr(self, **kwargs):
            class Frame:
                def to_dict(self, orient):
                    assert orient == "records"
                    return [{"stock_id": "5314", "date": "2026-10-08", "PER": 5.86, "PBR": 999}]
            return Frame()

    monkeypatch.setattr(taiwan, "DataLoader", Loader)
    result = peer_recovery.fetch_peer_valuation_fallback("5314.TWO", today=TODAY)
    assert result["metrics"] == {"pb": 4.39, "pe_ttm": 5.86}
    assert result["metric_sources"]["pb"]["provider"] == official_peer_valuation.PROVIDER
    assert result["metric_sources"]["pe_ttm"]["provider"] == "FinMind TaiwanStockPER"


def test_dynamic_peer_record_preserves_per_field_official_provenance(monkeypatch):
    from data_fetch.market_sources import peers, official_peer_valuation

    monkeypatch.setattr(peers, "_today", lambda: TODAY)
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [
        {"stock_id": code, "stock_name": code, "type": market,
         "industry_category": "生技醫療業", "date": TODAY.isoformat()}
        for code, market in (("6861", "twse"), ("1234", "tpex"))])
    monkeypatch.setattr(peers.yf, "Ticker", lambda symbol: type("Quote", (), {"info": {
        "symbol": symbol, "quoteType": "EQUITY", "industry": "Medical Devices",
        "grossMargins": .4, "operatingMargins": .2, "profitMargins": .1,
        "returnOnEquity": .12, "priceToSalesTrailing12Months": 3,
        "totalRevenue": 9e9, "totalAssets": 2e9}})())
    monkeypatch.setattr(peers, "fetch_peer_valuation_fallback", lambda *a, **k: {
        "status": "success", "metrics": {"pe_ttm": 5.86, "pb": 4.39},
        "metric_sources": {field: {"provider": official_peer_valuation.PROVIDER,
                                   "observed_at": "2026-10-08", "basis": "exchange_reported"}
                           for field in ("pe_ttm", "pb")},
        "attempts": [{"provider": official_peer_valuation.PROVIDER, "status": "success"}]})
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        "6861.TW", "睿生", "Healthcare", "Medical Devices", {"same_industry_peers": [{"stock_id": "1234"}]})
    row = result["peers"][0]
    assert row["pe_ttm"] == 5.86
    assert row["metric_sources"]["pb"]["provider"] == official_peer_valuation.PROVIDER
    assert any(attempt["provider"] == official_peer_valuation.PROVIDER
               for attempt in row["acquisition_attempts"])
    assert row["metrics_status"] == "complete"
    assert result["audit"]["coverage_status"] == "success"
