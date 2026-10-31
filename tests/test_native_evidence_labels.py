"""Native labels grant no source, owner, period, currency or amount."""
import pytest
from test_official_income_claims import selected, income_claims
from evidence_exit_gate import evaluate_report_evidence

OWNER='大東電業廠股份有限公司官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）'
INCOME=OWNER+'淨利為 0.032 億元。'
FCF=OWNER+'自由現金流為 0.0885 億元。'
TITLE='## 已觀測財務與歷史反證\n'
CONFIDENCE='## 估值偏離度客觀描述\n### 信心依據\n'

def rows(text, data=None):
    return [x for x in evaluate_report_evidence(text, {'data':selected() if data is None else data})['sampled_claims'] if x.get('financial_metric') in {'淨利','自由現金流'}]

@pytest.mark.parametrize('title,text',[
 (TITLE,'- **官方核實數據**：'+INCOME),
 (CONFIDENCE,'- **具體佐證**: '+INCOME),
 (TITLE,'- **官方核實數據**：'+INCOME+FCF),
])
def test_exact_native_evidence_labels_bind_originals(title,text):
    values=rows(title+text)
    assert values and all(x['status']=='verified' for x in values),values
    assert all(x['independent_primary_source_verified'] is True for x in values)
    assert all(x.get('financial_narrative_resolution',{}).get('original_claim_unchanged') is True for x in values)

@pytest.mark.parametrize('old,new',[
 ('0.032','0.32'),('0.032','-0.032'),
])
def test_amount_or_sign_mismatch_cannot_be_hidden_by_label(old,new):
    values=rows(CONFIDENCE+'- **具體佐證**: '+INCOME.replace(old,new))
    assert values and values[0]['status']=='mismatch',values

@pytest.mark.parametrize('old,new',[
 ('大東電業廠股份有限公司','台積電'),('TWD','USD'),
 ('TWD ',''),('2025-07-01','2024-07-01'),
 ('官方個別','官方合併'),('官方個別','官方集團'),
 ('具體佐證','台積電佐證'),('具體佐證','2024年度佐證'),
 ('具體佐證','預測佐證'),('信心依據','台積電信心依據'),
 ('估值偏離度客觀描述','2024年度估值偏離度客觀描述'),
 ('淨利為','預估淨利為'),
])
def test_scope_or_unknown_label_does_not_bind(old,new):
    values=rows((CONFIDENCE+'- **具體佐證**: '+INCOME).replace(old,new))
    assert values and all(x['status']=='unverifiable' for x in values),values

@pytest.mark.parametrize('extra',['# 台積電\n','# 美元\n','# 2024年度\n','# 未知分析\n'])
def test_inherited_unknown_scope_remains_unknown(extra):
    values=rows(extra+CONFIDENCE+'- **具體佐證**: '+INCOME)
    assert values and all(x['status']=='unverifiable' for x in values)

@pytest.mark.parametrize('tail',[
 '台積電預估營收為 1 億元。','此為合併口徑。','幣別為美元。',
 '此為未來預測。','此數據已證明擴產成效。','未知文字。',
])
def test_no_prose_or_third_party_can_be_consumed(tail):
    values=rows(TITLE+'- **官方核實數據**：'+INCOME+FCF+tail)
    assert values and all(x['status']=='unverifiable' for x in values if x.get('label')=='淨利'),values

@pytest.mark.parametrize('bad',[
 FCF.replace('大東電業廠股份有限公司','台積電'),
 FCF.replace('TWD','USD'),
 FCF.replace('TWD ',''),
 FCF.replace('2025-07-01','2024-07-01'),
 FCF.replace(OWNER,''),
])
def test_second_clause_requires_its_own_exact_owner_currency_period(bad):
    values=rows(TITLE+'- **官方核實數據**：'+INCOME+bad)
    assert values and values[0]['status']=='unverifiable',values

def test_tampered_primary_original_cannot_be_replaced_by_numeric_match():
    data=selected()
    data['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
    values=rows(CONFIDENCE+'- **具體佐證**: '+INCOME,data)
    assert values and all(x['status']=='unverifiable' for x in values)

def test_two_statement_check_retains_original_full_line_and_claim_identity():
    from evidence_exit_gate_claims import extract_numeric_claims
    text=TITLE+'- **官方核實數據**：'+INCOME+FCF
    originals=[x for x in extract_numeric_claims(text) if x.get('financial_metric') in {'淨利','自由現金流'}]
    verified=rows(text)
    assert len(originals)==len(verified)==2
    for original,result in zip(originals,verified):
        for key in ('id','line_number','raw_text','label','reported_value','unit','financial_actual'):
            assert result.get(key)==original.get(key),(key,original,result)
