import pytest
from financial_unit_declarations import financial_unit_declaration_issues
DATA={'financial_currency':'TWD','quant_metrics':{'unit_contract':{'money':'billion_twd'}},'revenue_history':[3.9,4.22,5.48,6.61],'net_income_history':[.09,.41,.73,.82],'fcf_history':[-.3,-.43,.08,-.23]}
@pytest.mark.parametrize('text',[
'大東電2022至2025年營收分別為3.9億元、4.22億元、5.48億元、6.61億元（來源：history.rows；原始範圍未核實）',
'淨利分別為0.09億元、0.41億元、0.73億元與0.82億元（換算自history.rows）',
'依據history.rows，自由現金流分別為-0.30億元、-0.43億元、0.08億元（換算為0.8億元）與-0.23億元。'])
def test_rejects_tenfold_history_conversion_even_with_unknown_period(text):
 assert financial_unit_declaration_issues(text,DATA)
@pytest.mark.parametrize('text',[
'營收分別為39.0億元、42.2億元、54.8億元、66.1億元（來源history.rows）',
'營收分別為3.9 billion_twd、4.22 billion_twd、5.48 billion_twd、6.61 billion_twd（來源history.rows）',
'另家公司營收分別為3.9億元、4.22億元、5.48億元、6.61億元',
'不可寫營收分別為3.9億元、4.22億元、5.48億元、6.61億元（來源history.rows）'])
def test_no_false_rejection(text):
 assert not financial_unit_declaration_issues(text,DATA)
def test_no_unit_contract_no_promoted_evidence():
 assert not financial_unit_declaration_issues('營收分別為3.9億元、4.22億元、5.48億元、6.61億元（來源history.rows）',{})



def test_native_role_and_report_paths_block_same_unit_contradiction():
 from financial_output_validator import validate_analysis_output
 from evidence_exit_gate import evaluate_report_evidence
 text='營收分別為3.9億元、4.22億元、5.48億元、6.61億元（來源history.rows；年度範圍未核實）'
 assert any('單位' in x for x in validate_analysis_output(2,text,DATA))
 result=evaluate_report_evidence(text,{'pipeline':'v1','data':DATA})
 assert result['verdict']=='rejected'
 assert result['financial_unit_declaration_checks'][0]['period_verified']is False
