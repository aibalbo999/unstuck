"""Revision-scoped report-quality review routes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from mapping_fields import safe_mapping_dict, safe_text
from report_index_parsing import is_safe_report_filename
from report_quality_review_store import SCHEMA_VERSION as REPORT_QUALITY_REVIEW_SCHEMA_VERSION


def register_report_quality_review_routes(
    router: APIRouter,
    *,
    get_output_dir: Callable[[], str],
    require_mutation_authorized: Callable[[Request], None],
    get_target: Callable[..., dict[str, Any] | None],
    record_review: Callable[..., dict[str, Any]],
) -> None:
    @router.get("/report-quality-audit/review")
    async def get_report_quality_review(
        filename: str = Query("", max_length=240),
        pipeline: str = Query("v1", max_length=24),
    ):
        if not is_safe_report_filename(filename, ".html"):
            raise HTTPException(status_code=400, detail="Invalid filename")
        target = await asyncio.to_thread(
            get_target,
            get_output_dir(),
            filename=filename,
            pipeline_id=pipeline,
        )
        if target is None:
            raise HTTPException(status_code=404, detail="Quality review target not found")
        return {"schema_version": REPORT_QUALITY_REVIEW_SCHEMA_VERSION, "target": target}

    @router.post("/report-quality-audit/review")
    async def save_report_quality_review(request: Request):
        require_mutation_authorized(request)
        payload = safe_mapping_dict(await request.json()) or {}
        filename = safe_text(payload.get("filename")).strip()
        pipeline = safe_text(payload.get("pipeline_id")).strip() or "v1"
        provided_revision = safe_text(payload.get("report_quality_revision")).strip()
        if not is_safe_report_filename(filename, ".html"):
            raise HTTPException(status_code=400, detail="Invalid filename")
        if not provided_revision:
            raise HTTPException(status_code=400, detail="report_quality_revision is required")
        target = await asyncio.to_thread(
            get_target,
            get_output_dir(),
            filename=filename,
            pipeline_id=pipeline,
        )
        if target is None:
            raise HTTPException(status_code=404, detail="Quality review target not found")
        expected_revision = safe_text(target.get("report_quality_revision")).strip()
        if provided_revision != expected_revision:
            raise HTTPException(status_code=409, detail="Report quality revision is stale; reload the audit target")
        try:
            review = await asyncio.to_thread(
                record_review,
                output_dir=get_output_dir(),
                filename=filename,
                ticker=safe_text(target.get("ticker")).strip(),
                pipeline_id=pipeline,
                report_quality_revision=expected_revision,
                missing_quality_fields=target.get("missing_quality_fields") or [],
                artifact_quality_summary=safe_mapping_dict(target.get("artifact_quality_summary")) or {},
                decision=safe_text(payload.get("decision")).strip(),
                note=safe_text(payload.get("note") or payload.get("reviewer_notes")),
                reviewer_label=safe_text(payload.get("reviewer_label")).strip() or "local_operator",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "schema_version": REPORT_QUALITY_REVIEW_SCHEMA_VERSION,
            "success": True,
            "target": {**target, "quality_review": review},
            "review": review,
            "effects": {
                "artifact_written": False,
                "report_index_written": False,
                "rerun_enqueued": False,
            },
        }
