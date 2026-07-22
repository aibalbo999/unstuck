"""Report confidence guardrails and reproducibility metadata."""

from __future__ import annotations

import os
from typing import Any

from data_trust_constants import SHA256_HEX_RE
from data_trust_scoring import normalize_data_trust
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number
from report_target_price_detection import detect_explicit_target_price_fields


EXPLICIT_TARGET_PRICE_MIN_SCORE = 60
DEFAULT_PROMPT_VERSION = "runtime_rules:unversioned"
MISSING_TEXT_TOKENS = {
    "N/A",
    "NA",
    "NONE",
    "NULL",
    "NIL",
    "MISSING",
    "-",
    "--",
    "NAN",
    "INF",
    "+INF",
    "-INF",
    "INFINITY",
    "+INFINITY",
    "-INFINITY",
}


def data_confidence_score(data_trust: Any) -> int:
    trust = normalize_data_trust(data_trust)
    try:
        return max(0, min(int(round(float(trust.get("score")))), 100))
    except (TypeError, ValueError):
        return 35


def provider_list_from_audit(data: dict) -> list[str]:
    data = safe_mapping_dict(data) or {}
    entries = dict.get(data, "source_audit")
    providers: list[str] = []
    seen = set()
    for entry in safe_dict_list(entries):
        provider = _safe_text(dict.get(entry, "provider")).strip()
        if provider and provider not in seen:
            providers.append(provider)
            seen.add(provider)
    return providers


def source_data_time(data: dict, data_trust: Any) -> str:
    data = safe_mapping_dict(data) or {}
    trust = normalize_data_trust(data_trust)
    last_market_data_at = _safe_text(dict.get(trust, "last_market_data_at")).strip()
    if last_market_data_at:
        return last_market_data_at
    entries = dict.get(data, "source_audit")
    fetched = []
    for entry in safe_dict_list(entries):
        fetched_at = _safe_text(dict.get(entry, "fetched_at")).strip()
        if fetched_at:
            fetched.append(fetched_at)
    return max(fetched) if fetched else ""


def build_data_confidence_controls(context: dict, data_trust: Any) -> dict:
    score = data_confidence_score(data_trust)
    detected_fields = detect_explicit_target_price_fields(context)
    low_confidence = score < EXPLICIT_TARGET_PRICE_MIN_SCORE
    status = "restricted" if low_confidence else "sufficient"
    message = (
        "資料信心低於門檻；最終結論不得輸出明確目標價，只能使用區間或標示資料不足。"
        if low_confidence else
        "資料信心達到明確目標價門檻；仍需保留來源與快照追溯。"
    )
    return {
        "data_confidence_score": score,
        "data_confidence_status": status,
        "conclusion_guardrails": {
            "explicit_target_price": {
                "allowed": not low_confidence,
                "min_data_confidence_score": EXPLICIT_TARGET_PRICE_MIN_SCORE,
                "detected_fields": detected_fields,
                "action": "block_explicit_target_price" if low_confidence else "allow_with_traceability",
                "message": message,
            }
        },
    }


def build_reproducibility_packet(context: dict, data_trust: Any, generated_at: str) -> dict:
    context = safe_mapping_dict(context) or {}
    data = safe_mapping_dict(dict.get(context, "data")) or {}
    prompt_fingerprint = validated_prompt_fingerprint(_first_text(context, data, "prompt_fingerprint"))
    return {
        "ticker": _first_value_text(
            dict.get(context, "ticker") if isinstance(context, dict) else None,
            dict.get(data, "ticker"),
        ),
        "data_snapshot_hash": "",
        "prompt_version": _first_text(context, data, "prompt_version") or DEFAULT_PROMPT_VERSION,
        "prompt_fingerprint": prompt_fingerprint,
        "model_id": _model_id(context, data),
        "pipeline_id": _first_value_text(
            dict.get(context, "pipeline_id") if isinstance(context, dict) else None,
            dict.get(data, "pipeline_id"),
        ),
        "code_commit": _first_text(context, data, "code_commit") or os.getenv("GIT_COMMIT", ""),
        "code_dirty": _first_bool(context, data, "code_dirty"),
        "generated_at": _safe_text(generated_at),
        "provider_list": provider_list_from_audit(data),
        "source_data_time": source_data_time(data, data_trust),
    }


def _first_bool(context: dict, data: dict, key: str) -> bool | None:
    for source in (context, data):
        value = dict.get(source, key) if isinstance(source, dict) else None
        if isinstance(value, bool):
            return value
    return None


def validated_prompt_fingerprint(value: Any) -> str:
    fingerprint = _safe_text(value).strip().lower()
    return fingerprint if SHA256_HEX_RE.fullmatch(fingerprint) else ""


def _first_text(context: dict, data: dict, key: str) -> str:
    for source in (context, data):
        value = dict.get(source, key) if isinstance(source, dict) else None
        text = _safe_text(value).strip()
        if text:
            return text
    return ""


def _first_value_text(*values: Any) -> str:
    for value in values:
        text = _safe_text(value).strip()
        if text:
            return text
    return ""


def _safe_text(value: Any) -> str:
    if is_non_finite_number(value):
        return ""
    text = safe_text(value)
    if isinstance(value, str) and _is_missing_text_token(text):
        return ""
    return text


def _is_missing_text_token(text: str) -> bool:
    stripped = text.strip()
    return not stripped or stripped.upper() in MISSING_TEXT_TOKENS


def _model_id(context: dict, data: dict) -> str:
    for key in ("model_id", "final_model_id", "decision_model_id"):
        value = _first_text(context, data, key)
        if value:
            return value
    metadata = dict.get(context, "metadata") if isinstance(context, dict) else None
    metadata_map = safe_mapping_dict(metadata)
    if metadata_map is not None:
        model_id = _safe_text(dict.get(metadata_map, "model_id")).strip()
        if model_id:
            return model_id
    return "unknown"
