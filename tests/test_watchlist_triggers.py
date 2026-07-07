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


def test_revenue_record_high_requires_volume_confirmation_when_available():
    from watchlist_triggers import evaluate_watchlist_triggers

    data = {
        "ticker": "2308.TW",
        "recent_monthly_revenue": ["2026年3月: NT$2.00億", "2026年4月: NT$2.50億", "2026年5月: NT$3.10億"],
        "daily_prices": [
            {"close": 100, "volume": 1000},
            {"close": 101, "volume": 1100},
            {"close": 102, "volume": 1200},
            {"close": 103, "volume": 1300},
            {"close": 104, "volume": 900},
        ],
    }
    item = {
        "ticker": "2308.TW",
        "pipeline": "v1",
        "triggers": [{"type": "revenue_record_high", "volume_ratio_threshold": 1.3}],
    }

    event = evaluate_watchlist_triggers(item, data, evaluation_date="2026-06-20")[0]

    assert event["evaluation_date"] == "2026-06-01"
    assert event["matched"] is False
    assert event["metrics"]["revenue_record"] is True
    assert event["metrics"]["volume_confirmed"] is False
    assert event["metrics"]["volume_threshold"] == 1.3
    assert event["metrics"]["volume_ratio"] < 1.3


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


def test_daily_screener_trigger_always_routes_to_mode_d():
    from watchlist_triggers import evaluate_watchlist_triggers

    item = {
        "ticker": "2449.TW",
        "pipeline": "v4",
        "triggers": [
            {
                "key": "daily_screener",
                "type": "daily_screener",
                "reason": "乖離率 28.4%，成交量放大 8.0x",
                "category": "technical_heat",
                "screen_date": "2026-06-26",
            }
        ],
    }

    events = evaluate_watchlist_triggers(item, {"ticker": "2449.TW"}, evaluation_date="2026-06-26")

    assert events[0]["matched"] is True
    assert events[0]["trigger_type"] == "daily_screener"
    assert events[0]["pipeline_selected"] == "v4"
    assert events[0]["label"] == "每日市場掃描"
    assert events[0]["metrics"]["screen_date"] == "2026-06-26"


def test_event_upcoming_trigger_matches_inside_notice_window():
    from watchlist_triggers import evaluate_watchlist_triggers

    item = {
        "ticker": "2330.TW",
        "pipeline": "v1",
        "triggers": [
            {
                "type": "event_upcoming",
                "event_type": "earnings_date",
                "target_date": "2026-07-16",
                "days_before": 14,
                "label": "財報日",
            }
        ],
    }
    data = {
        "event_calendar": {
            "events": [
                {
                    "type": "earnings_date",
                    "label": "財報日",
                    "date": "2026-07-16",
                }
            ]
        }
    }

    event = evaluate_watchlist_triggers(item, data, evaluation_date="2026-07-05")[0]

    assert event["matched"] is True
    assert event["trigger_type"] == "event_upcoming"
    assert event["pipeline_selected"] == "v4"
    assert event["label"] == "關鍵日期提醒"
    assert event["metrics"]["days_until"] == 11
    assert "財報日" in event["message"]


def test_price_near_level_trigger_matches_within_threshold():
    from watchlist_triggers import evaluate_watchlist_triggers

    item = {
        "ticker": "2330.TW",
        "pipeline": "v1",
        "triggers": [
            {
                "type": "price_near_level",
                "label": "接近分析師目標價",
                "target_price": 1000,
                "threshold_pct": 1.0,
            }
        ],
    }

    matched = evaluate_watchlist_triggers(item, {"current_price": 995}, evaluation_date="2026-07-05")[0]
    missed = evaluate_watchlist_triggers(item, {"current_price": 950}, evaluation_date="2026-07-05")[0]

    assert matched["matched"] is True
    assert matched["trigger_type"] == "price_near_level"
    assert matched["pipeline_selected"] == "v2"
    assert matched["metrics"]["distance_pct"] == -0.5
    assert missed["matched"] is False
    assert missed["metrics"]["distance_pct"] == -5.0


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


def test_watchlist_trigger_store_migrates_legacy_sqlite_events(monkeypatch, tmp_path):
    import sqlite3
    import watchlist_service
    import watchlist_store
    import watchlist_trigger_store

    legacy_db = tmp_path / "watchlist.sqlite3"
    operational_db = tmp_path / "operational.sqlite3"
    with sqlite3.connect(legacy_db) as conn:
        conn.execute(
            """
            CREATE TABLE watchlist_trigger_events (
                ticker TEXT NOT NULL,
                pipeline TEXT NOT NULL,
                trigger_key TEXT NOT NULL,
                evaluation_date TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                matched INTEGER NOT NULL,
                pipeline_selected TEXT NOT NULL,
                message TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                job_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                PRIMARY KEY (ticker, pipeline, trigger_key, evaluation_date)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO watchlist_trigger_events (
                ticker, pipeline, trigger_key, evaluation_date, trigger_type,
                matched, pipeline_selected, message, metrics_json, job_id, created_at
            ) VALUES ('2308.TW', 'v1', 'vix_above', '2026-06-20', 'vix_above',
                1, 'v3', 'VIX 35 > 30', '{"vix": 35}', 'job-1', '2026-06-20T16:00:00+08:00')
            """
        )

    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.setattr(watchlist_service, "WATCHLIST_DB_PATH", str(operational_db))
    monkeypatch.setattr(watchlist_store, "WATCHLIST_DB_PATH", str(operational_db))
    monkeypatch.setattr(watchlist_trigger_store, "LEGACY_WATCHLIST_DB_PATH", legacy_db, raising=False)
    watchlist_service.reset_watchlist_store_for_tests()

    latest = watchlist_trigger_store.latest_event_for_item("2308.TW", "v1")
    repeated = watchlist_trigger_store.latest_event_for_item("2308.TW", "v1")

    assert latest["trigger_type"] == "vix_above"
    assert latest["pipeline_selected"] == "v3"
    assert repeated == latest
    assert watchlist_store._db_path() == operational_db.resolve(strict=False)
    with sqlite3.connect(watchlist_store._db_path()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM watchlist_trigger_events").fetchone()[0] == 1


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
