"""Typed service boundary over the SQLite report metadata index."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from report_index import (
    _connect,
    delete_report_metadata,
    query_report_metadata,
    sync_report_metadata,
    upsert_report_metadata,
)
from report_index_parsing import is_safe_report_filename, output_dir_key


@dataclass(frozen=True)
class ReportListQuery:
    page: int
    limit: int
    q: str = ""
    pipeline: str = "all"
    recommendation: str = "all"
    data_trust: str = "all"
    include_versions: bool = False
    output_dir: Optional[str] = None
    sync_metadata: bool = True


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

    def exists(self, filename: str, output_dir: Optional[str] = None) -> bool:
        if not is_safe_report_filename(filename, ".html"):
            return False
        with _connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM reports WHERE output_dir = ? AND filename = ? LIMIT 1",
                (output_dir_key(output_dir), filename),
            ).fetchone()
        return row is not None

    def query(self, query: ReportListQuery) -> tuple[list[dict], int]:
        return query_report_metadata(
            page=query.page,
            limit=query.limit,
            q=query.q,
            pipeline=query.pipeline,
            recommendation=query.recommendation,
            data_trust=query.data_trust,
            include_versions=query.include_versions,
            output_dir=query.output_dir,
            sync_metadata=query.sync_metadata,
        )


DEFAULT_REPORT_REPOSITORY = ReportRepository()
