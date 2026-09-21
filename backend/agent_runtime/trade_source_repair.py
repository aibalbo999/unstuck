"""One source-only repair of the final mode-D agent; never rerun upstream agents."""
from __future__ import annotations

import copy
from workflow_quality_drafts import checkpoint_unvalidated_draft
from .cancellation import raise_if_cancelled


async def repair_trade_sources(result, data, context, rotator, run_agent):
    outputs = context.setdefault("structured_outputs", {})
    output = outputs.get(24, outputs.get("24", {}))
    assessment = output.get("source_assessment", {}) if isinstance(output, dict) else {}
    manifest = context.get("_trade_source_manifest") or {}
    source = manifest.get("catalog", {}).get("short_term_market_context", {})
    technical = source.get("technical_indicators") or {}
    events = source.get("event_calendar") or {}
    has_evidence = technical.get("availability") in {"available", "partial"} or bool(events.get("events"))
    if (assessment.get("status") != "degraded" or assessment.get("repair_attempted")
            or not manifest.get("visible") or not has_evidence):
        return result

    await checkpoint_unvalidated_draft(24, result, context)
    original = copy.deepcopy(output)
    previous = {key: context[key] for key in ("_audit_retry_instruction", "_trade_source_repair_attempted") if key in context}
    context["_trade_source_repair_attempted"] = True
    context["_audit_retry_instruction"] = (
        "只修復本次 Agent 24，不重寫前序分析。先檢查完整 trade-source 區塊與缺口：" +
        "；".join(str(x) for x in assessment.get("reason_codes", [])) +
        "。輸出完整 JSON，三組 source_refs 只能填本次區塊實際存在且支持相應主張的路徑。"
        "若資料不支持原方向，保持 Neutral 並具體說明缺口與重新評估条件；不得填假引用或強迫Long/Short。"
    )
    try:
        raise_if_cancelled(context)
        outputs.pop(24, None)
        outputs.pop("24", None)
        candidate = await run_agent(24, data, context, rotator)
        accepted = outputs.get(24, outputs.get("24"))
        if not isinstance(accepted, dict):
            original.setdefault("source_assessment", {})["repair_attempted"] = True
            outputs[24] = original
            return result
        accepted.setdefault("source_assessment", {})["repair_attempted"] = True
        return candidate
    except BaseException:
        outputs.pop(24, None)
        outputs.pop("24", None)
        outputs[24] = original
        raise
    finally:
        for key in ("_audit_retry_instruction", "_trade_source_repair_attempted"):
            if key in previous:
                context[key] = previous[key]
            else:
                context.pop(key, None)
