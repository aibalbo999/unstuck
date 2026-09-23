"""Keep source-absence repairs deterministic inside the existing transaction."""
from __future__ import annotations

import functools
import inspect

from validators import strip_generated_audit_sections, validate_analysis_output, validate_company_identity, validate_prompt_leakage
from .cancellation import raise_if_cancelled
from .deterministic_fallbacks import _clear_agent_blocking_issues
from .deterministic_skips import deterministic_agent_result
from .repair_candidates import validate_repair_candidate
from .repair_state import adopt_repair_result, repair_contract_issues
from .repair_transaction import preserve_failed_repair


def _repair_absent_source(agent_num, data, context):
    raise_if_cancelled(context)
    result = deterministic_agent_result(agent_num, data, context)
    if result is None:
        return None
    fatal, issues = validate_repair_candidate(agent_num, result, data, context,
        validators=(validate_prompt_leakage, validate_company_identity, validate_analysis_output),
        contract=repair_contract_issues)
    if fatal or issues:
        return False, "資料不足候選未通過品質檢查：" + "；".join(fatal or issues)
    context.setdefault("analyses", {})[agent_num] = strip_generated_audit_sections(result)
    _clear_agent_blocking_issues(context, agent_num)
    return adopt_repair_result(agent_num, context, (True, "缺少法說會逐字稿，保留不可評估結果並略過模型呼叫"))


def source_aware_repair(function):
    """Reuse the ordinary provider repair when its required source is present."""
    if inspect.iscoroutinefunction(function):
        @functools.wraps(function)
        async def asynchronous(agent, data, context, *args, **kwargs):
            result = _repair_absent_source(agent, data, context)
            if result is not None:
                return result
            return await function(agent, data, context, *args, **kwargs)
        return preserve_failed_repair(asynchronous)

    @functools.wraps(function)
    def synchronous(agent, data, context, *args, **kwargs):
        result = _repair_absent_source(agent, data, context)
        if result is not None:
            return result
        return function(agent, data, context, *args, **kwargs)
    return preserve_failed_repair(synchronous)
