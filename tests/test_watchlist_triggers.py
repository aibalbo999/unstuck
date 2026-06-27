import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_evaluate_watchlist_triggers_routes_bearish_and_revenue_events():
    from watchlist_triggers import evaluate_watchlist_triggers

    data = {
        "current_price": 90,
        "price_history": {"prices": [110, 108, 106, 104, 102, 100, 98, 96, 94, 90]},
        "institutional_trading": {
            "daily_total_net_buy_last_10": [
                {"date": "2026-06-17", "net_buy_thousand_shares": -1500},
                {"date": "2026-06-18", "net_buy_thousand_shares": -1200},
                {"date": "2026-06-19", "net_buy_thousand_shares": -1300},
            ]
        },
        "macro_indicators": {"indicators": {"vix": {"value": 35}}},
        "recent_monthly_revenue": ["2026年3月: NT$2.00億", "2026年4月: NT$2.50億", "2026年5月: NT$3.10億"],
    }
    item = {
        "ticker": "2308.TW",
        "pipeline": "v1",
        "triggers": [
            {"type": "price_below_sma", "sma_days": 5},
            {"type": "foreign_sell_streak", "days": 3, "min_lots": 1000},
            {"type": "vix_above", "threshold": 30},
            {"type": "revenue_record_high"},
        ],
    }

    events = evaluate_watchlist_triggers(item, data, evaluation_date="2026-06-20")
    matched = {event["trigger_type"]: event for event in events if event["matched"]}

    assert matched["price_below_sma"]["pipeline_selected"] == "v3"
    assert matched["foreign_sell_streak"]["pipeline_selected"] == "v3"
    assert matched["vix_above"]["pipeline_selected"] == "v3"
    assert matched["revenue_record_high"]["pipeline_selected"] == "v2"
    assert matched["price_below_sma"]["metrics"]["sma"] > 90


def test_report_catalyst_trigger_records_manual_radar_condition():
    from watchlist_triggers import evaluate_watchlist_triggers

    item = {
        "ticker": "2449.TW",
        "pipeline": "v1",
        "triggers": [
            {
                "type": "report_catalyst",
                "trigger_condition": "管理層調升毛利率指引",
                "impact_direction": "bullish",
            }
        ],
    }
    data = {
        "market_catalysts": {
            "items": ["法說會中管理層調升毛利率指引，並指出測試需求優於預期。"]
        }
    }

    events = evaluate_watchlist_triggers(item, data, evaluation_date="2026-06-20")

    assert events[0]["matched"] is True
    assert events[0]["trigger_type"] == "report_catalyst"
    assert events[0]["pipeline_selected"] == "v2"
    assert events[0]["label"] == "報告催化條件"
    assert "管理層調升毛利率指引" in events[0]["message"]


def test_watchlist_trigger_store_is_idempotent(monkeypatch, tmp_path):
    import watchlist_service
    import watchlist_trigger_store

    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()
    watchlist_service.upsert_watchlist_item({
        "ticker": "2308.TW",
        "pipeline": "v1",
        "triggers": [{"type": "vix_above", "threshold": 30}],
    })

    stored = watchlist_service.list_watchlist()["items"][0]
    assert stored["triggers"][0]["type"] == "vix_above"

    event = {
        "ticker": "2308.TW",
        "pipeline": "v1",
        "trigger_key": "vix_above",
        "trigger_type": "vix_above",
        "evaluation_date": "2026-06-20",
        "matched": True,
        "pipeline_selected": "v3",
        "message": "VIX 35 > 30",
        "metrics": {"vix": 35},
    }
    first = watchlist_trigger_store.record_trigger_event(event)
    second = watchlist_trigger_store.record_trigger_event(event)

    assert first["inserted"] is True
    assert second["inserted"] is False
    latest = watchlist_trigger_store.latest_event_for_item("2308.TW", "v1")
    assert latest["trigger_type"] == "vix_above"


def test_unmatched_trigger_event_can_upgrade_to_matched(monkeypatch, tmp_path):
    import watchlist_service
    import watchlist_trigger_store

    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()
    base = {
        "ticker": "2308.TW",
        "pipeline": "v1",
        "trigger_key": "vix_above",
        "trigger_type": "vix_above",
        "evaluation_date": "2026-06-20",
        "pipeline_selected": "v1",
        "message": "VIX 無資料",
        "metrics": {},
    }

    first = watchlist_trigger_store.record_trigger_event({**base, "matched": False})
    upgraded = watchlist_trigger_store.record_trigger_event({
        **base,
        "matched": True,
        "pipeline_selected": "v3",
        "message": "VIX 35 > 30",
        "metrics": {"vix": 35},
    })
    duplicate = watchlist_trigger_store.record_trigger_event({**base, "matched": True, "pipeline_selected": "v3"})

    assert first["inserted"] is True
    assert upgraded["inserted"] is True
    assert duplicate["inserted"] is False
    latest = watchlist_trigger_store.latest_event_for_item("2308.TW", "v1")
    assert latest["matched"] is True
    assert latest["pipeline_selected"] == "v3"
