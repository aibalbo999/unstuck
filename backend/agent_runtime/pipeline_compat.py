# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

from analysis_types import AnalysisContext, StockData


def run_analysis_pipeline(data: StockData, progress_callback=None, pipeline_id: str = "v1") -> AnalysisContext:
    """Compatibility wrapper; orchestration lives in pipeline.py."""
    from pipeline import run_analysis_pipeline as _run_analysis_pipeline

    return _run_analysis_pipeline(data, progress_callback=progress_callback, pipeline_id=pipeline_id)


async def run_analysis_pipeline_async(
    data: StockData,
    progress_callback=None,
    pipeline_id: str = "v1",
) -> AnalysisContext:
    """Compatibility wrapper; async DAG orchestration lives in pipeline.py."""
    from pipeline import run_analysis_pipeline_async as _run_analysis_pipeline_async

    return await _run_analysis_pipeline_async(
        data,
        progress_callback=progress_callback,
        pipeline_id=pipeline_id,
    )
