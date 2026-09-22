"""Syntactic boundaries excluding metadata and incomplete non-financial fragments."""
import re
from typing import Any
from evidence_claim_types import calendar_metadata_label, calendar_metadata_match
from evidence_technical_claims import MOVING_AVERAGE_PERIOD_LIST_RE

def _normalize_match_text(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z_\u4e00-\u9fff]+", "", str(value or "").lower())


_NUMERIC_UNIT_PATTERN = r"(?:TWD|%|x|X|倍|億|元|張|B|M|K|k|T)"
_TABLE_VALUE_LABEL_RE = re.compile(
    rf"^\s*(?:NT\$|\$)?\s*-?\d[\d,]*(?:\.\d+)?\s*(?:{_NUMERIC_UNIT_PATTERN}|billion[_ ]?twd|million[_ ]?twd|thousand[_ ]?twd)\s*$",
    re.IGNORECASE,
)
_NON_CLAIM_LABEL_MARKERS = (
    "code", "duration", "error", "hash", "pipeline", "prompt", "provider", "recordcount", "twse", "tradingview",
    "normalized financials", "交易計畫健康度", "核心論點", "數據/證據", "近 10 日每日趨勢", "daily trend",
    "Recent catalysts", "近期催化劑", "抓取", "資料日期", "時間", "程式碼", "版本", "錯誤", "耗時", "雜湊",
)
_NORMALIZED_NON_CLAIM_LABEL_MARKERS = tuple(_normalize_match_text(marker) for marker in _NON_CLAIM_LABEL_MARKERS)

def is_non_claim_match(line: str, match: re.Match[str], *, table_cell: bool = False) -> bool:
    # A source citation followed by a bare, truncated counter-evidence fragment
    # does not name a financial metric. Do not discard real values with units.
    if (not match.group("unit") and re.search(r"[)）]；反證[：:]\s*$", line[:match.start("num")])
            and re.search(r"[（(]來源[：:]", line[:match.start("num")])
            and not line[match.end("num"):].strip()):
        return True
    # Only a complete, explicitly labelled moving-average period list is metadata.
    if MOVING_AVERAGE_PERIOD_LIST_RE.match(line[match.start("num"):]):
        return True
    if calendar_metadata_label(match.group("label")):
        return calendar_metadata_match(match)
    timestamp = re.search(r"\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}:\d{2}", line)
    if (timestamp and timestamp.start() <= match.start("label") <= timestamp.end()) or (line[max(0, match.start("label") - 1):match.start("label")] == "_" and re.search(r"`normalized[_ ]financials`", line[max(0, match.start("label") - 40):match.end("label")], re.IGNORECASE)) or re.search(r"`institutional_trading`\s*[:：]\s*\d+\s*-\s*day\s+lookback\b", line, re.IGNORECASE) or re.search(r"(?:不可用|unavailable|fallback|error|錯誤)\s*[:：]?\s*(?:4\d{2}|5\d{2})\b", line[max(0, match.start("num") - 80):match.end("num") + 1], re.IGNORECASE) or re.match(r"(?:\s*-\s*(?:day|days|week|weeks|month|months)\b|\s*(?:日|天|週|周|個月|月)\b)", line[match.end("num"):], re.IGNORECASE) or (table_cell and _TABLE_VALUE_LABEL_RE.fullmatch(match.group("label"))):
        return True
    label = _normalize_match_text(match.group("label"))
    number_start = match.start("num")
    if any(marker in label for marker in _NORMALIZED_NON_CLAIM_LABEL_MARKERS) or re.search(r"[()（）].*(?:previous|前值)\s*$", match.group("label"), re.IGNORECASE):
        return True
    if re.search(r"\d{1,2}:\s*$", line[:number_start]) and any(marker in label for marker in ("marketdata", "截至", "資料日期", "資料時間", "抓取時間")):
        return True
    if number_start <= 0 or line[number_start - 1] != "T":
        return False
    suffix = line[match.end("num"):]
    return bool(re.match(r":\d{2}(?::\d{2})?(?:[.,+\-Z]|$)", suffix))

