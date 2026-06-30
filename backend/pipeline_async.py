"""Async analysis pipeline compatibility wrapper backed by LangGraph."""

from __future__ import annotations

from agent_runtime import AnalysisPipelineRunner, AnalysisRequest
from analysis_types import AnalysisContext, StockData
from config import API_KEY_SETUP_MESSAGE, has_api_keys
from workflow_graph import run_analysis_workflow


async def run_analysis_pipeline_async(
    data: StockData,
    progress_callback=None,
    pipeline_id: str = "v1",
    cancel_check=None,
    thread_id: str | None = None,
    checkpointer=None,
    checkpoint_path: str | None = None,
) -> AnalysisContext:
    """Run the selected analysis pipeline through the durable graph runtime."""

    if not has_api_keys():
        raise RuntimeError(API_KEY_SETUP_MESSAGE)
    result = await AnalysisPipelineRunner().run_async(
        AnalysisRequest(
            data=data,
            progress_callback=progress_callback,
            pipeline_id=pipeline_id,
            cancel_check=cancel_check,
            thread_id=thread_id,
            checkpointer=checkpointer,
            checkpoint_path=checkpoint_path,
        )
    )
    return result.context
