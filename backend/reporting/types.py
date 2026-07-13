"""Typed report-rendering contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from analysis_types import AnalysisContext
from mapping_fields import safe_mapping_dict


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
        snapshot = safe_mapping_dict(self.data_snapshot) or {}
        return safe_mapping_dict(dict.get(snapshot, "data_trust")) or {}
