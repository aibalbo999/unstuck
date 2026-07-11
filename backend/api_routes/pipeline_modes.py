"""Read-only pipeline mode catalog route."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from pipeline_mode_catalog import SCHEMA_VERSION, build_pipeline_mode_catalog


def create_pipeline_modes_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/pipeline-modes")
    def get_pipeline_modes():
        return JSONResponse(
            {"schema_version": SCHEMA_VERSION, "modes": build_pipeline_mode_catalog()},
            headers={"Cache-Control": "no-store"},
        )

    return router


__all__ = ["create_pipeline_modes_router"]
