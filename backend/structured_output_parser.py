"""Parse legacy report blocks into chart/rendering data."""

from __future__ import annotations

import re

from analysis_types import AnalysisContext
from pipeline_modes import get_structured_agent_num
from price_parser import extract_price_numbers, parse_price_number


DEFAULT_MOAT_SCORES = {
    "品牌影響力": 6,
    "網路效應": 4,
    "轉換成本": 7,
    "成本優勢": 7,
    "專利技術": 6,
    "整體護城河": 6,
}
ALLOWED_MOAT_KEYS = set(DEFAULT_MOAT_SCORES)


def parse_moat_scores_from_text(text: str) -> dict:
    moat_section = re.search(r"\[護城河評分\](.*?)\[/護城河評分\]", text or "", re.DOTALL)
    if not moat_section:
        return {}
    parsed = {}
    for line in moat_section.group(1).strip().split("\n"):
        if ":" not in line and "：" not in line:
            continue
        sep = ":" if ":" in line else "："
        key, val = line.split(sep, 1)
        key = re.sub(r"^[\s*・\-]+", "", key).strip()
        if key not in ALLOWED_MOAT_KEYS:
            continue
        score_match = re.search(r"[\d.]+", val.strip())
        if not score_match:
            continue
        parsed[key] = min(float(score_match.group()), 10)
    return parsed


def parse_price_targets_from_text(text: str, current_price=None) -> dict:
    parsed = {}
    price_section = re.search(r"\[目標股價\](.*?)\[/目標股價\]", text or "", re.DOTALL)
    if price_section:
        for line in price_section.group(1).strip().split("\n"):
            if ":" not in line and "：" not in line:
                continue
            sep = ":" if ":" in line else "："
            key, val = line.split(sep, 1)
            prices = extract_price_numbers(val)
            if prices and prices[0] > 1:
                parsed[key.strip()] = prices[0]

    if not parsed:
        scenario_map = {
            "熊市": ["熊市", "bear", "Bear"],
            "基本": ["基本", "base", "Base"],
            "牛市": ["牛市", "bull", "Bull"],
        }
        for label, keywords in scenario_map.items():
            for kw in keywords:
                number_pattern = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,6}(?:\.\d+)?"
                pattern = rf"{kw}.{{0,80}}?(?:NT\$|\$|合理股價|目標價|合理價值)\s*:?\s*({number_pattern})"
                match = re.search(pattern, text or "")
                if match:
                    price_val = parse_price_number(match.group(1))
                    if price_val > 10:
                        parsed[f"{label}情境"] = price_val
                        break

    if isinstance(current_price, (int, float)) and current_price > 100:
        suspicious = [
            key for key, price in parsed.items()
            if isinstance(price, (int, float)) and price < current_price * 0.05
        ]
        if suspicious:
            reparsed = {}
            for line in (text or "").splitlines():
                if not any(label in line for label in ["熊市", "基本", "牛市"]):
                    continue
                values = [value for value in extract_price_numbers(line) if value >= current_price * 0.05]
                if not values:
                    continue
                if "熊市" in line:
                    reparsed["熊市情境"] = values[0]
                elif "基本" in line:
                    reparsed["基本情境"] = values[0]
                elif "牛市" in line:
                    reparsed["牛市情境"] = values[0]
            if reparsed:
                parsed = reparsed
    return parsed


def parse_recommendation_from_text(text: str) -> dict:
    rec_section = re.search(r"\[投資建議\](.*?)\[/投資建議\]", text or "", re.DOTALL)
    if not rec_section:
        return {}
    parsed = {}
    for line in rec_section.group(1).strip().split("\n"):
        if ":" not in line and "：" not in line:
            continue
        sep = ":" if ":" in line else "："
        key, val = line.split(sep, 1)
        parsed[key.strip()] = val.strip()
    return parsed


def parse_structured_data(context: AnalysisContext) -> dict:
    """Parse moat scores, price targets, and recommendations from agent outputs."""
    parsed = {
        "moat_scores": {},
        "price_targets": {},
        "recommendation": {},
    }

    structured_outputs = context.get("structured_outputs", {})
    analyses = context.get("analyses", {})
    moat_agent = get_structured_agent_num("moat", context)
    valuation_agent = get_structured_agent_num("valuation", context)
    recommendation_agent = get_structured_agent_num("recommendation", context)
    if moat_agent is not None and moat_agent in structured_outputs:
        parsed["moat_scores"] = dict(structured_outputs[moat_agent].get("moat_scores", {}))
    if valuation_agent is not None and valuation_agent in structured_outputs:
        parsed["price_targets"] = dict(structured_outputs[valuation_agent].get("price_targets", {}))
    if recommendation_agent is not None and recommendation_agent in structured_outputs:
        parsed["recommendation"] = dict(structured_outputs[recommendation_agent].get("recommendation", {}))

    if moat_agent is not None and not parsed["moat_scores"] and moat_agent in analyses:
        parsed["moat_scores"] = parse_moat_scores_from_text(analyses[moat_agent])

    if moat_agent is not None and not parsed["moat_scores"]:
        parsed["moat_scores"] = dict(DEFAULT_MOAT_SCORES)

    if valuation_agent is not None and not parsed["price_targets"] and valuation_agent in analyses:
        current_price = context.get("data", {}).get("current_price") if isinstance(context.get("data"), dict) else None
        parsed["price_targets"] = parse_price_targets_from_text(analyses[valuation_agent], current_price)

    if recommendation_agent is not None and not parsed["recommendation"] and recommendation_agent in analyses:
        parsed["recommendation"] = parse_recommendation_from_text(analyses[recommendation_agent])

    return parsed
