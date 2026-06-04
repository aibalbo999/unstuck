"""Structured agent output models, parsing, and legacy report block conversion."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from analysis_types import AnalysisContext
from json_utils import extract_json_payload
from prompt_rules import build_structured_agent_instructions
from validators import _extract_price_numbers, _parse_price_number


STRUCTURED_AGENT_INSTRUCTIONS = build_structured_agent_instructions()


class StructuredModel(BaseModel):
    """Base model for native Google GenAI response_schema payloads."""

    model_config = ConfigDict(populate_by_name=True)


class MoatScores(StructuredModel):
    brand_influence: float = Field(..., ge=1, le=10, alias="品牌影響力")
    network_effect: float = Field(..., ge=1, le=10, alias="網路效應")
    switching_cost: float = Field(..., ge=1, le=10, alias="轉換成本")
    cost_advantage: float = Field(..., ge=1, le=10, alias="成本優勢")
    patent_technology: float = Field(..., ge=1, le=10, alias="專利技術")
    overall_moat: float = Field(..., ge=1, le=10, alias="整體護城河")


class MoatStructuredOutput(StructuredModel):
    moat_scores: MoatScores
    analysis_markdown: str = Field(..., min_length=1)


class PriceTargets(StructuredModel):
    bear_case: float = Field(..., ge=0, alias="熊市情境")
    base_case: float = Field(..., ge=0, alias="基本情境")
    bull_case: float = Field(..., ge=0, alias="牛市情境")


class ValuationSummary(StructuredModel):
    primary_method: Literal["normalized_dcf", "relative_valuation", "blended"]
    uses_market_value_wacc: bool
    uses_normalized_fcf: bool
    double_counting_check: str = Field(..., min_length=1)


class PriceTargetStructuredOutput(StructuredModel):
    price_targets: PriceTargets
    valuation_summary: ValuationSummary
    analysis_markdown: str = Field(..., min_length=1)


class RecommendationFields(StructuredModel):
    recommendation: Literal["買入", "持有", "避免"] = Field(..., alias="建議")
    target_3m: str = Field(..., min_length=1, alias="短期目標（3個月）")
    target_6m: str = Field(..., min_length=1, alias="中期目標（6個月）")
    target_12m: str = Field(..., min_length=1, alias="長期目標（12個月）")
    long_term_potential_5y: str = Field(..., min_length=1, alias="長期潛力（5年）")
    confidence: str = Field(..., min_length=1, alias="信心指數")


class RecommendationStructuredOutput(StructuredModel):
    recommendation: RecommendationFields
    analysis_markdown: str = Field(..., min_length=1)


STRUCTURED_AGENT_RESPONSE_SCHEMAS: dict[int, type[StructuredModel]] = {
    3: MoatStructuredOutput,
    4: PriceTargetStructuredOutput,
    7: RecommendationStructuredOutput,
}


def get_structured_response_schema(agent_num: int) -> Optional[type[StructuredModel]]:
    """Return the native response schema model for structured agents."""
    return STRUCTURED_AGENT_RESPONSE_SCHEMAS.get(agent_num)


def build_structured_output_instruction(agent_num: int) -> str:
    """Return JSON-only output instructions for agents with machine-read fields."""
    return STRUCTURED_AGENT_INSTRUCTIONS.get(agent_num, "")


def _extract_json_payload(raw_text: str) -> Optional[dict]:
    return extract_json_payload(raw_text)


def _coerce_number(value, minimum=None, maximum=None):
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.\-]", "", value.replace(",", ""))
        value = cleaned
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return round(number, 2)


def _pick_mapping_value(mapping: dict, *keys):
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def normalize_structured_output(agent_num: int, payload: Optional[dict]) -> Optional[dict]:
    """Validate and normalize JSON payloads from structured agents."""
    if not isinstance(payload, dict):
        return None

    if agent_num == 3:
        raw_scores = payload.get("moat_scores", {})
        allowed = {
            "品牌影響力": ("品牌影響力", "brand_influence"),
            "網路效應": ("網路效應", "network_effect"),
            "轉換成本": ("轉換成本", "switching_cost"),
            "成本優勢": ("成本優勢", "cost_advantage"),
            "專利技術": ("專利技術", "patent_technology"),
            "整體護城河": ("整體護城河", "overall_moat"),
        }
        scores = {}
        for key, aliases in allowed.items():
            score = _coerce_number(_pick_mapping_value(raw_scores, *aliases), 1, 10)
            if score is not None:
                scores[key] = score
        if not scores:
            return None
        return {
            "moat_scores": scores,
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num == 4:
        raw_targets = payload.get("price_targets", {})
        target_map = {
            "熊": "熊市情境",
            "bear": "熊市情境",
            "基本": "基本情境",
            "base": "基本情境",
            "Base": "基本情境",
            "牛": "牛市情境",
            "bull": "牛市情境",
        }
        targets = {}
        for raw_key, raw_value in raw_targets.items():
            canonical = None
            for marker, mapped in target_map.items():
                if marker in str(raw_key):
                    canonical = mapped
                    break
            if not canonical:
                continue
            price = _coerce_number(raw_value, 0, None)
            if price is not None:
                targets[canonical] = price
        if not targets:
            return None
        return {
            "price_targets": targets,
            "valuation_summary": payload.get("valuation_summary", {}) if isinstance(payload.get("valuation_summary"), dict) else {},
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num == 7:
        raw_rec = payload.get("recommendation", {})
        if not isinstance(raw_rec, dict) or not raw_rec:
            return None
        key_aliases = {
            "recommendation": "建議",
            "target_3m": "短期目標（3個月）",
            "target_6m": "中期目標（6個月）",
            "target_12m": "長期目標（12個月）",
            "long_term_potential_5y": "長期潛力（5年）",
            "confidence": "信心指數",
        }
        normalized_rec = {}
        for key, value in raw_rec.items():
            normalized_key = key_aliases.get(str(key).strip(), str(key).strip())
            normalized_rec[normalized_key] = str(value).strip()
        return {
            "recommendation": normalized_rec,
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    return None


def structured_output_to_report_text(agent_num: int, structured: dict, fallback_text: str = "") -> str:
    """Convert parsed JSON into the legacy report text expected by renderers."""
    body = structured.get("analysis_markdown") or fallback_text

    if agent_num == 3:
        scores = structured.get("moat_scores", {})
        score_lines = "\n".join(f"{key}: {scores[key]}" for key in scores)
        return f"[護城河評分]\n{score_lines}\n[/護城河評分]\n\n{body}".strip()

    if agent_num == 4:
        targets = structured.get("price_targets", {})
        order = ["熊市情境", "基本情境", "牛市情境"]
        price_lines = "\n".join(
            f"{key}: NT${targets[key]:,.0f}" for key in order if key in targets
        )
        summary = structured.get("valuation_summary", {})
        summary_text = ""
        if summary:
            summary_text = "\n\n## 結構化估值檢查\n" + "\n".join(
                f"- {key}: {value}" for key, value in summary.items()
            )
        return f"[目標股價]\n{price_lines}\n[/目標股價]\n\n{body}{summary_text}".strip()

    if agent_num == 7:
        rec = structured.get("recommendation", {})
        rec_lines = "\n".join(f"{key}: {value}" for key, value in rec.items())
        return f"[投資建議]\n{rec_lines}\n[/投資建議]\n\n{body}".strip()

    return fallback_text


def price_targets_have_unit_error(targets: dict, current_price) -> bool:
    """Detect NT$5-style target prices when the stock trades in the hundreds/thousands."""
    if not isinstance(current_price, (int, float)) or current_price <= 100:
        return False
    prices = [value for value in targets.values() if isinstance(value, (int, float))]
    return bool(prices) and any(price < current_price * 0.05 for price in prices)


def process_agent_response(agent_num: int, raw_text: str, context: AnalysisContext) -> str:
    """Persist JSON structured output and return report-ready text."""
    if agent_num not in STRUCTURED_AGENT_INSTRUCTIONS:
        return raw_text or ""

    payload = _extract_json_payload(raw_text or "")
    structured = normalize_structured_output(agent_num, payload)
    if not structured:
        return raw_text or ""

    if agent_num == 4:
        current_price = context.get("data", {}).get("current_price")
        targets = structured.get("price_targets", {})
        if price_targets_have_unit_error(targets, current_price):
            warning = (
                "## 系統品質檢查警示\n"
                "- Agent 4 結構化目標價疑似發生單位縮寫錯誤，已拒絕寫入圖表資料。"
                "請重跑或檢查估值正文中的完整股價數字。"
            )
            body = structured.get("analysis_markdown") or raw_text or ""
            return f"{body}\n\n{warning}".strip()

    context.setdefault("structured_outputs", {})[agent_num] = structured
    return structured_output_to_report_text(agent_num, structured, raw_text)


def parse_structured_data(context: AnalysisContext) -> dict:
    """Parse moat scores, price targets, and recommendations from agent outputs."""
    parsed = {
        "moat_scores": {},
        "price_targets": {},
        "recommendation": {},
    }

    structured_outputs = context.get("structured_outputs", {})
    if 3 in structured_outputs:
        parsed["moat_scores"] = dict(structured_outputs[3].get("moat_scores", {}))
    if 4 in structured_outputs:
        parsed["price_targets"] = dict(structured_outputs[4].get("price_targets", {}))
    if 7 in structured_outputs:
        parsed["recommendation"] = dict(structured_outputs[7].get("recommendation", {}))

    if not parsed["moat_scores"] and 3 in context["analyses"]:
        text = context["analyses"][3]
        try:
            allowed_moat_keys = {"品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河"}
            moat_section = re.search(r"\[護城河評分\](.*?)\[/護城河評分\]", text, re.DOTALL)
            if moat_section:
                moat_text = moat_section.group(1)
                for line in moat_text.strip().split("\n"):
                    if ":" in line or "：" in line:
                        sep = ":" if ":" in line else "："
                        key, val = line.split(sep, 1)
                        key = re.sub(r"^[\s*・\-]+", "", key).strip()
                        if key not in allowed_moat_keys:
                            continue
                        val = val.strip()
                        try:
                            score = float(re.search(r"[\d.]+", val).group())
                            parsed["moat_scores"][key] = min(score, 10)
                        except Exception:
                            pass
        except Exception:
            pass

    if not parsed["moat_scores"]:
        parsed["moat_scores"] = {
            "品牌影響力": 6,
            "網路效應": 4,
            "轉換成本": 7,
            "成本優勢": 7,
            "專利技術": 6,
            "整體護城河": 6,
        }

    if not parsed["price_targets"] and 4 in context["analyses"]:
        text = context["analyses"][4]
        try:
            price_section = re.search(r"\[目標股價\](.*?)\[/目標股價\]", text, re.DOTALL)
            if price_section:
                price_text = price_section.group(1)
                for line in price_text.strip().split("\n"):
                    if ":" in line or "：" in line:
                        sep = ":" if ":" in line else "："
                        key, val = line.split(sep, 1)
                        key = key.strip()
                        prices = _extract_price_numbers(val)
                        if prices:
                            price_val = prices[0]
                            if price_val > 1:
                                parsed["price_targets"][key] = price_val

            if not parsed["price_targets"]:
                scenario_map = {
                    "熊市": ["熊市", "bear", "Bear"],
                    "基本": ["基本", "base", "Base"],
                    "牛市": ["牛市", "bull", "Bull"],
                }
                for label, keywords in scenario_map.items():
                    for kw in keywords:
                        number_pattern = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,6}(?:\.\d+)?"
                        pattern = rf"{kw}.{{0,80}}?(?:NT\$|\$|合理股價|目標價|合理價值)\s*:?\s*({number_pattern})"
                        m = re.search(pattern, text)
                        if m:
                            price_val = _parse_price_number(m.group(1))
                            if price_val > 10:
                                key_name = f"{label}情境"
                                parsed["price_targets"][key_name] = price_val
                                break

            current_price = context.get("data", {}).get("current_price")
            if isinstance(current_price, (int, float)) and current_price > 100:
                suspicious = [
                    key for key, price in parsed["price_targets"].items()
                    if isinstance(price, (int, float)) and price < current_price * 0.05
                ]
                if suspicious:
                    reparsed = {}
                    for line in text.splitlines():
                        if not any(label in line for label in ["熊市", "基本", "牛市"]):
                            continue
                        values = [value for value in _extract_price_numbers(line) if value >= current_price * 0.05]
                        if not values:
                            continue
                        if "熊市" in line:
                            reparsed["熊市情境"] = values[0]
                        elif "基本" in line:
                            reparsed["基本情境"] = values[0]
                        elif "牛市" in line:
                            reparsed["牛市情境"] = values[0]
                    if reparsed:
                        parsed["price_targets"] = reparsed
        except Exception:
            pass

    if not parsed["recommendation"] and 7 in context["analyses"]:
        text = context["analyses"][7]
        try:
            rec_section = re.search(r"\[投資建議\](.*?)\[/投資建議\]", text, re.DOTALL)
            if rec_section:
                rec_text = rec_section.group(1)
                for line in rec_text.strip().split("\n"):
                    if ":" in line or "：" in line:
                        sep = ":" if ":" in line else "："
                        key, val = line.split(sep, 1)
                        parsed["recommendation"][key.strip()] = val.strip()
        except Exception:
            pass

    return parsed
