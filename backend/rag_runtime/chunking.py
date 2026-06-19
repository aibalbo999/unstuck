"""RAG chunk construction."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_MAX_INDEX_CHUNKS

from .documents import _normalize_whitespace, collect_rag_documents
from .types import RagChunk


MARKDOWN_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class MarkdownAwareChunker:
    """Chunk Markdown by heading sections before falling back to size windows."""

    def __init__(
        self,
        *,
        chunk_size: int | None = None,
        overlap: int | None = None,
        min_chunk_size: int = 400,
    ):
        configured_size = RAG_CHUNK_SIZE if chunk_size is None else int(chunk_size)
        self.chunk_size = max(configured_size, 80 if chunk_size is not None else min_chunk_size)
        configured_overlap = RAG_CHUNK_OVERLAP if overlap is None else int(overlap)
        self.overlap = min(max(configured_overlap, 0), self.chunk_size // 2)

    def chunk(self, source: str, text: str) -> list[RagChunk]:
        cleaned = _normalize_whitespace(text)
        if not cleaned:
            return []
        sections = self._markdown_sections(cleaned)
        raw_chunks: list[tuple[str, dict[str, Any]]] = []
        for section_text, metadata in sections:
            for section_index, part in enumerate(self._split_preserving_markdown_blocks(section_text)):
                chunk_metadata = dict(metadata)
                chunk_metadata["section_chunk_index"] = section_index
                raw_chunks.append((part, chunk_metadata))
        return self._to_chunks(source, raw_chunks)

    def _markdown_sections(self, text: str) -> list[tuple[str, dict[str, Any]]]:
        lines = text.splitlines()
        if not any(MARKDOWN_HEADER_RE.match(line.strip()) for line in lines):
            return [(part, {}) for part in self._split_preserving_markdown_blocks(text)]

        sections: list[tuple[str, dict[str, Any]]] = []
        header_stack: list[tuple[int, str, str]] = []
        current_lines: list[str] = []
        current_stack: list[tuple[int, str, str]] = []

        def flush() -> None:
            if not current_lines:
                return
            headers = [title for _level, title, _raw in current_stack]
            parent_headers = [raw for _level, _title, raw in current_stack[:-1]]
            body = "\n".join(current_lines).strip()
            section_text = "\n\n".join(part for part in ("\n".join(parent_headers).strip(), body) if part).strip()
            sections.append((
                section_text,
                {
                    "headers": headers,
                    "heading": headers[-1] if headers else "",
                    "header_level": current_stack[-1][0] if current_stack else None,
                },
            ))

        for line in lines:
            match = MARKDOWN_HEADER_RE.match(line.strip())
            if match:
                flush()
                level = len(match.group(1))
                title = match.group(2).strip()
                header_stack = [item for item in header_stack if item[0] < level]
                header_stack.append((level, title, line.strip()))
                current_stack = list(header_stack)
                current_lines = [line.strip()]
                continue
            if current_lines:
                current_lines.append(line)
            elif line.strip():
                current_stack = []
                current_lines = [line]
        flush()
        return sections

    def _split_preserving_markdown_blocks(self, text: str) -> list[str]:
        blocks = self._markdown_blocks(text)
        chunks: list[str] = []
        current = ""
        for block in blocks:
            candidate = f"{current}\n\n{block}".strip() if current else block
            if len(candidate) <= self.chunk_size:
                current = candidate
                continue
            if current:
                chunks.append(current.strip())
            if len(block) > self.chunk_size and not self._looks_like_table(block):
                chunks.extend(self._split_long_text(block))
                current = ""
            else:
                current = block
        if current:
            chunks.append(current.strip())
        return [chunk for chunk in chunks if chunk]

    def _markdown_blocks(self, text: str) -> list[str]:
        blocks: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            if not line.strip():
                if current:
                    blocks.append("\n".join(current).strip())
                    current = []
                continue
            current.append(line)
        if current:
            blocks.append("\n".join(current).strip())
        return blocks or [text.strip()]

    def _split_long_text(self, text: str) -> list[str]:
        chunks = []
        start = 0
        step = max(self.chunk_size - self.overlap, 1)
        while start < len(text):
            chunks.append(text[start:start + self.chunk_size].strip())
            start += step
        return chunks

    def _looks_like_table(self, block: str) -> bool:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        return len(lines) >= 2 and sum(1 for line in lines if line.startswith("|") and line.endswith("|")) >= 2

    def _to_chunks(self, source: str, chunks: list[tuple[str, dict[str, Any]]]) -> list[RagChunk]:
        result: list[RagChunk] = []
        for idx, (chunk, metadata) in enumerate(chunks):
            chunk_id = hashlib.sha1(f"{source}:{idx}:{chunk}".encode("utf-8", "ignore")).hexdigest()[:16]
            result.append(RagChunk(
                chunk_id=chunk_id,
                source=source,
                text=chunk,
                metadata={"source": source, "chunk_index": idx, **metadata},
            ))
        return result


def _chunk_document(source: str, text: str) -> list[RagChunk]:
    return MarkdownAwareChunker().chunk(source, text)


def _legacy_chunk_document(source: str, text: str) -> list[RagChunk]:
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
