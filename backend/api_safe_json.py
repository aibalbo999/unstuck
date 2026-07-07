"""JSON response helpers that tolerate market-data missing values."""

from __future__ import annotations

import math
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def sanitize_json_content(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_json_content(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_json_content(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):
        try:
            return sanitize_json_content(value.item())
        except Exception:
            return str(value)
    return value


class SafeJSONResponse(JSONResponse):
    """JSONResponse variant that converts NaN/Infinity to null before rendering."""

    def render(self, content: Any) -> bytes:
        return super().render(sanitize_json_content(jsonable_encoder(content)))
