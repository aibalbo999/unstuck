from __future__ import annotations

from typing import Any

from .analyst import _analyst_outlook, _earnings_forecast, _valuation
from .capital_quality import _profitability_quality, _risk_liquidity, _share_statistics
from .dividends_financials import _dividend_profile, _dividends, _financial_health, _financial_trends
from .events_alerts import _alert_suggestions, _event_calendar, _events, _news
from .ownership import _chip, _data_quality, _ownership_flow
from .peers_valuation import _peer_comparison, _valuation_range
from .profile import _company_profile, _identity, _market_session, _quote
from .technical import _performance_history, _price_trend, _technical_summary
from .utils import _json_safe, _number, _number_from_label


MODE_SUGGESTIONS = [
    {
        "pipeline_id": "v1",
        "label": "長線價值分析",
        "decision": "判斷是否值得納入長線研究清單。",
    },
    {
        "pipeline_id": "v2",
        "label": "持股與進出場決策",
        "decision": "決定現在要進場、續抱、減碼或等待。",
    },
    {
        "pipeline_id": "v3",
        "label": "泡沫與下行風險掃描",
        "decision": "檢查敘事是否過熱、是否需要避險或反向觀察。",
    },
    {
        "pipeline_id": "v4",
        "label": "事件波段交易計畫",
        "decision": "評估未來 1-2 週是否有可執行事件窗口。",
    },
]


def build_stock_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Turn the internal data payload into a stable stock-page snapshot."""
    current_price = _number(data.get("current_price"))
    analyst_target = _number(data.get("analyst_target_raw"), _number_from_label(data.get("analyst_target")))
    event_calendar = _event_calendar(data)
    snapshot = {
        "ticker": str(data.get("ticker") or "").strip().upper(),
        "identity": _identity(data),
        "company_profile": _company_profile(data),
        "quote": _quote(data),
        "market_session": _market_session(data, current_price=current_price),
        "valuation": _valuation(data, current_price=current_price, analyst_target=analyst_target),
        "analyst_outlook": _analyst_outlook(data, current_price=current_price, analyst_target=analyst_target),
        "earnings_forecast": _earnings_forecast(data, event_calendar=event_calendar),
        "share_statistics": _share_statistics(data),
        "risk_liquidity": _risk_liquidity(data, current_price=current_price),
        "profitability_quality": _profitability_quality(data),
        "dividends": _dividends(data),
        "dividend_profile": _dividend_profile(data),
        "financial_health": _financial_health(data),
        "financial_trends": _financial_trends(data),
        "peer_comparison": _peer_comparison(data),
        "valuation_range": _valuation_range(data, current_price=current_price),
        "price_trend": _price_trend(data),
        "performance_history": _performance_history(data),
        "technical_summary": _technical_summary(data),
        "ownership_flow": _ownership_flow(data),
        "event_calendar": event_calendar,
        "alert_suggestions": _alert_suggestions(
            data,
            current_price=current_price,
            analyst_target=analyst_target,
            event_calendar=event_calendar,
        ),
        "events": _events(data),
        "news": _news(data),
        "chip": _chip(data),
        "data_quality": _data_quality(data),
        "mode_suggestions": [dict(item) for item in MODE_SUGGESTIONS],
    }
    return _json_safe(snapshot)
