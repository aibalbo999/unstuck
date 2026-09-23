"""Data preparation helpers for report rerun workflows."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from data_fetch import FetchRequest
from data_trust import sanitize_for_snapshot
from mapping_fields import safe_mapping_dict


def rerun_data_payload(raw_data: Any) -> dict:
    data_map = safe_mapping_dict(raw_data)
    if data_map is None:
        return {}
    data = sanitize_for_snapshot(data_map)
    return data if isinstance(data, dict) else {}


async def prepare_full_rerun_data(
    snapshot: Any,
    *,
    pipeline_id: str,
    refresh_service: Any = None,
    progress_callback: Any = None,
) -> dict:
    snapshot_map = safe_mapping_dict(snapshot) or {}
    data = rerun_data_payload(dict.get(snapshot_map, "data"))
    if not data:
        raise HTTPException(status_code=400, detail="資料快照缺少 data payload")
    if refresh_service is None:
        return data

    ticker = str(dict.get(snapshot_map, "ticker") or data.get("ticker") or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="資料快照缺少 ticker，無法完整重抓資料")
    if callable(progress_callback):
        progress_callback({
            "type": "status",
            "phase": "rerun_refresh_data",
            "message": "完整重跑前正在刷新資料快照...",
            "pipeline_id": pipeline_id,
        })

    fetch_result = await refresh_service.fetch_async(
        FetchRequest.from_ticker(ticker, force_refresh=True)
    )
    raw_refreshed_data = getattr(fetch_result, "data", None)
    refreshed_data_map = safe_mapping_dict(raw_refreshed_data) if raw_refreshed_data is not None else {}
    if refreshed_data_map is None:
        raise HTTPException(status_code=502, detail="完整重跑前資料刷新失敗：資料刷新失敗")
    refreshed_data = sanitize_for_snapshot(refreshed_data_map)
    if not isinstance(refreshed_data, dict) or "error" in refreshed_data:
        message = (
            dict.get(refreshed_data, "error")
            if isinstance(refreshed_data, dict)
            else "資料刷新失敗"
        )
        raise HTTPException(status_code=502, detail=f"完整重跑前資料刷新失敗：{message}")
    return refreshed_data


def freeze_full_rerun_inputs(data: dict, *, pipeline_id: str, progress_callback: Any = None) -> None:
    """Establish a NEW full run's quant/input boundary; never call on resume."""
    from quant_engine import QuantEngine
    from analysis_input_provenance import freeze_analysis_inputs
    from analysis_job_helpers import build_data_fetch_blocking_notice
    from types import SimpleNamespace

    notice = build_data_fetch_blocking_notice(SimpleNamespace(data=data, data_trust=data.get("data_trust", {})))
    if notice:
        raise HTTPException(status_code=422, detail=notice["message"])

    data["quant_metrics"] = QuantEngine.compute_all(data)
    if data["quant_metrics"].get("fallback_fields"):
        data["quant_metrics"]["__has_fallback"] = True
    receipt = freeze_analysis_inputs(data)
    if callable(progress_callback):
        progress_callback({"type": "provenance", "phase": "analysis_input_frozen",
                           "pipeline_id": pipeline_id, **receipt})


__all__ = ["freeze_full_rerun_inputs", "prepare_full_rerun_data", "rerun_data_payload"]
