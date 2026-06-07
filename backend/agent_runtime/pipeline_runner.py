"""Canonical analysis pipeline service."""

from __future__ import annotations

import time

from .types import AnalysisRequest, AnalysisResult


class AnalysisPipelineRunner:
    async def run_async(self, request: AnalysisRequest) -> AnalysisResult:
        started = time.time()
        from pipeline import run_analysis_pipeline_async

        context = await run_analysis_pipeline_async(
            request.data,
            progress_callback=request.progress_callback,
            pipeline_id=request.pipeline_id,
            cancel_check=request.cancel_check,
        )
        duration_ms = max(0, int(round((time.time() - started) * 1000)))
        return AnalysisResult(
            context=context,
            pipeline_id=context.get("pipeline_id", request.pipeline_id),
            duration_ms=duration_ms,
            warnings=list(context.get("blocking_issues", []) or []),
        )


DEFAULT_ANALYSIS_PIPELINE_RUNNER = AnalysisPipelineRunner()
