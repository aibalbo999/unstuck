"""Shared TypedDict contracts for the analysis pipeline."""

from __future__ import annotations

from typing import Any, TypedDict


class StockData(TypedDict, total=False):
    ticker: str
    company_name: str
    company_identity: dict[str, Any]
    current_price: float
    fetch_date: str
    years: list[Any]
    revenue_history: list[Any]
    net_income_history: list[Any]
    fcf_history: list[Any]
    gross_margin_history: list[Any]
    op_margin_history: list[Any]
    net_margin_history: list[Any]
    roe_history: list[Any]
    price_history: dict[str, Any]
    recent_catalysts: list[dict[str, Any]]
    institutional_trading: dict[str, Any]
    pe_river_chart: dict[str, Any]


class ParsedStructuredData(TypedDict, total=False):
    moat_scores: dict[str, float]
    price_targets: dict[str, float]
    recommendation: dict[str, str]


class AuditResult(TypedDict, total=False):
    status: str
    critical: list[str]
    warnings: list[str]
    corrections: list[str]
    repair_agent_issues: dict[int, list[str]]
    report_preserved: bool


class AnalysisContext(TypedDict, total=False):
    ticker: str
    company_name: str
    data: StockData
    analyses: dict[int, str]
    structured_outputs: dict[int, dict[str, Any]]
    parsed: ParsedStructuredData
    context_digests: dict[int, str]
    blocking_issues: list[str]
    audit_repair_log: list[str]
    final_audit: AuditResult
    tear_sheet_summary: str
    total_time: float
    start_time: float
    execution_mode: str
