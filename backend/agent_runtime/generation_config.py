"""Generation config and provider call helpers for agent LLM requests."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from typing import Any, Optional

from google.genai import types

from config import LLM_AGENT_CALL_TIMEOUT_SECONDS
from forward_consistency_checker import RECOMMENDATION_RETURN_GATES, TARGET_REVERSAL_TOLERANCE_PCT
from google_prompt_safety import sanitize_google_system_instruction
from llm_input_capacity import estimate_input_tokens
from llm_client import generate_content, generate_content_async, generate_content_stream_async, response_text
from research_assumption_contract import TOPICS as RESEARCH_ASSUMPTION_TOPICS
from structured_output_models import STRUCTURED_AGENT_INSTRUCTIONS, get_structured_response_schema

from .prompt_config import SYSTEM_PROMPTS
from .retry_policy import AgentTransientError
from debate_output_completion import POLICY as AGENT6_COMPLETION_POLICY, INSTRUCTION as _AGENT6_COMPLETION_INSTRUCTION
from .routing import get_agent_function_tools


GENERATION_POLICY_VERSION = "agent-generation:v6"
AGENT7_COMPLETION_POLICY = "research-completion:v5-schema-first-completion"
AGENT16_COMPLETION_POLICY = "trading-completion:v1-low-thinking"
_DEFAULT_GENERATION_PROFILE = {
    "temperature": 0.7,
    "top_p": 0.95,
    "max_output_tokens": 8192,
}

# The former global 0.7/0.95/8192 policy made deterministic evidence roles as
# variable and expensive as the debate role.  Keep one explicit profile per
# numbered agent so report provenance can identify the policy actually used.
AGENT_GENERATION_PROFILES = {
    1: {"temperature": 0.45, "top_p": 0.90, "max_output_tokens": 8192},
    2: {"temperature": 0.25, "top_p": 0.90, "max_output_tokens": 8192},
    3: {"temperature": 0.30, "top_p": 0.90, "max_output_tokens": 4096},
    4: {"temperature": 0.20, "top_p": 0.85, "max_output_tokens": 6144},
    5: {"temperature": 0.45, "top_p": 0.90, "max_output_tokens": 8192},
    6: {"temperature": 0.25, "top_p": 0.95, "max_output_tokens": 8192},
    7: {"temperature": 0.25, "top_p": 0.90, "max_output_tokens": 6144},
    11: {"temperature": 0.40, "top_p": 0.90, "max_output_tokens": 3072},
    12: {"temperature": 0.30, "top_p": 0.90, "max_output_tokens": 4096},
    13: {"temperature": 0.25, "top_p": 0.90, "max_output_tokens": 3072},
    14: {"temperature": 0.20, "top_p": 0.85, "max_output_tokens": 6144},
    15: {"temperature": 0.40, "top_p": 0.90, "max_output_tokens": 3072},
    16: {"temperature": 0.25, "top_p": 0.90, "max_output_tokens": 6144},
    17: {"temperature": 0.40, "top_p": 0.90, "max_output_tokens": 3072},
    18: {"temperature": 0.25, "top_p": 0.90, "max_output_tokens": 4096},
    19: {"temperature": 0.25, "top_p": 0.90, "max_output_tokens": 6144},
    20: {"temperature": 0.20, "top_p": 0.85, "max_output_tokens": 1024},
    21: {"temperature": 0.25, "top_p": 0.90, "max_output_tokens": 4096},
    22: {"temperature": 0.35, "top_p": 0.90, "max_output_tokens": 3072},
    23: {"temperature": 0.30, "top_p": 0.90, "max_output_tokens": 3072},
    24: {"temperature": 0.20, "top_p": 0.85, "max_output_tokens": 4096},
}
_BOUNDED_THINKING_MODELS = {"gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash"}
_MEDIUM_THINKING_AGENTS = {7, 16, 19, 24}
_COMPLETION_LOW_THINKING_MODELS = _BOUNDED_THINKING_MODELS | {"gemini-3-flash-preview", "gemini-3.6-flash"}
_AGENT7_COMPLETION_INSTRUCTION = (
    "\n\nAgent 7 完整性契約：只輸出一份完整 JSON，先完成 response_schema 的所有必要欄位與結尾大括號。"
    "analysis_markdown 以 800–1200 字的精煉正文為目標，避免重貼原始表格、逐字重複其他 JSON 欄位或前序分析；"
    "若必要證據需更多文字，完整性與品質規則優先於此篇幅目標。"
    "保留支持、反證、資料不足與各期研究情境；不得為通過檢查改寫研究分類或補造價格。"
    f"assumption_reconciliation 必須涵蓋 {'、'.join(RESEARCH_ASSUMPTION_TOPICS)} 五項，並明確填寫 pending_recalculation；"
    "valuation_quote 與 growth_quote 只能逐字引用對應角色的完整可見來源，不改數字、單位或補造引文，"
    "找不到同語意來源時如實保留缺口，不以概述代替引文。"
    "引文優先選擇短而完整的連續原文，保留 Markdown、空格與反斜線，僅按 JSON 語法跳脫；"
    "不可把公式的反斜線加倍成不同原文字元，不可用省略號或拼接跨句內容。"
    "也可填寫當前來源片段的 quote_ref，並把對應 quote 留空，由系統逐字取回；不可以編號代替推論與缺口判斷。"
    "完成推薦前，按實際現價與12個月目標算出報酬，核對分類契約與正文；持有不等同暫時觀望。"
    "market_context_assessment 必須評估完整可見的全球市場與國際新聞來源，保留具體 reason 與有效 source_refs；"
    "不得為省字略過來源評估或刪減必要引用。"
)
_AGENT19_COMPLETION_INSTRUCTION = (
    "\n\nAgent 19 完整性契約：請一次輸出完整 JSON，先完成 response_schema 的所有必要欄位，"
    "recommendation 分類只使用 response_schema 列舉值，不自行創造分類。"
    "analysis_markdown 以 800–1200 字的精煉正文為目標，避免重貼原始表格、逐字重複其他 JSON 欄位或前序分析；"
    "若必要證據需更多文字，完整性與品質規則優先於此篇幅目標。"
    "保留做空觸發條件與防軋空停損點兩個必要標題，以及支持、反證與資料限制。"
    "market_context_assessment 必須評估完整來源，保留具體 reason 與有效 source_refs，不能為省字略過來源評估或刪減必要引用。"
    "製造業高成長情境仍須明確檢查產能、CapEx、折舊、良率與客戶議價五項風險；不適用或資料不足須逐項說明。"
    "非放空分類的 short_setup.entry_trigger 只表達等待與重新評估條件，不能混入條件達成即可進場或建立空單的指令；"
    "不開倉時 downside_target 可不適用，不得補造價格。"
    "若選擇 AVOID 且確實不建立部位，entry_trigger 須明確寫目前不建立空方部位；"
    "cover_stop 須保留不適用及目前不建立空方部位的原因，不能只寫 N/A；並保留軋空風險及重新評估條件。"
    "若包含既有部位、減碼或條件下單，須如實保留，不可改寫成無部位以通過檢查。"
)
_AGENT16_COMPLETION_INSTRUCTION = (
    "\n\nAgent 16 完整性契約：只輸出一份完整 JSON 與結尾大括號，先完成 response_schema 所有必要欄位，"
    "包括 recommendation、position_plan、confidence_basis、scenario_triggers、analysis_markdown。"
    "analysis_markdown 以 800–1200 字精煉整合，避免逐字重複前序分析、原始表格或其他 JSON 欄位；"
    "完整證據與品質規則優先於篇幅目標，不得刪減必要引用或以資料不足代替可驗證分析。"
    "保留支持、反證、失效條件、倉位與現金比例、成本及風險限制；不為完成欄位補造價格或改變研究分類。"
    "market_context_assessment 必須評估完整來源，保留具體 reason 與有效 source_refs；"
    "來源與資料缺口如實保留，不靠省略必要內容避免截斷。"
)


def _agent19_recommendation_contract_instruction() -> str:
    gates = RECOMMENDATION_RETURN_GATES
    return (
        "\n\n四個 response_schema 研究分類有不同語意，須由完整證據選擇，不預設任何分類："
        f"偏多觀察（BUY）：12 個月隱含報酬至少 {gates['買入']['min_expected_return_pct']:g}%；"
        f"中性觀察（HOLD）：12 個月隱含報酬須介於 {gates['持有']['min_expected_return_pct']:g}% 至 {gates['持有']['max_expected_return_pct']:g}%，"
        "不等於通用的等待或不開倉，也不能代表等待空方訊號；"
        "避險觀察（AVOID）：不預設目標價格漲跌方向，須以證據說明不承擔新部位的理由；"
        f"空方風險觀察（SHORT）：12 個月隱含報酬不得高於 {gates['放空']['max_expected_return_pct']:g}%，且 short_setup 必須具有可驗證價格與風險條件。"
        "隱含報酬為（該期目標價 / current_price - 1）×100%；各期目標（3、6、12 個月）均須與研究分類及正文一致，"
        "不能僅檢查 12 個月而忽略 3 或 6 個月目標的大幅下修或極端波幅；發生矛盾時應根據證據重審分類與估值假設。"
        f"BUY 各期目標應大致遞增，SHORT 應大致遞減，既有相鄰期間逆向偏差容忍度為 {TARGET_REVERSAL_TOLERANCE_PCT:g}%。"
        "缺少現價或目標價時保留資料不足，不得為符合門檻補造或調整價格，也不得為通過檢查而忽略反證或強迫選擇 AVOID。"
    )


def _thinking_level(agent_num: int | None, model_id: str) -> str | None:
    model = model_id.removeprefix("google:").removeprefix("models/")
    # Keep observed truncating evidence/assessment roles within their existing
    # output budgets; completion and financial gates still validate every reply.
    if agent_num in {1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 20, 21} and model in _COMPLETION_LOW_THINKING_MODELS:
        return "low"
    if agent_num in {16, 18, 19, 22, 23, 24} and model in _COMPLETION_LOW_THINKING_MODELS:
        return "low"
    if model_id in _BOUNDED_THINKING_MODELS:
        return "medium" if agent_num in _MEDIUM_THINKING_AGENTS else "low"
    return None

_PROMPT_STRUCTURED_TOOL_AGENTS = {2, 13, 18}


def generation_profile(agent_num: int) -> dict[str, int | float]:
    return dict(AGENT_GENERATION_PROFILES.get(agent_num, _DEFAULT_GENERATION_PROFILE))


def generation_event_metadata(agent_num: int, model_id: str) -> dict[str, int | float | str]:
    metadata = generation_profile(agent_num)
    if agent_num == 6:
        metadata['completion_policy_version'] = AGENT6_COMPLETION_POLICY
    if agent_num == 11:
        from industry_output_completion import POLICY
        metadata['completion_policy_version'] = POLICY
    level = _thinking_level(agent_num, model_id)
    if level is not None:
        metadata["thinking_level"] = level
    if agent_num == 16:
        metadata['completion_policy_version'] = AGENT16_COMPLETION_POLICY
    from assessment_output_completion import AGENTS, CONTRACT
    if agent_num in AGENTS:
        metadata['completion_policy_version'] = CONTRACT
    return metadata


def _sanitize_genai_schema(node: Any) -> Any:
    """Recursively remove or rewrite JSON-schema fields rejected by Google GenAI.

    Google GenAI's response_schema API rejects schemas that contain
    additionalProperties (produced by Pydantic when extra="forbid" is set),
    raising 400 INVALID_ARGUMENT: Unknown name "additional_properties".
    It also rejects exclusiveMinimum / exclusiveMaximum numeric bounds.
    """
    if isinstance(node, dict):
        node.pop("additionalProperties", None)
        if "exclusiveMinimum" in node and "minimum" not in node:
            node["minimum"] = node.pop("exclusiveMinimum")
        else:
            node.pop("exclusiveMinimum", None)
        if "exclusiveMaximum" in node and "maximum" not in node:
            node["maximum"] = node.pop("exclusiveMaximum")
        else:
            node.pop("exclusiveMaximum", None)
        for value in node.values():
            _sanitize_genai_schema(value)
    elif isinstance(node, list):
        for item in node:
            _sanitize_genai_schema(item)
    return node


def _generate_config_supports(field_name: str) -> bool:
    fields = getattr(types.GenerateContentConfig, "model_fields", {}) or {}
    return field_name in fields


def build_generation_config(agent_num: int, system_instruction: Optional[str] = None):
    """Build Google GenAI generation config, using JSON MIME type where supported."""
    function_tools = get_agent_function_tools(agent_num)
    # Google rejects native JSON response schemas and function tools in the same
    # request. Tool-backed evidence agents keep their deterministic calculators
    # and follow the JSON contract through the appended prompt instruction.
    uses_structured_response = (
        agent_num in STRUCTURED_AGENT_INSTRUCTIONS
        and agent_num not in _PROMPT_STRUCTURED_TOOL_AGENTS
    )
    config_kwargs = generation_profile(agent_num)
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if uses_structured_response:
        config_kwargs["response_mime_type"] = "application/json"
        response_schema_cls = get_structured_response_schema(agent_num)
        if response_schema_cls and _generate_config_supports("response_schema"):
            # Build a sanitized plain-dict schema: strip additionalProperties so
            # Google GenAI does not reject it with 400 INVALID_ARGUMENT.
            try:
                schema_dict = deepcopy(response_schema_cls.model_json_schema(by_alias=True))
                _sanitize_genai_schema(schema_dict)
                from market_source_schema import apply_market_source_schema
                schema_dict = apply_market_source_schema(schema_dict, agent_num)
                if agent_num == 7:
                    priority = ('assumption_reconciliation', 'market_context_assessment',
                                'recommendation', 'scenario_triggers', 'next_catalysts',
                                'reasoning_steps')
                    properties = schema_dict.get('properties', {})
                    schema_dict['propertyOrdering'] = [key for key in priority if key in properties] + [key for key in properties if key not in priority and key != 'analysis_markdown'] + (['analysis_markdown'] if 'analysis_markdown' in properties else [])
                config_kwargs["response_schema"] = schema_dict
            except Exception:
                # Fall back to passing the class directly if schema extraction fails.
                config_kwargs["response_schema"] = response_schema_cls
    if uses_structured_response:
        function_tools = []
    if function_tools:
        config_kwargs["tools"] = function_tools
        config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(maximum_remote_calls=6)

    try:
        return types.GenerateContentConfig(**config_kwargs)
    except TypeError:
        if "response_schema" in config_kwargs:
            config_kwargs.pop("response_schema", None)
            try:
                return types.GenerateContentConfig(**config_kwargs)
            except TypeError:
                pass
        config_kwargs.pop("response_mime_type", None)
        config_kwargs.pop("automatic_function_calling", None)
        config_kwargs.pop("tools", None)
        return types.GenerateContentConfig(**config_kwargs)


def agent_request_budget_options(agent_num: int) -> dict:
    """Reserve the SDK tool loop's upper bound, including its first request."""
    config = build_generation_config(agent_num)
    automatic = getattr(config, "automatic_function_calling", None)
    if not automatic or automatic.disable:
        return {}
    return {"request_units": max(1, int(automatic.maximum_remote_calls or 1))}


def _response_text(response) -> str:
    return response_text(response)


def google_safe_agent_system_instruction(agent_num: int, model_id: str) -> str:
    system_instruction = SYSTEM_PROMPTS.get(agent_num, "")
    if agent_num == 6:
        system_instruction += _AGENT6_COMPLETION_INSTRUCTION
        system_instruction += (
            "\n\nAgent6證據優先辯論契約：多頭/空頭是比較假設的功能性角色，不是強迫站隊。"
            "缺證據時，多頭可承認條件尚未成立，空頭亦不得把風險可能性當已發生。"
            "每輪都把已觀測事實、條件式解釋、反方挑戰與尚缺證據分開；"
            "新聞標題不能證實護城河、定價權、客戶集中、轉型成功或確定收益；"
            "非同期間同口徑的同業比率不能推出成本/定價競爭優勢。"
            "負FCF不能推出高速擴張、備料動機或DCF理論上不能使用；"
            "法人買賣超不能推出信心、動機或估值折價原因。"
            "不得先用粗體標題斷言因果再用後文免責；主持人必須保留每個未核實前提。"
            "官方財務金額每次須有獨立完整的公司、個別範圍、TWD與精確起訖日期，"
            "可直接引用提供的完整官方reference作為獨立段落；不能在同段混入vendor或推測。"
            "其餘辯論段落以證據的含義與可證偽條件分析，不能以省略角色內容或虛構數字完成格式。"
        )
    elif agent_num == 7:
        system_instruction += _AGENT7_COMPLETION_INSTRUCTION
        system_instruction += (
            "\n\n完整JSON的輸出順序：先assumption_reconciliation五列與總狀態，再market_context_assessment、"
            "recommendation、scenario_triggers、next_catalysts、reasoning_steps，最後analysis_markdown與結尾大括號。"
            "五列引文優先使用當前quote_ref並保留空quote，由伺服器還原原句；rationale精確說明差異或缺口，"
            "不要在正文再逐字重複五列或原始財報表。analysis_markdown精煉整合支持/反證/限制，保留模式必要章節。"
            "不得省略任一必要欄位、引用或反證來縮短，不能延續上次截斷JSON；重新輸出完整候選。"
        )
    elif agent_num == 11:
        from industry_output_completion import industry_instruction
        system_instruction += industry_instruction()
    elif agent_num in {3, 4, 14, 21}:
        system_instruction += (
            "\n\n評估完整性契約：只輸出完整 JSON，先完成 schema 必要欄位與結尾大括號。"
            "正文精煉整合，不重貼原始表格或重複 JSON 推論；必要證據與品質規則優先於篇幅。"
            "護城河各維度、三情境價格、估值理由及風險須實際評估，不能以省略欄位代替資料不足。"
            "確實缺少證據時保留 null 與具體原因，不能補零、用現價或任意倍率補造目標。"
            "DCF 不可用不代表其他方法必然可用；相對估值同樣須有本次可驗證來源、期間、公式與假設。"
        )
    elif agent_num == 16:
        system_instruction += _AGENT16_COMPLETION_INSTRUCTION
    elif agent_num == 19:
        system_instruction += _AGENT19_COMPLETION_INSTRUCTION
        system_instruction += _agent19_recommendation_contract_instruction()
    elif agent_num in {22, 23}:
        system_instruction += ("\n\n證據備忘錄完整性契約：只輸出完整 JSON 與結尾大括號，保留 as_of_date、confidence、"
                               "evidence_items、analysis_markdown 四個必要欄位。每項證據必須有 finding、source_refs、"
                               "freshness_note、counterevidence；引用只用實際來源路徑，明示資料日期、期間、單位與限制。"
                               "正文精煉整合支持、反證、兩週觀察與失效條件；不得僅填資料不足、重貼原始表格或逐字重複前序分析。"
                               "資料有缺口時具體交代缺少什麼及可驗證的重新評估條件，不補造資料或保證上漲。")
    elif agent_num == 24:
        system_instruction += ("\n\n完整性契約：只輸出完整 JSON。先完成八個核心欄位、三組來源引用及結尾大括號，"
                               "不要重貼原始資料或附加長篇正文；來源只能引用本次完整可見 trade-source 區塊，"
                               "沒有可驗證來源時明示 Neutral 與具體缺口，不得為完成欄位補造引用或价格。")
    elif "gemini-3-flash-preview" in model_id:
        system_instruction += "\n\nIMPORTANT: You are operating as a fallback model. You MUST provide a comprehensive, highly detailed, and complete analysis. Ensure your response is sufficiently long and detailed to form a formal report section. Do not provide a short or truncated response."
    return sanitize_google_system_instruction(system_instruction)


def _generate_content(api_key: str, model_id: str, agent_num: int, prompt: str):
    config = build_generation_config(agent_num, google_safe_agent_system_instruction(agent_num, model_id))
    config = apply_model_generation_policy(config, model_id, agent_num)
    return generate_content(api_key, model_id, prompt, config)


def apply_model_generation_policy(config, model_id: str, agent_num: int | None = None):
    level = _thinking_level(agent_num, model_id)
    if level is not None:
        return config.model_copy(update={"thinking_config": types.ThinkingConfig(thinking_level=level)})
    return config


def estimate_agent_input_tokens(agent_num: int, model_id: str, prompt: str) -> int:
    config = build_generation_config(agent_num, google_safe_agent_system_instruction(agent_num, model_id))
    values = config.model_dump(exclude_none=True)
    input_config = {key: value for key, value in values.items() if key in {"system_instruction", "response_schema", "tools"}}
    return estimate_input_tokens(prompt + json.dumps(input_config, ensure_ascii=False, default=str))


async def _generate_content_async(api_key: str, model_id: str, agent_num: int, prompt: str):
    config = build_generation_config(agent_num, google_safe_agent_system_instruction(agent_num, model_id))
    config = apply_model_generation_policy(config, model_id, agent_num)
    return await generate_content_async(api_key, model_id, prompt, config)


async def _generate_content_stream_async(api_key: str, model_id: str, agent_num: int, prompt: str, *, on_delta=None):
    config = build_generation_config(agent_num, google_safe_agent_system_instruction(agent_num, model_id))
    config = apply_model_generation_policy(config, model_id, agent_num)
    return await generate_content_stream_async(api_key, model_id, prompt, config, on_delta=on_delta)


async def _await_with_agent_timeout(coro, *, model_id: str, timeout_seconds: float | None = None):
    timeout = float(LLM_AGENT_CALL_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds)
    if timeout <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise AgentTransientError(f"LLM timeout after {timeout:.1f}s for model {model_id}") from exc
