"""Mutation-token authorization and CORS profile helpers for the API app."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException


MUTATION_HEADER_NAME = "X-Mutation-Token"


def runtime_mutation_token(runtime_token: str) -> str:
    return str(runtime_token or "").strip()


def is_local_deployment_mode(deployment_mode: str) -> bool:
    return str(deployment_mode or "local").strip().lower() == "local"


def is_restricted_cors_profile(deployment_mode: str) -> bool:
    return str(deployment_mode or "local").strip().lower() in {"production", "prod", "server", "lan"}


def cors_allow_methods(deployment_mode: str) -> list[str]:
    return ["GET", "POST", "DELETE", "OPTIONS"] if is_restricted_cors_profile(deployment_mode) else ["*"]


def cors_allow_headers(deployment_mode: str, mutation_header_name: str = MUTATION_HEADER_NAME) -> list[str]:
    if not is_restricted_cors_profile(deployment_mode):
        return ["*"]
    return ["Content-Type", mutation_header_name, "X-Admin-Token", "Last-Event-ID"]


def allowed_mutation_tokens(deployment_mode: str, runtime_token: str, mutation_api_token: str) -> set[str]:
    local_runtime_token = runtime_mutation_token(runtime_token) if is_local_deployment_mode(deployment_mode) else ""
    return {
        token for token in {
            local_runtime_token,
            str(mutation_api_token or "").strip(),
        }
        if token
    }


def client_config(
    deployment_mode: str,
    runtime_token: str,
    mutation_header_name: str = MUTATION_HEADER_NAME,
) -> dict:
    normalized_mode = str(deployment_mode or "local").strip().lower()
    return {
        "mutation_header": mutation_header_name,
        "mutation_token": runtime_mutation_token(runtime_token) if is_local_deployment_mode(normalized_mode) else "",
        "deployment_mode": normalized_mode,
    }


def require_mutation_authorized(
    request,
    *,
    check_mutation_rate_limit: Callable,
    allow_legacy_admin_token: bool,
    mutation_api_token: str,
    runtime_mutation_token: str,
    deployment_mode: str,
    max_requests: int,
    window_seconds: int,
) -> None:
    mutation_token = str(request.headers.get("x-mutation-token") or "").strip()
    legacy_token = str(request.headers.get("x-admin-token") or "").strip()
    check_mutation_rate_limit(
        request,
        [mutation_token, legacy_token],
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    supplied_tokens = [mutation_token]
    if allow_legacy_admin_token:
        supplied_tokens.append(legacy_token)
    allowed = allowed_mutation_tokens(deployment_mode, runtime_mutation_token, mutation_api_token)
    if not any(token and token in allowed for token in supplied_tokens):
        raise HTTPException(status_code=403, detail="Mutation endpoint requires a valid mutation token")
