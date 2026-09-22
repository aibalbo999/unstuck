import copy
import json
from pathlib import Path
import pytest
from final_audit_mode_contracts import v3_short_setup_contract_issues
from trade_execution_contract import contains_trade_order, observation_reason_is_explicit, evaluate_trade_execution
from trade_price_inputs import parse_price_range
ROWS=json.loads((Path(__file__).parent/'fixtures/error_prevention_mode_c_20260922.json').read_text())

@pytest.mark.parametrize('row',[r for r in ROWS if not r['job_id'].startswith('7e9b72ae')],ids=lambda r:r['job_id'][:8])
def test_retained_no_position_template_and_specific_invalidation(row):
    assert v3_short_setup_contract_issues(row['short_setup'],recommendation=row['recommendation'])==[]

@pytest.mark.parametrize('text',[
 '等待可驗證做空觸發後再評估。確認後做空。',
 '等待可驗證做空觸發後立即放空。',
 '目前不建立空方部位；等待可驗證做空觸發後再評估。次日建立空單。',
])
def test_future_actual_short_order_is_still_blocked(text):
    assert contains_trade_order(text)

@pytest.mark.parametrize('field',['squeeze_risk','thesis_invalidation'])
def test_correct_observation_phrase_never_fills_missing_risk_fields(field):
    row=next(r for r in ROWS if r['job_id'].startswith('88cee1aa'))
    setup=copy.deepcopy(row['short_setup']);setup[field]='資料不足'
    assert any(field in issue for issue in v3_short_setup_contract_issues(setup,recommendation=row['recommendation']))

@pytest.mark.parametrize('text',['營業利益率資料不足','費用率'])
def test_bare_financial_topic_is_not_a_specific_invalidation(text):
    assert not observation_reason_is_explicit(text)


def test_revenue_threshold_is_not_an_entry_price():
    row=next(r for r in ROWS if r['job_id'].startswith('7e9b72ae'));setup=row['short_setup']
    assert parse_price_range(setup['entry_trigger']) is None
    result=evaluate_trade_execution(direction='Short',entry_zone=setup['entry_trigger'],
        target_price=setup['downside_target'],stop_loss=setup['cover_stop'])
    assert 'invalid_entry_zone' in {i['id'] for i in result['issues']}

@pytest.mark.parametrize('text',[
 '股價900元以下，且單月營收跌破17億TWD。',
 '股價880至900元，且單月營收跌破17億TWD。',
])
def test_real_price_survives_separate_revenue_trigger(text):
    assert parse_price_range(text)==((880,900) if '880' in text else (900,900))

@pytest.mark.parametrize('text',['營收17億至20億元','營業收入17萬到20萬元','營收17至20億元'])
def test_revenue_range_removes_both_amounts_and_preserves_real_price(text):
    assert parse_price_range(text) is None
    assert parse_price_range(text+'，股價26元。')==(26,26)
