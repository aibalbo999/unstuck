"""Bound formatted retrieval evidence at complete excerpt boundaries."""

from __future__ import annotations

import re

from llm_rate_limits import estimate_text_tokens


EXCERPT_START = re.compile(r"(?m)^\u3010\u7247\u6bb5 \d+\uff5c\u4f86\u6e90\uff1a")
OMISSION_NOTE = (
    "[RAG evidence budget] Some retrieved excerpts were omitted to fit this agent's "
    "evidence budget. Omitted content is unavailable, not evidence of absence."
)


def limit_rag_evidence(text: str, *, max_chars: int, max_chunks: int, token_budget: int) -> str:
    """Keep citations and their bodies together; unknown text is one atomic record."""
    starts = [match.start() for match in EXCERPT_START.finditer(text)]
    header = text[:starts[0]].strip() if starts else ""
    ends = starts[1:] + [len(text)]
    chunks = [text[start:end].strip() for start, end in zip(starts, ends)] if starts else [text]

    def fits(candidate: str) -> bool:
        return len(candidate) <= max_chars and (token_budget <= 0 or estimate_text_tokens(candidate) <= token_budget)

    if fits(text) and len(chunks) <= max_chunks:
        return text
    if not fits(OMISSION_NOTE):
        return ""
    if header and not fits(header + "\n\n" + OMISSION_NOTE):
        return OMISSION_NOTE
    selected: list[str] = []
    for chunk in chunks:
        if len(selected) >= max_chunks:
            break
        candidate = "\n\n".join(part for part in [header, *selected, chunk, OMISSION_NOTE] if part)
        if fits(candidate):
            selected.append(chunk)
    return "\n\n".join(part for part in [header, *selected, OMISSION_NOTE] if part)
