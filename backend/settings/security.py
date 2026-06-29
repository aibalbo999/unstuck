"""Security and HTTP boundary settings."""

from __future__ import annotations

import os

from .env import env_bool, env_int, env_list, env_str, load_local_env


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
ALLOW_LEGACY_ADMIN_TOKEN = env_bool("ALLOW_LEGACY_ADMIN_TOKEN", False)
MUTATION_RATE_LIMIT_MAX_REQUESTS = env_int("MUTATION_RATE_LIMIT_MAX_REQUESTS", 120)
MUTATION_RATE_LIMIT_WINDOW_SECONDS = env_int("MUTATION_RATE_LIMIT_WINDOW_SECONDS", 60)
BASIC_AUTH_USERNAME = env_str("BASIC_AUTH_USERNAME", "").strip()
BASIC_AUTH_PASSWORD = env_str("BASIC_AUTH_PASSWORD", "")
EXTERNAL_ACCESS_CONTROLLED = env_bool("EXTERNAL_ACCESS_CONTROLLED", False)

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


def has_basic_auth_configured() -> bool:
    return bool(BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD)


def has_network_access_guard() -> bool:
    return has_basic_auth_configured() or EXTERNAL_ACCESS_CONTROLLED


if is_production_profile() and not MUTATION_API_TOKEN:
    raise ValueError("MUTATION_API_TOKEN must be set in production.")
if is_production_profile() and "*" in ALLOWED_ORIGINS:
    raise ValueError("ALLOWED_ORIGINS cannot include wildcard in production.")


__all__ = [
    "ALLOW_LEGACY_ADMIN_TOKEN",
    "ALLOWED_ORIGINS",
    "BASIC_AUTH_PASSWORD",
    "BASIC_AUTH_USERNAME",
    "EXTERNAL_ACCESS_CONTROLLED",
    "MUTATION_API_TOKEN",
    "MUTATION_RATE_LIMIT_MAX_REQUESTS",
    "MUTATION_RATE_LIMIT_WINDOW_SECONDS",
    "DEPLOYMENT_MODE",
    "UNSTUCK_ENV",
    "has_basic_auth_configured",
    "has_network_access_guard",
    "is_production_profile",
]
