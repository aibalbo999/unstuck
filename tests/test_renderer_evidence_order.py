"""Saved Oct8 reports: preserve originals and replay current strict publication gates.

Fixture bytes are gzip-compressed local saved artifacts, not fresh observations.
All rendering/persistence below is isolated; no workflow/model/provider is run.
"""
import asyncio
import copy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from evidence_exit_gate import evaluate_report_evidence
from report_analysis_evidence import freeze_input_evidence
from reporting import ReportRenderer, ReportRequest
from reporting.content_credibility_projection import project_content_credibility
from reporting.report_conformance_projection import project_report_conformance
from report_publication_gate import ReportPublicationBlockedError
from report_persistence import persist_report_bundle, report_bundle_keys_for_filename
from storage.report_storage import InMemoryStorage

CASES=json.loads(gzip.decompress((Path(__file__).parent/'fixtures/report_renderer_oct8_saved.json.gz').read_bytes()))
HISTORICAL_AB=json.loads(gzip.decompress((Path(__file__).parent/'fixtures/report_renderer_saved_modes_ab.json.gz').read_bytes()))

# Preserve the frozen fixture's historical expectations. Current guards also
# reject false MACD narratives, unsupported cashflow causes and invalid sessions.
# These overrides strengthen assertions; they do not alter original artifacts.
CURRENT_STRICT_EXPECTATIONS = {
    '1605.TW': ('rejected', 'blocked'),
    '5314.TWO': ('rejected', 'blocked'),
    '9904.TW': ('rejected', 'blocked'),
    '2882.TW': ('caution', 'blocked'),
    '2891.TW': ('caution', 'blocked'),
}

def current_expectations(case):
    return CURRENT_STRICT_EXPECTATIONS.get(case['ticker'],
        (case['expected_current_evidence'], case['expected_current_conformance']))

def assert_current_strict_reason(case, stored):
    ticker = case['ticker']; gate = stored['evidence_exit_gate']
    if ticker in {'1605.TW', '9904.TW'}:
        relation = 'positive_contraction' if ticker == '1605.TW' else 'crossed_zero'
        assert any(c.get('claimed_change') == 'expansion'
                   and c.get('comparison', {}).get('relation') == relation
                   and c.get('arithmetic_status') == 'mismatch'
                   for c in gate['technical_reasoning_checks'])
    elif ticker == '5314.TWO':
        assert any(c.get('reason_code') == 'cashflow_total_does_not_establish_operating_driver'
                   for c in gate['cashflow_causal_checks'])
    elif ticker in {'2882.TW', '2891.TW'}:
        assert any(c['id'] == 'v4_market_session_integrity_invalid'
                   and 'official_emergency_closure' in c.get('details', {}).get('reason_codes', [])
                   for c in stored['content_credibility']['blocking_issues'])

def saved_context(case, *, forecast=False):
    context=copy.deepcopy(case['snapshot'])
    context.update(copy.deepcopy(context['rerun_context']))
    for key in ('analyses','structured_outputs'):
        context[key]={int(k) if str(k).isdigit() else k:v for k,v in context.get(key,{}).items()}
    if forecast:
        packet=context.pop('analysis_evidence')
        context['_trade_source_manifest']=copy.deepcopy(packet['sections'].get('trade_source_manifest',{}).get('data',{}))
        context['data']['_analysis_input_evidence']=freeze_input_evidence(packet['sections']['analysis_input']['data'])
        context['market_context_original_input_fingerprint']=packet['market_context_original_input_fingerprint']
    else:
        context['saved_analysis_replay']={'source_filename':case['filename'],'source_conclusion_generated_at':context['conclusion_generated_at'],'source_analysis_input_cutoff':context['analysis_evidence']['analysis_input_cutoff']}
    return context

def render(case, **kwargs):
    context=saved_context(case,**kwargs)
    before=copy.deepcopy(context)
    bundle=asyncio.run(ReportRenderer().render_async(ReportRequest(context=context,pipeline_id=case['pipeline_id'],filename=case['filename'],generated_at=case['snapshot']['generated_at'])))
    assert context==before, 'Caller-owned original evidence/context changed'
    return bundle

def check_cold_read(bundle):
    stored=json.loads(json.dumps(bundle.data_snapshot))
    evidence=evaluate_report_evidence(bundle.markdown,stored)
    assert evidence==stored['evidence_exit_gate']==bundle.metadata['evidence_exit_gate']
    content=project_content_credibility(stored)
    assert content is not None
    assert content['status']==stored['content_credibility']['status']==bundle.metadata['content_credibility']['status']
    projected=project_report_conformance(stored['report_conformance'],evidence,content)
    assert projected['status']==stored['report_conformance']['status']==bundle.metadata['report_conformance']['status']
    return stored

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['ticker'])
def test_saved_nine_replay_preserves_current_strict_gates_and_cold_gate_identity(case):
    bundle=render(case)
    stored=check_cold_read(bundle)
    assert stored['analysis_evidence']==case['snapshot']['analysis_evidence']
    assert stored['evidence_exit_gate']['verdict']==current_expectations(case)[0]
    assert_current_strict_reason(case, stored)
    assert stored['report_conformance']['status']==current_expectations(case)[1]
    assert stored['publication_identity']['prediction_eligible'] is False
    storage=InMemoryStorage();keys=report_bundle_keys_for_filename(case['filename'])
    # Preserve all three prior artifacts when the real publication guard blocks.
    for key,content,ctype in [(keys.html_key,case['html'].encode(),'text/html'),(keys.md_key,case['markdown'].encode(),'text/markdown'),(keys.data_key,json.dumps(case['snapshot']).encode(),'application/json')]:storage.save_report(key,content,content_type=ctype)
    before={key:(storage.get_report(key).content,storage.get_report(key).metadata.content_type) for key in [keys.html_key,keys.md_key,keys.data_key]};indexed=[]
    if current_expectations(case)[1]=='blocked':
        with pytest.raises(ReportPublicationBlockedError):persist_report_bundle(filename=case['filename'],html_content=bundle.html,markdown_content=bundle.markdown,data_snapshot=stored,storage=storage,repository=SimpleNamespace(upsert=lambda *a,**kw:indexed.append(kw)))
        assert {key:(storage.get_report(key).content,storage.get_report(key).metadata.content_type) for key in before}==before
        assert indexed==[]
    else:
        persist_report_bundle(filename=case['filename'],html_content=bundle.html,markdown_content=bundle.markdown,data_snapshot=stored,storage=storage,repository=SimpleNamespace(upsert=lambda *a,**kw:{}))
        assert json.loads(storage.get_report(keys.data_key).content)['evidence_exit_gate']==evidence_for(bundle)

def evidence_for(bundle):return evaluate_report_evidence(bundle.markdown,bundle.data_snapshot)

@pytest.mark.parametrize('case',HISTORICAL_AB,ids=lambda c:c['pipeline_id'])
def test_saved_historical_modes_a_b_use_same_immutable_evidence_and_cold_gates(case):
    bundle=render(case)
    stored=check_cold_read(bundle)
    assert stored['analysis_evidence']==case['snapshot']['analysis_evidence']
    assert stored['publication_identity']['prediction_eligible'] is False

@pytest.mark.parametrize('fault',['missing_packet','changed_packet'])
def test_missing_or_invalid_original_input_is_not_rebuilt_from_current_data(fault):
    from evidence_financial_amounts import financial_comparison_snapshot
    case=CASES[0];context=saved_context(case)
    if fault=='missing_packet':
        from analysis_input_provenance import freeze_analysis_inputs
        context.pop('analysis_evidence')
        context['data']['current_price']=999999
        context.update(refreshed_without_analysis_rerun=True,snapshot_refreshed_at='2026-10-08T09:00:00Z')
        freeze_analysis_inputs(context['data'],cutoff='2026-10-08T09:00:00Z')
    else:context['analysis_evidence']['sections']['analysis_input']['data']['current_price']=999999
    before=copy.deepcopy(context)
    bundle=asyncio.run(ReportRenderer().render_async(ReportRequest(context=context,pipeline_id=case['pipeline_id'],generated_at=case['snapshot']['generated_at'])))
    stored=check_cold_read(bundle)
    assert context==before
    assert stored['analysis_evidence']['input_verification']!='hash_verified'
    assert financial_comparison_snapshot(stored)['_financial_source_context']=='original_input_unavailable'
    assert stored['evidence_exit_gate']['verdict']!='approved'

def test_replay_with_refreshed_container_keeps_original_financial_input():
    from evidence_financial_amounts import financial_comparison_snapshot
    case=CASES[0];context=saved_context(case);original=copy.deepcopy(context['analysis_evidence'])
    context['data']['revenue_history']=[999999]*5
    context.update(refreshed_without_analysis_rerun=True,snapshot_refreshed_at='2026-10-08T09:00:00Z')
    bundle=asyncio.run(ReportRenderer().render_async(ReportRequest(context=context,pipeline_id=case['pipeline_id'],generated_at=case['snapshot']['generated_at'])))
    stored=check_cold_read(bundle)
    assert stored['analysis_evidence']==original
    comparison=financial_comparison_snapshot(stored)
    assert comparison['_financial_source_context']=='preserved_original_analysis_input'
    assert comparison['data']==original['sections']['analysis_input']['data']
    assert comparison['data']['revenue_history']!=stored['data']['revenue_history']
    assert stored['publication_identity']['prediction_eligible'] is False

@pytest.mark.parametrize('fault,reason',[('value','support_level_source_value_mismatch'),('basis','support_level_source_scope_mismatch'),('missing_ref','support_level_source_observation_unverified')])
def test_reference_value_basis_and_missing_source_keep_real_gate_boundaries(fault,reason):
    case=CASES[0];context=saved_context(case,forecast=True);payload=context['structured_outputs'][24]
    payload['resistance_level']='N/A';payload['resistance_source_refs']=[]
    payload['price_level_evidence']=[row for row in payload['price_level_evidence'] if row['field']=='support_level']
    if fault=='value':payload['support_level']='99999'
    elif fault=='basis':payload['price_level_evidence'][0]['inputs'][0]['price_basis']='unadjusted_exchange_ohlc'
    else:
        payload['support_source_refs']=['short_term_market_context.unavailable']
        payload['price_level_evidence'][0]['inputs'][0]['ref']=payload['support_source_refs'][0]
    context['parsed']['trade_setup']=copy.deepcopy(payload)
    bundle=asyncio.run(ReportRenderer().render_async(ReportRequest(context=context,pipeline_id=case['pipeline_id'],generated_at=case['snapshot']['generated_at'])))
    stored=check_cold_read(bundle);gate=stored['evidence_exit_gate']
    assert reason in [r for check in gate['source_admission']['price_reference_checks'] for r in check['reason_codes']]
    # The untouched frozen report also contains a false MACD narrative.
    # An absent price reference cannot remove that independent rejection.
    assert gate['verdict']=='rejected'
    assert any(c.get('status')=='mismatch' for c in gate['technical_reasoning_checks'])

@pytest.mark.parametrize('case',[c for c in CASES if current_expectations(c)[1]=='blocked'],ids=lambda c:c['ticker'])
def test_new_forecast_capture_sees_same_strict_gates_as_saved_reader(case):
    bundle=render(case,forecast=True)
    stored=check_cold_read(bundle)
    assert stored['evidence_exit_gate']['verdict']==current_expectations(case)[0]
    assert_current_strict_reason(case, stored)
    assert stored['report_conformance']['status']=='blocked'
    assert stored['analysis_evidence']['input_verification']=='hash_verified'

@pytest.mark.parametrize('pipeline',['v1','v2','v3','v4'])
def test_gate_snapshot_contains_input_before_first_gate_all_modes(pipeline,monkeypatch):
    import reporting.renderer as module
    from analysis_input_provenance import freeze_analysis_inputs
    data={'ticker':'TEST','current_price':100,'quant_metrics':{'rsi':61}}
    freeze_analysis_inputs(data,cutoff='2026-10-08T07:00:00Z')
    real=module.evaluate_report_evidence;seen=[]
    def evidence(md,snapshot):
        assert snapshot['analysis_evidence']['input_verification']=='hash_verified'
        seen.append(copy.deepcopy(snapshot['analysis_evidence']))
        return real(md,snapshot)
    async def html(context):return '<html><p>股價: 100</p></html>'
    monkeypatch.setattr(module,'evaluate_report_evidence',evidence)
    monkeypatch.setattr(module,'generate_html_report_async',html)
    monkeypatch.setattr(module,'generate_markdown_report',lambda c:'- 股價: 100')
    bundle=asyncio.run(ReportRenderer().render_async(ReportRequest(context={'ticker':'TEST','data':data,'parsed':{},'pipeline_id':pipeline},pipeline_id=pipeline,generated_at='2026-10-08T07:01:00Z')))
    assert seen and all(x==bundle.data_snapshot['analysis_evidence'] for x in seen)
    assert evidence_for(bundle)==bundle.data_snapshot['evidence_exit_gate']
