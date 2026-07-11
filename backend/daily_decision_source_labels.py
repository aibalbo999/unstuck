"""Human-readable labels for daily decision queue source keys."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping


SOURCE_LABELS = MappingProxyType({
    "report_repair": "報告修復",
    "provider_impact": "資料來源",
    "notification_delivery": "通知通道",
    "backtest_due": "決策回測",
    "rerun_report": "報告重跑",
    "model_route_budget": "模型路由",
    "watchlist": "追蹤清單",
    "screener": "候選清單",
    "free_mode": "免費模式",
    "monitor": "監控",
})


def source_key(source: Any) -> str:
    if not isinstance(source, str):
        return ""
    return source.strip()


def source_label(source: Any) -> str:
    key = source_key(source)
    return SOURCE_LABELS.get(key, key)


def source_text(source: Any) -> str:
    key = source_key(source)
    label = source_label(key)
    return f"{label} ({key})" if label != key else key


def _source_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        count = int(value or 0)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0
    if isinstance(value, str):
        return count
    try:
        if value != count:
            return 0
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return 0
    return count


def normalize_source_counts(sources: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source, count in _source_items(sources):
        key = source_key(source)
        value = _source_count(count)
        if key and value > 0:
            counts[key] = counts.get(key, 0) + value
    return counts


def source_display_overrides(active_sources: Mapping[str, Any], overrides: Mapping[str, Any] | None) -> dict[str, str]:
    active_keys = {key for source in _source_keys(active_sources) if (key := source_key(source))}
    result: dict[str, str] = {}
    for source, value in _source_items(overrides):
        key = source_key(source)
        if key in active_keys and isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


def _source_items(sources: Any) -> list[tuple[Any, Any]]:
    items = getattr(sources, "items", None)
    if not callable(items):
        return []
    try:
        raw_items = items()
    except (TypeError, ValueError, RuntimeError, AttributeError):
        return []
    try:
        item_iter = iter(raw_items)
    except (TypeError, ValueError, RuntimeError, AttributeError):
        return []
    source_items: list[tuple[Any, Any]] = []
    while True:
        try:
            item = next(item_iter)
        except StopIteration:
            break
        except (TypeError, ValueError, RuntimeError, AttributeError):
            break
        if isinstance(item, (str, bytes)):
            continue
        try:
            source, value = item
        except (TypeError, ValueError, RuntimeError, AttributeError):
            continue
        source_items.append((source, value))
    return source_items


def _source_keys(sources: Any) -> list[Any]:
    keys = getattr(sources, "keys", None)
    if not callable(keys):
        return []
    try:
        raw_keys = keys()
    except (TypeError, ValueError, RuntimeError, AttributeError):
        return []
    if isinstance(raw_keys, (str, bytes)):
        return []
    try:
        key_iter = iter(raw_keys)
    except (TypeError, ValueError, RuntimeError, AttributeError):
        return []
    source_keys: list[Any] = []
    while True:
        try:
            source_keys.append(next(key_iter))
        except StopIteration:
            break
        except (TypeError, ValueError, RuntimeError, AttributeError):
            break
    return source_keys


def source_labels(sources: Any) -> dict[str, str]:
    labels: dict[str, str] = {}
    for source in _source_keys(sources):
        key = source_key(source)
        if key:
            labels[key] = source_label(key)
    return labels


def source_texts(sources: Any) -> dict[str, str]:
    texts: dict[str, str] = {}
    for source in _source_keys(sources):
        key = source_key(source)
        if key:
            texts[key] = source_text(key)
    return texts
