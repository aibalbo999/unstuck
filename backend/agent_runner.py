# ============================================================
# agent_runner.py - 連續式 Agent 執行引擎
# 包含：API Key 輪調、速率限制、7個分析 Agent 的 Prompt
# ============================================================

import asyncio
import time
from typing import Any, Optional
from google.genai import types
from agent_catalog import AGENT_NAMES
from assistant_tasks import (
    CONTEXT_DIGEST_TARGET_AGENTS,
    _build_context_digest_prompt,
    _build_tear_sheet_prompt,
    _format_previous,
    _format_structured_outputs_for_context,
    ensure_context_digest,
    ensure_context_digest_async,
    ensure_tear_sheet_summary,
    ensure_tear_sheet_summary_async,
)
from config import API_KEYS, AGENT_MODELS, AUDIT_MODEL, CONTEXT_DIGEST_MODEL, INTER_AGENT_DELAY
from financial_data import format_data_for_prompt
from financial_tools import calculate_cagr, calculate_dcf, calculate_ddm, calculate_wacc
from final_audit import run_final_report_audit
from llm_client import (
    KeyRotator,
    describe_quota_or_rate_error,
    estimate_text_tokens,
    generate_content,
    generate_content_async,
    is_missing_model_error,
    is_quota_or_rate_error,
    response_text,
    retry_delay_seconds,
)
from prompt_loader import load_agent_prompt_config
from prompt_rules import (
    build_agent_rule_block,
    build_identity_guard_rule_lines,
    build_output_cleanliness_rule,
    get_task_system_instruction,
)
from structured_outputs import (
    STRUCTURED_AGENT_INSTRUCTIONS,
    _coerce_number,
    _extract_json_payload,
    build_structured_output_instruction,
    normalize_structured_output,
    parse_structured_data,
    price_targets_have_unit_error,
    process_agent_response,
    structured_output_to_report_text,
)
from validators import (
    _extract_price_numbers,
    _parse_price_number,
    append_identity_warnings,
    append_quality_warnings,
    build_identity_retry_instruction,
    normalize_bad_number_commas,
    sanitize_model_output,
    strip_generated_audit_sections,
    strip_prompt_preamble,
    validate_analysis_output,
    validate_company_identity,
    validate_prompt_leakage,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Prompt 設定（外部 JSON）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROMPT_CONFIG = load_agent_prompt_config()
SYSTEM_PROMPTS = {int(k): v for k, v in PROMPT_CONFIG["system_prompts"].items()}
ANALYSIS_PROMPTS = {int(k): v for k, v in PROMPT_CONFIG["analysis_prompts"].items()}
FINAL_AUDIT_REPAIR_PASSES = 2


def get_agent_function_tools(agent_num: int) -> list:
    """Return Python function tools for agents that need deterministic math."""
    if agent_num == 2:
        return [calculate_cagr]
    if agent_num == 4:
        return [calculate_cagr, calculate_wacc, calculate_dcf, calculate_ddm]
    return []


def get_agent_model_sequence(agent_num: int) -> list[str]:
    """Return the strict single-model route for an analysis agent."""
    return [AGENT_MODELS[agent_num]]


def get_audit_model_sequence() -> list[str]:
    """Return the strict single-model route reserved for final audit reflection and rewrites."""
    return [AUDIT_MODEL]


def get_context_digest_model_sequence() -> list[str]:
    """Return the strict single-model route for context digest generation."""
    return [CONTEXT_DIGEST_MODEL]


def get_runtime_model_sequence(agent_num: int, context: Optional[dict] = None) -> list[str]:
    """Return the active model sequence, honoring temporary audit overrides."""
    override = (context or {}).get("_model_sequence_override", {})
    if isinstance(override, dict) and agent_num in override:
        models = override.get(agent_num) or []
        return list(dict.fromkeys(model for model in models if model))
    return get_agent_model_sequence(agent_num)


def is_agent_execution_failure(text: str) -> bool:
    return bool(text and text.startswith("[Agent ") and "執行失敗" in text)


OUTPUT_CLEANLINESS_RULE = build_output_cleanliness_rule()

def build_company_identity_guard(data: dict) -> str:
    """Build a hard identity lock so agents do not assign peer facts to the target company."""
    identity = data.get("company_identity", {}) or {}
    if not identity:
        return ""

    ticker = data.get("ticker", identity.get("ticker", "N/A"))
    stock_id = identity.get("stock_id", ticker)
    official_name = identity.get("official_name") or data.get("company_name", ticker)
    legal_name = identity.get("legal_name")
    english_names = identity.get("english_names", [])
    forbidden_aliases = identity.get("forbidden_aliases", [])

    lines = build_identity_guard_rule_lines({
        "ticker": ticker,
        "stock_id": stock_id,
        "official_name": official_name,
        "legal_name": legal_name,
        "english_names": ", ".join(english_names[:3]),
        "forbidden_aliases": ", ".join(forbidden_aliases),
    })

    return "\n".join(lines)


def build_generation_config(agent_num: int, system_instruction: Optional[str] = None):
    """Build Google GenAI generation config, using JSON MIME type where supported."""
    config_kwargs = {
        "temperature": 0.7,
        "top_p": 0.95,
        "max_output_tokens": 8192,
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if agent_num in STRUCTURED_AGENT_INSTRUCTIONS:
        config_kwargs["response_mime_type"] = "application/json"
    function_tools = get_agent_function_tools(agent_num)
    if function_tools:
        config_kwargs["tools"] = function_tools
        config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(maximum_remote_calls=6)

    try:
        return types.GenerateContentConfig(**config_kwargs)
    except TypeError:
        config_kwargs.pop("response_mime_type", None)
        config_kwargs.pop("automatic_function_calling", None)
        config_kwargs.pop("tools", None)
        return types.GenerateContentConfig(**config_kwargs)


def _response_text(response) -> str:
    return response_text(response)


def _generate_content(api_key: str, model_id: str, agent_num: int, prompt: str):
    config = build_generation_config(agent_num, SYSTEM_PROMPTS[agent_num])
    return generate_content(api_key, model_id, prompt, config)


async def _generate_content_async(api_key: str, model_id: str, agent_num: int, prompt: str):
    config = build_generation_config(agent_num, SYSTEM_PROMPTS[agent_num])
    return await generate_content_async(api_key, model_id, prompt, config)


def build_numeric_tool_instruction(agent_num: int) -> str:
    """Prompt agents with deterministic tool usage guidance."""
    return build_agent_rule_block("numeric_tool_instructions", agent_num)


def build_data_enrichment_instruction(agent_num: int) -> str:
    """Tell agents which enriched context slices are decision-relevant."""
    return build_agent_rule_block("data_enrichment_instructions", agent_num)


def build_prompt(agent_num: int, data: dict, context: dict) -> str:
    """根據 Agent 編號建立分析提示詞。"""
    ticker = data["ticker"]
    name = data["company_name"]
    fin_data = format_data_for_prompt(data)
    prev = _format_previous(context, agent_num)
    identity_guard = build_company_identity_guard(data)
    numeric_tool_instruction = build_numeric_tool_instruction(agent_num)
    enrichment_instruction = build_data_enrichment_instruction(agent_num)
    retry_instruction = context.get("_identity_retry_instruction", "")
    audit_retry_instruction = context.get("_audit_retry_instruction", "")
    audit_reflection_instruction = context.get("_audit_reflection_instruction", "")

    template = ANALYSIS_PROMPTS[agent_num]
    analysis_prompt = template.format(
        ticker=ticker,
        name=name,
        fin_data=fin_data,
        prev=prev,
    )

    structured_instruction = build_structured_output_instruction(agent_num)
    prompt_parts = [
        analysis_prompt,
        "⚠️ 若上方任務文字包含 [護城河評分]、[目標股價]、[投資建議] 等舊式區塊格式，請忽略舊式格式；本次只遵守下方 JSON 結構化輸出規則。" if structured_instruction else "",
        structured_instruction,
        numeric_tool_instruction,
        enrichment_instruction,
        identity_guard,
        retry_instruction,
        audit_reflection_instruction,
        audit_retry_instruction,
        OUTPUT_CLEANLINESS_RULE,
    ]
    return "\n\n".join(part for part in prompt_parts if part)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 核心 Agent 執行函數
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_single_agent(
    agent_num: int,
    data: dict,
    context: dict,
    rotator: KeyRotator,
    max_retries: int = 3
) -> str:
    """
    執行單個分析 Agent
    - 自動選擇可用的 API Key
    - 超限時自動重試
    - 錯誤時返回錯誤訊息
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_single_agent_async(agent_num, data, context, rotator, max_retries))

    model_sequence = get_runtime_model_sequence(agent_num, context)
    model_id = model_sequence[0]
    prompt = build_prompt(agent_num, data, context)
    
    for attempt in range(max_retries):
        api_key = None
        try:
            # 取得可用 API Key
            api_key = rotator.get_key(model_id, estimate_text_tokens(prompt, response_budget=8192))
            
            # 執行分析
            response = _generate_content(api_key, model_id, agent_num, prompt)
            result = process_agent_response(agent_num, _response_text(response), context)
            
            if result and len(result) > 100:
                return result
            else:
                print(f"    ⚠️  回應過短，重試 ({attempt+1}/{max_retries})")
                time.sleep(5)
                
        except Exception as e:
            error_msg = str(e)
            if is_quota_or_rate_error(error_msg):
                wait_time = retry_delay_seconds(e, default=65 * (attempt + 1))
                if api_key:
                    rotator.penalize(api_key, model_id, wait_time)
                quota_detail = describe_quota_or_rate_error(e)
                print(f"    ⏳ 配額/速率限制：{quota_detail[:160]}... 等待 {wait_time} 秒 ({attempt+1}/{max_retries})")
                time.sleep(wait_time)
            elif "404" in error_msg or "not found" in error_msg.lower():
                print(f"    ❌ 模型 {model_id} 不可用，嘗試備用模型...")
                # 嘗試備用模型
                backup_models = [model for model in model_sequence[1:] if model != model_id]
                for backup in backup_models:
                    try:
                        backup_key = rotator.get_key(backup, estimate_text_tokens(prompt, response_budget=8192))
                        response = _generate_content(backup_key, backup, agent_num, prompt)
                        return process_agent_response(agent_num, _response_text(response), context)
                    except Exception:
                        continue
                return f"[Agent {agent_num} 執行失敗：模型不可用]"
            else:
                print(f"    ❌ 錯誤：{error_msg[:100]}... 重試 ({attempt+1}/{max_retries})")
                time.sleep(10 * (attempt + 1))
    
    return f"[Agent {agent_num} 執行失敗：模型 {model_id} 多次失敗，未啟用跨模型 fallback]"


async def run_single_agent_async(
    agent_num: int,
    data: dict,
    context: dict,
    rotator: KeyRotator,
    max_retries: int = 3
) -> str:
    """
    非同步執行單個分析 Agent。
    - 使用 Google GenAI SDK 的 client.aio 非同步呼叫
    - quota/rate limit 會快速切換下一組 Key 或下一個模型
    """
    prompt = build_prompt(agent_num, data, context)
    model_sequence = get_runtime_model_sequence(agent_num, context)
    last_error = ""

    for model_index, model_id in enumerate(model_sequence):
        if model_index > 0:
            print(f"    🔁 切換備援模型：{model_id}")

        attempts_for_model = max(max_retries, len(rotator.keys)) if model_index == 0 else len(rotator.keys)

        for attempt in range(attempts_for_model):
            api_key = None
            try:
                api_key = await rotator.async_get_key(model_id, estimate_text_tokens(prompt, response_budget=8192))

                response = await _generate_content_async(api_key, model_id, agent_num, prompt)
                result = process_agent_response(agent_num, _response_text(response), context)

                if result and len(result) > 100:
                    return result

                last_error = "回應過短"
                print(f"    ⚠️  {model_id} 回應過短，嘗試下一組 Key/模型 ({attempt+1}/{attempts_for_model})")
                await asyncio.sleep(1)

            except Exception as e:
                error_msg = str(e)
                last_error = error_msg

                if is_quota_or_rate_error(error_msg):
                    quota_detail = describe_quota_or_rate_error(e)
                    wait_time = retry_delay_seconds(e, default=1)
                    if api_key:
                        rotator.penalize(api_key, model_id, wait_time)
                    last_error = quota_detail
                    print(
                        f"    ⏭️  {model_id} 配額/速率限制：{quota_detail[:160]}... "
                        f"改試下一組 Key/模型 ({attempt+1}/{attempts_for_model})"
                    )
                    await asyncio.sleep(1)
                    continue

                if is_missing_model_error(error_msg):
                    print(f"    ❌ 模型 {model_id} 不可用，改試下一個備援模型...")
                    break

                print(f"    ❌ {model_id} 錯誤：{error_msg[:100]}... 非同步重試 ({attempt+1}/{attempts_for_model})")
                await asyncio.sleep(min(10 * (attempt + 1), 30))

    return f"[Agent {agent_num} 執行失敗：所有模型/Key 不可用，最後錯誤：{last_error[:120]}]"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 主要執行管道
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_analysis_pipeline(data: dict, progress_callback=None) -> dict:
    """Compatibility wrapper; orchestration lives in pipeline.py."""
    from pipeline import run_analysis_pipeline as _run_analysis_pipeline

    return _run_analysis_pipeline(data, progress_callback=progress_callback)


async def run_analysis_pipeline_async(data: dict, progress_callback=None) -> dict:
    """Compatibility wrapper; async DAG orchestration lives in pipeline.py."""
    from pipeline import run_analysis_pipeline_async as _run_analysis_pipeline_async

    return await _run_analysis_pipeline_async(data, progress_callback=progress_callback)


def _build_reflection_generation_config():
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=1200,
        system_instruction=get_task_system_instruction("audit_reflection"),
    )


def _build_audit_reflection_prompt(agent_num: int, issues: list[str], previous_text: str, data: dict) -> str:
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


def generate_audit_reflection(agent_num: int, issues: list[str], previous_text: str, data: dict, rotator: KeyRotator) -> str:
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
            print(f"       ↳ 反思步驟呼叫失敗，改用 deterministic reflection：{str(exc)[:100]}")
            break
    return _fallback_audit_reflection(agent_num, issues)


async def generate_audit_reflection_async(agent_num: int, issues: list[str], previous_text: str, data: dict, rotator: KeyRotator) -> str:
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
            print(f"       ↳ 非同步反思步驟呼叫失敗，改用 deterministic reflection：{str(exc)[:100]}")
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


def _clear_agent_blocking_issues(context: dict, agent_num: int):
    agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
    prefixes = (f"Agent {agent_num} ", f"Agent {agent_num}: ", f"{agent_name}: ")
    context["blocking_issues"] = [
        issue for issue in context.get("blocking_issues", [])
        if not str(issue).startswith(prefixes)
    ]
    if not context["blocking_issues"]:
        context.pop("blocking_issues", None)


def _repair_agent_output(agent_num: int, data: dict, context: dict, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Synchronously ask the relevant agent to rewrite after final audit failure."""
    previous_instruction = context.get("_audit_retry_instruction")
    previous_reflection_instruction = context.get("_audit_reflection_instruction")
    previous_model_override = context.get("_model_sequence_override")
    try:
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
            context["structured_outputs"].pop(agent_num, None)
            result = run_single_agent(agent_num, data, context, rotator, max_retries=1)
            result = sanitize_model_output(result)
            if is_agent_execution_failure(result):
                return False, result
            prompt_issues = validate_prompt_leakage(result)
            identity_issues = validate_company_identity(result, data)
            if prompt_issues or identity_issues:
                return False, "；".join(prompt_issues + identity_issues)
            quality_issues = validate_analysis_output(agent_num, result, data)
            if quality_issues:
                last_result = append_quality_warnings(agent_num, result, data)
                last_quality_issues = quality_issues
                current_issues = quality_issues
                print(f"       ↳ 第 {repair_attempt + 1} 次重寫仍觸發品質紅線，改用紅線重新要求修復。")
                continue
            context["analyses"][agent_num] = strip_generated_audit_sections(result)
            _clear_agent_blocking_issues(context, agent_num)
            return True, "已重寫並通過品質檢查"
        if last_result:
            context["analyses"][agent_num] = last_result
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


async def _repair_agent_output_async(agent_num: int, data: dict, context: dict, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Asynchronously ask the relevant agent to rewrite after final audit failure."""
    previous_instruction = context.get("_audit_retry_instruction")
    previous_reflection_instruction = context.get("_audit_reflection_instruction")
    previous_model_override = context.get("_model_sequence_override")
    try:
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
            context["structured_outputs"].pop(agent_num, None)
            result = await run_single_agent_async(agent_num, data, context, rotator, max_retries=1)
            result = sanitize_model_output(result)
            if is_agent_execution_failure(result):
                return False, result
            prompt_issues = validate_prompt_leakage(result)
            identity_issues = validate_company_identity(result, data)
            if prompt_issues or identity_issues:
                return False, "；".join(prompt_issues + identity_issues)
            quality_issues = validate_analysis_output(agent_num, result, data)
            if quality_issues:
                last_result = append_quality_warnings(agent_num, result, data)
                last_quality_issues = quality_issues
                current_issues = quality_issues
                print(f"       ↳ 第 {repair_attempt + 1} 次重寫仍觸發品質紅線，改用紅線重新要求修復。")
                continue
            context["analyses"][agent_num] = strip_generated_audit_sections(result)
            _clear_agent_blocking_issues(context, agent_num)
            return True, "已重寫並通過品質檢查"
        if last_result:
            context["analyses"][agent_num] = last_result
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


def attempt_final_audit_repair(context: dict, audit: dict, rotator: KeyRotator):
    repair_requests = audit.get("repair_agent_issues", {}) or {}
    if not repair_requests:
        context.setdefault("audit_repair_log", []).append("最終稽核發現問題，但沒有可定位到單一 Agent 的自動重寫項目；報告會保留並標示異常。")
        return

    print("  🛠️  最終稽核發現異常，嘗試請相關 Agent 自動重寫修復...")
    data = context.get("data", {})
    for agent_num in sorted(repair_requests):
        agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
        ok, message = _repair_agent_output(agent_num, data, context, rotator, repair_requests[agent_num])
        status = "成功" if ok else "失敗"
        log = f"{agent_name} AI 修復{status}：{message}"
        context.setdefault("audit_repair_log", []).append(log)
        print(f"     - {log}")


async def attempt_final_audit_repair_async(context: dict, audit: dict, rotator: KeyRotator):
    repair_requests = audit.get("repair_agent_issues", {}) or {}
    if not repair_requests:
        context.setdefault("audit_repair_log", []).append("最終稽核發現問題，但沒有可定位到單一 Agent 的自動重寫項目；報告會保留並標示異常。")
        return

    print("  🛠️  最終稽核發現異常，嘗試請相關 Agent 非同步重寫修復...")
    data = context.get("data", {})
    for agent_num in sorted(repair_requests):
        agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
        ok, message = await _repair_agent_output_async(agent_num, data, context, rotator, repair_requests[agent_num])
        status = "成功" if ok else "失敗"
        log = f"{agent_name} AI 修復{status}：{message}"
        context.setdefault("audit_repair_log", []).append(log)
        print(f"     - {log}")


def _summarize_audit_issues(audit: dict, limit: int = 3) -> str:
    issues = [str(item) for item in (audit.get("critical", []) or [])[:limit]]
    return "；".join(issues) if issues else "無可列示異常"


def finalize_final_audit(
    context: dict,
    rotator: KeyRotator,
    max_repair_passes: int = FINAL_AUDIT_REPAIR_PASSES,
) -> dict:
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

        print(f"  🧭 最終稽核第 {repair_pass + 1}/{max_repair_passes} 輪修復，完成後會重新稽核。")
        attempt_final_audit_repair(context, last_audit, rotator)
        if not last_audit.get("repair_agent_issues"):
            break

    context["parsed"] = parse_structured_data(context)
    context["final_audit"] = run_final_report_audit(context, append_section=True)
    return context["final_audit"]


async def finalize_final_audit_async(
    context: dict,
    rotator: KeyRotator,
    max_repair_passes: int = FINAL_AUDIT_REPAIR_PASSES,
) -> dict:
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

        print(f"  🧭 最終稽核第 {repair_pass + 1}/{max_repair_passes} 輪非同步修復，完成後會重新稽核。")
        await attempt_final_audit_repair_async(context, last_audit, rotator)
        if not last_audit.get("repair_agent_issues"):
            break

    context["parsed"] = parse_structured_data(context)
    context["final_audit"] = run_final_report_audit(context, append_section=True)
    return context["final_audit"]
