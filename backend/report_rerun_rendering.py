"""Render and persist partial-rerun report bundles."""

from __future__ import annotations

import time
from typing import Any

from data_trust import data_snapshot_filename_for_report
from data_trust_snapshot import set_snapshot_integrity
from report_persistence import persist_report_bundle
from reporting import ReportRequest
from report_rerun_context import RERUN_SCOPE_LABELS
from storage.report_storage import LocalFileStorage, ReportStorage


def rerun_report_filename(ticker: str, pipeline_id: str) -> tuple[str, str, str]:
    safe_ticker = str(ticker or "report").strip().upper().replace(".", "_").replace("/", "_")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_ticker}_{pipeline_id}_report_{timestamp}.html"
    md_filename = f"{safe_ticker}_{pipeline_id}_report_{timestamp}.md"
    data_filename = data_snapshot_filename_for_report(filename)
    return filename, md_filename, data_filename


async def render_and_save_rerun_report(
    *,
    context: dict,
    pipeline_id: str,
    output_dir: str,
    report_renderer: Any,
    scope: str,
    source_filename: str,
    storage: ReportStorage | None = None,
) -> dict:
    filename, _, _ = rerun_report_filename(context.get("ticker"), pipeline_id)
    context["partial_rerun"] = {
        "scope": scope,
        "label": RERUN_SCOPE_LABELS[scope],
        "source_report": source_filename,
        "generated_report": filename,
    }
    report_bundle = await report_renderer.render_async(
        ReportRequest(
            context=context,
            pipeline_id=pipeline_id,
            filename=filename,
        )
    )
    data_snapshot = dict(report_bundle.data_snapshot)
    data_snapshot["partial_rerun"] = context["partial_rerun"]
    data_snapshot["rerun_from_report"] = source_filename
    data_snapshot["rerun_scope"] = scope
    set_snapshot_integrity(data_snapshot)

    persisted = persist_report_bundle(
        filename=filename,
        html_content=report_bundle.html,
        markdown_content=report_bundle.markdown,
        data_snapshot=data_snapshot,
        storage=storage or LocalFileStorage(output_dir),
        output_dir=output_dir,
    )
    return {
        "success": True,
        "scope": scope,
        "scope_label": RERUN_SCOPE_LABELS[scope],
        "source_filename": source_filename,
        "filename": persisted["filename"],
        "md_filename": persisted["md_filename"],
        "data_filename": persisted["data_filename"],
        "data_trust": persisted["data_trust"],
        "partial_rerun": context["partial_rerun"],
        "metadata": persisted["metadata"],
    }
