def test_dcf_scenario_assumptions_classify_high_growth_and_stable_phases():
    from financial_dcf_scenarios import dcf_scenario_assumptions, dcf_scenario_note

    high_phase, high_assumptions = dcf_scenario_assumptions(80)
    assert high_phase == "high_growth"
    assert high_assumptions["bear"]["growth_rate_pct"] == 20
    assert high_assumptions["base"]["growth_rate_pct"] == 25
    assert high_assumptions["bull"]["growth_rate_pct"] == 30
    assert "高成長期" in dcf_scenario_note(high_phase)

    stable_phase, stable_assumptions = dcf_scenario_assumptions(20)
    assert stable_phase == "stable"
    assert stable_assumptions["bear"]["growth_rate_pct"] == 4
    assert stable_assumptions["base"]["growth_rate_pct"] == 5
    assert stable_assumptions["bull"]["growth_rate_pct"] == 6
    assert "穩定期" in dcf_scenario_note(stable_phase)


def test_build_dcf_scenarios_applies_margin_bias_and_wacc_floor():
    from financial_dcf_scenarios import build_dcf_scenarios

    calls = []

    def fake_dcf(**kwargs):
        calls.append(kwargs)
        return {
            "base_fcf_billion_twd": kwargs["base_fcf_billion_twd"],
            "wacc_pct": kwargs["wacc_pct"],
            "terminal_growth_pct": kwargs["terminal_growth_pct"],
        }

    result = build_dcf_scenarios(
        base_fcf_billion_twd=10,
        base_fcf_note="latest available FCF",
        latest_revenue_growth_pct=20,
        wacc_pct=2.5,
        shares_outstanding=100_000_000,
        net_debt_billion_twd=1,
        dcf_calculator=fake_dcf,
    )

    scenarios = result["scenarios"]
    assert result["growth_phase"] == "stable"
    assert scenarios["bear"]["base_fcf_billion_twd"] == 8
    assert scenarios["base"]["base_fcf_billion_twd"] == 10
    assert scenarios["bull"]["base_fcf_billion_twd"] == 12
    assert scenarios["bull"]["wacc_pct"] == 3.0
    assert calls[2]["terminal_growth_pct"] == 2.5
    assert scenarios["bear"]["growth_bias_pct"] == -20
    assert scenarios["bull"]["margin_bias_pct"] == 20
