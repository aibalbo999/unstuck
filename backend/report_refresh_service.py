"""Report data snapshot refresh services."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

from fastapi import HTTPException

from company_display import company_display_name
from data_fetch import FetchRequest
from data_trust import build_data_snapshot, data_snapshot_filename_for_report, sanitize_for_snapshot, utc_now_iso
from decision_tracking import build_decision_freshness
from report_refresh_freshness import _stale_sources
from report_refresh_diff import refresh_data_diff, refresh_requires_analysis_rerun
from report_artifacts import MissingReportArtifact, ReportArtifactLocator
from report_history_storage import storage_for_existing_output_dir
from report_index import is_safe_report_filename, upsert_report_metadata
from report_persistence import DATA_SNAPSHOT_CONTENT_TYPE
from mapping_fields import safe_mapping_dict
from storage.report_storage import ReportStorage


ANALYSIS_TEXT_STALE_MESSAGE = "資料快照已刷新，但 HTML/Markdown 分析本文未重新執行；投資結論仍以原報告生成時間為準。"


async def refresh_report_data_snapshot(
    filename: str,
    *,
    output_dir: str,
    refresh_service: Any,
    storage: ReportStorage | None = None,
    refreshed_data: dict | None = None,
    return_refreshed_data: bool = False,
) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    content_storage = storage_for_existing_output_dir(output_dir, storage)
    if content_storage is None:
        raise HTTPException(status_code=404, detail="找不到報告")
    data_filename = data_snapshot_filename_for_report(filename)
    try:
        bundle = ReportArtifactLocator(content_storage).require_bundle(filename, require_markdown=False)
    except MissingReportArtifact as exc:
        if exc.kind == "html":
            raise HTTPException(status_code=404, detail="找不到報告") from exc
        if exc.kind == "data":
            raise HTTPException(status_code=404, detail="舊報告沒有資料快照，無法只刷新資料") from exc
        raise HTTPException(status_code=404, detail=f"找不到報告檔案：{exc.kind}") from exc

    try:
        previous_snapshot = bundle.read_data_snapshot()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"資料快照無法讀取：{exc}") from exc

    ticker = str(previous_snapshot.get("ticker") or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="資料快照缺少 ticker")

    stale_sources = _stale_sources(previous_snapshot)
    if refreshed_data is None:
        result = await refresh_service.fetch_async(
            FetchRequest.from_ticker(ticker, force_refresh=True, record_provider_sla=False)
        )
        raw_refreshed_data = getattr(result, "data", None)
    else:
        raw_refreshed_data = refreshed_data
    refreshed_data_map = safe_mapping_dict(raw_refreshed_data) if raw_refreshed_data is not None else {}
    if refreshed_data_map is None:
        raise HTTPException(status_code=502, detail="資料刷新失敗")
    refreshed_data = sanitize_for_snapshot(refreshed_data_map)
    if not isinstance(refreshed_data, dict):
        raise HTTPException(status_code=502, detail="資料刷新失敗")
    if "error" in refreshed_data:
        message = dict.get(refreshed_data, "error") or "資料刷新失敗"
        raise HTTPException(status_code=502, detail=message)

    refresh_generated_at = utc_now_iso()
    context = {
        "ticker": refreshed_data.get("ticker") or ticker,
        "company_name": company_display_name(refreshed_data, previous_snapshot.get("company_name") or ticker),
        "pipeline_id": previous_snapshot.get("pipeline"),
        "data": refreshed_data,
        "conclusion_generated_at": previous_snapshot.get("conclusion_generated_at") or previous_snapshot.get("generated_at"),
        "snapshot_refreshed_at": refresh_generated_at,
        "deterministic_fallbacks": previous_snapshot.get("deterministic_fallbacks", []),
        "report_lint": previous_snapshot.get("report_lint", {}),
        "refreshed_from_report": filename,
        "refresh_stale_sources": stale_sources,
    }
    provisional_snapshot = build_data_snapshot(
        context,
        pipeline_id=previous_snapshot.get("pipeline"),
        generated_at=refresh_generated_at,
    )
    refresh_diff = refresh_data_diff(previous_snapshot, provisional_snapshot)
    analysis_text_stale = refresh_requires_analysis_rerun(previous_snapshot, provisional_snapshot, refresh_diff)
    context.update({
        "decision_validity_status": "needs_rerun" if analysis_text_stale else "current",
        "requires_rerun_reason": ANALYSIS_TEXT_STALE_MESSAGE if analysis_text_stale else "",
        "refreshed_without_analysis_rerun": analysis_text_stale,
        "analysis_text_stale_message": ANALYSIS_TEXT_STALE_MESSAGE if analysis_text_stale else "",
    })
    refreshed_snapshot = build_data_snapshot(
        context,
        pipeline_id=previous_snapshot.get("pipeline"),
        generated_at=refresh_generated_at,
    )

    content_storage.save_report(
        bundle.data_key,
        json.dumps(refreshed_snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
        content_type=DATA_SNAPSHOT_CONTENT_TYPE,
    )
    decision_freshness = build_decision_freshness(os.path.join(output_dir, bundle.data_key))
    metadata = upsert_report_metadata(
        filename,
        output_dir=output_dir,
        data_trust=refreshed_snapshot.get("data_trust"),
    )
    response = {
        "success": True,
        "filename": filename,
        "data_filename": data_filename,
        "data_trust": refreshed_snapshot.get("data_trust"),
        "source_audit": refreshed_snapshot.get("source_audit", [])[:12],
        "refresh_stale_sources": stale_sources,
        "refresh_diff": refresh_diff,
        "analysis_text_stale": analysis_text_stale,
        "analysis_text_stale_message": ANALYSIS_TEXT_STALE_MESSAGE if analysis_text_stale else "",
        "decision_freshness": decision_freshness,
        "metadata": metadata or {},
    }
    if return_refreshed_data:
        response["refreshed_data"] = deepcopy(refreshed_data)
    return response
