"""Keep historical reference identity distinct from current observation freshness.

A verified packet/hash establishes the saved input binding only. It does not
establish official source truth, market-session validity, or historical PIT.
Never recover a missing saved catalog by rebuilding positional references today.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _ticker(value):
    return value.strip().upper() if isinstance(value, str) else ""


def evaluation_day(context):
    raw = _mapping(context).get("candidate_evaluation_at")
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if moment.tzinfo is not None:
            return moment.astimezone(ZoneInfo("Asia/Taipei")).date()
    except (ValueError, TypeError):
        pass
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def saved_trade_source_catalog(snapshot):
    """Return an input/output-bound historical catalog, or explicit unknown.

    ``analysis_input`` in the receipt is for the internal lineage calculation;
    callers must not include it in public diagnostic checks.
    """
    from report_analysis_evidence import validate_analysis_evidence
    from workflow_trade_evidence import trade_manifest_matches_input
    packet = validate_analysis_evidence(_mapping(snapshot).get("analysis_evidence"))
    sections = _mapping(packet.get("sections"))
    manifest = _mapping(_mapping(sections.get("trade_source_manifest")).get("data"))
    inputs = _mapping(_mapping(sections.get("analysis_input")).get("data"))
    context = _mapping(_mapping(snapshot).get("rerun_context"))
    outputs = _mapping(context.get("structured_outputs"))
    output = _mapping(outputs.get("24", outputs.get(24)))
    output_fingerprint = _mapping(output.get("source_assessment")).get("source_fingerprint")
    reasons = []
    if packet.get("input_verification") != "hash_verified" or not trade_manifest_matches_input(manifest, inputs):
        reasons.append("saved_catalog_input_binding_unverified")
    if not output_fingerprint or output_fingerprint != manifest.get("fingerprint"):
        reasons.append("saved_catalog_output_binding_unverified")
    catalog = _mapping(manifest.get("catalog"))
    root = _mapping(catalog.get("short_term_market_context"))
    input_ticker = _ticker(inputs.get("ticker"))
    current_ticker = _ticker(_mapping(_mapping(snapshot).get("data")).get("ticker"))
    top_ticker = _ticker(_mapping(snapshot).get("ticker"))
    catalog_ticker = _ticker(root.get("ticker"))
    if (not input_ticker or current_ticker != input_ticker or catalog_ticker != input_ticker
            or (top_ticker and top_ticker != input_ticker)):
        reasons.append("saved_catalog_security_identity_unverified")
    # Some records carry their own identity. A matching parent fingerprint does
    # not authorize borrowing an explicitly different issuer's record.
    for group, field in (("institutional_evidence", "records"), ("ownership_evidence", "records"),
                         ("recent_news", "items"), ("event_calendar", "events")):
        values = _mapping(root.get(group)).get(field, [])
        for value in values if isinstance(values, list) else []:
            if isinstance(value, dict) and "ticker" in value and _ticker(value["ticker"]) != input_ticker:
                reasons.append("saved_catalog_record_security_mismatch")
                break
    bound_day = _day(root.get("as_of"))
    try:
        cutoff = datetime.fromisoformat(str(packet.get("analysis_input_cutoff")).replace("Z", "+00:00"))
        cutoff_day = cutoff.astimezone(ZoneInfo("Asia/Taipei")).date() if cutoff.tzinfo else None
    except (ValueError, TypeError):
        cutoff_day = None
    if not bound_day or not cutoff_day or bound_day > cutoff_day:
        reasons.append("saved_catalog_temporal_binding_unverified")
    receipt = {"status": "unverified" if reasons else "bound_saved_catalog",
               "reason_codes": reasons, "catalog_fingerprint": manifest.get("fingerprint"),
               "catalog_as_of": bound_day.isoformat() if bound_day else None,
               "scope": "saved input/output identity; not official truth, session validity or historical PIT",
               "analysis_input": inputs if not reasons else {}}
    return ({} if reasons else catalog), receipt


def reference_temporal_status(catalog, ref, *, as_of):
    """Check the exact saved record without reindexing or finding substitutes."""
    from trade_source_contract import resolve_reference
    value = resolve_reference(catalog, ref)
    result = {"reference": ref, "status": "missing", "observed_date": None,
              "age_days": None, "max_age_days": None, "evaluation_date": as_of.isoformat()}
    if value is None:
        return result
    root = _mapping(catalog.get("short_term_market_context"))
    observed = None
    maximum = None
    if ".institutional_evidence.records[" in ref:
        observed, maximum = _day(_mapping(value).get("observed_at")), 7
    elif ".ownership_evidence.records[" in ref:
        observed, maximum = _day(_mapping(value).get("observed_at")), 14
    elif ".recent_news.items[" in ref:
        observed, maximum = _day(_mapping(value).get("published_at")), 14
    elif ".technical_indicators." in ref:
        observed, maximum = _day(_mapping(root.get("technical_indicators")).get("as_of")), 7
    elif ".daily_market_data.bars[" in ref:
        # Historical bars remain legitimate references for levels; the window's
        # latest observation must still be current. A past bar is not today's bar.
        observed, maximum = _day(_mapping(root.get("daily_market_data")).get("as_of")), 7
    elif ".event_calendar.events[" in ref:
        # The event date may be future by definition. Source binding is checked
        # separately; never equate a scheduled event date with a publication date.
        event_day = _day(_mapping(value).get("end_date") or _mapping(value).get("date"))
        if event_day is None:
            return {**result, "status": "date_unverified"}
        return {**result, "status": "stale" if event_day < as_of else "scheduled_event_requires_existing_event_gate",
                "event_date": event_day.isoformat(), "date_role": "event_date_not_publication_date"}
    else:
        return {**result, "status": "unsupported_reference_kind"}
    bound_day = _day(root.get("as_of"))
    if observed is None or bound_day is None:
        return {**result, "status": "date_unverified", "max_age_days": maximum}
    age = (as_of - observed).days
    status = ("future_at_source_binding" if observed > bound_day else "future_at_evaluation" if age < 0
              else "stale" if age > maximum else "current_within_bound")
    return {**result, "status": status, "observed_date": observed.isoformat(), "age_days": age, "max_age_days": maximum}
