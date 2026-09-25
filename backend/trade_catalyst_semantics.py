"""Separate mode-D facts, dated events, future rechecks and policy warnings.

New claims are checked before normalization. This projection never supplies a
missing claim, source, event date, timezone or confirmation status.
"""
from __future__ import annotations

from datetime import date
import re

SEMANTIC_FIELDS = ("observed_signal", "observed_source_refs", "event_catalyst",
                   "recheck_condition", "financial_risk_flags")
EVENT_STATUSES = {"unknown", "scheduled", "confirmed", "date_range"}
_ABSENT = {"", "n/a", "na", "null", "unknown", "未評估", "未知", "資料不足"}


def optional_claim_text(value):
    return value.strip() if isinstance(value, str) and value.strip().lower() not in _ABSENT else None


def _refs(value):
    return [item.strip() for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def normalize_trade_catalyst_fields(payload):
    """Additive normalization; legacy reports keep absent fields absent."""
    result = {}
    for key in ("observed_signal", "recheck_condition"):
        if key in payload:
            result[key] = optional_claim_text(payload.get(key))
    for key in ("observed_source_refs", "financial_risk_flags"):
        if key in payload:
            result[key] = _refs(payload.get(key))
    if "event_catalyst" in payload:
        event = payload.get("event_catalyst")
        result["event_catalyst"] = None
        if isinstance(event, dict):
            result["event_catalyst"] = {
                **{key: optional_claim_text(event.get(key)) for key in ("description", "date", "end_date", "timezone")},
                "status": event.get("status") if isinstance(event.get("status"), str) and event.get("status") in EVENT_STATUSES else "unknown",
                "source_refs": _refs(event.get("source_refs")),
            }
    return result


def _valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _event_issues(event, catalog, visible):
    from trade_source_contract import reference_is_evidence, resolve_reference
    if event is None:
        return []
    if not isinstance(event, dict):
        return ["invalid_event_catalyst"]
    if any(value is not None and not isinstance(value, str) for key, value in event.items() if key in {"description", "date", "end_date", "timezone"}):
        return ["invalid_event_catalyst"]
    if not isinstance(event.get("source_refs"), list) or any(not isinstance(ref, str) for ref in event["source_refs"]):
        return ["invalid_event_catalyst_refs"]
    status = event.get("status")
    if status == "unknown":
        return (["unknown_event_contains_assertion"] if event["source_refs"] or any(optional_claim_text(event.get(k)) for k in ("description", "date", "end_date", "timezone")) else [])
    if not isinstance(status, str) or status not in EVENT_STATUSES or not _valid_date(event.get("date")) or not optional_claim_text(event.get("description")):
        return ["invalid_event_schedule"]
    refs = event["source_refs"]
    if not visible or not refs:
        return ["unbound_event_schedule"]
    calendar = catalog.get("short_term_market_context", {}).get("event_calendar", {})
    start, end = _valid_date(calendar.get("as_of")), _valid_date(calendar.get("window_end"))
    event_date = _valid_date(event["date"])
    event_end = _valid_date(event.get("end_date"))
    if not start or not end or event_date > end or (event_end or event_date) < start:
        return ["event_outside_verified_window"]
    if status == "date_range" and (not event_end or event_end <= event_date):
        return ["invalid_event_date_range"]
    for ref in refs:
        if (not isinstance(ref, str) or not re.fullmatch(r"short_term_market_context\.event_calendar\.events\[\d+\]", ref)
                or not reference_is_evidence(catalog, ref, "catalyst_source_refs")):
            return ["invalid_event_catalyst_refs"]
        record = resolve_reference(catalog, ref)
        # A schedule is not issuer confirmation; publisher dates are not event dates.
        if (event["description"] != record.get("label") or event["date"] != record.get("date")
                or status != record.get("date_status")
                or optional_claim_text(event.get("end_date")) != optional_claim_text(record.get("end_date"))
                or optional_claim_text(event.get("timezone")) != optional_claim_text(record.get("timezone"))):
            return ["event_schedule_scope_mismatch"]
    return []


def trade_semantic_issues(payload, context):
    """Inspect original types and field meanings; callers retain source checks."""
    from trade_catalyst_claims import catalyst_observation_text
    from trade_financial_risk import NEGATIVE_FCF_WARNING, negative_fcf_value
    from trade_source_contract import SUPPORTED_VERSIONS, CONTRACT_VERSION
    issues = []
    manifest = context.get("_trade_source_manifest")
    manifest = manifest if isinstance(manifest, dict) else {}
    catalog = manifest.get("catalog", {})
    visible = bool(manifest.get("visible")) and manifest.get("version") in SUPPORTED_VERSIONS
    if manifest.get("version") == CONTRACT_VERSION:
        issues.extend("missing_" + key for key in SEMANTIC_FIELDS if key not in payload)
    for key in ("observed_signal", "recheck_condition"):
        if key in payload and payload[key] is not None and not isinstance(payload[key], str):
            issues.append("invalid_" + key)
    for key in ("observed_source_refs", "financial_risk_flags"):
        if key in payload and (not isinstance(payload[key], list) or any(not isinstance(item, str) for item in payload[key])):
            issues.append("invalid_" + key)
    recheck = optional_claim_text(payload.get("recheck_condition"))
    # Only an explicit terminal future recheck is exempt from present-tense proof.
    if recheck and catalyst_observation_text(recheck):
        issues.append("recheck_contains_actual_or_ambiguous_claim")
    if "event_catalyst" in payload:
        issues.extend(_event_issues(payload.get("event_catalyst"), catalog, visible))
    flags = _refs(payload.get("financial_risk_flags"))
    if any(flag != NEGATIVE_FCF_WARNING for flag in flags):
        issues.append("unsupported_financial_risk_flag")
    if (NEGATIVE_FCF_WARNING in flags or NEGATIVE_FCF_WARNING in str(payload.get("core_catalyst") or "")) and negative_fcf_value(context.get("data", {})) is None:
        issues.append("unverified_financial_policy_warning")
    observed = optional_claim_text(payload.get("observed_signal"))
    if observed or recheck or payload.get("event_catalyst"):
        # A newly populated fact field must never hide an unrelated old summary.
        core = catalyst_observation_text(payload.get("core_catalyst"), allow_policy_suffix=negative_fcf_value(context.get("data", {})) is not None)
        if core.strip("，,；;。.!！ \n") and core.strip("，,；;。.!！ \n") != (observed or "").strip("，,；;。.!！ \n"):
            issues.append("core_catalyst_semantic_mismatch")
    return list(dict.fromkeys(issues))
