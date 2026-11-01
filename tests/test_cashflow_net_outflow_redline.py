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
