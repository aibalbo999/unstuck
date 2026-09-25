"""One source-only repair of the final mode-D agent; never rerun upstream agents."""
from __future__ import annotations

import copy
import json
from trade_source_contract import allowed_source_refs
from trade_source_diagnostics import source_repair_feedback
from workflow_quality_drafts import checkpoint_unvalidated_draft
from .cancellation import raise_if_cancelled


async def repair_trade_sources(result, data, context, rotator, run_agent, *, validate_candidate=None):
    outputs = context.setdefault("structured_outputs", {})
    output = outputs.get(24, outputs.get("24", {}))
    assessment = output.get("source_assessment", {}) if isinstance(output, dict) else {}
    manifest = context.get("_trade_source_manifest") or {}
    has_evidence = any(allowed_source_refs(manifest.get("catalog", {})).values())
    if ((assessment.get("output_completion") or {}).get("status") == "local_fallback"
            or assessment.get("status") != "degraded" or assessment.get("repair_attempted")
            or not manifest.get("visible") or not has_evidence):
        return result

    await checkpoint_unvalidated_draft(24, result, context)
    original = copy.deepcopy(output)
    original_source_state = {key: copy.deepcopy(context[key]) for key in
        ("_trade_source_manifest", "_trade_completion_receipt") if key in context}

    def restore_original_source_state():
        for key in ("_trade_source_manifest", "_trade_completion_receipt"):
            context.pop(key, None)
        context.update(copy.deepcopy(original_source_state))
    previous = {key: context[key] for key in ("_audit_retry_instruction", "_trade_source_repair_attempted") if key in context}
    context["_trade_source_repair_attempted"] = True
    context["_audit_retry_instruction"] = (
        "只修復本次 Agent 24，不重寫前序分析。先檢查完整 trade-source 區塊與缺口：" +
        "；".join(str(x) for x in assessment.get("reason_codes", [])) +
        "。輸出完整 JSON，三組 source_refs 只能填本次區塊實際存在且支持相應主張的路徑。"
        "目前未通過的核心催化主張：" + json.dumps(str(original.get("core_catalyst") or "")[:1200], ensure_ascii=False) +
        "。逐項核對主張，不要保留沒有證據的敘述再把引用清空。"
        "法人主張需寫出主體、期間、觀測日、數值與單位，並引用同一 institutional_evidence record；不能只寫外資累積或法人買超。"
        "event_calendar 整個物件及 availability 不是催化引用；無已確認事件不等於市場没有事件。"
        "Neutral 也必須符合來源要求：可使用有來源的技術條件說明觀望，無法確認的其他主張保留為未知，不能當成事實。"
        "明示 observed_signal、observed_source_refs、event_catalyst、recheck_condition、financial_risk_flags 五欄，不可省略，未知用 null／空陣列。"
        "observed_signal 逐項寫可核驗現況且自有 observed_source_refs；recheck_condition 僅用『等待…後再重新評估』表達尚未發生條件。"
        "core_catalyst 僅複述 observed_signal 原文或完整重新評估條件；財務警示另欄，financial_risk_flags 模型輸出空陣列交由系統判定。"
        "event_catalyst 的描述、日期、結束日、時區與狀態須與同一完整事件來源一致，缺資料用 null，不把新聞日期變成事件日期。"
        "現況不得使用單一累計值推定連續買超；未來重新評估條件也不能取代現況的來源引用。"
        "若資料不支持原方向，保持 Neutral 並具體說明缺口與重新評估条件；不得填假引用或強迫Long/Short。"
        + source_repair_feedback(assessment, manifest, original)
    )
    try:
        raise_if_cancelled(context)
        outputs.pop(24, None)
        outputs.pop("24", None)
        candidate = await run_agent(24, data, context, rotator)
        accepted = outputs.get(24, outputs.get("24"))
        if not isinstance(accepted, dict):
            restore_original_source_state()
            original.setdefault("source_assessment", {})["repair_attempted"] = True
            outputs[24] = original
            return result
        accepted.setdefault("source_assessment", {})["repair_attempted"] = True
        if validate_candidate is not None:
            context.setdefault("blocking_issues", []).extend(
                f"Agent 24 source repair: {issue}" for issue in validate_candidate(candidate)
            )
        return candidate
    except BaseException:
        restore_original_source_state()
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
