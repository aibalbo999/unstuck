"""Report rendering and persistence for analysis jobs."""

from __future__ import annotations

import time

from config import OUTPUT_DIR as DEFAULT_OUTPUT_DIR
from report_persistence import persist_report_bundle
from reporting import ReportRequest
from storage.report_storage import LocalFileStorage, ReportStorage


async def render_and_persist_report(
    *,
    job_id: str,
    ticker_upper: str,
    current_pipeline_id: str,
    pipeline_def: dict,
    sequence_index: int,
    sequence_total: int,
    context: dict,
    audit_notice: dict,
    renderer,
    cancel_check,
    append_event_func,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    storage: ReportStorage | None = None,
) -> dict:
    append_event_func(job_id, {
        "type": "status",
        "message": f"生成 {pipeline_def['short_label']} HTML / Markdown 報告...",
        "pipeline_id": current_pipeline_id,
        "pipeline_label": pipeline_def["label"],
    })
    cancel_check()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_ticker = ticker_upper.replace(".", "_")
    filename = f"{safe_ticker}_{current_pipeline_id}_report_{timestamp}.html"
    report_bundle = await renderer.render_async(
        ReportRequest(
            context=context,
            pipeline_id=current_pipeline_id,
            filename=filename,
        )
    )
    data_snapshot = report_bundle.data_snapshot
    persisted = persist_report_bundle(
        filename=filename,
        html_content=report_bundle.html,
        markdown_content=report_bundle.markdown,
        data_snapshot=data_snapshot,
        storage=storage or LocalFileStorage(output_dir),
        output_dir=output_dir,
    )

    return {
        "type": "report_done",
        "filename": persisted["filename"],
        "md_filename": persisted["md_filename"],
        "data_filename": persisted["data_filename"],
        "data_trust": persisted["data_trust"],
        "audit": audit_notice,
        "pipeline_id": current_pipeline_id,
        "pipeline_label": pipeline_def["label"],
        "pipeline_index": sequence_index,
        "pipeline_total": sequence_total,
    }
