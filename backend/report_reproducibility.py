"""Report confidence guardrails and reproducibility metadata."""

from __future__ import annotations

import os
import re
import math
from typing import Any

from data_trust_constants import SHA256_HEX_RE
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
    entries = dict.get(data, "source_audit") if isinstance(data, dict) else []
    providers: list[str] = []
    seen = set()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        provider = _safe_text(dict.get(entry, "provider")).strip()
        if provider and provider not in seen:
            providers.append(provider)
            seen.add(provider)
    return providers


def source_data_time(data: dict, data_trust: Any) -> str:
    trust = normalize_data_trust(data_trust)
    last_market_data_at = _safe_text(dict.get(trust, "last_market_data_at")).strip()
    if last_market_data_at:
        return last_market_data_at
    entries = dict.get(data, "source_audit") if isinstance(data, dict) else []
    fetched = []
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
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
    data = dict.get(context, "data", {}) if isinstance(context, dict) else {}
    if not isinstance(data, dict):
        data = {}
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


def detect_explicit_target_price_fields(context: dict) -> list[str]:
    fields: list[str] = []
    for root in ("parsed", "structured_outputs"):
        value = dict.get(context, root) if isinstance(context, dict) else None
        fields.extend(_detect_target_prices(value, (root,)))
    return sorted(dict.fromkeys(fields))


def _detect_target_prices(value: Any, path: tuple[str, ...]) -> list[str]:
    if isinstance(value, dict):
        fields: list[str] = []
        for key, item in _safe_dict_items(value):
            key_text = _safe_text(key)
            if not key_text:
                continue
            fields.extend(_detect_target_prices(item, (*path, key_text)))
        return fields
    if isinstance(value, list):
        fields = []
        for index, item in _safe_enumerate_list(value):
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
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    text = _safe_text(value).strip()
    if not text:
        return False
    upper_text = text.upper()
    if any(marker.upper() in upper_text for marker in _INSUFFICIENT_MARKERS):
        return False
    numbers = _PRICE_NUMBER_RE.findall(text)
    if len(numbers) >= 2 and any(marker in text for marker in _RANGE_MARKERS):
        return False
    return bool(numbers)


def _safe_enumerate_list(value: list) -> list[tuple[int, Any]]:
    items: list[tuple[int, Any]] = []
    try:
        iterator = iter(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        try:
            iterator = list.__iter__(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return items
    index = 0
    used_native = False
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            return items
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            if items or used_native:
                return items
            try:
                iterator = list.__iter__(value)
            except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
                return items
            used_native = True
            continue
        items.append((index, item))
        index += 1


def _safe_dict_items(value: dict) -> list[tuple[Any, Any]]:
    items: list[tuple[Any, Any]] = []
    try:
        raw_items = value.items()
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        try:
            raw_items = dict.items(value)
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return items
    used_native = False
    try:
        iterator = iter(raw_items)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        try:
            iterator = iter(dict.items(value))
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return items
        used_native = True
    while True:
        try:
            item = next(iterator)
        except StopIteration:
            return items
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            if items or used_native:
                return items
            try:
                iterator = iter(dict.items(value))
            except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
                return items
            used_native = True
            continue
        try:
            key, child = item
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            continue
        items.append((key, child))


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
    if value is None:
        return ""
    try:
        return str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ""


def _model_id(context: dict, data: dict) -> str:
    for key in ("model_id", "final_model_id", "decision_model_id"):
        value = _first_text(context, data, key)
        if value:
            return value
    metadata = dict.get(context, "metadata") if isinstance(context, dict) else None
    if isinstance(metadata, dict):
        model_id = _safe_text(dict.get(metadata, "model_id")).strip()
        if model_id:
            return model_id
    return "unknown"
