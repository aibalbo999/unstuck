"""Security and HTTP boundary settings."""

from __future__ import annotations

import os

from .env import env_list, env_str, load_local_env


load_local_env()

UNSTUCK_ENV = env_str("UNSTUCK_ENV", "").strip().lower()
_deployment_mode = env_str("DEPLOYMENT_MODE", "").strip().lower()
if UNSTUCK_ENV in {"production", "prod"}:
    DEPLOYMENT_MODE = "production"
elif UNSTUCK_ENV in {"local", "dev", "development", "test"} and not _deployment_mode:
    DEPLOYMENT_MODE = "local"
else:
    DEPLOYMENT_MODE = _deployment_mode or "local"
_configured_token = os.getenv("MUTATION_API_TOKEN")
MUTATION_API_TOKEN: str | None = str(_configured_token).strip() if _configured_token else None

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


def is_production_profile(mode: str | None = None) -> bool:
    return str(mode or DEPLOYMENT_MODE or "local").strip().lower() in {"production", "prod", "server", "lan"}


if is_production_profile() and not MUTATION_API_TOKEN:
    raise ValueError("MUTATION_API_TOKEN must be set in production.")
if is_production_profile() and "*" in ALLOWED_ORIGINS:
    raise ValueError("ALLOWED_ORIGINS cannot include wildcard in production.")


__all__ = ["ALLOWED_ORIGINS", "MUTATION_API_TOKEN", "DEPLOYMENT_MODE", "UNSTUCK_ENV", "is_production_profile"]
