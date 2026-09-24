"""Institutional roles share verified source scope without inferring daily trends."""

import copy

import pytest

from agent_runtime.prompting import build_prompt
from institutional_evidence import institutional_evidence_issues
from llm_rate_limits import estimate_text_tokens


ROLES = (15, 18, 23)
PIPELINES = {15: "v2", 18: "v3", 23: "v4"}
PROVIDER = "FinMind TaiwanStockInstitutionalInvestorsBuySell"


def data_with_flows():
    return {
        "ticker": "2330.TW", "company_name": "Institutional fixture",
        "institutional_trading": {
            "source": PROVIDER, "lookback_trading_days": 30,
            "latest_date": "2026-09-24",
            "net_buy_thousand_shares_by_category": {
                "foreign": 150, "investment_trust": -20, "dealer": None,
            },
            "total_net_buy_thousand_shares": 130,
            "last_5_trading_days_net_buy_thousand_shares": 50,
            "daily_total_net_buy_last_10": [
                {"date": "2026-09-23", "net_buy_thousand_shares": -1},
                {"date": "2026-09-24", "net_buy_thousand_shares": 2},
            ],
        },
    }


def source_section(prompt):
    assert "【法人與籌碼來源語意】" in prompt
    assert "【法人逐項來源契約】" in prompt
    return prompt.split("【法人逐項來源契約】", 1)[1].split("\n\n", 1)[0]


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("model", ["gemma-4-31b-it", "gemini-3.8-flash"])
def test_effective_prompt_preserves_verified_population_period_dates_and_units(role, model):
    data = data_with_flows()
    context = {"pipeline_id": PIPELINES[role], "analyses": {}, "_prompt_model_id": model}
    before = copy.deepcopy((data, context))

    prompt = build_prompt(role, data, context)
    section = source_section(prompt)

    assert "截至2026-09-24，外資近30個交易日淨買超150千股。" in section
    assert "截至2026-09-24，投信近30個交易日淨賣超20千股。" in section
    assert "三大法人合計近5個交易日淨買超50千股。" in section
    assert "三大法人合計2026-09-23單日淨賣超1千股。" in section
    assert "三大法人合計2026-09-24單日淨買超2千股。" in section
    assert "source ref=institutional_trading.net_buy_thousand_shares_by_category.foreign" in section
    assert f"provider={PROVIDER}" in section
    assert "source ref=institutional_trading.net_buy_thousand_shares_by_category.dealer" not in section
    assert "累計值不證明每日連續買超" in section
    assert "單日與5/10/20/30日" in section
    assert "觀測天數不足" in section
    assert "千股，不是千張" in prompt and "禁止借用其他分項或把null當0" in prompt
    assert institutional_evidence_issues(section, data) == []
    assert (data, context) == before
    # The bounded six-record fixture adds a small source guide, not another
    # history expansion; original evidence and final output rules remain intact.
    assert estimate_text_tokens(section, response_budget=0) < 1800
    assert "daily_total_net_buy_last_10" in prompt
    assert "JSON" in prompt


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("days", [5, 10, 20, 30])
def test_typed_observation_keeps_its_actual_window_without_implying_other_windows(role, days):
    path = "short_term_market_context.institutional_evidence.records[1]"
    data = {
        "ticker": "2330.TW", "company_name": "Typed fixture",
        "short_term_market_context": {"institutional_evidence": {"records": [None, {
            "population": "foreign", "value": -12, "unit": "thousand_shares",
            "window": {"kind": "trailing_trading_days", "trading_days": days},
            "observed_at": "2026-09-24", "provider": PROVIDER,
        }]}},
    }

    section = source_section(build_prompt(role, data, {"pipeline_id": PIPELINES[role]}))

    facts = [line for line in section.splitlines() if line.startswith("- ")]
    assert len(facts) == 1
    assert f"外資近{days}個交易日淨賣超12千股。" in facts[0]
    assert f"source ref={path}" in facts[0]
    assert institutional_evidence_issues(facts[0], data, allowed_paths=[path]) == []
    assert institutional_evidence_issues(facts[0], data, allowed_paths=[])


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("kind", ["missing", "unknown-provider", "unknown-period", "aggregate-only"])
def test_missing_or_aggregate_only_sources_do_not_become_daily_or_subgroup_evidence(role, kind):
    data = {"ticker": "2330.TW", "company_name": "Limited fixture"}
    if kind != "missing":
        data["institutional_trading"] = {
            "source": PROVIDER, "lookback_trading_days": 30,
            "latest_date": "2026-09-24", "total_net_buy_thousand_shares": 130,
        }
        if kind == "unknown-provider":
            data["institutional_trading"]["source"] = "unknown"
        elif kind == "unknown-period":
            data["institutional_trading"].pop("lookback_trading_days")

    section = source_section(build_prompt(role, data, {"pipeline_id": PIPELINES[role]}))

    facts = [line for line in section.splitlines() if line.startswith("- ")]
    if kind == "aggregate-only":
        assert len(facts) == 1
        assert "三大法人合計近30個交易日淨買超130千股。" in facts[0]
        assert all(word not in facts[0] for word in ("外資", "投信", "單日", "連續"))
        assert "累計值不證明每日連續買超" in section
    else:
        assert facts == []
        assert "沒有可逐項核驗的法人來源；不得補造主體、期間或數字" in section


def test_unrelated_roles_do_not_receive_institutional_source_expansion():
    prompt = build_prompt(11, data_with_flows(), {"pipeline_id": "v2"})
    assert "【法人逐項來源契約】" not in prompt
    assert "【法人與籌碼來源語意】" not in prompt
