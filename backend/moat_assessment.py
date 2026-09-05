"""Evidence-preserving moat score projection shared by schemas and reports."""

from __future__ import annotations

import math
import re

from mapping_fields import safe_mapping_dict


MOAT_FIELDS = {
    "品牌影響力": "brand_influence",
    "網路效應": "network_effect",
    "轉換成本": "switching_cost",
    "成本優勢": "cost_advantage",
    "專利技術": "patent_technology",
    "整體護城河": "overall_moat",
}


def moat_score(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:/\s*10|分)?\s*", value)
        if not match:
            return None
        value = match.group(1)
    try:
        score = float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None
    return round(score, 2) if math.isfinite(score) and 1 <= score <= 10 else None


def normalize_moat_evidence(value) -> dict[str, float | None]:
    scores = safe_mapping_dict(value) or {}
    result = {}
    for label, alias in MOAT_FIELDS.items():
        # Only genuine string keys participate; unknown never borrows another field.
        raw = next((item for key, item in scores.items() if type(key) is str and key == label), None)
        if not any(type(key) is str and key == label for key in scores):
            raw = next((item for key, item in scores.items() if type(key) is str and key == alias), None)
        result[label] = moat_score(raw)
    return result


def moat_assessment(value) -> dict:
    scores = normalize_moat_evidence(value)
    unknown = [key for key, score in scores.items() if score is None]
    status = "unassessed" if len(unknown) == len(scores) else "partial" if unknown else "assessed"
    return {"status": status, "unassessed_fields": unknown, "assessed_count": len(scores) - len(unknown)}
