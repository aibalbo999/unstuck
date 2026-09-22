"""Separate a terminal future recheck from asserted present catalyst evidence."""
import re
from financial_claim_context import SENTENCE_BREAK

_RECHECK_START = re.compile(r"(?:^|[，,；;。\n])\s*(?:須|需|必須)?等待|(?:^|[，,；;。\n])\s*(?:重新評估條件[：:]?\s*(?:為|是)?\s*等待)")
_RECHECK_END = re.compile(r"(?:重新(?:評估|檢查)|再(?:評估|觀察))(?:條件)?[。.!！\s]*$")
_ASSERTED_OR_AMBIGUOUS = re.compile(r"但是|然而|但|其實|目前|已|截至|最近|過去|近\s*\d|(?:資料|數據)顯示|顯示")
_CLAUSE_BREAK = re.compile(r"，|(?<!\d),|,(?!\d)")


def catalyst_observation_text(text):
    """Only omit an explicit terminal recheck, never earlier facts or mixed claims.

    This projection does not supply evidence. Long/Short still require references;
    numbers, populations, continuity and ownership in the retained text are checked
    against the original catalog. Unsupported/ambiguous suffixes stay visible.
    """
    text = str(text or "")
    for match in _RECHECK_START.finditer(text):
        suffix = text[match.end():]
        body = suffix.rstrip('。.!！?？\n ')
        if (_RECHECK_END.search(suffix) and not _ASSERTED_OR_AMBIGUOUS.search(suffix)
                and not SENTENCE_BREAK.search(body) and not _CLAUSE_BREAK.search(body)):
            return text[:match.start()].rstrip()
    return text
