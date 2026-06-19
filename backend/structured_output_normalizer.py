"""Normalize structured-agent JSON and convert it to report text."""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import ValidationError

from confidence_calibration import build_confidence_calibration, confidence_score
from structured_output_models import (
    BubbleSniperStructuredOutput,
    MoatStructuredOutput,
    PriceTargetStructuredOutput,
    RecommendationStructuredOutput,
)


STRICT_STRUCTURED_SCHEMAS = {
    3: MoatStructuredOutput,
    4: PriceTargetStructuredOutput,
    7: RecommendationStructuredOutput,
    12: MoatStructuredOutput,
    14: PriceTargetStructuredOutput,
    16: RecommendationStructuredOutput,
    19: BubbleSniperStructuredOutput,
}


def _validated_payload(agent_num: int, payload: dict) -> Optional[dict]:
    schema = STRICT_STRUCTURED_SCHEMAS.get(agent_num)
    if schema is None:
        return payload
    try:
        return schema.model_validate(payload).model_dump(by_alias=True)
    except ValidationError:
        return None


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


def _coerce_reasoning_steps(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        return []
    steps = []
    for item in candidates:
        text = str(item).strip()
        if text:
            steps.append(text)
    return steps


def _coerce_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def normalize_structured_output(agent_num: int, payload: Optional[dict]) -> Optional[dict]:
    """Validate and normalize JSON payloads from structured agents."""
    if not isinstance(payload, dict):
        return None
    payload = _validated_payload(agent_num, payload)
    if payload is None:
        return None

    if agent_num in {3, 12}:
        raw_scores = payload.get("moat_scores", {})
        reasoning_steps = _coerce_reasoning_steps(payload.get("reasoning_steps"))
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
            "reasoning_steps": reasoning_steps,
            "moat_scores": scores,
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num in {4, 14}:
        raw_targets = payload.get("price_targets", {})
        if not isinstance(raw_targets, dict):
            raw_targets = {}
        valuation_reasoning = {
            "dcf_reasoning": _coerce_text(_pick_mapping_value(raw_targets, "dcf_reasoning", "DCF推論", "DCF 推論")),
            "peer_reasoning": _coerce_text(_pick_mapping_value(raw_targets, "peer_reasoning", "同業推論", "同業比較推論")),
            "scenario_reasoning": _coerce_text(_pick_mapping_value(raw_targets, "scenario_reasoning", "情境推論", "情境差異推論")),
        }
        raw_root_reasoning = payload.get("valuation_reasoning")
        if isinstance(raw_root_reasoning, dict):
            for key in ("dcf_reasoning", "peer_reasoning", "scenario_reasoning"):
                if not valuation_reasoning.get(key):
                    valuation_reasoning[key] = _coerce_text(raw_root_reasoning.get(key))
        valuation_reasoning = {key: value for key, value in valuation_reasoning.items() if value}
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
            "valuation_reasoning": valuation_reasoning,
            "valuation_summary": payload.get("valuation_summary", {}) if isinstance(payload.get("valuation_summary"), dict) else {},
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num in {7, 16, 19}:
        raw_rec = payload.get("recommendation", {})
        reasoning_steps = _coerce_reasoning_steps(payload.get("reasoning_steps"))
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
            
        confidence_basis = payload.get("confidence_basis")
        if isinstance(confidence_basis, dict):
            normalized_rec["confidence_basis"] = confidence_basis

        return {
            "reasoning_steps": reasoning_steps,
            "recommendation": normalized_rec,
            "scenario_triggers": payload.get("scenario_triggers", []),
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    return None


def structured_output_to_report_text(agent_num: int, structured: dict, fallback_text: str = "") -> str:
    """Convert parsed JSON into the legacy report text expected by renderers."""
    body = structured.get("analysis_markdown") or fallback_text

    if agent_num in {3, 12}:
        scores = structured.get("moat_scores", {})
        score_lines = "\n".join(f"{key}: {scores[key]}" for key in scores)
        return f"[護城河評分]\n{score_lines}\n[/護城河評分]\n\n{body}".strip()

    if agent_num in {4, 14}:
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

    if agent_num in {7, 16, 19}:
        rec = structured.get("recommendation", {})
        display_rec = {k: v for k, v in rec.items() if not isinstance(v, dict)}
        separator = "：" if agent_num == 19 else ": "
        rec_lines = "\n".join(f"{key}{separator}{value}" for key, value in display_rec.items())
        
        basis = rec.get("confidence_basis", {})
        basis_text = ""
        if basis:
            basis_text += "\n\n### 信心依據\n"
            for ev in basis.get("evidence_items", []):
                basis_text += f"- **具體佐證**: {ev}\n"
            for rsk in basis.get("key_risks_acknowledged", []):
                basis_text += f"- **已納入考量的風險**: {rsk}\n"
            for gap in basis.get("data_gaps", []):
                basis_text += f"- **已知缺口**: {gap}\n"
                
        triggers = structured.get("scenario_triggers", [])
        trigger_text = ""
        if triggers:
            trigger_text += "\n\n### 情境觸發器\n"
            for t in triggers:
                trigger_text += f"- 若「{t.get('trigger_condition', '')}」：建議 {t.get('action', '')}\n"

        recommendation_block = f"[投資建議]\n{rec_lines}\n[/投資建議]"
        if agent_num == 19:
            return f"{body}{basis_text}{trigger_text}\n\n{recommendation_block}".strip()
        return f"{recommendation_block}\n\n{body}{basis_text}{trigger_text}".strip()

    return fallback_text


def price_targets_have_unit_error(targets: dict, current_price) -> bool:
    """Detect NT$5-style target prices when the stock trades in the hundreds/thousands."""
    if not isinstance(current_price, (int, float)) or current_price <= 100:
        return False
    prices = [value for value in targets.values() if isinstance(value, (int, float))]
    return bool(prices) and any(price < current_price * 0.05 for price in prices)


def warn_high_confidence_with_low_trust(agent_num: int, structured: dict, context: dict) -> None:
    if agent_num not in {7, 16, 19}:
        return
    trust = context.get("data", {}).get("data_trust", {}) if isinstance(context.get("data"), dict) else {}
    calibration = build_confidence_calibration(structured.get("recommendation", {}) or {}, trust)
    context["confidence_calibration"] = calibration
    if calibration.get("status") != "needs_downgrade":
        return
    status = calibration.get("data_trust_status", "unknown")
    confidence = calibration.get("raw_confidence", "N/A")
    cap = calibration.get("max_recommended_confidence")
    context.setdefault("structured_quality_warnings", []).append(
        f"Agent {agent_num} 在 data_trust={status} 時給出高信心（{confidence}），建議信心上限 {cap}/10，需於報告中明確說明資料限制。"
    )


_confidence_score = confidence_score
_warn_high_confidence_with_low_trust = warn_high_confidence_with_low_trust
