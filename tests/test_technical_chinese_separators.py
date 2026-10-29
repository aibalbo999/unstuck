"""Chinese separators preserve exact key:value ownership and every basis gate."""
import pytest
from evidence_technical_claims import technical_indicator_path


@pytest.mark.parametrize('suffix',['、SMA10:57.80999985元','（source ref=short_term_market_context.technical_indicators）'])
def test_dated_exact_sma_assignment_accepts_chinese_separator(suffix):
 claim={'label':'sma5','reported_value':57.45999985,'unit':'元','_technical_as_of':'2026-10-29',
        'technical_context_text':'2026-10-29 SMA5:57.45999985元'+suffix}
 assert technical_indicator_path(claim)==('data.technical_indicators.sma_5',)


@pytest.mark.parametrize('suffix',['、其他資料另列','（source ref=short_term_market_context.technical_indicators.atr_14）'])
def test_dated_exact_atr_assignment_accepts_chinese_separator(suffix):
 claim={'label':'ATR14','reported_value':1.15485731,'unit':'元','_technical_as_of':'2026-10-29',
        'technical_context_text':'2026-10-29 ATR14:1.15485731元'+suffix}
 assert technical_indicator_path(claim)==('data.technical_indicators.atr_14',)


@pytest.mark.parametrize('patch',[
 {'reported_value':999.0},{'unit':'%'},{'_technical_as_of':'2026-10-28'},
 {'technical_context_text':'2026-10-29 預估 SMA5:57.45999985元、SMA10:57.80999985元'},
 {'technical_context_text':'2026-10-29 volume SMA5:57.45999985元、SMA10:57.80999985元'},
 {'technical_context_text':'2026-10-29 SMA5:57.45999985元、SMA5:57.45999985元'},
])
def test_chinese_separator_cannot_override_wrong_value_unit_date_or_basis(patch):
 claim={'label':'sma5','reported_value':57.45999985,'unit':'元','_technical_as_of':'2026-10-29',
        'technical_context_text':'2026-10-29 SMA5:57.45999985元、SMA10:57.80999985元'}
 claim.update(patch);assert technical_indicator_path(claim)==()


def test_separators_do_not_admit_generated_support_level():
 claim={'label':'支撐位','reported_value':56.9,'unit':'元','_technical_as_of':'2026-10-29',
        'technical_context_text':'2026-10-29 模型支撐位:56.90元（模型計畫）'}
 assert technical_indicator_path(claim)in(None,())


def test_public_evidence_gate_still_rejects_wrong_scalar_with_chinese_separator():
 from evidence_exit_gate import evaluate_report_evidence
 snapshot={'data':{'current_price':999,'risk_price':999,'technical_indicators':{
  'availability':'available','as_of':'2026-10-29','source':'yfinance 5y history',
  'sma_5':57.45999985,'sma_50':999,'sma_10':57.80999985}}}
 result=evaluate_report_evidence('2026-10-29 SMA5:999元、SMA10:57.80999985元',snapshot,min_sample=1)
 claim=next(c for c in result['sampled_claims']if c['reported_value']==999)
 assert claim['status']=='mismatch' and claim['matched_path']=='data.technical_indicators.sma_5'
 assert claim['candidate_count']==1


@pytest.mark.parametrize('patch',[{'as_of':'2026-10-28'},{'source':'unknown'},{'sma_5':None}])
def test_public_gate_never_verifies_missing_or_wrong_date_source_with_separator(patch):
 from evidence_exit_gate import evaluate_report_evidence
 technical={'availability':'available','as_of':'2026-10-29','source':'yfinance 5y history','sma_5':57.45999985};technical.update(patch)
 result=evaluate_report_evidence('2026-10-29 SMA5:57.45999985元（source ref=short_term_market_context.technical_indicators）',{'data':{'technical_indicators':technical}},min_sample=1)
 assert result['verified_count']==0
