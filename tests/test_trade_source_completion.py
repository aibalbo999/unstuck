import json
import asyncio
import pytest
from structured_output_runtime import process_agent_response
from agent_runtime.generation_config import generation_profile, generation_event_metadata

def setup_payload(**updates):
    return dict(trade_direction="Long", entry_zone="100", target_price="110", stop_loss="95",
                support_level="95", resistance_level="110", core_catalyst="等待確認突破條件", risk_level="High",
                support_source_refs=["short_term_market_context.technical_indicators.sma_20"],
                resistance_source_refs=["short_term_market_context.technical_indicators.sma_5"],
                catalyst_source_refs=["short_term_market_context.technical_indicators.sma_5"],
                observed_signal=None, observed_source_refs=[], event_catalyst=None,
                recheck_condition=None, financial_risk_flags=[], **updates)

@pytest.mark.parametrize("missing", ["core_catalyst", "support_source_refs", "risk_level"])
def test_incomplete_runtime_trade_response_is_not_normalized_to_success(missing):
    payload=setup_payload();payload.pop(missing)
    context={"structured_outputs": {24: {"trade_direction":"Neutral"}}}
    process_agent_response(24,json.dumps(payload),context)
    assert not context["structured_outputs"].get(24)

def test_minor_missing_json_brace_with_complete_fields_remains_usable():
    context={"structured_outputs":{}}
    process_agent_response(24,json.dumps(setup_payload())[:-1],context)
    assert context["structured_outputs"][24]["trade_direction"]=="Long"

def test_agent24_completion_budget_and_thinking():
    assert generation_profile(24)["max_output_tokens"] == 4096
    assert generation_event_metadata(24,"gemini-3.8-flash")["thinking_level"]=="low"
    assert generation_event_metadata(24,"gemini-3-flash-preview")["thinking_level"]=="low"

def test_fake_refs_are_rejected_against_visible_catalog():
    context={"structured_outputs":{}, "_trade_source_manifest":{"version":"trade-sources:v1","visible":True,
             "fingerprint":"fixed", "catalog":{"short_term_market_context":{"technical_indicators":{"availability":"available","source":"fixture","as_of":"2026-09-21","sma_20":95,"sma_5":110}}}}}
    payload=setup_payload();payload["catalyst_source_refs"]=["short_term_market_context.invented"]
    process_agent_response(24,json.dumps(payload),context)
    result=context["structured_outputs"][24]
    assert result["trade_direction"]=="Neutral"
    assert result["source_assessment"]["status"]=="degraded"
    assert "invalid_catalyst_source_refs" in result["source_assessment"]["reason_codes"]

def test_visible_exact_refs_retained_without_inventing_new_ones():
    context={"structured_outputs":{}, "_trade_source_manifest":{"version":"trade-sources:v1","visible":True,
             "fingerprint":"fixed", "catalog":{"short_term_market_context":{"technical_indicators":{"availability":"available","source":"fixture","as_of":"2026-09-21","sma_20":95,"sma_5":110}}}}}
    process_agent_response(24,json.dumps(setup_payload()),context)
    result=context["structured_outputs"][24]
    assert result["trade_direction"]=="Long"
    assert result["source_assessment"]["status"]=="source_bound"

def test_omitted_block_cannot_authorize_references():
    from trade_source_contract import bind_source_prompt
    context={"structured_outputs":{}}
    bind_source_prompt(context,"prompt truncated","complete evidence block",{"short_term_market_context":{"x":1}},"hash")
    process_agent_response(24,json.dumps(setup_payload()),context)
    assert context["structured_outputs"][24]["source_assessment"]["status"]=="degraded"

def test_source_repair_is_one_bounded_local_call_and_preserves_upstream():
    from agent_runtime.trade_source_repair import repair_trade_sources
    context={"structured_outputs":{22:{"kept":True},24:{"source_assessment":{"status":"degraded","reason_codes":["missing_support_source_refs"]}}},
             "_trade_source_manifest":{"visible":True,"catalog":{"short_term_market_context":{"technical_indicators":{"availability":"available","source":"fixture","as_of":"2026-09-21","sma_20":95}}}}}
    calls=[]
    async def run(agent,data,ctx,rotator):
        calls.append(agent)
        assert "missing_support_source_refs" in ctx["_audit_retry_instruction"]
        ctx["structured_outputs"][24]={"source_assessment":{"status":"degraded","repair_attempted":True}}
        return "still conservative"
    result=asyncio.run(repair_trade_sources("original",{},context,None,run))
    assert result=="still conservative"
    asyncio.run(repair_trade_sources(result,{},context,None,run))
    assert calls==[24] and context["structured_outputs"][22]=={"kept":True}
    assert "_audit_retry_instruction" not in context

def test_no_visible_sources_do_not_spend_repair_call():
    from agent_runtime.trade_source_repair import repair_trade_sources
    context={"structured_outputs":{24:{"source_assessment":{"status":"degraded"}}},
             "_trade_source_manifest":{"visible":False,"catalog":{}}}
    async def run(*args):raise AssertionError("no evidence available")
    assert asyncio.run(repair_trade_sources("original",{},context,None,run))=="original"

def test_metadata_path_cannot_count_as_trade_evidence():
    context={"structured_outputs":{}, "_trade_source_manifest":{"version":"trade-sources:v1","visible":True,
             "catalog":{"short_term_market_context":{"as_of":"2026-09-21"}}}}
    payload=setup_payload()
    for k in ["support_source_refs","resistance_source_refs","catalyst_source_refs"]:
        payload[k]=["short_term_market_context.as_of"]
    process_agent_response(24,json.dumps(payload),context)
    assert context["structured_outputs"][24]["trade_direction"]=="Neutral"

def test_unparseable_response_cannot_reuse_prior_structured_success():
    context={"structured_outputs":{24: setup_payload()}}
    process_agent_response(24,"",context)
    assert not context["structured_outputs"].get(24)

def test_unterminated_string_is_not_repaired_into_a_market_assertion():
    payload=setup_payload()
    text=json.dumps(payload)[:-1]+', "analysis_markdown": "uncertain claim that never finished'
    context={"structured_outputs":{}}
    process_agent_response(24,text,context)
    assert not context["structured_outputs"].get(24)

def test_incomplete_trade_output_is_not_cached(monkeypatch):
    from agent_runtime import step_cache
    monkeypatch.setattr(step_cache,"AGENT_STEP_CACHE_ENABLED",True)
    monkeypatch.setattr(step_cache,"AGENT_STEP_CACHE_SECONDS",60)
    monkeypatch.setattr(step_cache,"set_cache_json",lambda *a,**k: pytest.fail("incomplete draft cached"))
    step_cache.store_cached_agent_step("key",agent_num=24,context={"structured_outputs":{}},model_id="model",text='{"trade_direction":"Long"')

def test_single_quoted_cut_string_cannot_be_repaired_into_success():
    payload=setup_payload()
    payload["core_catalyst"]="unfinished"
    context={"structured_outputs":{}}
    raw=repr({k:v for k,v in payload.items() if k!="core_catalyst"})[:-1]+", 'core_catalyst': 'unfinished"
    process_agent_response(24,raw,context)
    assert not context["structured_outputs"].get(24)

def test_partial_invalid_reference_list_cannot_authorize_direction():
    context={"structured_outputs":{}, "_trade_source_manifest":{"version":"trade-sources:v1","visible":True,
             "catalog":{"short_term_market_context":{"technical_indicators":{"availability":"available","source":"fixture","as_of":"2026-09-21","sma_20":95,"sma_5":110}}}}}
    payload=setup_payload()
    payload['catalyst_source_refs'].append('short_term_market_context.invented')
    process_agent_response(24,json.dumps(payload),context)
    result=context['structured_outputs'][24]
    assert result['trade_direction']=='Neutral'
    assert result['source_assessment']['status']=='degraded'

def test_price_reference_cannot_substitute_for_institutional_catalyst():
    context={"structured_outputs":{}, "_trade_source_manifest":{"version":"trade-sources:v1","visible":True,
             "catalog":{"short_term_market_context":{"technical_indicators":{"availability":"available","source":"fixture","as_of":"2026-09-21","sma_20":95,"sma_5":110}}}}}
    payload=setup_payload()
    payload['core_catalyst']='外資近三日持續買超且大戶持股集中度維持高檔。'
    process_agent_response(24,json.dumps(payload),context)
    result=context['structured_outputs'][24]
    assert result['trade_direction']=='Neutral'
    assert 'catalyst_evidence_scope_mismatch' in result['source_assessment']['reason_codes']

@pytest.mark.parametrize('extra, expected', [('', 'Long'), ('，同時外資買超', 'Neutral')])
def test_verified_investor_conference_does_not_exempt_flow_claims(extra, expected):
    payload=setup_payload()
    payload['core_catalyst']='已公告法人說明會，等待突破110'+extra
    payload['catalyst_source_refs']=['short_term_market_context.event_calendar.events[0]']
    context={'_trade_source_manifest':{'version':'trade-sources:v1','visible':True,'catalog':{
        'short_term_market_context':{
            'technical_indicators':{'availability':'available','source':'fixture','as_of':'2026-09-21','sma_20':95,'sma_5':110},
            'event_calendar':{'events':[{'date':'2026-09-25','source':'company','label':'法人說明會'}]}}}}}
    process_agent_response(24,json.dumps(payload),context)
    assert context['structured_outputs'][24]['trade_direction']==expected
