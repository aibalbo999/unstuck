"""An actual native moat section is structural; its individual facts still bind."""
from copy import deepcopy
from decimal import Decimal
import pytest
from test_official_income_claims import selected,income_claims

TITLE='# 1623.TW（大東電）投資銀行等級估值解讀報告'
HEADINGS=TITLE+'\n\n## 護城河逐項證據\n\n### 大東電 (1623.TW) 競爭護城河評估報告\n\n#### 6. 競爭優勢持久性總結\n'


def paragraph(data):
 from official_income_prompt import official_income_prompt_facts
 facts=official_income_prompt_facts(data);cf=data['official_financial_projection']['facts']['cashflows']['ttm']
 def money(value):return format(Decimal(value)/Decimal(100000000),'f')
 return ('* **現金流觀察：** 大東電官方個別 TTM（'+facts['period_start']+' 至 '+facts['period_end']+'）淨利為 '+money(facts['net_income_ttm_raw'])+' 億元新臺幣；同期間營業現金流為 '+money(cf['operating_cash_flow'])+' 億元新臺幣，CapEx（PPE 及無形資產取得支出）合計 '+money(-(cf['ppe_purchase']+cf['intangible_purchase']))+' 億元新臺幣，自由現金流為 '+money(cf['free_cash_flow'])+' 億元新臺幣（來源：`data.cash_flow.official_reference`、`data.cash_flow.official_income_facts` 及其 `source_documents`）。')


def test_actual_native_wrapper_qualifies_only_the_replayed_individual_income():
 data=selected();before=deepcopy(data);rows=income_claims(HEADINGS+paragraph(data),data)
 assert len(rows)==1 and rows[0]['status']=='verified',rows
 assert rows[0]['independent_primary_source_verified'] is True
 assert rows[0]['financial_report_scope']=='individual' and rows[0]['financial_currency']=='TWD'
 assert rows[0]['financial_period']=='2025-07-01/2026-06-30'
 assert rows[0]['historical_pit_verified'] is False and rows[0]['native_acquisition'] is False
 assert data==before and data['net_income_ttm_raw']==860640000


@pytest.mark.parametrize('mutate',[
 lambda t:t.replace('### 大東電 (1623.TW)','### 台積電 (2330.TW)'),
 lambda t:t.replace('### 大東電 (1623.TW)','### 同業大東電 (1623.TW)'),
 lambda t:t.replace('#### 6. 競爭優勢持久性總結','#### 6. 競爭者財務比較'),
 lambda t:t.replace('## 護城河逐項證據','## 2024 年度護城河逐項證據'),
 lambda t:t.replace('## 護城河逐項證據','## 合併口徑護城河逐項證據'),
 lambda t:t.replace(TITLE, '# 台積電'),
 lambda t:t.replace('2025-07-01','2024-07-01'),
 lambda t:t.replace('2026-06-30','2025-06-30'),
 lambda t:t.replace('官方個別','官方合併'),
 lambda t:t.replace('億元新臺幣','億美元'),
 lambda t:t+'（資料為合併口徑）',
 lambda t:t+'；此為台積電資料。',
 lambda t:t.replace('淨利為','預估淨利為'),
])
def test_unknown_ancestor_owner_period_currency_or_suffix_cannot_borrow_source(mutate):
 data=selected();text=HEADINGS+paragraph(data);changed=mutate(text)
 assert changed!=text
 rows=income_claims(changed,data)
 assert rows and all(r['status']=='unverifiable' for r in rows),rows


@pytest.mark.parametrize('literal',['-0.032','8.6064','0.32'])
def test_wrong_current_income_stays_mismatch_not_vendor_match(literal):
 data=selected();text=(HEADINGS+paragraph(data)).replace('淨利為 0.032','淨利為 '+literal)
 rows=income_claims(text,data)
 assert len(rows)==1 and rows[0]['status']=='mismatch',rows


def test_other_consumed_cashflow_amount_must_match_source_too():
 data=selected();text=HEADINGS+paragraph(data)
 import re
 changed=re.sub(r'(營業現金流為 )[+-]?[\d.]+',r'\g<1>99.9',text)
 assert changed!=text
 rows=income_claims(changed,data);assert rows and all(r['status']=='unverifiable' for r in rows),rows


def test_reference_damage_or_caller_alias_does_not_supply_identity():
 data=selected();text=HEADINGS+paragraph(data)
 data['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
 assert all(r['status']=='unverifiable' for r in income_claims(text,data))
 data=selected();data['company_identity']={'allowed_aliases':['台積電']}
 changed=text.replace('### 大東電 (1623.TW)','### 台積電 (1623.TW)')
 assert all(r['status']=='unverifiable' for r in income_claims(changed,data))


@pytest.mark.parametrize('metric', ['CapEx（PPE 及無形資產取得支出）合計 ', '自由現金流為 '])
def test_each_other_consumed_amount_must_match_source(metric):
 data=selected();text=HEADINGS+paragraph(data)
 import re
 changed=re.sub('('+re.escape(metric)+r')[+-]?[\d.]+',r'\g<1>99.9',text)
 assert changed!=text
 rows=income_claims(changed,data)
 assert rows and all(row['status']=='unverifiable' for row in rows),rows


@pytest.mark.parametrize('mutate', [
 lambda t:t.replace('## 護城河逐項證據\n',''),
 lambda t:t.replace('### 大東電 (1623.TW) 競爭護城河評估報告\n',''),
 lambda t:t.replace('官方個別 TTM（2025-07-01 至 2026-06-30）','官方個別 TTM'),
 lambda t:t.replace('億元新臺幣；同期間','百萬元新臺幣；同期間'),
 lambda t:t.replace('data.cash_flow.official_reference','data.other_reference'),
 lambda t:t.replace('* **現金流觀察：**','* **未來現金流觀察：**'),
 lambda t:t.replace('#### 6. 競爭優勢持久性總結','#### 6. 競爭優勢持久性總結（美元）'),
])
def test_missing_native_structure_or_changed_reference_does_not_bind(mutate):
 data=selected();text=HEADINGS+paragraph(data);changed=mutate(text);assert changed!=text
 rows=income_claims(changed,data)
 assert rows and all(row['status']=='unverifiable' for row in rows),rows
