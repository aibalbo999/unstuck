import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_watchlist_report_alerts_prioritize_and_compact_latest_reports():
    from watchlist_report_alerts import apply_report_alerts

    items = [
        {"ticker": "2330.TW", "enabled": True},
        {"ticker": "2308.TW", "enabled": True},
        {"ticker": "2454.TW", "enabled": False},
    ]
    reports = {
        "2308.TW": {
            "filename": "delta.html",
            "date": "2026-06-08",
            "decision_freshness": {
                "requires_rerun": True,
                "message": "資料已更新，投資結論需重跑。",
            },
            "data_trust": {"status": "fresh"},
            "ignored": "large payload",
        },
        "2330.TW": {},
        "2454.TW": {"filename": "disabled.html"},
    }

    result = apply_report_alerts(items, "/tmp/output", latest_report_lookup=lambda item, _output_dir: reports[item["ticker"]])

    assert result["priority_counts"] == {"high": 1, "medium": 1, "normal": 0, "low": 1}
    assert [item["ticker"] for item in result["items"]] == ["2308.TW", "2330.TW", "2454.TW"]
    assert result["items"][0]["decision_priority"] == "high"
    assert result["items"][0]["decision_alert"]["reason"] == "needs_rerun"
    assert result["items"][0]["latest_report"] == {
        "filename": "delta.html",
        "date": "2026-06-08",
        "decision_freshness": {
            "requires_rerun": True,
            "message": "資料已更新，投資結論需重跑。",
        },
        "data_trust": {"status": "fresh"},
    }
    assert result["items"][1]["decision_priority"] == "medium"
    assert result["items"][1]["decision_alert"]["reason"] == "missing_report"
    assert result["items"][2]["decision_priority"] == "low"


def test_watchlist_report_alert_ticker_match_accepts_base_symbol():
    from watchlist_report_alerts import ticker_matches

    assert ticker_matches({"ticker": "2308.TW"}, "2308") is True
    assert ticker_matches({"ticker": "2308"}, "2308.TW") is True
    assert ticker_matches({"ticker": "2330.TW"}, "2308.TW") is False
