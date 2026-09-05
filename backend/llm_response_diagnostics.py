"""Bounded observations only: no SDK objects, payloads, or inferred failure causes."""

from __future__ import annotations

import re
from contextlib import suppress

from llm_usage import extract_usage
from security_sanitizer import sanitize_error_message


MAX_LABELS = 16
MAX_LABEL_CHARS = 64
MAX_COUNT = (1 << 63) - 1


def _field(value, name, default=None):
    try:
        return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)
    except Exception:
        return default


def _items(value):
    return value if isinstance(value, (list, tuple)) else ()


def _label(value, *, reason=False):
    value = _field(value, "name", value)
    if not isinstance(value, str) or not value:
        return None
    if reason:
        value = value.rsplit(".", 1)[-1]
        return value if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value) else None
    # Tool identifiers are useful; free-form strings and credential-shaped values are not.
    value = value[:MAX_LABEL_CHARS]
    if sanitize_error_message(value) != value:
        return None
    return value if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]*", value) else None


def _add_label(labels, value, *, reason=False):
    label = _label(value, reason=reason)
    if label and label not in labels and len(labels) < MAX_LABELS:
        labels.append(label)


class ResponseDiagnostics:
    """Aggregate visible stream facts, never retain chunks or AFC history.

    Candidate count is the largest candidate list observed, not a sum per chunk.
    Usage and AFC histories are cumulative SDK snapshots, not token/call deltas.
    Function call counts describe observed parts, not confirmed tool executions.
    """

    def __init__(self, *, stream=False):
        self.stream = stream
        self._usage_fields = {}
        self.data = {
            "finish_reasons": [],
            "block_reason": None,
            "candidate_count": None,
            "function_call_count": 0,
            "function_call_names": [],
            "afc_history_present": False,
            "afc_function_call_count": 0,
            "afc_function_call_names": [],
            "usage": None,
        }
        if stream:
            self.data.update(stream_chunk_count=0, stream_completed=False, output_chars=0)

    def observe(self, response):
        if self.stream:
            self.data["stream_chunk_count"] = min(MAX_COUNT, self.data["stream_chunk_count"] + 1)
        candidates = _field(response, "candidates")
        if isinstance(candidates, (list, tuple)):
            self.data["candidate_count"] = min(MAX_COUNT, max(self.data["candidate_count"] or 0, len(candidates)))
        for candidate in _items(candidates):
            _add_label(self.data["finish_reasons"], _field(candidate, "finish_reason"), reason=True)
            count = self._observe_calls(_field(candidate, "content"), "function_call_names")
            self.data["function_call_count"] = min(MAX_COUNT, self.data["function_call_count"] + count)
        reason = _label(_field(_field(response, "prompt_feedback"), "block_reason"), reason=True)
        if reason:
            self.data["block_reason"] = reason
        history = _field(response, "automatic_function_calling_history")
        if isinstance(history, (list, tuple)):
            self.data["afc_history_present"] = True
            count = sum(self._observe_calls(content, "afc_function_call_names") for content in history)
            self.data["afc_function_call_count"] = min(MAX_COUNT, max(self.data["afc_function_call_count"], count))
        usage = extract_usage(response, include_missing=False)
        if usage:
            self._usage_fields.update(usage)
            self.data["usage"] = extract_usage({"usage": self._usage_fields})

    def _observe_calls(self, content, names_field):
        count = 0
        for part in _items(_field(content, "parts")):
            call = _field(part, "function_call")
            if call is not None:
                count += 1
                _add_label(self.data[names_field], _field(call, "name"))
        return count

    def add_text(self, delta):
        self.data["output_chars"] = min(MAX_COUNT, self.data["output_chars"] + len(delta))

    def snapshot(self):
        return {
            name: value.copy() if isinstance(value, (list, dict)) else value
            for name, value in self.data.items()
        }


def attach_response_diagnostics(exc, diagnostics):
    """Do not replace provider/cancellation exceptions or change retry classification."""
    with suppress(Exception):
        exc.llm_response_diagnostics = diagnostics.snapshot()


def response_diagnostics(response=None, *, error=None):
    # asyncio.wait_for chains TimeoutError from the cancelled stream's exception.
    current = error
    for _ in range(6):
        if current is None:
            break
        saved = _field(current, "llm_response_diagnostics")
        if isinstance(saved, dict):
            return _bounded_snapshot(saved)
        current = _field(current, "__cause__") or _field(current, "__context__")
    saved = _field(response, "diagnostics")
    if isinstance(saved, dict):
        return _bounded_snapshot(saved)
    if response is None:
        return None
    diagnostics = ResponseDiagnostics()
    diagnostics.observe(response)
    return diagnostics.snapshot()


def _bounded_snapshot(saved):
    snapshot = ResponseDiagnostics(stream=isinstance(saved.get("stream_completed"), bool)).snapshot()
    for name, default in snapshot.items():
        value = saved.get(name)
        if name == "usage":
            snapshot[name] = extract_usage({"usage": value})
        elif name == "block_reason":
            snapshot[name] = _label(value, reason=True)
        elif isinstance(default, list):
            for label in _items(value):
                _add_label(snapshot[name], label, reason=name == "finish_reasons")
                if len(snapshot[name]) == MAX_LABELS:
                    break
        elif isinstance(default, bool):
            snapshot[name] = value if isinstance(value, bool) else default
        elif isinstance(value, int) and not isinstance(value, bool):
            snapshot[name] = min(MAX_COUNT, max(0, value))
    return snapshot


def response_kind(result: str) -> str:
    if not result.strip():
        return "empty"
    return "short" if len(result) <= 100 else "text"
