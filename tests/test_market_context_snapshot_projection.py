"""Snapshot size governance must not launder raw market-source assertions."""

import copy

import pytest

from test_market_context_assessment import assessment_context, assessment_module


def _context():
    context = assessment_context()
    context["parsed"] = {"recommendation": {"建議": "等待", "信心": 50}}
    context["final_audit"] = {"status": "passed", "critical": [], "warnings": []}
    return context


def test_oversized_snapshot_preserves_raw_forged_ref_and_critical_verdict():
    from data_trust_snapshot import build_data_snapshot

    context = _context()
    raw = context["structured_outputs"][7]["market_context_assessment"]
    raw["international_news_context"]["source_refs"] = ["MODEL_INVENTED_REFERENCE"]
    before = copy.deepcopy(context)
    assert assessment_module().assess_final_market_context(context)["status"] == "critical"

    snapshot = build_data_snapshot(context, max_bytes=400)
    assert "structured_outputs" not in snapshot["rerun_context"]
    restored = assessment_module().assess_final_market_context(snapshot)
    assert restored["status"] == "critical"
    assert snapshot["market_context_raw_assessment"] == raw
    assert context == before


def test_governance_of_unrelated_data_keeps_valid_source_assertions_valid():
    from data_trust_snapshot import build_data_snapshot

    context = _context()
    context["data"]["large_noncore_field"] = "x" * 20_000
    context = {**assessment_context(data=context["data"]), "parsed": context["parsed"]}
    before = copy.deepcopy(context)
    snapshot = build_data_snapshot(context, max_bytes=400)
    assert "large_noncore_field" not in snapshot["data"]
    assert assessment_module().assess_final_market_context(snapshot)["status"] == "passed"
    assert context == before


@pytest.mark.parametrize("oversized", [False, True])
def test_current_content_projection_rejects_sources_changed_after_recorded_audit(oversized):
    from data_trust_snapshot import build_data_snapshot
    from reporting.content_credibility import evaluate_content_credibility
    from reporting.content_credibility_projection import project_content_credibility
    from reporting.market_context import final_market_report_text

    snapshot = build_data_snapshot(_context(), max_bytes=400 if oversized else 2_000_000)
    snapshot["data"]["international_news_context"]["topics"][0]["headline"] = "Changed source"
    before = copy.deepcopy(snapshot)
    context = {**snapshot, **snapshot["rerun_context"]}
    assert "來源引用無法綁定" in final_market_report_text(context, 7, "Original report")

    direct = evaluate_content_credibility(context, snapshot)
    projected = project_content_credibility(snapshot)
    assert direct["status"] == "blocked"
    assert projected is not None and projected["status"] == "blocked"
    for result in (direct, projected):
        check = next(item for item in result["checks"] if item["id"] == "market_context_assessment")
        assert check["details"] == assessment_module().assess_final_market_context(context)
    assert snapshot == before


@pytest.mark.parametrize("changed", ["source", "price", "receipt", "manifest", "claim", "refresh"])
def test_preservation_receipt_cannot_authorize_changed_snapshot_inputs(changed):
    from data_trust_snapshot import build_data_snapshot
    from market_context_manifest import manifest_matches_input

    data = _context()["data"]
    data["large_noncore_field"] = "x" * 20_000
    context = assessment_context(data=data)
    snapshot = build_data_snapshot(context, max_bytes=400)
    assert snapshot["market_context_snapshot_receipts"]
    # Runtime validation never implicitly trusts a snapshot's preservation receipt.
    assert not manifest_matches_input(snapshot["market_context_manifests"]["7"], snapshot["data"], 7)
    if changed == "source":
        snapshot["data"]["international_news_context"]["topics"][0]["headline"] = "Changed"
    elif changed == "price":
        snapshot["data"]["current_price"] = 999
    elif changed == "receipt":
        snapshot["market_context_snapshot_receipts"]["7"]["manifest_hash"] = "0" * 64
    elif changed == "manifest":
        snapshot["market_context_manifests"]["7"]["prompt_hash"] = "0" * 64
    elif changed == "claim":
        snapshot["market_context_raw_assessment"]["international_news_context"]["reason"] = "Changed claim"
    else:
        refreshed_context = {**snapshot, **snapshot["rerun_context"], "pipeline_id": "v1"}
        refreshed_context["data"]["current_price"] = 999
        refreshed_context["structured_outputs"] = {7: {
            "market_context_assessment": snapshot["market_context_raw_assessment"]}}
        snapshot = build_data_snapshot(refreshed_context, max_bytes=400)
        assert not snapshot.get("market_context_snapshot_receipts")
    assert assessment_module().assess_final_market_context(snapshot)["status"] == "critical"


def test_invalid_original_manifest_cannot_obtain_a_preservation_receipt():
    from data_trust_snapshot import build_data_snapshot

    context = _context()
    context["data"]["large_noncore_field"] = "x" * 20_000  # Added AFTER the runtime manifest.
    snapshot = build_data_snapshot(context, max_bytes=400)
    assert not snapshot.get("market_context_snapshot_receipts")
    assert assessment_module().assess_final_market_context(snapshot)["status"] == "critical"


def test_display_projection_is_not_used_as_raw_claim_when_original_is_unavailable():
    from data_trust_snapshot import build_data_snapshot

    snapshot = build_data_snapshot(_context(), max_bytes=400)
    snapshot.pop("market_context_raw_assessment")
    assert snapshot["market_context_assessment"]["international_news_context"]["impact"] == "no_material_impact"
    assert assessment_module().assess_final_market_context(snapshot)["status"] == "warning"
