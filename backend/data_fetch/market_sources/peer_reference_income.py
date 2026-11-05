"""Period-bound official evidence for an undefined peer P/E, never a number.

Admission is an explicit set of independently qualified consolidated issuers.
Neither missing P/E nor a single negative quarter establishes this evidence.
"""
from calendar import monthrange
from datetime import date, datetime
import json
import re
from bs4 import BeautifulSoup
from .peer_reference_issuers import consolidated_issuer

_DEFAULT = consolidated_issuer()
TICKER = _DEFAULT.ticker
CODE = _DEFAULT.code
SHORT = _DEFAULT.short
LEGAL = _DEFAULT.legal
UBN = _DEFAULT.ubn
COMPANY = _DEFAULT.company_header
SCHEMA='twse-peer-reference-income.v1'
APPLICABILITY='not_applicable_nonpositive_reference_income'
FIELDS=['證券代號','證券名稱','收盤價','殖利率(%)','股利年度','本益比','股價淨值比','財報年/季']
INDEX_FIELDS=['證券代號','資料年度','資料類型','結案類型','性質','資料細節說明','備註','電子檔案','檔案大小','上傳日期','財務報告更(補)正']


def unique_json(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate JSON key')
            result[key]=value
        return result
    return json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=unique)


def quarter_end(year,quarter):
    if type(year)is not int or type(quarter)is not int or not 2013<=year<=2100 or quarter not in (1,2,3,4):
        raise ValueError('unverified financial period')
    return date(year,quarter*3,monthrange(year,quarter*3)[1])


def required_periods(year,quarter):
    quarter_end(year,quarter)
    return [(year,4)]if quarter==4 else[(year,quarter),(year-1,quarter),(year-1,4)]


def parse_methodology(raw):
    if (not isinstance(raw,bytes)or not 0<len(raw)<=250000
            or not raw.rstrip().lower().endswith(b'</html>')):
        raise ValueError('official valuation methodology incomplete')
    soup=BeautifulSoup(raw.decode('utf-8',errors='strict'),'html.parser')
    # The published page nests the clauses below a surrounding "basis" li.
    # Count leaf clauses only; an ancestor's repeated text is not a new rule.
    clauses=[''.join(li.get_text(' ',strip=True).split())for li in soup.select('body li')if not li.find('li')]
    required=('本益比=收盤價／每股參考稅後純益','每股參考稅後純益=該公司稅後參考純益／發行參考股數',
        '當每股參考稅後純益為0或負數時，則不計算本益比。',
        '近滿4季財務報告為計算基礎')
    if sum(all(piece in clause for piece in required)for clause in clauses)!=1:
        raise ValueError('official nonpositive-income rule no longer matches admitted methodology')


def parse_reference(raw,observed_day,*,issuer_ticker=TICKER):
    issuer = consolidated_issuer(issuer_ticker)
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
        if row[0]==issuer.code:selected.append(row)
    if len(selected)!=1:raise ValueError('missing or duplicate reference issuer')
    row=selected[0]
    if row[1]!=issuer.short or row[5]!='-'or not isinstance(row[7],str):
        raise ValueError('positive/ambiguous P/E or incorrect reference issuer')
    match=re.fullmatch(r'([0-9]{3})/([1-4])',row[7])
    if not match:raise ValueError('financial reference quarter unavailable')
    year,quarter=int(match[1])+1911,int(match[2])
    if quarter_end(year,quarter)>observed_day:raise ValueError('future financial reference')
    lag=(observed_day.year-year)*4+(observed_day.month-1)//3+1-quarter
    if not 0<=lag<=2:raise ValueError('stale financial reference')
    return {'year':year,'quarter':quarter,'raw_pe':row[5],'observed_at':observed_day.isoformat(),
            'reference_quarter':row[7],'official_short_name':row[1]}


def parse_calendar_index(raw,year,quarters,observed_day,*,issuer_ticker=TICKER):
    issuer = consolidated_issuer(issuer_ticker)
    if (not isinstance(raw,bytes)or not 0<len(raw)<=250000 or not raw.rstrip().lower().endswith(b'</html>')
            or type(observed_day)is not date or not isinstance(quarters,(list,tuple))
            or not quarters or len(set(quarters))!=len(quarters)):
        raise ValueError('unverified complete filing index')
    for q in quarters:quarter_end(year,q)
    soup=BeautifulSoup(raw.decode('big5',errors='strict'),'html.parser')
    text=' '.join(soup.get_text(' ',strip=True).split())
    if '公司名稱：'+issuer.short not in text.replace(' ','')or '會計期間：曆年制'not in text.replace(' ',''):
        raise ValueError('calendar year or company not established by filing index')
    tables=[t for t in soup.find_all('table')if t.find('tr')and
        [c.get_text(' ',strip=True)for c in t.find('tr').find_all(['td','th'],recursive=False)]==INDEX_FIELDS]
    if len(tables)!=1:raise ValueError('filing table schema unverified')
    rows=tables[0].find_all('tr')[1:]
    if not 1<=len(rows)<=64:raise ValueError('filing index over limit or empty')
    result={};names={1:'一',2:'二',3:'三',4:'四'}
    for row in rows:
        cells=row.find_all(['td','th'],recursive=False);values=[c.get_text(' ',strip=True)for c in cells]
        if len(values)!=11 or values[0]!=issuer.code or values[2]!='財務報告書':raise ValueError('index issuer or shape mismatch')
        match=re.fullmatch(str(year-1911)+r'年第([一二三四])季',values[1].replace(' ',''))
        if not match:raise ValueError('index fiscal year or quarter mismatch')
        q=next(q for q,n in names.items()if n==match[1])
        if values[5]!='IFRSs合併財報':continue
        if q not in quarters:continue
        if q in result or values[10]!='無':raise ValueError('duplicate or corrected filing is not admitted')
        links=cells[7].find_all('a');filename=f'{year}{q:02d}_{issuer.code}_AI1.pdf'
        if (len(links)!=1 or links[0].get_text(strip=True)!=filename
                or links[0].get('href')!=f'javascript:readfile2("A","{issuer.code}","{filename}");'
                or not re.fullmatch(r'[1-9][0-9,]{0,12}',values[8])):raise ValueError('published filing action unverified')
        match=re.fullmatch(r'([0-9]{3})/([0-9]{2})/([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2})',values[9])
        if not match:raise ValueError('filing publication time unverified')
        yy,mm,dd,hh,mi,ss=map(int,match.groups());published=datetime(yy+1911,mm,dd,hh,mi,ss)
        if not quarter_end(year,q)<=published.date()<observed_day:
            raise ValueError('filing is future, predates period, or may follow valuation calculation')
        result[q]={'filename':filename,'published_at':published.isoformat(),'size':int(values[8].replace(',','')),
                   'scope':'consolidated','calendar':'calendar_year','period_end':quarter_end(year,q).isoformat()}
    if set(result)!=set(quarters):raise ValueError('required filing not in complete published index')
    return result


def parse_cumulative_income(raw,year,quarter,*,issuer_ticker=TICKER):
    issuer = consolidated_issuer(issuer_ticker)
    quarter_end(year,quarter)
    if not isinstance(raw,bytes)or not 0<len(raw)<=250000:raise ValueError('income body outside limit')
    soup=BeautifulSoup(raw.decode('utf-8',errors='strict'),'html.parser')
    if raw.lower().count(b'</table>')!=2:raise ValueError('income tables incomplete')
    for name,expected in (('yearseason',f'{year}Q{quarter}'),('year',str(year)),('season',str(quarter))):
        fields=soup.select('input[name='+name+']')
        if len(fields)!=1 or fields[0].get('value')!=expected:raise ValueError('income period metadata mismatch')
    from .official_mopsfin_financial import parse_statement
    facts=parse_statement(raw,issuer.code,'IncomeStatement')
    tables=soup.find_all('table');headers=tables[1].select('thead th')
    if len(headers)!=2 or ' '.join(headers[1].get_text(' ',strip=True).split())!=issuer.company_header:
        raise ValueError('income issuer/name/business header mismatch')
    labels=tables[0].select('tbody tr');values=tables[1].select('tbody tr')
    total=[value.get_text(' ',strip=True)for label,value in zip(labels,values)
           if label.get_text(' ',strip=True)=='本期淨利（淨損）']
    from .official_mopsfin_financial import _amount
    income=facts['ProfitLossAttributableToOwnersOfParent']
    if len(total)!=1 or _amount(total[0],label='本期淨利（淨損）')!=income:
        raise ValueError('total versus parent reference-income basis requires separate qualification')
    return income


def derive_nonpositive_income(year,quarter,incomes):
    """Use money from disjoint cumulative periods; never sum per-share EPS."""
    periods=required_periods(year,quarter)
    if (not isinstance(incomes,dict)or set(incomes)!=set(periods)
            or any(type(v)is not int for v in incomes.values())):
        raise ValueError('missing or ambiguous cumulative income periods')
    income=(incomes[(year,4)]if quarter==4 else
            incomes[(year-1,4)]-incomes[(year-1,quarter)]+incomes[(year,quarter)])
    if income>0:raise ValueError('positive reference income does not explain missing P/E')
    start=date(year,1,1)if quarter==4 else date(year-1,quarter*3+1,1)
    return {'net_income_twd':income,'period_start':start.isoformat(),
            'period_end':quarter_end(year,quarter).isoformat(),
            'basis':'reported_cumulative_parent_income',
            'derivation':'annual'if quarter==4 else'prior_annual - prior_YTD + current_YTD'}
