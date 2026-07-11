import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import prompt_loader  # noqa: E402
import prompt_rules  # noqa: E402
from prompt_loader import load_agent_prompt_config  # noqa: E402


def test_sample_financial_fixture_covers_final_agent_quality_inputs():
    fixture = json.loads((ROOT / "tests" / "fixtures" / "sample_financial_data.json").read_text(encoding="utf-8"))

    assert fixture["ticker"].endswith(".TW")
    assert fixture["quant_metrics"]["calculations"]["dcf_scenarios_default"]["base"]["price_per_share_twd"] > 0
    assert fixture["data_trust"]["status"] == "fresh"


def test_final_agent_prompts_preserve_risk_and_quality_contracts():
    config = load_agent_prompt_config()
    agents = config["analysis_prompts"]
    systems = config["system_prompts"]

    agent7 = systems["7"] + "\n" + agents["7"]
    agent16 = systems["16"] + "\n" + agents["16"]
    agent19 = systems["19"] + "\n" + agents["19"]

    assert "[風險評估]" in agent7
    assert "不可給出「買入/持有/避免」" in agent7 or "不可提供「買入」" in agent7
    assert "confidence_basis" in agent7 or "信心" in agent7

    assert "[風險評估]" in agent16
    assert "情境觸發器" in agent16 or "scenario_triggers" in agent16
    assert "不可給出「買入/持有/避免」" in agent16 or "不可提供「買入」" in agent16

    assert "做空觸發條件（Catalyst for crash）" in agent19
    assert "防軋空停損點（Stop-loss level）" in agent19
    assert "[投資建議]" in agent19
    assert "no text may appear after [/投資建議]" in agent19 or "不得在 [/投資建議] 後添加任何文字" in agent19


def test_agent_prompt_config_validates_schema_and_exposes_prompt_version(tmp_path):
    config = load_agent_prompt_config()

    assert config["version"] == 2
    assert len(config["prompt_fingerprint"]) == 64
    assert config["prompt_version"] == f"agents:v2:{config['prompt_fingerprint'][:16]}"

    invalid = tmp_path / "bad_agents.json"
    invalid.write_text(
        json.dumps(
            {
                "version": 1,
                "description": "bad fixture",
                "state_view_policy": {},
                "system_prompts": {"1": ""},
                "analysis_prompts": {"1": "ok"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    try:
        load_agent_prompt_config(str(invalid))
    except ValueError as exc:
        assert "Prompt config schema invalid" in str(exc)
    else:
        raise AssertionError("invalid prompt config should fail schema validation")


def test_agent_prompt_config_rejects_unknown_jinja_variables(tmp_path):
    config = json.loads((ROOT / "backend" / "prompts" / "agents.json").read_text(encoding="utf-8"))
    config["analysis_prompts"]["1"] = "分析 {{ ticker }} 與 {{ typo_field }}"
    invalid = tmp_path / "unknown_jinja_variable.json"
    invalid.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    try:
        load_agent_prompt_config(str(invalid))
    except ValueError as exc:
        assert "unknown Jinja variables" in str(exc)
        assert "typo_field" in str(exc)
    else:
        raise AssertionError("unknown Jinja variables should fail prompt config validation")


def test_agent_prompt_config_rejects_invalid_jinja_syntax(tmp_path):
    config = json.loads((ROOT / "backend" / "prompts" / "agents.json").read_text(encoding="utf-8"))
    config["analysis_prompts"]["1"] = "分析 {{ ticker"
    invalid = tmp_path / "invalid_jinja_syntax.json"
    invalid.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    try:
        load_agent_prompt_config(str(invalid))
    except ValueError as exc:
        assert "invalid Jinja syntax" in str(exc)
        assert "prompt 1" in str(exc)
    else:
        raise AssertionError("invalid Jinja syntax should fail prompt config validation")


def test_agent_prompt_config_keeps_legacy_placeholder_compatibility(tmp_path):
    config = json.loads((ROOT / "backend" / "prompts" / "agents.json").read_text(encoding="utf-8"))
    config["analysis_prompts"]["1"] = "分析 {ticker}"
    legacy = tmp_path / "legacy_placeholder.json"
    legacy.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    loaded = load_agent_prompt_config(str(legacy))

    assert loaded["analysis_prompts"]["1"] == "分析 {ticker}"


def test_prompt_identity_changes_when_same_version_content_changes(tmp_path):
    original = json.loads((ROOT / "backend" / "prompts" / "agents.json").read_text(encoding="utf-8"))
    changed = json.loads(json.dumps(original, ensure_ascii=False))
    changed["analysis_prompts"]["1"] += "\n內容身份測試"
    original_path = tmp_path / "original_agents.json"
    changed_path = tmp_path / "changed_agents.json"
    original_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    changed_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")

    original_config = load_agent_prompt_config(str(original_path))
    changed_config = load_agent_prompt_config(str(changed_path))

    assert original_config["prompt_version"] != changed_config["prompt_version"]
    assert len(original_config["prompt_fingerprint"]) == 64
    assert len(changed_config["prompt_fingerprint"]) == 64
    assert original_config["prompt_version"].startswith("agents:v2:")
    assert changed_config["prompt_version"].startswith("agents:v2:")


def test_prompt_identity_is_canonical_across_description_and_key_order(tmp_path):
    original = json.loads((ROOT / "backend" / "prompts" / "agents.json").read_text(encoding="utf-8"))
    reordered = json.loads(json.dumps(original, ensure_ascii=False))
    reordered["description"] = "non-execution documentation changed"
    reordered["system_prompts"] = dict(reversed(list(reordered["system_prompts"].items())))
    reordered["analysis_prompts"] = dict(reversed(list(reordered["analysis_prompts"].items())))
    original_path = tmp_path / "canonical_original.json"
    reordered_path = tmp_path / "canonical_reordered.json"
    original_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    reordered_path.write_text(json.dumps(reordered, ensure_ascii=False), encoding="utf-8")

    original_config = load_agent_prompt_config(str(original_path))
    reordered_config = load_agent_prompt_config(str(reordered_path))

    assert original_config["prompt_fingerprint"] == reordered_config["prompt_fingerprint"]
    assert original_config["prompt_version"] == reordered_config["prompt_version"]


def test_prompt_identity_changes_when_runtime_rules_change(tmp_path):
    agents = json.loads((ROOT / "backend" / "prompts" / "agents.json").read_text(encoding="utf-8"))
    original_rules = json.loads((ROOT / "backend" / "prompts" / "runtime_rules.json").read_text(encoding="utf-8"))
    changed_rules = json.loads(json.dumps(original_rules, ensure_ascii=False))
    changed_rules["output_cleanliness_rule"]["rules"].append("內容身份測試規則")
    agents_path = tmp_path / "agents.json"
    original_rules_path = tmp_path / "original_runtime_rules.json"
    changed_rules_path = tmp_path / "changed_runtime_rules.json"
    agents_path.write_text(json.dumps(agents, ensure_ascii=False), encoding="utf-8")
    original_rules_path.write_text(json.dumps(original_rules, ensure_ascii=False), encoding="utf-8")
    changed_rules_path.write_text(json.dumps(changed_rules, ensure_ascii=False), encoding="utf-8")

    original_config = load_agent_prompt_config(str(agents_path), str(original_rules_path))
    changed_config = load_agent_prompt_config(str(agents_path), str(changed_rules_path))

    assert original_config["prompt_fingerprint"] != changed_config["prompt_fingerprint"]
    assert original_config["prompt_version"] != changed_config["prompt_version"]


def test_prompt_config_rejects_non_object_runtime_rules(tmp_path):
    agents = ROOT / "backend" / "prompts" / "agents.json"
    invalid_rules = tmp_path / "invalid_runtime_rules.json"
    invalid_rules.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    try:
        load_agent_prompt_config(str(agents), str(invalid_rules))
    except ValueError as exc:
        assert "Runtime prompt rules root must be an object" in str(exc)
    else:
        raise AssertionError("non-object runtime rules should fail prompt config validation")


def test_prompt_identity_and_injection_share_runtime_rules_snapshot(tmp_path, monkeypatch):
    agents = json.loads((ROOT / "backend" / "prompts" / "agents.json").read_text(encoding="utf-8"))
    runtime_rules = json.loads(
        (ROOT / "backend" / "prompts" / "runtime_rules.json").read_text(encoding="utf-8")
    )
    runtime_rules["output_cleanliness_rule"]["title"] = "SNAPSHOT_A"
    agents_path = tmp_path / "agents.json"
    rules_path = tmp_path / "runtime_rules.json"
    agents_path.write_text(json.dumps(agents, ensure_ascii=False), encoding="utf-8")
    rules_path.write_text(json.dumps(runtime_rules, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(prompt_rules, "DEFAULT_RULES_FILE", rules_path)
    load_agent_prompt_config.cache_clear()
    prompt_rules.load_runtime_prompt_rules.cache_clear()

    try:
        load_agent_prompt_config(str(agents_path))
        runtime_rules["output_cleanliness_rule"]["title"] = "SNAPSHOT_B"
        rules_path.write_text(json.dumps(runtime_rules, ensure_ascii=False), encoding="utf-8")

        injected_rule = prompt_rules.build_output_cleanliness_rule()

        assert "SNAPSHOT_A" in injected_rule
        assert "SNAPSHOT_B" not in injected_rule
    finally:
        load_agent_prompt_config.cache_clear()
        prompt_rules.load_runtime_prompt_rules.cache_clear()


def test_model_routes_allow_gemini_35_flash_with_flash_25_fallback_rotation():
    routes = json.loads((ROOT / "backend" / "model_routes.json").read_text(encoding="utf-8"))
    routed_models = [
        routes.get("default_analysis_model"),
        routes.get("default_decision_model"),
        routes.get("context_digest_model"),
        routes.get("tear_sheet_model"),
        routes.get("audit_model"),
        *(routes.get("analysis_fallback_models") or []),
        *(routes.get("audit_fallback_models") or []),
        *list((routes.get("agents") or {}).values()),
    ]
    for fallback_models in (routes.get("agent_fallbacks") or {}).values():
        routed_models.extend(fallback_models or [])

    assert "gemini-3.5-flash" in routed_models
    assert "gemini-2.5-flash" in routed_models
    assert routes["default_decision_model"] == "gemini-3.5-flash"
    assert set(routes["audit_fallback_models"]) == {"gemini-2.5-flash"}
    for agent_num in ("7", "16", "19", "24"):
        assert routes["agents"][agent_num] == "gemini-3.5-flash"
        assert "gemini-2.5-flash" in routes["agent_fallbacks"][agent_num]
