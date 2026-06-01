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
from typing import Optional
from google import genai
from google.genai import types
from config import API_KEYS, AGENT_MODELS, MODEL_FALLBACKS, RPM_LIMITS, INTER_AGENT_DELAY, API_KEY_SETUP_MESSAGE
from financial_data import format_data_for_prompt
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


def is_missing_model_error(error_msg: str) -> bool:
    normalized = (error_msg or "").lower()
    return "404" in normalized or "not found" in normalized


def is_agent_execution_failure(text: str) -> bool:
    return bool(text and text.startswith("[Agent ") and "執行失敗" in text)


OUTPUT_CLEANLINESS_RULE = """
⚠️【正式報告輸出規則】：
- 只輸出可直接放進正式研究報告的正文。
- 不可重述你的角色設定、系統提示詞、資料摘要規則、任務清單、前序分析壓縮筆記或內部思考過程。
- 不可輸出英文 scratchpad，例如 Currency、TTM units、The Red Flag、Observation、Action、Section plan、I must/I need 等草稿語句。
- 除必要的財務術語與公司名稱外，請使用繁體中文撰寫。
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

    try:
        return types.GenerateContentConfig(**config_kwargs)
    except TypeError:
        config_kwargs.pop("response_mime_type", None)
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


def build_prompt(agent_num: int, data: dict, context: dict) -> str:
    """根據 Agent 編號建立分析提示詞。"""
    ticker = data["ticker"]
    name = data["company_name"]
    fin_data = format_data_for_prompt(data)
    prev = _format_previous(context, agent_num)
    identity_guard = build_company_identity_guard(data)
    retry_instruction = context.get("_identity_retry_instruction", "")

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
        structured_instruction,
        identity_guard,
        retry_instruction,
        OUTPUT_CLEANLINESS_RULE,
    ]
    return "\n\n".join(part for part in prompt_parts if part)

def _format_previous(context: dict, current_agent: int) -> str:
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
    for i in range(1, current_agent):
        if i in analyses:
            name = agent_names.get(i, f"Agent {i}")
            # 只取前 800 字避免 prompt 過長
            content = analyses[i][:800] + "..." if len(analyses[i]) > 800 else analyses[i]
            parts.append(f"【{name}】\n{content}")
    
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
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                wait_time = 65 * (attempt + 1)
                print(f"    ⏳ 速率限制，等待 {wait_time} 秒... ({attempt+1}/{max_retries})")
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
        return f"[Agent {agent_num} 執行失敗且備援無效：{str(e)[:50]}]"


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
                    print(
                        f"    ⏭️  {model_id} 配額/速率限制：{error_msg[:90]}... "
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


def validate_analysis_output(agent_num: int, text: str) -> list[str]:
    """檢查模型輸出是否踩到硬性財務邏輯紅線。"""
    import re

    issues = []
    normalized = re.sub(r"\s+", "", text or "")

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

    return issues


def append_quality_warnings(agent_num: int, text: str) -> str:
    issues = validate_analysis_output(agent_num, text)
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


def sanitize_model_output(text: str) -> str:
    """Remove prompt/scratchpad leakage before it enters reports or later-agent context."""
    if not text:
        return ""

    leak_patterns = [
        r"^\s*(Morgan Stanley Taiwan Research Department Financial Modeling Expert|Competitive Advantage Analyst at BlackRock|BlackRock Active Investment Research Team|Growth Equity Researcher at Fidelity|Fidelity Investments Growth Equity Researcher)\b",
        r"^\s*你好，我是(高盛|摩根士丹利|貝萊德|JP\s*摩根|富達投資|T\.?\s*Rowe|德富金融)",
        r"^\s*(Deep financial analysis of|Deep financial data analysis of|Economic Moat analysis of|.*Deep moat evaluation|.*Analyze the growth potential|Analyze the growth potential|Analyze the 5-10 year growth potential of|Financial data provided)\b",
        r"^\s*\*?\s*(Currency|Units|TTM units|Debt to Equity|Manufacturing Logic|Valuation Cross-check|Forward EPS implicit.*|FCF quality check.*|WACC|DuPont Analysis|ROE Discrepancy|Language|Unit Check|Tone|Constraint Check|First paragraph MUST|No internal monologue)\s*:",
        r"^\s*\*?\s*(Specific scoring format|Traditional Chinese|Rigorous adherence|Cross-check Forward EPS|Manufacturing logic|First paragraph MUST|No internal monologue)\b",
        r"^\s*\*?\s*(Observation|The Red Flag|Action|Company Profile|Financials \(Key Highlights\))\s*:",
        r"^\s*\*?\s*(Section\s+[IVX0-9]+|TAM|SAM|SOM|Estimation)\s*:",
        r"^\s*\d+\.\s*(Market Size|Key Growth Drivers|AI\s*&\s*New Tech Impact|Long-term Market Share|5-Year Growth Scenarios|Overall Growth Potential)",
        r"^\s*\*?\s*(Data|Trend|Calculation|Driver|Net Profit|Margins|Quality|Critical Check|Conversion Rate|Warning Flag|Total Debt|Net Cash Position|Valuation|Growth|Key Product|Intellectual Property)\s*:",
        r"\b(I must|I need to|Let's|Wait:|As a Fidelity researcher)\b",
    ]
    leak_re = re.compile("|".join(leak_patterns), re.IGNORECASE)

    kept_lines = []
    for line in text.splitlines():
        stripped = line.strip()
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
        result = run_single_agent(agent_num, data, context, rotator)
        result = sanitize_model_output(result)

        if is_agent_execution_failure(result):
            context.setdefault("blocking_issues", []).append(f"Agent {agent_num} {agent_name}: {result}")
            context["analyses"][agent_num] = result
            print(f"  ❌ {result}")
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

        result = append_quality_warnings(agent_num, result)
        
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
    
    # 解析結構化數據
    context["parsed"] = parse_structured_data(context)
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
        result = await run_single_agent_async(agent_num, data, context, rotator)
        result = sanitize_model_output(result)

        if is_agent_execution_failure(result):
            context.setdefault("blocking_issues", []).append(f"Agent {agent_num} {agent_name}: {result}")
            context["analyses"][agent_num] = result
            print(f"  ❌ {result}")
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

        result = append_quality_warnings(agent_num, result)

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

    context["parsed"] = parse_structured_data(context)
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
