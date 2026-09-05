"""Local text boundaries shared by deterministic financial claim checks."""

from __future__ import annotations

import re


NUMBER = r"(?<![\d.,+\-])[-+]?\d+(?:\.\d+)?(?![\d.])"
VALUE_LINK = r"(?:高達|達到|達|為|約為|約|處於|維持在|=|:|：)*"
PERIOD_LABEL = (
    r"(?:20\d{2}年(?:\d{1,2}月|第?[1-4]季)?|TTM|LTM|"
    r"最新年度|前一年度|上年度|本年度|年度|全年|去年同期月|"
    r"本月|上月|月度|月|本季|上季|季度|季|去年|今年|基期|本期|前期)"
)
REVENUE_GROWTH = re.compile(
    rf"(?P<label>{PERIOD_LABEL})?營收(?:的)?(?:需|必須|要)?"
    r"(?P<growth_kind>年增率|月增率|季增率|成長率|增長率|年增|月增|季增|成長|增長|暴增|增加|提升)"
    rf"{VALUE_LINK}(?P<num>{NUMBER})%",
    re.IGNORECASE,
)
SENTENCE_BREAK = re.compile(r"[。；;！？!?\n]|(?<!\d)\.(?!\d)")
CONDITIONAL = re.compile(r"若|如果|假如|一旦|假設|倘若|除非|尚未達成")
THRESHOLD = re.compile(
    r"(?:停損|止損|加碼|減碼|進場|出場|觸發|買入)(?:條件|門檻|線)|條件|門檻|觸發點|"
    r"才(?:可|能|考慮)?(?:加碼|買入|進場)"
)
PROJECTION = re.compile(r"情境|預估|預測|預計|預期|假設|未來|明年|目標|展望|推估|隱含")
NEGATION = re.compile(r"並非|不(?!僅|只|但)|缺乏|沒有|尚未|未(?:能|具)|無法|勿|避免")


def sentence_span(text: str, start: int, end: int) -> tuple[int, int]:
    left = 0
    for match in SENTENCE_BREAK.finditer(text, 0, start):
        left = match.end()
    following = SENTENCE_BREAK.search(text, end)
    return left, following.start() if following else len(text)


def section_heading(text: str, start: int) -> str:
    headings = list(re.finditer(r"(?m)^#{1,6}[^\n]*", text[:start]))
    return headings[-1].group() if headings else ""


def is_conditional_claim(text: str, start: int, end: int) -> bool:
    left, right = sentence_span(text, start, end)
    prefix = text[left:start]
    clause_prefix = re.split(r"[，,|]|但是|然而|但", prefix)[-1]
    # A later comma-separated condition must not negate an already stated actual.
    suffix = re.split(r"[，,|]", text[end:right], maxsplit=1)[0]
    heading = section_heading(text, start)
    return bool(
        CONDITIONAL.search(prefix) or NEGATION.search(clause_prefix)
        or THRESHOLD.search(prefix + suffix) or CONDITIONAL.search(suffix)
        or THRESHOLD.search(heading)
    )


def is_actual_claim(text: str, start: int, end: int) -> bool:
    left, right = sentence_span(text, start, end)
    prefix = re.split(r"[，,|]|但是|然而|但", text[left:start])[-1]
    suffix = re.split(r"[，,|]|但是|然而|但", text[end:right], maxsplit=1)[0]
    return not (
        is_conditional_claim(text, start, end)
        or PROJECTION.search(prefix + text[start:end] + suffix)
        or PROJECTION.search(section_heading(text, start))
    )


def revenue_growth_claims(text: str, *, actual_only: bool = False) -> list[re.Match]:
    predicate = is_actual_claim if actual_only else lambda t, s, e: not is_conditional_claim(t, s, e)
    return [match for match in REVENUE_GROWTH.finditer(text) if predicate(text, match.start(), match.end())]


def revenue_period(label: str) -> tuple[str, int | None]:
    dated = re.fullmatch(r"(20\d{2})年(?:(\d{1,2})月|第?([1-4])季)?", label)
    if dated:
        year, month, quarter = dated.groups()
        if month:
            return "monthly", int(year) * 12 + int(month) - 1
        if quarter:
            return "quarterly", int(year) * 4 + int(quarter) - 1
        return "annual", int(year)
    if label in {"前一年度", "上年度", "去年"}:
        return "annual", -1
    if label in {"最新年度", "本年度", "今年"}:
        return "annual", 0
    if label in {"上月", "本月"}:
        return "monthly", -1 if label == "上月" else 0
    if label in {"上季", "本季"}:
        return "quarterly", -1 if label == "上季" else 0
    if label in {"基期", "前期", "本期"}:
        return "explicit", 0 if label == "本期" else -1
    if label.upper() in {"TTM", "LTM"} or label in {"年度", "全年"}:
        return "annual", None
    if "月" in label:
        return "monthly", None
    if "季" in label:
        return "quarterly", None
    return "unknown", None
