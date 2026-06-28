import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

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


def test_model_routes_do_not_use_low_quota_gemini_35_flash():
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

    assert "gemini-3.5-flash" not in routed_models
    assert routes["default_decision_model"] == "gemini-2.5-flash"
    assert set(routes["audit_fallback_models"]) == {"gemini-2.5-flash"}
