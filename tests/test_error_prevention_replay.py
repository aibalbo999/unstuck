"""Offline corpus contracts: missing evidence is never counted as a repaired job."""
import importlib.util
import json
from pathlib import Path
import pytest


def module():
    path=Path(__file__).parents[1]/'scripts/replay_error_prevention.py'
    assert path.exists(), 'Historical replay CLI must be available without production state'
    spec=importlib.util.spec_from_file_location('error_replay',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def test_missing_evidence_is_not_success():
    result=module().replay_case({'kind':'job','identity':'missing','context':{},'data':{}})
    assert result['classification']=='evidence_missing'


def test_neutral_case_uses_real_current_contract_and_keeps_true_order():
    fn=module().replay_case
    setup={'trade_direction':'Neutral','entry_zone':'N/A','target_price':'N/A','stop_loss':'N/A',
           'core_catalyst':'等待量縮後，再重新評估是否有明確進場時點。','risk_level':'High'}
    case={'kind':'job','identity':'fixture','data':{'ticker':'2305.TW'},
          'labels':['mode_execution'],'context':{'pipeline_id':'v4','parsed':{'trade_setup':setup},
          'analyses':{'24':'等待重新評估'},'structured_outputs':{'24':setup}}}
    assert fn(case)['checks']['mode_execution']==[]
    setup['core_catalyst']+='次日買入10張。'
    assert fn(case)['checks']['mode_execution']


def test_corpus_replay_validates_hash_and_stays_inside_root(tmp_path):
    m=module();case={'kind':'job','identity':'missing','context':{},'data':{}}
    content=json.dumps(case).encode();(tmp_path/'case.json').write_bytes(content)
    manifest={'schema_version':1,'cases':[{'identity':'missing','payload':'case.json','sha256':m.sha256(content)}]}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    assert m.replay_manifest(tmp_path/'manifest.json')['results'][0]['classification']=='evidence_missing'
    (tmp_path/'case.json').write_text('{}')
    assert m.replay_manifest(tmp_path/'manifest.json')['results'][0]['classification']=='evidence_missing'
    manifest['cases'][0]['payload']='../outside.json'
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    assert 'outside' in m.replay_manifest(tmp_path/'manifest.json')['results'][0]['missing'][0]


def test_export_redacts_credentials_but_keeps_financial_source_and_key_slot():
    m=module()
    value={'metadata':{'key_hash':'sensitive','key_slot':3,'headers':{'Authorization':'Bearer secret'}},
           'data':{'foreign_net_buy':1528.58},'env':{'TOKEN':'secret'}}
    clean,paths=m.redact_sensitive(value)
    assert clean['metadata']['key_slot']==3 and clean['data']==value['data']
    assert 'sensitive' not in json.dumps(clean) and 'secret' not in json.dumps(clean)
    assert paths


def test_report_unknown_original_input_binding_is_not_a_fixed_case():
    m=module()
    case={'kind':'report','identity':'unknown','data':{'ticker':'2305.TW'},'markdown':'等待重新評估。',
          'snapshot':{'data':{'ticker':'2305.TW'},'analysis_evidence':{'input_verification':'unknown'}},
          'context':{'pipeline_id':'v4','parsed':{'trade_setup':{'trade_direction':'Neutral',
          'entry_zone':'N/A','core_catalyst':'等待重新評估。','risk_level':'High'}}}}
    assert m.replay_case(case)['classification']=='evidence_missing'


def test_registered_full_corpus_when_explicitly_provided():
    import os
    location=os.environ.get('STOCK_ERROR_PREVENTION_CORPUS')
    if not location:pytest.skip('Full retained corpus is private; set STOCK_ERROR_PREVENTION_CORPUS for offline replay')
    m=module();root=Path(location)
    result=m.replay_manifest(root/'manifest.json')
    m.write_json(root/'current-replay.json',result)
    registry=json.loads((Path(__file__).parent/'fixtures/error_prevention_manifest_20260922.json').read_text())
    assert {r['identity'] for r in result['results']}=={r['identity'] for r in registry['cases']}
    assert all(r['classification'] in {'evidence_missing','fixed_in_scoped_replay','still_reproduced','true_error_still_blocked'} for r in result['results'])
    baseline={r['identity']:r['current_classification'] for r in registry['cases']}
    for row in result['results']:
        if baseline[row['identity']] in {'fixed_in_scoped_replay','true_error_still_blocked'}:
            assert row['classification']==baseline[row['identity']], row['identity']
    assert all(r.get('original_input_verified') is True for r in result['results']
               if r.get('kind')=='report' and r['classification']=='fixed_in_scoped_replay')


def test_confirmed_true_error_becoming_valid_is_a_regression_not_a_fix(monkeypatch):
    import final_audit
    monkeypatch.setattr(final_audit,'run_final_report_audit',lambda *a,**k:{'critical':[]})
    m=module();input_hash='a'*64
    case={'kind':'job','identity':'known-bad','labels':['mode_execution'],'input_hash':input_hash,'data':{'ticker':'2305.TW'},
          'manual_review':{'confirmed_true_error':True,'input_hash':input_hash},
          'context':{'pipeline_id':'v4','analyses':{'24':'等待重新評估。'},'structured_outputs':{'24':{
          'trade_direction':'Neutral','entry_zone':'N/A','core_catalyst':'等待重新評估。','risk_level':'High'}}}}
    assert m.replay_case(case)['classification']=='true_error_unexpectedly_passed'


def test_serialized_credential_metadata_is_redacted():
    clean,paths=module().redact_sensitive({'message':'Authorization: Bearer secret.token.value; api_key="private-credential"',
        'OPENAI_API_KEY':'private-key','data':{'revenue':100}})
    assert 'secret.token.value' not in clean['message'] and 'private-credential' not in clean['message']
    assert 'OPENAI_API_KEY' not in clean and clean['data']=={'revenue':100} and paths


def test_unknown_original_failure_family_cannot_be_claimed_fixed():
    case={'kind':'job','identity':'uncovered','labels':[], 'data':{'ticker':'2305.TW'},
          'context':{'pipeline_id':'v4','analyses':{'24':'等待重新評估。'},'structured_outputs':{'24':{
          'trade_direction':'Neutral','entry_zone':'N/A','core_catalyst':'等待重新評估。','risk_level':'High'}}}}
    result=module().replay_case(case)
    assert result['classification']=='evidence_missing'
    assert any('original failure family' in reason for reason in result['missing'])

@pytest.mark.parametrize('name',['api_key','access_token'])
def test_json_string_credential_assignment_is_redacted(name):
    value=json.dumps({name:'private-credential'})
    clean,paths=module().redact_sensitive({'message':value})
    assert 'private-credential' not in clean['message'] and paths
