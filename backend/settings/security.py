"""Security and HTTP boundary settings."""

from __future__ import annotations

import os

from .env import env_list, env_str, load_local_env


load_local_env()

DEPLOYMENT_MODE = env_str("DEPLOYMENT_MODE", "local").strip().lower()
_configured_token = os.getenv("MUTATION_API_TOKEN")
MUTATION_API_TOKEN: str | None = str(_configured_token).strip() if _configured_token else None
if DEPLOYMENT_MODE not in {"local", "dev", "development", "test"} and not MUTATION_API_TOKEN:
    raise ValueError("MUTATION_API_TOKEN must be set in production.")


ALLOWED_ORIGINS = env_list(
    "ALLOWED_ORIGINS",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
)
__all__ = ["ALLOWED_ORIGINS", "MUTATION_API_TOKEN", "DEPLOYMENT_MODE"]
