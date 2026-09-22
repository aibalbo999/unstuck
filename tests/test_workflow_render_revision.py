"""Revision endpoints survive a real cold SQLite resume without rewriting inputs."""
import asyncio
from types import SimpleNamespace

import pytest
from langgraph.graph import END, START, StateGraph

import report_reproducibility
import workflow_services
from analysis_input_provenance import freeze_analysis_inputs
from data_trust_snapshot import build_data_snapshot
from report_analysis_evidence import capture_analysis_evidence
from workflow_checkpoints import execute_persistent_graph
from workflow_context import legacy_context_from_graph
from workflow_state import AgentGraphState


def test_cold_sqlite_resume_records_render_revision_preserving_start_and_input(tmp_path, monkeypatch):
    runtime = {"commit": "a" * 40, "dirty": False}
    monkeypatch.setattr(workflow_services, "runtime_code_identity", lambda: dict(runtime))
    monkeypatch.setattr(report_reproducibility, "runtime_code_identity", lambda: dict(runtime), raising=False)
    data = {"ticker": "2305.TW", "current_price": 35, "source_audit": [
        {"provider": "fixture", "fetched_at": "2026-09-22T10:00:00Z"}]}
    frozen = freeze_analysis_inputs(data, cutoff="2026-09-22T10:00:00Z")
    initial = workflow_services.initialize_graph_state(data, pipeline_id="v4")
    calls, snapshots = [], []

    def builder(defer):
        graph = StateGraph(AgentGraphState)
        async def completed(state):
            calls.append(("completed", runtime["commit"]))
            return {"execution_trace": [{"id": "completed"}]}
        async def render(state):
            calls.append(("render", runtime["commit"]))
            if defer:
                raise RuntimeError("fixture provider temporarily unavailable")
            context = legacy_context_from_graph(state, SimpleNamespace(progress_callback=None, cancel_check=None))
            snapshots.append(build_data_snapshot(context))
            return {"status": "done"}
        graph.add_node("completed", completed)
        graph.add_node("render", render)
        graph.add_edge(START, "completed")
        graph.add_edge("completed", "render")
        graph.add_edge("render", END)
        return graph

    def run(defer, fresh):
        return asyncio.run(execute_persistent_graph(graph_builder=builder(defer), initial_state=fresh,
            thread_id="same-frozen-input", checkpoint_path=tmp_path / "checkpoint.sqlite3"))
    with pytest.raises(RuntimeError, match="fixture provider"):
        run(True, initial)
    runtime.update(commit="b" * 40, dirty=True)
    # A new worker can construct different initial data; persisted input must win.
    new_initial = workflow_services.initialize_graph_state({"ticker": "2305.TW", "current_price": 999}, pipeline_id="v4")
    resumed = run(False, new_initial)
    assert calls == [("completed", "a" * 40), ("render", "a" * 40), ("render", "b" * 40)]
    assert resumed["code_commit"] == "a" * 40
    packet = snapshots[0]["reproducibility_packet"]
    assert packet["code_commit"] == "a" * 40
    assert packet["code_dirty"] is False
    assert packet["analysis_input_hash"] == frozen["analysis_input_hash"]
    assert snapshots[0]["data"]["current_price"] == 35
    evidence = capture_analysis_evidence({"data": snapshots[0]["data"]})
    assert evidence["input_verification"] == "hash_verified"
    assert packet["render_runtime_commit"] == "b" * 40
    assert packet["render_runtime_dirty"] is True
    assert packet["analysis_start_vs_render_revision_mismatch"] is True
    assert packet["revision_provenance_scope"] == "analysis_start_and_report_render_endpoints_only"


@pytest.mark.parametrize("start,render,expected", [
    ("a" * 40, "a" * 40, False), ("a" * 40, "b" * 40, True),
    ("", "a" * 40, None), ("a" * 40, "", None), ("", "", None),
])
def test_revision_endpoint_unknown_is_not_inferred_from_environment(monkeypatch, start, render, expected):
    monkeypatch.setenv("GIT_COMMIT", "e" * 40)
    monkeypatch.setattr(report_reproducibility, "runtime_code_identity",
                        lambda: {"commit": render, "dirty": None}, raising=False)
    context = {"code_commit": start, "code_dirty": False,
               "render_runtime_commit": "stale-context-must-not-win"}
    packet = report_reproducibility.build_reproducibility_packet(context, {}, "2026-09-22")
    assert packet["code_commit"] == (start or "e" * 40)  # Preserve the legacy field contract.
    assert packet["render_runtime_commit"] == (render or None)
    assert packet["render_runtime_dirty"] is None
    assert packet["analysis_start_vs_render_revision_mismatch"] is expected


def test_mixed_revision_report_html_and_markdown_show_both_endpoints(monkeypatch):
    from reporting.trust_controls import build_trust_controls_html, build_trust_controls_markdown
    monkeypatch.setattr(report_reproducibility, "runtime_code_identity",
                        lambda: {"commit": "<b&>", "dirty": True})
    context = {"code_commit": "<a&>", "code_dirty": False}
    html = build_trust_controls_html({}, context)
    markdown = "\n".join(build_trust_controls_markdown({}, context))
    assert "&lt;a&amp;&gt;" in html and "&lt;b&amp;&gt;" in html
    assert "<a&>" not in html and "<b&>" not in html
    for rendered in (html, markdown):
        assert "任務起始" in rendered and "報告產出" in rendered
        assert "僅記錄兩端，不代表所有節點使用同一版本" in rendered
        assert "含未提交變更" in rendered
    assert "<a&>" in markdown and "<b&>" in markdown


@pytest.mark.parametrize("dirty,suffix", [(False, "乾淨"), (True, "含未提交變更"), (None, "工作樹狀態未知")])
def test_same_revision_preserves_existing_display(monkeypatch, dirty, suffix):
    from reporting.trust_controls import build_trust_controls_markdown
    monkeypatch.setattr(report_reproducibility, "runtime_code_identity",
                        lambda: {"commit": "a" * 40, "dirty": dirty})
    markdown = "\n".join(build_trust_controls_markdown({}, {"code_commit": "a" * 40, "code_dirty": dirty}))
    assert f"程式碼狀態：{'a' * 12}（{suffix}）" in markdown
    assert "報告產出" not in markdown


@pytest.mark.parametrize('render_dirty,label', [(True, '含未提交變更'), (None, '工作樹狀態未知')])
def test_same_commit_render_dirty_or_unknown_does_not_display_only_clean_start(monkeypatch, render_dirty, label):
    from reporting.trust_controls import build_trust_controls_html, build_trust_controls_markdown
    monkeypatch.setattr(report_reproducibility, 'runtime_code_identity',
                        lambda: {'commit': 'a' * 40, 'dirty': render_dirty})
    context = {'code_commit': 'a' * 40, 'code_dirty': False}
    packet = report_reproducibility.build_reproducibility_packet(context, {}, '2026-09-22')
    assert packet['analysis_start_vs_render_revision_mismatch'] is False
    for rendered in (build_trust_controls_html({}, context), '\n'.join(build_trust_controls_markdown({}, context))):
        assert '任務起始' in rendered and '報告產出' in rendered
        assert label in rendered


@pytest.mark.parametrize('start_dirty', [False, True, None])
def test_unknown_start_env_fallback_is_never_labelled_as_original_revision(monkeypatch, start_dirty):
    from reporting.trust_controls import build_trust_controls_html, build_trust_controls_markdown
    monkeypatch.setenv('GIT_COMMIT', 'a' * 40)
    monkeypatch.setattr(report_reproducibility, 'runtime_code_identity',
                        lambda: {'commit': 'a' * 40, 'dirty': False})
    context = {'code_dirty': start_dirty}
    packet = report_reproducibility.build_reproducibility_packet(context, {}, '2026-09-22')
    assert packet['code_commit'] == 'a' * 40  # legacy compatibility only, not start proof
    assert packet['analysis_start_vs_render_revision_mismatch'] is None
    for rendered in (build_trust_controls_html({}, context), '\n'.join(build_trust_controls_markdown({}, context))):
        assert '任務起始版本未知' in rendered
        assert f"報告產出：{'a' * 12}（乾淨）" in rendered
        assert f"程式碼狀態：{'a' * 12}" not in rendered
