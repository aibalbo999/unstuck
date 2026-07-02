"""Static UI routes."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse


def create_static_router(
    get_static_dir: Callable[[], str],
    get_client_config: Optional[Callable[[], dict]] = None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    def read_root():
        index_html = Path(get_static_dir(), "index.html").read_text(encoding="utf-8")
        return HTMLResponse(index_html)

    @router.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(os.path.join(get_static_dir(), "favicon.ico"), media_type="image/x-icon")

    @router.get("/apple-touch-icon.png", include_in_schema=False)
    @router.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
    def apple_touch_icon():
        return FileResponse(os.path.join(get_static_dir(), "apple-touch-icon.png"), media_type="image/png")

    @router.get("/api/client-config")
    def client_config():
        headers = {"Cache-Control": "no-store"}
        if get_client_config is None:
            return JSONResponse({"mutation_header": "X-Mutation-Token", "mutation_token": ""}, headers=headers)
        return JSONResponse(get_client_config(), headers=headers)

    return router
