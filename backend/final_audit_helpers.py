"""Small deterministic helpers for final report audit orchestration."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from validators import _extract_target_price_numbers

PERCENT_NUMBER_PATTERN = r"(?:[+＋\-−－]\s*)?\d+(?:[.．]\d+)?(?:[eE][-+]?\d+)?\s*[%％]"
RANGE_SEPARATOR_PATTERN = r"(?:-|–|—|－|−|~|～|〜|至|到|\bto\b|\band\b|與|和)"


def is_agent_execution_failure(text: str) -> bool:
    return bool(text and text.startswith("[Agent ") and "執行失敗" in text)


def recommendation_value(recommendation: dict, key_fragment: str) -> str:
    for key, value in (recommendation or {}).items():
        if key_fragment in str(key):
            return str(value)
    return ""


def extract_first_price(value: str) -> Optional[float]:
    text = re.sub(PERCENT_NUMBER_PATTERN, "", str(value or ""))
    try:
        prices = _extract_target_price_numbers(text)
    except Exception:
        return None
    if not prices:
        return None
    if _looks_like_price_range(text) and len(prices) >= 2:
        return sum(prices[:2]) / 2
    return prices[0]


def _looks_like_price_range(text: str) -> bool:
    return bool(
        re.search(
            rf"\d\s*(?:元|塊)?\s*{RANGE_SEPARATOR_PATTERN}\s*(?:NT\$?|NTD|TWD|新台幣|臺幣|台幣)?\s*\d",
            text,
        )
    )


def add_unique_issue(items: list[str], issue: str):
    if issue and issue not in items:
        items.append(issue)


def source_note_corrections(data_notes: list) -> list[str]:
    corrections = []
    if any("口徑互斥" in note for note in data_notes):
        corrections.append("資料源出現淨利/淨利率口徑互斥時，報告已採用 EPS/P/E 自洽的校準口徑。")
    if any("revenueGrowth" in note for note in data_notes):
        corrections.append("Yahoo revenueGrowth 已降級為近期/季度口徑，不得直接當年度或 TTM 年增率。")
    return corrections


def future_price_history_correction(price_history: dict, *, today: date | None = None) -> str:
    if not isinstance(price_history, dict):
        return ""
    future_dates = []
    comparison_date = today or date.today()
    for raw_date in price_history.keys():
        try:
            parsed_date = datetime.fromisoformat(str(raw_date)[:10]).date()
        except ValueError:
            continue
        if parsed_date > comparison_date:
            future_dates.append(str(raw_date)[:10])
    if not future_dates:
        return ""
    return f"歷史股價含未來日期，報告圖表會忽略：{', '.join(sorted(future_dates)[:5])}。"
