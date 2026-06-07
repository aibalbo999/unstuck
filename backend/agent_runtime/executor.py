"""Canonical agent execution service."""

from __future__ import annotations

import time

from .routing import get_runtime_model_sequence
from .single_agent import run_single_agent_async
from .types import AgentExecutionResult, AgentRunRequest


class AgentExecutor:
    async def run_async(self, request: AgentRunRequest) -> AgentExecutionResult:
        started = time.time()
        model_sequence = get_runtime_model_sequence(request.agent_num, request.context)
        text = await run_single_agent_async(
            request.agent_num,
            request.data,
            request.context,
            request.rotator,
            max_retries=request.max_retries,
        )
        duration_ms = max(0, int(round((time.time() - started) * 1000)))
        structured = (request.context.get("structured_outputs", {}) or {}).get(request.agent_num)
        warnings = [
            warning for warning in (request.context.get("structured_quality_warnings", []) or [])
            if f"Agent {request.agent_num} " in str(warning)
        ]
        return AgentExecutionResult(
            agent_num=request.agent_num,
            text=text,
            structured_output=structured,
            model_id=model_sequence[0] if model_sequence else "",
            attempts=1,
            duration_ms=duration_ms,
            warnings=warnings,
        )

    def run(self, request: AgentRunRequest) -> AgentExecutionResult:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_async(request))
        raise RuntimeError("AgentExecutor.run() cannot run inside an active event loop; use run_async().")


DEFAULT_AGENT_EXECUTOR = AgentExecutor()
