"""Synthetic offline quotes exercise FCF policy; never official/execution evidence."""
import json,hashlib
from structured_output_runtime import process_agent_response
from trade_financial_risk import NEGATIVE_FCF_WARNING,LEGACY_NEGATIVE_FCF_WARNING
from trade_source_contract import bind_source_prompt
from test_trade_source_completion import setup_payload


def context(value):
    ctx={'pipeline_id':'v4','data':{'free_cash_flow_raw':value},'structured_outputs':{}}
    catalog={'short_term_market_context':{'technical_indicators':{'availability':'available','source':'synthetic offline fixture;not official','price_adjustment_basis':'synthetic test basis;not exchange raw','as_of':'2026-09-24','sma_20':95,'sma_5':110}}}
    block=json.dumps(catalog);bind_source_prompt(ctx,block,block,catalog,hashlib.sha256(block.encode()).hexdigest());return ctx


def priced_payload():
    # These two inputs are declared synthetic SMA observations in context().
    # This tests the native parser contract, not actual SMA or exchange quotes.
    payload=setup_payload()
    payload['price_level_evidence']=[
        {'field':field,'kind':'direct_reference','operation':'identity',
         'inputs':[{'ref':payload[role][0],'observed_date':'2026-09-24',
                    'window_sessions':period,'price_basis':'synthetic test basis;not exchange raw'}]}
        for field,role,period in [('support_level','support_source_refs',20),
                                  ('resistance_level','resistance_source_refs',5)]
    ]
    return payload


def test_stale_owned_negative_flag_removed_before_binding_preserves_supported_plan():
    ctx=context(100);payload={**priced_payload(),'financial_risk_flags':[LEGACY_NEGATIVE_FCF_WARNING]};raw=json.dumps(payload)
    process_agent_response(24,raw,ctx,completion_diagnostics={'finish_reasons':['STOP']});out=ctx['structured_outputs'][24]
    assert out['trade_direction']=='Long' and out['entry_zone']==payload['entry_zone']
    assert out['source_assessment']['status']=='source_bound' and not out['financial_risk_flags']
    assert out['source_assessment']['output_completion']['raw_sha256']==hashlib.sha256(raw.encode()).hexdigest()


def test_uncertain_info_fcf_is_limitation_not_asserted_financial_pressure():
    ctx=context(-1);text=process_agent_response(24,json.dumps(priced_payload()),ctx)
    out=ctx['structured_outputs'][24];assert NEGATIVE_FCF_WARNING in out['financial_risk_flags']
    assert '短線財務壓力升高' not in text and '不得視為已確認' in text
    assert out['source_assessment']['status']=='source_bound'


def test_unsupported_fcf_assertion_in_reason_is_not_cured_by_flag_cleanup():
    ctx=context(100);payload={**priced_payload(),'core_catalyst':'自由現金流為負，因此股價會上漲','financial_risk_flags':[LEGACY_NEGATIVE_FCF_WARNING]}
    process_agent_response(24,json.dumps(payload),ctx);out=ctx['structured_outputs'][24]
    from reporting.content_credibility_trade_basis import evaluate_trade_basis
    gate=evaluate_trade_basis({'parsed':{'trade_setup':out}},ctx['data'],'v4')
    assert any(issue['id']=='v4_unverified_fcf_as_catalyst' for issue in gate['blocking_issues'])


def test_missing_current_price_receipt_still_rejects_legacy_payload_before_fcf_assertions():
    ctx=context(-1)
    process_agent_response(24,json.dumps(setup_payload()),ctx)
    assert 'price_level_evidence' in ctx['_trade_incomplete_fields']
    assert not ctx['structured_outputs'].get(24)


def test_synthetic_price_metadata_mismatch_still_degrades_plan():
    ctx=context(100);payload=priced_payload()
    payload['price_level_evidence'][0]['inputs'][0]['observed_date']='2026-09-23'
    process_agent_response(24,json.dumps(payload),ctx)
    out=ctx['structured_outputs'][24]
    assert out['trade_direction']=='Neutral'
    assert 'support_level_source_date_mismatch' in out['source_assessment']['reason_codes']


def test_synthetic_receipts_do_not_establish_official_execution_approval():
    from report_source_admission import report_source_admission
    ctx=context(100);payload=priced_payload()
    process_agent_response(24,json.dumps(payload),ctx)
    out=ctx['structured_outputs'][24]
    assert out['source_assessment']['status']=='source_bound'
    gate=report_source_admission({**ctx['data'],'ticker':'2305.TW'},out)
    assert not gate['source_eligible'] and not gate['eligible'] and not gate['actionable']
    assert 'latest_official_price_raw_evidence_missing' in gate['blockers']
