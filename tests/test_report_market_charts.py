import json

import pytest
from bs4 import BeautifulSoup

from reporting.html_chart_context import build_html_chart_context
from reporting.html_renderer import generate_html_report


def market_data():
    return {
        "currency": "TWD",
        "price_history_ranges": {
            "source": "price provider",
            "ranges": {
                "1m": {"dates": ["2026-01-03", "2026-01-02", "2099-01-01"], "prices": [102, 100, 200]},
                "3m": {"dates": ["2025-12-01", "2026-01-02"], "prices": [90, 100]},
            },
        },
        "institutional_trading": {
            "source": "flow provider",
            "latest_date": "2026-01-03",
            "daily_total_net_buy_last_10": [
                {"date": "2026-01-03", "net_buy_thousand_shares": -12},
                {"date": "2026-01-02", "net_buy_thousand_shares": 0},
                {"date": "2099-01-01", "net_buy_thousand_shares": 900},
            ],
            "net_buy_thousand_shares_by_category": {"foreign": -20, "investment_trust": 8, "dealer": None},
        },
    }


@pytest.mark.parametrize("mode,dates", [("v2", ["2025-12-01", "2026-01-02"]), ("v3", ["2025-12-01", "2026-01-02"]), ("v4", ["2026-01-02", "2026-01-03"])])
def test_market_chart_context_uses_mode_horizon_and_aligned_valid_dates(mode, dates):
    context = build_html_chart_context(market_data(), {}, pipeline_id=mode)
    market = context["chart_data"]["market"]
    assert market["price"]["dates"] == dates
    assert market["price"]["prices"] == ([100, 102] if mode == "v4" else [90, 100])
    assert market["dailyFlow"] == {"dates": ["2026-01-02", "2026-01-03"], "values": [0, -12]}
    assert market["categoryFlow"] == {"labels": ["外資", "投信", "自營商"], "values": [-20, 8, None]}
    assert market["currency"] == "TWD"
    assert context["market_price_source"] == "price provider"


def test_market_chart_missing_values_stay_missing_and_fallback_is_labelled():
    data = market_data()
    data["price_history_ranges"]["ranges"] = {}
    data["price_history"] = {"2026-01-02": None, "2026-01-03": 100}
    data["institutional_trading"]["net_buy_thousand_shares_by_category"] = {"foreign": False, "dealer": "NaN"}
    context = build_html_chart_context(data, {}, pipeline_id="v4")
    assert context["market_price_title"] == "歷史股價（低頻資料）"
    assert context["chart_data"]["market"]["price"] == {"dates": ["2026-01-02", "2026-01-03"], "prices": [None, 100]}
    assert context["chart_data"]["market"]["categoryFlow"]["values"] == [None, None, None]


@pytest.mark.parametrize("mode", ["v2", "v3", "v4"])
def test_mode_report_contains_market_charts_with_no_duplicate_canvas_ids(mode):
    html = generate_html_report({"ticker": "2330.TW", "pipeline_id": mode, "data": market_data(), "parsed": {}, "analyses": {}})
    soup = BeautifulSoup(html, "html.parser")
    ids = [canvas["id"] for canvas in soup.select("canvas")]
    assert {"marketPriceChart", "institutionalDailyChart", "institutionalCategoryChart"} <= set(ids)
    assert len(ids) == len(set(ids))
    assert soup.select_one('a[href="#market-charts"]') is not None
    if mode == "v3":
        assert "peRiverChart" in ids
    if mode == "v4":
        assert "revenueChart" not in ids
    payload = json.loads(soup.select_one("#report-chart-data").string)
    assert payload["market"]["dailyFlow"]["values"] == [0, -12]


def test_valuation_without_scenarios_has_explicit_empty_state():
    html = generate_html_report({"ticker": "2330.TW", "data": {"current_price": 100}, "parsed": {}, "analyses": {}})
    soup = BeautifulSoup(html, "html.parser")
    canvas = soup.select_one("#valuationChart")
    assert canvas["data-empty-message"] == "缺少有效估值情境，無法比較目標價。"
    assert "估值情境與當前股價" in html
