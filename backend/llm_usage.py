"""Provider token usage normalization helpers."""

from __future__ import annotations


def extract_usage(response) -> dict[str, int] | None:
    """Normalize provider token usage metadata when the provider exposes it."""
    if response is None:
        return None
    raw_usage = None
    if isinstance(response, dict):
        raw_usage = response.get("usage") or response.get("usage_metadata")
    if raw_usage is None:
        raw_usage = getattr(response, "usage", None) or getattr(response, "usage_metadata", None)
    if raw_usage is None:
        return None

    input_tokens = _usage_int(raw_usage, "input_tokens", "prompt_token_count", "prompt_tokens")
    output_tokens = _usage_int(raw_usage, "output_tokens", "candidates_token_count", "completion_tokens")
    total_tokens = _usage_int(raw_usage, "total_tokens", "total_token_count")
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
        value = raw_usage.get(name) if isinstance(raw_usage, dict) else getattr(raw_usage, name, None)
        if value is None:
            continue
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return None
