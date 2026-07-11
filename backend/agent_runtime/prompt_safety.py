"""Safe coercion helpers for agent prompt assembly."""

import json


def _safe_prompt_text(value, fallback: str = "") -> str:
    try:
        text = str(value).strip()
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return fallback
    return text if text else fallback


def _safe_prompt_text_list(value, *, limit: int | None = None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _safe_prompt_text(value)
        return [text] if text else []
    try:
        iterator = _safe_prompt_sequence_iterator(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        text = _safe_prompt_text(value)
        return [text] if text else []

    results: list[str] = []
    try:
        for item in iterator:
            text = _safe_prompt_text(item)
            if text:
                results.append(text)
            if limit is not None and len(results) >= limit:
                break
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        pass
    return results


def _safe_prompt_sequence_iterator(value):
    if isinstance(value, list):
        return list.__iter__(value)
    if isinstance(value, tuple):
        return tuple.__iter__(value)
    if isinstance(value, set):
        return set.__iter__(value)
    if isinstance(value, frozenset):
        return frozenset.__iter__(value)
    return iter(value)


def _safe_prompt_json_item(value):
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        if isinstance(value, dict):
            result = {}
            try:
                items = dict.items(value)
                for key, item in items:
                    safe_key = _safe_prompt_text(key)
                    if safe_key:
                        result[safe_key] = _safe_prompt_json_item(item)
            except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
                pass
            return result
        if not isinstance(value, str):
            try:
                _safe_prompt_sequence_iterator(value)
            except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
                pass
            else:
                return _safe_prompt_json_list(value)
        text = _safe_prompt_text(value)
        return text if text else None
    return value


def _safe_prompt_json_list(value, *, limit: int | None = None) -> list:
    if value is None:
        return []
    if isinstance(value, dict):
        item = _safe_prompt_json_item(value)
        return [item] if item is not None else []
    if isinstance(value, str):
        text = _safe_prompt_text(value)
        return [text] if text else []
    try:
        iterator = _safe_prompt_sequence_iterator(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        item = _safe_prompt_json_item(value)
        return [item] if item is not None else []

    results = []
    try:
        for item in iterator:
            safe_item = _safe_prompt_json_item(item)
            if safe_item is not None:
                results.append(safe_item)
            if limit is not None and len(results) >= limit:
                break
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        pass
    return results


def _safe_bool_flag(value) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False
