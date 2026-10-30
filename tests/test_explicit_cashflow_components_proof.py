from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import pytest
from test_tewc_quarterly_reference import reference

def projected():
    from official_financial_projection import project_official_financials
    return project_official_financials({
        "ticker":"1623.TW", "company_name":"大東電", "financial_currency":"TWD"}, reference())
from evidence_official_financial_claims import official_fcf_claim


def make():
    data=projected(); f=data['official_financial_projection']['facts']; c=f['cashflows']['ttm']
    amount=lambda key:format(Decimal(str(c[key]))/Decimal('100000000'),'.5f')
    direction='淨流出' if c['free_cash_flow']<0 else '淨流入'
    text=(f'- **官方個別 TTM 現金流為{direction}**：依據官方個別財務報表（期間為 {f["period_start"]} 至 {f["period_end"]}，來源：`cash_flow.official_reference`），'
          f'大東電營業現金流為 {amount("operating_cash_flow")} 億元新臺幣，購置不動產廠房設備與無形資產支出分別為 {amount("ppe_purchase")} 億元及 {amount("intangible_purchase")} 億元，'
          f'計算之個別 TTM 自由現金流為 {amount("free_cash_flow")} 億元新臺幣（{(Decimal(str(c["free_cash_flow"]))/Decimal("1000000000")).quantize(Decimal("0.0001"),rounding=ROUND_HALF_UP)} billion_twd）。')
    claim={'financial_metric':'自由現金流','reported_value':float(amount('free_cash_flow')),'unit':'億元',
           '_financial_heading_ancestors':[], 'financial_display_precision':5,'raw_text':text,'financial_parent_context':'- 現金流表現與流動性限制：\n'}
    return data,claim


def test_exact_official_components_and_explicit_period_are_bound():
    data,claim=make(); before=deepcopy(data)
    result=official_fcf_claim(claim,data,scale=100000000,tolerance_pct=1)
    assert result and result['status']=='verified'
    assert result['financial_period']=='2025-07-01/2026-06-30'
    assert result['independent_primary_source_verified'] is True
    assert result['historical_pit_verified'] is False
    assert data==before


@pytest.mark.parametrize('old,new',[
 ('2025-07-01','2024-07-01'),('2026-06-30','2025-06-30'),('大東電','華通'),
 ('官方個別財務報表','官方合併財務報表'),('新臺幣','美元'),
 ('cash_flow.official_reference','unbound_reference'),('營業現金流為','未來營業現金流為'),
 ('購置不動產廠房設備與無形資產支出','購置不動產廠房設備支出'),
 ('0.12000','0.11000'),('0.08850','0.88500'),('0.0089','0.0885'),
 ('。','。此為華通資料'),
])
def test_malformed_owner_period_components_or_suffix_cannot_borrow_proof(old,new):
    data,claim=make(); assert old in claim['raw_text'];claim['raw_text']=claim['raw_text'].replace(old,new)
    result=official_fcf_claim(claim,data,scale=100000000,tolerance_pct=1)
    assert result is None or result['status']!='verified'


@pytest.mark.parametrize('parent',['- 華通現金流：','- 2024年度：','- 集團口徑：'])
def test_parent_scope_cannot_be_erased(parent):
    data,claim=make();claim['financial_parent_context']=parent
    assert official_fcf_claim(claim,data,scale=100000000,tolerance_pct=1) is None


def test_changed_archived_reference_fails_closed():
    data,claim=make();data['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
    assert official_fcf_claim(claim,data,scale=100000000,tolerance_pct=1) is None


def test_complete_native_heading_chain_is_required():
    from evidence_financial_amounts import _native_mode_a_structural_headings
    data,claim=make();title=next(x for x in _native_mode_a_structural_headings(data) if x.startswith('# '))
    claim['financial_heading']='## 四、主要風險因子'
    claim['_financial_heading_ancestors']=[title,claim['financial_heading']]
    assert official_fcf_claim(claim,data,scale=100000000,tolerance_pct=1)['status']=='verified'
    for invalid in [[title,'## 華通',claim['financial_heading']], [title,'## 2024年度',claim['financial_heading']], None, []]:
        claim['_financial_heading_ancestors']=invalid
        assert official_fcf_claim(claim,data,scale=100000000,tolerance_pct=1) is None


def test_whole_extractor_and_checker_preserve_full_context_and_negative_controls():
    from evidence_exit_gate import evaluate_report_evidence
    from evidence_financial_amounts import _native_mode_a_structural_headings
    data,claim=make();title=next(x for x in _native_mode_a_structural_headings(data) if x.startswith('# '))
    for parent,scope,want in [('- 現金流表現與流動性限制：','## 四、主要風險因子',True),
                              ('- 華通現金流：','## 四、主要風險因子',False),
                              ('- 現金流表現與流動性限制：','## 2024年度',False)]:
        result=evaluate_report_evidence(title+'\n'+scope+'\n'+parent+'\n  '+claim['raw_text'],{'data':data})
        fcf=[c for c in result['sampled_claims'] if c.get('financial_metric')=='自由現金流']
        assert fcf
        assert all((c['status']=='verified')==want for c in fcf),fcf
