import asyncio

from agent_runtime.trade_source_repair import repair_trade_sources
from test_trade_source_repair_integration_review import context, degraded


def test_repair_explains_failed_claim_instead_of_only_internal_reason_code():
    ctx=context();text=degraded(ctx)
    ctx['structured_outputs'][24]['core_catalyst']='RSI過熱且外資累積，暫時觀望'
    ctx['structured_outputs'][24]['source_assessment']['reason_codes']=['catalyst_evidence_scope_mismatch']
    instructions=[]
    async def run(*args):
        instructions.append(ctx['_audit_retry_instruction'])
        return 'candidate'
    asyncio.run(repair_trade_sources(text,{},ctx,None,run))
    assert 'RSI過熱且外資累積' in instructions[0]
    assert '主體、期間、觀測日、數值與單位' in instructions[0]
    assert 'event_calendar 整個物件' in instructions[0]
    assert 'Neutral 也必須' in instructions[0]
    assert ctx['analyses']=={22:'kept22',23:'kept23'}


def test_visible_institutional_only_catalog_can_receive_one_source_repair():
    ctx=context();text=degraded(ctx);calls=[]
    ctx['_trade_source_manifest']['catalog']={'short_term_market_context':{'institutional_evidence':{'records':[
        {'value':10,'unit':'thousand_shares','population':'total','window':{'kind':'trailing_trading_days','trading_days':5},
         'observed_at':'2026-09-21','provider':'fixture'}]}}}
    async def run(*args):calls.append(24);return 'candidate'
    asyncio.run(repair_trade_sources(text,{},ctx,None,run))
    assert calls==[24]


def test_availability_flag_without_dated_evidence_does_not_spend_repair():
    ctx=context();text=degraded(ctx)
    ctx['_trade_source_manifest']['catalog']={'short_term_market_context':{
        'technical_indicators':{'availability':'available','sma_20':95}}}
    async def run(*args):raise AssertionError('No usable source')
    assert asyncio.run(repair_trade_sources(text,{},ctx,None,run))==text
