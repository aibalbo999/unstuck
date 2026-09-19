"""Source-bound mode-D unit and credit-trading checks used by normal repair gates."""

from __future__ import annotations

import math
import re

from financial_claim_context import is_actual_claim
from output_sanitizer import strip_generated_audit_sections

_COUNT = r"(?P<number>\d[\d,]*(?:\.\d+)?)(?P<scale>萬|千)?"
_VOLUME = re.compile(_COUNT + r"(?P<unit>張|股)")
_CREDIT_FIELDS = {
    "融資賣出": "margin_sale", "融券賣出": "short_sale",
    "融資買進": "margin_purchase", "融券買進": "short_purchase",
    "融資餘額": "margin_balance", "融券餘額": "short_balance",
    "融資前日餘額": "margin_previous_balance", "融券前日餘額": "short_previous_balance",
}
_CREDIT = re.compile(r"(?P<label>" + "|".join(_CREDIT_FIELDS) + r")"
                     r"(?:目前|當日|今日|為|約|達|達到|至|[:：=|])*" + _COUNT + r"(?P<unit>張|股)?")


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _taiwan_equity(data):
    company = _mapping(data.get("company"))
    ticker = str(data.get("ticker") or company.get("ticker")
                 or _mapping(company.get("identity")).get("ticker") or "").upper()
    return ticker.endswith((".TW", ".TWO"))


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _count(match):
    return float(match["number"].replace(",", "")) * {None: 1, "千": 1000, "萬": 10000}[match["scale"]]


def _close(first, second):
    # Permit normal rounding of source counts, never a 1000-fold unit change.
    return abs(first - second) <= max(0.51, abs(second) * 0.0001)


def _volume_issues(text, data):
    context = _mapping(data.get("short_term_market_context")) or data
    daily = _mapping(context.get("daily_market_data"))
    indicators = _mapping(context.get("technical_indicators"))
    if "daily_market_data" not in context and "technical_indicators" not in context:
        return []
    unit = daily.get("volume_unit")
    bars = daily.get("bars")
    bars = bars if isinstance(bars, (list, tuple)) else []
    values = [bar.get("volume") for bar in bars if isinstance(bar, dict)]
    values += [indicators.get(key) for key in ("volume_latest", "volume_sma_5", "volume_sma_20")]
    values = [number for value in values if (number := _number(value)) is not None]
    issues = []
    for match in _VOLUME.finditer(text):
        before = re.split(r"[。；;\n]", text[max(0, match.start() - 24):match.start()])[-1]
        after = re.split(r"[。；;，,\n]", text[match.end():match.end() + 14])[0]
        if not re.search(r"成交量|均量|量能|放量|縮量", before + after):
            continue
        if not is_actual_claim(text, match.start(), match.end()):
            continue
        if unit not in ("shares", "lots"):
            issues.append("成交量單位紅線：來源 volume_unit 未提供或單位未確認；不得將原始數值宣稱為股或張，請標示單位未確認。")
            continue
        claimed = _count(match)
        expected_unit = "股" if unit == "shares" else "張"
        if match["unit"] == expected_unit:
            continue
        if not _taiwan_equity(data):
            issues.append("成交量單位紅線：只有已確認台股標的可使用 1 張 = 1000 股；其他市場或標的不明時，必須沿用來源原始單位。")
            continue
        factor = 1000 if unit == "shares" else 0.001
        converted = [value / factor for value in values]
        if any(_close(claimed, value) for value in values) and not any(_close(claimed, value) for value in converted):
            issues.append(f"成交量單位紅線：來源 volume_unit={unit}，原始數值不可直接標成{match['unit']}；若換算台股張數，1 張 = 1000 股，必須同時換算數值。")
    return issues


def _credit_issues(text, data):
    chip = _mapping(data.get("chip_data")) or _mapping(data.get("chip_context"))
    credit = chip.get("twse_margin_short_sales")
    if not isinstance(credit, dict):
        return []
    issues = []
    for match in _CREDIT.finditer(text):
        if not is_actual_claim(text, match.start(), match.end()):
            continue
        field = _CREDIT_FIELDS[match["label"]]
        if field in {"margin_balance", "short_balance"}:
            prefix = re.split(r"[，,。；;\n]", text[max(0, match.start() - 24):match.start()])[-1]
            periods = list(re.finditer(r"昨日|前日|前一(?:交易)?日|今日|當日|目前|最新", prefix))
            if periods and periods[-1].group() in {"昨日", "前日", "前一日", "前一交易日"}:
                field = field.replace("_balance", "_previous_balance")
        expected = _number(credit.get(field))
        if expected is None:
            issues.append(f"融資券欄位紅線：{match['label']} 對應 twse_margin_short_sales.{field} 為 null 或缺值，必須標示資料不足，不得借用其他融資／融券欄位或視為 0。")
        elif match["unit"] and credit.get("source") != "TWSE OpenAPI MI_MARGN":
            issues.append(f"融資券單位紅線：{match['label']} 來源未確認為 TWSE MI_MARGN，單位未確認，不得自行假定張數或換算股數。")
        elif not _close(_count(match), expected * (1000 if match["unit"] == "股" else 1)):
            issues.append(f"融資券欄位紅線：{match['label']} 必須使用 twse_margin_short_sales.{field}={expected:g}，不可混用融資與融券數值。")
    return issues


def short_term_evidence_issues(agent_num, text, data):
    data = _mapping(data)
    if agent_num not in {22, 23, 24}:
        return []
    text = re.sub(r"[^\S\n]+|[*`]", "", strip_generated_audit_sections(text))
    issues = _volume_issues(text, data) if agent_num in {22, 24} else []
    if agent_num in {23, 24}:
        issues.extend(_credit_issues(text, data))
    return list(dict.fromkeys(issues))
