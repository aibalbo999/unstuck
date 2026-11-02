import pytest
from test_official_income_claims import selected,TEXT,income_claims
from test_official_individual_annual_facts import annual,checked
from official_debt_prompt import official_debt_reference_prompt
from test_official_debt_component_claims import claims


@pytest.mark.parametrize("heading",["## 七、官方財務事實清單","## 7. 官方財務事實清單"])
def test_neutral_ordinal_preserves_exact_annual_ttm_and_debt_scope(heading):
    data=selected()
    texts=[annual(data)["periods"]["2025"]["statements"]["淨利"],TEXT]
    for text in texts:
        rows=checked(heading+"\n\n"+text,data)
        assert rows and all(r["status"]=="verified" for r in rows),rows
    debt=next(s for s in official_debt_reference_prompt(data).splitlines() if "一年內到期之長期借款為" in s)
    rows=claims(heading+"\n\n"+debt,data)
    assert rows and all(r["status"]=="verified" for r in rows),rows


@pytest.mark.parametrize("ancestor",["# 台積電","# 合併財報","# 2024年度財務分析","# USD預估"])
def test_numbered_neutral_heading_never_hides_conflicting_ancestor(ancestor):
    rows=income_claims(ancestor+"\n\n## 七、官方財務事實清單\n\n"+TEXT,selected())
    assert rows and all(r["status"]=="unverifiable" for r in rows),rows
