"""Lightweight in-memory RAG service for long filings, transcripts, and news."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Optional

from google.genai import types

from agent_catalog import AGENT_NAMES
from config import (
    EMBEDDING_MODEL,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_ENABLED,
    RAG_MAX_CHUNKS_PER_AGENT,
    RAG_MAX_CONTEXT_CHARS,
    RAG_MAX_INDEX_CHUNKS,
    RAG_MIN_SOURCE_CHARS,
)
from llm_client import (
    KeyRotator,
    describe_quota_or_rate_error,
    embed_content,
    embed_content_async,
    estimate_text_tokens,
    is_missing_model_error,
    is_quota_or_rate_error,
    retry_delay_seconds,
)


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

AGENT_RAG_QUERIES = {
    1: "business model revenue segments supply chain customers product mix management strategy concentration pricing power disruption 供應鏈 客戶集中 價格壓力 替代風險",
    2: "five year financial statements revenue margin free cash flow balance sheet debt profitability cash conversion working capital capex impairment restatement 財務 報表 現金流 轉換率 營運資金 減損",
    3: "competitive moat peers switching costs technology patents cost advantage market share commoditization substitution entry barrier customer churn 護城河 競爭 替代 商品化 弱項",
    4: "valuation DCF WACC FCF PE multiple target price capex margin assumptions sensitivity terminal value estimate revision downside 估值 折現 同業 倍數 下修 敏感度",
    5: "growth drivers TAM demand catalysts capacity AI technology long term opportunity risks bottleneck adoption cycle competition margin dilution 成長 產能 瓶頸 技術 擴張 逆風",
    6: "bull bear debate catalysts risks valuation controversy downside upside counterarguments downgrade miss warning headwind estimate cut guidance cut demand slowdown margin compression customer concentration inventory correction 衰退 下修 警告 逆風 降評 未達預期 砍單 庫存去化 毛利率壓力 競爭",
    7: "final investment decision recommendation target price confidence risks catalysts valuation institutional flow downgrade miss warning downside upside risk event 籌碼 外資 投信 下修 降評 催化 風險",
    11: "macro economy interest rates inflation geopolitics policy tariff subsidy industry cycle inventory destocking capex expansion demand supply headwind tailwind 總經 利率 通膨 地緣政治 政策 產業週期 去庫存 順風 逆風",
    12: "business model economic moat revenue mechanism switching costs scale economy brand patents peers margin market share competitive erosion 商業模式 賺錢機制 護城河 轉換成本 規模經濟 毛利率 競爭侵蝕",
    13: "forensic accounting red flags free cash flow conversion inventory receivables margin deterioration debt leverage DuPont ROE liquidity capex 財務排雷 紅旗 自由現金流 存貨 應收帳款 毛利率惡化 槓桿 杜邦",
    14: "growth valuation DCF TAM SAM catalysts revenue growth FCF growth WACC forward PE PB estimate revision double counting 估值 成長 本益比 目標價 法說 催化 雙重樂觀 下修",
    15: "institutional trading foreign investors investment trust dealer net buy sell technical sentiment PE river chart crowded trade breakout momentum 法人 外資 投信 自營商 買賣超 籌碼 技術面 情緒 河流圖 動能",
    16: "portfolio manager trading decision bull bear actionable plan risk control entry exit timing valuation chip flow macro red flags left side trade 實戰交易 進出場 風控 多空 籌碼 估值 總經 紅旗 左側交易",
}


@dataclass
class RagChunk:
    chunk_id: str
    source: str
    text: str
    metadata: dict[str, Any]
    embedding: Optional[list[float]] = None


@dataclass
class RagSearchResult:
    chunk: RagChunk
    score: float


class InMemoryRagIndex:
    """Small local vector store; cosine search when embeddings exist, lexical otherwise."""

    def __init__(self, chunks: list[RagChunk]):
        self.chunks = chunks

    @property
    def has_embeddings(self) -> bool:
        return any(chunk.embedding for chunk in self.chunks)

    def search(
        self,
        query: str,
        query_embedding: Optional[list[float]] = None,
        top_k: int = RAG_MAX_CHUNKS_PER_AGENT,
        max_chars: int = RAG_MAX_CONTEXT_CHARS,
    ) -> list[RagSearchResult]:
        if not self.chunks:
            return []

        scored = []
        for chunk in self.chunks:
            if query_embedding and chunk.embedding:
                score = _cosine_similarity(query_embedding, chunk.embedding)
            else:
                score = _lexical_score(query, chunk.text, chunk.source)
            scored.append(RagSearchResult(chunk=chunk, score=score))

        scored.sort(key=lambda item: item.score, reverse=True)
        selected: list[RagSearchResult] = []
        used_chars = 0
        for item in scored:
            if len(selected) >= max(1, top_k):
                break
            if item.score <= 0 and selected:
                break
            remaining = max_chars - used_chars
            if remaining <= 200:
                break
            clipped_text = _clip_text(item.chunk.text, remaining)
            selected.append(RagSearchResult(
                chunk=RagChunk(
                    chunk_id=item.chunk.chunk_id,
                    source=item.chunk.source,
                    text=clipped_text,
                    metadata=item.chunk.metadata,
                    embedding=item.chunk.embedding,
                ),
                score=item.score,
            ))
            used_chars += len(clipped_text) + 120
        return selected


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


def _extract_embeddings(response) -> list[list[float]]:
    embeddings = getattr(response, "embeddings", None) or []
    vectors = []
    for embedding in embeddings:
        values = getattr(embedding, "values", None) or []
        vectors.append([float(value) for value in values])
    return vectors


def _embedding_config(task_type: str, title: str | None = None):
    kwargs = {"task_type": task_type}
    if title:
        kwargs["title"] = title
    return types.EmbedContentConfig(**kwargs)


def _attach_vectors(chunks: list[RagChunk], vectors: list[list[float]]) -> int:
    attached = 0
    for chunk, vector in zip(chunks, vectors):
        if vector:
            chunk.embedding = vector
            attached += 1
    return attached


def build_rag_index(data: dict[str, Any], rotator: Optional[KeyRotator] = None) -> Optional[InMemoryRagIndex]:
    """Build an in-memory RAG index; if embedding fails, keep lexical chunks."""
    if not RAG_ENABLED:
        return None
    chunks = build_chunks(data)
    if not chunks:
        return None

    index = InMemoryRagIndex(chunks)
    if not isinstance(rotator, KeyRotator):
        return index

    api_key = None
    try:
        texts = [chunk.text for chunk in chunks]
        estimated_tokens = estimate_text_tokens("\n\n".join(texts))
        api_key = rotator.get_key(EMBEDDING_MODEL, estimated_tokens)
        response = embed_content(
            api_key,
            EMBEDDING_MODEL,
            texts,
            _embedding_config("RETRIEVAL_DOCUMENT", title=str(data.get("company_name") or data.get("ticker") or "stock")),
        )
        _attach_vectors(chunks, _extract_embeddings(response))
    except Exception as exc:
        if is_quota_or_rate_error(str(exc)):
            if api_key:
                rotator.penalize(api_key, EMBEDDING_MODEL, retry_delay_seconds(exc, default=60))
            print(f"  ⏭️  RAG embedding 遇到配額限制，改用本地詞彙檢索：{describe_quota_or_rate_error(exc)[:120]}")
        elif is_missing_model_error(str(exc)):
            print(f"  ⚠️  RAG embedding 模型不可用，改用本地詞彙檢索：{str(exc)[:120]}")
        else:
            print(f"  ⚠️  RAG embedding 建索引失敗，改用本地詞彙檢索：{str(exc)[:120]}")
    return index


async def build_rag_index_async(data: dict[str, Any], rotator: Optional[KeyRotator] = None) -> Optional[InMemoryRagIndex]:
    """Async RAG index builder for the analysis pipeline."""
    if not RAG_ENABLED:
        return None
    chunks = build_chunks(data)
    if not chunks:
        return None

    index = InMemoryRagIndex(chunks)
    if not isinstance(rotator, KeyRotator):
        return index

    api_key = None
    try:
        texts = [chunk.text for chunk in chunks]
        estimated_tokens = estimate_text_tokens("\n\n".join(texts))
        api_key = await rotator.async_get_key(EMBEDDING_MODEL, estimated_tokens)
        response = await embed_content_async(
            api_key,
            EMBEDDING_MODEL,
            texts,
            _embedding_config("RETRIEVAL_DOCUMENT", title=str(data.get("company_name") or data.get("ticker") or "stock")),
        )
        _attach_vectors(chunks, _extract_embeddings(response))
    except Exception as exc:
        if is_quota_or_rate_error(str(exc)):
            if api_key:
                rotator.penalize(api_key, EMBEDDING_MODEL, retry_delay_seconds(exc, default=60))
            print(f"  ⏭️  RAG embedding 遇到配額限制，改用本地詞彙檢索：{describe_quota_or_rate_error(exc)[:120]}")
        elif is_missing_model_error(str(exc)):
            print(f"  ⚠️  RAG embedding 模型不可用，改用本地詞彙檢索：{str(exc)[:120]}")
        else:
            print(f"  ⚠️  RAG embedding 建索引失敗，改用本地詞彙檢索：{str(exc)[:120]}")
    return index


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _tokenize_for_lexical(text: str) -> list[str]:
    lowered = str(text or "").lower()
    latin = re.findall(r"[a-z0-9][a-z0-9_./+-]{1,}", lowered)
    cjk_terms = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    return latin + cjk_terms


def _lexical_score(query: str, text: str, source: str = "") -> float:
    query_terms = set(_tokenize_for_lexical(query))
    if not query_terms:
        return 0.0
    haystack = f"{source}\n{text}".lower()
    return float(sum(1 for term in query_terms if term in haystack))


def _agent_query(agent_num: int, data: dict[str, Any]) -> str:
    return " ".join([
        str(data.get("ticker") or ""),
        str(data.get("company_name") or ""),
        str(data.get("industry") or ""),
        AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
        AGENT_RAG_QUERIES.get(agent_num, ""),
    ]).strip()


def _format_results(results: list[RagSearchResult], agent_num: int) -> str:
    if not results:
        return ""
    parts = [
        f"【RAG 語意檢索精選資料｜Agent {agent_num}】",
        "以下片段來自長篇法說會、財報、新聞或外部長文本；只可作為引用依據，不可假設已讀全文。",
    ]
    for idx, result in enumerate(results, 1):
        score = f"{result.score:.3f}" if isinstance(result.score, float) else str(result.score)
        parts.append(
            f"【片段 {idx}｜來源：{result.chunk.source}｜相關度：{score}】\n"
            f"{result.chunk.text}"
        )
    return "\n\n".join(parts)


def _embed_query(query: str, rotator: Optional[KeyRotator]) -> Optional[list[float]]:
    if not isinstance(rotator, KeyRotator):
        return None
    api_key = None
    try:
        api_key = rotator.get_key(EMBEDDING_MODEL, estimate_text_tokens(query))
        response = embed_content(
            api_key,
            EMBEDDING_MODEL,
            query,
            _embedding_config("RETRIEVAL_QUERY"),
        )
        vectors = _extract_embeddings(response)
        return vectors[0] if vectors else None
    except Exception as exc:
        if is_quota_or_rate_error(str(exc)) and api_key:
            rotator.penalize(api_key, EMBEDDING_MODEL, retry_delay_seconds(exc, default=60))
        if not is_quota_or_rate_error(str(exc)) and not is_missing_model_error(str(exc)):
            print(f"  ⚠️  RAG query embedding 失敗，改用本地詞彙檢索：{str(exc)[:120]}")
        return None


async def _embed_query_async(query: str, rotator: Optional[KeyRotator]) -> Optional[list[float]]:
    if not isinstance(rotator, KeyRotator):
        return None
    api_key = None
    try:
        api_key = await rotator.async_get_key(EMBEDDING_MODEL, estimate_text_tokens(query))
        response = await embed_content_async(
            api_key,
            EMBEDDING_MODEL,
            query,
            _embedding_config("RETRIEVAL_QUERY"),
        )
        vectors = _extract_embeddings(response)
        return vectors[0] if vectors else None
    except Exception as exc:
        if is_quota_or_rate_error(str(exc)) and api_key:
            rotator.penalize(api_key, EMBEDDING_MODEL, retry_delay_seconds(exc, default=60))
        if not is_quota_or_rate_error(str(exc)) and not is_missing_model_error(str(exc)):
            print(f"  ⚠️  RAG query embedding 失敗，改用本地詞彙檢索：{str(exc)[:120]}")
        return None


def ensure_agent_rag_context(agent_num: int, context: dict, rotator: Optional[KeyRotator] = None) -> str:
    if not RAG_ENABLED:
        return ""
    rag_context = context.setdefault("rag_context", {})
    if agent_num in rag_context:
        return rag_context[agent_num]

    index = context.get("rag_index")
    if index is None:
        index = build_rag_index(context.get("data", {}) or {}, rotator)
        if index is not None:
            context["rag_index"] = index
    if not isinstance(index, InMemoryRagIndex) or not index.chunks:
        return ""

    query = _agent_query(agent_num, context.get("data", {}) or {})
    query_embedding = _embed_query(query, rotator) if index.has_embeddings else None
    results = index.search(query, query_embedding=query_embedding)
    formatted = _format_results(results, agent_num)
    if formatted:
        rag_context[agent_num] = formatted
    return formatted


async def ensure_agent_rag_context_async(agent_num: int, context: dict, rotator: Optional[KeyRotator] = None) -> str:
    if not RAG_ENABLED:
        return ""
    rag_context = context.setdefault("rag_context", {})
    if agent_num in rag_context:
        return rag_context[agent_num]

    index = context.get("rag_index")
    if index is None:
        index = await build_rag_index_async(context.get("data", {}) or {}, rotator)
        if index is not None:
            context["rag_index"] = index
    if not isinstance(index, InMemoryRagIndex) or not index.chunks:
        return ""

    query = _agent_query(agent_num, context.get("data", {}) or {})
    query_embedding = await _embed_query_async(query, rotator) if index.has_embeddings else None
    results = index.search(query, query_embedding=query_embedding)
    formatted = _format_results(results, agent_num)
    if formatted:
        rag_context[agent_num] = formatted
    return formatted
