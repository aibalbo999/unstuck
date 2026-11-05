"""Explicit parent/NCI and ordinary EPS reconciliation, never generic PE fill."""
from copy import deepcopy
from datetime import date
from decimal import Decimal,ROUND_HALF_UP
import json
import pytest
from test_peer_reference_income import income_body,index_body,reference_body
from data_fetch.market_sources import peer_reference_income as p,peer_reference_transport as t

TICKER='2723.TW';SHARES=180000000;DAY=date(2026,11,4)
def body(year=2026,quarter=2,parent=574918,nci=9727,eps='3.19'):
    from bs4 import BeautifulSoup
    raw=income_body(year,quarter,parent).decode().replace('6230 尼得科超眾 (上市電腦及週邊設備業)','2723 美食-KY (上市觀光事業)')
    soup=BeautifulSoup(raw,'html.parser');a,b=soup.find_all('table');labels=a.select('tbody tr');values=b.select('tbody tr')
    for label,value in zip(labels,values):
        if label.get_text(' ',strip=True)=='本期淨利（淨損）':value.td.string=f'{parent+nci:,}'
    for title,value in [('非控制權益（淨利∕損）',f'{nci:,}'),('基本每股盈餘',eps)]:
        a.tbody.append(BeautifulSoup('<tr><td>'+title+'</td></tr>','html.parser').tr)
        b.tbody.append(BeautifulSoup('<tr><td>'+value+'</td></tr>','html.parser').tr)
    return str(soup).encode()
def parse(raw=None,**kwargs):return p.parse_cumulative_income(body()if raw is None else raw,2026,2,issuer_ticker=TICKER,**kwargs)

def test_parent_allocation_admission_is_distinct_from_total_and_ttm_uses_money():
    assert parse()==574918000
    values={(2026,2):parse(),(2025,2):p.parse_cumulative_income(body(2025,2,329000,7993,'1.83'),2025,2,issuer_ticker=TICKER),(2025,4):p.parse_cumulative_income(body(2025,4,-443839,9859,'-2.47'),2025,4,issuer_ticker=TICKER)}
    d=p.derive_nonpositive_income(2026,2,values)
    assert d['net_income_twd']==-197921000 and d['basis']=='reported_cumulative_parent_income'
    assert d['period_start']=='2025-07-01'and d['period_end']=='2026-06-30'
    assert d['net_income_twd']!=-186328000 # Group total includes NCI.


def test_request_is_exact_new_issuer_subject_and_common_keys_are_reused():
    request=t.spec('income',year=2026,quarter=2,peer_ticker=TICKER)
    assert request['data']['companyId']=='2723 美食-KY'
    assert request['params']['consolidated_reference_issuer']==TICKER and t.canonical_spec(request)==request
    for kind,kwargs in [('home',{}),('methodology',{}),('reference',{'day':DAY})]:
        assert t.raw_key(t.spec(kind,peer_ticker=TICKER,**kwargs))==t.raw_key(t.spec(kind,**kwargs))

@pytest.mark.parametrize('damage',['total','nci','missing_nci','duplicate_nci','missing_eps','duplicate_eps','wrong_eps','exponent','nan','issuer','unit','scope','period','alignment'])
def test_conflicting_or_missing_allocation_EPS_global_evidence_rejects(damage):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(body().decode(),'html.parser');labels=soup.find_all('table')[0].select('tbody tr');values=soup.find_all('table')[1].select('tbody tr')
    slots={r.get_text(' ',strip=True):i for i,r in enumerate(labels)}
    if damage in ['total','nci']:values[slots['本期淨利（淨損）'if damage=='total'else'非控制權益（淨利∕損）']].td.string='0'
    if damage in ['missing_nci','duplicate_nci','missing_eps','duplicate_eps']:
        title='非控制權益（淨利∕損）'if 'nci'in damage else'基本每股盈餘';n=slots[title]
        if damage.startswith('missing'):labels[n].decompose();values[n].decompose()
        else:
            soup.find_all('table')[0].tbody.append(deepcopy(labels[n]));soup.find_all('table')[1].tbody.append(deepcopy(values[n]))
    if damage in ['wrong_eps','exponent','nan']:values[slots['基本每股盈餘']].td.string={'wrong_eps':'-3.19','exponent':'3.19e0','nan':'NaN'}[damage]
    if damage=='alignment':values[-1].decompose()
    raw=str(soup).encode()
    if damage=='issuer':raw=raw.replace(b'2723',b'6558')
    if damage=='unit':raw=raw.replace('新台幣'.encode(),'美元'.encode())
    if damage=='scope':raw=raw.replace('合併'.encode(),'個別'.encode())
    if damage=='period':raw=raw.replace(b'2026Q2',b'2025Q2')
    with pytest.raises(ValueError):parse(raw)


def test_positive_reference_money_still_cannot_explain_missing_PE():
    assert parse(body(parent=574918,nci=0))==574918000
    with pytest.raises(ValueError):p.derive_nonpositive_income(2026,2,{(2026,2):574918000,(2025,2):329000000,(2025,4):443839000})

@pytest.mark.parametrize('ticker,header',[('6230.TW','6230 尼得科超眾 (上市電腦及週邊設備業)'),('6558.TW','6558 興能高 (上市其他電子業)')])
def test_existing_consolidated_issuers_keep_strict_parent_equals_total(ticker,header):
    raw=body().decode().replace('2723 美食-KY (上市觀光事業)',header).encode()
    with pytest.raises(ValueError,match='separate qualification'):p.parse_cumulative_income(raw,2026,2,issuer_ticker=ticker)


def test_profile_ordinary_share_reconciliation_basis_is_immutable():
    from data_fetch.market_sources.peer_reference_issuers import consolidated_issuer
    from dataclasses import FrozenInstanceError
    profile=consolidated_issuer(TICKER)
    assert profile.ordinary_shares==180000000 and profile.registered_country=='KY 開曼群島'
    with pytest.raises(FrozenInstanceError):profile.ordinary_shares=180000001


def test_extreme_untrusted_amount_is_a_rejected_fact_not_an_arithmetic_crash():
    with pytest.raises(ValueError):parse(body(parent=10**40,nci=0,eps='1.00'))
