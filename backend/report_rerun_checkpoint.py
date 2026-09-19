"""Bind full rerun retries to one job's persistent graph and input snapshot."""
from __future__ import annotations

import hashlib

from fastapi import HTTPException

from runtime_dependencies import runtime_settings_for_output_dir
from workflow_checkpoints import open_checkpointer
from workflow_context import copy_json


async def full_rerun_checkpoint(*, job_id, source_filename, scope, pipeline_id, output_dir):
    """Return request options and saved input, without reserving model capacity.

    Direct service calls without a queue job retain their nonpersistent behavior.
    Use a job-specific thread; never share progress across separately queued jobs.
    Source and scope isolate runs; a changed source pipeline must fail closed.
    """
    if not job_id:
        return {}, None
    source_id = hashlib.sha256(source_filename.encode("utf-8")).hexdigest()
    thread_id = f"{job_id}:report-rerun:{scope}:{source_id}"
    settings = runtime_settings_for_output_dir(output_dir)
    options = {
        "thread_id": thread_id,
        "checkpoint_path": settings.checkpoint_path,
        "checkpoint_backend": settings.checkpoint_backend,
        "checkpoint_postgres_dsn": settings.checkpoint_postgres_dsn,
    }
    async with open_checkpointer(
        checkpoint_path=settings.checkpoint_path,
        checkpoint_backend=settings.checkpoint_backend,
        postgres_dsn=settings.checkpoint_postgres_dsn,
    ) as saver:
        saved = await saver.aget_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}})
    if saved is None:
        return options, None
    state = saved.checkpoint.get("channel_values", {})
    raw = state.get("raw_financial_data")
    data = raw.get("input") if isinstance(raw, dict) else None
    if (state.get("pipeline_id") != pipeline_id
            or not isinstance(data, dict) or not data):
        raise HTTPException(status_code=409, detail="重跑進度與原資料無法確認一致，請建立新的完整重跑任務。")
    return options, copy_json(data)
