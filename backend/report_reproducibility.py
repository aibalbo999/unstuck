"""Report confidence guardrails and reproducibility metadata."""

from __future__ import annotations

import os
import re
from typing import Any

from data_trust_scoring import normalize_data_trust


EXPLICIT_TARGET_PRICE_MIN_SCORE = 60
DEFAULT_PROMPT_VERSION = "runtime_rules:unversioned"
_PRICE_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_TARGET_KEY_MARKERS = (
    "target_price",
    "price_targets",
    "targetprice",
    "目標價",
    "目標",
    "3個月",
    "6個月",
    "12個月",
    "1-2週目標",
)
_RANGE_MARKERS = ("~", "-", "–", "—", "至", "到", "區間", "range")
_INSUFFICIENT_MARKERS = ("資料不足", "不足", "無法", "不產生", "不提供", "未提供", "N/A", "NA")


def data_confidence_score(data_trust: Any) -> int:
    trust = normalize_data_trust(data_trust)
    try:
        return max(0, min(int(round(float(trust.get("score")))), 100))
    except (TypeError, ValueError):
        return 35


def provider_list_from_audit(data: dict) -> list[str]:
    entries = data.get("source_audit") if isinstance(data, dict) else []
    providers: list[str] = []
    seen = set()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        provider = str(entry.get("provider") or "").strip()
        if provider and provider not in seen:
            providers.append(provider)
            seen.add(provider)
    return providers


def source_data_time(data: dict, data_trust: Any) -> str:
    trust = normalize_data_trust(data_trust)
    if trust.get("last_market_data_at"):
        return str(trust.get("last_market_data_at"))
    entries = data.get("source_audit") if isinstance(data, dict) else []
    fetched = [
        str(entry.get("fetched_at"))
        for entry in entries if isinstance(entry, dict) and entry.get("fetched_at")
    ] if isinstance(entries, list) else []
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
    data = context.get("data", {}) if isinstance(context, dict) else {}
    if not isinstance(data, dict):
        data = {}
    return {
        "ticker": str(context.get("ticker") or data.get("ticker") or ""),
        "data_snapshot_hash": "",
        "prompt_version": _first_text(context, data, "prompt_version") or DEFAULT_PROMPT_VERSION,
        "model_id": _model_id(context, data),
        "pipeline_id": str(context.get("pipeline_id") or data.get("pipeline_id") or ""),
        "code_commit": _first_text(context, data, "code_commit") or os.getenv("GIT_COMMIT", ""),
        "generated_at": str(generated_at or ""),
        "provider_list": provider_list_from_audit(data),
        "source_data_time": source_data_time(data, data_trust),
    }


def detect_explicit_target_price_fields(context: dict) -> list[str]:
    fields: list[str] = []
    for root in ("parsed", "structured_outputs"):
        value = context.get(root) if isinstance(context, dict) else None
        fields.extend(_detect_target_prices(value, (root,)))
    return sorted(dict.fromkeys(fields))


def _detect_target_prices(value: Any, path: tuple[str, ...]) -> list[str]:
    if isinstance(value, dict):
        fields: list[str] = []
        for key, item in value.items():
            fields.extend(_detect_target_prices(item, (*path, str(key))))
        return fields
    if isinstance(value, list):
        fields = []
        for index, item in enumerate(value):
            fields.extend(_detect_target_prices(item, (*path, str(index))))
        return fields
    if _is_target_path(path) and _is_explicit_price(value):
        return [".".join(path)]
    return []


def _is_target_path(path: tuple[str, ...]) -> bool:
    key_text = ".".join(path).lower().replace(" ", "")
    return any(marker.lower().replace(" ", "") in key_text for marker in _TARGET_KEY_MARKERS)


def _is_explicit_price(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    text = str(value).strip()
    if not text:
        return False
    upper_text = text.upper()
    if any(marker.upper() in upper_text for marker in _INSUFFICIENT_MARKERS):
        return False
    numbers = _PRICE_NUMBER_RE.findall(text)
    if len(numbers) >= 2 and any(marker in text for marker in _RANGE_MARKERS):
        return False
    return bool(numbers)


def _first_text(context: dict, data: dict, key: str) -> str:
    for source in (context, data):
        value = source.get(key) if isinstance(source, dict) else None
        if str(value or "").strip():
            return str(value).strip()
    return ""


def _model_id(context: dict, data: dict) -> str:
    for key in ("model_id", "final_model_id", "decision_model_id"):
        value = _first_text(context, data, key)
        if value:
            return value
    metadata = context.get("metadata") if isinstance(context, dict) else None
    if isinstance(metadata, dict) and str(metadata.get("model_id") or "").strip():
        return str(metadata.get("model_id")).strip()
    return "unknown"
