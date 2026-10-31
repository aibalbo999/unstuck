import pytest
from test_official_income_claims import selected,income_claims
TITLE='## 獨立反證審查報告：大東電 (1623.TW)\n### 三、 已觀測財務與歷史反證\n'
CLAUSE='- **官方 TTM 數據核對**：大東電業廠股份有限公司官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）淨利為 0.032 億元。'
def test_native_label_keeps_exact_source_binding():
 row=income_claims(TITLE+CLAUSE,selected())[0]
 assert row['status']=='verified',row
@pytest.mark.parametrize('old,new',[('0.032','0.32'),('0.032','-0.032')])
def test_bad_amount_or_sign_remains_mismatch(old,new):
 row=income_claims(TITLE+CLAUSE.replace(old,new),selected())[0]
 assert row['status']=='mismatch',row
@pytest.mark.parametrize('old,new',[('TWD','USD'),('2025-07-01','2024-07-01'),('大東電業廠股份有限公司','台積電'),('官方個別','官方合併'),('官方 TTM 數據核對','台積電數據核對')])
def test_unbound_or_foreign_scope_stays_unknown(old,new):
 assert income_claims(TITLE+CLAUSE.replace(old,new),selected())[0]['status']=='unverifiable'


def test_full_native_moat_heading_keeps_scope():
 data=selected()
 from evidence_financial_amounts import _native_mode_a_structural_headings
 title=next(v for v in _native_mode_a_structural_headings(data) if v.startswith('# '))
 text=title+'\n## 競爭護城河深度評估報告\n### 五、 已觀測財務與歷史反證\n'+CLAUSE
 row=income_claims(text,data)[0]
 assert row['status']=='verified',row
 for foreign in ('# 台積電\n','# 2024年度\n','# 美元\n'):
  assert income_claims(text.replace(title+'\n',foreign,1),data)[0]['status']=='unverifiable'
