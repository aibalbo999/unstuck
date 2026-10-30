from copy import deepcopy
import pytest
from test_native_moat_income_scope import selected,HEADINGS,paragraph,TITLE
from evidence_exit_gate import evaluate_report_evidence

def rows(text,data):
 return [r for r in evaluate_report_evidence(text,{'data':data})['sampled_claims'] if r.get('financial_metric')=='自由現金流']

def test_complete_native_moat_fcf_reuses_all_originals_without_mutating_input():
 data=selected();before=deepcopy(data);r=rows(HEADINGS+paragraph(data),data)
 assert len(r)==1 and r[0]['status']=='verified',r
 assert r[0]['independent_primary_source_verified'] is True
 assert r[0]['historical_pit_verified'] is False
 assert r[0]['financial_period']=='2025-07-01/2026-06-30'
 assert data==before

@pytest.mark.parametrize('old,new',[
 ('大東電','台積電'),('2025-07-01','2024-07-01'),('2026-06-30','2025-06-30'),
 ('官方個別','官方合併'),('億元新臺幣','億元美元'),('同期間','前一年'),
 ('data.cash_flow.official_reference','data.unbound_reference'),
 ('data.cash_flow.official_income_facts','data.unbound_income'),
 ('## 護城河逐項證據','## 2024年度護城河逐項證據'),
 ('#### 6. 競爭優勢持久性總結','#### 6. 同業比較'),
 ('* **現金流觀察：**','* **未來現金流觀察：**')])
def test_changed_owner_period_currency_or_complete_sentence_remains_unverified(old,new):
 data=selected();text=HEADINGS+paragraph(data);assert old in text
 r=rows(text.replace(old,new),data);assert r and all(x['status']!='verified'for x in r)

@pytest.mark.parametrize('metric',['淨利為','營業現金流為','合計','自由現金流為'])
def test_each_consumed_amount_must_match(metric):
 import re
 data=selected();text=HEADINGS+paragraph(data)
 text=re.sub('('+re.escape(metric)+r' )[+-]?[0-9.]+',r'\g<1>99.9',text)
 r=rows(text,data);assert r and all(x['status']!='verified'for x in r)

def test_damaged_official_reference_cannot_supply_cashflow():
 data=selected();text=HEADINGS+paragraph(data)
 data['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
 r=rows(text,data);assert r and all(x['status']!='verified'for x in r)
