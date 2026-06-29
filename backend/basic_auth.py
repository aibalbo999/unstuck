"""Optional Basic Auth guard for network-exposed deployments."""

from __future__ import annotations

import base64
import hmac

from fastapi import Response

from config import BASIC_AUTH_PASSWORD, BASIC_AUTH_USERNAME


BASIC_AUTH_REALM = "stock-agent"


def basic_auth_enabled() -> bool:
    return bool(str(BASIC_AUTH_USERNAME or "").strip() and str(BASIC_AUTH_PASSWORD or ""))


def basic_auth_exempt_path(path: str) -> bool:
    return path == "/healthz"


def is_basic_auth_authorized(authorization: str | None) -> bool:
    if not basic_auth_enabled():
        return True
    scheme, _, encoded = str(authorization or "").partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except Exception:
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    expected_user = str(BASIC_AUTH_USERNAME or "").strip()
    expected_password = str(BASIC_AUTH_PASSWORD or "")
    return hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_password)


def basic_auth_challenge_response() -> Response:
    return Response(
        "Authentication required",
        status_code=401,
        headers={"WWW-Authenticate": f'Basic realm="{BASIC_AUTH_REALM}", charset="UTF-8"'},
    )
