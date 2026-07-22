"""Parse legacy report blocks into chart/rendering data."""

from __future__ import annotations

import re
import unicodedata

from analysis_types import AnalysisContext
from pipeline_modes import get_structured_agent_num
from recommendation_labels import normalize_recommendation_label
from price_parser import HORIZON_ONLY_PATTERN, extract_target_price_numbers


DEFAULT_MOAT_SCORES = {
    "品牌影響力": 6,
    "網路效應": 4,
    "轉換成本": 7,
    "成本優勢": 7,
    "專利技術": 6,
    "整體護城河": 6,
}
ALLOWED_MOAT_KEYS = set(DEFAULT_MOAT_SCORES)
PERCENT_NUMBER_PATTERN = r"(?:[+＋\-−－]\s*)?\d+(?:[.．]\d+)?(?:[eE][-+]?\d+)?\s*[%％]"
RANGE_SEPARATOR_PATTERN = r"(?:-|–|—|－|−|~|～|〜|至|到|\bto\b|\band\b|與|和)"
SCENARIO_VALUE_PREFIX_PATTERN = re.compile(
    r"^\s*(?:熊市|基本|牛市|bear|base|bull)[^:：]*[:：]\s*",
    flags=re.IGNORECASE,
)


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
            parts = _split_key_value_line(line)
            if parts is None:
                continue
            key, val = parts
            price = _target_price_from_text(val)
            if price is not None and price > 1:
                parsed[key.strip()] = price

    if not parsed:
        scenario_map = {
            "熊市": ["熊市", "bear", "Bear"],
            "基本": ["基本", "base", "Base"],
            "牛市": ["牛市", "bull", "Bull"],
        }
        for line in (text or "").splitlines():
            for label, keywords in scenario_map.items():
                if not any(keyword in line for keyword in keywords):
                    continue
                price_val = _target_price_from_text(line)
                if price_val is not None and price_val > 10:
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
                value = _target_price_from_text(line)
                if value is None or value < current_price * 0.05:
                    continue
                if "熊市" in line:
                    reparsed["熊市情境"] = value
                elif "基本" in line:
                    reparsed["基本情境"] = value
                elif "牛市" in line:
                    reparsed["牛市情境"] = value
            if reparsed:
                parsed = reparsed
    return parsed


def _target_price_from_text(text: str) -> float | None:
    cleaned = re.sub(PERCENT_NUMBER_PATTERN, "", str(text or ""))
    if _is_horizon_only_scenario_value(cleaned):
        return None
    prices = [price for price in extract_target_price_numbers(cleaned) if price > 0]
    if not prices:
        return None
    if _looks_like_price_range(cleaned) and len(prices) >= 2:
        return sum(prices[:2]) / 2
    return prices[0]


def _is_horizon_only_scenario_value(text: str) -> bool:
    value = SCENARIO_VALUE_PREFIX_PATTERN.sub("", str(text or "")).strip()
    if ":" in value or "：" in value:
        sep = ":" if ":" in value else "："
        value = value.split(sep, 1)[1].strip()
    value = unicodedata.normalize("NFKC", value)
    return bool(value and HORIZON_ONLY_PATTERN.match(value))


def _looks_like_price_range(text: str) -> bool:
    return bool(
        re.search(
            rf"\d\s*(?:元|塊)?\s*{RANGE_SEPARATOR_PATTERN}\s*"
            rf"(?:NT\$?|NTD|TWD|新台幣|臺幣|台幣)?\s*\d",
            text,
        )
    )


def _split_key_value_line(line: str) -> tuple[str, str] | None:
    separator_positions = [(line.find(separator), separator) for separator in (":", "：") if separator in line]
    if not separator_positions:
        return None
    _, separator = min(separator_positions, key=lambda item: item[0])
    key, value = line.split(separator, 1)
    return key, value


def parse_recommendation_from_text(text: str) -> dict:
    rec_section = re.search(r"\[投資建議\](.*?)\[/投資建議\]", text or "", re.DOTALL)
    if not rec_section:
        return {}
    parsed = {}
    for line in rec_section.group(1).strip().split("\n"):
        parts = _split_key_value_line(line)
        if parts is None:
            continue
        key, val = parts
        normalized_key = key.strip()
        parsed[normalized_key] = (
            normalize_recommendation_label(val.strip())
            if normalized_key == "建議"
            else val.strip()
        )
    return parsed


def parse_structured_data(context: AnalysisContext) -> dict:
    """Parse moat scores, price targets, and recommendations from agent outputs."""
    parsed = {
        "moat_scores": {},
        "price_targets": {},
        "recommendation": {},
        "trade_setup": {},
    }

    structured_outputs = context.get("structured_outputs", {})
    analyses = context.get("analyses", {})
    moat_agent = get_structured_agent_num("moat", context)
    valuation_agent = get_structured_agent_num("valuation", context)
    recommendation_agent = get_structured_agent_num("recommendation", context)
    trade_setup_agent = get_structured_agent_num("trade_setup", context)
    if moat_agent is not None and moat_agent in structured_outputs:
        parsed["moat_scores"] = dict(structured_outputs[moat_agent].get("moat_scores", {}))
    if valuation_agent is not None and valuation_agent in structured_outputs:
        parsed["price_targets"] = dict(structured_outputs[valuation_agent].get("price_targets", {}))
    if recommendation_agent is not None and recommendation_agent in structured_outputs:
        parsed["recommendation"] = dict(structured_outputs[recommendation_agent].get("recommendation", {}))
        _normalize_parsed_recommendation(parsed["recommendation"])
    if trade_setup_agent is not None and trade_setup_agent in structured_outputs:
        parsed["trade_setup"] = {
            key: structured_outputs[trade_setup_agent].get(key, "")
            for key in (
                "trade_direction",
                "entry_zone",
                "target_price",
                "stop_loss",
                "core_catalyst",
                "risk_level",
            )
        }

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


def _normalize_parsed_recommendation(recommendation: dict) -> None:
    if "建議" in recommendation:
        recommendation["建議"] = normalize_recommendation_label(recommendation.get("建議"))
