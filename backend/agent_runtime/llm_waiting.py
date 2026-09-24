"""Keep provider response waits separate from bounded, cancellable key waits."""
import asyncio
import math

from config import LLM_AGENT_CALL_TIMEOUT_SECONDS, LLM_KEY_ADMISSION_TIMEOUT_SECONDS
from llm_key_admission import key_admission_scope
from .cancellation import CANCEL_CHECK_CONTEXT_KEY
from .retry_policy import AgentTransientError


def key_admission_timeout(timeout=None):
    """Keep unsent waits bounded, even when generation has no finite deadline."""
    admission = float(LLM_KEY_ADMISSION_TIMEOUT_SECONDS)
    if not math.isfinite(admission) or admission <= 0:
        admission = 15.0
    generation = float(LLM_AGENT_CALL_TIMEOUT_SECONDS if timeout is None else timeout)
    return min(admission, generation) if math.isfinite(generation) and generation > 0 else admission


def _scope(context, model, timeout):
    return key_admission_scope(
        model, key_admission_timeout(timeout),
        context.get(CANCEL_CHECK_CONTEXT_KEY),
    )


def acquire_key(rotator, model, tokens, context, timeout, **budget):
    with _scope(context, model, timeout):
        return rotator.get_key(model, tokens, **budget)


async def acquire_key_async(rotator, model, tokens, context, timeout, **budget):
    with _scope(context, model, timeout):
        return await rotator.async_get_key(model, tokens, **budget)


async def await_response(coro, *, model_id, timeout):
    if timeout <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise AgentTransientError(f"LLM timeout after {timeout:.1f}s for model {model_id}") from exc
