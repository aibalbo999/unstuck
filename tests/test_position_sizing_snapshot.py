"""Trusted workflow sizing inputs survive snapshots without borrowing model data."""

from copy import deepcopy
import json

import pytest

from data_trust_snapshot import build_data_snapshot, verify_data_snapshot_integrity
from position_sizing_runtime import assess_position_plan
from report_analysis_completeness import assess_report_analysis_completeness
from test_position_sizing_contract import audited_plan, context as sizing_context, plan
from test_report_analysis_completeness_v2 import b_context


def calculated_context():
    payload = b_context()
    payload['position_sizing_context'] = sizing_context()
    valid_plan = audited_plan(plan(), payload['position_sizing_context'])
    output = payload['structured_outputs'][16]
    output['position_plan'] = valid_plan
    output['position_sizing_assessment'] = assess_position_plan(
        valid_plan, payload, output['recommendation'], output['analysis_markdown'])
    assert output['position_sizing_assessment']['issues'] == []
    payload['parsed']['position_plan'] = deepcopy(valid_plan)
    return payload


def position_status(snapshot):
    return assess_report_analysis_completeness(snapshot)['mode_assessment']['position_sizing_status']


def make_snapshot(context):
    snapshot = build_data_snapshot(context, pipeline_id='v2', max_bytes=1_000_000)
    # Exercise the actual persisted JSON types/keys as well as the builder.
    result = json.loads(json.dumps(snapshot, ensure_ascii=False, allow_nan=False))
    assert verify_data_snapshot_integrity(result)['valid']
    return result


def test_calculated_context_survives_canonical_snapshot_and_resave_with_integrity():
    payload = calculated_context()
    before = deepcopy(payload)
    assert position_status(payload) == 'calculated'
    snapshot = make_snapshot(payload)
    assert position_status(snapshot) == 'calculated'
    assert snapshot['rerun_context']['position_sizing_context'] == payload['position_sizing_context']
    resaved = make_snapshot(snapshot)
    assert position_status(resaved) == 'calculated'
    assert resaved['rerun_context']['position_sizing_context'] == payload['position_sizing_context']
    assert payload == before


def test_legacy_calculated_receipt_without_trusted_inputs_remains_unconfirmed():
    payload = calculated_context()
    payload.pop('position_sizing_context')
    snapshot = make_snapshot(payload)
    assert 'position_sizing_context' not in snapshot['rerun_context']
    assert position_status(snapshot) == 'unconfirmed'


@pytest.mark.parametrize('location', ['data', 'output', 'model_evidence'])
def test_provider_or_model_sizing_inputs_never_enter_workflow_channel(location):
    payload = calculated_context()
    inputs = payload.pop('position_sizing_context')
    if location == 'data':
        payload['data']['position_sizing_context'] = inputs
    elif location == 'output':
        payload['structured_outputs'][16]['position_sizing_context'] = inputs
    else:
        payload['structured_outputs'][16]['position_plan']['sizing_evidence']['position_sizing_context'] = inputs
        payload['parsed']['position_plan'] = deepcopy(payload['structured_outputs'][16]['position_plan'])
    snapshot = make_snapshot(payload)
    assert 'position_sizing_context' not in snapshot['rerun_context']
    assert position_status(snapshot) == 'unconfirmed'


@pytest.mark.parametrize('alteration', ['input', 'hash', 'receipt'])
def test_tampered_workflow_context_stays_unconfirmed_even_with_valid_snapshot_hash(alteration):
    payload = calculated_context()
    if alteration == 'input':
        payload['position_sizing_context']['inputs']['risk_budget_amount'] = 10_000
    elif alteration == 'hash':
        payload['position_sizing_context']['context_sha256'] = '0' * 64
    else:
        payload['structured_outputs'][16]['position_sizing_assessment']['calculation']['position_percent'] = 100
    snapshot = make_snapshot(payload)
    assert position_status(snapshot) == 'unconfirmed'


def test_invalid_outer_integrity_keeps_quality_warning_separate_from_valid_sizing():
    snapshot = make_snapshot(calculated_context())
    snapshot['company_name'] = 'changed after sealing'
    integrity = verify_data_snapshot_integrity(snapshot)
    assert integrity['valid'] is False
    # The index caller passes the independent integrity verdict to completeness.
    result = assess_report_analysis_completeness({**snapshot, 'snapshot_integrity': integrity})
    assert result['quality_warning'] is True
    assert result['mode_assessment']['position_sizing_status'] == 'calculated'
    assert result['status'] not in {'complete', 'observation'}


@pytest.mark.parametrize('pipeline', ['v1', 'v2', 'v3', 'v4'])
def test_snapshot_never_creates_sizing_context_when_workflow_did_not_supply_it(pipeline):
    snapshot = build_data_snapshot({'pipeline_id': pipeline, 'data': {}}, pipeline_id=pipeline)
    assert 'position_sizing_context' not in snapshot['rerun_context']


def test_explicit_workflow_absence_does_not_recover_stale_nested_inputs():
    payload = calculated_context()
    payload['rerun_context'] = {'position_sizing_context': deepcopy(payload['position_sizing_context'])}
    payload['position_sizing_context'] = None
    snapshot = make_snapshot(payload)
    assert snapshot['rerun_context'].get('position_sizing_context') is None
    assert position_status(snapshot) == 'unconfirmed'
