"""Runtime helpers for yfinance core fetch orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CoreFetchRequest:
    ticker: str
    original_ticker: str
    cache_key: str
    fetch_started_epoch: float


@dataclass(frozen=True)
class ResolvedCoreStock:
    provider: object
    stock: object
    info: dict
    ticker: str


def build_core_fetch_request(ticker: str, *, now_epoch: Callable[[], float]) -> CoreFetchRequest:
    normalized_ticker = str(ticker or "").strip().upper()
    return CoreFetchRequest(
        ticker=normalized_ticker,
        original_ticker=normalized_ticker,
        cache_key=f"financial_data:{normalized_ticker}",
        fetch_started_epoch=now_epoch(),
    )


def read_fresh_cache_payload(
    request: CoreFetchRequest,
    *,
    force_refresh: bool,
    get_cached: Callable[[str], dict | None],
    build_fresh_cache_payload: Callable,
    assess_cached: Callable,
    append_cache_audit: Callable,
    now_epoch: Callable[[], float],
    emit: Callable[[str], None],
) -> dict | None:
    if force_refresh:
        emit(f"  ♻️  {request.original_ticker} 已要求強制刷新，略過既有財務資料快取...")
        return None

    cached = get_cached(request.cache_key)
    fresh_cached, stale_sources, schema_mismatch = build_fresh_cache_payload(
        request.original_ticker,
        cached,
        assess_cached=assess_cached,
        append_cache_audit=append_cache_audit,
        now_epoch=now_epoch(),
    )
    if fresh_cached:
        age_minutes = (fresh_cached.get("data_freshness", {}).get("age_seconds") or 0) / 60
        emit(f"  ✅ 使用快取的 {fresh_cached.get('ticker', request.original_ticker)} 財務數據（市場資料約 {age_minutes:.1f} 分鐘前更新）")
        return fresh_cached
    if stale_sources:
        stale_labels = ", ".join(stale_sources)
        emit(
            f"  ♻️  {request.original_ticker} 快取來源已過期（{stale_labels}），重新抓取核心分析資料..."
        )
    if schema_mismatch:
        emit(f"  ♻️  {request.original_ticker} 快取資料口徑已更新，重新抓取財務數據...")
    return None


def resolve_core_stock(
    ticker: str,
    *,
    market_data_provider,
    get_market_data_provider: Callable[[str], object],
    emit: Callable[[str], None],
) -> ResolvedCoreStock:
    provider = market_data_provider or get_market_data_provider(ticker)
    stock, info, is_valid, resolved_ticker, attempts = provider.resolve_stock(ticker)
    attempts = list(attempts or [])
    for index, attempt in enumerate(attempts[1:], start=1):
        previous = attempts[index - 1]
        if not previous.get("valid"):
            emit(f"    ⚠️ {previous.get('ticker')} 查無資料，嘗試 {attempt.get('ticker')}...")
    if is_valid:
        ticker = str(resolved_ticker or ticker).strip().upper()
    return ResolvedCoreStock(provider=provider, stock=stock, info=info or {}, ticker=ticker)


def read_current_price(stock, info: dict, *, safe_get: Callable) -> object:
    current_price = safe_get(info, "currentPrice", safe_get(info, "regularMarketPrice", "N/A"))
    if current_price == "N/A":
        current_price = safe_get(info, "previousClose", "N/A")

    if current_price != "N/A":
        return current_price

    try:
        hist_1d = stock.history(period="5d")
        if not hist_1d.empty:
            return round(float(hist_1d["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return current_price
