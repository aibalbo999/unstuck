"""Provider token usage normalization helpers."""

from __future__ import annotations


def extract_usage(response, *, include_missing: bool = True) -> dict[str, int] | None:
    """Normalize provider token usage metadata when the provider exposes it."""
    if response is None:
        return None
    raw_usage = _usage_field(response, "usage") or _usage_field(response, "usage_metadata")
    if raw_usage is None:
        return None

    input_tokens = _usage_int(raw_usage, "input_tokens", "prompt_token_count", "prompt_tokens")
    output_tokens = _usage_int(raw_usage, "output_tokens", "candidates_token_count", "completion_tokens")
    total_tokens = _usage_int(raw_usage, "total_tokens", "total_token_count")
    if not include_missing:
        return {
            name: value for name, value in {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            }.items() if value is not None
        } or None
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = int(input_tokens or 0) + int(output_tokens or 0)
    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    usage = {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
    }
    if total_tokens is not None:
        usage["total_tokens"] = int(total_tokens)
    return usage


def _usage_int(raw_usage, *names: str) -> int | None:
    for name in names:
        value = _usage_field(raw_usage, name)
        if value is None:
            continue
        try:
            return min((1 << 63) - 1, max(0, int(value)))
        except (TypeError, ValueError, OverflowError):
            continue
    return None


def _usage_field(value, name):
    try:
        return value.get(name) if isinstance(value, dict) else getattr(value, name, None)
    except Exception:
        return None
