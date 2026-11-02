from copy import deepcopy
import pytest
from evidence_official_financial_claims import official_debt_component_claims
from test_official_financial_claim_binding import projected


def narrative(amount='0.005', *, date='2026-06-30', owner='大東電', scope='個別', suffix=''):
    return (f'- **債務水準與結構分析**：截至 {date}，{owner}{scope}借款與租賃負債總額為 0.028 億元。'
            f'結構包含：短期借款 0.010 億元、一年內到期長期借款 {amount} 億元、長期借款 0.010 億元，'
            f'以及租賃負債約 0.003 億元。短期償債壓力（一年內需償還金額約 0.015 億元）相對較高。{suffix}')


@pytest.mark.parametrize('amount,status',[('0.005','verified'),('0.0005','mismatch'),('-0.005','mismatch')])
def test_dated_individual_debt_list_preserves_local_component_scope(amount,status):
    data=projected();before=deepcopy(data)
    rows=official_debt_component_claims(narrative(amount),{'data':data})
    assert len(rows)==1 and rows[0]['status']==status, rows
    assert rows[0]['financial_period']=='2026-06-30'
    assert rows[0]['matched_path'].endswith('.current_portion_longterm_borrowings')
    assert rows[0]['independent_primary_source_verified'] is True
    assert rows[0]['historical_pit_verified'] is False
    assert data==before


@pytest.mark.parametrize('change',[
    {'date':'2025-06-30'}, {'owner':'華通'}, {'scope':'合併'},
    {'suffix':'此為華通資料。'}, {'suffix':'以美元計價。'},
    {'suffix':'假設未來一年內到期長期借款仍為 0.005 億元。'},
])
def test_debt_list_cannot_borrow_date_issuer_scope_currency_or_future(change):
    rows=official_debt_component_claims(narrative(**change),{'data':projected()})
    assert rows and all(r['status']=='unverifiable'for r in rows)


def test_unrecognized_qualifier_cannot_hide_after_component_list():
    rows=official_debt_component_claims(narrative(suffix='另以尚未揭露之估計數調整。'),{'data':projected()})
    assert rows and all(r['status']=='unverifiable'for r in rows)


def test_unverified_raw_original_never_qualifies_narrative():
    data=projected();data['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
    assert all(r['status']=='unverifiable'for r in official_debt_component_claims(narrative(),{'data':data}))

def explicit_component(data,amount='0.005'):
    fact=data['official_financial_projection']['facts']
    return f"{fact['issuer_name']}官方個別財報 TWD 截至 2026-06-30 一年內到期之長期借款為 {amount} 億元。"

@pytest.mark.parametrize('heading',['## 四、財務槓桿與償債能力','## 官方財務事實清單'])
def test_complete_twd_component_statement_uses_original_not_a_header(heading):
    data=projected();rows=official_debt_component_claims(heading+'\n\n'+explicit_component(data),{'data':data})
    assert len(rows)==1 and rows[0]['status']=='verified',rows

@pytest.mark.parametrize('ancestor',['# 台積電','# 2024年度','# USD','# 合併財報','# 預估財報'])
def test_complete_component_cannot_hide_a_conflicting_ancestor(ancestor):
    data=projected();text=ancestor+'\n\n## 四、財務槓桿與償債能力\n\n'+explicit_component(data)
    rows=official_debt_component_claims(text,{'data':data})
    assert rows and all(x['status']=='unverifiable'for x in rows),rows

@pytest.mark.parametrize('old,new',[('TWD','USD'),('2026-06-30','2025-06-30'),('個別','合併')])
def test_complete_component_local_scope_cannot_be_replaced(old,new):
    data=projected();rows=official_debt_component_claims(explicit_component(data).replace(old,new),{'data':data})
    assert rows and all(x['status']=='unverifiable'for x in rows),rows

@pytest.mark.parametrize('value',['0.005001','0.0005','-0.005'])
def test_complete_component_false_precision_and_unit_factor_remain_mismatch(value):
    data=projected();rows=official_debt_component_claims(explicit_component(data,value),{'data':data})
    assert len(rows)==1 and rows[0]['status']=='mismatch',rows


def test_full_native_bilingual_title_needs_same_issuer_verified_english_name(monkeypatch):
    import official_income_prompt
    data=projected()
    title='# 1623.TW 大東電 / Ta Tun Electric Wire & Cable Co., Ltd. - 華爾街深度研究報告'
    text=title+'\n\n## 官方財務事實清單\n\n'+explicit_component(data)
    monkeypatch.setattr(official_income_prompt,'official_income_prompt_facts',lambda d:{'issuer_name':'大東電業廠股份有限公司','issuer_english_name':'TA TUN ELECTRIC WIRE & CABLE CO., LTD.'})
    rows=official_debt_component_claims(text,{'data':data})
    assert rows[0]['status']=='verified'
    monkeypatch.setattr(official_income_prompt,'official_income_prompt_facts',lambda d:{'issuer_name':'其他公司','issuer_english_name':'TA TUN ELECTRIC WIRE & CABLE CO., LTD.'})
    assert official_debt_component_claims(text,{'data':data})[0]['status']=='unverifiable'
