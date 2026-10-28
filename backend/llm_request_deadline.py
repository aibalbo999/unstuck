"""Carry an admitted response deadline to the SDK without changing shared clients."""
from contextlib import contextmanager
from contextvars import ContextVar
import math

from google.genai import types

_response_timeout = ContextVar("llm_response_timeout_seconds", default=None)


def current_response_timeout():
    return _response_timeout.get()


@contextmanager
def response_timeout_scope(seconds):
    value = float(seconds) if seconds is not None else 0.0
    timeout = value if math.isfinite(value) and value > 0 else None
    token = _response_timeout.set(timeout)
    try:
        yield
    finally:
        _response_timeout.reset(token)


def apply_response_timeout(config):
    """Override the client default, but retain an explicit shorter request limit.

    GenAI derives X-Server-Timeout from this per-request HttpOptions timeout.
    The application still enforces its outer deadline and completion gates.
    """
    seconds = current_response_timeout()
    if seconds is None:
        return config
    if config is None or isinstance(config, dict):
        config = types.GenerateContentConfig.model_validate(config or {})
    options = config.http_options or types.HttpOptions()
    milliseconds = max(1, math.ceil(seconds * 1000))
    if options.timeout is not None and options.timeout > 0:
        milliseconds = min(milliseconds, options.timeout)
    headers = dict(options.headers or {})
    server_timeout = math.ceil(milliseconds / 1000)
    for name in list(headers):
        if name.lower() != "x-server-timeout":
            continue
        explicit = headers.pop(name)
        try:
            explicit_seconds = float(explicit)
        except (TypeError, ValueError):
            raise ValueError("X-Server-Timeout must be a positive finite number") from None
        if not math.isfinite(explicit_seconds) or explicit_seconds <= 0:
            raise ValueError("X-Server-Timeout must be a positive finite number")
        server_timeout = min(server_timeout, explicit_seconds)
        milliseconds = min(milliseconds, max(1, math.ceil(explicit_seconds * 1000)))
    # The SDK may retain an old auto-generated header on a cached client.
    # Request-local headers must override it, without mutating shared state.
    headers["X-Server-Timeout"] = f"{server_timeout:g}"
    return config.model_copy(update={"http_options": options.model_copy(
        update={"timeout": milliseconds, "headers": headers})})
