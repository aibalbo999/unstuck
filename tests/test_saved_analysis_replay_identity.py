"""A replay must not become a new forecast or inflate the evaluation population."""
import copy
import json
from datetime import date

from data_trust_snapshot import build_data_snapshot
from decision_tracking import build_decision_freshness, build_decision_tracking
from report_publication_identity import publication_identity, replay_notice


REPLAY = {"source_filename": "1301_TW_v4_report_job_original.html",
          "source_conclusion_generated_at": "2026-10-02T10:15:15+00:00",
          "source_analysis_input_cutoff": "2026-10-02T10:09:22+00:00",
          "market_as_of": "2026-10-02", "no_new_model_call": True}


def snapshot():
    return build_data_snapshot({"ticker": "1301.TW", "pipeline_id": "v4",
        "saved_analysis_replay": copy.deepcopy(REPLAY), "data": {"current_price": 68.3}},
        pipeline_id="v4", generated_at="2026-10-03T02:29:40+00:00")


def test_snapshot_preserves_analysis_time_and_records_publication_separately():
    value = snapshot()
    assert value["conclusion_generated_at"] == REPLAY["source_conclusion_generated_at"]
    assert value["publication_generated_at"] == "2026-10-03T02:29:40+00:00"
    assert value["saved_analysis_replay"] == REPLAY
    assert not publication_identity(value)["prediction_eligible"]
    freshness = build_decision_freshness(snapshot=value)
    tracking = build_decision_tracking({"current_price": 68.3}, snapshot=value)
    assert freshness["status"] == "saved_analysis_replay" and not freshness["requires_rerun"]
    assert tracking["status"] == "excluded_replay" and tracking["return_pct"] is None
    text = replay_notice(value)
    assert "2026-10-02 18:15" in text and "2026-10-02 18:09" in text and "2026-10-03 10:29" in text


def test_missing_archived_analysis_time_is_not_filled_with_publication_time():
    value = build_data_snapshot({"saved_analysis_replay": {"source_filename": "legacy.html"}, "data": {}},
                                generated_at="2026-10-03T02:29:40+00:00")
    assert value["conclusion_generated_at"] == ""
    assert "不能推定" in replay_notice(value)


def test_new_model_forecast_and_real_partial_rerun_keep_normal_tracking():
    value = {"generated_at": "2026-10-03T02:29:40+00:00", "data": {"current_price": 69},
             "partial_rerun": {"scope": "final_recommendation"}}
    assert publication_identity(value)["prediction_eligible"]
    assert build_decision_freshness(snapshot=value)["status"] == "current"
    assert build_decision_tracking({"current_price": 68}, snapshot=value)["status"] == "tracked"


def test_direct_trade_evaluation_rejects_canonical_replay_before_price_fetch(monkeypatch, tmp_path):
    import mode_trade_backtest as module
    from storage.report_storage import LocalFileStorage
    from report_persistence import report_bundle_keys_for_filename
    filename = "1301_TW_v4_report_20261003_102940.html"
    storage = LocalFileStorage(str(tmp_path))
    storage.save_report(report_bundle_keys_for_filename(filename).data_key,
                        json.dumps(snapshot()).encode(), content_type="application/json")
    called = []
    results, skips = module.evaluate_report_trades(report={"filename": filename}, pipeline_id="v4",
        generated=date(2026, 10, 3), as_of=date(2027, 1, 1), output_dir=str(tmp_path),
        bar_fetcher=lambda *a: called.append(a), allow_historical_evaluation=True)
    assert results == [] and skips[0]["reason"] == "saved_analysis_replay_not_prediction"
    assert not called


def test_population_excludes_replay_before_date_calendar_and_sampling(monkeypatch):
    import performance_population as module
    monkeypatch.setattr(module, "query_report_metadata", lambda **kw: ([{"filename": "replay.html", "ticker": "1301.TW", "publication_identity": {"kind": "saved_analysis_replay"}}], 1))
    result = module.indexed_population("unused", as_of=date(2026, 10, 2), saved=[])
    assert result["report_count"] == 0 and result["expected_slots"] == 0
    assert result["excluded_non_prediction_count"] == 1 and result["excluded_non_prediction_slots"] == 2


def test_latest_tracking_selects_previous_real_forecast_instead_of_replay(monkeypatch):
    import decision_tracking_service as module
    import tracking_latest_reports as selection
    rows = [{"filename": "replay.html", "ticker": "1301.TW", "pipeline_id": "v4", "timestamp": 2},
            {"filename": "real.html", "ticker": "1301.TW", "pipeline_id": "v4", "timestamp": 1}]
    monkeypatch.setattr(selection, "query_report_metadata", lambda **kw: (rows, 2))
    monkeypatch.setattr(selection, "_read_snapshot", lambda row: {"saved_analysis_replay": {"source_filename": "real.html"}} if row["filename"] == "replay.html" else {})
    monkeypatch.setattr(selection, "row_to_report", lambda row, **kw: row)
    assert [row["filename"] for row in module.latest_reports_for_ticker("1301.TW", "unused")] == ["real.html"]


def test_due_backtest_poll_skips_replay_before_model_or_provider_calls(monkeypatch):
    import decision_backtest_service as module
    import legacy_evidence_revisions
    monkeypatch.setattr(module.report_history_service, "list_reports", lambda **kw: {"reports": [
        {"filename": "replay.html", "publication_identity": {"kind": "saved_analysis_replay"}}]})
    monkeypatch.setattr(legacy_evidence_revisions, "run_due_revisions", lambda **kw: {})
    result = module.run_due_backtests(output_dir="unused", as_of=date(2027, 1, 1),
        price_fetcher=lambda *a: (_ for _ in ()).throw(AssertionError("provider called")),
        bar_fetcher=lambda *a: (_ for _ in ()).throw(AssertionError("provider called")))
    assert result["evaluated_count"] == 0 and result["skipped"][0]["reason"] == "saved_analysis_replay_not_prediction"


def test_replay_usage_notice_in_html_and_markdown_preserves_quality_warning():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown
    context = {**snapshot(), "content_credibility": {"status": "warning"},
               "report_conformance": {"status": "warning"}, "evidence_exit_gate": {"verdict": "caution"}}
    for text in (build_report_reading_notice_html(context), build_report_reading_notice_markdown(context)):
        assert "保存分析驗證重播" in text and "未產生新模型預測" in text
        assert "2026-10-02 18:15" in text and "2026-10-03 10:29" in text
        assert "有警示" in text or "需人工確認" in text
        assert ">saved_analysis_replay<" not in text
        assert "目前無法確認投資結論" not in text


def test_tracking_paginates_past_archived_replay_versions(monkeypatch):
    import decision_tracking_service as module
    import tracking_latest_reports as selection
    def history(**kw):
        if kw['page'] == 1:
            return ([{'filename': 'replay.html', 'ticker': '1301.TW', 'pipeline_id': 'v4', 'timestamp': 2}], 101)
        return ([{'filename': 'real.html', 'ticker': '1301.TW', 'pipeline_id': 'v4', 'timestamp': 1}], 101)
    monkeypatch.setattr(selection, 'query_report_metadata', history)
    monkeypatch.setattr(selection, '_read_snapshot', lambda row: {'saved_analysis_replay': {'source_filename': 'real.html'}} if row['filename'] == 'replay.html' else {})
    monkeypatch.setattr(selection, 'row_to_report', lambda row, **kw: row)
    assert module.latest_reports_for_ticker('1301.TW', 'unused')[0]['filename'] == 'real.html'
