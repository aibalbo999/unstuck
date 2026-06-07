"""RAG document collection and text normalization helpers."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from config import RAG_MIN_SOURCE_CHARS


INTERESTING_PATH_MARKERS = (
    "transcript",
    "earnings_call",
    "conference_call",
    "filing",
    "annual_report",
    "quarterly_report",
    "financial_report",
    "shareholder_letter",
    "presentation",
    "business_description",
    "long_business_summary",
    "news",
    "catalyst",
    "法說",
    "逐字稿",
    "財報",
    "年報",
    "季報",
    "新聞",
)

RECORD_TEXT_KEYS = (
    "title",
    "headline",
    "summary",
    "snippet",
    "description",
    "text",
    "content",
    "body",
    "transcript",
    "date",
    "source",
)


def _normalize_whitespace(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", str(text or ""))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _interesting_path(path: str) -> bool:
    lowered = path.lower()
    return any(marker.lower() in lowered for marker in INTERESTING_PATH_MARKERS)


def _clip_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(max_chars - 20, 0)].rstrip() + "\n...（RAG 片段截斷）"


def _record_to_text(record: dict[str, Any]) -> str:
    parts = []
    for key in RECORD_TEXT_KEYS:
        value = record.get(key)
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            try:
                value = json.dumps(value, ensure_ascii=False)
            except TypeError:
                value = str(value)
        value = str(value).strip()
        if value:
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def collect_rag_documents(data: dict[str, Any]) -> list[dict[str, str]]:
    """Collect only long or semantically rich text fields from a stock data payload."""
    documents: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_document(source: str, text: str):
        cleaned = _normalize_whitespace(text)
        if not cleaned:
            return
        if len(cleaned) < RAG_MIN_SOURCE_CHARS and not _interesting_path(source):
            return
        digest = hashlib.sha1(f"{source}:{cleaned}".encode("utf-8", "ignore")).hexdigest()
        if digest in seen:
            return
        seen.add(digest)
        documents.append({"source": source, "text": cleaned})

    def walk(value: Any, path: str, depth: int = 0):
        if depth > 5 or value is None:
            return
        if isinstance(value, str):
            add_document(path, value)
            return
        if isinstance(value, dict):
            record_text = _record_to_text(value)
            if record_text and (_interesting_path(path) or len(record_text) >= RAG_MIN_SOURCE_CHARS):
                add_document(path, record_text)
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key), depth + 1)
            return
        if isinstance(value, list):
            for idx, item in enumerate(value[:50]):
                walk(item, f"{path}[{idx}]", depth + 1)

    walk(data or {}, "data")
    return documents
