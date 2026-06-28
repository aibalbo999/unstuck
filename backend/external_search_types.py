"""Shared external search result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    title: str
    snippet: str
    link: str
    source: str
    published_at: str = ""
    provider: str = ""
