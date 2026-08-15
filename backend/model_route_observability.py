"""Model-route observability payload helpers."""

from __future__ import annotations

from typing import Any

from job_observability import build_ops_dashboard_snapshot
from mapping_fields import safe_mapping_dict
from model_route_budget import build_model_route_budget


async def build_model_route_budget_payload(telemetry_limit: int = 5000) -> dict:
    snapshot = await _dashboard_snapshot_or_empty(telemetry_limit=telemetry_limit)
    payload = safe_mapping_dict(snapshot.get("model_route_budget")) if isinstance(snapshot, dict) else {}
    if payload:
        return payload
    empty = build_model_route_budget([])
    if isinstance(snapshot, dict) and snapshot.get("observability_unavailable"):
        empty["observability_unavailable"] = True
    return empty


async def _dashboard_snapshot_or_empty(**kwargs: Any) -> dict:
    try:
        import asyncio

        return await asyncio.to_thread(build_ops_dashboard_snapshot, **kwargs)
    except Exception:
        return {"observability_unavailable": True}


__all__ = ["build_model_route_budget_payload"]
