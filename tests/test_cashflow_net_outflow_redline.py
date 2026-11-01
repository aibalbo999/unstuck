import pytest
from cashflow_causal_claims import cashflow_driver_inference_issues

@pytest.mark.parametrize('text',[
 '自由現金流連續兩年（2025年度與TTM）呈現淨流出，主要受營運資金（存貨與應收帳款）增加及資本支出擴大影響。',
 '自由現金流處於淨流出，顯示擴產造成壓力。',
 'FCF淨流出，主要受營運資金增加影響。',
 '自由現金流呈淨流出，主要受營運資金增加影響。上述推論仍需核實。',
])
def test_net_outflow_does_not_establish_a_specific_operating_driver(text):
 checks=cashflow_driver_inference_issues(text)
 assert checks and checks[0]['reason_code']=='cashflow_total_does_not_establish_operating_driver'

@pytest.mark.parametrize('text',[
 '自由現金流呈淨流出，可能主要受營運資金增加影響，仍需原件核實。',
 '自由現金流呈淨流出，不能證明營運資金增加。',
 '自由現金流呈淨流出，營運資金變動仍須核實。',
 '本次DCF工具因自由現金流非正值而顯示unavailable；這不代表DCF理論一般不可用。',
 '營運資產及負債淨變動為負值；原件中的存貨變動現金影響列於獨立事實清單。',
])
def test_observation_hypothesis_and_tool_status_remain_distinct(text):
 assert not cashflow_driver_inference_issues(text)

@pytest.mark.parametrize('text',[
 '自由現金流由正轉負，面臨營運資金壓力：官方數據顯示年度及TTM自由現金流均呈淨流出。',
 '自由現金流呈淨流出，顯示營運資金管理壓力增加。',
 '負向現金流之具體經營動機（如確切之備料訂單或擴產進度）缺乏官方原件直接證實，目前僅能視為待核實之假說。',
])
def test_generic_pressure_and_explicit_missing_causal_evidence_are_not_drivers(text):
 assert not cashflow_driver_inference_issues(text)

def test_missing_evidence_after_an_asserted_driver_does_not_erase_the_assertion():
 assert cashflow_driver_inference_issues('自由現金流淨流出證實擴產，缺乏官方原件直接證實的部分仍待補件。')
