"""Deprecated agent runtime module alias.

New code should use agent_runtime.AgentExecutor and agent_runtime.AnalysisPipelineRunner.
"""

from __future__ import annotations

import sys
import warnings

from agent_runtime import legacy_agent_runner as _legacy
from agent_runtime.executor import AgentExecutor
from agent_runtime.pipeline_runner import AnalysisPipelineRunner
from agent_runtime.types import AgentExecutionResult, AgentRunRequest, AnalysisRequest, AnalysisResult

_legacy.AgentExecutionResult = AgentExecutionResult
_legacy.AgentExecutor = AgentExecutor
_legacy.AgentRunRequest = AgentRunRequest
_legacy.AnalysisPipelineRunner = AnalysisPipelineRunner
_legacy.AnalysisRequest = AnalysisRequest
_legacy.AnalysisResult = AnalysisResult


def _deprecated_function(name, func):
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"agent_runner.{name} is deprecated; use agent_runtime typed services/modules instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return func(*args, **kwargs)

    wrapper.__name__ = getattr(func, "__name__", name)
    wrapper.__doc__ = getattr(func, "__doc__", None)
    return wrapper


for _name in (
    "get_agent_model_sequence",
    "get_audit_model_sequence",
    "get_context_digest_model_sequence",
    "get_runtime_model_sequence",
    "build_generation_config",
    "build_prompt",
    "run_single_agent",
    "run_single_agent_async",
    "run_analysis_pipeline",
    "run_analysis_pipeline_async",
    "attempt_final_audit_repair",
    "attempt_final_audit_repair_async",
    "finalize_final_audit",
    "finalize_final_audit_async",
):
    if hasattr(_legacy, _name):
        setattr(_legacy, _name, _deprecated_function(_name, getattr(_legacy, _name)))

sys.modules[__name__] = _legacy
