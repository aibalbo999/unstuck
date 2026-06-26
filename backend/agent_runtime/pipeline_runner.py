"""Canonical analysis pipeline service."""

from __future__ import annotations

import time
from typing import Any

from .types import AnalysisRequest, AnalysisResult


def create_default_workflow_services(**kwargs):
    from workflow_graph import create_default_workflow_services as _create_services

    return _create_services(**kwargs)


async def run_analysis_workflow(**kwargs):
    from workflow_graph import run_analysis_workflow as _run_workflow

    return await _run_workflow(**kwargs)


def legacy_context_from_graph(*args: Any, **kwargs: Any):
    from workflow_graph import legacy_context_from_graph as _legacy_context_from_graph

    return _legacy_context_from_graph(*args, **kwargs)


class AnalysisPipelineRunner:
    async def run_async(self, request: AnalysisRequest) -> AnalysisResult:
        started = time.time()
        services = create_default_workflow_services(
            progress_callback=request.progress_callback,
            cancel_check=request.cancel_check,
        )
        initial_state = services.initialize(dict(request.data), request.pipeline_id)
        final_state = await run_analysis_workflow(
            initial_state=initial_state,
            pipeline_id=request.pipeline_id,
            services=services,
            checkpointer=request.checkpointer,
            thread_id=request.thread_id,
        )
        context = legacy_context_from_graph(final_state, services)
        duration_ms = max(0, int(round((time.time() - started) * 1000)))
        return AnalysisResult(
            context=context,
            pipeline_id=context.get("pipeline_id", request.pipeline_id),
            duration_ms=duration_ms,
            warnings=list(context.get("blocking_issues", []) or []),
        )


DEFAULT_ANALYSIS_PIPELINE_RUNNER = AnalysisPipelineRunner()
