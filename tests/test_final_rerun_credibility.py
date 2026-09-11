"""Final-only reruns cannot bypass the new source contract or rewrite upstream."""

import asyncio
import copy

import pytest
from fastapi import HTTPException

import report_rerun_service as service
from agent_runtime import audit_repair
from context_dependencies import upstream_agent_numbers
from market_context_assessment import assess_final_market_context
from market_context_manifest import build_market_context_manifest, build_source_blocks
from pipeline_modes import get_structured_agent_num
from test_market_context_manifest import source_data


def snapshot_for(pipeline="v1"):
    final = get_structured_agent_num("recommendation", pipeline)
    prior = upstream_agent_numbers(final, {"pipeline_id": pipeline})
    return {"ticker": "TEST", "pipeline": pipeline, "data": source_data(),
            "rerun_context": {"analyses": {str(agent): f"prior {agent}" for agent in (*prior, final)},
                              "structured_outputs": {str(agent): {"analysis_markdown": f"prior {agent}"} for agent in (*prior, final)},
                              "market_context_manifests": {str(final): {"old": True}}}}


@pytest.mark.parametrize("pipeline", ["v1", "v2", "v3"])
def test_final_rerun_starts_new_market_contract_without_old_final_sources(pipeline, tmp_path):
    snapshot = snapshot_for(pipeline)
    original = copy.deepcopy(snapshot)
    context, _, final = service._build_final_rerun_context(f"TEST_{pipeline}_report_20260906_010000.html", snapshot, str(tmp_path))
    assert context.get("market_context_contract_version") == "market_context.v1"
    assert context.get("market_context_manifests") == {}
    assert final not in context["analyses"] and final not in context["structured_outputs"]
    prior = next(iter(context["structured_outputs"]))
    context["structured_outputs"][prior]["analysis_markdown"] = "local candidate mutation"
    assert snapshot == original


@pytest.mark.parametrize("missing", [11, 20, 21])
def test_final_rerun_requires_all_prior_groups_not_numeric_agent_order(missing, tmp_path, monkeypatch):
    snapshot = snapshot_for()
    snapshot["rerun_context"]["analyses"].pop(str(missing))
    monkeypatch.setattr(service, "read_report_markdown", lambda *a, **k: "")
    with pytest.raises(HTTPException) as raised:
        service._build_final_rerun_context("TEST_v1_report_20260906_010000.html", snapshot, str(tmp_path))
    assert raised.value.status_code == 409
    assert str(missing) in raised.value.detail


def workflow(monkeypatch, tmp_path, *, kind="valid", repair_kind=None, upstream_critical=False):
    snapshot = snapshot_for()
    rendered, repairs = [], []

    def produce(context, mode):
        data = context["data"]
        blocks = build_source_blocks(data, agent_num=7)
        manifest = build_market_context_manifest(data, "\n".join(b["text"] for b in blocks), blocks, agent_num=7)
        context["market_context_manifests"] = {7: manifest}
        assessment = {source: {"impact": "no_material_impact", "reason": "利率與需求資訊尚未改變本次等待決策。", "source_refs": info["visible_refs"][:1]}
                      for source, info in manifest["sources"].items()}
        if mode == "forged":
            assessment["international_news_context"]["source_refs"] = ["mc:model-invented"]
        context["structured_outputs"][7] = {"market_context_assessment": assessment if mode != "missing" else None}
        context["analyses"][7] = "[Agent 7 執行失敗] fixture failure" if mode == "failed" else "new final decision"
        return 7, context["analyses"][7]

    async def generate(agent, data, context, rotator):
        return produce(context, kind)

    def audit(context, append_section=True):
        market = assess_final_market_context(context)
        result = {"status": "needs_attention" if market["critical"] else "passed", "critical": market["critical"],
                  "warnings": market["warnings"], "repair_agent_issues": market["repair_agent_issues"],
                  "coverage_repair_agent_issues": market["coverage_repair_agent_issues"], "market_context": market}
        if upstream_critical:
            result.update(critical=["valuation requires raw-source correction"], repair_agent_issues={4: ["upstream correction"]})
        return result

    async def repair(context, audit_result, rotator, progress_callback=None):
        requests = {*audit_result.get("repair_agent_issues", {}), *audit_result.get("coverage_repair_agent_issues", {})}
        repairs.append(requests)
        if repair_kind is not None:
            produce(context, repair_kind)
        return True

    async def render(**kwargs):
        rendered.append(copy.deepcopy(kwargs["context"]))
        return {"success": True}

    monkeypatch.setattr(service, "KeyRotator", lambda *a: object())
    monkeypatch.setattr(service, "run_agent_with_quality_gates_async", generate)
    monkeypatch.setattr(service, "run_final_report_audit", audit)
    monkeypatch.setattr(service, "parse_structured_data", lambda context: {})
    monkeypatch.setattr(service, "render_and_save_rerun_report", render)
    monkeypatch.setattr(audit_repair, "attempt_final_audit_repair_async", repair)
    monkeypatch.setattr(audit_repair, "MAX_REPAIR_ITERATIONS", 1)

    def run():
        return asyncio.run(service._run_final_recommendation_rerun(
            filename="TEST_v1_report_20260906_010000.html", snapshot=snapshot, output_dir=str(tmp_path), report_renderer=object()))

    return run, rendered, repairs, snapshot


def test_normal_final_rerun_publishes_only_new_final_and_keeps_snapshot_readonly(monkeypatch, tmp_path):
    run, rendered, repairs, snapshot = workflow(monkeypatch, tmp_path)
    original = copy.deepcopy(snapshot)
    assert run()["success"]
    assert rendered[0]["final_audit"]["market_context"]["status"] == "passed"
    assert not repairs and snapshot == original


def test_forged_final_source_is_repaired_before_render(monkeypatch, tmp_path):
    run, rendered, repairs, _ = workflow(monkeypatch, tmp_path, kind="forged", repair_kind="valid")
    assert run()["success"]
    assert repairs == [{7}]
    assert rendered[0]["final_audit"]["market_context"]["status"] == "passed"


@pytest.mark.parametrize("kind", ["forged", "failed"])
def test_unresolved_final_failure_never_calls_renderer_or_persistence(monkeypatch, tmp_path, kind):
    run, rendered, repairs, _ = workflow(monkeypatch, tmp_path, kind=kind)
    with pytest.raises(HTTPException) as raised:
        run()
    assert raised.value.status_code == 409
    assert not rendered
    assert repairs == ([{7}] if kind == "forged" else [])


def test_coverage_exhaustion_stays_warning_without_fabricating_assessment(monkeypatch, tmp_path):
    run, rendered, repairs, _ = workflow(monkeypatch, tmp_path, kind="missing")
    assert run()["success"]
    assert repairs == [{7}]
    audit = rendered[0]["final_audit"]
    assert not audit["critical"] and audit["market_context"]["status"] == "warning"
    assert all(item["impact"] == "not_assessed" for item in audit["market_context"]["assessment"].values())


def test_upstream_critical_requires_full_rerun_without_repair_or_render(monkeypatch, tmp_path):
    run, rendered, repairs, snapshot = workflow(monkeypatch, tmp_path, upstream_critical=True)
    original = copy.deepcopy(snapshot)
    with pytest.raises(HTTPException) as raised:
        run()
    assert raised.value.status_code == 409 and "完整重跑" in raised.value.detail
    assert not rendered and not repairs and snapshot == original


@pytest.mark.parametrize("kind,repair_ok", [("forged", True), ("missing", False)])
def test_real_repair_round_is_final_only_and_optional_failure_stays_warning(monkeypatch, tmp_path, kind, repair_ok):
    real_attempt = audit_repair.attempt_final_audit_repair_async
    run, rendered, _, _ = workflow(monkeypatch, tmp_path, kind=kind)
    agents = []

    async def rewrite(agent, data, context, rotator, issues):
        agents.append(agent)
        if repair_ok:
            context["analyses"][agent] = "new repaired final"
            for source, item in context["structured_outputs"][agent]["market_context_assessment"].items():
                item["source_refs"] = context["market_context_manifests"][agent]["sources"][source]["visible_refs"][:1]
        return repair_ok, "fixture final-only rewrite"

    monkeypatch.setattr(audit_repair, "attempt_final_audit_repair_async", real_attempt)
    monkeypatch.setattr(audit_repair, "_repair_agent_output_async", rewrite)
    assert run()["success"]
    assert agents == [7]
    assert not rendered[0]["final_audit"]["critical"]
    assert rendered[0]["final_audit"]["market_context"]["status"] == ("passed" if repair_ok else "warning")


def test_missing_prior_snapshot_and_markdown_require_full_rerun(tmp_path):
    snapshot = snapshot_for()
    snapshot["rerun_context"]["analyses"] = {"7": "old final only"}
    with pytest.raises(HTTPException) as raised:
        service._build_final_rerun_context("TEST_v1_report_20260906_010000.html", snapshot, str(tmp_path))
    assert raised.value.status_code == 409
    assert "完整重跑" in raised.value.detail


def test_initial_final_generation_cannot_rewrite_prior_analysis(monkeypatch, tmp_path):
    run, rendered, repairs, snapshot = workflow(monkeypatch, tmp_path)
    original = copy.deepcopy(snapshot)
    generate = service.run_agent_with_quality_gates_async

    async def mutate_prior(*args):
        result = await generate(*args)
        args[2]["analyses"][4] = "unauthorized upstream revision"
        return result

    monkeypatch.setattr(service, "run_agent_with_quality_gates_async", mutate_prior)
    with pytest.raises(HTTPException) as raised:
        run()
    assert raised.value.status_code == 409
    assert not rendered and not repairs and snapshot == original


def test_final_rerun_with_unavailable_optional_sources_warns_without_repair(monkeypatch, tmp_path):
    run, rendered, repairs, snapshot = workflow(monkeypatch, tmp_path, kind="missing")
    for source in ("global_market_context", "international_news_context"):
        snapshot["data"].pop(source)
    assert run()["success"]
    assert not repairs
    assert {check["reason_code"] for check in rendered[0]["final_audit"]["market_context"]["checks"]} == {"source_unavailable"}


@pytest.mark.parametrize("stage", ["generate", "repair"])
@pytest.mark.parametrize("failure", ["cancelled", "deferred"])
def test_final_rerun_interruption_propagates_without_render(monkeypatch, tmp_path, stage, failure):
    from agent_runtime.deferred import AgentDeferredError

    run, rendered, _, snapshot = workflow(monkeypatch, tmp_path, kind="forged")
    original = copy.deepcopy(snapshot)
    error = (asyncio.CancelledError() if failure == "cancelled" else
             AgentDeferredError(7, [{"model_id": "fixture", "retry_wait_seconds": 60}]))

    async def interrupt(*args, **kwargs):
        raise error

    if stage == "generate":
        monkeypatch.setattr(service, "run_agent_with_quality_gates_async", interrupt)
    else:
        monkeypatch.setattr(audit_repair, "attempt_final_audit_repair_async", interrupt)
    with pytest.raises(type(error)):
        run()
    assert not rendered and snapshot == original
