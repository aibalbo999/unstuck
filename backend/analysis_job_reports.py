"""Report rendering and persistence for analysis jobs."""

from __future__ import annotations

import json
import os
import time

from config import OUTPUT_DIR as DEFAULT_OUTPUT_DIR
from data_trust import data_snapshot_filename_for_report
from report_index import upsert_report_metadata
from reporting import ReportRequest


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
) -> dict:
    append_event_func(job_id, {
        "type": "status",
        "message": f"生成 {pipeline_def['short_label']} HTML / Markdown 報告...",
        "pipeline_id": current_pipeline_id,
        "pipeline_label": pipeline_def["label"],
    })
    cancel_check()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_ticker = ticker_upper.replace(".", "_")
    filename = f"{safe_ticker}_{current_pipeline_id}_report_{timestamp}.html"
    md_filename = f"{safe_ticker}_{current_pipeline_id}_report_{timestamp}.md"
    data_filename = data_snapshot_filename_for_report(filename)
    report_bundle = await renderer.render_async(
        ReportRequest(
            context=context,
            pipeline_id=current_pipeline_id,
            filename=filename,
        )
    )

    with open(os.path.join(output_dir, filename), "w", encoding="utf-8") as f:
        f.write(report_bundle.html)
    with open(os.path.join(output_dir, md_filename), "w", encoding="utf-8") as f:
        f.write(report_bundle.markdown)
    data_snapshot = report_bundle.data_snapshot
    with open(os.path.join(output_dir, data_filename), "w", encoding="utf-8") as f:
        json.dump(data_snapshot, f, ensure_ascii=False, indent=2)
    upsert_report_metadata(
        filename,
        output_dir=output_dir,
        html_content=report_bundle.html,
        markdown_content=report_bundle.markdown,
        data_trust=data_snapshot.get("data_trust"),
    )

    return {
        "type": "report_done",
        "filename": filename,
        "md_filename": md_filename,
        "data_filename": data_filename,
        "data_trust": data_snapshot.get("data_trust"),
        "audit": audit_notice,
        "pipeline_id": current_pipeline_id,
        "pipeline_label": pipeline_def["label"],
        "pipeline_index": sequence_index,
        "pipeline_total": sequence_total,
    }
