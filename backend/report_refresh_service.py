"""Report data snapshot refresh services."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import HTTPException

from data_fetch import FetchRequest
from data_trust import build_data_snapshot, data_snapshot_filename_for_report, normalize_data_trust, utc_now_iso
from decision_tracking import build_decision_freshness
from report_index import is_safe_report_filename, upsert_report_metadata


ANALYSIS_TEXT_STALE_MESSAGE = "資料快照已刷新，但 HTML/Markdown 分析本文未重新執行；投資結論仍以原報告生成時間為準。"


def _source_status_map(snapshot: dict) -> dict:
    status_map = {}
    entries = snapshot.get("source_audit", []) if isinstance(snapshot, dict) else []
    if not isinstance(entries, list):
        return status_map
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "unknown")
        provider = str(entry.get("provider") or "unknown")
        status_map[(source, provider)] = {
            "source": source,
            "provider": provider,
            "status": str(entry.get("status") or "unknown"),
            "message": str(entry.get("message") or entry.get("error_kind") or "")[:160],
        }
    return status_map


def refresh_data_diff(previous_snapshot: dict, refreshed_snapshot: dict) -> dict:
    before_trust = normalize_data_trust(previous_snapshot.get("data_trust") if isinstance(previous_snapshot, dict) else None)
    after_trust = normalize_data_trust(refreshed_snapshot.get("data_trust") if isinstance(refreshed_snapshot, dict) else None)
    before_stale = set(before_trust.get("stale_sources", []) or [])
    after_stale = set(after_trust.get("stale_sources", []) or [])
    before_failures = set(before_trust.get("critical_failures", []) or [])
    after_failures = set(after_trust.get("critical_failures", []) or [])
    before_status = _source_status_map(previous_snapshot)
    after_status = _source_status_map(refreshed_snapshot)
    source_status_changes = []
    for key in sorted(set(before_status) | set(after_status)):
        before = before_status.get(key, {"source": key[0], "provider": key[1], "status": "missing", "message": ""})
        after = after_status.get(key, {"source": key[0], "provider": key[1], "status": "missing", "message": ""})
        if before["status"] != after["status"]:
            source_status_changes.append({
                "source": key[0],
                "provider": key[1],
                "before": before["status"],
                "after": after["status"],
                "message": after.get("message") or before.get("message") or "",
            })

    summary = []
    if before_trust.get("status") != after_trust.get("status"):
        summary.append(f"可信度 {before_trust.get('status')} → {after_trust.get('status')}")
    removed_stale = sorted(before_stale - after_stale)
    added_stale = sorted(after_stale - before_stale)
    removed_failures = sorted(before_failures - after_failures)
    added_failures = sorted(after_failures - before_failures)
    if removed_stale:
        summary.append("解除過期：" + "、".join(removed_stale[:4]))
    if added_stale:
        summary.append("新增過期：" + "、".join(added_stale[:4]))
    if removed_failures:
        summary.append("解除核心異常：" + "、".join(removed_failures[:4]))
    if added_failures:
        summary.append("新增核心異常：" + "、".join(added_failures[:4]))
    if not summary:
        summary.append("資料可信度狀態未變更")

    return {
        "data_trust_status": {
            "before": before_trust.get("status"),
            "after": after_trust.get("status"),
            "changed": before_trust.get("status") != after_trust.get("status"),
        },
        "stale_sources": {"removed": removed_stale, "added": added_stale},
        "critical_failures": {"removed": removed_failures, "added": added_failures},
        "source_status_changes": source_status_changes[:20],
        "summary": summary,
    }


async def refresh_report_data_snapshot(
    filename: str,
    *,
    output_dir: str,
    refresh_service: Any,
) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    html_path = os.path.join(output_dir, filename)
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="找不到報告")

    data_filename = data_snapshot_filename_for_report(filename)
    data_path = os.path.join(output_dir, data_filename)
    if not os.path.exists(data_path):
        raise HTTPException(status_code=404, detail="舊報告沒有資料快照，無法只刷新資料")

    try:
        with open(data_path, "r", encoding="utf-8") as f:
            previous_snapshot = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"資料快照無法讀取：{exc}") from exc

    ticker = str(previous_snapshot.get("ticker") or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="資料快照缺少 ticker")

    result = await refresh_service.fetch_async(
        FetchRequest.from_ticker(ticker, force_refresh=True, record_provider_sla=False)
    )
    refreshed_data = result.data or {}
    if not isinstance(refreshed_data, dict) or "error" in refreshed_data:
        message = refreshed_data.get("error") if isinstance(refreshed_data, dict) else "資料刷新失敗"
        raise HTTPException(status_code=502, detail=message)

    refresh_generated_at = utc_now_iso()
    context = {
        "ticker": refreshed_data.get("ticker") or ticker,
        "company_name": refreshed_data.get("company_name") or previous_snapshot.get("company_name") or ticker,
        "pipeline_id": previous_snapshot.get("pipeline"),
        "data": refreshed_data,
        "conclusion_generated_at": previous_snapshot.get("conclusion_generated_at") or previous_snapshot.get("generated_at"),
        "snapshot_refreshed_at": refresh_generated_at,
        "decision_validity_status": "needs_rerun",
        "requires_rerun_reason": ANALYSIS_TEXT_STALE_MESSAGE,
        "deterministic_fallbacks": previous_snapshot.get("deterministic_fallbacks", []),
        "report_lint": previous_snapshot.get("report_lint", {}),
        "refreshed_from_report": filename,
        "refreshed_without_analysis_rerun": True,
        "analysis_text_stale_message": ANALYSIS_TEXT_STALE_MESSAGE,
    }
    refreshed_snapshot = build_data_snapshot(
        context,
        pipeline_id=previous_snapshot.get("pipeline"),
        generated_at=refresh_generated_at,
    )
    refresh_diff = refresh_data_diff(previous_snapshot, refreshed_snapshot)

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(refreshed_snapshot, f, ensure_ascii=False, indent=2)
    decision_freshness = build_decision_freshness(data_path)
    metadata = upsert_report_metadata(
        filename,
        output_dir=output_dir,
        data_trust=refreshed_snapshot.get("data_trust"),
    )
    return {
        "success": True,
        "filename": filename,
        "data_filename": data_filename,
        "data_trust": refreshed_snapshot.get("data_trust"),
        "source_audit": refreshed_snapshot.get("source_audit", [])[:12],
        "refresh_diff": refresh_diff,
        "analysis_text_stale": True,
        "analysis_text_stale_message": ANALYSIS_TEXT_STALE_MESSAGE,
        "decision_freshness": decision_freshness,
        "metadata": metadata or {},
    }
