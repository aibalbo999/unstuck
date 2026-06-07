"""RAG chunk construction."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_MAX_INDEX_CHUNKS

from .documents import _normalize_whitespace, collect_rag_documents
from .types import RagChunk


def _chunk_document(source: str, text: str) -> list[RagChunk]:
    cleaned = _normalize_whitespace(text)
    if not cleaned:
        return []

    chunk_size = max(RAG_CHUNK_SIZE, 400)
    overlap = min(max(RAG_CHUNK_OVERLAP, 0), chunk_size // 2)
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", cleaned) if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs or [cleaned]:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start:start + chunk_size].strip())
                start += max(chunk_size - overlap, 1)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            chunks.append(current.strip())
            prefix = current[-overlap:].strip() if overlap and current else ""
            current = f"{prefix}\n\n{paragraph}".strip() if prefix else paragraph

    if current:
        chunks.append(current.strip())

    result = []
    for idx, chunk in enumerate(chunks):
        chunk_id = hashlib.sha1(f"{source}:{idx}:{chunk}".encode("utf-8", "ignore")).hexdigest()[:16]
        result.append(RagChunk(
            chunk_id=chunk_id,
            source=source,
            text=chunk,
            metadata={"source": source, "chunk_index": idx},
        ))
    return result


def build_chunks(data: dict[str, Any]) -> list[RagChunk]:
    chunks: list[RagChunk] = []
    for document in collect_rag_documents(data):
        chunks.extend(_chunk_document(document["source"], document["text"]))
        if len(chunks) >= RAG_MAX_INDEX_CHUNKS:
            break
    return chunks[:RAG_MAX_INDEX_CHUNKS]
