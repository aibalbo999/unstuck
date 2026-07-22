"""Context digest generation tasks used before high-dependency agents."""

from __future__ import annotations

import json

from context_digest_payload import (
    _build_context_digest_prompt,
    _ensure_digest_payload_shape,
    _fallback_context_digest_payload,
    _normalize_digest_text,
)
from context_digest_runtime import (
    _agent_event_kwargs,
    _build_digest_generation_config,
    _context_digest_cache_key,
    _context_digest_model_sequence,
    _digest_input_hash,
    _get_cached_context_digest,
    _store_cached_context_digest,
)
from llm_client import (
    KeyRotator,
    describe_quota_or_rate_error,
    estimate_text_tokens,
    generate_content,
    generate_content_async,
    is_missing_model_error,
    is_quota_or_rate_error,
    response_text,
)
from runtime_events import emit_context_event, emit_context_event_async, emit_log, make_runtime_event


CONTEXT_DIGEST_TARGET_AGENTS = {4, 7, 14, 16, 19, 21}


def _generate_context_digest_content(api_key: str, model_id: str, prompt: str):
    return generate_content(api_key, model_id, prompt, _build_digest_generation_config())


async def _generate_context_digest_content_async(api_key: str, model_id: str, prompt: str):
    return await generate_content_async(api_key, model_id, prompt, _build_digest_generation_config())


def ensure_context_digest(agent_num: int, context: dict, rotator: KeyRotator, progress_callback=None):
    """Run a lightweight summarization agent before high-dependency agents."""
    if agent_num not in CONTEXT_DIGEST_TARGET_AGENTS:
        return
    digests = context.setdefault("context_digests", {})
    input_hash = _digest_input_hash(agent_num, context)
    digest_hash_map = context.setdefault("_digest_hash_map", {})
    cache_key = (int(agent_num), input_hash)
    if cache_key in digest_hash_map:
        digests[agent_num] = digest_hash_map[cache_key]
        return
    if agent_num in digests:
        return

    models = _context_digest_model_sequence()
    for model_id in models:
        persistent_cache_key = _context_digest_cache_key(agent_num, input_hash, model_id, context)
        cached_digest = _get_cached_context_digest(persistent_cache_key)
        if cached_digest is not None:
            digests[agent_num] = cached_digest
            digest_hash_map[cache_key] = cached_digest
            return

    prompt = _build_context_digest_prompt(agent_num, context)
    for model_id in models:
        persistent_cache_key = _context_digest_cache_key(agent_num, input_hash, model_id, context)
        try:
            emit_context_event(
                context,
                make_runtime_event(
                    "status",
                    **_agent_event_kwargs(
                        context,
                        agent_num,
                        model_id,
                        "context_digest_model_call",
                        f"Agent {agent_num} 前序摘要正在呼叫模型 {model_id}...",
                    ),
                ),
                progress_callback,
            )
            api_key = rotator.get_key(model_id, estimate_text_tokens(prompt, response_budget=4096))
            response = _generate_context_digest_content(api_key, model_id, prompt)
            digest = _normalize_digest_text(response_text(response), agent_num, context)
            digests[agent_num] = digest
            digest_hash_map[cache_key] = digest
            _store_cached_context_digest(persistent_cache_key, digest)
            emit_log(f"  🧾 Agent {agent_num} 前序提煉摘要完成。")
            emit_context_event(
                context,
                make_runtime_event(
                    "status",
                    **_agent_event_kwargs(
                        context,
                        agent_num,
                        model_id,
                        "context_digest_done",
                        f"Agent {agent_num} 前序提煉摘要完成。",
                    ),
                ),
                progress_callback,
            )
            return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                emit_context_event(
                    context,
                    make_runtime_event(
                        "status",
                        **_agent_event_kwargs(
                            context,
                            agent_num,
                            model_id,
                            "model_fallback",
                            f"Context digest 模型 {model_id} 不可用，嘗試備援模型。",
                            level="warning",
                        ),
                    ),
                    progress_callback,
                )
                continue
            if is_quota_or_rate_error(str(exc)):
                message = f"提煉 Agent 遇到配額限制，改用 fallback 摘要：{describe_quota_or_rate_error(exc)[:120]}"
                emit_log(f"  ⏭️  {message}")
                event = _agent_event_kwargs(context, agent_num, model_id, "context_digest_fallback", message, level="warning")
                event["metadata"] = {**event["metadata"], "error_kind": exc.__class__.__name__}
                emit_context_event(context, make_runtime_event("status", **event), progress_callback)
                break
            message = f"提煉 Agent 失敗，改用 fallback 摘要：{str(exc)[:120]}"
            emit_log(f"  ⚠️  {message}")
            event = _agent_event_kwargs(context, agent_num, model_id, "context_digest_fallback", message, level="warning")
            event["metadata"] = {**event["metadata"], "error_kind": exc.__class__.__name__}
            emit_context_event(context, make_runtime_event("status", **event), progress_callback)
            break

    fallback_digest = json.dumps(
        _fallback_context_digest_payload(agent_num, context, reason="提煉 Agent 呼叫失敗"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    digests[agent_num] = fallback_digest
    if models:
        _store_cached_context_digest(_context_digest_cache_key(agent_num, input_hash, models[0], context), fallback_digest)


async def ensure_context_digest_async(agent_num: int, context: dict, rotator: KeyRotator, progress_callback=None):
    """Async summarization agent before high-dependency agents."""
    if agent_num not in CONTEXT_DIGEST_TARGET_AGENTS:
        return
    digests = context.setdefault("context_digests", {})
    input_hash = _digest_input_hash(agent_num, context)
    digest_hash_map = context.setdefault("_digest_hash_map", {})
    cache_key = (int(agent_num), input_hash)
    if cache_key in digest_hash_map:
        digests[agent_num] = digest_hash_map[cache_key]
        return
    if agent_num in digests:
        return

    models = _context_digest_model_sequence()
    for model_id in models:
        persistent_cache_key = _context_digest_cache_key(agent_num, input_hash, model_id, context)
        cached_digest = _get_cached_context_digest(persistent_cache_key)
        if cached_digest is not None:
            digests[agent_num] = cached_digest
            digest_hash_map[cache_key] = cached_digest
            return

    prompt = _build_context_digest_prompt(agent_num, context)
    for model_id in models:
        persistent_cache_key = _context_digest_cache_key(agent_num, input_hash, model_id, context)
        try:
            await emit_context_event_async(
                context,
                make_runtime_event(
                    "status",
                    **_agent_event_kwargs(
                        context,
                        agent_num,
                        model_id,
                        "context_digest_model_call",
                        f"Agent {agent_num} 前序摘要正在呼叫模型 {model_id}...",
                    ),
                ),
                progress_callback,
            )
            api_key = await rotator.async_get_key(model_id, estimate_text_tokens(prompt, response_budget=4096))
            response = await _generate_context_digest_content_async(api_key, model_id, prompt)
            digest = _normalize_digest_text(response_text(response), agent_num, context)
            digests[agent_num] = digest
            digest_hash_map[cache_key] = digest
            _store_cached_context_digest(persistent_cache_key, digest)
            emit_log(f"  🧾 Agent {agent_num} 前序提煉摘要完成。")
            await emit_context_event_async(
                context,
                make_runtime_event(
                    "status",
                    **_agent_event_kwargs(
                        context,
                        agent_num,
                        model_id,
                        "context_digest_done",
                        f"Agent {agent_num} 前序提煉摘要完成。",
                    ),
                ),
                progress_callback,
            )
            return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                await emit_context_event_async(
                    context,
                    make_runtime_event(
                        "status",
                        **_agent_event_kwargs(
                            context,
                            agent_num,
                            model_id,
                            "model_fallback",
                            f"Context digest 模型 {model_id} 不可用，嘗試備援模型。",
                            level="warning",
                        ),
                    ),
                    progress_callback,
                )
                continue
            if is_quota_or_rate_error(str(exc)):
                message = f"提煉 Agent 遇到配額限制，改用 fallback 摘要：{describe_quota_or_rate_error(exc)[:120]}"
                emit_log(f"  ⏭️  {message}")
                event = _agent_event_kwargs(context, agent_num, model_id, "context_digest_fallback", message, level="warning")
                event["metadata"] = {**event["metadata"], "error_kind": exc.__class__.__name__}
                await emit_context_event_async(context, make_runtime_event("status", **event), progress_callback)
                break
            message = f"提煉 Agent 失敗，改用 fallback 摘要：{str(exc)[:120]}"
            emit_log(f"  ⚠️  {message}")
            event = _agent_event_kwargs(context, agent_num, model_id, "context_digest_fallback", message, level="warning")
            event["metadata"] = {**event["metadata"], "error_kind": exc.__class__.__name__}
            await emit_context_event_async(context, make_runtime_event("status", **event), progress_callback)
            break

    fallback_digest = json.dumps(
        _fallback_context_digest_payload(agent_num, context, reason="提煉 Agent 呼叫失敗"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    digests[agent_num] = fallback_digest
    if models:
        _store_cached_context_digest(_context_digest_cache_key(agent_num, input_hash, models[0], context), fallback_digest)
