"""Small, bounded completion observations shared by parsing and response caching."""
import re

INCOMPLETE_FINISH_REASONS = frozenset({"MAX_TOKENS", "LENGTH", "SAFETY", "RECITATION"})


def completion_diagnostics(value):
    value = value if isinstance(value, dict) else {}
    reasons = value.get("finish_reasons")
    reasons = reasons if isinstance(reasons, (list, tuple)) else []
    result = {"finish_reasons": [x for x in reasons if isinstance(x, str)
              and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", x)][:16]}
    if isinstance(value.get("stream_completed"), bool):
        result["stream_completed"] = value["stream_completed"]
    return result


def completion_is_incomplete(value):
    observed = completion_diagnostics(value)
    return bool(INCOMPLETE_FINISH_REASONS.intersection(observed["finish_reasons"])) or observed.get("stream_completed") is False
