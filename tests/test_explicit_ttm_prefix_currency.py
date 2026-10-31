import pytest
from test_official_income_claims import selected,income_claims
TITLE='## 獨立反證審查報告：大東電 (1623.TW)\n### 三、 已觀測財務與歷史反證\n'
CLAUSE='- **官方淨利核實**：大東電業廠股份有限公司官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）淨利為 0.032 億元。'
def test_complete_prefix_currency_clause_replays_same_official_income():
 row=income_claims(TITLE+CLAUSE,selected())[0]
 assert row['status']=='verified',row
 assert row['independent_primary_source_verified'] is True
 assert row['historical_pit_verified'] is False
@pytest.mark.parametrize('old,new',[('0.032','0.32'),('0.032','-0.032')])
def test_wrong_value_or_sign_still_mismatches(old,new):
 row=income_claims(TITLE+CLAUSE.replace(old,new),selected())[0]
 assert row['status']=='mismatch',row
@pytest.mark.parametrize('old,new', [('TWD ',''),('TWD','USD'),('2025-07-01','2025-01-01'),('大東電業廠股份有限公司','台積電'),('官方個別','官方合併'),('官方淨利核實','台積電淨利核實')])
def test_scope_or_currency_damage_stays_unknown(old,new):
 row=income_claims(TITLE+CLAUSE.replace(old,new),selected())[0]
 assert row['status']=='unverifiable',row
@pytest.mark.parametrize('heading',['# 同業獲利\n','# 2024年度\n','# 美元預測\n'])
def test_incompatible_ancestor_cannot_be_hidden(heading):
 row=income_claims(heading+TITLE+CLAUSE,selected())[0]
 assert row['status']=='unverifiable',row
