"""Strict 2646 individual-income protocol, separate from consolidated parent income.

Pure parsing and mathematical explanation are not native acquisition proof.
The producer/consumer must additionally replay the current official master,
complete originals, independent owners and the exact observed valuation period.
"""
from datetime import date, datetime
import re
from bs4 import BeautifulSoup
from .peer_reference_income import (FIELDS, INDEX_FIELDS, quarter_end,
    required_periods, unique_json, parse_methodology, APPLICABILITY)
from .official_mopsfin_financial import _amount

TICKER = '2646.TW'
CODE = '2646'
SHORT = '星宇航空'
LEGAL = '星宇航空股份有限公司'
UBN = '51712072'
COMPANY = '2646 星宇航空 (上市航運業)'
PUBLISHED_COMPANY_LABEL = '2646 星宇航空'
SCHEMA = 'twse-individual-reference-income.v1'
STATEMENT_TYPE = '2'
INDUSTRY_CODE = '15'


def parse_reference(raw,observed_day):
    if type(observed_day)is not date or not isinstance(raw,bytes)or not 0<len(raw)<=1000000:
        raise ValueError('unverified reference roster')
    value=unique_json(raw)
    if (not isinstance(value,dict)or value.get('stat')!='OK'or value.get('date')!=observed_day.strftime('%Y%m%d')
            or value.get('fields')!=FIELDS or not isinstance(value.get('data'),list)
            or value.get('selectType')!='ALL'or type(value.get('total'))is not int
            or value['total']!=len(value['data'])
            or not 800<=len(value['data'])<=2000):raise ValueError('unverified complete reference roster')
    seen=set();selected=[]
    for row in value['data']:
        if (not isinstance(row,list)or len(row)!=8 or not isinstance(row[0],str)
                or not 1<=len(row[0])<=12 or row[0]in seen):raise ValueError('unverified reference row')
        seen.add(row[0])
        if row[0]==CODE:selected.append(row)
    if len(selected)!=1:raise ValueError('missing or duplicate reference issuer')
    row=selected[0]
    if row[1]!=SHORT or row[5]!='-'or not isinstance(row[7],str):
        raise ValueError('positive/ambiguous P/E or incorrect reference issuer')
    match=re.fullmatch(r'([0-9]{3})/([1-4])',row[7])
    if not match:raise ValueError('financial reference quarter unavailable')
    year,quarter=int(match[1])+1911,int(match[2])
    if quarter_end(year,quarter)>observed_day:raise ValueError('future financial reference')
    lag=(observed_day.year-year)*4+(observed_day.month-1)//3+1-quarter
    if not 0<=lag<=2:raise ValueError('stale financial reference')
    return {'year':year,'quarter':quarter,'raw_pe':row[5],'observed_at':observed_day.isoformat(),
            'reference_quarter':row[7],'official_short_name':row[1]}


def parse_calendar_index(raw,year,quarters,observed_day):
    if (not isinstance(raw,bytes)or not 0<len(raw)<=250000 or not raw.rstrip().lower().endswith(b'</html>')
            or type(observed_day)is not date or not isinstance(quarters,(list,tuple))
            or not quarters or len(set(quarters))!=len(quarters)):
        raise ValueError('unverified complete filing index')
    for q in quarters:quarter_end(year,q)
    soup=BeautifulSoup(raw.decode('big5',errors='strict'),'html.parser')
    text=' '.join(soup.get_text(' ',strip=True).split())
    if '公司名稱：'+SHORT not in text.replace(' ','')or '會計期間：曆年制'not in text.replace(' ',''):
        raise ValueError('calendar year or company not established by filing index')
    tables=[t for t in soup.find_all('table')if t.find('tr')and
        [c.get_text(' ',strip=True)for c in t.find('tr').find_all(['td','th'],recursive=False)]==INDEX_FIELDS]
    if len(tables)!=1:raise ValueError('filing table schema unverified')
    rows=tables[0].find_all('tr')[1:]
    if not 1<=len(rows)<=64:raise ValueError('filing index over limit or empty')
    result={};names={1:'一',2:'二',3:'三',4:'四'}
    for row in rows:
        cells=row.find_all(['td','th'],recursive=False);values=[c.get_text(' ',strip=True)for c in cells]
        if len(values)!=11 or values[0]!=CODE or values[2]!='財務報告書':raise ValueError('index issuer or shape mismatch')
        match=re.fullmatch(str(year-1911)+r'年第([一二三四])季',values[1].replace(' ',''))
        if not match:raise ValueError('index fiscal year or quarter mismatch')
        q=next(q for q,n in names.items()if n==match[1])
        if values[5]!='IFRSs個別財報':continue
        if q not in quarters:continue
        if q in result or values[10]!='無':raise ValueError('duplicate or corrected filing is not admitted')
        links=cells[7].find_all('a');filename=f'{year}{q:02d}_{CODE}_AI2.pdf'
        if (len(links)!=1 or links[0].get_text(strip=True)!=filename
                or links[0].get('href')!=f'javascript:readfile2("A","{CODE}","{filename}");'
                or not re.fullmatch(r'[1-9][0-9,]{0,12}',values[8])):raise ValueError('published filing action unverified')
        match=re.fullmatch(r'([0-9]{3})/([0-9]{2})/([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2})',values[9])
        if not match:raise ValueError('filing publication time unverified')
        yy,mm,dd,hh,mi,ss=map(int,match.groups());published=datetime(yy+1911,mm,dd,hh,mi,ss)
        if not quarter_end(year,q)<=published.date()<observed_day:
            raise ValueError('filing is future, predates period, or may follow valuation calculation')
        result[q]={'filename':filename,'published_at':published.isoformat(),'size':int(values[8].replace(',','')),
                   'scope':'individual','calendar':'calendar_year','period_end':quarter_end(year,q).isoformat()}
    if set(result)!=set(quarters):raise ValueError('required filing not in complete published index')
    return result

def parse_cumulative_income(raw, year, quarter):
    """Read the one explicit individual net-income row; no mother/total alias."""
    quarter_end(year, quarter)
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= 250000
            or raw.lower().count(b'</table>') != 2
            or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper()):
        raise ValueError('individual income original incomplete or over limit')
    soup = BeautifulSoup(raw.decode('utf-8', errors='strict'), 'html.parser')
    for name, expected in (('yearseason', f'{year}Q{quarter}'), ('year', str(year)), ('season', str(quarter))):
        fields = soup.select('input[name=' + name + ']')
        if len(fields) != 1 or fields[0].get('value') != expected:
            raise ValueError('individual cumulative period metadata mismatch')
    if '金額單位：新台幣仟元' not in soup.get_text(' ', strip=True):
        raise ValueError('individual monetary unit not verified')
    tables = soup.find_all('table')
    if len(tables) != 2:
        raise ValueError('individual table schema missing')
    headers = [' '.join(cell.get_text(' ', strip=True).split()) for cell in tables[1].select('thead th')]
    if headers != ['個別', COMPANY]:
        raise ValueError('individual scope or exact issuer header mismatch')
    labels, values = tables[0].select('tbody tr'), tables[1].select('tbody tr')
    if not labels or len(labels) != len(values) or len(labels) > 200:
        raise ValueError('individual income row alignment mismatch')
    selected = []
    for label_row, value_row in zip(labels, values):
        label_cells = label_row.find_all('td', recursive=False)
        value_cells = value_row.find_all('td', recursive=False)
        if len(label_cells) != 1 or len(value_cells) != 1:
            raise ValueError('individual income ambiguous columns')
        label = label_cells[0].get_text(' ', strip=True)
        if '母公司業主' in label or '非控制權益' in label:
            raise ValueError('consolidated owner row cannot enter individual income')
        if label == '本期淨利（淨損）':
            selected.append(value_cells[0].get_text(' ', strip=True))
    if len(selected) != 1:
        raise ValueError('individual net-income row missing or duplicated')
    return _amount(selected[0], label='本期淨利（淨損）')


def derive_nonpositive_income(year, quarter, incomes):
    periods = required_periods(year, quarter)
    if (not isinstance(incomes, dict) or set(incomes) != set(periods)
            or any(type(value) is not int for value in incomes.values())):
        raise ValueError('individual cumulative periods incomplete or ambiguous')
    net = (incomes[(year, 4)] if quarter == 4 else
           incomes[(year - 1, 4)] - incomes[(year - 1, quarter)] + incomes[(year, quarter)])
    if net > 0:
        raise ValueError('positive individual income does not explain missing P/E')
    start = date(year, 1, 1) if quarter == 4 else date(year - 1, quarter * 3 + 1, 1)
    return {'net_income_twd': net, 'period_start': start.isoformat(),
            'period_end': quarter_end(year, quarter).isoformat(),
            'basis': 'reported_cumulative_individual_income',
            'derivation': 'annual' if quarter == 4 else 'prior_annual - prior_YTD + current_YTD'}
