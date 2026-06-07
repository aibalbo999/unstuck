"""Typed service boundary over the SQLite report metadata index."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from report_index import delete_report_metadata, query_report_metadata, sync_report_metadata, upsert_report_metadata


@dataclass(frozen=True)
class ReportListQuery:
    page: int
    limit: int
    q: str = ""
    pipeline: str = "all"
    recommendation: str = "all"
    data_trust: str = "all"
    output_dir: Optional[str] = None


class ReportRepository:
    """Small repository wrapper so services do not depend on raw index functions."""

    def sync(self, output_dir: Optional[str] = None) -> None:
        sync_report_metadata(output_dir)

    def upsert(
        self,
        filename: str,
        *,
        output_dir: Optional[str] = None,
        html_content: Optional[str] = None,
        markdown_content: Optional[str] = None,
        data_trust: Optional[dict] = None,
    ) -> Optional[dict]:
        return upsert_report_metadata(
            filename,
            output_dir=output_dir,
            html_content=html_content,
            markdown_content=markdown_content,
            data_trust=data_trust,
        )

    def delete(self, filename: str, output_dir: Optional[str] = None) -> None:
        delete_report_metadata(filename, output_dir)

    def query(self, query: ReportListQuery) -> tuple[list[dict], int]:
        return query_report_metadata(
            page=query.page,
            limit=query.limit,
            q=query.q,
            pipeline=query.pipeline,
            recommendation=query.recommendation,
            data_trust=query.data_trust,
            output_dir=query.output_dir,
        )


DEFAULT_REPORT_REPOSITORY = ReportRepository()
