"""Parsed lineage receipts do not add fresh-acquisition denominator events."""
import copy
import json
import pytest

from provider_acquisition import observation_kind, project_acquisition_events


def row(*, count=0, status="success", policy="parsed-receipt-only:v1"):
    return {
        "source": "global_market_context", "provider": "yfinance global context",
        "record_count": count, "status": status, "message": "", "created_at": 100.0,
        "details": {"event_kind": "http_parsed_receipt", "selection_policy": policy},
    }


def test_exact_zero_record_parsed_receipt_is_observational_only():
    assert observation_kind(row()) == "aggregate_count"


def test_unrecognized_policy_retains_existing_empty_classification():
    assert observation_kind(row(policy="unrecognized")) == "empty_count"


def test_positive_record_event_is_not_silently_removed():
    assert observation_kind(row(count=3)) == "fetched_count"


@pytest.mark.parametrize('native_http_flag', [None, True])
def test_parsed_receipt_preserves_denominator_and_original_input(native_http_flag):
    events = [row(count=2), row(status="error")]
    for event in events:
        event["details_json"] = json.dumps({"event_kind": "http_attempt", "http_request_sent": True})
        event.pop("details")
    extra = row()
    if native_http_flag is not None:
        # Real fred_transport_receipts.observe_parsed_response rows retain this
        # observed fact, but are not a second native request.
        extra['details']['http_request_sent'] = native_http_flag
    extra["details_json"] = json.dumps(extra.pop("details"))
    original = copy.deepcopy(events + [extra])
    before, = project_acquisition_events(events, window="last_24h", now=101.0)["sources"]
    after, = project_acquisition_events(events + [extra], window="last_24h", now=101.0)["sources"]
    for field in ("fetched_count", "failed_count", "empty_count", "fetch_attempts", "nonempty_rate", "http_attempt_count"):
        assert after[field] == before[field]
    assert after["fetch_attempts"] == 2 and after["nonempty_rate"] == 0.5
    assert after["aggregate_count"] == before["aggregate_count"] + 1
    assert events + [extra] == original


def test_native_transport_and_actual_parsed_receipt_count_one_http_request():
    base = {'source': 'macro_indicators', 'provider': 'FRED native HTTP',
            'record_count': 0, 'status': 'success', 'message': '', 'created_at': 100.0}
    transport = {**base, 'details_json': json.dumps({'event_kind': 'http_transport_receipt',
        'selection_policy': 'transport-receipt-only:v1', 'http_request_sent': True})}
    parsed = {**base, 'provider': 'FRED parsed observations', 'details_json': json.dumps({
        'event_kind': 'http_parsed_receipt', 'selection_policy': 'parsed-receipt-only:v1',
        'http_request_sent': True, 'raw_count': 1, 'usable_count': 1})}
    projected, = project_acquisition_events([transport, parsed], window='last_24h', now=101.0)['sources']
    assert projected['http_attempt_count'] == 1
    assert projected['fetch_attempts'] == 0 and projected['aggregate_count'] == 2
