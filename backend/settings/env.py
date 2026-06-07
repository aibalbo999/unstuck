"""Environment parsing helpers for backend settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_ROUTES_FILE = BASE_DIR / "model_routes.json"


def is_placeholder_key(key: str) -> bool:
    lowered = str(key or "").lower()
    return any(marker in lowered for marker in ["replace_with", "your_key", "example", "placeholder"])


def load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (key not in os.environ or is_placeholder_key(os.environ[key])):
            os.environ[key] = value


def split_keys(raw: str) -> list[str]:
    return [key.strip() for key in str(raw or "").replace("\n", ",").split(",") if key.strip()]


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return str(default or "").strip()
    return raw.strip()


def env_list(name: str, default: Optional[list[str]] = None) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return list(default or [])
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in raw.split(",") if item.strip()]


def json_env_dict(name: str) -> dict:
    raw = os.getenv(name, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}
