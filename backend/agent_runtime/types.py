"""Typed contracts for agent and pipeline runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from analysis_types import AnalysisContext, StockData


@dataclass(frozen=True)
class AgentRunRequest:
    agent_num: int
    data: StockData
    context: AnalysisContext
    rotator: Any
    max_retries: int = 3


@dataclass
class AgentExecutionResult:
    agent_num: int
    text: str
    structured_output: Optional[dict] = None
    model_id: str = ""
    attempts: int = 1
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisRequest:
    data: StockData
    pipeline_id: str = "v1"
    progress_callback: Optional[Callable] = None
    cancel_check: Optional[Callable[[], None]] = None
    thread_id: Optional[str] = None
    checkpointer: Any | None = None
    checkpoint_path: Optional[str] = None
    report_filename: Optional[str] = None


@dataclass
class AnalysisResult:
    context: AnalysisContext
    pipeline_id: str
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)
