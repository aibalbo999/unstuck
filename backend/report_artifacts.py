"""Locate and read report artifact bundles through one interface."""

from __future__ import annotations

import json
from dataclasses import dataclass

from report_paths import report_storage_candidates_for_filename
from storage.report_storage import ReportStorage, StoredReportContent


class MissingReportArtifact(FileNotFoundError):
    def __init__(self, filename: str, kind: str):
        self.filename = filename
        self.kind = kind
        super().__init__(f"Missing {kind} artifact for {filename}")


@dataclass(frozen=True)
class ReportArtifactBundle:
    filename: str
    storage: ReportStorage
    html_key: str
    markdown_key: str | None
    data_key: str

    def read_data_item(self) -> StoredReportContent:
        item = self.storage.get_report(self.data_key)
        if item is None:
            raise MissingReportArtifact(self.filename, "data")
        return item

    def read_data_snapshot(self) -> dict:
        item = self.read_data_item()
        payload = json.loads(item.content.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("report data snapshot must be a JSON object")
        return payload


class ReportArtifactLocator:
    def __init__(self, storage: ReportStorage):
        self.storage = storage

    def existing_key(self, filename: str, *, kind: str) -> str | None:
        for key in report_storage_candidates_for_filename(filename, kind=kind):
            if self.storage.exists(key):
                return key
        return None

    def require_key(self, filename: str, *, kind: str) -> str:
        key = self.existing_key(filename, kind=kind)
        if key is None:
            raise MissingReportArtifact(filename, kind)
        return key

    def require_bundle(
        self,
        filename: str,
        *,
        require_markdown: bool = True,
        require_data: bool = True,
    ) -> ReportArtifactBundle:
        html_key = self.require_key(filename, kind="html")
        markdown_key = self.existing_key(filename, kind="md")
        if require_markdown and markdown_key is None:
            raise MissingReportArtifact(filename, "md")
        data_key = self.require_key(filename, kind="data") if require_data else (
            self.existing_key(filename, kind="data") or ""
        )
        return ReportArtifactBundle(
            filename=filename,
            storage=self.storage,
            html_key=html_key,
            markdown_key=markdown_key,
            data_key=data_key,
        )


__all__ = ["MissingReportArtifact", "ReportArtifactBundle", "ReportArtifactLocator"]
