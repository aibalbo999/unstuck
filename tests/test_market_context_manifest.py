"""Market refs describe complete evidence in the successful prompt only."""

import copy
import importlib
import importlib.util

import pytest


def manifest_module():
    assert importlib.util.find_spec("market_context_manifest") is not None, "Runtime-issued source manifests are required"
    return importlib.import_module("market_context_manifest")


def source_data():
    return {
        "ticker": "TEST", "company_name": "Test company", "current_price": 100,
        "global_market_context": {"items": [{"symbol": "QQQ", "change_1d_pct": 2, "source": "market"}]},
        "international_news_context": {"topics": [
            {"headline": "Supply outlook", "summary": "Demand remains uncertain", "source": "wire"},
            {"headline": "Rates decision", "summary": "Discount rate may rise", "source": "issuer"},
            {"headline": "Third topic", "summary": "Not present in compact prompt", "source": "wire"},
        ]},
    }


def test_partial_source_body_or_ref_alone_does_not_count_as_visible():
    module = manifest_module()
    block = {"id": "source-1", "text": "完整來源：央行利率新聞與來源網址"}
    assert module.visible_source_items(block["text"], [block]) == [block]
    assert module.visible_source_items(block["text"][:8], [block]) == []
    assert module.visible_source_items(block["id"], [block]) == []


def test_compact_manifest_keeps_canonical_indices_and_only_visible_refs():
    module = manifest_module()
    data = source_data()
    blocks = module.build_source_blocks(data, agent_num=7, compact=True)
    prompt = "\n".join(block["text"] for block in blocks)
    manifest = module.build_market_context_manifest(data, prompt, blocks, agent_num=7)
    assert len(manifest["sources"]["international_news_context"]["visible_refs"]) == 2
    assert manifest["sources"]["international_news_context"]["available_count"] == 3
    assert {item["path"] for item in manifest["items"]} == {
        "data.global_market_context.items[0]", "data.international_news_context.topics[0]",
        "data.international_news_context.topics[1]",
    }
    assert all(item["item_hash"] and item["block_hash"] for item in manifest["items"])
    assert "Third topic" not in prompt


def test_identical_content_at_another_path_or_input_has_distinct_refs():
    module = manifest_module()
    data = source_data()
    data["international_news_context"]["topics"] = [{"headline": "Same"}, {"headline": "Same"}]
    blocks = module.build_source_blocks(data, agent_num=7)
    assert len({block["ref"] for block in blocks}) == len(blocks)
    changed = copy.deepcopy(data)
    changed["ticker"] = "OTHER"
    assert {block["ref"] for block in blocks}.isdisjoint(
        {block["ref"] for block in module.build_source_blocks(changed, agent_num=7)})


def test_input_fingerprint_excludes_generated_manifest_and_final_snapshot_hash():
    module = manifest_module()
    data = source_data()
    decorated = {**data, "market_context_manifests": {7: {"hash": "later"}}, "snapshot_hash": "later", "content_hash": "later"}
    assert module.market_input_fingerprint(data) == module.market_input_fingerprint(decorated)


def test_real_prompt_final_budget_selects_intact_blocks_only(monkeypatch):
    module = manifest_module()
    from agent_runtime import prompting

    data = source_data()
    context = {"pipeline_id": "v1", "market_context_contract_version": "market_context.v1"}
    monkeypatch.setattr(prompting, "_enforce_prompt_token_budget", lambda prompt, *a, **k: prompt[:200])
    prompt = prompting.build_prompt(7, data, context)
    candidate = context["_market_context_attempt_manifests"][7]
    assert candidate["prompt_hash"] == module.prompt_fingerprint(prompt)
    assert candidate["items"] == []
    assert candidate["sources"]["international_news_context"]["omission_reason"] == "prompt_omitted"
    assert not context.get("market_context_manifests")


def test_manifest_cannot_lie_about_source_availability():
    module = manifest_module()
    data = source_data()
    blocks = module.build_source_blocks(data, agent_num=7)
    manifest = module.build_market_context_manifest(data, "\n".join(b["text"] for b in blocks), blocks, agent_num=7)
    manifest["sources"]["international_news_context"]["availability"] = "unavailable"
    assert not module.manifest_matches_input(manifest, data, 7)


def test_prompt_rules_require_shared_market_assessment_and_unavailable_dcf_exception():
    from prompt_rules import build_agent_rule_block
    from structured_output_models import build_structured_output_instruction

    for agent in (7, 16, 19):
        rules = build_structured_output_instruction(agent)
        assert "market_context_assessment" in rules
        assert "source_refs" in rules and "no_material_impact" in rules
        assert "完整" in build_agent_rule_block("data_enrichment_instructions", agent)
    for agent in (4, 14):
        assert "metric_status" in build_agent_rule_block("numeric_tool_instructions", agent)


@pytest.mark.parametrize("field,value", [("ref", []), ("index", False)])
def test_malformed_manifest_identity_fails_closed_without_crashing(field, value):
    module = manifest_module()
    data = source_data()
    blocks = module.build_source_blocks(data, agent_num=7)
    manifest = module.build_market_context_manifest(data, "\n".join(b["text"] for b in blocks), blocks, agent_num=7)
    manifest["items"][0][field] = value
    assert module.manifest_matches_input(manifest, data, 7) is False


def test_compact_category_selection_can_bind_an_original_index_after_32():
    module = manifest_module()
    data = source_data()
    data["global_market_context"]["items"] = [{"symbol": f"same-{i}", "category": "equity", "latest": 100} for i in range(35)]
    data["global_market_context"]["items"] += [{"symbol": "BOND", "category": "bond", "latest": 100}, {"symbol": "OIL", "category": "commodity", "latest": 100}]
    blocks = module.build_source_blocks(data, agent_num=7, compact=True)
    manifest = module.build_market_context_manifest(data, "\n".join(b["text"] for b in blocks), blocks, agent_num=7)
    assert any(item["index"] == 35 for item in manifest["items"])
    assert module.manifest_matches_input(manifest, data, 7)
