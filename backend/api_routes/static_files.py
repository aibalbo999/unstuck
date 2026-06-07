"""Static UI routes."""

from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import APIRouter
from fastapi.responses import FileResponse


def create_static_router(get_static_dir: Callable[[], str]) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    def read_root():
        return FileResponse(os.path.join(get_static_dir(), "index.html"))

    @router.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(os.path.join(get_static_dir(), "favicon.ico"), media_type="image/x-icon")

    @router.get("/apple-touch-icon.png", include_in_schema=False)
    @router.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
    def apple_touch_icon():
        return FileResponse(os.path.join(get_static_dir(), "apple-touch-icon.png"), media_type="image/png")

    return router

