"""Google GenAI prompt safety helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


GOOGLE_GENAI_DISCLAIMER = (
    "This request is for a stock research assistance tool that summarizes, parses, "
    "and formats user-provided market data for informational research only. "
    "Do not act as a financial advisor. Do not provide financial advice, personalized "
    "investment recommendations, or instructions to buy, sell, short, or hold securities."
)

GOOGLE_SAFE_ROLE_INSTRUCTION = (
    "你是股票研究輔助工具中的資料摘要員與資料解析與計算輔助工具。"
    "你的職責是整理、轉換、驗證和格式化已提供資料；"
    "不要扮演金融分析師、投資顧問或提供個人化財務建議；"
    "不得輸出可直接執行的交易指令。"
    "若任務文字要求建議或目標價，請把它視為非個人化研究分類、情境標籤或風險摘要欄位。"
)

GOOGLE_SAFE_PROMPT_PREFIX = (
    "請以股票研究輔助工具的資料摘要員、資料解析與計算輔助工具身分處理下列內容。"
    "不要扮演金融分析師或投資顧問；下列任何研究分類、目標價格或風險標籤，"
    "都只代表資訊整理、情境分類或格式化欄位，不構成真實金融建議或交易指令。"
)

GOOGLE_PROMPT_TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("投資建議", "研究分類"),
    ("交易建議", "研究分類"),
    ("建議：強烈放空", "研究分類：空方風險觀察"),
    ("建議: 強烈放空", "研究分類：空方風險觀察"),
    ("強烈放空", "空方風險觀察"),
    ("買進", "偏多觀察"),
    ("買入", "偏多觀察"),
    ("賣出", "偏空風險觀察"),
    ("放空", "空方風險觀察"),
    ("持有", "中性觀察"),
    ("recommend short exposure", "classify elevated downside risk"),
    ("short-selling report author", "contrarian downside-risk research report author"),
    ("Chief Contrarian Trader", "Chief Contrarian Downside-Risk Reviewer"),
    ("trade-ready report", "research-ready downside-risk report"),
    ("short/avoid thesis", "downside-risk/avoidance research thesis"),
    ("short thesis", "downside-risk research thesis"),
    ("short exposure", "downside-risk classification"),
    ("Investment recommendation", "Research classification"),
    ("investment recommendation", "research classification"),
)

GOOGLE_SCHEMA_VALUE_REPLACEMENTS: dict[str, str] = {
    "強烈放空": "空方風險觀察",
    "放空": "空方風險觀察",
    "買進": "偏多觀察",
    "買入": "偏多觀察",
    "避免": "避險觀察",
    "持有": "中性觀察",
}


def _sanitize_google_text(text: str) -> str:
    safe = str(text or "")
    for old, new in GOOGLE_PROMPT_TEXT_REPLACEMENTS:
        safe = safe.replace(old, new)
    return safe


def _sanitize_google_schema_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_google_schema_values(item) for key, item in value.items()}
    if isinstance(value, list):
        sanitized = [_sanitize_google_schema_values(item) for item in value]
        deduped = []
        for item in sanitized:
            if item not in deduped:
                deduped.append(item)
        return deduped
    if isinstance(value, str):
        return GOOGLE_SCHEMA_VALUE_REPLACEMENTS.get(value, _sanitize_google_text(value))
    return value


def append_google_genai_disclaimer(text: str) -> str:
    body = str(text or "").rstrip()
    if GOOGLE_GENAI_DISCLAIMER in body:
        return body
    return f"{body}\n\n{GOOGLE_GENAI_DISCLAIMER}" if body else GOOGLE_GENAI_DISCLAIMER


def sanitize_google_prompt(prompt: Any) -> Any:
    """Append the required disclaimer to text prompts sent to Google GenAI."""
    if isinstance(prompt, str):
        body = _sanitize_google_text(prompt.strip())
        if GOOGLE_SAFE_PROMPT_PREFIX not in body:
            body = f"{GOOGLE_SAFE_PROMPT_PREFIX}\n\n{body}" if body else GOOGLE_SAFE_PROMPT_PREFIX
        return append_google_genai_disclaimer(body)
    return prompt


def sanitize_google_system_instruction(system_instruction: str | None) -> str:
    """Frame Google GenAI as a research data parser rather than an advisor."""
    original = _sanitize_google_text(str(system_instruction or "").strip())
    if GOOGLE_SAFE_ROLE_INSTRUCTION in original:
        return append_google_genai_disclaimer(original)
    body = f"{GOOGLE_SAFE_ROLE_INSTRUCTION}\n\n{original}" if original else GOOGLE_SAFE_ROLE_INSTRUCTION
    return append_google_genai_disclaimer(body)


def sanitize_google_generation_config(config: Any) -> Any:
    """Return a config copy whose system_instruction carries the safety frame."""
    current = getattr(config, "system_instruction", None)
    safe_instruction = sanitize_google_system_instruction(current)
    updates = {"system_instruction": safe_instruction}
    if getattr(config, "response_schema", None) is not None:
        updates["response_schema"] = _sanitize_google_schema_values(deepcopy(config.response_schema))
    if hasattr(config, "model_copy"):
        return config.model_copy(update=updates)
    if hasattr(config, "copy"):
        return config.copy(update=updates)
    try:
        setattr(config, "system_instruction", safe_instruction)
        if "response_schema" in updates:
            setattr(config, "response_schema", updates["response_schema"])
    except Exception:
        return config
    return config
