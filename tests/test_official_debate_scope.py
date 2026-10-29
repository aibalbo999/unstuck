import pytest
from test_official_income_claims import income_claims
from test_official_income_native_summary_heading import data_with_english
TEXT='大東電官方個別TTM（2025-07-01至2026-06-30）淨利為0.032億元新臺幣。'
@pytest.mark.parametrize('parent',['🐻 空頭：','🐂 多頭：'])
def test_exact_debate_stance_does_not_change_explicit_official_fact(parent):
 rows=income_claims(parent+'\n'+TEXT,data_with_english())
 assert rows and all(r['status']=='verified'for r in rows),rows
@pytest.mark.parametrize('scope',['# 台積電','# 2024年度','# 合併財報','# 美元','# 未來預測'])
def test_debate_stance_cannot_hide_conflicting_ancestor(scope):
 rows=income_claims(scope+'\n🐻 空頭：\n'+TEXT,data_with_english())
 assert rows and all(r['status']=='unverifiable'for r in rows),rows
@pytest.mark.parametrize('parent',['🐻 台積電空頭：','🐻 空頭2024年度：','🐻 空頭合併：','🐻 空頭美元：'])
def test_only_exact_neutral_stance_is_admitted(parent):
 rows=income_claims(parent+'\n'+TEXT,data_with_english())
 assert rows and all(r['status']=='unverifiable'for r in rows),rows
