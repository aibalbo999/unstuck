"""Typed request/result contracts for stock data fetching."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class FetchOptions:
    skip_optional_http: bool = False
    force_refresh: bool = False
    include_provider_results: bool = True
    record_provider_sla: bool = True


@dataclass(frozen=True)
class FetchRequest:
    ticker: str
    options: FetchOptions = field(default_factory=FetchOptions)

    @classmethod
    def from_ticker(cls, ticker: str, **options) -> "FetchRequest":
        return cls(ticker=str(ticker or "").strip().upper(), options=FetchOptions(**options))


@dataclass
class ProviderResult:
    source: str
    provider: str
    status: str
    value: Any = None
    audit: dict = field(default_factory=dict)
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)
    as_of: str | None = None
    confidence: float | None = None
    raw_ref: str | None = None


@dataclass
class FetchResult:
    request: FetchRequest
    data: dict
    source_audit: list[dict] = field(default_factory=list)
    data_trust: dict = field(default_factory=dict)
    provider_results: list[ProviderResult] = field(default_factory=list)
    cache_hit: bool = False
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def payload(self) -> dict:
        return self.data


ProviderCallable = Callable[[FetchRequest], ProviderResult]
