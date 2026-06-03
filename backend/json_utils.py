"""Robust JSON extraction helpers for LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

try:
    from json_repair import repair_json
except Exception:  # pragma: no cover - optional dependency in older installs
    repair_json = None


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _candidate_json_texts(raw_text: str) -> list[str]:
    text = _strip_code_fence(raw_text)
    candidates = [text]

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])

    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _lightweight_repair(text: str) -> str:
    """Repair common model JSON mistakes without changing semantic content."""
    repaired = text.strip()
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    repaired = repaired.replace("\u201c", '"').replace("\u201d", '"')
    repaired = repaired.replace("\u2018", "'").replace("\u2019", "'")
    return repaired


def extract_json_payload(raw_text: str) -> Optional[dict[str, Any]]:
    """Parse a dict JSON payload from model output, tolerating fences and minor syntax issues."""
    if not raw_text:
        return None

    for candidate in _candidate_json_texts(raw_text):
        for variant in (candidate, _lightweight_repair(candidate)):
            try:
                payload = json.loads(variant)
                return payload if isinstance(payload, dict) else None
            except json.JSONDecodeError:
                pass

        if repair_json is None:
            continue

        try:
            repaired = repair_json(candidate)
            payload = json.loads(repaired)
            return payload if isinstance(payload, dict) else None
        except Exception:
            continue

    return None
