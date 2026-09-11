"""Deprecated compatibility module for legacy agent runtime imports."""

from agent_catalog import AGENT_NAMES  # noqa: F401
from assistant_tasks import (  # noqa: F401
    CONTEXT_DIGEST_TARGET_AGENTS,
    _format_previous,
    ensure_context_digest,
    ensure_context_digest_async,
    ensure_tear_sheet_summary,
    ensure_tear_sheet_summary_async,
)
from config import AGENT_MODELS  # noqa: F401
from final_audit import run_final_report_audit  # noqa: F401
from structured_output_parser import parse_structured_data  # noqa: F401
from runtime_events import emit_log
from validators import (  # noqa: F401
    append_quality_warnings,
    sanitize_model_output,
    strip_generated_audit_sections,
    validate_analysis_output,
    validate_company_identity,
    validate_prompt_leakage,
)

from . import audit_repair as _audit_repair
from .audit_repair import *  # noqa: F401,F403
from .llm_calls import *  # noqa: F401,F403
from .prompt_config import *  # noqa: F401,F403
from .prompting import *  # noqa: F401,F403
from .routing import *  # noqa: F401,F403
from .single_agent import *  # noqa: F401,F403

_CANONICAL_REPAIR_AGENT_OUTPUT = _audit_repair._repair_agent_output


def _clear_agent_blocking_issues(context, agent_num):
    agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
    prefixes = (f"Agent {agent_num} ", f"Agent {agent_num}: ", f"{agent_name}: ")
    context["blocking_issues"] = [
        issue for issue in context.get("blocking_issues", [])
        if not str(issue).startswith(prefixes)
    ]
    if not context["blocking_issues"]:
        context.pop("blocking_issues", None)


def _repair_agent_output(agent_num, data, context, rotator, issues):
    previous = _audit_repair.run_single_agent
    _audit_repair.run_single_agent = run_single_agent
    try:
        return _CANONICAL_REPAIR_AGENT_OUTPUT(agent_num, data, context, rotator, issues)
    finally:
        _audit_repair.run_single_agent = previous


def attempt_final_audit_repair(context, audit, rotator):
    return _call_canonical_repair("attempt_final_audit_repair", context, audit, rotator)


def _summarize_audit_issues(audit, limit: int = 3) -> str:
    issues = [str(item) for item in (audit.get("critical", []) or [])[:limit]]
    return "；".join(issues) if issues else "無可列示異常"


def finalize_final_audit(context, rotator, max_repair_passes=FINAL_AUDIT_REPAIR_PASSES):
    return _call_canonical_repair("finalize_final_audit", context, rotator, max_repair_passes=max_repair_passes)


def _call_canonical_repair(name, *args, **kwargs):
    """Preserve legacy monkeypatch seams while sharing the atomic implementation."""
    overrides = {"_repair_agent_output": _repair_agent_output, "run_single_agent": run_single_agent,
                 "run_final_report_audit": run_final_report_audit, "parse_structured_data": parse_structured_data}
    previous = {key: getattr(_audit_repair, key) for key in overrides}
    try:
        for key, value in overrides.items():
            setattr(_audit_repair, key, value)
        result = getattr(_audit_repair, name)(*args, **kwargs)
        if args and isinstance(args[0], dict) and "audit_repair_log" in args[0]:
            args[0]["audit_repair_log"] = [str(item).replace(" 自動修復", " AI 修復") for item in args[0]["audit_repair_log"]]
        return result
    finally:
        for key, value in previous.items():
            setattr(_audit_repair, key, value)
