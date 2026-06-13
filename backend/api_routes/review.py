"""Review and certification API routes."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request

from report_index import is_safe_report_filename
from report_review_gate import get_review_status, write_ai_review_result


@dataclass(frozen=True)
class ReviewRouteDeps:
    get_output_dir: Callable[[], str]
    require_mutation_authorized: Callable[[Request], None]


def create_review_router(deps: ReviewRouteDeps) -> APIRouter:
    router = APIRouter()

    @router.get("/api/report/{filename}/review")
    def get_report_review_status(filename: str):
        if not is_safe_report_filename(filename, ".html"):
            raise HTTPException(status_code=400, detail="Invalid filename")
        return get_review_status(filename, deps.get_output_dir())

    @router.post("/api/report/{filename}/review")
    async def save_report_review(filename: str, request: Request):
        deps.require_mutation_authorized(request)
        if not is_safe_report_filename(filename, ".html"):
            raise HTTPException(status_code=400, detail="Invalid filename")

        payload = await request.json()
        verdict = payload.get("status") or payload.get("verdict")
        if not verdict:
            raise HTTPException(status_code=400, detail="Missing review verdict")

        # In a real setup, this endpoint might trigger an async AI review job
        # For now, it allows an operator/frontend to submit a manual review state
        return write_ai_review_result(
            filename,
            deps.get_output_dir(),
            verdict=verdict,
            review_summary=payload.get("reviewer_notes") or payload.get("review_summary") or "",
            critical_issues=payload.get("critical_issues", []),
            warnings=payload.get("warnings", []),
            review_agents_used=payload.get("review_agents_used", []),
        )

    return router
