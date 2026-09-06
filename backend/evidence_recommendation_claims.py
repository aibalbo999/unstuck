"""Bind explicit recommendation horizons to their own saved conclusion field."""

import re

from evidence_claim_numbers import clean_number

_HORIZONS = {"3": "短期目標（3個月）", "6": "中期目標（6個月）", "12": "長期目標（12個月）"}
_LABEL_PATHS = {
    "短期目標3個月": _HORIZONS["3"], "中期目標6個月": _HORIZONS["6"],
    "長期目標12個月": _HORIZONS["12"], "長期潛力5年": "長期潛力（5年）",
    **{f"{key}個月目標": value for key, value in _HORIZONS.items()},
}
_PAIR = re.compile(r"(?:^|[;；|])\s*(?:買入|買進|持有|避免|放空|觀望)?\s*(3|6|12)個月\s*[:：]\s*(?:NT\$|\$)?(-?\d[\d,]*(?:\.\d+)?)\s*(?:元|TWD)?(?=\s*(?:[;；|]|$))", re.I)


def recommendation_horizon_path(claim: dict, normalized_label: str) -> tuple[str, ...] | None:
    path = _LABEL_PATHS.get(normalized_label)
    text = re.sub(r"[*_`]", "", str(claim.get("raw_text") or ""))
    if not path and re.match(r"^\s*\|\s*最終投資建議\s*\|", text) and (horizon := re.search(r"(12|6|3)個月$", normalized_label)):
        pairs = [pair for pair in _PAIR.finditer(text) if pair.group(1) == horizon.group(1)]
        if len(pairs) == 1 and clean_number(pairs[0].group(2)) == claim.get("reported_value"):
            path = _HORIZONS[horizon.group(1)]
    if path:
        return () if claim.get("_legacy_conclusion_context_missing") else (f"rerun_context.parsed.recommendation.{path}",)
    return None
