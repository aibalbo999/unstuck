from __future__ import annotations

from typing import Any

from .utils import _number, _text


def _chip(data: dict[str, Any]) -> dict[str, Any]:
    institutional = data.get("institutional_trading") if isinstance(data.get("institutional_trading"), dict) else {}
    chip_data = data.get("chip_data") if isinstance(data.get("chip_data"), dict) else {}
    margin = chip_data.get("twse_margin_short_sales") if isinstance(chip_data.get("twse_margin_short_sales"), dict) else {}
    tdcc = chip_data.get("tdcc_shareholder_distribution") if isinstance(chip_data.get("tdcc_shareholder_distribution"), dict) else {}
    return {
        "institutional_summary": _text(institutional.get("summary")),
        "institutional_trading": institutional,
        "margin_short_sales": margin,
        "shareholder_distribution": tdcc,
    }

def _ownership_flow(data: dict[str, Any]) -> dict[str, Any]:
    institutional = data.get("institutional_trading") if isinstance(data.get("institutional_trading"), dict) else {}
    chip_data = data.get("chip_data") if isinstance(data.get("chip_data"), dict) else {}
    margin_source = chip_data.get("twse_margin_short_sales") if isinstance(chip_data.get("twse_margin_short_sales"), dict) else {}
    holder_source = chip_data.get("tdcc_shareholder_distribution") if isinstance(chip_data.get("tdcc_shareholder_distribution"), dict) else {}
    categories = _ownership_categories(institutional)
    total_net = _number(institutional.get("total_net_buy_thousand_shares"))
    last_5_net = _number(institutional.get("last_5_trading_days_net_buy_thousand_shares"))
    margin_balance = _number(margin_source.get("margin_balance"))
    short_balance = _number(margin_source.get("short_balance"))
    borrowed_short_balance = _number(margin_source.get("borrowed_short_sale_balance"))
    major_holders = _number(holder_source.get("major_holders_gt_1000_lots_pct"), holder_source.get("large_holder_pct"))
    retail_holders = _number(holder_source.get("retail_holders_lt_50_lots_pct"))
    has_data = any(
        value is not None
        for value in (
            total_net,
            last_5_net,
            margin_balance,
            short_balance,
            borrowed_short_balance,
            major_holders,
            retail_holders,
        )
    ) or bool(categories)
    if not has_data:
        return {
            "status": "insufficient_data",
            "label": "籌碼資料不足",
            "institutional": {},
            "margin": {},
            "holders": {},
            "signals": [],
        }
    return {
        "status": "available",
        "label": _ownership_label(_text(institutional.get("trend")), total_net),
        "institutional": {
            "summary": _text(institutional.get("summary")),
            "trend": _text(institutional.get("trend")),
            "latest_date": _text(institutional.get("latest_date")),
            "total_net_buy_thousand_shares": total_net,
            "last_5_trading_days_net_buy_thousand_shares": last_5_net,
            "categories": categories,
        },
        "margin": {
            "margin_balance": margin_balance,
            "short_balance": short_balance,
            "borrowed_short_sale_balance": borrowed_short_balance,
            "as_of_date": _text(margin_source.get("as_of_date")),
        },
        "holders": {
            "major_holders_gt_1000_lots_pct": major_holders,
            "retail_holders_lt_50_lots_pct": retail_holders,
            "as_of_date": _text(holder_source.get("as_of_date")),
        },
        "signals": _ownership_signals(total_net, categories, major_holders),
    }

def _ownership_categories(institutional: dict[str, Any]) -> list[dict[str, Any]]:
    source = institutional.get("net_buy_thousand_shares_by_category")
    if not isinstance(source, dict):
        return []
    labels = {
        "foreign": "外資",
        "investment_trust": "投信",
        "dealer": "自營商",
    }
    rows = []
    for key in ("foreign", "investment_trust", "dealer"):
        value = _number(source.get(key))
        if value is not None:
            rows.append({"key": key, "label": labels[key], "net_buy_thousand_shares": value})
    return rows

def _ownership_label(trend: str, total_net: float | None) -> str:
    normalized = trend.lower()
    if normalized == "accumulation":
        return "法人買超"
    if normalized == "distribution":
        return "法人賣超"
    if total_net is not None:
        if total_net > 0:
            return "法人買超"
        if total_net < 0:
            return "法人賣超"
    return "籌碼中性"

def _ownership_signals(
    total_net: float | None,
    categories: list[dict[str, Any]],
    major_holders: float | None,
) -> list[str]:
    signals = []
    if total_net is not None:
        signals.append(f"近30日法人合計{_flow_word(total_net)} {_lots_label(total_net)}")
    foreign = next((row for row in categories if row.get("key") == "foreign"), None)
    if foreign and _number(foreign.get("net_buy_thousand_shares")) is not None:
        value = _number(foreign.get("net_buy_thousand_shares"))
        signals.append(f"外資{_flow_word(value)} {_lots_label(value)}")
    if major_holders is not None:
        signals.append(f"千張以上大戶 {major_holders:.1f}%")
    return signals[:3]

def _flow_word(value: float | None) -> str:
    number = _number(value)
    if number is None or number == 0:
        return "持平"
    return "買超" if number > 0 else "賣超"

def _lots_label(value: float | None) -> str:
    number = abs(_number(value) or 0)
    if float(number).is_integer():
        return f"{number:,.0f}張"
    return f"{number:,.1f}張"

def _data_quality(data: dict[str, Any]) -> dict[str, Any]:
    trust = data.get("data_trust") if isinstance(data.get("data_trust"), dict) else {}
    return {
        "status": _text(trust.get("status")) or "unknown",
        "score": _number(trust.get("score")),
        "reason_codes": list(trust.get("reason_codes") or []),
    }
