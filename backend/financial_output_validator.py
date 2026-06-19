"""Financial logic audit rules for model-generated analysis."""

from __future__ import annotations

import re
from typing import Optional

from audit_rule_engine import evaluate_configured_audit_rules
from output_sanitizer import strip_generated_audit_sections


def safe_float(value) -> Optional[float]:
    if value is None or value == "N/A":
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("x", "").replace("%", "").strip()
            if not value:
                return None
        return float(value)
    except (TypeError, ValueError):
        return None


def relative_gap(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1.0)


def money_text_to_billion(raw_num: str, unit: str = "") -> Optional[float]:
    value = safe_float(raw_num)
    if value is None:
        return None
    unit = unit or ""
    if unit == "億":
        return value / 10
    if unit == "兆":
        return value * 1000
    return value


def has_data_quality_caveat(normalized: str) -> bool:
    return any(
        word in normalized
        for word in [
            "資料品質警示",
            "口徑差異",
            "口徑不同",
            "口徑偏差",
            "口徑互斥",
            "不可直接",
            "不得直接",
            "不能直接",
            "不應直接",
            "僅列為警示",
            "僅供對照",
            "需人工複核",
            "同期間年度",
            "年度杜邦恒等式",
        ]
    )


CYCLICAL_INDUSTRY_KEYWORDS = [
    "航運",
    "海運",
    "貨櫃",
    "散裝",
    "面板",
    "顯示器",
    "LCD",
    "OLED",
    "記憶體",
    "DRAM",
    "NAND",
    "Memory",
    "Shipping",
    "Marine",
    "Display",
]


def is_cyclical_low_pe_setup(data: dict) -> bool:
    signature = " ".join(str(data.get(key, "") or "") for key in ["company_name", "sector", "industry"])
    if not any(keyword.lower() in signature.lower() for keyword in CYCLICAL_INDUSTRY_KEYWORDS):
        return False
    pe = safe_float(data.get("pe_ratio_raw"))
    if pe is None:
        pe = safe_float(data.get("pe_ratio"))
    return pe is not None and 0 < pe < 5


def extract_revenue_mentions(normalized: str) -> list[dict]:
    mentions = []
    pattern = re.compile(
        r"(?P<label>TTM|LTM|20\d{2}年|最新年度|前一年度)?"
        r"營收(?:為|=|:|：|達|約)?(?:NT\$?)?"
        r"(?P<num>\d+(?:\.\d+)?)(?P<unit>B|億|兆)?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(normalized):
        value_b = money_text_to_billion(match.group("num"), match.group("unit") or "")
        if value_b is None:
            continue
        mentions.append({
            "label": match.group("label") or "",
            "value_b": value_b,
            "start": match.start(),
        })
    return mentions


def extract_first_money_billion(pattern: str, normalized: str) -> Optional[float]:
    match = re.search(pattern, normalized, flags=re.IGNORECASE)
    if not match:
        return None
    return money_text_to_billion(match.group("num"), match.groupdict().get("unit") or "")


def extract_first_percent(pattern: str, normalized: str) -> Optional[float]:
    match = re.search(pattern, normalized, flags=re.IGNORECASE)
    if not match:
        return None
    return safe_float(match.group("num"))


def append_deep_numeric_consistency_issues(issues: list[str], normalized: str):
    """Catch arithmetic contradictions that do not depend on a named rule."""
    revenue_mentions = extract_revenue_mentions(normalized)
    revenue_growth_claim = extract_first_percent(
        r"營收(?:年增率|成長率|年增|成長|增長|暴增)(?:高達|達|為|=|:|：|約)?(?P<num>-?\d+(?:\.\d+)?)%",
        normalized,
    )
    if revenue_growth_claim is not None and len(revenue_mentions) >= 2:
        current = next((item for item in revenue_mentions if item["label"].upper() in {"TTM", "LTM"}), revenue_mentions[-1])
        base_candidates = [item for item in revenue_mentions if item is not current and item["value_b"] > 0]
        if base_candidates:
            base = base_candidates[-1] if current["start"] > base_candidates[-1]["start"] else base_candidates[0]
            expected_growth = (current["value_b"] / base["value_b"] - 1) * 100
            if abs(revenue_growth_claim - expected_growth) > max(10, abs(expected_growth) * 0.35):
                issues.append(
                    "算術一致性紅線：報告列出的營收基期與 TTM/最新營收推不出所宣稱的營收成長率；"
                    f"依文中數字約為 {expected_growth:.1f}%，不是 {revenue_growth_claim:.1f}%。"
                )

    revenue_b = next((item["value_b"] for item in revenue_mentions if item["label"].upper() in {"TTM", "LTM"}), None)
    if revenue_b is None and revenue_mentions:
        revenue_b = revenue_mentions[0]["value_b"]
    margin_pct = extract_first_percent(r"淨利率(?:為|=|:|：|約|高達)?(?P<num>-?\d+(?:\.\d+)?)%", normalized)
    market_cap_b = extract_first_money_billion(
        r"市值(?:為|=|:|：|約)?(?:NT\$?)?(?P<num>\d+(?:\.\d+)?)(?P<unit>B|億|兆)?",
        normalized,
    )
    pe = extract_first_percent(
        r"(?:TTM)?(?:P/E|本益比)(?:為|=|:|：|約)?(?P<num>\d+(?:\.\d+)?)x?",
        normalized,
    )
    if revenue_b and margin_pct is not None and market_cap_b and pe and pe > 0:
        implied_income_from_margin = revenue_b * margin_pct / 100
        implied_income_from_pe = market_cap_b / pe
        if relative_gap(implied_income_from_margin, implied_income_from_pe) > 0.25:
            issues.append(
                "估值一致性紅線：文中 TTM 營收×淨利率 推回淨利，與 市值÷P/E 推回淨利差異超過 25%；"
                "必須標示資料口徑互斥並採用校準後口徑。"
            )

    if not has_data_quality_caveat(normalized):
        roe = extract_first_percent(r"ROE(?:為|=|:|：|約)?(?P<num>-?\d+(?:\.\d+)?)%", normalized)
        roa = extract_first_percent(r"ROA(?:為|=|:|：|約)?(?P<num>-?\d+(?:\.\d+)?)%", normalized)
        equity_multiplier_match = re.search(
            r"權益乘數(?:為|=|:|：|約)?(?P<num>\d+(?:\.\d+)?)(?:x|倍)?",
            normalized,
            flags=re.IGNORECASE,
        )
        equity_multiplier = safe_float(equity_multiplier_match.group("num")) if equity_multiplier_match else None
        if roe is not None and roa is not None and equity_multiplier is not None:
            implied_roe = roa * equity_multiplier
            if abs(implied_roe - roe) > max(3, abs(roe) * 0.15):
                issues.append(
                    "杜邦數值一致性紅線：文中 ROA×權益乘數 與 ROE 差距過大；"
                    "若不是同期間同口徑資料，不可作為杜邦恒等式拆解。"
                )


def validate_analysis_output(agent_num: int, text: str, data: Optional[dict] = None) -> list[str]:
    """檢查模型輸出是否踩到硬性財務邏輯紅線。"""
    issues = []
    normalized = re.sub(r"\s+", "", strip_generated_audit_sections(text or ""))
    data = data or {}

    issues.extend(
        evaluate_configured_audit_rules(
            agent_num,
            normalized,
            has_data_quality_caveat=has_data_quality_caveat(normalized),
        )
    )

    if agent_num in (4, 7, 14, 16, 19) and is_cyclical_low_pe_setup(data):
        low_pe_bargain_claim = (
            any(word in normalized for word in ["低本益比", "本益比偏低", "P/E偏低", "PE偏低", "本益比低", "P/E低", "PE低"])
            and any(word in normalized for word in ["低估", "被低估", "便宜", "估值便宜", "買入", "上修"])
        )
        has_cycle_caveat = any(word in normalized for word in ["景氣循環", "循環股", "高PE買", "低PE賣", "獲利高峰", "谷底", "庫存循環"])
        if low_pe_bargain_claim and not has_cycle_caveat:
            issues.append(
                "景氣循環股紅線：航運、面板、記憶體等循環產業在 P/E < 5x 時，"
                "不可單靠低本益比推論低估；需先判斷是否處於獲利高峰與循環反轉風險。"
            )

    yahoo_growth = str(data.get("yahoo_revenue_growth", "")).replace("%", "").strip()
    if yahoo_growth and yahoo_growth != "N/A" and yahoo_growth in normalized:
        if any(word in normalized for word in ["營收年增率", "TTM營收成長", "TTM營收年增", "營收成長率高達"]):
            if not any(word in normalized for word in ["Yahoo近期", "季度口徑", "近期口徑", "不可直接稱為"]):
                issues.append(
                    "成長率口徑紅線：Yahoo revenueGrowth 通常是近期/季度口徑，不可直接寫成 TTM 或年度營收年增率；"
                    "請改用年度財報 YoY 或 TTM 相對最新年度 run-rate 檢查。"
                )

    provider_margin = str(data.get("profit_margin_provider", "")).replace("%", "").strip()
    calibrated_margin = str(data.get("profit_margin", "")).replace("%", "").strip()
    if provider_margin and provider_margin != "N/A" and calibrated_margin and provider_margin != calibrated_margin:
        if provider_margin in normalized and "淨利率" in normalized:
            if not any(word in normalized for word in ["Yahoo原始", "資料源對照", "口徑互斥", "不採用"]):
                issues.append(
                    "淨利率口徑紅線：Yahoo 原始 profitMargins 與 P/E/EPS 推回淨利互斥時，"
                    "正式分析必須採用校準後淨利率，原始值只能作為資料品質警示。"
                )

    append_deep_numeric_consistency_issues(issues, normalized)

    return list(dict.fromkeys(issues))


def append_quality_warnings(agent_num: int, text: str, data: Optional[dict] = None) -> str:
    issues = validate_analysis_output(agent_num, text, data)
    if not issues:
        return text

    warning_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"{text}\n\n"
        "## 系統品質檢查警示\n"
        "以下內容觸發硬性財務邏輯檢查；閱讀本段分析時請優先採用警示所述修正口徑：\n"
        f"{warning_lines}"
    )


_safe_float = safe_float
_relative_gap = relative_gap
_money_text_to_billion = money_text_to_billion
_has_data_quality_caveat = has_data_quality_caveat
_is_cyclical_low_pe_setup = is_cyclical_low_pe_setup
_extract_revenue_mentions = extract_revenue_mentions
_extract_first_money_billion = extract_first_money_billion
_extract_first_percent = extract_first_percent
_append_deep_numeric_consistency_issues = append_deep_numeric_consistency_issues
