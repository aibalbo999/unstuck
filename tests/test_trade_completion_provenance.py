import json
from structured_output_runtime import process_agent_response
from test_trade_source_completion import setup_payload
from report_analysis_completeness import assess_report_analysis_completeness
from test_report_analysis_completeness import context as report_context


def test_max_tokens_cannot_be_admitted_even_if_json_repair_fills_all_fields():
    ctx={'structured_outputs':{}}
    process_agent_response(24,json.dumps(setup_payload()),ctx,completion_diagnostics={'finish_reasons':['MAX_TOKENS']})
    assert not ctx['structured_outputs'].get(24)
    assert ctx['_trade_incomplete_fields']==['provider_output_incomplete']


def test_persist_completion_on_accepted_structured_output():
    ctx={'structured_outputs':{}}
    raw=json.dumps(setup_payload())
    process_agent_response(24,raw,ctx,model_id='fixture',completion_diagnostics={'finish_reasons':['STOP']})
    completion=ctx['structured_outputs'][24]['source_assessment']['output_completion']
    assert completion['status']=='complete'
    assert completion['finish_reasons']==['STOP']
    assert len(completion['raw_sha256'])==64
    assert completion['generation_policy_version']
    assert 'raw_text' not in completion


def test_report_incomplete_receipt_cannot_be_hidden_by_green_gates():
    ctx=report_context()
    ctx['structured_outputs'][24]['source_assessment']['output_completion']={'status':'incomplete'}
    result=assess_report_analysis_completeness(ctx)
    assert result['status']=='degraded'
    assert 'output_incomplete' in result['reason_codes']
