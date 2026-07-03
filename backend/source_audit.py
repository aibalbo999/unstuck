"""Runtime wrappers for audited data source fetches."""

from __future__ import annotations

import inspect
import time
from typing import Any, Callable, Optional

from data_trust import (
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
    append_source_audit,
    build_source_audit_entry,
    finalize_data_trust,
    source_record_count,
)
from provider_resilience import (
    ProviderCircuitOpenError,
    ProviderRateLimitOpenError,
    call_provider_with_resilience,
    call_provider_with_resilience_async,
)


def record_count_from_value(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return 0 if not value.strip() or value.strip().upper() == "N/A" else 1
    if isinstance(value, list):
        return len([item for item in value if item is not None])
    if isinstance(value, tuple):
        return len([item for item in value if item is not None])
    if isinstance(value, dict):
        return len(value)
    return 1


def audited_fetch(
    source: str,
    provider: str,
    func: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    default: Any = None,
    *,
    record_counter: Optional[Callable[[Any], int]] = None,
    cache_hit: bool = False,
    stale: bool = False,
    unavailable_if_empty: bool = True,
    success_message: str = "來源抓取成功。",
    unavailable_message: str = "來源未回傳可用資料。",
) -> dict:
    started = time.time()
    try:
        value = call_provider_with_resilience(provider, func, args, kwargs or {})
    except (ProviderCircuitOpenError, ProviderRateLimitOpenError) as exc:
        finished = time.time()
        return {
            "value": default,
            "audit": build_source_audit_entry(
                source,
                provider,
                AUDIT_STATUS_UNAVAILABLE,
                started_at_epoch=started,
                finished_at_epoch=finished,
                record_count=0,
                cache_hit=cache_hit,
                stale=stale,
                error_kind=exc.__class__.__name__,
                message=str(exc)[:240],
            ),
        }
    except Exception as exc:
        finished = time.time()
        return {
            "value": default,
            "audit": build_source_audit_entry(
                source,
                provider,
                AUDIT_STATUS_ERROR,
                started_at_epoch=started,
                finished_at_epoch=finished,
                record_count=0,
                cache_hit=cache_hit,
                stale=stale,
                error_kind=exc.__class__.__name__,
                message=str(exc)[:240],
            ),
        }

    finished = time.time()
    count = record_counter(value) if record_counter else record_count_from_value(value)
    status = AUDIT_STATUS_SUCCESS
    message = success_message
    if unavailable_if_empty and count <= 0:
        status = AUDIT_STATUS_UNAVAILABLE
        message = unavailable_message
    return {
        "value": value,
        "audit": build_source_audit_entry(
            source,
            provider,
            status,
            fetched_at_epoch=finished,
            started_at_epoch=started,
            finished_at_epoch=finished,
            record_count=count,
            cache_hit=cache_hit,
            stale=stale,
            message=message,
        ),
    }


async def audited_fetch_async(
    source: str,
    provider: str,
    func_or_awaitable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    default: Any = None,
    *,
    record_counter: Optional[Callable[[Any], int]] = None,
    cache_hit: bool = False,
    stale: bool = False,
    unavailable_if_empty: bool = True,
    success_message: str = "來源抓取成功。",
    unavailable_message: str = "來源未回傳可用資料。",
) -> dict:
    started = time.time()
    try:
        value = await call_provider_with_resilience_async(provider, func_or_awaitable, args, kwargs or {})
    except (ProviderCircuitOpenError, ProviderRateLimitOpenError) as exc:
        finished = time.time()
        return {
            "value": default,
            "audit": build_source_audit_entry(
                source,
                provider,
                AUDIT_STATUS_UNAVAILABLE,
                started_at_epoch=started,
                finished_at_epoch=finished,
                record_count=0,
                cache_hit=cache_hit,
                stale=stale,
                error_kind=exc.__class__.__name__,
                message=str(exc)[:240],
            ),
        }
    except Exception as exc:
        finished = time.time()
        return {
            "value": default,
            "audit": build_source_audit_entry(
                source,
                provider,
                AUDIT_STATUS_ERROR,
                started_at_epoch=started,
                finished_at_epoch=finished,
                record_count=0,
                cache_hit=cache_hit,
                stale=stale,
                error_kind=exc.__class__.__name__,
                message=str(exc)[:240],
            ),
        }

    finished = time.time()
    count = record_counter(value) if record_counter else record_count_from_value(value)
    status = AUDIT_STATUS_SUCCESS
    message = success_message
    if unavailable_if_empty and count <= 0:
        status = AUDIT_STATUS_UNAVAILABLE
        message = unavailable_message
    return {
        "value": value,
        "audit": build_source_audit_entry(
            source,
            provider,
            status,
            fetched_at_epoch=finished,
            started_at_epoch=started,
            finished_at_epoch=finished,
            record_count=count,
            cache_hit=cache_hit,
            stale=stale,
            message=message,
        ),
    }


def append_audit_entry(data: dict, entry: dict) -> dict:
    append_source_audit(data, entry)
    finalize_data_trust(data)
    return data


def append_payload_source_audit(
    data: dict,
    source: str,
    provider: str,
    status: str,
    *,
    fetched_at_epoch: Optional[float] = None,
    started_at_epoch: Optional[float] = None,
    finished_at_epoch: Optional[float] = None,
    record_count: Optional[int] = None,
    cache_hit: bool = False,
    stale: bool = False,
    error_kind: str = "",
    message: str = "",
) -> dict:
    append_source_audit(
        data,
        build_source_audit_entry(
            source,
            provider,
            status,
            fetched_at_epoch=fetched_at_epoch,
            started_at_epoch=started_at_epoch,
            finished_at_epoch=finished_at_epoch,
            record_count=source_record_count(source, data) if record_count is None else record_count,
            cache_hit=cache_hit,
            stale=stale,
            error_kind=error_kind,
            message=message,
        ),
    )
    finalize_data_trust(data)
    return data
