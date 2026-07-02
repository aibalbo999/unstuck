"""Quality-screening rules for fast pass/gray/reject decisions."""

from __future__ import annotations

import math
from typing import Any


SCHEMA_VERSION = "quality_funnel.v1"

SECTOR_RULE_OVERRIDES: dict[str, dict[str, Any]] = {
    "financials": {
        "skip": {"fcf", "interest_coverage", "gross_margin", "ocf_to_net_income", "debt_to_equity"},
        "minimum": {"net_margin": 8.0},
    },
    "semiconductors": {
        "minimum": {"gross_margin": 35.0},
    },
    "reit": {
        "skip": {"fcf", "ocf_to_net_income"},
        "minimum": {"net_margin": 15.0},
    },
}

_HARD_RULES: list[dict[str, Any]] = [
    {
        "id": "roe",
        "label": "ROE",
        "keys": ["roe_avg_pct", "roe_pct", "return_on_equity_pct"],
        "minimum": 8.0,
        "unit": "%",
    },
    {
        "id": "fcf",
        "label": "五年累計 FCF",
        "keys": ["free_cash_flow_5y_sum", "fcf_5y_sum", "cumulative_fcf", "fcf_sum"],
        "minimum": 0.0,
        "unit": "",
    },
    {
        "id": "interest_coverage",
        "label": "利息保障倍數",
        "keys": ["interest_coverage", "interest_coverage_ratio"],
        "minimum": 2.0,
        "unit": "x",
    },
    {
        "id": "gross_margin",
        "label": "毛利率",
        "keys": ["gross_margin_pct", "gross_margin"],
        "minimum": 15.0,
        "unit": "%",
    },
    {
        "id": "ocf_to_net_income",
        "label": "OCF/Net Income",
        "keys": ["ocf_to_net_income", "operating_cash_flow_to_net_income"],
        "minimum": 0.7,
        "unit": "x",
    },
    {
        "id": "net_margin",
        "label": "淨利率",
        "keys": ["net_margin_pct", "net_margin"],
        "minimum": 5.0,
        "unit": "%",
    },
    {
        "id": "share_dilution",
        "label": "五年股本稀釋",
        "keys": ["share_dilution_5y_pct", "shares_dilution_5y_pct", "share_count_growth_5y_pct"],
        "maximum": 20.0,
        "unit": "%",
    },
]

_WARNING_RULES: list[dict[str, Any]] = [
    {
        "id": "debt_to_equity",
        "label": "Debt/Equity",
        "keys": ["debt_to_equity_pct", "debt_to_equity"],
        "maximum": 200.0,
        "unit": "%",
    }
]


def evaluate_quality_funnel(
    metrics: dict[str, Any] | None,
    *,
    sector: str | None = None,
    industry: str | None = None,
) -> dict[str, Any]:
    """Evaluate fundamental quality rules without mutating source metrics."""
    values = metrics if isinstance(metrics, dict) else {}
    profile = _sector_profile(sector, industry)
    overrides = SECTOR_RULE_OVERRIDES.get(profile, {})
    passed_rules = []
    failed_rules = []
    missing_rules = []
    skipped_rules = []
    warnings = []

    for source_rule in _HARD_RULES:
        rule = _apply_rule_override(source_rule, overrides)
        if rule is None:
            skipped_rules.append(_skipped_rule(source_rule))
            continue
        value = _first_number(values, rule["keys"])
        if value is None:
            missing_rules.append(_missing_rule(rule))
            continue
        result = _rule_result(rule, value)
        if result["passed"]:
            passed_rules.append(result)
        else:
            failed_rules.append(result)

    for source_rule in _WARNING_RULES:
        rule = _apply_rule_override(source_rule, overrides)
        if rule is None:
            continue
        value = _first_number(values, rule["keys"])
        if value is None:
            continue
        result = _rule_result(rule, value)
        if not result["passed"]:
            warnings.append({**result, "severity": "warning"})

    outcome = "pass"
    if failed_rules:
        outcome = "reject"
    elif missing_rules:
        outcome = "gray"

    score = max(0, min(100, round(100 - len(failed_rules) * 20 - len(missing_rules) * 8 - len(warnings) * 5)))
    return {
        "schema_version": SCHEMA_VERSION,
        "outcome": outcome,
        "score": score,
        "summary": _summary(outcome, failed_rules, missing_rules),
        "passed_rules": passed_rules,
        "failed_rules": failed_rules,
        "missing_rules": missing_rules,
        "skipped_rules": skipped_rules,
        "warnings": warnings,
    }


def _sector_profile(sector: str | None, industry: str | None) -> str | None:
    signature = f"{sector or ''} {industry or ''}".strip().lower()
    if not signature:
        return None
    if any(keyword in signature for keyword in ("reit", "real estate investment trust", "不動產投資信託")):
        return "reit"
    if any(keyword in signature for keyword in ("semiconductor", "semiconductors", "foundry", "wafer", "半導體", "晶圓")):
        return "semiconductors"
    if any(keyword in signature for keyword in ("financial", "finance", "bank", "insurance", "金融", "銀行", "保險", "金控")):
        return "financials"
    return None


def _apply_rule_override(rule: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any] | None:
    rule_id = str(rule.get("id") or "")
    if rule_id in set(overrides.get("skip") or set()):
        return None
    adjusted = dict(rule)
    minimums = overrides.get("minimum") if isinstance(overrides.get("minimum"), dict) else {}
    maximums = overrides.get("maximum") if isinstance(overrides.get("maximum"), dict) else {}
    if rule_id in minimums:
        adjusted.pop("maximum", None)
        adjusted["minimum"] = float(minimums[rule_id])
    if rule_id in maximums:
        adjusted.pop("minimum", None)
        adjusted["maximum"] = float(maximums[rule_id])
    return adjusted


def _skipped_rule(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rule["id"],
        "label": rule["label"],
        "reason": "sector_override_not_applicable",
        "message": f"{rule['label']} 規則不適用於此產業分類，已由行業化品質漏斗跳過。",
    }


def _rule_result(rule: dict[str, Any], value: float) -> dict[str, Any]:
    if "minimum" in rule:
        threshold = float(rule["minimum"])
        operator = ">="
        passed = value >= threshold
    else:
        threshold = float(rule["maximum"])
        operator = "<="
        passed = value <= threshold
    return {
        "id": rule["id"],
        "label": rule["label"],
        "value": value,
        "threshold": threshold,
        "operator": operator,
        "unit": rule.get("unit", ""),
        "passed": passed,
        "message": f"{rule['label']} {_format_value(value, rule.get('unit', ''))} {operator} {_format_value(threshold, rule.get('unit', ''))}",
    }


def _missing_rule(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rule["id"],
        "label": rule["label"],
        "keys": list(rule["keys"]),
        "message": f"缺少 {rule['label']} 指標，需補資料後再判斷。",
    }


def _summary(outcome: str, failed_rules: list[dict[str, Any]], missing_rules: list[dict[str, Any]]) -> str:
    if outcome == "reject":
        labels = "、".join(rule["label"] for rule in failed_rules)
        return f"品質漏斗否決：{labels} 未達最低門檻。"
    if outcome == "gray":
        labels = "、".join(rule["label"] for rule in missing_rules[:3])
        suffix = "等" if len(missing_rules) > 3 else ""
        return f"品質漏斗灰區：缺少 {labels}{suffix}，需補資料後再判斷。"
    return "品質漏斗通過：主要獲利、現金流與稀釋指標未觸發否決。"


def _first_number(metrics: dict[str, Any], keys: list[str]) -> float | None:
    lower_map = {str(key).strip().lower(): value for key, value in metrics.items()}
    for key in keys:
        if key in metrics:
            value = _to_number(metrics[key])
            if value is not None:
                return value
        value = _to_number(lower_map.get(str(key).strip().lower()))
        if value is not None:
            return value
    return None


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip()
    if not text or text in {"-", "--", "N/A", "na", "null"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.replace(",", "").replace("%", "").replace("+", "").replace("(", "").replace(")", "")
    try:
        number = float(text)
    except ValueError:
        return None
    if negative:
        number = -number
    return number if math.isfinite(number) else None


def _format_value(value: float, unit: str) -> str:
    if abs(value) >= 1000 and unit == "":
        text = f"{value:,.0f}"
    elif float(value).is_integer():
        text = f"{value:.0f}"
    else:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}{unit}" if unit else text


__all__ = ["evaluate_quality_funnel"]
