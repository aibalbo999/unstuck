# ============================================================
# agent_runner.py - 連續式 Agent 執行引擎
# 包含：API Key 輪調、速率限制、7個分析 Agent 的 Prompt
# ============================================================

import json
import asyncio
import time
import re
import inspect
from contextlib import suppress
from datetime import date, datetime
from typing import Any, Optional
from google import genai
from google.genai import types
from config import API_KEYS, AGENT_MODELS, MODEL_FALLBACKS, RPM_LIMITS, INTER_AGENT_DELAY, API_KEY_SETUP_MESSAGE
from financial_data import format_data_for_prompt
from financial_tools import calculate_cagr, calculate_dcf, calculate_wacc
from prompt_loader import load_agent_prompt_config


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API Key 輪調管理器
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class KeyRotator:
    """
    API Key 輪調管理器
    - 追蹤每個 Key + Model 組合的呼叫時間
    - 自動選擇未超過 RPM 的 Key
    - 超過限制時自動等待
    """
    
    def __init__(self, keys: list):
        if not keys:
            raise RuntimeError(API_KEY_SETUP_MESSAGE)
        self.keys = keys
        self.index = 0
        # 格式：{key: {model: [timestamp, ...]}}
        self.call_log: dict = {k: {} for k in keys}
    
    def _clean_old_calls(self, key: str, model: str):
        """清除超過 60 秒的通話記錄"""
        now = time.time()
        if model not in self.call_log[key]:
            self.call_log[key][model] = []
        self.call_log[key][model] = [
            t for t in self.call_log[key][model] 
            if now - t < 60
        ]
    
    def get_key(self, model: str) -> str:
        """取得可用的 API Key（自動輪調 + 速率限制）"""
        rpm_limit = RPM_LIMITS.get(model, 5)
        
        # 嘗試所有 Key 找到可用的
        for attempt in range(len(self.keys)):
            key = self.keys[self.index]
            self.index = (self.index + 1) % len(self.keys)
            
            self._clean_old_calls(key, model)
            current_calls = len(self.call_log[key][model])
            
            if current_calls < rpm_limit:
                self.call_log[key][model].append(time.time())
                key_preview = f"{key[:8]}...{key[-4:]}"
                print(f"    🔑 使用 Key {self.keys.index(key)+1}/{len(self.keys)} ({key_preview})")
                return key
        
        # 所有 Key 都已超限，等待最早的呼叫過期
        print(f"    ⏳ 所有 API Key 已達 RPM 限制，等待 60 秒...")
        time.sleep(60)
        return self.get_key(model)

    async def async_get_key(self, model: str) -> str:
        """非同步取得可用 API Key，避免在 async pipeline 中阻塞 event loop。"""
        rpm_limit = RPM_LIMITS.get(model, 5)

        for attempt in range(len(self.keys)):
            key = self.keys[self.index]
            self.index = (self.index + 1) % len(self.keys)

            self._clean_old_calls(key, model)
            current_calls = len(self.call_log[key][model])

            if current_calls < rpm_limit:
                self.call_log[key][model].append(time.time())
                key_preview = f"{key[:8]}...{key[-4:]}"
                print(f"    🔑 使用 Key {self.keys.index(key)+1}/{len(self.keys)} ({key_preview})")
                return key

        print(f"    ⏳ 所有 API Key 已達 RPM 限制，非同步等待 60 秒...")
        await asyncio.sleep(60)
        return await self.async_get_key(model)
    
    def get_status(self) -> dict:
        """取得各 Key 的使用狀態"""
        now = time.time()
        status = {}
        for i, key in enumerate(self.keys):
            key_name = f"Key-{i+1}"
            status[key_name] = {}
            for model, calls in self.call_log[key].items():
                recent = [t for t in calls if now - t < 60]
                status[key_name][model] = len(recent)
        return status


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Prompt 設定（外部 JSON）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROMPT_CONFIG = load_agent_prompt_config()
SYSTEM_PROMPTS = {int(k): v for k, v in PROMPT_CONFIG["system_prompts"].items()}
ANALYSIS_PROMPTS = {int(k): v for k, v in PROMPT_CONFIG["analysis_prompts"].items()}
FINAL_AUDIT_REPAIR_PASSES = 2
CONTEXT_DIGEST_TARGET_AGENTS = {4, 7}


def get_agent_function_tools(agent_num: int) -> list:
    """Return Python function tools for agents that need deterministic math."""
    if agent_num == 2:
        return [calculate_cagr]
    if agent_num == 4:
        return [calculate_cagr, calculate_wacc, calculate_dcf]
    return []


def get_agent_model_sequence(agent_num: int) -> list[str]:
    """Return primary model plus configured fallbacks without duplicates."""
    primary = AGENT_MODELS[agent_num]
    sequence = [primary, *MODEL_FALLBACKS.get(primary, [])]
    return list(dict.fromkeys(model for model in sequence if model))


def is_quota_or_rate_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return (
        "429" in normalized
        or "quota" in normalized
        or "rate" in normalized
        or "resource_exhausted" in normalized
        or "resource exhausted" in normalized
    )


def describe_quota_or_rate_error(error: Any) -> str:
    """Return a concise, secret-safe description of a Google quota/rate error."""
    raw = str(error)
    details = getattr(error, "details", None)
    code = getattr(error, "code", None)
    status = getattr(error, "status", None)
    message = getattr(error, "message", None)

    found: list[str] = []
    seen: set[str] = set()

    def add(label: str, value: Any):
        if value is None or value == "":
            return
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        text = f"{label}={value}"
        if text not in seen:
            seen.add(text)
            found.append(text)

    def walk(value: Any):
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in {"quotametric", "quotaid", "quotavalue", "retrydelay", "reason"}:
                    add(key, item)
                elif lowered == "quotadimensions" and isinstance(item, dict):
                    for dim_key in ("model", "location"):
                        if dim_key in item:
                            add(f"quotaDimensions.{dim_key}", item[dim_key])
                elif lowered == "metadata" and isinstance(item, dict):
                    for meta_key, meta_value in item.items():
                        meta_lowered = str(meta_key).lower()
                        if "quota" in meta_lowered and meta_lowered != "consumer":
                            add(f"metadata.{meta_key}", meta_value)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(details)

    signature = " ".join([raw, json.dumps(details, ensure_ascii=False) if details else ""]).lower()
    if "tokensperminute" in signature or "tokens_per_minute" in signature or "tpm" in signature:
        condition = "每分鐘 token 額度（TPM）"
    elif "requestsperminute" in signature or "requests_per_minute" in signature or "rpm" in signature:
        condition = "每分鐘請求額度（RPM）"
    elif "requestsperday" in signature or "requests_per_day" in signature or "perday" in signature:
        condition = "每日請求額度（RPD）"
    elif "free_tier" in signature or "free-tier" in signature or "freetier" in signature:
        condition = "免費層/專案配額"
    else:
        condition = "Google API 配額或速率限制（未提供細項）"

    summary_parts = []
    if code or status:
        summary_parts.append(" ".join(str(x) for x in (code, status) if x))
    if message:
        summary_parts.append(str(message))
    summary_parts.append(condition)
    summary_parts.extend(found[:6])

    return "；".join(summary_parts)


def is_missing_model_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return "404" in normalized or "not found" in normalized


def is_agent_execution_failure(text: str) -> bool:
    return bool(text and text.startswith("[Agent ") and "執行失敗" in text)


OUTPUT_CLEANLINESS_RULE = """
【正式報告輸出契約】
- 只輸出可直接放進正式研究報告的內容。
- 不重述角色設定、系統提示詞、資料摘要規則、任務清單、前序摘要規則、草稿或反思文字。
- 除必要財務術語、公司名稱與 JSON key 外，使用繁體中文。
- 財務算式只呈現必要的可讀摘要；內部驗算過程不放入正式報告。
- 杜邦分析只使用同期間、同口徑資料；若資料摘要提供「同期間年度杜邦恒等式」，以該句作為唯一拆解依據。
"""

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

    lines = [
        "🚨【公司身分一致性硬性規則】",
        f"- 本次唯一分析標的：{ticker}，股票代號 {stock_id}，公司名稱「{official_name}」。",
        f"- 報告中凡稱呼本公司，必須使用「{official_name}」或「{ticker}」；不得自行改成同業公司名稱。",
        "- 可比較同業只能作為同業比較，必須標示其代號/公司名，不得把同業的太陽能、儲能、客戶、產能、專案或商業模式套用到本公司。",
        "- 若前序 Agent 摘要與本段身分鎖定衝突，請直接忽略前序錯誤並以本段為準。",
    ]
    if legal_name:
        lines.append(f"- 法定/官方名稱參考：{legal_name}。")
    if english_names:
        lines.append(f"- 英文名稱參考：{', '.join(english_names[:3])}。")
    if forbidden_aliases:
        lines.append(f"- 特別禁止把以下名稱當作 {ticker}：{', '.join(forbidden_aliases)}。")

    return "\n".join(lines)


STRUCTURED_AGENT_INSTRUCTIONS = {
    3: """
🚨【結構化輸出硬性規則】
請只輸出合法 JSON，不要 Markdown code fence，不要前言，不要附註。
JSON schema:
{
  "moat_scores": {
    "品牌影響力": number,
    "網路效應": number,
    "轉換成本": number,
    "成本優勢": number,
    "專利技術": number,
    "整體護城河": number
  },
  "analysis_markdown": "繁體中文正式報告正文"
}
所有分數必須是 1-10 的數字。analysis_markdown 不可重複系統提示詞或草稿筆記。
""",
    4: """
🚨【結構化輸出硬性規則】
請只輸出合法 JSON，不要 Markdown code fence，不要前言，不要附註。
JSON schema:
{
  "price_targets": {
    "熊市情境": number,
    "基本情境": number,
    "牛市情境": number
  },
  "valuation_summary": {
    "primary_method": "normalized_dcf|relative_valuation|blended",
    "uses_market_value_wacc": true,
    "uses_normalized_fcf": true,
    "double_counting_check": "繁體中文一句話"
  },
  "analysis_markdown": "繁體中文正式報告正文"
}
目標價必須是完整股價數字，例如 5249，不可輸出 5 來代表 5,249。analysis_markdown 不可把 DCF 與 EPS×P/E 宣稱為完全吻合。
""",
    7: """
🚨【結構化輸出硬性規則】
請只輸出合法 JSON，不要 Markdown code fence，不要前言，不要附註。
JSON schema:
{
  "recommendation": {
    "建議": "買入|持有|避免",
    "短期目標（3個月）": "NT$完整數字",
    "中期目標（6個月）": "NT$完整數字",
    "長期目標（12個月）": "NT$完整數字",
    "長期潛力（5年）": "NT$完整數字",
    "信心指數": "1-10/10"
  },
  "analysis_markdown": "繁體中文正式決策備忘錄正文"
}
所有目標價都必須與 Agent 4 的三情境估值同量級，不可發生千元被縮成個位數。
""",
}


def build_structured_output_instruction(agent_num: int) -> str:
    """Return JSON-only output instructions for agents with machine-read fields."""
    return STRUCTURED_AGENT_INSTRUCTIONS.get(agent_num, "")


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
    """Extract text from a Google GenAI response without leaking object internals."""
    try:
        text = getattr(response, "text", None)
    except Exception:
        text = None
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    parts = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(part_text)
    return "\n".join(parts)


def _generate_content(api_key: str, model_id: str, agent_num: int, prompt: str):
    """Call Google GenAI synchronously with an isolated per-key client."""
    client = genai.Client(api_key=api_key)
    try:
        return client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=build_generation_config(agent_num, SYSTEM_PROMPTS[agent_num]),
        )
    finally:
        with suppress(Exception):
            client.close()


async def _generate_content_async(api_key: str, model_id: str, agent_num: int, prompt: str):
    """Call Google GenAI through the async client implementation."""
    client = genai.Client(api_key=api_key)
    try:
        return await client.aio.models.generate_content(
            model=model_id,
            contents=prompt,
            config=build_generation_config(agent_num, SYSTEM_PROMPTS[agent_num]),
        )
    finally:
        with suppress(Exception):
            await client.aio.aclose()
        with suppress(Exception):
            client.close()


def _extract_json_payload(raw_text: str) -> Optional[dict]:
    """Parse JSON responses, tolerating accidental code fences."""
    if not raw_text:
        return None

    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None


def _coerce_number(value, minimum=None, maximum=None):
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.\-]", "", value.replace(",", ""))
        value = cleaned
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return round(number, 2)


def normalize_structured_output(agent_num: int, payload: Optional[dict]) -> Optional[dict]:
    """Validate and normalize JSON payloads from structured agents."""
    if not isinstance(payload, dict):
        return None

    if agent_num == 3:
        raw_scores = payload.get("moat_scores", {})
        allowed = ["品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河"]
        scores = {}
        for key in allowed:
            score = _coerce_number(raw_scores.get(key), 1, 10)
            if score is not None:
                scores[key] = score
        if not scores:
            return None
        return {
            "moat_scores": scores,
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num == 4:
        raw_targets = payload.get("price_targets", {})
        target_map = {"熊": "熊市情境", "基本": "基本情境", "Base": "基本情境", "牛": "牛市情境"}
        targets = {}
        for raw_key, raw_value in raw_targets.items():
            canonical = None
            for marker, mapped in target_map.items():
                if marker in str(raw_key):
                    canonical = mapped
                    break
            if not canonical:
                continue
            price = _coerce_number(raw_value, 0, None)
            if price is not None:
                targets[canonical] = price
        if not targets:
            return None
        return {
            "price_targets": targets,
            "valuation_summary": payload.get("valuation_summary", {}) if isinstance(payload.get("valuation_summary"), dict) else {},
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num == 7:
        raw_rec = payload.get("recommendation", {})
        if not isinstance(raw_rec, dict) or not raw_rec:
            return None
        return {
            "recommendation": {str(k).strip(): str(v).strip() for k, v in raw_rec.items()},
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    return None


def structured_output_to_report_text(agent_num: int, structured: dict, fallback_text: str = "") -> str:
    """Convert parsed JSON into the legacy report text expected by renderers."""
    body = structured.get("analysis_markdown") or fallback_text

    if agent_num == 3:
        scores = structured.get("moat_scores", {})
        score_lines = "\n".join(f"{key}: {scores[key]}" for key in scores)
        return f"[護城河評分]\n{score_lines}\n[/護城河評分]\n\n{body}".strip()

    if agent_num == 4:
        targets = structured.get("price_targets", {})
        order = ["熊市情境", "基本情境", "牛市情境"]
        price_lines = "\n".join(
            f"{key}: NT${targets[key]:,.0f}" for key in order if key in targets
        )
        summary = structured.get("valuation_summary", {})
        summary_text = ""
        if summary:
            summary_text = "\n\n## 結構化估值檢查\n" + "\n".join(
                f"- {key}: {value}" for key, value in summary.items()
            )
        return f"[目標股價]\n{price_lines}\n[/目標股價]\n\n{body}{summary_text}".strip()

    if agent_num == 7:
        rec = structured.get("recommendation", {})
        rec_lines = "\n".join(f"{key}: {value}" for key, value in rec.items())
        return f"[投資建議]\n{rec_lines}\n[/投資建議]\n\n{body}".strip()

    return fallback_text


def price_targets_have_unit_error(targets: dict, current_price) -> bool:
    """Detect NT$5-style target prices when the stock trades in the hundreds/thousands."""
    if not isinstance(current_price, (int, float)) or current_price <= 100:
        return False
    prices = [value for value in targets.values() if isinstance(value, (int, float))]
    return bool(prices) and any(price < current_price * 0.05 for price in prices)


def process_agent_response(agent_num: int, raw_text: str, context: dict) -> str:
    """Persist JSON structured output and return report-ready text."""
    if agent_num not in STRUCTURED_AGENT_INSTRUCTIONS:
        return raw_text or ""

    payload = _extract_json_payload(raw_text or "")
    structured = normalize_structured_output(agent_num, payload)
    if not structured:
        return raw_text or ""

    if agent_num == 4:
        current_price = context.get("data", {}).get("current_price")
        targets = structured.get("price_targets", {})
        if price_targets_have_unit_error(targets, current_price):
            warning = (
                "## 系統品質檢查警示\n"
                "- Agent 4 結構化目標價疑似發生單位縮寫錯誤，已拒絕寫入圖表資料。"
                "請重跑或檢查估值正文中的完整股價數字。"
            )
            body = structured.get("analysis_markdown") or raw_text or ""
            return f"{body}\n\n{warning}".strip()

    context.setdefault("structured_outputs", {})[agent_num] = structured
    return structured_output_to_report_text(agent_num, structured, raw_text)


def build_numeric_tool_instruction(agent_num: int) -> str:
    """Prompt agents with deterministic tool usage guidance."""
    if agent_num == 2:
        return (
            "【數值工具使用規則】\n"
            "- CAGR 請呼叫 calculate_cagr，或引用財務 JSON 中 deterministic_financial_tool_results.calculations.revenue_cagr。\n"
            "- FCF/淨利、年度成長率與杜邦恒等式應以 JSON 欄位與工具結果為準，不自行心算替換單位。\n"
            "- 正式輸出可列簡短公式摘要，但不要輸出內部驗算草稿。"
        )
    if agent_num == 4:
        return (
            "【估值工具使用規則】\n"
            "- WACC 權重請呼叫 calculate_wacc，或引用 deterministic_financial_tool_results.calculations.market_value_wacc_default。\n"
            "- DCF 情境請呼叫 calculate_dcf，或引用 deterministic_financial_tool_results.calculations.dcf_scenarios_default。\n"
            "- 若自行調整成長率、折現率或 normalized FCF，需清楚列出參數，計算結果以工具回傳值為準。\n"
            "- 本益比估值與 DCF 必須分開呈現；正式輸出只保留必要算式摘要。"
        )
    return ""


def _format_structured_outputs_for_context(context: dict) -> str:
    structured = context.get("structured_outputs", {}) or {}
    if not structured:
        return "{}"
    try:
        return json.dumps(structured, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        return str(structured)


def _build_context_digest_prompt(current_agent: int, context: dict) -> str:
    target = AGENT_NAMES.get(current_agent, f"Agent {current_agent}")
    previous = _format_previous(context, current_agent, include_digest=False)
    return (
        "請擔任投資研究提煉 Agent，將前序分析整理成給下一位分析師使用的結構化摘要。\n"
        f"下一位分析師：Agent {current_agent} {target}\n\n"
        "輸出請使用合法 JSON，不要 Markdown code fence。JSON schema:\n"
        "{\n"
        '  "decision_relevant_facts": ["..."],\n'
        '  "financial_cross_checks": ["..."],\n'
        '  "valuation_or_recommendation_implications": ["..."],\n'
        '  "risks_and_counterarguments": ["..."],\n'
        '  "open_data_quality_issues": ["..."]\n'
        "}\n\n"
        "已解析的結構化輸出：\n"
        f"{_format_structured_outputs_for_context(context)}\n\n"
        "完整前序分析（未截斷）：\n"
        f"{previous}"
    )


def _build_digest_generation_config():
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=4096,
        response_mime_type="application/json",
        system_instruction=(
            "你是金融研究流程中的提煉 Agent。你的任務是保留決策所需事實、數字、假設、"
            "衝突與風險，不新增外部資料，不替下一個 Agent 下結論。"
        ),
    )


def _generate_context_digest_content(api_key: str, model_id: str, prompt: str):
    client = genai.Client(api_key=api_key)
    try:
        return client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=_build_digest_generation_config(),
        )
    finally:
        with suppress(Exception):
            client.close()


async def _generate_context_digest_content_async(api_key: str, model_id: str, prompt: str):
    client = genai.Client(api_key=api_key)
    try:
        return await client.aio.models.generate_content(
            model=model_id,
            contents=prompt,
            config=_build_digest_generation_config(),
        )
    finally:
        with suppress(Exception):
            await client.aio.aclose()
        with suppress(Exception):
            client.close()


def _normalize_digest_text(text: str, current_agent: int, context: dict) -> str:
    payload = _extract_json_payload(text or "")
    if isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(
        _fallback_context_digest_payload(current_agent, context, reason="提煉 Agent 未回傳可解析 JSON"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _fallback_context_digest_payload(current_agent: int, context: dict, reason: str) -> dict:
    completed = sorted(context.get("analyses", {}).keys())
    return {
        "digest_type": "deterministic_fallback",
        "reason": reason,
        "target_agent": current_agent,
        "completed_agents": completed,
        "structured_outputs": context.get("structured_outputs", {}),
        "instruction": "提煉摘要不可用時，下一個 Agent 必須直接閱讀下方完整前序分析；系統不再截斷前序內容。",
    }


def ensure_context_digest(agent_num: int, context: dict, rotator: KeyRotator):
    """Run a lightweight summarization agent before high-dependency agents."""
    if agent_num not in CONTEXT_DIGEST_TARGET_AGENTS:
        return
    digests = context.setdefault("context_digests", {})
    if agent_num in digests:
        return

    prompt = _build_context_digest_prompt(agent_num, context)
    for model_id in get_agent_model_sequence(agent_num):
        try:
            response = _generate_context_digest_content(rotator.get_key(model_id), model_id, prompt)
            digests[agent_num] = _normalize_digest_text(_response_text(response), agent_num, context)
            print(f"  🧾 Agent {agent_num} 前序提煉摘要完成。")
            return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            if is_quota_or_rate_error(str(exc)):
                print(f"  ⏭️  提煉 Agent 遇到配額限制，改用 fallback 摘要：{describe_quota_or_rate_error(exc)[:120]}")
                break
            print(f"  ⚠️  提煉 Agent 失敗，改用 fallback 摘要：{str(exc)[:120]}")
            break

    digests[agent_num] = json.dumps(
        _fallback_context_digest_payload(agent_num, context, reason="提煉 Agent 呼叫失敗"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


async def ensure_context_digest_async(agent_num: int, context: dict, rotator: KeyRotator):
    """Async summarization agent before Agent 4/7."""
    if agent_num not in CONTEXT_DIGEST_TARGET_AGENTS:
        return
    digests = context.setdefault("context_digests", {})
    if agent_num in digests:
        return

    prompt = _build_context_digest_prompt(agent_num, context)
    for model_id in get_agent_model_sequence(agent_num):
        try:
            api_key = await rotator.async_get_key(model_id)
            response = await _generate_context_digest_content_async(api_key, model_id, prompt)
            digests[agent_num] = _normalize_digest_text(_response_text(response), agent_num, context)
            print(f"  🧾 Agent {agent_num} 前序提煉摘要完成。")
            return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            if is_quota_or_rate_error(str(exc)):
                print(f"  ⏭️  提煉 Agent 遇到配額限制，改用 fallback 摘要：{describe_quota_or_rate_error(exc)[:120]}")
                break
            print(f"  ⚠️  提煉 Agent 失敗，改用 fallback 摘要：{str(exc)[:120]}")
            break

    digests[agent_num] = json.dumps(
        _fallback_context_digest_payload(agent_num, context, reason="提煉 Agent 呼叫失敗"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def build_prompt(agent_num: int, data: dict, context: dict) -> str:
    """根據 Agent 編號建立分析提示詞。"""
    ticker = data["ticker"]
    name = data["company_name"]
    fin_data = format_data_for_prompt(data)
    prev = _format_previous(context, agent_num)
    identity_guard = build_company_identity_guard(data)
    numeric_tool_instruction = build_numeric_tool_instruction(agent_num)
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
        identity_guard,
        retry_instruction,
        audit_reflection_instruction,
        audit_retry_instruction,
        OUTPUT_CLEANLINESS_RULE,
    ]
    return "\n\n".join(part for part in prompt_parts if part)

def _format_previous(context: dict, current_agent: int, include_digest: bool = True) -> str:
    """格式化前序分析摘要"""
    analyses = context.get("analyses", {})
    if not analyses:
        return "（無前序分析）"
    
    agent_names = {
        1: "整體分析",
        2: "財務分析",
        3: "護城河評估",
        4: "估值分析",
        5: "成長潛力",
        6: "多空辯論",
    }
    
    parts = []
    digest = (context.get("context_digests", {}) or {}).get(current_agent)
    if include_digest and digest:
        parts.append(f"【提煉 Agent 結構化摘要】\n{digest}")
        parts.append("【完整前序分析（未截斷）】")

    for i in range(1, current_agent):
        if i in analyses:
            name = agent_names.get(i, f"Agent {i}")
            clean_analysis = strip_generated_audit_sections(str(analyses[i]))
            parts.append(f"【{name}】\n{clean_analysis}")
    
    return "\n\n".join(parts) if parts else "（無前序分析）"


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

    model_id = AGENT_MODELS[agent_num]
    prompt = build_prompt(agent_num, data, context)
    
    for attempt in range(max_retries):
        try:
            # 取得可用 API Key
            api_key = rotator.get_key(model_id)
            
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
                wait_time = 65 * (attempt + 1)
                quota_detail = describe_quota_or_rate_error(e)
                print(f"    ⏳ 配額/速率限制：{quota_detail[:160]}... 等待 {wait_time} 秒 ({attempt+1}/{max_retries})")
                time.sleep(wait_time)
            elif "404" in error_msg or "not found" in error_msg.lower():
                print(f"    ❌ 模型 {model_id} 不可用，嘗試備用模型...")
                # 嘗試備用模型
                backup_models = MODEL_FALLBACKS.get(model_id, [])
                for backup in backup_models:
                    try:
                        response = _generate_content(rotator.get_key(backup), backup, agent_num, prompt)
                        return process_agent_response(agent_num, _response_text(response), context)
                    except Exception:
                        continue
                return f"[Agent {agent_num} 執行失敗：模型不可用]"
            else:
                print(f"    ❌ 錯誤：{error_msg[:100]}... 重試 ({attempt+1}/{max_retries})")
                time.sleep(10 * (attempt + 1))
    
    # 如果重試皆失敗，自動降級/備援至最穩定的 gemini-3.5-flash
    print(f"    ⚠️ 模型 {model_id} 多次失敗，啟用備援機制 (gemini-3.5-flash)...")
    try:
        response = _generate_content(
            rotator.get_key("gemini-3.5-flash"),
            "gemini-3.5-flash",
            agent_num,
            prompt,
        )
        return process_agent_response(agent_num, _response_text(response), context)
    except Exception as e:
        if is_quota_or_rate_error(str(e)):
            return f"[Agent {agent_num} 執行失敗且備援無效：{describe_quota_or_rate_error(e)[:120]}]"
        return f"[Agent {agent_num} 執行失敗且備援無效：{str(e)[:120]}]"


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
    model_sequence = get_agent_model_sequence(agent_num)
    last_error = ""

    for model_index, model_id in enumerate(model_sequence):
        if model_index > 0:
            print(f"    🔁 切換備援模型：{model_id}")

        attempts_for_model = max(max_retries, len(rotator.keys)) if model_index == 0 else len(rotator.keys)

        for attempt in range(attempts_for_model):
            try:
                api_key = await rotator.async_get_key(model_id)

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

AGENT_NAMES = {
    1: "商業模式與整體分析",
    2: "五年財務深度分析",
    3: "競爭護城河評估",
    4: "投資銀行估值分析",
    5: "未來成長潛力",
    6: "多空辯論",
    7: "最終投資決策",
}


def _safe_float(value) -> Optional[float]:
    if value is None or value == "N/A":
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("x", "").replace("%", "").strip()
            if not value:
                return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _relative_gap(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1.0)


def _money_text_to_billion(raw_num: str, unit: str = "") -> Optional[float]:
    value = _safe_float(raw_num)
    if value is None:
        return None
    unit = unit or ""
    if unit == "億":
        return value / 10
    if unit == "兆":
        return value * 1000
    return value


def _has_data_quality_caveat(normalized: str) -> bool:
    return any(
        word in normalized
        for word in [
            "資料品質警示",
            "口徑差異",
            "口徑不同",
            "口徑偏差",
            "口徑互斥",
            "不可直接",
            "不得直接",
            "不能直接",
            "不應直接",
            "僅列為警示",
            "僅供對照",
            "需人工複核",
            "同期間年度",
            "年度杜邦恒等式",
        ]
    )


def strip_generated_audit_sections(text: str) -> str:
    """Remove system-generated warning/audit tails before re-validating model text."""
    if not text:
        return ""
    generated_headers = [
        "\n## 系統品質檢查警示",
        "\n## 系統身分一致性警示",
        "\n## 系統最終稽核",
        "\n### 系統品質檢查警示",
        "\n### 系統身分一致性警示",
        "\n### 系統最終稽核",
    ]
    indexes = [text.find(header) for header in generated_headers if text.find(header) != -1]
    if not indexes:
        return text
    return text[:min(indexes)].rstrip()


def _extract_revenue_mentions(normalized: str) -> list[dict]:
    mentions = []
    pattern = re.compile(
        r"(?P<label>TTM|LTM|20\d{2}年|最新年度|前一年度)?"
        r"營收(?:為|=|:|：|達|約)?(?:NT\$?)?"
        r"(?P<num>\d+(?:\.\d+)?)(?P<unit>B|億|兆)?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(normalized):
        value_b = _money_text_to_billion(match.group("num"), match.group("unit") or "")
        if value_b is None:
            continue
        mentions.append({
            "label": match.group("label") or "",
            "value_b": value_b,
            "start": match.start(),
        })
    return mentions


def _extract_first_money_billion(pattern: str, normalized: str) -> Optional[float]:
    match = re.search(pattern, normalized, flags=re.IGNORECASE)
    if not match:
        return None
    return _money_text_to_billion(match.group("num"), match.groupdict().get("unit") or "")


def _extract_first_percent(pattern: str, normalized: str) -> Optional[float]:
    match = re.search(pattern, normalized, flags=re.IGNORECASE)
    if not match:
        return None
    return _safe_float(match.group("num"))


def _append_deep_numeric_consistency_issues(issues: list[str], normalized: str):
    """Catch arithmetic contradictions that do not depend on a named rule."""
    revenue_mentions = _extract_revenue_mentions(normalized)
    revenue_growth_claim = _extract_first_percent(
        r"營收(?:年增率|成長率|年增|成長|增長|暴增)(?:高達|達|為|=|:|：|約)?(?P<num>-?\d+(?:\.\d+)?)%",
        normalized,
    )
    if revenue_growth_claim is not None and len(revenue_mentions) >= 2:
        current = next((item for item in revenue_mentions if item["label"].upper() in {"TTM", "LTM"}), revenue_mentions[-1])
        base_candidates = [item for item in revenue_mentions if item is not current and item["value_b"] > 0]
        if base_candidates:
            base = base_candidates[-1] if current["start"] > base_candidates[-1]["start"] else base_candidates[0]
            expected_growth = (current["value_b"] / base["value_b"] - 1) * 100
            if abs(revenue_growth_claim - expected_growth) > max(10, abs(expected_growth) * 0.35):
                issues.append(
                    "算術一致性紅線：報告列出的營收基期與 TTM/最新營收推不出所宣稱的營收成長率；"
                    f"依文中數字約為 {expected_growth:.1f}%，不是 {revenue_growth_claim:.1f}%。"
                )

    revenue_b = next((item["value_b"] for item in revenue_mentions if item["label"].upper() in {"TTM", "LTM"}), None)
    if revenue_b is None and revenue_mentions:
        revenue_b = revenue_mentions[0]["value_b"]
    margin_pct = _extract_first_percent(r"淨利率(?:為|=|:|：|約|高達)?(?P<num>-?\d+(?:\.\d+)?)%", normalized)
    market_cap_b = _extract_first_money_billion(
        r"市值(?:為|=|:|：|約)?(?:NT\$?)?(?P<num>\d+(?:\.\d+)?)(?P<unit>B|億|兆)?",
        normalized,
    )
    pe = _extract_first_percent(
        r"(?:TTM)?(?:P/E|本益比)(?:為|=|:|：|約)?(?P<num>\d+(?:\.\d+)?)x?",
        normalized,
    )
    if revenue_b and margin_pct is not None and market_cap_b and pe and pe > 0:
        implied_income_from_margin = revenue_b * margin_pct / 100
        implied_income_from_pe = market_cap_b / pe
        if _relative_gap(implied_income_from_margin, implied_income_from_pe) > 0.25:
            issues.append(
                "估值一致性紅線：文中 TTM 營收×淨利率 推回淨利，與 市值÷P/E 推回淨利差異超過 25%；"
                "必須標示資料口徑互斥並採用校準後口徑。"
            )

    if not _has_data_quality_caveat(normalized):
        roe = _extract_first_percent(r"ROE(?:為|=|:|：|約)?(?P<num>-?\d+(?:\.\d+)?)%", normalized)
        roa = _extract_first_percent(r"ROA(?:為|=|:|：|約)?(?P<num>-?\d+(?:\.\d+)?)%", normalized)
        equity_multiplier_match = re.search(
            r"權益乘數(?:為|=|:|：|約)?(?P<num>\d+(?:\.\d+)?)(?:x|倍)?",
            normalized,
            flags=re.IGNORECASE,
        )
        equity_multiplier = _safe_float(equity_multiplier_match.group("num")) if equity_multiplier_match else None
        if roe is not None and roa is not None and equity_multiplier is not None:
            implied_roe = roa * equity_multiplier
            if abs(implied_roe - roe) > max(3, abs(roe) * 0.15):
                issues.append(
                    "杜邦數值一致性紅線：文中 ROA×權益乘數 與 ROE 差距過大；"
                    "若不是同期間同口徑資料，不可作為杜邦恒等式拆解。"
                )


def validate_analysis_output(agent_num: int, text: str, data: Optional[dict] = None) -> list[str]:
    """檢查模型輸出是否踩到硬性財務邏輯紅線。"""
    issues = []
    normalized = re.sub(r"\s+", "", strip_generated_audit_sections(text or ""))
    data = data or {}

    has_dupont_gap = (
        ("ROA" in normalized)
        and ("權益乘數" in normalized)
        and any(word in normalized for word in ["差距", "落差", "不一致", "偏差"])
        and any(word in normalized for word in ["應付帳款", "非計息負債", "無息流動負債", "營運槓桿"])
    )
    if has_dupont_gap:
        issues.append(
            "杜邦分析紅線：同期間 ROE = ROA × 權益乘數（或淨利率 × 資產周轉 × 權益乘數）是恒等式；"
            "不同資料口徑造成的差距不得歸因於應付帳款或非計息負債。"
        )

    mixed_ttm_dupont = (
        "TTM" in normalized
        and "杜邦" in normalized
        and "資產周轉" in normalized
        and "權益乘數" in normalized
        and any(word in normalized for word in ["差距", "口徑", "不一致", "偏差"])
        and not _has_data_quality_caveat(normalized)
    )
    if mixed_ttm_dupont:
        issues.append(
            "杜邦分析紅線：不可把 Yahoo TTM ROE/ROA/淨利率與最新年度資產周轉率或權益乘數拼接成 TTM 杜邦公式；"
            "若資料口徑不同，應改用同期間年度杜邦恒等式或僅列資料品質警示。"
        )

    if agent_num == 4:
        dcf_pe_blend = (
            "DCF" in normalized
            and any(word in normalized for word in ["ForwardEPS", "預估EPS"])
            and any(word in normalized for word in ["完全吻合", "完全相符", "完全等於", "數學防呆"])
        )
        if dcf_pe_blend:
            issues.append(
                "估值方法紅線：DCF 與 EPS × P/E 是兩套不同估值法；P/E 乘法只能作相對估值交叉檢查，"
                "不得宣稱 DCF 必須與其完全吻合。"
            )

        book_value_wacc = (
            "WACC" in normalized
            and any(word in normalized for word in ["D/E", "負債權益比", "帳面"])
            and re.search(r"權益權重.{0,12}9[0-6]%", normalized)
        )
        if book_value_wacc:
            issues.append(
                "WACC 紅線：上市公司 WACC 權重應採市場價值資本結構；不可用帳面 D/E 直接推出股權權重。"
            )

    high_growth_fcf = (
        re.search(r"營收.{0,30}(?:成長|增加|提升|暴增).{0,12}(?:[5-9]\d|1\d\d)%", normalized)
        and (
            re.search(r"FCF.{0,20}(?:轉換率|/淨利).{0,12}(?:1\d\d|超過100|>100)%", normalized)
            or re.search(r"自由現金流.{0,20}(?:轉換率|/淨利).{0,12}(?:1\d\d|超過100|>100)%", normalized)
        )
    )
    fcf_has_caution = any(
        word in normalized
        for word in ["不可持續", "一次性", "異常", "需查核", "質疑", "預收", "營運資金", "資本支出", "CapEx", "遞延"]
    )
    if high_growth_fcf and not fcf_has_caution:
        issues.append(
            "FCF 品質紅線：硬體製造業在營收成長超過 50% 時仍有 FCF/淨利 >100%，不可視為常態；"
            "需拆解營運資金、預收款與 CapEx，DCF 應使用 normalized FCF。"
        )

    if agent_num in (4, 5, 7):
        aggressive_growth = re.search(r"營收.{0,30}(?:成長|增加|提升).{0,12}(?:[5-9]\d|1\d\d)%", normalized)
        no_capacity_cost = not any(word in normalized for word in ["CapEx", "資本支出", "折舊", "產能", "良率", "第二供應商"])
        if aggressive_growth and no_capacity_cost:
            issues.append(
                "製造業情境紅線：營收成長超過 50% 時，必須同步討論產能、CapEx、折舊、良率與客戶議價風險。"
            )

    if agent_num in (4, 7):
        high_multiple = re.search(r"(?:ForwardP/E|目標本益比|合理ForwardP/E|給予).{0,20}(?:2[5-9]|[3-9]\d)(?:\.\d+)?x", normalized)
        high_implied_growth = (
            re.search(r"營收.{0,40}(?:成長|增長|暴增|增加|提升).{0,20}(?:[5-9]\d|1\d\d)%", normalized)
            or ("ForwardEPS" in normalized and "隱含" in normalized and any(word in normalized for word in ["營收需", "營收必須", "營收要"]))
        )
        if high_multiple and high_implied_growth:
            issues.append(
                "雙重樂觀紅線：若 Forward EPS/財測已隱含營收暴增，不應再套用高 Forward P/E 重複計價成長；"
                "基本情境應使用折讓倍數或 normalized DCF。"
            )

    yahoo_growth = str(data.get("yahoo_revenue_growth", "")).replace("%", "").strip()
    if yahoo_growth and yahoo_growth != "N/A" and yahoo_growth in normalized:
        if any(word in normalized for word in ["營收年增率", "TTM營收成長", "TTM營收年增", "營收成長率高達"]):
            if not any(word in normalized for word in ["Yahoo近期", "季度口徑", "近期口徑", "不可直接稱為"]):
                issues.append(
                    "成長率口徑紅線：Yahoo revenueGrowth 通常是近期/季度口徑，不可直接寫成 TTM 或年度營收年增率；"
                    "請改用年度財報 YoY 或 TTM 相對最新年度 run-rate 檢查。"
                )

    provider_margin = str(data.get("profit_margin_provider", "")).replace("%", "").strip()
    calibrated_margin = str(data.get("profit_margin", "")).replace("%", "").strip()
    if provider_margin and provider_margin != "N/A" and calibrated_margin and provider_margin != calibrated_margin:
        if provider_margin in normalized and "淨利率" in normalized:
            if not any(word in normalized for word in ["Yahoo原始", "資料源對照", "口徑互斥", "不採用"]):
                issues.append(
                    "淨利率口徑紅線：Yahoo 原始 profitMargins 與 P/E/EPS 推回淨利互斥時，"
                    "正式分析必須採用校準後淨利率，原始值只能作為資料品質警示。"
                )

    _append_deep_numeric_consistency_issues(issues, normalized)

    return issues


def append_quality_warnings(agent_num: int, text: str, data: Optional[dict] = None) -> str:
    issues = validate_analysis_output(agent_num, text, data)
    if not issues:
        return text

    warning_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"{text}\n\n"
        "## 系統品質檢查警示\n"
        "以下內容觸發硬性財務邏輯檢查；閱讀本段分析時請優先採用警示所述修正口徑：\n"
        f"{warning_lines}"
    )


def _count_unqualified_alias(text: str, alias: str, peer_code=None) -> int:
    """Count suspicious alias mentions that are not clearly marked as peer comparisons."""
    if not text or not alias:
        return 0

    count = 0
    peer_tokens = []
    if peer_code:
        peer_tokens = [peer_code, f"{peer_code}.TW", f"{peer_code}.TWO"]

    peer_context_words = [
        "同業",
        "競爭",
        "競品",
        "對手",
        "可比",
        "比較",
        "peer",
        "Peers",
        "同業比較",
    ]

    for match in re.finditer(re.escape(alias), text, flags=re.IGNORECASE):
        window = text[max(0, match.start() - 30): min(len(text), match.end() + 30)]
        if peer_tokens and any(token in window for token in peer_tokens):
            continue
        if any(word in window for word in peer_context_words):
            continue
        count += 1
    return count


def validate_company_identity(text: str, data: dict) -> list[str]:
    """Detect target-company identity contamination before it enters later-agent context."""
    identity = data.get("company_identity", {}) or {}
    if not identity or not text:
        return []

    issues = []
    ticker = data.get("ticker", identity.get("ticker", ""))
    stock_id = identity.get("stock_id", ticker.replace(".TW", "").replace(".TWO", ""))
    official_name = identity.get("official_name")
    allowed_aliases = set(identity.get("allowed_aliases", []))
    forbidden_aliases = set(identity.get("forbidden_aliases", []))

    current_ticker_patterns = [
        re.escape(ticker),
        re.escape(stock_id),
        rf"{re.escape(stock_id)}\.(?:TW|TWO)",
    ]

    def alias_bound_to_current_ticker(alias: str) -> bool:
        alias_re = re.escape(alias)
        for ticker_re in current_ticker_patterns:
            patterns = [
                rf"{alias_re}\s*[（(]\s*{ticker_re}",
                rf"{ticker_re}\s*[）)]?\s*{alias_re}",
            ]
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
                return True
        return False

    for alias in identity.get("forbidden_aliases", []):
        if len(alias) < 2:
            continue
        if alias_bound_to_current_ticker(alias):
            issues.append(f"公司身分錯置：輸出將「{alias}」綁定到本次標的 {ticker}。")
            continue
        unqualified_count = _count_unqualified_alias(text, alias)
        if unqualified_count >= 2:
            issues.append(f"公司身分污染：輸出中多次以「{alias}」作為主體，疑似套用了錯誤公司。")

    for peer in identity.get("same_industry_peers", []):
        peer_name = peer.get("stock_name", "")
        peer_code = peer.get("stock_id", "")
        # 同業名單裡有不少兩字名稱會同時是產業普通名詞（例如「綠電」）。
        # 這類詞只適合在「代號綁定錯置」時攔截，不能單靠出現次數判定為公司身分污染。
        if not peer_name or peer_name in allowed_aliases or peer_name in forbidden_aliases:
            continue
        if alias_bound_to_current_ticker(peer_name):
            issues.append(f"公司身分錯置：同業「{peer_name}」被綁定到本次標的 {ticker}。")
            continue
        if len(peer_name) < 3:
            continue
        unqualified_count = _count_unqualified_alias(text, peer_name, peer_code=peer_code)
        if unqualified_count >= 4:
            issues.append(f"公司身分污染：同業「{peer_name}」在未標示為同業的脈絡中出現 {unqualified_count} 次。")

    if official_name and issues and official_name not in text:
        issues.append(f"公司身分缺失：輸出未使用官方中文名稱「{official_name}」。")

    return list(dict.fromkeys(issues))


def build_identity_retry_instruction(data: dict, issues: list[str]) -> str:
    """Tell the model exactly why the prior output was rejected."""
    identity = data.get("company_identity", {}) or {}
    official_name = identity.get("official_name") or data.get("company_name", data.get("ticker", "本公司"))
    ticker = data.get("ticker", identity.get("ticker", "N/A"))
    issue_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        "🚨【前一次輸出已被系統退件，請重寫】\n"
        f"退件原因：\n{issue_lines}\n"
        f"請完全重寫本段，唯一主體必須是「{official_name}（{ticker}）」；"
        "不得使用同業公司名稱作為本公司稱呼，也不得把同業商業模式、專案或新聞套用到本公司。"
    )


def append_identity_warnings(text: str, issues: list[str]) -> str:
    if not issues:
        return text
    warning_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"{text}\n\n"
        "## 系統身分一致性警示\n"
        "本段未通過公司身分一致性檢查，報告不應作為正式輸出：\n"
        f"{warning_lines}"
    )


REPORT_CONTENT_START_RE = re.compile(
    r"^\s*(?:#{1,4}\s+.+|(?:#{1,4}\s+)?(?:[一二三四五六七八九十]+[、.．]|執行摘要|短中長期展望|長期展望|關鍵催化因子|主要風險|最終投資決策論述|"
    r"🐂\s*多頭[：:]|🐻\s*空頭[：:]|\[護城河評分\]|\[目標股價\]|\[投資建議\]))"
)

PROMPT_LEAK_RESIDUE_RE = re.compile(
    r"(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department|BlackRock Active Investment Research Team|"
    r"Growth Equity Researcher at Fidelity|Valid parseable JSON only|No markdown code fences|Specific JSON schema|"
    r"JSON schema:|analysis_markdown|moat_scores|price_targets|Must use \"|No roleplay meta-talk|Check:\s*Did I|Past 5 years of financial trends|"
    r"Analyze the \"Economic Moat\"|Analyze the growth potential|"
    r"Growth Scenarios \(5 years\)|Professional, data-driven)",
    re.IGNORECASE,
)


def strip_prompt_preamble(text: str) -> str:
    """Drop leaked role/task setup before the first formal report section."""
    if not text:
        return ""

    if "\\n" in text and ("analysis_markdown" in text or "\\n##" in text or "\\n###" in text):
        text = text.replace("\\n", "\n")

    lines = text.splitlines()
    start_index = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if REPORT_CONTENT_START_RE.match(stripped):
            start_index = idx
            break

    if start_index and any(PROMPT_LEAK_RESIDUE_RE.search(line) for line in lines[:start_index]):
        lines = lines[start_index:]

    while lines and lines[-1].strip() in {'"', '"}', '}', '},', "```"}:
        lines.pop()

    return "\n".join(lines)


def validate_prompt_leakage(text: str) -> list[str]:
    """Return high-confidence prompt leakage findings after sanitization."""
    if not text:
        return []
    findings = []
    for pattern in [
        "Senior Analyst at Goldman Sachs",
        "Valid parseable JSON only",
        "No markdown code fences",
        "Specific JSON schema",
        "Check: Did I",
        "No roleplay meta-talk",
    ]:
        if pattern.lower() in text.lower():
            findings.append(f"輸出仍包含內部提示詞片段：{pattern}")
    return findings


def sanitize_model_output(text: str) -> str:
    """Remove prompt/scratchpad leakage before it enters reports or later-agent context."""
    if not text:
        return ""

    text = strip_prompt_preamble(text)
    leak_patterns = [
        r"^\s*(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department Financial Modeling Expert|Competitive Advantage Analyst at BlackRock|BlackRock Active Investment Research Team|Growth Equity Researcher at Fidelity|Fidelity Investments Growth Equity Researcher)\b",
        r"^\s*你好，我是(高盛|摩根士丹利|貝萊德|JP\s*摩根|富達投資|T\.?\s*Rowe|德富金融)",
        r"^\s*(Deep financial analysis of|Deep financial data analysis of|Economic Moat analysis of|.*Deep moat evaluation|.*Analyze the growth potential|Analyze the growth potential|Analyze the 5-10 year growth potential of|Financial data provided)\b",
        r"^\s*\*?\s*(Currency|Units|TTM units|Debt to Equity|Manufacturing Logic|Valuation Cross-check|Forward EPS implicit.*|FCF quality check.*|WACC|DuPont Analysis|ROE Discrepancy|Language|Unit Check|Tone|Constraint Check|First paragraph MUST|No internal monologue|Valid parseable JSON only|No markdown code fences|No extra text outside JSON|JSON schema|Specific JSON schema|analysis_markdown|moat_scores|price_targets|recommendation)\s*:",
        r"^\s*\*?\s*(Specific scoring format|Traditional Chinese|Rigorous adherence|Cross-check Forward EPS|Manufacturing logic|First paragraph MUST|No internal monologue|Valid parseable JSON only|No markdown code fences|No extra text outside JSON|JSON schema|No roleplay meta-talk|analysis_markdown|moat_scores|price_targets|recommendation)\b",
        r"^\s*\*?\s*(Observation|The Red Flag|Action|Company Profile|Financials \(Key Highlights\))\s*:",
        r"^\s*\*?\s*(Section\s+[IVX0-9]+|TAM|SAM|SOM|Estimation)\s*:",
        r"^\s*\d+\.\s*(Market Size|Key Growth Drivers|AI\s*&\s*New Tech Impact|Long-term Market Share|5-Year Growth Scenarios|Overall Growth Potential)",
        r"^\s*\*?\s*(Data|Trend|Calculation|Driver|Net Profit|Margins|Quality|Critical Check|Conversion Rate|Warning Flag|Total Debt|Net Cash Position|Valuation|Growth|Key Product|Intellectual Property|Financials|Cash Flow|Identity|Check)\s*:",
        r"^\s*(Professional, data-driven|Company Overview & Business Model|Macroeconomics & Industry Trends|Supply Chain Position & Competitive Landscape|Key Risk Factors|Analyze the \"Economic Moat\"|Analyze the growth potential)\b",
        r"\b(I must|I need to|Let's|Wait:|As a Fidelity researcher)\b",
    ]
    leak_re = re.compile("|".join(leak_patterns), re.IGNORECASE)

    kept_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in {'"', '"}', '}', '},', "```"}:
            continue
        if leak_re.search(stripped):
            continue
        kept_lines.append(line)

    cleaned = "\n".join(kept_lines)
    cleaned = normalize_bad_number_commas(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def normalize_bad_number_commas(text: str) -> str:
    """Fix values like 1,0064.8億 -> 10,064.8億."""
    def repl(match):
        raw = f"{match.group(1)}{match.group(2)}"
        decimal = match.group(3) or ""
        return f"{int(raw):,}{decimal}"

    return re.sub(r"(?<!\d)(\d),(\d{4})(\.\d+)?(?=億)", repl, text or "")


def _parse_price_number(raw: str) -> float:
    return float(raw.replace(",", ""))


def _extract_price_numbers(text: str) -> list[float]:
    """Extract currency-like prices while preserving thousands separators."""
    import re

    number_pattern = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
    currency_matches = re.findall(rf"(?:NT\$?|\$)\s*({number_pattern})", text)
    matches = currency_matches or re.findall(number_pattern, text)
    return [_parse_price_number(match) for match in matches]


def run_analysis_pipeline(data: dict, progress_callback=None) -> dict:
    """
    執行完整的 7-Agent 連續分析管道
    
    Args:
        data: 從 financial_data.fetch_stock_data() 返回的數據字典
        progress_callback: 進度回調函數（可選）
    
    Returns:
        包含所有分析結果的 context 字典
    """
    ticker = data["ticker"]
    name = data["company_name"]
    
    # 初始化輪調器和上下文
    rotator = KeyRotator(API_KEYS)
    context = {
        "ticker": ticker,
        "company_name": name,
        "data": data,
        "analyses": {},
        "structured_outputs": {},
        "start_time": time.time(),
    }
    
    print(f"\n{'='*60}")
    print(f"  🚀 開始分析 {ticker} {name}")
    print(f"  📅 時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  🔑 可用 API Keys：{len(API_KEYS)} 組（輪調中）")
    print(f"{'='*60}\n")
    
    for agent_num in range(1, 8):
        agent_name = AGENT_NAMES[agent_num]
        model_id = AGENT_MODELS[agent_num]
        
        print(f"{'─'*60}")
        print(f"  📌 Agent {agent_num}/7：{agent_name}")
        print(f"  🤖 模型：{model_id}")
        print(f"{'─'*60}")
        
        start = time.time()

        context["structured_outputs"].pop(agent_num, None)
        ensure_context_digest(agent_num, context, rotator)
        result = run_single_agent(agent_num, data, context, rotator)
        result = sanitize_model_output(result)

        if is_agent_execution_failure(result):
            context.setdefault("blocking_issues", []).append(f"Agent {agent_num} {agent_name}: {result}")
            context["analyses"][agent_num] = result
            print(f"  ❌ {result}")
            break

        prompt_leak_issues = validate_prompt_leakage(result)
        if prompt_leak_issues:
            print("  🚨 輸出清洗後仍偵測到 prompt 洩漏，停止產生正式報告。")
            for issue in prompt_leak_issues:
                print(f"     - {issue}")
            context.setdefault("blocking_issues", []).extend(
                f"Agent {agent_num} {agent_name}: {issue}"
                for issue in prompt_leak_issues
            )
            context["analyses"][agent_num] = result
            break

        identity_issues = validate_company_identity(result, data)
        if identity_issues:
            print("  🚨 公司身分一致性檢查未通過，退回 Agent 重寫...")
            for issue in identity_issues:
                print(f"     - {issue}")
            context["_identity_retry_instruction"] = build_identity_retry_instruction(data, identity_issues)
            context["structured_outputs"].pop(agent_num, None)
            retry_result = run_single_agent(agent_num, data, context, rotator)
            retry_result = sanitize_model_output(retry_result)
            retry_prompt_leak_issues = validate_prompt_leakage(retry_result)
            if retry_prompt_leak_issues:
                print("  🚨 重寫輸出仍偵測到 prompt 洩漏，停止產生正式報告。")
                context.setdefault("blocking_issues", []).extend(
                    f"Agent {agent_num} {agent_name}: {issue}"
                    for issue in retry_prompt_leak_issues
                )
                context.pop("_identity_retry_instruction", None)
                result = retry_result
                context["analyses"][agent_num] = result
                break
            retry_issues = validate_company_identity(retry_result, data)
            context.pop("_identity_retry_instruction", None)

            result = retry_result
            identity_issues = retry_issues
            if identity_issues:
                print("  ❌ 重寫後仍未通過公司身分一致性檢查，停止產生正式報告。")
                for issue in identity_issues:
                    print(f"     - {issue}")
                context.setdefault("blocking_issues", []).extend(
                    f"Agent {agent_num} {agent_name}: {issue}"
                    for issue in identity_issues
                )
                result = append_identity_warnings(result, identity_issues)
            else:
                print("  ✅ 重寫後通過公司身分一致性檢查。")

        result = append_quality_warnings(agent_num, result, data)
        
        elapsed = time.time() - start
        context["analyses"][agent_num] = result
        
        print(f"  ✅ 完成！耗時 {elapsed:.1f} 秒")
        print(f"  📝 輸出長度：{len(result)} 字元")
        
        # 顯示結果前 100 字
        preview = result[:120].replace("\n", " ")
        print(f"  💬 預覽：{preview}...")
        
        if progress_callback:
            progress_callback(agent_num, 7, agent_name)

        if context.get("blocking_issues"):
            break
        
        # Agent 之間的延遲（避免速率限制）
        if agent_num < 7:
            wait = INTER_AGENT_DELAY
            print(f"\n  ⏰ 等待 {wait} 秒後執行下一個 Agent...\n")
            time.sleep(wait)
    
    # 解析結構化數據、嘗試修復跨 Agent 稽核問題，再輸出最終稽核摘要。
    finalize_final_audit(context, rotator)
    context["total_time"] = time.time() - context["start_time"]
    
    print(f"\n{'='*60}")
    print(f"  🎉 分析完成！總耗時：{context['total_time']:.1f} 秒")
    print(f"{'='*60}\n")
    
    return context


async def _call_progress_callback(progress_callback, current: int, total: int, name: str):
    if not progress_callback:
        return
    result = progress_callback(current, total, name)
    if inspect.isawaitable(result):
        await result


async def run_analysis_pipeline_async(data: dict, progress_callback=None) -> dict:
    """
    非同步執行完整 7-Agent 管道。
    主要差異：Gemini 呼叫與 agent 間等待使用 await，避免阻塞 worker event loop。
    """
    ticker = data["ticker"]
    name = data["company_name"]

    rotator = KeyRotator(API_KEYS)
    context = {
        "ticker": ticker,
        "company_name": name,
        "data": data,
        "analyses": {},
        "structured_outputs": {},
        "start_time": time.time(),
        "execution_mode": "async",
    }

    print(f"\n{'='*60}")
    print(f"  🚀 開始非同步分析 {ticker} {name}")
    print(f"  📅 時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  🔑 可用 API Keys：{len(API_KEYS)} 組（輪調中）")
    print(f"{'='*60}\n")

    for agent_num in range(1, 8):
        agent_name = AGENT_NAMES[agent_num]
        model_id = AGENT_MODELS[agent_num]

        print(f"{'─'*60}")
        print(f"  📌 Agent {agent_num}/7：{agent_name}")
        print(f"  🤖 模型：{model_id}")
        print(f"{'─'*60}")

        start = time.time()

        context["structured_outputs"].pop(agent_num, None)
        await ensure_context_digest_async(agent_num, context, rotator)
        result = await run_single_agent_async(agent_num, data, context, rotator)
        result = sanitize_model_output(result)

        if is_agent_execution_failure(result):
            context.setdefault("blocking_issues", []).append(f"Agent {agent_num} {agent_name}: {result}")
            context["analyses"][agent_num] = result
            print(f"  ❌ {result}")
            break

        prompt_leak_issues = validate_prompt_leakage(result)
        if prompt_leak_issues:
            print("  🚨 輸出清洗後仍偵測到 prompt 洩漏，停止產生正式報告。")
            for issue in prompt_leak_issues:
                print(f"     - {issue}")
            context.setdefault("blocking_issues", []).extend(
                f"Agent {agent_num} {agent_name}: {issue}"
                for issue in prompt_leak_issues
            )
            context["analyses"][agent_num] = result
            break

        identity_issues = validate_company_identity(result, data)
        if identity_issues:
            print("  🚨 公司身分一致性檢查未通過，退回 Agent 非同步重寫...")
            for issue in identity_issues:
                print(f"     - {issue}")
            context["_identity_retry_instruction"] = build_identity_retry_instruction(data, identity_issues)
            context["structured_outputs"].pop(agent_num, None)
            retry_result = await run_single_agent_async(agent_num, data, context, rotator)
            retry_result = sanitize_model_output(retry_result)
            retry_prompt_leak_issues = validate_prompt_leakage(retry_result)
            if retry_prompt_leak_issues:
                print("  🚨 重寫輸出仍偵測到 prompt 洩漏，停止產生正式報告。")
                context.setdefault("blocking_issues", []).extend(
                    f"Agent {agent_num} {agent_name}: {issue}"
                    for issue in retry_prompt_leak_issues
                )
                context.pop("_identity_retry_instruction", None)
                result = retry_result
                context["analyses"][agent_num] = result
                break
            retry_issues = validate_company_identity(retry_result, data)
            context.pop("_identity_retry_instruction", None)

            result = retry_result
            identity_issues = retry_issues
            if identity_issues:
                print("  ❌ 重寫後仍未通過公司身分一致性檢查，停止產生正式報告。")
                for issue in identity_issues:
                    print(f"     - {issue}")
                context.setdefault("blocking_issues", []).extend(
                    f"Agent {agent_num} {agent_name}: {issue}"
                    for issue in identity_issues
                )
                result = append_identity_warnings(result, identity_issues)
            else:
                print("  ✅ 重寫後通過公司身分一致性檢查。")

        result = append_quality_warnings(agent_num, result, data)

        elapsed = time.time() - start
        context["analyses"][agent_num] = result

        print(f"  ✅ 完成！耗時 {elapsed:.1f} 秒")
        print(f"  📝 輸出長度：{len(result)} 字元")

        preview = result[:120].replace("\n", " ")
        print(f"  💬 預覽：{preview}...")

        await _call_progress_callback(progress_callback, agent_num, 7, agent_name)

        if context.get("blocking_issues"):
            break

        if agent_num < 7:
            wait = INTER_AGENT_DELAY
            print(f"\n  ⏰ 非同步等待 {wait} 秒後執行下一個 Agent...\n")
            await asyncio.sleep(wait)

    await finalize_final_audit_async(context, rotator)
    context["total_time"] = time.time() - context["start_time"]

    print(f"\n{'='*60}")
    print(f"  🎉 非同步分析完成！總耗時：{context['total_time']:.1f} 秒")
    print(f"{'='*60}\n")

    return context


def parse_structured_data(context: dict) -> dict:
    """解析 Agent 輸出中的結構化數據（評分、目標價等）"""
    parsed = {
        "moat_scores": {},
        "price_targets": {},
        "recommendation": {},
    }

    structured_outputs = context.get("structured_outputs", {})
    if 3 in structured_outputs:
        parsed["moat_scores"] = dict(structured_outputs[3].get("moat_scores", {}))
    if 4 in structured_outputs:
        parsed["price_targets"] = dict(structured_outputs[4].get("price_targets", {}))
    if 7 in structured_outputs:
        parsed["recommendation"] = dict(structured_outputs[7].get("recommendation", {}))
    
    # 解析護城河評分（Agent 3）。JSON 是主路徑，regex 僅作相容備援。
    if not parsed["moat_scores"] and 3 in context["analyses"]:
        text = context["analyses"][3]
        try:
            import re
            allowed_moat_keys = {"品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河"}
            moat_section = re.search(r'\[護城河評分\](.*?)\[/護城河評分\]', text, re.DOTALL)
            if moat_section:
                moat_text = moat_section.group(1)
                for line in moat_text.strip().split('\n'):
                    if ':' in line or '：' in line:
                        sep = ':' if ':' in line else '：'
                        key, val = line.split(sep, 1)
                        key = re.sub(r"^[\s*・\-]+", "", key).strip()
                        if key not in allowed_moat_keys:
                            continue
                        val = val.strip()
                        try:
                            score = float(re.search(r'[\d.]+', val).group())
                            parsed["moat_scores"][key] = min(score, 10)
                        except Exception:
                            pass
        except Exception:
            pass
    
    # 設定預設護城河分數（如解析失敗）
    if not parsed["moat_scores"]:
        parsed["moat_scores"] = {
            "品牌影響力": 6,
            "網路效應": 4,
            "轉換成本": 7,
            "成本優勢": 7,
            "專利技術": 6,
            "整體護城河": 6,
        }
    
    # 解析目標股價（Agent 4）。JSON 是主路徑，regex 僅作相容備援。
    if not parsed["price_targets"] and 4 in context["analyses"]:
        text = context["analyses"][4]
        try:
            import re
            # --- Primary: parse [目標股價] block ---
            price_section = re.search(r'\[目標股價\](.*?)\[/目標股價\]', text, re.DOTALL)
            if price_section:
                price_text = price_section.group(1)
                for line in price_text.strip().split('\n'):
                    if ':' in line or '：' in line:
                        sep = ':' if ':' in line else '：'
                        key, val = line.split(sep, 1)
                        key = key.strip()
                        prices = _extract_price_numbers(val)
                        if prices:
                            price_val = prices[0]
                            if price_val > 1:  # 排除百分比數字
                                parsed["price_targets"][key] = price_val
            
            # --- Fallback: parse from markdown tables or inline text ---
            if not parsed["price_targets"]:
                scenario_map = {
                    "熊市": ["熊市", "bear", "Bear"],
                    "基本": ["基本", "base", "Base"],
                    "牛市": ["牛市", "bull", "Bull"],
                }
                for label, keywords in scenario_map.items():
                    for kw in keywords:
                        # 在 kw 後面的文字中找 NT$ 數字，忽略百分比行
                        number_pattern = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,6}(?:\.\d+)?"
                        pattern = rf'{kw}.{{0,80}}?(?:NT\$|\$|合理股價|目標價|合理價值)\s*:?\s*({number_pattern})'
                        m = re.search(pattern, text)
                        if m:
                            price_val = _parse_price_number(m.group(1))
                            if price_val > 10:  # 合理股價應 > 10
                                key_name = f"{label}情境"
                                parsed["price_targets"][key_name] = price_val
                                break

            current_price = context.get("data", {}).get("current_price")
            if isinstance(current_price, (int, float)) and current_price > 100:
                suspicious = [
                    key for key, price in parsed["price_targets"].items()
                    if isinstance(price, (int, float)) and price < current_price * 0.05
                ]
                if suspicious:
                    reparsed = {}
                    for line in text.splitlines():
                        if not any(label in line for label in ["熊市", "基本", "牛市"]):
                            continue
                        values = [value for value in _extract_price_numbers(line) if value >= current_price * 0.05]
                        if not values:
                            continue
                        if "熊市" in line:
                            reparsed["熊市情境"] = values[0]
                        elif "基本" in line:
                            reparsed["基本情境"] = values[0]
                        elif "牛市" in line:
                            reparsed["牛市情境"] = values[0]
                    if reparsed:
                        parsed["price_targets"] = reparsed
        except Exception:
            pass
    
    # 解析投資建議（Agent 7）。JSON 是主路徑，regex 僅作相容備援。
    if not parsed["recommendation"] and 7 in context["analyses"]:
        text = context["analyses"][7]
        try:
            import re
            rec_section = re.search(r'\[投資建議\](.*?)\[/投資建議\]', text, re.DOTALL)
            if rec_section:
                rec_text = rec_section.group(1)
                for line in rec_text.strip().split('\n'):
                    if ':' in line or '：' in line:
                        sep = ':' if ':' in line else '：'
                        key, val = line.split(sep, 1)
                        parsed["recommendation"][key.strip()] = val.strip()
        except Exception:
            pass
    
    return parsed


def _recommendation_value(recommendation: dict, key_fragment: str) -> str:
    for key, value in (recommendation or {}).items():
        if key_fragment in str(key):
            return str(value)
    return ""


def _extract_first_price(value: str) -> Optional[float]:
    try:
        prices = _extract_price_numbers(value or "")
    except Exception:
        return None
    return prices[0] if prices else None


def _add_unique_issue(items: list[str], issue: str):
    if issue and issue not in items:
        items.append(issue)


def _append_final_audit_section(context: dict, audit: dict):
    """Expose non-blocking final audit notes in the final decision section."""
    if context.get("_final_audit_appended"):
        return
    if 7 not in context.get("analyses", {}):
        return

    critical = audit.get("critical", [])
    warnings = audit.get("warnings", [])
    corrections = audit.get("corrections", [])
    repair_log = context.get("audit_repair_log", [])
    if not critical and not warnings and not corrections and not repair_log:
        return

    lines = ["## 系統最終稽核"]
    if critical:
        lines.append("### 仍需注意的異常")
        lines.extend(f"- {item}" for item in critical[:8])
    if repair_log:
        lines.append("### AI 修復紀錄")
        lines.extend(f"- {item}" for item in repair_log[:8])
    if corrections:
        lines.append("### 已套用校正")
        lines.extend(f"- {item}" for item in corrections[:8])
    if warnings:
        lines.append("### 非阻斷提醒")
        lines.extend(f"- {item}" for item in warnings[:8])
    context["analyses"][7] = f"{context['analyses'][7].rstrip()}\n\n" + "\n".join(lines)
    context["_final_audit_appended"] = True


def _build_reflection_generation_config():
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=1200,
        system_instruction=(
            "你是金融分析品質稽核的反思助手。你只分析前次輸出為何踩到紅線，"
            "並提出下一次重寫時的修正策略；不要產生正式報告段落。"
        ),
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
    client = genai.Client(api_key=api_key)
    try:
        return client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=_build_reflection_generation_config(),
        )
    finally:
        with suppress(Exception):
            client.close()


async def _generate_reflection_content_async(api_key: str, model_id: str, prompt: str):
    client = genai.Client(api_key=api_key)
    try:
        return await client.aio.models.generate_content(
            model=model_id,
            contents=prompt,
            config=_build_reflection_generation_config(),
        )
    finally:
        with suppress(Exception):
            await client.aio.aclose()
        with suppress(Exception):
            client.close()


def generate_audit_reflection(agent_num: int, issues: list[str], previous_text: str, data: dict, rotator: KeyRotator) -> str:
    """Generate a pre-rewrite reflection, falling back deterministically if needed."""
    if not isinstance(rotator, KeyRotator):
        return _fallback_audit_reflection(agent_num, issues)

    prompt = _build_audit_reflection_prompt(agent_num, issues, previous_text, data)
    for model_id in get_agent_model_sequence(agent_num):
        try:
            response = _generate_reflection_content(rotator.get_key(model_id), model_id, prompt)
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
    for model_id in get_agent_model_sequence(agent_num):
        try:
            api_key = await rotator.async_get_key(model_id)
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


async def _repair_agent_output_async(agent_num: int, data: dict, context: dict, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Asynchronously ask the relevant agent to rewrite after final audit failure."""
    previous_instruction = context.get("_audit_retry_instruction")
    previous_reflection_instruction = context.get("_audit_reflection_instruction")
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


def run_final_report_audit(context: dict, append_section: bool = True) -> dict:
    """
    Cross-agent final audit before report rendering.

    The audit is deterministic. It classifies serious issues, asks the pipeline
    to repair them in a separate pass, and always leaves enough information for
    the renderer to preserve a report with visible abnormality notes.
    """
    data = context.get("data", {}) or {}
    analyses = context.get("analyses", {}) or {}
    parsed = context.get("parsed", {}) or {}
    structured_outputs = context.get("structured_outputs", {}) or {}

    critical: list[str] = []
    warnings: list[str] = []
    corrections: list[str] = []
    repair_agent_issues: dict[int, list[str]] = {}

    def add_agent_repair_issue(agent_num: int, issue: str):
        repair_agent_issues.setdefault(agent_num, [])
        _add_unique_issue(repair_agent_issues[agent_num], issue)

    completed_agents = set(analyses.keys())
    missing_agents = [num for num in range(1, 8) if num not in completed_agents or not str(analyses.get(num, "")).strip()]
    if missing_agents:
        _add_unique_issue(critical, f"缺少 Agent 輸出：{', '.join(str(num) for num in missing_agents)}")
        for agent_num in missing_agents:
            add_agent_repair_issue(agent_num, "缺少 Agent 輸出，請補跑本 Agent 並產生完整正式段落。")

    for agent_num, text in analyses.items():
        agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
        audited_text = strip_generated_audit_sections(str(text))
        if is_agent_execution_failure(str(text)):
            _add_unique_issue(critical, f"{agent_name} 輸出為失敗訊息，不能產生正式報告。")
            add_agent_repair_issue(agent_num, "前次輸出為失敗訊息，請重新執行本 Agent。")
        if "分析進行中" in audited_text:
            _add_unique_issue(critical, f"{agent_name} 仍含佔位文字「分析進行中」。")
            add_agent_repair_issue(agent_num, "前次輸出仍是佔位文字，請補齊正式分析。")

        for issue in validate_prompt_leakage(audited_text):
            _add_unique_issue(critical, f"{agent_name}: {issue}")
            add_agent_repair_issue(agent_num, issue)
        for issue in validate_company_identity(audited_text, data):
            _add_unique_issue(critical, f"{agent_name}: {issue}")
            add_agent_repair_issue(agent_num, issue)

        for issue in validate_analysis_output(agent_num, audited_text, data):
            _add_unique_issue(critical, f"{agent_name}: {issue}")
            add_agent_repair_issue(agent_num, issue)

    # Structured agents must remain parseable. Regex/default fallbacks are useful
    # for old reports but should not silently pass new production reports.
    for agent_num, label in [(3, "護城河評分"), (4, "三情境目標價"), (7, "最終投資建議")]:
        if agent_num in completed_agents and agent_num not in structured_outputs:
            _add_unique_issue(critical, f"Agent {agent_num} {label} 未提供可解析 JSON 結構化輸出。")
            add_agent_repair_issue(agent_num, f"{label} 未提供可解析 JSON 結構化輸出。")

    price_targets = parsed.get("price_targets", {}) or {}
    required_targets = ["熊市情境", "基本情境", "牛市情境"]
    missing_targets = [key for key in required_targets if key not in price_targets]
    if missing_targets:
        _add_unique_issue(critical, f"Agent 4 缺少目標價情境：{', '.join(missing_targets)}")
        add_agent_repair_issue(4, f"缺少目標價情境：{', '.join(missing_targets)}")

    current_price = data.get("current_price")
    numeric_targets = {
        key: value for key, value in price_targets.items()
        if isinstance(value, (int, float))
    }
    if isinstance(current_price, (int, float)) and current_price > 100:
        tiny_targets = [
            f"{key}=NT${value:g}"
            for key, value in numeric_targets.items()
            if value < current_price * 0.05
        ]
        if tiny_targets:
            _add_unique_issue(critical, f"目標價疑似單位縮小錯誤：{', '.join(tiny_targets)}")
            add_agent_repair_issue(4, f"目標價疑似單位縮小錯誤：{', '.join(tiny_targets)}")

    if all(key in numeric_targets for key in required_targets):
        bear = numeric_targets["熊市情境"]
        base = numeric_targets["基本情境"]
        bull = numeric_targets["牛市情境"]
        if not (bear <= base <= bull):
            _add_unique_issue(critical, f"三情境目標價順序不合理：熊市 {bear:g}、基本 {base:g}、牛市 {bull:g}。")
            add_agent_repair_issue(4, f"三情境目標價順序不合理：熊市 {bear:g}、基本 {base:g}、牛市 {bull:g}。")

    moat_scores = parsed.get("moat_scores", {}) or {}
    required_moat = {"品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河"}
    if not required_moat.issubset(moat_scores.keys()):
        missing = sorted(required_moat - set(moat_scores.keys()))
        _add_unique_issue(critical, f"Agent 3 護城河評分缺少欄位：{', '.join(missing)}")
        add_agent_repair_issue(3, f"護城河評分缺少欄位：{', '.join(missing)}")

    recommendation = parsed.get("recommendation", {}) or {}
    if not recommendation:
        _add_unique_issue(critical, "Agent 7 缺少最終投資建議結構化資料。")
        add_agent_repair_issue(7, "缺少最終投資建議結構化資料。")
    else:
        rec_text = _recommendation_value(recommendation, "建議")
        if not any(word in rec_text for word in ["買入", "持有", "避免"]):
            _add_unique_issue(critical, f"Agent 7 投資建議不在允許值內：{rec_text or '空白'}")
            add_agent_repair_issue(7, f"投資建議不在允許值內：{rec_text or '空白'}")
        for label in ["3個月", "6個月", "12個月", "信心"]:
            if not _recommendation_value(recommendation, label):
                _add_unique_issue(critical, f"Agent 7 缺少 {label} 欄位。")
                add_agent_repair_issue(7, f"缺少 {label} 欄位。")

        target_12m = _extract_first_price(_recommendation_value(recommendation, "12個月"))
        if target_12m is not None and all(key in numeric_targets for key in required_targets):
            bear = numeric_targets["熊市情境"]
            bull = numeric_targets["牛市情境"]
            lower = bear * 0.7
            upper = bull * 1.3
            if not (lower <= target_12m <= upper):
                _add_unique_issue(
                    warnings,
                    f"Agent 7 的 12 個月目標價 NT${target_12m:g} 與 Agent 4 三情境區間差距較大，需人工確認。"
                )

    data_notes = data.get("data_source_notes", []) or []
    if any("口徑互斥" in note for note in data_notes):
        _add_unique_issue(corrections, "資料源出現淨利/淨利率口徑互斥時，報告已採用 EPS/P/E 自洽的校準口徑。")
    if any("revenueGrowth" in note for note in data_notes):
        _add_unique_issue(corrections, "Yahoo revenueGrowth 已降級為近期/季度口徑，不得直接當年度或 TTM 年增率。")

    price_history = data.get("price_history", {}) or {}
    if isinstance(price_history, dict):
        future_dates = []
        today = date.today()
        for raw_date in price_history.keys():
            try:
                parsed_date = datetime.fromisoformat(str(raw_date)[:10]).date()
            except ValueError:
                continue
            if parsed_date > today:
                future_dates.append(str(raw_date)[:10])
        if future_dates:
            _add_unique_issue(
                corrections,
                f"歷史股價含未來日期，報告圖表會忽略：{', '.join(sorted(future_dates)[:5])}。"
            )

    status = "needs_attention" if critical else "passed"
    audit = {
        "status": status,
        "critical": critical,
        "warnings": warnings,
        "corrections": corrections,
        "repair_agent_issues": repair_agent_issues,
        "report_preserved": True,
    }

    if append_section and critical:
        _append_final_audit_section(context, audit)

    if critical:
        if append_section:
            print("  ⚠️  最終跨 Agent 稽核仍有異常；報告會保留，並在報告內標示異常提醒。")
        else:
            print("  ⚠️  最終跨 Agent 稽核發現異常，準備嘗試 AI 自動修復。")
        for issue in critical[:8]:
            print(f"     - {issue}")
    elif warnings or corrections:
        print("  ✅ 最終跨 Agent 稽核通過，已附加非阻斷稽核註記。")
    else:
        print("  ✅ 最終跨 Agent 稽核通過。")

    return audit
