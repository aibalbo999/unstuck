"""Persisted hashes describe canonical bytes; a damaged input is never resealed."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from data_trust_snapshot_integrity import set_snapshot_integrity,verify_data_snapshot_integrity
from report_persistence import persist_report_bundle
from report_publication_gate import ReportPublicationBlockedError
from report_artifacts import ReportArtifactLocator
from storage.report_storage import InMemoryStorage


def snapshot():
    return set_snapshot_integrity({'ticker':'TEST','pipeline':'v1',
        'data':{'ticker':'TEST','current_price':100,'analysis_input_hash':'unchanged-input'},
        'final_audit':{'status':'passed','critical':[]},
        'report_conformance':{'status':'passed'},'content_credibility':{'status':'passed'},
        'evidence_exit_gate':{'verdict':'approved','failed_count':0,'coverage_complete':True,
            'sampled_claims':[{'reported_value':100,'status':'verified','_technical_as_of':'2026-10-22',
                               '_price_history_months':{'secret_internal':'not a public claim'}}]}})


def publish(payload, storage, indexed):
    return persist_report_bundle(filename='TEST_v1_report_job_boundary.html',html_content='<html>100</html>',
        markdown_content='股價：100',data_snapshot=payload,storage=storage,
        repository=SimpleNamespace(upsert=lambda *a,**kw:indexed.append(kw) or {}))


def test_canonical_pruning_retains_valid_cold_hash_and_original_input():
    payload=snapshot();before=deepcopy(payload);storage=InMemoryStorage();indexed=[]
    assert verify_data_snapshot_integrity(payload)['valid']
    publish(payload,storage,indexed)
    cold=ReportArtifactLocator(storage).require_bundle('TEST_v1_report_job_boundary.html').read_data_snapshot()
    assert verify_data_snapshot_integrity(cold)['valid']
    assert cold['snapshot_hash'] and cold['snapshot_hash']!=before['snapshot_hash']
    claim=cold['evidence_exit_gate']['sampled_claims'][0]
    assert claim=={'reported_value':100,'status':'verified'}
    assert cold['data']==before['data'] and payload==before and len(indexed)==1


@pytest.mark.parametrize('damage',['price','claim','internal'])
def test_corrupted_presealed_input_is_rejected_before_any_write(damage):
    payload=snapshot();storage=InMemoryStorage();indexed=[]
    if damage=='price':payload['data']['current_price']=101
    elif damage=='claim':payload['evidence_exit_gate']['sampled_claims'][0]['reported_value']=101
    else:payload['evidence_exit_gate']['sampled_claims'][0]['_technical_as_of']='2025-01-01'
    assert not verify_data_snapshot_integrity(payload)['valid']
    with pytest.raises(ReportPublicationBlockedError,match='snapshot_hash mismatch'):publish(payload,storage,indexed)
    assert storage.list_reports()==[] and indexed==[]


def test_legacy_missing_hash_is_not_given_a_new_attestation():
    payload=snapshot()
    for k in ('snapshot_hash','content_hash','snapshot_size_bytes'):payload.pop(k,None)
    storage=InMemoryStorage();publish(payload,storage,[])
    cold=ReportArtifactLocator(storage).require_bundle('TEST_v1_report_job_boundary.html').read_data_snapshot()
    assert 'snapshot_hash' not in cold and 'content_hash' not in cold
