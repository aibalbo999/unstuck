"""Typed shared state for the multi-agent analysis blackboard."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    info = "info"
    warning = "warning"
    high = "high"
    critical = "critical"


class ProviderValue(BaseModel):
    provider: str
    field: str
    value: float | str | None
    unit: str = ""
    period: str | None = None
    statement_type: Literal["consolidated", "parent_only", "unknown"] = "unknown"
    fetched_at: datetime | None = None
    source_url: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)


class ValidationIssue(BaseModel):
    field: str
    severity: Severity
    providers: list[str]
    values: list[ProviderValue] = Field(default_factory=list)
    diff_pct: float = 0.0
    threshold_pct: float = 0.0
    likely_cause: str | None = None
    resolution: str | None = None


class RiskFlag(BaseModel):
    id: str
    severity: Severity
    category: Literal[
        "data_quality",
        "accounting",
        "liquidity",
        "valuation",
        "moat",
        "growth",
        "sentiment",
        "peer_selection",
    ]
    title: str
    evidence_refs: list[str] = Field(default_factory=list)
    source_agents: list[str] = Field(default_factory=list)
    impact: str
    confidence: float = Field(ge=0, le=1)


class AgentReport(BaseModel):
    agent_id: str
    role: str
    markdown: str
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    structured_output: dict[str, Any] | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)


class CircuitBreakerState(BaseModel):
    status: Literal["closed", "open", "half_open"] = "closed"
    blocking_fields: list[str] = Field(default_factory=list)
    attempts: int = 0
    reason: str | None = None


class AgentState(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    run_id: str
    ticker: str
    company_name: str
    company_identity: dict[str, Any] = Field(default_factory=dict)
    raw_financial_data: dict[str, Any] = Field(default_factory=dict)
    provider_values: dict[str, list[ProviderValue]] = Field(default_factory=dict)
    normalized_financials: dict[str, Any] = Field(default_factory=dict)
    source_audit: list[dict[str, Any]] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    circuit_breaker: CircuitBreakerState = Field(default_factory=CircuitBreakerState)
    peer_context: dict[str, Any] = Field(default_factory=dict)
    quant_metrics: dict[str, Any] = Field(default_factory=dict)
    tool_results: dict[str, Any] = Field(default_factory=dict)
    agent_reports: dict[str, AgentReport] = Field(default_factory=dict)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)
