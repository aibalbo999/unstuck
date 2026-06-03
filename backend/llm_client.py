"""Google GenAI client helpers, API-key rotation, and dynamic rate limiting."""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from google import genai

from config import API_KEY_SETUP_MESSAGE, RPM_LIMITS, TPM_LIMITS


@dataclass
class TokenBucket:
    capacity: float
    refill_per_second: float
    tokens: float
    updated_at: float

    @classmethod
    def per_minute(cls, limit: int | float) -> "TokenBucket":
        capacity = max(float(limit), 1.0)
        return cls(
            capacity=capacity,
            refill_per_second=capacity / 60.0,
            tokens=capacity,
            updated_at=time.monotonic(),
        )

    def reserve(self, amount: int | float = 1) -> float:
        amount = min(max(float(amount), 1.0), self.capacity)
        now = time.monotonic()

        if now < self.updated_at:
            wait = self.updated_at - now + amount / self.refill_per_second
            self.updated_at += amount / self.refill_per_second
            return wait

        elapsed = now - self.updated_at
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated_at = now

        if self.tokens >= amount:
            self.tokens -= amount
            return 0.0

        shortage = amount - self.tokens
        wait = shortage / self.refill_per_second
        self.tokens = 0.0
        self.updated_at = now + wait
        return wait

    def peek_wait(self, amount: int | float = 1) -> float:
        amount = min(max(float(amount), 1.0), self.capacity)
        now = time.monotonic()

        if now < self.updated_at:
            return self.updated_at - now + amount / self.refill_per_second

        tokens = min(self.capacity, self.tokens + (now - self.updated_at) * self.refill_per_second)
        if tokens >= amount:
            return 0.0
        return (amount - tokens) / self.refill_per_second

    def penalize(self, seconds: float) -> None:
        self.tokens = 0.0
        self.updated_at = max(self.updated_at, time.monotonic() + max(seconds, 0.0))


class KeyRotator:
    """
    API Key rotator with per-key/model token buckets.

    RPM is always enforced. TPM is enforced when configured for the model.
    The async path uses an asyncio lock so parallel agents can share one rotator
    without racing each other into a 429.
    """

    def __init__(self, keys: list[str]):
        if not keys:
            raise RuntimeError(API_KEY_SETUP_MESSAGE)
        self.keys = list(keys)
        self.index = 0
        self._rpm_buckets: dict[tuple[str, str], TokenBucket] = {}
        self._tpm_buckets: dict[tuple[str, str], TokenBucket] = {}
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    def _bucket(self, store: dict, key: str, model: str, limit: int | float) -> TokenBucket:
        bucket_key = (key, model)
        if bucket_key not in store:
            store[bucket_key] = TokenBucket.per_minute(limit)
        return store[bucket_key]

    def _reserve_for_key(self, key: str, model: str, estimated_tokens: int = 0) -> float:
        rpm_limit = RPM_LIMITS.get(model, RPM_LIMITS.get("*", 5))
        wait = self._bucket(self._rpm_buckets, key, model, rpm_limit).reserve(1)

        tpm_limit = TPM_LIMITS.get(model) or TPM_LIMITS.get("*")
        if tpm_limit and estimated_tokens > 0:
            token_wait = self._bucket(self._tpm_buckets, key, model, tpm_limit).reserve(estimated_tokens)
            wait = max(wait, token_wait)

        return wait

    def _wait_for_key(self, key: str, model: str, estimated_tokens: int = 0) -> float:
        rpm_limit = RPM_LIMITS.get(model, RPM_LIMITS.get("*", 5))
        wait = self._bucket(self._rpm_buckets, key, model, rpm_limit).peek_wait(1)

        tpm_limit = TPM_LIMITS.get(model) or TPM_LIMITS.get("*")
        if tpm_limit and estimated_tokens > 0:
            token_wait = self._bucket(self._tpm_buckets, key, model, tpm_limit).peek_wait(estimated_tokens)
            wait = max(wait, token_wait)

        return wait

    def _next_key(self) -> str:
        key = self.keys[self.index]
        self.index = (self.index + 1) % len(self.keys)
        return key

    def _preview_key(self, key: str) -> str:
        return f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"

    def get_key(self, model: str, estimated_tokens: int = 0) -> str:
        """Return a key after reserving RPM/TPM budget; sleeps only when budget is depleted."""
        while True:
            with self._sync_lock:
                candidates = [self._next_key() for _ in self.keys]
                reservations = [
                    (self._wait_for_key(key, model, estimated_tokens), key)
                    for key in candidates
                ]
                wait, key = min(reservations, key=lambda item: item[0])
                if wait <= 0:
                    self._reserve_for_key(key, model, estimated_tokens)

            if wait > 0:
                print(f"    ⏳ {model} 動態限速等待 {wait:.1f} 秒...")
                time.sleep(wait)
                continue

            print(f"    🔑 使用 Key {self.keys.index(key)+1}/{len(self.keys)} ({self._preview_key(key)})")
            return key

    async def async_get_key(self, model: str, estimated_tokens: int = 0) -> str:
        """Async version of get_key for parallel agent execution."""
        while True:
            async with self._async_lock:
                candidates = [self._next_key() for _ in self.keys]
                reservations = [
                    (self._wait_for_key(key, model, estimated_tokens), key)
                    for key in candidates
                ]
                wait, key = min(reservations, key=lambda item: item[0])
                if wait <= 0:
                    self._reserve_for_key(key, model, estimated_tokens)

            if wait > 0:
                print(f"    ⏳ {model} 動態限速等待 {wait:.1f} 秒...")
                await asyncio.sleep(wait)
                continue

            print(f"    🔑 使用 Key {self.keys.index(key)+1}/{len(self.keys)} ({self._preview_key(key)})")
            return key

    def penalize(self, key: str, model: str, wait_seconds: float = 60) -> None:
        """Push a key/model pair into cooldown after provider-side rate limiting."""
        with self._sync_lock:
            rpm_limit = RPM_LIMITS.get(model, RPM_LIMITS.get("*", 5))
            self._bucket(self._rpm_buckets, key, model, rpm_limit).penalize(wait_seconds)
            tpm_limit = TPM_LIMITS.get(model) or TPM_LIMITS.get("*")
            if tpm_limit:
                self._bucket(self._tpm_buckets, key, model, tpm_limit).penalize(wait_seconds)

    def get_status(self) -> dict:
        now = time.monotonic()
        status = {}
        for i, key in enumerate(self.keys):
            key_name = f"Key-{i+1}"
            status[key_name] = {}
            for (bucket_key, model), bucket in self._rpm_buckets.items():
                if bucket_key != key:
                    continue
                available_in = max(bucket.updated_at - now, 0.0)
                status[key_name][model] = {
                    "rpm_tokens": round(bucket.tokens, 2),
                    "available_in_seconds": round(available_in, 2),
                }
        return status


def estimate_text_tokens(text: str, response_budget: int = 0) -> int:
    """Small local estimate for TPM throttling; intentionally conservative."""
    if not text:
        return max(response_budget, 1)
    return max(int(len(text) / 3.5) + response_budget, 1)


def response_text(response) -> str:
    """Extract text from a Google GenAI response without leaking object internals."""
    try:
        text = getattr(response, "text", None)
    except Exception:
        text = None
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    parts = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(part_text)
    return "\n".join(parts)


def generate_content(api_key: str, model_id: str, prompt: str, config):
    """Call Google GenAI synchronously with an isolated per-key client."""
    client = genai.Client(api_key=api_key)
    try:
        return client.models.generate_content(model=model_id, contents=prompt, config=config)
    finally:
        with suppress(Exception):
            client.close()


async def generate_content_async(api_key: str, model_id: str, prompt: str, config):
    """Call Google GenAI through the async client implementation."""
    client = genai.Client(api_key=api_key)
    try:
        return await client.aio.models.generate_content(model=model_id, contents=prompt, config=config)
    finally:
        with suppress(Exception):
            await client.aio.aclose()
        with suppress(Exception):
            client.close()


def is_quota_or_rate_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return (
        "429" in normalized
        or "quota" in normalized
        or "rate" in normalized
        or "resource_exhausted" in normalized
        or "resource exhausted" in normalized
    )


def retry_delay_seconds(error: Any, default: float = 60) -> float:
    details = getattr(error, "details", None)
    raw = " ".join([str(error), json.dumps(details, ensure_ascii=False) if details else ""])
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", raw, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r"retry(?:_|-)?after['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)", raw, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return default


def describe_quota_or_rate_error(error: Any) -> str:
    """Return a concise, secret-safe description of a Google quota/rate error."""
    raw = str(error)
    details = getattr(error, "details", None)
    code = getattr(error, "code", None)
    status = getattr(error, "status", None)
    message = getattr(error, "message", None)

    found: list[str] = []
    seen: set[str] = set()

    def add(label: str, value: Any):
        if value is None or value == "":
            return
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        text = f"{label}={value}"
        if text not in seen:
            seen.add(text)
            found.append(text)

    def walk(value: Any):
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in {"quotametric", "quotaid", "quotavalue", "retrydelay", "reason"}:
                    add(key, item)
                elif lowered == "quotadimensions" and isinstance(item, dict):
                    for dim_key in ("model", "location"):
                        if dim_key in item:
                            add(f"quotaDimensions.{dim_key}", item[dim_key])
                elif lowered == "metadata" and isinstance(item, dict):
                    for meta_key, meta_value in item.items():
                        meta_lowered = str(meta_key).lower()
                        if "quota" in meta_lowered and meta_lowered != "consumer":
                            add(f"metadata.{meta_key}", meta_value)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(details)

    signature = " ".join([raw, json.dumps(details, ensure_ascii=False) if details else ""]).lower()
    if "tokensperminute" in signature or "tokens_per_minute" in signature or "tpm" in signature:
        condition = "每分鐘 token 額度（TPM）"
    elif "requestsperminute" in signature or "requests_per_minute" in signature or "rpm" in signature:
        condition = "每分鐘請求額度（RPM）"
    elif "requestsperday" in signature or "requests_per_day" in signature or "perday" in signature:
        condition = "每日請求額度（RPD）"
    elif "free_tier" in signature or "free-tier" in signature or "freetier" in signature:
        condition = "免費層/專案配額"
    else:
        condition = "Google API 配額或速率限制（未提供細項）"

    summary_parts = []
    if code or status:
        summary_parts.append(" ".join(str(x) for x in (code, status) if x))
    if message:
        summary_parts.append(str(message))
    summary_parts.append(condition)
    summary_parts.extend(found[:6])

    return "；".join(summary_parts)


def is_missing_model_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return "404" in normalized or "not found" in normalized
