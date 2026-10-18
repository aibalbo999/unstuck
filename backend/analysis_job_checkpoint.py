"""Read the actual frozen inputs before a normal job resumes its graphs."""
from __future__ import annotations

import json

from job_store import get_job
from pipeline_modes import get_pipeline_run_sequence
from workflow_checkpoints import open_checkpointer
from workflow_context import copy_json


class AnalysisCheckpointInputError(RuntimeError):
    pass


def _same_saved_request(job, ticker, pipeline_sequence):
    return (isinstance(job, dict) and str(job.get("ticker") or "").strip().upper() == ticker
            and get_pipeline_run_sequence(job.get("pipeline_id")) == tuple(pipeline_sequence))


def _resolved_identity_matches(job, ticker, pipeline_sequence, resolved):
    # The provider already resolved this exact request during the original
    # acquisition. Bind that result to the server-owned job snapshot; do not
    # equate TW/TWO or merely compare numeric prefixes.
    if job is None:
        return resolved == ticker
    if not _same_saved_request(job, ticker, pipeline_sequence):
        return False
    snapshot = job.get("data_snapshot")
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except ValueError:
            return False
    if snapshot is not None and (not isinstance(snapshot, dict) or snapshot.get("ticker") != resolved):
        return False
    if resolved == ticker:
        return True
    if not isinstance(snapshot, dict) or snapshot.get("ticker") != resolved:
        return False
    from data_fetch.market_sources.ticker_resolver import get_market_data_provider
    provider = get_market_data_provider(ticker)
    return resolved in provider.ticker_candidates(ticker)


async def load_analysis_checkpoint_inputs(*, job_id, ticker, pipeline_sequence, settings):
    """Keep same-job input immutable; a new job has no matching checkpoint.

    Do not refreeze legacy inputs, touch source freshness or copy data into
    provider caches. Each mode retains its own temporal memory and input receipt.
    """
    inputs = {}
    job = get_job(job_id) or None
    if job is not None and not _same_saved_request(job, ticker, pipeline_sequence):
        raise AnalysisCheckpointInputError("續跑進度與原資料身分無法確認一致，請建立新的分析工作。")
    async with open_checkpointer(
        checkpoint_path=settings.checkpoint_path,
        checkpoint_backend=getattr(settings, "checkpoint_backend", "sqlite"),
        postgres_dsn=getattr(settings, "checkpoint_postgres_dsn", ""),
    ) as saver:
        for pipeline in pipeline_sequence:
            thread = f"{job_id}:{pipeline}"
            saved = await saver.aget_tuple({"configurable": {"thread_id": thread, "checkpoint_ns": ""}})
            if saved is None:
                continue
            config = saved.config.get("configurable", {})
            state = saved.checkpoint.get("channel_values", {})
            if (not isinstance(config, dict) or config.get("thread_id") != thread
                    or config.get("checkpoint_ns", "") != "" or not isinstance(state, dict)):
                raise AnalysisCheckpointInputError("續跑進度與原資料身分無法確認一致，請建立新的分析工作。")
            raw = state.get("raw_financial_data")
            data = raw.get("input") if isinstance(raw, dict) else None
            if (state.get("pipeline_id") != pipeline or not isinstance(data, dict) or not data
                    or state.get("ticker") != data.get("ticker")
                    or not _resolved_identity_matches(job, ticker, pipeline_sequence, data.get("ticker"))
                    or state.get("job_id") not in (None, job_id)):
                raise AnalysisCheckpointInputError("續跑進度與原資料身分無法確認一致，請建立新的分析工作。")
            inputs[pipeline] = copy_json(data)
    return inputs


def new_mode_input(data):
    """Derive an unstarted mode from the same source data, with a new receipt."""
    return copy_json({key: value for key, value in data.items() if key not in {
        "temporal_memory", "analysis_input_cutoff", "analysis_input_hash", "_analysis_input_evidence",
    }})
