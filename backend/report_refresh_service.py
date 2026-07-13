"""Report data snapshot refresh services."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from company_display import company_display_name
from config import SOURCE_FRESHNESS_MAX_AGE_SECONDS
from data_fetch import FetchRequest
from data_trust import build_data_snapshot, data_snapshot_filename_for_report, normalize_data_trust, sanitize_for_snapshot, utc_now_iso
from decision_tracking import build_decision_freshness
from report_artifacts import MissingReportArtifact, ReportArtifactLocator
from report_history_storage import storage_for_existing_output_dir
from report_index import is_safe_report_filename, upsert_report_metadata
from report_persistence import DATA_SNAPSHOT_CONTENT_TYPE
from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text
from storage.report_storage import ReportStorage


ANALYSIS_TEXT_STALE_MESSAGE = "資料快照已刷新，但 HTML/Markdown 分析本文未重新執行；投資結論仍以原報告生成時間為準。"
DECISION_RELEVANT_DATA_KEYS = (
    "current_price",
    "market_cap_raw",
    "pe_ratio_raw",
    "pb_ratio",
    "ps_ratio",
    "ev_ebitda",
    "revenue_ttm_raw",
    "net_income_ttm_raw",
    "free_cash_flow_raw",
    "total_debt_raw",
    "total_cash_raw",
    "years",
    "revenue_history",
    "net_income_history",
    "gross_profit_history",
    "operating_income_history",
    "fcf_history",
    "gross_margin_history",
    "op_margin_history",
    "net_margin_history",
    "roe_history",
    "recent_monthly_revenue",
    "institutional_trading",
    "pe_river_chart",
)
HIGH_FREQUENCY_REFRESH_SOURCES = ("market_data", "recent_catalysts")


def _stale_sources(previous_snapshot: dict, *, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    previous_snapshot_map = safe_mapping_dict(previous_snapshot) or {}
    entries = safe_sequence_items(dict.get(previous_snapshot_map, "source_audit", []))
    if not entries:
        return list(HIGH_FREQUENCY_REFRESH_SOURCES)

    stale: set[str] = set()
    latest_success: dict[str, datetime] = {}
    seen_sources: set[str] = set()
    for raw_entry in entries:
        entry = safe_mapping_dict(raw_entry)
        if entry is None:
            continue
        source = str(dict.get(entry, "source") or "").strip()
        if not source:
            continue
        seen_sources.add(source)
        if str(dict.get(entry, "status") or "").strip().lower() != "success":
            stale.add(source)
            continue
        timestamp = _source_audit_timestamp(entry)
        if timestamp is None:
            stale.add(source)
            continue
        if source not in latest_success or timestamp > latest_success[source]:
            latest_success[source] = timestamp

    seen_sources.update(HIGH_FREQUENCY_REFRESH_SOURCES)
    for source in seen_sources:
        timestamp = latest_success.get(source)
        if timestamp is None:
            stale.add(source)
            continue
        max_age = int(SOURCE_FRESHNESS_MAX_AGE_SECONDS.get(source, 24 * 60 * 60))
        if (now - timestamp).total_seconds() > max_age:
            stale.add(source)
    return sorted(stale)


def _source_audit_timestamp(entry: dict) -> datetime | None:
    entry_map = safe_mapping_dict(entry) or {}
    for key in ("created_at", "fetched_at", "timestamp"):
        value = dict.get(entry_map, key)
        if value is None:
            continue
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    text = safe_text(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _source_status_map(snapshot: dict) -> dict:
    status_map = {}
    snapshot_map = safe_mapping_dict(snapshot) or {}
    entries = safe_sequence_items(dict.get(snapshot_map, "source_audit", []))
    for raw_entry in entries:
        entry = safe_mapping_dict(raw_entry)
        if entry is None:
            continue
        source = str(dict.get(entry, "source") or "unknown")
        provider = str(dict.get(entry, "provider") or "unknown")
        status_map[(source, provider)] = {
            "source": source,
            "provider": provider,
            "status": str(dict.get(entry, "status") or "unknown"),
            "message": str(dict.get(entry, "message") or dict.get(entry, "error_kind") or "")[:160],
        }
    return status_map


def refresh_data_diff(previous_snapshot: dict, refreshed_snapshot: dict) -> dict:
    previous_snapshot_map = safe_mapping_dict(previous_snapshot) or {}
    refreshed_snapshot_map = safe_mapping_dict(refreshed_snapshot) or {}
    before_trust = normalize_data_trust(dict.get(previous_snapshot_map, "data_trust"))
    after_trust = normalize_data_trust(dict.get(refreshed_snapshot_map, "data_trust"))
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


def refresh_requires_analysis_rerun(previous_snapshot: dict, refreshed_snapshot: dict, refresh_diff: dict) -> bool:
    previous_snapshot_map = safe_mapping_dict(previous_snapshot) or {}
    refreshed_snapshot_map = safe_mapping_dict(refreshed_snapshot) or {}
    refresh_diff_map = safe_mapping_dict(refresh_diff) or {}
    if (
        dict.get(previous_snapshot_map, "refreshed_without_analysis_rerun")
        or dict.get(previous_snapshot_map, "decision_validity_status") == "needs_rerun"
    ):
        return True
    before_data = safe_mapping_dict(dict.get(previous_snapshot_map, "data")) or {}
    after_data = safe_mapping_dict(dict.get(refreshed_snapshot_map, "data")) or {}
    for key in DECISION_RELEVANT_DATA_KEYS:
        if _stable_data_value(before_data, key) != _stable_data_value(after_data, key):
            return True

    stale_sources_diff = safe_mapping_dict(dict.get(refresh_diff_map, "stale_sources")) or {}
    if dict.get(stale_sources_diff, "removed") or dict.get(stale_sources_diff, "added"):
        return True
    critical_failures_diff = safe_mapping_dict(dict.get(refresh_diff_map, "critical_failures")) or {}
    if dict.get(critical_failures_diff, "removed") or dict.get(critical_failures_diff, "added"):
        return True

    before_trust = normalize_data_trust(dict.get(previous_snapshot_map, "data_trust"))
    after_trust = normalize_data_trust(dict.get(refreshed_snapshot_map, "data_trust"))
    if _actionable_reason_codes(before_trust) != _actionable_reason_codes(after_trust):
        return True
    if before_trust.get("status") != after_trust.get("status"):
        return not _provider_sla_only_partial(after_trust)
    return False


def _stable_data_value(data: dict, key: str) -> str:
    if key not in data:
        return "__missing__"
    return json.dumps(data.get(key), ensure_ascii=False, sort_keys=True, default=str)


def _actionable_reason_codes(trust: dict) -> set[str]:
    return {
        code for code in (trust.get("reason_codes") or [])
        if str(code).startswith(("source_error:", "source_stale:"))
        or code in {"critical_sources_error", "missing_usable_critical_data"}
    }


def _provider_sla_only_partial(trust: dict) -> bool:
    codes = set(trust.get("reason_codes") or [])
    return (
        trust.get("status") == "partial"
        and "provider_sla_critical" in codes
        and not trust.get("critical_failures")
        and not trust.get("stale_sources")
        and not _actionable_reason_codes(trust)
    )


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
