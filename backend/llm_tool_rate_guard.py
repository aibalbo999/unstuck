"""Call-scoped admission for SDK automatic function calling HTTP requests."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from contextvars import ContextVar

import httpx
from google.genai import types

import llm_rate_limits as limits
from llm_input_capacity import ensure_input_capacity, estimate_input_tokens
from llm_provider_routes import split_model_provider


_scope = ContextVar("llm_tool_request_scope", default=None)
_sleep_async = asyncio.sleep


class ToolRequestGuardError(RuntimeError):
    """A local tool-loop contract failure, not a retryable provider error."""


def tool_request_scope(rotator, api_key, model_id, *, request_units=1):
    enabled = request_units > 1 and split_model_provider(model_id)[0] == "google"
    return _ToolRequestScope(rotator, api_key, model_id, min(int(request_units), 6) if enabled else 0)


def current_tool_scope(api_key):
    scope = _scope.get()
    return scope if scope is not None and scope.api_key == api_key else None


def generation_client(api_key, model_id, cached_client, factory, http_options):
    scope = current_tool_scope(api_key)
    if scope is not None and scope.model_id == model_id:
        return scope.client(factory, http_options())
    return cached_client(api_key)


def _request_input_tokens(request):
    try:
        payload = json.loads(request.content)
        inputs = {key: payload[key] for key in (
            "contents", "systemInstruction", "tools", "toolConfig", "cachedContent",
        ) if key in payload}
        generation = payload.get("generationConfig") or {}
        schemas = {key: generation[key] for key in ("responseSchema", "responseJsonSchema") if key in generation}
        if schemas:
            inputs["generationConfig"] = schemas
        return estimate_input_tokens(json.dumps(inputs, ensure_ascii=False))
    except (ValueError, TypeError, AttributeError, httpx.RequestNotRead):
        raise ToolRequestGuardError("Cannot estimate tool request input") from None


async def _finish_cleanup(awaitable):
    """Finish resource cleanup even if the caller is cancelled again."""
    task = asyncio.ensure_future(awaitable)
    cancelled = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as exc:
            cancelled = exc
    task.result()
    if cancelled is not None:
        raise cancelled


@asynccontextmanager
async def closing_stream(stream):
    error = None
    try:
        yield stream
    except BaseException as exc:
        error = exc
        raise
    finally:
        try:
            if callable(close := getattr(stream, "aclose", None)):
                await _finish_cleanup(close())
            elif callable(close := getattr(stream, "close", None)):
                close()
        except Exception:
            if error is None:
                raise


class _ToolRequestScope:
    def __init__(self, rotator, api_key, model_id, maximum):
        self.rotator, self.api_key, self.model_id = rotator, api_key, model_id
        self.maximum, self.sent = maximum, 0
        self._client = self._transport = None
        self._counter_lock = threading.Lock()
        self.active = False

    def __enter__(self):
        self.active = True
        self._token = _scope.set(self if self.maximum else None)
        return self

    async def __aenter__(self):
        return self.__enter__()

    def _reset(self):
        self.active = False
        _scope.reset(self._token)

    async def _aclose(self):
        try:
            if self._client is not None:
                try:
                    self._client.close()
                finally:
                    await self._client.aio.aclose()
            elif self._transport is not None:
                await self._transport.aclose()
        finally:
            self._client = self._transport = None

    def __exit__(self, exc_type, error, traceback):
        self._reset()
        try:
            self._close_sync()
        except Exception:
            if error is None:
                raise

    def _close_sync(self):
        if self._client is None and self._transport is None:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._aclose())
        else:
            # A sync call may run inside an event loop; its unused async client
            # has no loop-bound connections and can be closed in a helper thread.
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(lambda: asyncio.run(self._aclose())).result()

    async def __aexit__(self, exc_type, error, traceback):
        self._reset()
        try:
            if self._client is not None or self._transport is not None:
                await _finish_cleanup(self._aclose())
        except Exception:
            if error is None:
                raise

    def client(self, factory, options):
        if not self.active:
            raise ToolRequestGuardError("Tool request scope is closed")
        if self._client is None:
            self._transport = httpx.AsyncHTTPTransport()
            options = (options or types.HttpOptions()).model_copy(update={
                "retry_options": types.HttpRetryOptions(attempts=1),
                "client_args": {"event_hooks": {"request": [self.before_request]}, "follow_redirects": False},
                "async_client_args": {"transport": self._transport,
                                      "event_hooks": {"request": [self.before_request_async]}, "follow_redirects": False},
            })
            self._client = factory(api_key=self.api_key, http_options=options)
        return self._client

    def _claim_request(self, request):
        path, _, action = request.url.path.rpartition(":")
        if action not in {"generateContent", "streamGenerateContent"}:
            return False
        model = split_model_provider(self.model_id)[1].removeprefix("models/")
        if (not self.active or _scope.get() is not self or request.method != "POST"
                or not path.endswith("/models/" + model)
                or request.headers.get("x-goog-api-key", self.api_key) != self.api_key):
            raise ToolRequestGuardError("Tool request does not match its scope")
        with self._counter_lock:
            if self.sent >= self.maximum:
                raise ToolRequestGuardError("Tool request budget exhausted")
            self.sent += 1
            return self.sent > 1

    def _estimate(self, request):
        tokens = _request_input_tokens(request)
        ensure_input_capacity(
            self.model_id, tokens,
            input_limit=limits.MODEL_INPUT_TOKEN_LIMITS.get(self.model_id, limits.MODEL_INPUT_TOKEN_LIMITS.get("*", 0)),
            tpm_limit=limits.TPM_LIMITS.get(self.model_id) or limits.TPM_LIMITS.get("*"),
        )
        return tokens

    def _try_reserve(self, tokens):
        with self.rotator._sync_lock:
            wait = self.rotator._wait_for_key(self.api_key, self.model_id, tokens)
            if wait <= 0:
                # Shared refusal must not debit local buckets on each retry.
                wait = self.rotator._reserve_shared_for_key(self.api_key, self.model_id, tokens)
                if wait <= 0:
                    wait = self.rotator._reserve_for_key(self.api_key, self.model_id, tokens)
            return wait

    def before_request(self, request):
        if self._claim_request(request):
            tokens = self._estimate(request)
            while (wait := self._try_reserve(tokens)) > 0:
                time.sleep(wait)

    async def before_request_async(self, request):
        if self._claim_request(request):
            tokens = self._estimate(request)
            while True:
                async with self.rotator._async_lock:
                    wait = self._try_reserve(tokens)
                if wait <= 0:
                    return
                await _sleep_async(wait)
