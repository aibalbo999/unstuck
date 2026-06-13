"""Multi-source financial data cross-validation layer.

Compares core financial fields across yfinance, FMP, and future sources.
Flags divergences above threshold and upgrades data_trust accordingly.
"""

from __future__ import annotations

from typing import Any, Optional


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

# Fields to cross-validate (fin_data key -> human-readable label)
CROSS_VALIDATE_FIELDS: dict[str, str] = {
    "revenue_ttm_raw": "TTM 營收",
    "net_income_ttm_raw": "TTM 淨利",
    "free_cash_flow_raw": "自由現金流",
    "pe_ratio_raw": "本益比（TTM P/E）",
    "pb_ratio": "股價淨值比（P/B）",
    "gross_margin_raw": "毛利率",
    "operating_margin_raw": "營業利益率",
    "profit_margin_raw": "淨利率",
    "market_cap_raw": "市值",
    "total_debt_raw": "總負債",
    "current_price": "當前股價",
}

# Divergence threshold: above this % → flag as divergent
DIVERGENCE_THRESHOLD_PCT = 5.0

# If any field diverges beyond this → escalate to 'conflict'
CONFLICT_THRESHOLD_PCT = 20.0


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "N/A":
        return None
    try:
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("NT$", "").replace("$", "").replace("%", "").strip()
            if not cleaned:
                return None
            value = cleaned
        result = float(value)
        import math
        if not math.isfinite(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _relative_divergence(a: float, b: float) -> float:
    """Return |a-b| / max(|a|, |b|, 1) as percentage."""
    return abs(a - b) / max(abs(a), abs(b), 1.0) * 100


def _median_of(*values: Optional[float]) -> Optional[float]:
    """Return median of non-None values."""
    valid = sorted(v for v in values if v is not None)
    n = len(valid)
    if n == 0:
        return None
    if n % 2 == 1:
        return valid[n // 2]
    return (valid[n // 2 - 1] + valid[n // 2]) / 2


# ------------------------------------------------------------------
# Core validation
# ------------------------------------------------------------------

def cross_validate_field(
    field_key: str,
    sources: dict[str, Any],
) -> dict:
    """Cross-validate a single financial field across multiple sources.

    Args:
        field_key: The data field name (e.g. 'revenue_ttm_raw').
        sources: Dict of {source_name: raw_value}, e.g.
                 {'yfinance': 2.3e12, 'fmp': 2.31e12, 'twse': None}

    Returns:
        {
            'field': field_key,
            'values': {source: float_or_None, ...},
            'consensus_value': float | None,
            'max_divergence_pct': float | None,
            'verdict': 'aligned' | 'divergent' | 'conflict' | 'insufficient_data',
            'divergent_sources': [source, ...],
        }
    """
    numeric: dict[str, Optional[float]] = {
        src: _safe_float(val) for src, val in sources.items()
    }
    valid = {src: v for src, v in numeric.items() if v is not None}

    if len(valid) < 2:
        return {
            "field": field_key,
            "values": numeric,
            "consensus_value": next(iter(valid.values()), None),
            "max_divergence_pct": None,
            "verdict": "insufficient_data",
            "divergent_sources": [],
        }

    consensus = _median_of(*valid.values())
    divergences: dict[str, float] = {
        src: _relative_divergence(v, consensus)
        for src, v in valid.items()
        if consensus is not None
    }
    max_div = max(divergences.values()) if divergences else 0.0

    if max_div >= CONFLICT_THRESHOLD_PCT:
        verdict = "conflict"
    elif max_div >= DIVERGENCE_THRESHOLD_PCT:
        verdict = "divergent"
    else:
        verdict = "aligned"

    divergent_sources = [
        src for src, pct in divergences.items()
        if pct >= DIVERGENCE_THRESHOLD_PCT
    ]

    return {
        "field": field_key,
        "label": CROSS_VALIDATE_FIELDS.get(field_key, field_key),
        "values": numeric,
        "consensus_value": consensus,
        "max_divergence_pct": round(max_div, 2),
        "verdict": verdict,
        "divergent_sources": divergent_sources,
    }


def cross_validate_sources(
    primary_data: dict,
    supplementary_sources: dict[str, dict],
) -> dict:
    """Run cross-validation across all configured fields.

    Args:
        primary_data: Main data dict (yfinance-based, the system's `data`).
        supplementary_sources: Additional source dicts keyed by source name,
            e.g. {'fmp': {...}, 'twse': {...}}.

    Returns:
        {
            'overall_verdict': 'aligned' | 'divergent' | 'conflict' | 'insufficient_data',
            'fields': {field_key: cross_validate_field_result, ...},
            'conflict_fields': [field_key, ...],
            'divergent_fields': [field_key, ...],
            'notes': [str, ...],
            'data_trust_penalty': int,   # suggested score penalty (0-20)
        }
    """
    field_results: dict[str, dict] = {}
    conflict_fields: list[str] = []
    divergent_fields: list[str] = []

    for field_key in CROSS_VALIDATE_FIELDS:
        sources: dict[str, Any] = {"yfinance": primary_data.get(field_key)}
        for source_name, source_data in (supplementary_sources or {}).items():
            sources[source_name] = source_data.get(field_key) if isinstance(source_data, dict) else None

        result = cross_validate_field(field_key, sources)
        field_results[field_key] = result

        if result["verdict"] == "conflict":
            conflict_fields.append(field_key)
        elif result["verdict"] == "divergent":
            divergent_fields.append(field_key)

    # Determine overall verdict
    if conflict_fields:
        overall = "conflict"
    elif divergent_fields:
        overall = "divergent"
    elif all(r["verdict"] == "insufficient_data" for r in field_results.values()):
        overall = "insufficient_data"
    else:
        overall = "aligned"

    # Build notes
    notes: list[str] = []
    if conflict_fields:
        labels = [CROSS_VALIDATE_FIELDS.get(f, f) for f in conflict_fields]
        notes.append(f"跨來源嚴重衝突欄位（差距 >{CONFLICT_THRESHOLD_PCT}%）：{'、'.join(labels)}；建議人工查核原始資料。")
    if divergent_fields:
        labels = [CROSS_VALIDATE_FIELDS.get(f, f) for f in divergent_fields]
        notes.append(f"跨來源差異欄位（差距 {DIVERGENCE_THRESHOLD_PCT}-{CONFLICT_THRESHOLD_PCT}%）：{'、'.join(labels)}；分析已採用中位數共識口徑。")

    # Suggest data_trust penalty
    penalty = 0
    penalty += min(20, len(conflict_fields) * 8)
    penalty += min(10, len(divergent_fields) * 3)

    return {
        "overall_verdict": overall,
        "fields": field_results,
        "conflict_fields": conflict_fields,
        "divergent_fields": divergent_fields,
        "notes": notes,
        "data_trust_penalty": penalty,
        "sources_compared": ["yfinance"] + list((supplementary_sources or {}).keys()),
    }


def apply_cross_validation_to_data(
    data: dict,
    supplementary_sources: dict[str, dict],
) -> dict:
    """Run cross-validation and inject results + penalty into data dict in-place.

    This mutates `data` by:
    - Adding `data['cross_validation']` with full results.
    - Appending notes to `data['data_source_notes']`.
    - Storing `data['cross_validation_penalty']` for trust scoring downstream.
    """
    if not supplementary_sources:
        return data

    result = cross_validate_sources(data, supplementary_sources)
    data["cross_validation"] = result
    data["cross_validation_penalty"] = result.get("data_trust_penalty", 0)

    existing_notes: list = data.get("data_source_notes") or []
    for note in result.get("notes", []):
        if note not in existing_notes:
            existing_notes.append(note)
    data["data_source_notes"] = existing_notes

    return data
