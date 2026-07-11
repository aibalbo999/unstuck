import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "backend" / "static" / "commercial" / "shared" / "operator_policy.js").as_uri()


def run_policy(expression: str):
    script = f"""
      import * as policy from {json.dumps(MODULE)};
      process.stdout.write(JSON.stringify({{value: {expression}}}));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["value"]


def test_policy_amounts_use_five_million_operator_guardrails():
    assert run_policy("policy.policyAmounts()") == {
        "capital": 5_000_000,
        "cashReserve": 1_000_000,
        "deployableCapital": 4_000_000,
        "maxPosition": 750_000,
        "maxTradeRisk": 50_000,
    }


def test_position_plan_respects_risk_and_position_caps():
    plan = run_policy(
        "policy.positionPlan({entryPrice: 100, stopPrice: 90, targetPrice: 125})"
    )

    assert plan["shares"] == 5_000
    assert plan["investment"] == 500_000
    assert plan["maxLoss"] == 50_000
    assert plan["targetGain"] == 125_000
    assert plan["riskReward"] == 2.5
    assert plan["binding"] == "risk"


def test_position_plan_uses_position_cap_and_rejects_invalid_prices():
    capped = run_policy(
        "policy.positionPlan({entryPrice: 100, stopPrice: 99, targetPrice: 110})"
    )

    assert capped["shares"] == 7_500
    assert capped["investment"] == 750_000
    assert capped["binding"] == "position"
    assert run_policy(
        "policy.positionPlan({entryPrice: 100, stopPrice: 100, targetPrice: 110})"
    ) is None


def test_weight_amount_and_trim_amount_use_operator_capital():
    assert run_policy("policy.amountForWeight(22)") == 1_100_000
    assert run_policy("policy.trimToPositionLimit(22)") == 350_000
    assert run_policy("policy.trimToPositionLimit(15)") == 0


def test_format_twd_does_not_turn_missing_values_into_zero():
    assert "5,000,000" in run_policy("policy.formatTwd(5000000)")
    assert run_policy("policy.formatTwd(null)") == "資料不足"
