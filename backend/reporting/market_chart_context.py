"""Mode-specific market charts sourced only from the saved data snapshot."""

from __future__ import annotations

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text

from .chart_payload import chart_number, chart_price_history
from .html_sanitizer import sanitize_report_plain_text


def _text(value, default=""):
    return sanitize_report_plain_text(safe_text(value)).strip() or default


def _dated_series(value, *, positive=False):
    payload = chart_price_history(value)
    if "dates" in payload:
        rows = dict(zip(payload["dates"], payload["prices"]))
    else:
        rows = payload
    dates = sorted(rows)
    values = [rows[day] for day in dates]
    if positive:
        values = [value if value is not None and value > 0 else None for value in values]
    return {"dates": dates, "prices": values}


def build_market_chart_context(data: dict, *, price_range: str) -> dict:
    history = safe_mapping_dict(data.get("price_history_ranges")) or {}
    ranges = safe_mapping_dict(history.get("ranges")) or {}
    price = _dated_series(ranges.get(price_range), positive=True)
    price_title = "近一個月股價" if price_range == "1m" else "近三個月股價"
    price_source = _text(history.get("source"), "報告股價快照")
    if sum(value is not None for value in price["prices"]) < 2:
        price = _dated_series(data.get("price_history"), positive=True)
        price_title = "歷史股價（低頻資料）"
        price_source = "報告歷史股價快照"

    institutional = safe_mapping_dict(data.get("institutional_trading")) or {}
    daily_rows = safe_dict_list(institutional.get("daily_total_net_buy_last_10"))
    daily = _dated_series({
        "dates": [row.get("date") for row in daily_rows],
        "prices": [row.get("net_buy_thousand_shares") for row in daily_rows],
    })
    categories = safe_mapping_dict(institutional.get("net_buy_thousand_shares_by_category")) or {}
    return {
        "market_chart_data": {
            "price": price,
            "dailyFlow": {"dates": daily["dates"], "values": daily["prices"]},
            "categoryFlow": {
                "labels": ["外資", "投信", "自營商"],
                "values": [chart_number(categories.get(key)) for key in ("foreign", "investment_trust", "dealer")],
            },
            "currency": _text(data.get("currency"), "TWD"),
        },
        "market_price_title": price_title,
        "market_price_source": price_source,
        "market_price_period": " ~ ".join([price["dates"][0], price["dates"][-1]]) if price["dates"] else "資料不足",
        "market_flow_source": _text(institutional.get("source"), "報告法人籌碼快照"),
        "market_flow_period": " ~ ".join([daily["dates"][0], daily["dates"][-1]]) if daily["dates"] else "資料不足",
        "market_flow_as_of": _text(institutional.get("latest_date"), "未記錄"),
    }
