"""Fingerprint the exact non-secret model-route file loaded by this process."""

from __future__ import annotations

from settings.models import MODEL_ROUTES_FILE_SHA256


def model_route_policy_sha256() -> str:
    return MODEL_ROUTES_FILE_SHA256
