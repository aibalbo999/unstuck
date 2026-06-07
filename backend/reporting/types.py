"""Typed report-rendering contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from analysis_types import AnalysisContext


@dataclass(frozen=True)
class ReportRequest:
    context: AnalysisContext
    pipeline_id: Optional[str] = None
    filename: str = ""
    generated_at: Optional[str] = None


@dataclass
class ReportBundle:
    html: str
    markdown: str
    data_snapshot: dict
    metadata: dict = field(default_factory=dict)

    @property
    def data_trust(self) -> dict:
        return self.data_snapshot.get("data_trust", {}) if isinstance(self.data_snapshot, dict) else {}
