"""Recognize a target field's explicit unavailable status before numeric parsing."""

from __future__ import annotations

import re
import unicodedata


_TARGET_LABEL = (
    r"(?:短期|中期|長期)(?:目標|潛力)?(?:\s*\(\s*\d+\s*(?:個月|月|年)\s*\))?"
    r"|(?:3|6|12)\s*(?:個月|月|months?|m)(?:目標(?:股價|價)?)?"
    r"|(?:熊市|基本|牛市)(?:情境)?|(?:bear|base|bull)(?:\s+case)?"
    r"|目標股價|目標價|target\s+price|price\s+target"
)
_UNASSESSED_PREFIX = re.compile(
    rf"^\s*(?:(?:{_TARGET_LABEL})\s*:\s*)?"
    r"(?:N\s*/\s*A|NA|not\s+(?:available|assessed|applicable)|unassessed"
    r"|尚未評估|未評估|不適用|資料不足)"
    r"(?=$|[\s/(\[:;,。\-])",
    re.IGNORECASE,
)
_EXPLICIT_NUMERIC_TARGET = re.compile(
    r"(?:目標股價|目標價|合理股價|合理價(?:值)?|target\s+price|price\s+target)"
    r"\s*(?:(?:[:=]|為|約|介於|落在|由|from|上調至|下修至|修正為|is|at|around|about"
    r"|between|revised\s+to|raised\s+to|lowered\s+to)\s*)?"
    r"(?:(?:NT\$?|NTD|TWD|USD|US\$|HK\$|\$|新台幣|臺幣|台幣)\s*)?"
    r"[+]?\d[\d,.]*(?:e[+-]?\d+)?",
    re.IGNORECASE,
)
_CLAUSE_SEPARATOR = re.compile(r"[();；。\n]|(?<!\d)[,，]|[,，](?!\d)")
_REFERENCE_PREFIX = re.compile(
    r"(?:舊|歷史|前次|先前|原先|\bprevious|\bprior|\bhistorical|\bold)\s*(?:的\s*)?$",
    re.IGNORECASE,
)
_REFERENCE_SUFFIX = re.compile(r"未採用|不採用|僅供參考|僅為參考|not\s+adopted", re.IGNORECASE)
_CURRENT_PREFIX = re.compile(r"本次|目前|現在|不是|並非|\bcurrent|\bnew|\bnot\b", re.IGNORECASE)


def target_price_context(value: str) -> str:
    """Keep only current target clauses when a leading status says unavailable.

    This applies only to target values, not generic prices or prose containing
    an unavailable metric such as EPS. Mixed explicit price claims stay subject
    to ordinary direction checks rather than becoming a no-position exemption.
    """
    text = unicodedata.normalize("NFKC", str(value or ""))
    if not _UNASSESSED_PREFIX.match(text):
        return text
    targets = list(_EXPLICIT_NUMERIC_TARGET.finditer(text))
    current_clauses = []
    for index, target in enumerate(targets):
        prefix = _CLAUSE_SEPARATOR.split(text[:target.start()])[-1]
        end = targets[index + 1].start() if index + 1 < len(targets) else len(text)
        remainder = text[target.end():end]
        suffix = re.split(r"[();；。\n]", remainder, maxsplit=1)[0]
        # Old or expressly unused targets explain missing evidence. A current
        # target, even inside parentheses, must still reach direction checks.
        reference = _REFERENCE_PREFIX.search(prefix) and not _CURRENT_PREFIX.search(prefix)
        if not (reference or _REFERENCE_SUFFIX.search(suffix)):
            # Preserve the horizon label and full range/revision clause. Drop
            # other explanation numbers before the shared numeric extractor.
            tail = _CLAUSE_SEPARATOR.split(remainder, maxsplit=1)[0]
            current_clauses.append(prefix + target.group(0) + tail)
    return "; ".join(current_clauses)


def target_is_explicitly_unassessed(value: str) -> bool:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return bool(_UNASSESSED_PREFIX.match(text) and not target_price_context(text))
