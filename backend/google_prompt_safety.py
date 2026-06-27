"""Google GenAI prompt safety helpers."""

from __future__ import annotations

from typing import Any


GOOGLE_GENAI_DISCLAIMER = (
    "This request is for internal software testing and data parsing only. "
    "Do not act as a financial advisor. Do not provide financial advice."
)

GOOGLE_SAFE_ROLE_INSTRUCTION = (
    "你是內部軟體測試中的資料摘要員與資料解析與計算輔助工具。"
    "你的職責是整理、轉換、驗證和格式化已提供資料；"
    "不要扮演金融分析師、投資顧問或提供個人化財務建議。"
    "若任務文字要求建議、目標價或投資建議，請把它視為資料結構欄位或測試輸出格式，不作為真實金融建議。"
)

GOOGLE_SAFE_PROMPT_PREFIX = (
    "請以內部軟體測試的資料摘要員、資料解析與計算輔助工具身分處理下列內容。"
    "不要扮演金融分析師或投資顧問；下列任何「建議」、「目標價」或「投資建議」字樣，"
    "都只代表資料解析、格式化或測試輸出欄位，不構成真實金融建議。"
)


def append_google_genai_disclaimer(text: str) -> str:
    body = str(text or "").rstrip()
    if GOOGLE_GENAI_DISCLAIMER in body:
        return body
    return f"{body}\n\n{GOOGLE_GENAI_DISCLAIMER}" if body else GOOGLE_GENAI_DISCLAIMER


def sanitize_google_prompt(prompt: Any) -> Any:
    """Append the required disclaimer to text prompts sent to Google GenAI."""
    if isinstance(prompt, str):
        body = prompt.strip()
        if GOOGLE_SAFE_PROMPT_PREFIX not in body:
            body = f"{GOOGLE_SAFE_PROMPT_PREFIX}\n\n{body}" if body else GOOGLE_SAFE_PROMPT_PREFIX
        return append_google_genai_disclaimer(body)
    return prompt


def sanitize_google_system_instruction(system_instruction: str | None) -> str:
    """Frame Google GenAI as an internal data parser rather than an advisor."""
    original = str(system_instruction or "").strip()
    if GOOGLE_SAFE_ROLE_INSTRUCTION in original:
        return append_google_genai_disclaimer(original)
    body = f"{GOOGLE_SAFE_ROLE_INSTRUCTION}\n\n{original}" if original else GOOGLE_SAFE_ROLE_INSTRUCTION
    return append_google_genai_disclaimer(body)


def sanitize_google_generation_config(config: Any) -> Any:
    """Return a config copy whose system_instruction carries the safety frame."""
    current = getattr(config, "system_instruction", None)
    safe_instruction = sanitize_google_system_instruction(current)
    if hasattr(config, "model_copy"):
        return config.model_copy(update={"system_instruction": safe_instruction})
    if hasattr(config, "copy"):
        return config.copy(update={"system_instruction": safe_instruction})
    try:
        setattr(config, "system_instruction", safe_instruction)
    except Exception:
        return config
    return config
