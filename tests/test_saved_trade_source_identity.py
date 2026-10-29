"""Saved list indices must retain their original identity and separate expiry."""
from copy import deepcopy
from datetime import date

from report_analysis_evidence import _digest, _seal
from workflow_trade_evidence import trade_input_fingerprint


def record(day="2026-10-20", value=120):
    return {"path": "institutional_trading.daily_total_net_buy_last_10[9].net_buy_thousand_shares",
            "value": value, "unit": "thousand_shares", "population": "total",
            "window": {"kind": "day", "date": day}, "observed_at": day,
            "provider": "fixture", "lineage_status": "recomputed"}


def saved(day="2026-10-20"):
    ref = "short_term_market_context.institutional_evidence.records[1]"
    catalog = {"short_term_market_context": {"ticker": "2356.TW", "as_of": "2026-10-21", "institutional_evidence": {
        "records": [record("2026-10-14", 50), record(day)], "availability": "available"}}}
    data = {"ticker": "2356.TW"}
    manifest = {"visible": True, "version": "trade-sources:v4", "catalog": catalog,
                "fingerprint": _digest(catalog), "input_fingerprint": trade_input_fingerprint(data)}
    section = lambda value: {"status": "preserved", "data": value, "fingerprint": _digest(value)}
    packet = _seal({"schema_version": 1, "status": "preserved", "capture_boundary": "analysis_start",
                   "input_verification": "hash_verified", "analysis_input_cutoff": "2026-10-21T02:00:00+00:00",
                   "sections": {"trade_source_manifest": section(manifest), "analysis_input": section(data)}})
    setup = {"core_catalyst": "2026-10-20三大法人合計單日淨買超120千股。", "catalyst_source_refs": [ref],
             "observed_signal": "2026-10-20三大法人合計單日淨買超120千股。", "observed_source_refs": [ref]}
    return {"analysis_evidence": packet, "data": deepcopy(data), "pipeline": "v4",
            "generated_at": "2026-10-21T03:00:00+00:00", "rerun_context": {"parsed": {"trade_setup": setup},
            "structured_outputs": {"24": {**setup, "source_assessment": {"source_fingerprint": manifest["fingerprint"]}}}}}


def test_frozen_catalog_preserves_reference_when_current_list_shrinks():
    from saved_trade_source_identity import saved_trade_source_catalog, reference_temporal_status
    snapshot = saved()
    catalog, evidence = saved_trade_source_catalog(snapshot)
    assert evidence["status"] == "bound_saved_catalog"
    assert catalog["short_term_market_context"]["institutional_evidence"]["records"][1]["value"] == 120
    assert reference_temporal_status(catalog, "short_term_market_context.institutional_evidence.records[1]", as_of=date(2026, 10, 27))["status"] == "current_within_bound"


def test_expired_reference_remains_expired_not_promoted_by_saved_hash():
    from saved_trade_source_identity import saved_trade_source_catalog, reference_temporal_status
    catalog, _ = saved_trade_source_catalog(saved("2026-10-19"))
    result = reference_temporal_status(catalog, "short_term_market_context.institutional_evidence.records[1]", as_of=date(2026, 10, 27))
    assert result["status"] == "stale"
    assert result["age_days"] == 8


def test_invalid_packet_missing_original_input_and_wrong_output_binding_stay_unknown():
    from saved_trade_source_identity import saved_trade_source_catalog
    invalid = saved()
    invalid["analysis_evidence"]["sections"]["trade_source_manifest"]["data"]["catalog"]["short_term_market_context"]["as_of"] = "2026-10-22"
    assert saved_trade_source_catalog(invalid)[1]["status"] == "unverified"
    missing = saved()
    missing["analysis_evidence"]["sections"]["analysis_input"] = {"status": "omitted"}
    missing["analysis_evidence"].pop("packet_fingerprint")
    _seal(missing["analysis_evidence"])
    assert saved_trade_source_catalog(missing)[1]["status"] == "unverified"
    wrong = saved()
    wrong["rerun_context"]["structured_outputs"]["24"]["source_assessment"]["source_fingerprint"] = "0" * 64
    assert saved_trade_source_catalog(wrong)[1]["status"] == "unverified"


def test_future_observation_cannot_be_backdated_to_the_saved_cutoff():
    from saved_trade_source_identity import saved_trade_source_catalog, reference_temporal_status
    catalog, _ = saved_trade_source_catalog(saved("2026-10-22"))
    status = reference_temporal_status(catalog, "short_term_market_context.institutional_evidence.records[1]", as_of=date(2026, 10, 27))
    assert status["status"] == "future_at_source_binding"


def test_saved_packet_cannot_be_borrowed_by_a_different_security():
    from saved_trade_source_identity import saved_trade_source_catalog
    for target in ("3231.TW", "2356.TWO", "2356", ""):
        snapshot = saved()
        snapshot["data"]["ticker"] = target
        catalog, identity = saved_trade_source_catalog(snapshot)
        assert catalog == {}
        assert "saved_catalog_security_identity_unverified" in identity["reason_codes"]
    snapshot = saved()
    snapshot["ticker"] = "3231.TW"
    assert saved_trade_source_catalog(snapshot)[1]["status"] == "unverified"


def test_same_issuer_new_snapshot_data_preserves_binding_but_foreign_record_does_not():
    from saved_trade_source_identity import saved_trade_source_catalog
    snapshot = saved()
    snapshot["data"].update(ticker="2356.tw", new_observation=True)
    assert saved_trade_source_catalog(snapshot)[1]["status"] == "bound_saved_catalog"
    packet = snapshot["analysis_evidence"]
    manifest_section = packet["sections"]["trade_source_manifest"]
    manifest = manifest_section["data"]
    manifest["catalog"]["short_term_market_context"]["institutional_evidence"]["records"][1]["ticker"] = "3231.TW"
    manifest["fingerprint"] = _digest(manifest["catalog"])
    manifest_section["fingerprint"] = _digest(manifest)
    packet.pop("packet_fingerprint")
    _seal(packet)
    snapshot["rerun_context"]["structured_outputs"]["24"]["source_assessment"]["source_fingerprint"] = manifest["fingerprint"]
    assert "saved_catalog_record_security_mismatch" in saved_trade_source_catalog(snapshot)[1]["reason_codes"]


def test_real_missing_reference_is_not_rebound_to_similar_record():
    from saved_trade_source_identity import saved_trade_source_catalog, reference_temporal_status
    catalog, _ = saved_trade_source_catalog(saved())
    assert reference_temporal_status(catalog, "short_term_market_context.institutional_evidence.records[99]", as_of=date(2026, 10, 27))["status"] == "missing"


def test_event_date_is_not_mistaken_for_source_publication_or_reused_after_event():
    from saved_trade_source_identity import reference_temporal_status
    catalog = {"short_term_market_context": {"as_of": "2026-10-21", "event_calendar": {"events": [
        {"date": "2026-11-02", "label": "conference", "source": "fixture", "status": "scheduled"}]}}}
    ref = "short_term_market_context.event_calendar.events[0]"
    assert reference_temporal_status(catalog, ref, as_of=date(2026, 10, 27))["status"] == "scheduled_event_requires_existing_event_gate"
    assert reference_temporal_status(catalog, ref, as_of=date(2026, 11, 3))["status"] == "stale"


def test_gate_keeps_original_index_even_when_current_index_points_elsewhere(monkeypatch):
    import reporting.content_credibility_trade_basis as module
    snapshot = saved()
    current = {"short_term_market_context": {"as_of": "2026-10-27", "institutional_evidence": {
        "records": [record("2026-10-20", 120), record("2026-10-21", -999)], "availability": "available"}}}
    monkeypatch.setattr(module, "source_catalog", lambda data: current)
    observed = []
    monkeypatch.setattr(module, "institutional_claim_lineage", lambda data, value: observed.append(value["value"]) or {"status": "recomputed", "independent_primary_source_verified": False})
    monkeypatch.setattr(module, "catalyst_claim_issues", lambda text, catalog, refs: [])
    context = {**snapshot["rerun_context"], "candidate_evaluation_at": "2026-10-27T20:00:00+08:00"}
    result = module.evaluate_trade_basis(context, snapshot["data"], "v4", snapshot=snapshot)
    assert observed == [120]
    assert not result["blocking_issues"]
    assert any(check["id"] == "v4_trade_source_identity" for check in result["checks"])


def test_saved_reference_expiry_blocks_even_when_catalog_binding_valid(monkeypatch):
    import reporting.content_credibility_trade_basis as module
    snapshot = saved("2026-10-19")
    monkeypatch.setattr(module, "institutional_claim_lineage", lambda data, value: {"status": "recomputed"})
    monkeypatch.setattr(module, "catalyst_claim_issues", lambda text, catalog, refs: [])
    context = {**snapshot["rerun_context"], "candidate_evaluation_at": "2026-10-27T20:00:00+08:00"}
    result = module.evaluate_trade_basis(context, snapshot["data"], "v4", snapshot=snapshot)
    assert "v4_trade_reason_source_stale" in {item["id"] for item in result["blocking_issues"]}
    assert "v4_trade_reason_source_missing" not in {item["id"] for item in result["blocking_issues"]}


def test_refreshed_snapshot_does_not_substitute_new_flow_into_historical_claim(monkeypatch):
    import reporting.content_credibility_trade_basis as module
    snapshot = saved()
    snapshot["data"] = {"ticker": "2356.TW", "new_data": True}
    observed = []
    monkeypatch.setattr(module, "institutional_claim_lineage", lambda data, value: observed.append(data) or {"status": "recomputed"})
    monkeypatch.setattr(module, "catalyst_claim_issues", lambda text, catalog, refs: [])
    context = {**snapshot["rerun_context"], "candidate_evaluation_at": "2026-10-27T20:00:00+08:00"}
    original = deepcopy(snapshot)
    module.evaluate_trade_basis(context, snapshot["data"], "v4", snapshot=snapshot)
    assert observed == [{"ticker": "2356.TW"}]
    assert snapshot == original
