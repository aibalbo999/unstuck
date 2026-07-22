"""FastAPI app shell setup helpers."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from api_observability_service import build_prometheus_metrics


def install_cors_static_and_metrics(
    app: FastAPI,
    *,
    allowed_origins: list[str],
    allow_methods: list[str],
    allow_headers: list[str],
    static_dir: str,
    get_provider_sla_summary: Callable,
    get_task_queue: Callable,
    build_metrics: Callable = build_prometheus_metrics,
    emit_warning: Callable[[str], None] | None = None,
) -> None:
    allow_credentials = "*" not in allowed_origins
    if not allow_credentials and emit_warning is not None:
        emit_warning("警告：ALLOWED_ORIGINS 含萬用字元 *，已停用 credentials 支援。")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
    )
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics():
        content = await build_metrics(
            lambda limit=100: get_provider_sla_summary(limit),
            task_queue=get_task_queue(),
        )
        return PlainTextResponse(content, media_type="text/plain; version=0.0.4")
