"""Disposition decisions never rewrite or score the frozen 76-row cohort."""
import copy
import hashlib
import json
import sqlite3
from datetime import datetime

import pytest


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


@pytest.fixture
def cohort(tmp_path, monkeypatch):
    import legacy76_dispositions as dispositions

    path = tmp_path / "operational.sqlite3"
    rows, revisions, originals = [], [], []
    for i in range(76):
        original = {"report_filename": f"fixture_{i}.html", "status": "insufficient_data",
                    "reason": "missing_ohlc", "horizon_trading_days": 10}
        scope = {"scope_id": digest(i), "ticker": f"{1000+i}.TW", "report_filename": original["report_filename"],
                 "generated_date": "2026-09-17", "maturity_date": "2026-10-05", "sessions": ["2026-10-05"],
                 "original_payload": original, "original_payload_sha256": digest(original)}
        rows.append(scope)
        originals.append((scope["report_filename"], encoded(original)))
        plan = {"trade_direction": "Long", "entry_zone": "65.07-68.10" if i < 3 else "65.0-68.0",
                "target_price": "71.2", "stop_loss": "61.07" if i < 3 else "61.0"}
        data = {"ticker": scope["ticker"], "quote_type": None if i in (3, 4) else "EQUITY"}
        payload = {"scope": scope, "state": "insufficient_data" if i < 6 else "no_trade",
                   "metrics": {"status": "insufficient_data" if i < 6 else "no_trade",
                               "reason": "off_grid_or_unknown_instrument" if i < 5 else "plan_price_basis_unverified"},
                   "report_snapshot": {"data": data, "rerun_context": {"parsed": {"trade_setup": plan}}},
                   "report_snapshot_raw_sha256": digest({"original_snapshot": i}),
                   "source_admission": {"eligible": True, "all_historical_bars_verified": False,
                                        "raw_evidence": {"source_url": "https://example.invalid/archived-official", "raw_response_sha256": digest(i)}},
                   "point_in_time_verified": False, "actual_cost_verified": False, "strategy_validated": False}
        revisions.append((digest({"revision": i}), dispositions.BATCH_ID, scope["scope_id"], "2026-10-21",
                          payload["state"], encoded(payload), "2026-10-21T14:40:00+00:00"))
    manifest = {"batch_id": dispositions.BATCH_ID, "schema_version": "legacy-revision-scope-v1", "rows": rows}
    manifest_sha = digest(manifest)
    monkeypatch.setattr(dispositions, "MANIFEST_SHA256", manifest_sha)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE trade_evidence_revision_batches_v1(batch_id TEXT PRIMARY KEY,manifest_json TEXT,manifest_sha256 TEXT,active INTEGER)")
        conn.execute("INSERT INTO trade_evidence_revision_batches_v1 VALUES(?,?,?,1)", (dispositions.BATCH_ID, encoded(manifest), manifest_sha))
        conn.execute("CREATE TABLE trade_evidence_revisions_v1(revision_id TEXT PRIMARY KEY,batch_id TEXT,scope_id TEXT,as_of_session TEXT,state TEXT,payload_json TEXT,created_at TEXT)")
        conn.executemany("INSERT INTO trade_evidence_revisions_v1 VALUES(?,?,?,?,?,?,?)", revisions)
        conn.execute("CREATE TABLE trade_evaluation_results_v1(report_filename TEXT PRIMARY KEY,payload_json TEXT)")
        conn.executemany("INSERT INTO trade_evaluation_results_v1 VALUES(?,?)", originals)
    return dispositions, path, rows


def request_for(preview, indexes=(0, 1, 2)):
    candidates = preview["unscored_scopes"]
    return {"batch_id": preview["batch_id"], "reviewer": "fixture reviewer", "review_note": "Reviewed original plan and exact invalid price grid; no price changes.",
            "items": [{**candidates[i]["request_binding"], "action": "close_unscored",
                       "reason": "invalid_original_price_grid"} for i in indexes]}


def original_tables(path):
    with sqlite3.connect(path) as conn:
        return {t: conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in
                ("trade_evaluation_results_v1", "trade_evidence_revisions_v1", "trade_evidence_revision_batches_v1")}


def moment():
    return datetime.fromisoformat("2026-10-22T21:24:00+08:00")


def test_preview_never_writes_and_keeps_recoverable_scopes_open(cohort):
    d, path, rows = cohort
    before = path.read_bytes()
    p = d.preview(path, moment=moment())
    assert path.read_bytes() == before
    assert p["approved_scope_count"] == 76
    assert p["trading_terminal_scope_count"] == 70
    assert p["unscored_disposition_scope_count"] == 0
    assert len(p["unscored_scopes"]) == 6
    assert [s["suggested_reason"] for s in p["unscored_scopes"]].count("invalid_original_price_grid") == 3
    assert all(s["suggested_action"] == "review_required" for s in p["unscored_scopes"][3:])
    assert p["completed_market_session"] == "2026-10-22"
    assert p["evidence_session"] == "2026-10-21"
    assert p["validated_strategy_results"] == 0


def test_apply_is_atomic_idempotent_reversible_and_preserves_76_and_history(cohort):
    d, path, rows = cohort
    before = original_tables(path)
    initial = d.preview(path, moment=moment())
    request = request_for(initial)
    p = d.preview(path, request=request, moment=moment())
    result = d.apply(path, request, expected_preview_sha256=p["preview_sha256"], moment=moment())
    assert result["appended_events"] == 3
    again = d.apply(path, request, expected_preview_sha256=p["preview_sha256"], moment=moment())
    assert again["appended_events"] == 0 and again["already_applied"]
    after = d.preview(path, moment=moment())
    assert after["approved_scope_count"] == 76
    assert after["trading_terminal_scope_count"] == 70
    assert after["unscored_disposition_scope_count"] == 3
    assert after["remaining_scope_count"] == 3
    assert original_tables(path) == before
    assert after["validated_strategy_results"] == 0
    closed = [r for r in after["unscored_scopes"] if r["disposition"]]
    reopen = {"batch_id": d.BATCH_ID, "reviewer": "fixture reviewer", "review_note": "Reopen for documented review; no original result replacement.",
              "items": [{**r["request_binding"], "action": "reopen", "reason": "review_reopened",
                         "reopens_event_id": r["disposition"]["event_id"]} for r in closed]}
    rp = d.preview(path, request=reopen, moment=moment())
    assert d.apply(path, reopen, expected_preview_sha256=rp["preview_sha256"], moment=moment())["appended_events"] == 3
    assert d.preview(path, moment=moment())["remaining_scope_count"] == 6
    assert original_tables(path) == before


def test_missing_fields_alone_cannot_close_a_recoverable_scope(cohort):
    d, path, _ = cohort
    p = d.preview(path, moment=moment())
    request = request_for(p, (3,))
    with pytest.raises(ValueError, match="invalid.*grid|price.*grid"):
        d.preview(path, request=request, moment=moment())
    request["items"][0]["reason"] = "unrecoverable_original_evidence"
    with pytest.raises(ValueError, match="review|evidence"):
        d.preview(path, request=request, moment=moment())


def inventory_review(item):
    records = []
    for kind in ("original_generation_inputs", "historical_source_archive"):
        receipt = {"kind": kind, "scope_id": item["scope_id"], "original_payload_sha256": item["original_payload_sha256"],
                   "source_ref": "fixture://inventory/" + kind, "searched_at": "2026-10-22T21:00:00+08:00",
                   "result": "does_not_bind_original_contract", "finding": "Fixture inventory explicitly reviewed; contains no binding for original plan basis."}
        records.append({**receipt, "receipt": receipt, "receipt_sha256": digest(receipt)})
    return {"schema_version": "legacy76-unrecoverability-review:v1", "scope_id": item["scope_id"],
            "revision_payload_sha256": item["revision_payload_sha256"], "original_contract_unrecoverable": True,
            "current_data_not_used_as_pit": True, "original_plan_unchanged": True,
            "conclusion": "Fixture reviewer attests an exhausted original-input and historical-archive inventory; absence is not inferred from a missing field alone.",
            "searched_records": records}


def test_explicit_inventory_can_close_unscored_but_tampered_receipt_cannot(cohort):
    d, path, _ = cohort
    request = request_for(d.preview(path, moment=moment()), (3,))
    item = request["items"][0]
    item["reason"] = "unrecoverable_original_evidence"
    item["evidence_review"] = inventory_review(item)
    tampered = copy.deepcopy(request)
    tampered["items"][0]["evidence_review"]["searched_records"][0]["receipt"]["finding"] = "changed"
    before = path.read_bytes()
    with pytest.raises(ValueError, match="receipt"):
        d.preview(path, request=tampered, moment=moment())
    assert path.read_bytes() == before
    p = d.preview(path, request=request, moment=moment())
    assert d.apply(path, request, expected_preview_sha256=p["preview_sha256"], moment=moment())["appended_events"] == 1
    p = d.preview(path, moment=moment())
    assert p["unscored_disposition_scope_count"] == 1 and p["remaining_scope_count"] == 5
    assert not p["unscored_scopes"][4]["disposition"]


@pytest.mark.parametrize("action", ["no_trade", "hit", "miss", "validated"])
def test_disposition_cannot_invent_a_trading_result(cohort, action):
    d, path, _ = cohort
    request = request_for(d.preview(path, moment=moment()), (0,))
    request["items"][0]["action"] = action
    before = path.read_bytes()
    with pytest.raises(ValueError, match="outcome|validated"):
        d.preview(path, request=request, moment=moment())
    assert path.read_bytes() == before


def test_multi_item_validation_failure_is_atomic(cohort):
    d, path, _ = cohort
    request = request_for(d.preview(path, moment=moment()), (0, 3))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="price grid"):
        d.apply(path, request, expected_preview_sha256="0" * 64, moment=moment())
    assert path.read_bytes() == before


def test_changed_original_or_manifest_blocks_apply(cohort):
    d, path, scopes = cohort
    request = request_for(d.preview(path, moment=moment()), (0,))
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE trade_evaluation_results_v1 SET payload_json='{}' WHERE report_filename=?", (scopes[0]["report_filename"],))
    with pytest.raises(ValueError, match="original"):
        d.preview(path, request=request, moment=moment())
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE trade_evidence_revision_batches_v1 SET manifest_sha256=?", ("f" * 64,))
    with pytest.raises(ValueError, match="manifest"):
        d.preview(path, moment=moment())


def test_stale_preview_or_revision_and_out_of_scope_abort_without_write(cohort):
    d, path, _ = cohort
    request = request_for(d.preview(path, moment=moment()))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="preview"):
        d.apply(path, request, expected_preview_sha256="0" * 64, moment=moment())
    assert path.read_bytes() == before
    changed = copy.deepcopy(request)
    changed["items"][0]["revision_id"] = "a" * 64
    with pytest.raises(ValueError, match="revision|binding"):
        d.preview(path, request=changed, moment=moment())
    changed["batch_id"] = "other-batch"
    with pytest.raises(ValueError, match="batch"):
        d.preview(path, request=changed, moment=moment())
    assert path.read_bytes() == before


def test_summary_partition_and_scheduler_skip_only_reviewed_scopes(cohort, monkeypatch):
    from datetime import date
    from types import SimpleNamespace
    import legacy_evidence_revisions as revisions
    import mode_trade_backtest
    import report_history_storage
    import report_artifacts
    import maturity_source_admission
    import trade_path_backtest

    d, path, scopes = cohort
    with sqlite3.connect(path) as conn:
        manifest = json.loads(conn.execute("SELECT manifest_json FROM trade_evidence_revision_batches_v1").fetchone()[0])
    request = request_for(d.preview(path, moment=moment()))
    p = d.preview(path, request=request, moment=moment())
    d.apply(path, request, expected_preview_sha256=p["preview_sha256"], moment=moment())
    monkeypatch.setattr(revisions.trade_backtest_store, "_path", lambda: path)
    monkeypatch.setattr(revisions.trade_backtest_store, "list_results", lambda **kw: [s["original_payload"] for s in scopes])
    def exact_result(*, report_filename, horizon_trading_days):
        assert horizon_trading_days == 10
        return next((s['original_payload'] for s in scopes if s['report_filename'] == report_filename), None)
    monkeypatch.setattr(revisions.trade_backtest_store, 'get_result', exact_result)
    monkeypatch.setattr(revisions, "session_window", lambda *a: {"status": "verified", "sessions": ["2026-10-05"]})
    monkeypatch.setattr(mode_trade_backtest, "_parsed_snapshot", lambda *a: {})
    monkeypatch.setattr(mode_trade_backtest, "_plan_inputs", lambda *a: ({"direction": "Long"}, (5, 10), ""))
    class Storage:
        def get_report(self, key):
            return SimpleNamespace(content=b'{"data":{}}')
    monkeypatch.setattr(report_history_storage, "storage_for_existing_output_dir", lambda *a: Storage())
    monkeypatch.setattr(report_artifacts.ReportArtifactLocator, "require_key", lambda *a, **kw: "fixture-key")
    monkeypatch.setattr(maturity_source_admission, "assess_maturity_source", lambda *a: {"eligible": False, "reason": "fixture_source_wait"})
    monkeypatch.setattr(trade_path_backtest, "evaluate_trade_path", lambda **kw: pytest.fail("no scoring without source evidence"))
    fetched = []
    result = revisions.run_due_revisions(output_dir="isolated", as_of=date(2026, 10, 22), bar_fetcher=lambda ticker, *a: fetched.append(ticker) or [])
    assert result["closed_unscored"] == 3
    assert result["already_terminal"] == 70
    assert result["awaiting_source_evidence"] == 3
    assert set(fetched) == {s["ticker"] for s in scopes[3:6]}
    assert not result["errors"]
    summary = revisions.revision_summary()
    assert summary["approved_scope_count"] == 76
    assert summary["terminal_scope_count"] == 70
    assert summary["unscored_disposition_scope_count"] == 3
    assert summary["remaining_scope_count"] == 3
    assert summary["settled_scope_count"] == 73
    assert summary["validated_strategy_results"] == 0
    assert manifest["rows"] == scopes
    # A validation refusal is a normal unscored result, distinct from exceptions.
    monkeypatch.setattr(maturity_source_admission, "assess_maturity_source", lambda *a: {"eligible": True})
    monkeypatch.setattr(mode_trade_backtest, "_execution_context", lambda *a: {})
    monkeypatch.setattr(trade_path_backtest, "evaluate_trade_path", lambda **kw: {"status": "insufficient_data", "reason": "plan_price_basis_unverified"})
    refused = revisions.run_due_revisions(output_dir="isolated", as_of=date(2026, 10, 22), bar_fetcher=lambda *a: [{"date": "2026-10-05"}])
    assert refused["validation_rejection_count"] == refused["new_revisions"] == 3
    assert not refused["errors"] and refused["awaiting_source_evidence"] == 0
    same_day = revisions.run_due_revisions(output_dir="isolated", as_of=date(2026, 10, 22), bar_fetcher=lambda *a: pytest.fail("same evidence day must not refetch"))
    assert same_day["already_attempted_session"] == 3 and same_day["closed_unscored"] == 3
    def broken(ticker, *args):
        if ticker == scopes[3]["ticker"]:
            raise OSError("fixture provider exception")
        return [{"date": "2026-10-05"}]
    next_day = revisions.run_due_revisions(output_dir="isolated", as_of=date(2026, 10, 23), bar_fetcher=broken)
    assert next_day["validation_rejection_count"] == 2 and len(next_day["errors"]) == 1
    assert next_day["errors"][0]["stage"] == "source_fetch"
    assert next_day["errors"][0]["exception_type"] == "OSError"
    assert next_day["already_attempted_session"] == 0
    assert next_day["as_of_evidence_session"] == "2026-10-23"
    # Identical scope IDs in another batch retain the old behavior.
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO trade_evidence_revision_batches_v1 VALUES('other','{}','other',1)")
    monkeypatch.setattr(revisions, "active_manifests", lambda: [{"batch_id": "other", "rows": [scopes[0]]}])
    monkeypatch.setattr(d, "active_for_path", lambda *a: pytest.fail("other batch must not read fixed-batch dispositions"))
    other = revisions.run_due_revisions(output_dir="isolated", as_of=date(2026, 10, 23), bar_fetcher=lambda *a: [{"date": "2026-10-05"}])
    assert other["closed_unscored"] == 0 and other["new_revisions"] == 1 and not other["errors"]


def test_dispositions_do_not_change_performance_hit_miss_or_denominator(cohort, monkeypatch):
    import legacy_evidence_revisions as revisions
    import decision_backtest_service as service
    d, path, scopes = cohort
    monkeypatch.setattr(revisions.trade_backtest_store, "_path", lambda: path)
    monkeypatch.setattr(revisions.trade_backtest_store, "list_results", lambda **kw: [s["original_payload"] for s in scopes])
    monkeypatch.setattr(service.decision_tracking_store, "list_backtest_results", lambda **kw: [])
    before = service.compute_performance_stats()
    request = request_for(d.preview(path, moment=moment()))
    p = d.preview(path, request=request, moment=moment())
    d.apply(path, request, expected_preview_sha256=p["preview_sha256"], moment=moment())
    after = service.compute_performance_stats()
    for field in ("summary", "by_horizon", "trade_summary", "trade_by_horizon", "population"):
        assert after[field] == before[field]
    assert after["trade_summary"]["scored_count"] == 0
    assert after["legacy_evidence_revisions"]["unscored_disposition_scope_count"] == 3


def test_journal_tampering_fails_closed(cohort):
    d, path, _ = cohort
    request = request_for(d.preview(path, moment=moment()), (0,))
    p = d.preview(path, request=request, moment=moment())
    d.apply(path, request, expected_preview_sha256=p["preview_sha256"], moment=moment())
    with sqlite3.connect(path) as conn:
        conn.execute(f"UPDATE {d.TABLE} SET payload_json='{{}}'")
    with pytest.raises(ValueError, match="integrity"):
        d.active_for_path(path)


def test_cli_preview_is_readonly_and_apply_requires_reviewed_fingerprint(cohort, capsys):
    import importlib.util
    from pathlib import Path
    d, path, _ = cohort
    spec = importlib.util.spec_from_file_location("disposition_cli", Path(__file__).resolve().parents[1] / "scripts/manage_legacy76_dispositions.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    before = path.read_bytes()
    assert cli.main(["preview", "--db", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["approved_scope_count"] == 76
    assert path.read_bytes() == before
    with pytest.raises(SystemExit):
        cli.main(["apply", "--db", str(path), "--request", "not-read.json"])
    assert path.read_bytes() == before


def test_concurrent_identical_request_is_idempotent_after_preview(cohort, monkeypatch):
    d, path, _ = cohort
    request = request_for(d.preview(path, moment=moment()))
    p = d.preview(path, request=request, moment=moment())
    connect = d._connect
    raced = []
    def interleaved(path, *, write=False):
        if write and not raced:
            raced.append(True)
            inner = d.apply(path, request, expected_preview_sha256=p["preview_sha256"], moment=moment())
            assert inner["appended_events"] == 3
        return connect(path, write=write)
    monkeypatch.setattr(d, "_connect", interleaved)
    result = d.apply(path, request, expected_preview_sha256=p["preview_sha256"], moment=moment())
    assert result["already_applied"] and result["appended_events"] == 0
    with sqlite3.connect(path) as conn:
        assert conn.execute(f"SELECT count(*) FROM {d.TABLE}").fetchone()[0] == 3


def test_insert_failure_rolls_back_whole_journal_request(cohort):
    d, path, scopes = cohort
    request = request_for(d.preview(path, moment=moment()))
    with sqlite3.connect(path) as conn:
        conn.execute(f"CREATE TABLE {d.TABLE}(sequence INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE,batch_id TEXT,scope_id TEXT,action TEXT,payload_json TEXT,created_at TEXT)")
        # Fixed hex fixture ID, never external SQL text.
        conn.execute(f"CREATE TRIGGER fixture_reject_second BEFORE INSERT ON {d.TABLE} WHEN NEW.scope_id='{scopes[1]['scope_id']}' BEGIN SELECT RAISE(ABORT,'fixture journal failure'); END")
    p = d.preview(path, request=request, moment=moment())
    before = original_tables(path)
    with pytest.raises(sqlite3.IntegrityError, match="fixture journal failure"):
        d.apply(path, request, expected_preview_sha256=p["preview_sha256"], moment=moment())
    with sqlite3.connect(path) as conn:
        assert conn.execute(f"SELECT count(*) FROM {d.TABLE}").fetchone()[0] == 0
    assert original_tables(path) == before
