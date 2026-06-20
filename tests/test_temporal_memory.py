import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_build_temporal_memory_uses_previous_report_and_backtest(monkeypatch, tmp_path):
    import decision_tracking_store
    import temporal_memory_service

    monkeypatch.setattr(decision_tracking_store, "DECISION_TRACKING_DB_PATH", str(tmp_path / "tracking.sqlite3"))
    decision_tracking_store.reset_decision_tracking_store_for_tests()
    reports = [
        {
            "filename": "2308_v2_report_20260401_090000.html",
            "ticker": "2308.TW",
            "date": "2026-04-01 09:00",
            "summary": "本季看好 AI 電源成長。",
            "recommendation": {"recommendation": "買入", "target_3m": "NT$220", "target_6m": "NT$250", "target_12m": "NT$300"},
        },
        {
            "filename": "2308_v2_report_20260101_090000.html",
            "ticker": "2308.TW",
            "date": "2026-01-01 09:00",
            "summary": "上一季高估擴產速度。",
            "recommendation": {"recommendation": "買入", "target_3m": "NT$210", "target_6m": "NT$240", "target_12m": "NT$280"},
        },
    ]
    monkeypatch.setattr(
        temporal_memory_service.report_history_service,
        "list_reports",
        lambda **kwargs: {"reports": reports, "pagination": {}},
    )
    decision_tracking_store.upsert_backtest_result({
        "report_filename": "2308_v2_report_20260401_090000.html",
        "ticker": "2308.TW",
        "pipeline_id": "v2",
        "horizon_months": 3,
        "generated_date": "2026-04-01",
        "evaluation_date": "2026-06-20",
        "initial_price": 200,
        "actual_price": 180,
        "target_price": 220,
        "recommendation": "買入",
        "market_return_pct": -10,
        "strategy_roi_pct": -10,
        "target_error_pct": -18.18,
        "outcome": "miss",
        "reason": "buy_thesis_not_met",
    })

    memory = temporal_memory_service.build_temporal_memory("2308.TW", output_dir=str(tmp_path), current_price=180)

    assert memory["previous_report"]["filename"] == "2308_v2_report_20260401_090000.html"
    assert memory["previous_report"]["recommendation"] == "買入"
    assert memory["previous_report"]["target_3m"] == "NT$220"
    assert memory["current_price"] == 180
    assert memory["backtests"][0]["outcome"] == "miss"
    assert "預測落空" in memory["reflection_prompt"]
    assert "請在此次分析中明確檢討" in memory["reflection_prompt"]


def test_temporal_memory_is_routed_only_to_final_decision_agents():
    from agent_runtime.prompting import data_for_agent_prompt

    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "current_price": 180,
        "temporal_memory": {"reflection_prompt": "Agent 歷史反思"},
    }

    assert "temporal_memory" not in data_for_agent_prompt(4, data)
    assert "temporal_memory" in data_for_agent_prompt(7, data)
    assert "temporal_memory" in data_for_agent_prompt(16, data)
    assert "temporal_memory" in data_for_agent_prompt(19, data)


def test_report_row_surfaces_temporal_memory_from_snapshot(tmp_path):
    import report_index_rows

    snapshot = tmp_path / "sample.data.json"
    snapshot.write_text(json.dumps({"data": {"temporal_memory": {"reflection_prompt": "上一季檢討"}}}, ensure_ascii=False), encoding="utf-8")

    class Row(dict):
        def keys(self):
            return super().keys()

    row = Row({
        "filename": "2308_report_20260620_090000.html",
        "ticker": "2308.TW",
        "company_name": "台達電",
        "report_date": "2026-06-20 09:00",
        "timestamp": 1781926800,
        "pipeline_id": "v1",
        "recommendation_json": "{}",
        "data_trust_json": "{}",
        "data_snapshot_filename": "sample.data.json",
        "output_dir": str(tmp_path),
        "analysis_text_stale": 0,
        "analysis_text_stale_message": "",
    })

    report = report_index_rows.row_to_report(row)

    assert report["temporal_memory"]["reflection_prompt"] == "上一季檢討"
