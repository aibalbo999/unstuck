import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_quality_funnel_passes_high_quality_company():
    from quality_funnel import evaluate_quality_funnel

    result = evaluate_quality_funnel({
        "roe_avg_pct": 22.0,
        "free_cash_flow_5y_sum": 1_250_000_000,
        "interest_coverage": 12.0,
        "gross_margin_pct": 48.0,
        "ocf_to_net_income": 1.12,
        "net_margin_pct": 19.0,
        "share_dilution_5y_pct": 1.5,
    })

    assert result["outcome"] == "pass"
    assert result["score"] >= 85
    assert result["failed_rules"] == []
    assert {rule["id"] for rule in result["passed_rules"]} >= {"roe", "fcf", "gross_margin"}


def test_quality_funnel_rejects_hard_failures():
    from quality_funnel import evaluate_quality_funnel

    result = evaluate_quality_funnel({
        "roe_avg_pct": 5.0,
        "free_cash_flow_5y_sum": -120_000_000,
        "interest_coverage": 1.4,
        "gross_margin_pct": 10.0,
        "ocf_to_net_income": 0.5,
        "net_margin_pct": 2.0,
        "share_dilution_5y_pct": 35.0,
    })

    failed_rule_ids = {rule["id"] for rule in result["failed_rules"]}
    assert result["outcome"] == "reject"
    assert {"roe", "fcf", "interest_coverage", "share_dilution"} <= failed_rule_ids
    assert result["score"] < 50


def test_quality_funnel_marks_missing_fundamentals_as_gray():
    from quality_funnel import evaluate_quality_funnel

    result = evaluate_quality_funnel({"roe_avg_pct": 21.0})

    missing_rule_ids = {rule["id"] for rule in result["missing_rules"]}
    assert result["outcome"] == "gray"
    assert "fcf" in missing_rule_ids
    assert result["failed_rules"] == []


def test_quality_funnel_uses_financial_sector_rule_overrides():
    from quality_funnel import evaluate_quality_funnel

    result = evaluate_quality_funnel(
        {
            "roe_avg_pct": 11.0,
            "net_margin_pct": 9.0,
            "share_dilution_5y_pct": 1.0,
        },
        sector="Financial Services",
        industry="Banks",
    )

    assert result["outcome"] == "pass"
    skipped_rule_ids = {rule["id"] for rule in result["skipped_rules"]}
    assert {"fcf", "interest_coverage", "gross_margin", "ocf_to_net_income"} <= skipped_rule_ids
    assert not result["missing_rules"]


def test_quality_funnel_applies_semiconductor_gross_margin_floor():
    from quality_funnel import evaluate_quality_funnel

    result = evaluate_quality_funnel(
        {
            "roe_avg_pct": 22.0,
            "free_cash_flow_5y_sum": 100_000_000,
            "interest_coverage": 8.0,
            "gross_margin_pct": 20.0,
            "ocf_to_net_income": 1.0,
            "net_margin_pct": 12.0,
            "share_dilution_5y_pct": 1.0,
        },
        sector="Technology",
        industry="Semiconductors",
    )

    assert result["outcome"] == "reject"
    gross_margin = next(rule for rule in result["failed_rules"] if rule["id"] == "gross_margin")
    assert gross_margin["threshold"] == 35.0


def test_market_screener_import_attaches_quality_funnel(monkeypatch, tmp_path):
    import market_screener
    import watchlist_service

    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()

    result = market_screener.import_candidates_to_watchlist([
        {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "category": "institutional_accumulation",
            "reason": "外資與投信同步買超",
            "score": 4500,
            "screen_date": "2026-06-26",
            "metrics": {
                "roe_avg_pct": 28.0,
                "free_cash_flow_5y_sum": 500_000_000_000,
                "interest_coverage": 30.0,
                "gross_margin_pct": 54.0,
                "ocf_to_net_income": 1.08,
                "net_margin_pct": 38.0,
                "share_dilution_5y_pct": 0.2,
            },
        }
    ])

    assert result["imported_count"] == 1
    item = watchlist_service.list_watchlist()["items"][0]
    trigger = item["triggers"][0]
    assert "quality:pass" in item["tags"]
    assert trigger["quality_funnel"]["outcome"] == "pass"
