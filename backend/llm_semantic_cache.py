"""Optional semantic-ish cache for provider text LLM responses."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from typing import Any

from cache_store import get_cache_json, set_cache_json
from config import (
    LLM_SEMANTIC_CACHE_ENABLED,
    LLM_SEMANTIC_CACHE_MAX_INDEX_ENTRIES,
    LLM_SEMANTIC_CACHE_MIN_SIMILARITY,
    LLM_SEMANTIC_CACHE_SECONDS,
)


SCHEMA_VERSION = 1
_WORD_RE = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]+", re.IGNORECASE)
_CONFIG_FIELDS = (
    "temperature",
    "top_p",
    "top_k",
    "max_output_tokens",
    "response_mime_type",
    "system_instruction",
)


def get_cached_llm_response(model_id: str, prompt: str, config: Any) -> dict | None:
    if not _cache_enabled():
        return None
    exact_key = _entry_key(model_id, prompt, config)
    exact = _load_entry(exact_key)
    if exact is not None:
        exact["cache_match"] = "exact"
        exact["cache_similarity"] = 1.0
        return exact

    threshold = float(LLM_SEMANTIC_CACHE_MIN_SIMILARITY)
    if threshold >= 1.0:
        return None

    prompt_features = _prompt_features(prompt)
    best_key = ""
    best_score = 0.0
    try:
        index = get_cache_json(_index_key(model_id, config))
    except Exception:
        return None
    if not isinstance(index, list):
        return None
    for item in index:
        if not isinstance(item, dict):
            continue
        entry_key = str(item.get("entry_key") or "")
        candidate_features = item.get("features")
        if not entry_key or not isinstance(candidate_features, list):
            continue
        score = _feature_similarity(prompt_features, candidate_features)
        if score > best_score:
            best_key = entry_key
            best_score = score

    if not best_key or best_score < threshold:
        return None
    entry = _load_entry(best_key)
    if entry is None:
        return None
    entry["cache_match"] = "semantic"
    entry["cache_similarity"] = best_score
    return entry


def store_llm_response(
    model_id: str,
    prompt: str,
    config: Any,
    *,
    text: str,
    usage: dict[str, int] | None = None,
) -> None:
    if not _cache_enabled() or not str(text or "").strip():
        return
    features = _prompt_features(prompt)
    entry_key = _entry_key(model_id, prompt, config)
    entry = {
        "schema_version": SCHEMA_VERSION,
        "model_id": str(model_id or ""),
        "config_fingerprint": _config_fingerprint(config),
        "prompt_fingerprint": _sha256_text(_canonical_prompt(prompt)),
        "features": features,
        "text": str(text or ""),
        "usage": usage or None,
        "created_at": time.time(),
    }
    try:
        set_cache_json(entry_key, entry, LLM_SEMANTIC_CACHE_SECONDS)
        _update_index(model_id, config, entry_key, features)
    except Exception:
        return


def _cache_enabled() -> bool:
    return bool(LLM_SEMANTIC_CACHE_ENABLED) and int(LLM_SEMANTIC_CACHE_SECONDS) > 0


def _load_entry(cache_key: str) -> dict | None:
    try:
        cached = get_cache_json(cache_key)
    except Exception:
        return None
    if not isinstance(cached, dict):
        return None
    if cached.get("schema_version") != SCHEMA_VERSION:
        return None
    text = str(cached.get("text") or "")
    if not text.strip():
        return None
    usage = cached.get("usage")
    return {
        "text": text,
        "usage": usage if isinstance(usage, dict) else None,
        "model_id": str(cached.get("model_id") or ""),
    }


def _update_index(model_id: str, config: Any, entry_key: str, features: list[str]) -> None:
    index_key = _index_key(model_id, config)
    cached_index = get_cache_json(index_key)
    index = cached_index if isinstance(cached_index, list) else []
    index = [item for item in index if isinstance(item, dict) and item.get("entry_key") != entry_key]
    index.insert(
        0,
        {
            "entry_key": entry_key,
            "features": features,
            "created_at": time.time(),
        },
    )
    max_entries = max(1, int(LLM_SEMANTIC_CACHE_MAX_INDEX_ENTRIES))
    set_cache_json(index_key, index[:max_entries], LLM_SEMANTIC_CACHE_SECONDS)


def _entry_key(model_id: str, prompt: str, config: Any) -> str:
    payload = {
        "model_id": str(model_id or ""),
        "config": _config_fingerprint(config),
        "prompt": _canonical_prompt(prompt),
    }
    return "llm_semantic:entry:" + _sha256_json(payload)


def _index_key(model_id: str, config: Any) -> str:
    payload = {
        "model_id": str(model_id or ""),
        "config": _config_fingerprint(config),
    }
    return "llm_semantic:index:" + _sha256_json(payload)


def _config_fingerprint(config: Any) -> str:
    values: dict[str, Any] = {}
    if config is not None:
        for field in _CONFIG_FIELDS:
            value = getattr(config, field, None)
            if value is not None:
                values[field] = _jsonable(value)
        for field in ("response_schema", "tools", "automatic_function_calling"):
            value = getattr(config, field, None)
            if value is not None:
                values[f"{field}_hash"] = _sha256_text(repr(value))
    return _sha256_json(values)


def _canonical_prompt(prompt: str) -> str:
    return re.sub(r"\s+", " ", str(prompt or "").strip().lower())


def _prompt_features(prompt: str) -> list[str]:
    text = _canonical_prompt(prompt)
    features: set[str] = set()
    for match in _WORD_RE.findall(text):
        token = match.lower()
        if _is_cjk(token):
            features.update(token)
            features.update(token[index : index + 2] for index in range(max(0, len(token) - 1)))
        elif len(token) >= 2:
            features.add(token)
    if not features and text:
        compact = re.sub(r"\s+", "", text)
        features.update(compact[index : index + 3] for index in range(max(1, len(compact) - 2)))
    return sorted(feature for feature in features if feature)[:512]


def _feature_similarity(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(str(item) for item in right)
    if not left_set or not right_set:
        return 0.0
    overlap = len(left_set & right_set)
    if overlap == 0:
        return 0.0
    return overlap / math.sqrt(len(left_set) * len(right_set))


def _is_cjk(token: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in token)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    return repr(value)


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(encoded)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()
