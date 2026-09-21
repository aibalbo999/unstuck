"""Saved short-plan price consistency, distinct from external market evidence."""

import re

from evidence_daily_price_claims import DAILY_DATE_RE
from trade_price_inputs import parse_price_range

COVER_STOP_PATH = "rerun_context.parsed.short_setup.cover_stop"


def saved_cover_stop_path(claim: dict, normalized_label: str) -> tuple[str, ...] | None:
    if normalized_label not in {"回補停損", "coverstop", "cover_stop"}:
        return None
    text = str(claim.get("raw_text") or "")
    if DAILY_DATE_RE.search(text) or re.search(r"新聞|券商|news|forecast|預估|預測|昨日", text, re.I):
        return ()
    if str(claim.get("unit") or "").lower() not in {"", "元", "twd"}:
        return ()
    return (COVER_STOP_PATH,)


def saved_cover_stop_number(value, snapshot) -> float | None:
    if not isinstance(snapshot, dict):
        return None
    context = snapshot.get("rerun_context")
    context = context if isinstance(context, dict) else {}
    identities = {str(item).strip() for item in (snapshot.get("pipeline"), context.get("pipeline_id")) if item}
    if identities != {"v3"}:
        return None
    parsed = parse_price_range(value)
    return parsed[0] if parsed and parsed[0] == parsed[1] else None
