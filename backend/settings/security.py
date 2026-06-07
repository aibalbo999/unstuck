"""Security and HTTP boundary settings."""

from __future__ import annotations

from .env import env_list, env_str


ALLOWED_ORIGINS = env_list(
    "ALLOWED_ORIGINS",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)
MUTATION_API_TOKEN = env_str("MUTATION_API_TOKEN", env_str("ADMIN_API_TOKEN", ""))


__all__ = ["ALLOWED_ORIGINS", "MUTATION_API_TOKEN"]
