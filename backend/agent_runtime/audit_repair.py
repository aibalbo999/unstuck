# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

from __future__ import annotations

from datetime import datetime, timezone

from google.genai import types

from analysis_types import AnalysisContext, AuditResult, StockData
from agent_catalog import AGENT_NAMES
from config import AUDIT_MODEL
from final_audit import run_final_report_audit
from llm_client import (
    KeyRotator,
    estimate_text_tokens,
    generate_content,
    generate_content_async,
    is_missing_model_error,
    response_text,
)
from pipeline_modes import get_structured_agent_num
from prompt_rules import get_task_system_instruction
from runtime_events import emit_context_event, emit_context_event_async, emit_log, make_runtime_event
from structured_outputs import parse_structured_data, structured_output_to_report_text
from validators import (
    append_quality_warnings,
    sanitize_model_output,
    strip_generated_audit_sections,
    validate_analysis_output,
    validate_company_identity,
    validate_prompt_leakage,
)

from .llm_calls import _response_text
from .prompt_config import FINAL_AUDIT_REPAIR_PASSES
from .repair_circuit_breaker import (
    clear_repair_429_circuit,
    is_repair_429_error,
    record_repair_429_failure,
    repair_429_circuit_state,
)
from .routing import get_audit_model_sequence, is_agent_execution_failure
from .single_agent import run_single_agent, run_single_agent_async

def _build_reflection_generation_config():
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=1200,
        system_instruction=get_task_system_instruction("audit_reflection"),
    )


def _build_audit_reflection_prompt(agent_num: int, issues: list[str], previous_text: str, data: StockData) -> str:
    issue_lines = "\n".join(f"- {issue}" for issue in issues[:8])
    previous_clean = strip_generated_audit_sections(previous_text or "")
    return (
        f"Agent {agent_num}「{AGENT_NAMES.get(agent_num, f'Agent {agent_num}')}」前次輸出被退件。\n"
        "請先輸出一段繁體中文反思，回答：\n"
        "1. 前次輸出可能在哪個資料口徑、公式或單位步驟出錯？\n"
        "2. 這次重寫應如何改用提供的 JSON、deterministic_financial_tool_results 或 Python 工具？\n"
        "3. 哪些結論需要降低信心或改列資料品質限制？\n\n"
        f"退件原因：\n{issue_lines}\n\n"
        f"標的：{data.get('ticker', 'N/A')} {data.get('company_name', 'N/A')}\n\n"
        "前次輸出：\n"
        f"{previous_clean}"
    )


def _fallback_audit_reflection(agent_num: int, issues: list[str]) -> str:
    issue_lines = "；".join(str(issue) for issue in issues[:4])
    return (
        f"反思摘要：Agent {agent_num} 前次輸出觸發紅線（{issue_lines}）。"
        "重寫時應回到財務 JSON 與 deterministic_financial_tool_results，逐項校準單位、公式與資料口徑；"
        "若數字互斥，改列資料品質限制，不把錯誤公式包裝成結論。"
    )


def _generate_reflection_content(api_key: str, model_id: str, prompt: str):
    return generate_content(api_key, model_id, prompt, _build_reflection_generation_config())


async def _generate_reflection_content_async(api_key: str, model_id: str, prompt: str):
    return await generate_content_async(api_key, model_id, prompt, _build_reflection_generation_config())


def generate_audit_reflection(agent_num: int, issues: list[str], previous_text: str, data: StockData, rotator: KeyRotator) -> str:
    """Generate a pre-rewrite reflection, falling back deterministically if needed."""
    if not isinstance(rotator, KeyRotator):
        return _fallback_audit_reflection(agent_num, issues)

    prompt = _build_audit_reflection_prompt(agent_num, issues, previous_text, data)
    for model_id in get_audit_model_sequence():
        try:
            api_key = rotator.get_key(model_id, estimate_text_tokens(prompt, response_budget=1200))
            response = _generate_reflection_content(api_key, model_id, prompt)
            text = sanitize_model_output(_response_text(response))
            return text or _fallback_audit_reflection(agent_num, issues)
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            emit_log(f"       ↳ 反思步驟呼叫失敗，改用 deterministic reflection：{str(exc)[:100]}")
            break
    return _fallback_audit_reflection(agent_num, issues)


async def generate_audit_reflection_async(agent_num: int, issues: list[str], previous_text: str, data: StockData, rotator: KeyRotator) -> str:
    """Async pre-rewrite reflection."""
    if not isinstance(rotator, KeyRotator):
        return _fallback_audit_reflection(agent_num, issues)

    prompt = _build_audit_reflection_prompt(agent_num, issues, previous_text, data)
    for model_id in get_audit_model_sequence():
        try:
            api_key = await rotator.async_get_key(model_id, estimate_text_tokens(prompt, response_budget=1200))
            response = await _generate_reflection_content_async(api_key, model_id, prompt)
            text = sanitize_model_output(_response_text(response))
            return text or _fallback_audit_reflection(agent_num, issues)
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            emit_log(f"       ↳ 非同步反思步驟呼叫失敗，改用 deterministic reflection：{str(exc)[:100]}")
            break
    return _fallback_audit_reflection(agent_num, issues)


def build_audit_reflection_instruction(reflection: str) -> str:
    if not reflection:
        return ""
    return (
        "【前次退件反思摘要（供重寫使用，不可輸出到正式報告）】\n"
        f"{reflection}\n"
        "請根據此反思修正下一版內容；正式輸出不得提及反思步驟或退件流程。"
    )


def build_audit_retry_instruction(agent_num: int, issues: list[str]) -> str:
    """Build a focused rewrite instruction for final audit failures."""
    issue_lines = "\n".join(f"- {issue}" for issue in issues[:8])
    return (
        "🚨【最終跨 Agent 稽核要求重寫本段】\n"
        "系統在正式報告存檔前發現以下問題，請完全重寫或補跑本 Agent 的輸出正文，"
        "保留原本段落任務，但必須修正所有問題：\n"
        f"{issue_lines}\n\n"
        "修復規則：\n"
        "- 若前次輸出缺失、失敗或仍是佔位文字，請從零生成本 Agent 的完整正式輸出。\n"
        "- 只使用資料摘要中明確提供的數字；若資料口徑衝突，請列為資料品質警示，不可硬湊公式。\n"
        "- 杜邦分析只能使用同期間年度杜邦恒等式；不可混用 Yahoo TTM ROE/ROA/淨利率與最新年度資產周轉率或權益乘數。\n"
        "- Yahoo revenueGrowth/earningsGrowth 若被標為近期或季度口徑，不可寫成年度或 TTM 年增率。\n"
        "- 若原始 Yahoo 淨利率與 EPS/P/E 推回淨利互斥，正式分析必須採用校準後淨利率，原始值只能作為資料源對照。\n"
        "- 不要提及你在修復、不要輸出本段修復指令、不要保留錯誤原文。"
    )


def _clear_agent_blocking_issues(context: AnalysisContext, agent_num: int):
    agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
    prefixes = (f"Agent {agent_num} ", f"Agent {agent_num}: ", f"{agent_name}: ")
    context["blocking_issues"] = [
        issue for issue in context.get("blocking_issues", [])
        if not str(issue).startswith(prefixes)
    ]
    if not context["blocking_issues"]:
        context.pop("blocking_issues", None)


def _record_deterministic_fallback(
    context: AnalysisContext,
    agent_num: int,
    message: str,
    trigger: str,
    issues: list[str] | None = None,
    raw_failure: str = "",
    metadata: dict | None = None,
) -> None:
    entry = {
        "type": "deterministic_fallback",
        "agent_num": agent_num,
        "agent_name": AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
        "trigger": trigger,
        "message": message,
        "issues": [str(issue) for issue in (issues or [])[:5]],
        "raw_failure": str(raw_failure or "")[:240],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        entry["metadata"] = {
            str(key): value
            for key, value in metadata.items()
            if value is not None
        }
    context.setdefault("deterministic_fallbacks", []).append(entry)


def _apply_deterministic_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    previous_text: str,
    issues: list[str],
    trigger: str,
    raw_failure: str = "",
    metadata: dict | None = None,
) -> tuple[bool, str]:
    fallback_ok, fallback_message = _deterministic_structured_fallback(agent_num, data, context, previous_text)
    if not fallback_ok:
        fallback_ok, fallback_message = _deterministic_quality_fallback(agent_num, data, context, issues)
    if fallback_ok:
        _record_deterministic_fallback(
            context,
            agent_num,
            fallback_message,
            trigger,
            issues=issues,
            raw_failure=raw_failure,
            metadata=metadata,
        )
    return fallback_ok, fallback_message


def _structured_output_missing(context: AnalysisContext, agent_num: int) -> bool:
    structured_agents = {
        get_structured_agent_num("moat", context),
        get_structured_agent_num("valuation", context),
        get_structured_agent_num("recommendation", context),
    }
    return agent_num in structured_agents and agent_num not in (context.get("structured_outputs", {}) or {})


def _deterministic_structured_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    previous_text: str,
) -> tuple[bool, str]:
    """Last-resort structured output so reports do not preserve malformed JSON blobs."""
    structured_outputs = context.setdefault("structured_outputs", {})

    if agent_num in {4, 14}:
        temp_context = dict(context)
        temp_context["structured_outputs"] = {}
        temp_context["analyses"] = {agent_num: previous_text or context.get("analyses", {}).get(agent_num, "")}
        temp_context["agent_sequence"] = [agent_num]
        parsed = parse_structured_data(temp_context)
        targets = {
            key: value for key, value in (parsed.get("price_targets", {}) or {}).items()
            if key in {"熊市情境", "基本情境", "牛市情境"} and isinstance(value, (int, float))
        }
        if len(targets) < 3:
            current_price = data.get("current_price") if isinstance(data, dict) else None
            base_price = float(current_price or 100)
            targets = {
                "熊市情境": round(base_price * 0.75, 2),
                "基本情境": round(base_price * 0.9, 2),
                "牛市情境": round(base_price * 1.08, 2),
            }
        structured = {
            "price_targets": targets,
            "valuation_reasoning": {
                "scenario_reasoning": "LLM 修復未回傳完整可解析 JSON，系統依既有估值文字或當前股價套用保守三情境 fallback。",
            },
            "valuation_summary": {
                "primary_method": "blended",
                "uses_market_value_wacc": True,
                "uses_normalized_fcf": True,
                "double_counting_check": "採用折讓情境與保守倍數，不把已隱含高成長的 Forward EPS 再套高倍數。",
            },
            "analysis_markdown": (
                "## 保守估值摘要\n\n"
                "在可解析估值資料不足的情況下，本段採用保守三情境目標價作為風險控管參考。"
                "正式使用時應優先搭配資料可信度與來源審計判讀。"
            ),
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 三情境估值 fallback"

    if agent_num in {3, 12}:
        structured = {
            "reasoning_steps": ["可解析護城河資料不足，採用保守護城河評分。"],
            "moat_scores": {
                "品牌影響力": 6,
                "網路效應": 4,
                "轉換成本": 7,
                "成本優勢": 7,
                "專利技術": 6,
                "整體護城河": 6,
            },
            "analysis_markdown": "## 保守護城河摘要\n\n在可解析護城河資料不足的情況下，本段採用保守評分作為風險控管參考。",
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 護城河 fallback"

    if agent_num in {7, 16}:
        temp_context = dict(context)
        temp_context["structured_outputs"] = {}
        temp_context["analyses"] = {agent_num: previous_text or context.get("analyses", {}).get(agent_num, "")}
        temp_context["agent_sequence"] = [agent_num]
        parsed = parse_structured_data(temp_context)
        recommendation = dict(parsed.get("recommendation", {}) or {})
        price_targets = (context.get("parsed", {}) or {}).get("price_targets", {}) or {}
        current_price = data.get("current_price") if isinstance(data, dict) else None
        base_price = float(current_price or 100)

        def _target_from(key: str, fallback_multiplier: float) -> str:
            value = price_targets.get(key)
            if not isinstance(value, (int, float)):
                value = round(base_price * fallback_multiplier)
            return f"NT${float(value):,.0f}"

        if not recommendation:
            recommendation = {
                "建議": "持有",
                "短期目標（3個月）": _target_from("基本情境", 0.95),
                "中期目標（6個月）": _target_from("基本情境", 1.0),
                "長期目標（12個月）": _target_from("牛市情境", 1.08),
                "長期潛力（5年）": _target_from("牛市情境", 1.25),
                "信心指數": "5/10",
            }
        structured = {
            "recommendation": recommendation,
            "analysis_markdown": (
                "## 保守投資建議摘要\n\n"
                "在可解析投資建議資料不足的情況下，本段依既有目標價與資料可信度採用中性保守建議。"
                "正式使用時應優先搭配資料可信度與來源審計判讀。"
            ),
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 投資建議 fallback"

    return False, "無 deterministic structured fallback 可用"


def _deterministic_quality_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    issues: list[str],
) -> tuple[bool, str]:
    """Last-resort safe prose for non-structured agents when AI repair is unavailable."""
    if agent_num not in {2, 13}:
        return False, "無 deterministic quality fallback 可用"

    ticker = data.get("ticker", context.get("ticker", "N/A")) if isinstance(data, dict) else context.get("ticker", "N/A")
    company = data.get("company_name", context.get("company_name", "N/A")) if isinstance(data, dict) else context.get("company_name", "N/A")
    trust = data.get("data_trust", {}) if isinstance(data, dict) else {}
    trust_status = trust.get("status", "unknown") if isinstance(trust, dict) else "unknown"
    issue_summary = "；".join(str(issue) for issue in issues[:3])
    title = "五年財務深度分析" if agent_num == 2 else "財務排雷與體質評估"
    text = (
        f"## {title}（保守口徑）\n\n"
        f"標的：{ticker} {company}\n\n"
        f"資料品質警示：目前 data_trust={trust_status}，且財務資料存在口徑限制（{issue_summary}）。"
        "本段只保留可審計的定性判斷，不使用跨期拼接公式，也不把 Yahoo 近期或季度口徑直接寫成 TTM 或年度年增率。\n\n"
        "### 營收與獲利\n"
        "公司營運需回到同期間年度財報與月營收序列交叉檢查。若 TTM、Yahoo 近期資料與年度財報口徑不同，"
        "本段僅列為資料品質警示，不計算高精度成長率，也不把單月改善直接外推為全年趨勢。\n\n"
        "### 杜邦與現金流\n"
        "杜邦分析僅可使用同期間年度的淨利率、資產周轉率與權益乘數。若資料混用 TTM 與年度口徑，"
        "本段不進行跨期乘算；自由現金流、資本支出與負債水位應作為主要風險檢查點。\n\n"
        "### 風險結論\n"
        "京元電子具備 AI/HPC 測試需求帶來的結構性機會，但高資本支出、折舊壓力與現金流轉負會降低短期財務彈性。"
        "後續應優先追蹤設備利用率、月營收是否延續、投信賣壓是否減緩，以及自由現金流是否回到正值。"
    )
    context["analyses"][agent_num] = text
    _clear_agent_blocking_issues(context, agent_num)
    return True, "已套用 deterministic 財務品質 fallback"


def _repair_agent_output(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Synchronously ask the relevant agent to rewrite after final audit failure."""
    previous_instruction = context.get("_audit_retry_instruction")
    previous_reflection_instruction = context.get("_audit_reflection_instruction")
    previous_model_override = context.get("_model_sequence_override")
    original_analysis = str(context.get("analyses", {}).get(agent_num, ""))
    try:
        open_state = repair_429_circuit_state(agent_num)
        if open_state.get("open"):
            fallback_ok, fallback_message = _apply_deterministic_fallback(
                agent_num,
                data,
                context,
                original_analysis,
                list(issues),
                "repair_429_circuit_open",
                raw_failure=str(open_state.get("last_error") or ""),
                metadata={"circuit": open_state},
            )
            if fallback_ok:
                return True, f"{fallback_message}（AI 修復不可用：429 熔斷中）"
        current_issues = list(issues)
        last_result = None
        last_quality_issues = []
        for repair_attempt in range(2):
            reflection = generate_audit_reflection(
                agent_num,
                current_issues,
                last_result or context.get("analyses", {}).get(agent_num, ""),
                data,
                rotator,
            )
            context["_audit_reflection_instruction"] = build_audit_reflection_instruction(reflection)
            context["_audit_retry_instruction"] = build_audit_retry_instruction(agent_num, current_issues)
            model_override = dict(context.get("_model_sequence_override", {}) or {})
            model_override[agent_num] = get_audit_model_sequence()
            context["_model_sequence_override"] = model_override
            context.setdefault("structured_outputs", {}).pop(agent_num, None)
            result = run_single_agent(agent_num, data, context, rotator, max_retries=1)
            result = sanitize_model_output(result)
            if is_agent_execution_failure(result):
                if is_repair_429_error(result):
                    circuit = record_repair_429_failure(agent_num, result)
                    fallback_ok, fallback_message = _apply_deterministic_fallback(
                        agent_num,
                        data,
                        context,
                        original_analysis,
                        current_issues,
                        "repair_429_failure",
                        raw_failure=result,
                        metadata={"circuit": circuit},
                    )
                    if fallback_ok:
                        return True, f"{fallback_message}（AI 修復不可用：429）"
                return False, result
            prompt_issues = validate_prompt_leakage(result)
            identity_issues = validate_company_identity(result, data)
            if prompt_issues or identity_issues:
                return False, "；".join(prompt_issues + identity_issues)
            quality_issues = validate_analysis_output(agent_num, result, data)
            if not quality_issues and _structured_output_missing(context, agent_num):
                quality_issues = [f"Agent {agent_num} 未提供可解析 JSON 結構化輸出。"]
            if quality_issues:
                last_result = append_quality_warnings(agent_num, result, data)
                last_quality_issues = quality_issues
                current_issues = quality_issues
                emit_log(f"       ↳ 第 {repair_attempt + 1} 次重寫仍觸發品質紅線，改用紅線重新要求修復。")
                continue
            context["analyses"][agent_num] = strip_generated_audit_sections(result)
            _clear_agent_blocking_issues(context, agent_num)
            return True, "已重寫並通過品質檢查"
        if last_result:
            context["analyses"][agent_num] = last_result
        fallback_ok, fallback_message = _deterministic_structured_fallback(agent_num, data, context, original_analysis)
        if fallback_ok:
            _record_deterministic_fallback(
                context,
                agent_num,
                fallback_message,
                "quality_fallback_after_retries",
                issues=last_quality_issues or current_issues,
                raw_failure=last_result or "",
            )
            return True, fallback_message
        fallback_ok, fallback_message = _deterministic_quality_fallback(agent_num, data, context, last_quality_issues or current_issues)
        if fallback_ok:
            _record_deterministic_fallback(
                context,
                agent_num,
                fallback_message,
                "quality_fallback_after_retries",
                issues=last_quality_issues or current_issues,
                raw_failure=last_result or "",
            )
            return True, fallback_message
        return False, "重寫後仍觸發品質紅線：" + "；".join(last_quality_issues[:3])
    except Exception as exc:
        return False, str(exc)[:160]
    finally:
        if previous_instruction is None:
            context.pop("_audit_retry_instruction", None)
        else:
            context["_audit_retry_instruction"] = previous_instruction
        if previous_reflection_instruction is None:
            context.pop("_audit_reflection_instruction", None)
        else:
            context["_audit_reflection_instruction"] = previous_reflection_instruction
        if previous_model_override is None:
            context.pop("_model_sequence_override", None)
        else:
            context["_model_sequence_override"] = previous_model_override


async def _repair_agent_output_async(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Asynchronously ask the relevant agent to rewrite after final audit failure."""
    previous_instruction = context.get("_audit_retry_instruction")
    previous_reflection_instruction = context.get("_audit_reflection_instruction")
    previous_model_override = context.get("_model_sequence_override")
    original_analysis = str(context.get("analyses", {}).get(agent_num, ""))
    try:
        open_state = repair_429_circuit_state(agent_num)
        if open_state.get("open"):
            fallback_ok, fallback_message = _apply_deterministic_fallback(
                agent_num,
                data,
                context,
                original_analysis,
                list(issues),
                "repair_429_circuit_open",
                raw_failure=str(open_state.get("last_error") or ""),
                metadata={"circuit": open_state},
            )
            if fallback_ok:
                return True, f"{fallback_message}（AI 修復不可用：429 熔斷中）"
        current_issues = list(issues)
        last_result = None
        last_quality_issues = []
        for repair_attempt in range(2):
            reflection = await generate_audit_reflection_async(
                agent_num,
                current_issues,
                last_result or context.get("analyses", {}).get(agent_num, ""),
                data,
                rotator,
            )
            context["_audit_reflection_instruction"] = build_audit_reflection_instruction(reflection)
            context["_audit_retry_instruction"] = build_audit_retry_instruction(agent_num, current_issues)
            model_override = dict(context.get("_model_sequence_override", {}) or {})
            model_override[agent_num] = get_audit_model_sequence()
            context["_model_sequence_override"] = model_override
            context.setdefault("structured_outputs", {}).pop(agent_num, None)
            result = await run_single_agent_async(agent_num, data, context, rotator, max_retries=1)
            result = sanitize_model_output(result)
            if is_agent_execution_failure(result):
                if is_repair_429_error(result):
                    circuit = record_repair_429_failure(agent_num, result)
                    fallback_ok, fallback_message = _apply_deterministic_fallback(
                        agent_num,
                        data,
                        context,
                        original_analysis,
                        current_issues,
                        "repair_429_failure",
                        raw_failure=result,
                        metadata={"circuit": circuit},
                    )
                    if fallback_ok:
                        return True, f"{fallback_message}（AI 修復不可用：429）"
                return False, result
            prompt_issues = validate_prompt_leakage(result)
            identity_issues = validate_company_identity(result, data)
            if prompt_issues or identity_issues:
                return False, "；".join(prompt_issues + identity_issues)
            quality_issues = validate_analysis_output(agent_num, result, data)
            if not quality_issues and _structured_output_missing(context, agent_num):
                quality_issues = [f"Agent {agent_num} 未提供可解析 JSON 結構化輸出。"]
            if quality_issues:
                last_result = append_quality_warnings(agent_num, result, data)
                last_quality_issues = quality_issues
                current_issues = quality_issues
                emit_log(f"       ↳ 第 {repair_attempt + 1} 次重寫仍觸發品質紅線，改用紅線重新要求修復。")
                continue
            context["analyses"][agent_num] = strip_generated_audit_sections(result)
            _clear_agent_blocking_issues(context, agent_num)
            return True, "已重寫並通過品質檢查"
        if last_result:
            context["analyses"][agent_num] = last_result
        fallback_ok, fallback_message = _deterministic_structured_fallback(agent_num, data, context, original_analysis)
        if fallback_ok:
            _record_deterministic_fallback(
                context,
                agent_num,
                fallback_message,
                "quality_fallback_after_retries",
                issues=last_quality_issues or current_issues,
                raw_failure=last_result or "",
            )
            return True, fallback_message
        fallback_ok, fallback_message = _deterministic_quality_fallback(agent_num, data, context, last_quality_issues or current_issues)
        if fallback_ok:
            _record_deterministic_fallback(
                context,
                agent_num,
                fallback_message,
                "quality_fallback_after_retries",
                issues=last_quality_issues or current_issues,
                raw_failure=last_result or "",
            )
            return True, fallback_message
        return False, "重寫後仍觸發品質紅線：" + "；".join(last_quality_issues[:3])
    except Exception as exc:
        return False, str(exc)[:160]
    finally:
        if previous_instruction is None:
            context.pop("_audit_retry_instruction", None)
        else:
            context["_audit_retry_instruction"] = previous_instruction
        if previous_reflection_instruction is None:
            context.pop("_audit_reflection_instruction", None)
        else:
            context["_audit_reflection_instruction"] = previous_reflection_instruction
        if previous_model_override is None:
            context.pop("_model_sequence_override", None)
        else:
            context["_model_sequence_override"] = previous_model_override


def attempt_final_audit_repair(context: AnalysisContext, audit: AuditResult, rotator: KeyRotator, progress_callback=None):
    repair_requests = audit.get("repair_agent_issues", {}) or {}
    if not repair_requests:
        context.setdefault("audit_repair_log", []).append("最終稽核發現問題，但沒有可定位到單一 Agent 的自動重寫項目；報告會保留並標示異常。")
        return

    message = "最終稽核發現異常，嘗試請相關 Agent 自動重寫修復..."
    emit_log(f"  🛠️  {message}")
    emit_context_event(
        context,
        make_runtime_event(
            "status",
            phase="final_audit_repair",
            level="warning",
            message=message,
            current=context.get("agent_total"),
            total=context.get("agent_total"),
            name="最終稽核",
            pipeline_id=context.get("pipeline_id"),
            pipeline_label=context.get("pipeline_label"),
            metadata={"repair_agents": sorted(repair_requests)},
        ),
        progress_callback,
    )
    data = context.get("data", {})
    for agent_num in sorted(repair_requests):
        agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
        ok, message = _repair_agent_output(agent_num, data, context, rotator, repair_requests[agent_num])
        status = "成功" if ok else "失敗"
        log = f"{agent_name} AI 修復{status}：{message}"
        context.setdefault("audit_repair_log", []).append(log)
        emit_log(f"     - {log}")
        emit_context_event(
            context,
            make_runtime_event(
                "status",
                phase="final_audit_repair_result",
                level="info" if ok else "error",
                message=log,
                current=context.get("agent_total"),
                total=context.get("agent_total"),
                name=agent_name,
                agent_num=agent_num,
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"ok": ok},
            ),
            progress_callback,
        )


async def attempt_final_audit_repair_async(context: AnalysisContext, audit: AuditResult, rotator: KeyRotator, progress_callback=None):
    repair_requests = audit.get("repair_agent_issues", {}) or {}
    if not repair_requests:
        context.setdefault("audit_repair_log", []).append("最終稽核發現問題，但沒有可定位到單一 Agent 的自動重寫項目；報告會保留並標示異常。")
        return

    message = "最終稽核發現異常，嘗試請相關 Agent 非同步重寫修復..."
    emit_log(f"  🛠️  {message}")
    await emit_context_event_async(
        context,
        make_runtime_event(
            "status",
            phase="final_audit_repair",
            level="warning",
            message=message,
            current=context.get("agent_total"),
            total=context.get("agent_total"),
            name="最終稽核",
            pipeline_id=context.get("pipeline_id"),
            pipeline_label=context.get("pipeline_label"),
            metadata={"repair_agents": sorted(repair_requests)},
        ),
        progress_callback,
    )
    data = context.get("data", {})
    for agent_num in sorted(repair_requests):
        agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
        ok, message = await _repair_agent_output_async(agent_num, data, context, rotator, repair_requests[agent_num])
        status = "成功" if ok else "失敗"
        log = f"{agent_name} AI 修復{status}：{message}"
        context.setdefault("audit_repair_log", []).append(log)
        emit_log(f"     - {log}")
        await emit_context_event_async(
            context,
            make_runtime_event(
                "status",
                phase="final_audit_repair_result",
                level="info" if ok else "error",
                message=log,
                current=context.get("agent_total"),
                total=context.get("agent_total"),
                name=agent_name,
                agent_num=agent_num,
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"ok": ok},
            ),
            progress_callback,
        )


def _summarize_audit_issues(audit: AuditResult, limit: int = 3) -> str:
    issues = [str(item) for item in (audit.get("critical", []) or [])[:limit]]
    return "；".join(issues) if issues else "無可列示異常"


def finalize_final_audit(
    context: AnalysisContext,
    rotator: KeyRotator,
    max_repair_passes: int = FINAL_AUDIT_REPAIR_PASSES,
    progress_callback=None,
) -> AuditResult:
    """Run final audit, repair repairable failures, re-audit, then preserve report state."""
    last_audit = None
    for repair_pass in range(max_repair_passes + 1):
        context["parsed"] = parse_structured_data(context)
        last_audit = run_final_report_audit(context, append_section=False)
        if not last_audit.get("critical"):
            context["final_audit"] = run_final_report_audit(context, append_section=True)
            return context["final_audit"]

        if repair_pass >= max_repair_passes:
            remaining = _summarize_audit_issues(last_audit)
            context.setdefault("audit_repair_log", []).append(
                f"最終稽核自動修復已達 {max_repair_passes} 輪上限；報告會保留並標示剩餘異常：{remaining}"
            )
            break

        message = f"最終稽核第 {repair_pass + 1}/{max_repair_passes} 輪修復，完成後會重新稽核。"
        emit_log(f"  🧭 {message}")
        emit_context_event(
            context,
            make_runtime_event(
                "status",
                phase="final_audit_repair_pass",
                level="warning",
                message=message,
                current=context.get("agent_total"),
                total=context.get("agent_total"),
                name="最終稽核",
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"repair_pass": repair_pass + 1, "max_repair_passes": max_repair_passes},
            ),
            progress_callback,
        )
        attempt_final_audit_repair(context, last_audit, rotator, progress_callback=progress_callback)
        if not last_audit.get("repair_agent_issues"):
            break

    context["parsed"] = parse_structured_data(context)
    context["final_audit"] = run_final_report_audit(context, append_section=True)
    return context["final_audit"]


async def finalize_final_audit_async(
    context: AnalysisContext,
    rotator: KeyRotator,
    max_repair_passes: int = FINAL_AUDIT_REPAIR_PASSES,
    progress_callback=None,
) -> AuditResult:
    """Async final audit flow with repair and mandatory re-audit before rendering."""
    last_audit = None
    for repair_pass in range(max_repair_passes + 1):
        context["parsed"] = parse_structured_data(context)
        last_audit = run_final_report_audit(context, append_section=False)
        if not last_audit.get("critical"):
            context["final_audit"] = run_final_report_audit(context, append_section=True)
            return context["final_audit"]

        if repair_pass >= max_repair_passes:
            remaining = _summarize_audit_issues(last_audit)
            context.setdefault("audit_repair_log", []).append(
                f"最終稽核自動修復已達 {max_repair_passes} 輪上限；報告會保留並標示剩餘異常：{remaining}"
            )
            break

        message = f"最終稽核第 {repair_pass + 1}/{max_repair_passes} 輪非同步修復，完成後會重新稽核。"
        emit_log(f"  🧭 {message}")
        await emit_context_event_async(
            context,
            make_runtime_event(
                "status",
                phase="final_audit_repair_pass",
                level="warning",
                message=message,
                current=context.get("agent_total"),
                total=context.get("agent_total"),
                name="最終稽核",
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"repair_pass": repair_pass + 1, "max_repair_passes": max_repair_passes},
            ),
            progress_callback,
        )
        await attempt_final_audit_repair_async(context, last_audit, rotator, progress_callback=progress_callback)
        if not last_audit.get("repair_agent_issues"):
            break

    context["parsed"] = parse_structured_data(context)
    context["final_audit"] = run_final_report_audit(context, append_section=True)
    return context["final_audit"]
