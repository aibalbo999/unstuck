"""Adapters that record runtime/provider events into the API usage ledger."""

from __future__ import annotations

from pathlib import Path

from api_usage_store import record_api_usage


def record_runtime_event_usage(
    job_id: str,
    payload: dict,
    *,
    created_at: float | None = None,
    db_path: str | Path | None = None,
) -> None:
    phase = str(payload.get("phase") or "")
    if phase not in {"llm_model_call", "llm_model_error", "llm_model_response"}:
        return
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    model_id = str(metadata.get("model_id") or "unknown")
    message = str(payload.get("message") or "")
    if phase == "llm_model_call":
        record_api_usage(
            service="Gemini / Google AI",
            provider="google_ai",
            operation=phase,
            model_id=model_id,
            status="attempt",
            units=1,
            metadata={"job_id": job_id, **metadata},
            created_at=created_at,
            db_path=db_path,
        )
        return
    if phase == "llm_model_error":
        error_category = str(metadata.get("error_category") or "")
        status = "quota_error" if (
            error_category == "quota"
            or "429" in message
            or "quota" in message.lower()
            or "rate" in message.lower()
        ) else "error"
        record_api_usage(
            service="Gemini / Google AI",
            provider="google_ai",
            operation=phase,
            model_id=model_id,
            status=status,
            units=0,
            metadata={"job_id": job_id, "message": message, **metadata},
            created_at=created_at,
            db_path=db_path,
        )
        return
    record_api_usage(
        service="Gemini / Google AI",
        provider="google_ai",
        operation=phase,
        model_id=model_id,
        status="success",
        units=0,
        metadata={"job_id": job_id, **metadata},
        created_at=created_at,
        db_path=db_path,
    )


def record_provider_audit_usage(
    entry: dict,
    *,
    created_at: float | None = None,
    db_path: str | Path | None = None,
) -> None:
    if not isinstance(entry, dict):
        return
    status = str(entry.get("status") or "unknown")
    units = 0 if status == "skipped_fresh_cache" else 1
    record_api_usage(
        service="Data Provider",
        provider=str(entry.get("provider") or "unknown"),
        operation=str(entry.get("source") or "unknown"),
        status=status,
        units=units,
        metadata={
            "duration_ms": entry.get("duration_ms"),
            "record_count": entry.get("record_count"),
            "message": entry.get("message"),
        },
        created_at=created_at,
        db_path=db_path,
    )


__all__ = ["record_provider_audit_usage", "record_runtime_event_usage"]
