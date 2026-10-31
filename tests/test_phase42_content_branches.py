"""Saved-source branches; no model calls or historical writes."""
import copy
import gzip
import json
from pathlib import Path
import pytest
from trade_source_contract import bind_trade_payload, CONTRACT_VERSION, source_block, bind_source_prompt
from agent_runtime.deterministic_fallback_trade_evidence import attributed_event_swing_fallback
from market_context_manifest import build_source_blocks, market_assessment_workplan
from workflow_trade_evidence import trade_manifest_matches_input

FIXTURES=Path(__file__).parent/'fixtures'
CASES=json.loads(gzip.decompress((FIXTURES/'report_renderer_oct8_saved.json.gz').read_bytes()))
REJECTED=json.loads(gzip.decompress((FIXTURES/'report_content_rejected_oct8.json.gz').read_bytes()))

@pytest.mark.parametrize('case',REJECTED,ids=lambda c:c['ticker'])
def test_degraded_identical_observation_does_not_lose_its_field_citation(case):
    original=copy.deepcopy(case['payload']); catalog=case['catalog']
    # Replay the actual saved rejected payload, including its local policy prefix.
    context={'data':{},'_trade_source_manifest':{'version':CONTRACT_VERSION,'visible':True,'catalog':catalog}}
    result,assessment=bind_trade_payload(original,context)
    assert assessment['status']=='degraded'
    assert result['catalyst_source_refs']==[]
    assert result['observed_signal']==original['observed_signal']
    assert result['observed_source_refs']==original['observed_source_refs']
    assert '已核驗的日期、數值及來源保留' in result['core_catalyst']
    assert assessment['rejection_diagnostics']['original_core_catalyst']==original['core_catalyst']

@pytest.mark.parametrize('case',[c for c in CASES if c['ticker'] in {'2882.TW','2891.TW'}],ids=lambda c:c['ticker'])
def test_saved_fallback_reports_bound_facts_without_inventing_trade_or_provider(case):
    data=copy.deepcopy(case['snapshot']['analysis_evidence']['sections']['analysis_input']['data'])
    context={'data':data}
    block,catalog,fingerprint=source_block(data)
    bind_source_prompt(context,block,block,catalog,fingerprint)
    assert trade_manifest_matches_input(context['_trade_source_manifest'],data)
    before=copy.deepcopy(data)
    out=attributed_event_swing_fallback(data,context)
    assert out['observed_signal'] and out['observed_source_refs']
    assert out['trade_direction']=='Neutral' and out['entry_zone']==out['target_price']==out['stop_loss']=='N/A'
    assert out['source_assessment']['status']=='degraded'
    assert out['source_assessment']['output_completion']['provider_finish_observed'] is False
    assert out['catalyst_source_refs']==[] and out['event_catalyst'] is None
    validated,assessment=bind_trade_payload(out,context)
    assert validated['observed_signal']==out['observed_signal']
    assert not any(code.startswith('observed_') for code in assessment['reason_codes'])
    assert data==before
    context['data']={**data,'current_price':99999}
    rejected=attributed_event_swing_fallback(data,context)
    assert rejected['observed_signal'] is None and rejected['observed_source_refs']==[]

@pytest.mark.parametrize('agent',[7,16,19])
def test_workplan_uses_only_actual_visible_refs_and_does_not_assign_impact(agent):
    data={'global_market_context':{'items':[{'symbol':'TEST','close':10}]},
          'international_news_context':{'topics':[{'title':'dated input'}]}}
    blocks=build_source_blocks(data,agent_num=agent)
    text=market_assessment_workplan(data,blocks)
    plan=json.loads(text.split('\n',1)[1])
    for source,entry in plan.items():
        assert entry['visible_source_refs']==[b['ref'] for b in blocks if b['source']==source]
        assert 'impact' not in entry and 'reason' not in entry
    assert 'not_assessed' in text and '兩週' in text
    missing=json.loads(market_assessment_workplan({},[]).split('\n',1)[1])
    assert all(v['available_count']==0 and v['visible_source_refs']==[] for v in missing.values())

@pytest.mark.parametrize('force',[False,True])
def test_forced_official_recovery_bypasses_cache_without_changing_dates_or_limits(monkeypatch,force):
    import official_institutional_source as official
    from datetime import datetime,timezone
    captured=[]
    monkeypatch.setattr(official,'expected_sessions',lambda *a,**k:['2026-10-08'])
    def fetch(key,callback,**kwargs):
        captured.append((key,kwargs))
        return {'rows':{'5314':{'foreign':-2508317,'investment_trust':0,'dealer':-61862}},
                'raw_evidence':{'raw_response_sha256':'new-version','retrieved_at':'2026-10-08T13:16:00Z'}},{}
    monkeypatch.setattr('shared_provider_cache.shared_fetch',fetch)
    original={'daily_category_observations':[{'date':'2026-10-08','category':'foreign',
                'net_buy_shares':191683,'source':'saved','unit':'shares'}]}
    before=copy.deepcopy(original)
    out,diagnostics=official.recover_institutional_observations('5314.TWO',original,
        now_epoch=datetime(2026,10,8,13,20,tzinfo=timezone.utc).timestamp(),limit=30,force_refresh=force)
    assert captured[0][1]['use_cache'] is (not force)
    assert captured[0][1]['freshness_seconds']==300  # existing provisional TTL preserved
    assert diagnostics['latest_official_observation']['categories']['foreign']==-2508317
    assert diagnostics['conflicts'][0]['selected']=='primary'
    assert original==before


def test_saved_official_version_receipt_is_exact_and_does_not_claim_finality():
    from institutional_evidence_prompt import build_institutional_source_prompt
    case=next(c for c in CASES if c['ticker']=='5314.TWO')
    data=case['snapshot']['analysis_evidence']['sections']['analysis_input']['data']
    before=copy.deepcopy(data)
    text=build_institutional_source_prompt(data)
    observation=data['institutional_trading']['latest_official_observation']
    assert observation['raw_evidence']['raw_response_sha256'] in text
    assert observation['raw_evidence']['retrieved_at'] in text
    assert '191683' in text and 'provisional' in text
    assert '"finality_guaranteed": false' in text
    assert data==before
