"""Report data snapshot refresh services."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from company_display import company_display_name
from config import SOURCE_FRESHNESS_MAX_AGE_SECONDS
from data_fetch import FetchRequest
from data_trust import build_data_snapshot, data_snapshot_filename_for_report, normalize_data_trust, utc_now_iso
from decision_tracking import build_decision_freshness
from report_history_storage import existing_storage_key, storage_for_existing_output_dir
from report_index import is_safe_report_filename, upsert_report_metadata
from report_persistence import DATA_SNAPSHOT_CONTENT_TYPE
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
    entries = previous_snapshot.get("source_audit", []) if isinstance(previous_snapshot, dict) else []
    if not isinstance(entries, list):
        return list(HIGH_FREQUENCY_REFRESH_SOURCES)

    stale: set[str] = set()
    latest_success: dict[str, datetime] = {}
    seen_sources: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "").strip()
        if not source:
            continue
        seen_sources.add(source)
        if str(entry.get("status") or "").strip().lower() != "success":
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
    for key in ("created_at", "fetched_at", "timestamp"):
        value = entry.get(key)
        if not value:
            continue
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    text = str(value or "").strip()
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


def refresh_requires_analysis_rerun(previous_snapshot: dict, refreshed_snapshot: dict, refresh_diff: dict) -> bool:
    if previous_snapshot.get("refreshed_without_analysis_rerun") or previous_snapshot.get("decision_validity_status") == "needs_rerun":
        return True
    before_data = previous_snapshot.get("data") if isinstance(previous_snapshot.get("data"), dict) else {}
    after_data = refreshed_snapshot.get("data") if isinstance(refreshed_snapshot.get("data"), dict) else {}
    for key in DECISION_RELEVANT_DATA_KEYS:
        if _stable_data_value(before_data, key) != _stable_data_value(after_data, key):
            return True

    if refresh_diff.get("stale_sources", {}).get("removed") or refresh_diff.get("stale_sources", {}).get("added"):
        return True
    if refresh_diff.get("critical_failures", {}).get("removed") or refresh_diff.get("critical_failures", {}).get("added"):
        return True

    before_trust = normalize_data_trust(previous_snapshot.get("data_trust") if isinstance(previous_snapshot, dict) else None)
    after_trust = normalize_data_trust(refreshed_snapshot.get("data_trust") if isinstance(refreshed_snapshot, dict) else None)
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
) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    content_storage = storage_for_existing_output_dir(output_dir, storage)
    html_key = existing_storage_key(content_storage, filename, kind="html") if content_storage is not None else None
    if html_key is None:
        raise HTTPException(status_code=404, detail="找不到報告")

    data_filename = data_snapshot_filename_for_report(filename)
    data_key = existing_storage_key(content_storage, filename, kind="data") if content_storage is not None else None
    if data_key is None:
        raise HTTPException(status_code=404, detail="舊報告沒有資料快照，無法只刷新資料")

    try:
        item = content_storage.get_report(data_key) if content_storage is not None else None
        if item is None:
            raise FileNotFoundError(data_key)
        previous_snapshot = json.loads(item.content.decode("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"資料快照無法讀取：{exc}") from exc

    ticker = str(previous_snapshot.get("ticker") or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="資料快照缺少 ticker")

    stale_sources = _stale_sources(previous_snapshot)
    result = await refresh_service.fetch_async(
        FetchRequest.from_ticker(ticker, force_refresh=False, record_provider_sla=False)
    )
    refreshed_data = result.data or {}
    if not isinstance(refreshed_data, dict) or "error" in refreshed_data:
        message = refreshed_data.get("error") if isinstance(refreshed_data, dict) else "資料刷新失敗"
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
        data_key,
        json.dumps(refreshed_snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
        content_type=DATA_SNAPSHOT_CONTENT_TYPE,
    )
    decision_freshness = build_decision_freshness(os.path.join(output_dir, data_key))
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
        "refresh_stale_sources": stale_sources,
        "refresh_diff": refresh_diff,
        "analysis_text_stale": analysis_text_stale,
        "analysis_text_stale_message": ANALYSIS_TEXT_STALE_MESSAGE if analysis_text_stale else "",
        "decision_freshness": decision_freshness,
        "metadata": metadata or {},
    }
