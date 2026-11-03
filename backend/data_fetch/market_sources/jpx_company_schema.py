"""Finite public JPX form/result contracts; source text is never executed."""
from datetime import date
import re
from urllib.parse import urljoin,urlsplit,parse_qs

from bs4 import BeautifulSoup

HOST='https://www2.jpx.co.jp'
ENTRY_URL=HOST+'/tseHpFront/JJK020010Action.do?Show=Show'
SEARCH_URL=HOST+'/tseHpFront/JJK020010Action.do'
DETAIL_URL=HOST+'/tseHpFront/JJK020030Action.do'
LIMIT=500_000
MONTHS=('January','February','March','April','May','June','July','August','September','October','November','December')
HEADINGS=['Code','Issuename','MarketSegment','Industry','Fiscalyear-end','Alerts,etc.','Basicinformation','Stockprices']
DETAIL_HEADINGS=['Code','ISINCode','MarketSegment','Industry','Fiscalyear-end','Tradingunit']


def page(raw):
    if not isinstance(raw,bytes)or not 100<len(raw)<=LIMIT:raise ValueError('jpx_body_invalid')
    return BeautifulSoup(raw,'html.parser')


def common_code(code):
    if not isinstance(code,str)or not re.fullmatch(r'[1-9]\d{3}0',code):raise ValueError('jpx_common_code_invalid')
    return code


def _compact(text):return re.sub(r'\s+','',text)


def form_action(form,canonical):
    url=urljoin(HOST,form.get('action',''));u=urlsplit(url)
    base=urlsplit(canonical).path
    if (form.get('method','').upper()!='POST'or u.scheme!='https'or u.netloc!='www2.jpx.co.jp'
            or u.query or u.fragment or not re.fullmatch(re.escape(base)+r'(?:;jsessionid=[0-9A-F]{33})?',u.path)):
        raise ValueError('jpx_form_action_invalid')
    return url


def _hidden(form):
    fields={}
    for node in form.select('input[type="hidden"][name]'):
        if node.has_attr('disabled'):continue
        key,value=node['name'],node.get('value','')
        if key in fields or len(key)>100 or len(value)>2048:raise ValueError('jpx_form_fields_ambiguous')
        fields[key]=value
    return fields


def search_form(raw,code):
    common_code(code);soup=page(raw);forms=soup.find_all('form',attrs={'name':'JJK020010Form'})
    if len(forms)!=1:raise ValueError('jpx_search_form_missing')
    form=forms[0];url=form_action(form,SEARCH_URL)
    if (len(form.select('input[name="eqMgrCd"][maxlength="5"]'))!=1
            or len(form.select('input[name="szkbuChkbx"][value="011"]'))!=1
            or form.select('input[name="jjHisiKbnChkbx"][checked]')):raise ValueError('jpx_search_contract_invalid')
    fields=_hidden(form)
    if set(fields)!={'sniMtGmnId','dspSsuPdMapOut','szkbuChkbxMapOut'}:raise ValueError('jpx_search_fields_changed')
    fields.update(ListShow='ListShow',eqMgrCd=code,dspSsuPd='10',mgrMiTxtBx='',szkbuChkbx='011')
    return url,fields


def parse_listing(raw,code):
    common_code(code);soup=page(raw)
    if len(soup.find_all('form',attrs={'name':'JJK020030Form'}))!=1:raise ValueError('jpx_not_result_form')
    if _compact(soup.get_text()).count('Displayof1-1items/1')!=2:raise ValueError('jpx_result_count_invalid')
    tables=[]
    for table in soup.find_all('table'):
        for row in table.find_all('tr',recursive=False):
            if [_compact(th.get_text(' ',strip=True))for th in row.find_all('th',recursive=False)]==HEADINGS:tables.append(table)
    if len(tables)!=1:raise ValueError('jpx_result_header_invalid')
    rows=[r for r in tables[0].find_all('tr',recursive=False)if r.find('td',recursive=False)]
    if len(rows)!=1:raise ValueError('jpx_result_rows_invalid')
    cells=rows[0].find_all('td',recursive=False)
    if len(cells)!=8:raise ValueError('jpx_column_count_invalid')
    labels=[c.get_text(' ',strip=True)for c in cells[:5]]
    if labels[0]!=code or not 1<=len(labels[1])<=200 or labels[2]!='Prime'or not labels[3]or labels[4]not in MONTHS:
        raise ValueError('jpx_current_prime_identity_invalid')
    for cell,label,suffix in zip(cells[:5],labels,['eqMgrCd','eqMgrNm','szkbuNm','gyshDspNm','dspYuKssnKi']):
        values=cell.find_all('input',attrs={'name':'ccJjCrpSelKekkLst_st[0].'+suffix,'type':'hidden'})
        if len(values)!=1 or values[0].get('value')!=label:raise ValueError('jpx_identity_disagreement')
    if cells[5].get_text(' ',strip=True)or cells[5].find(['img','a','input']):raise ValueError('jpx_listing_alert_present')
    buttons=cells[6].find_all('input',attrs={'name':'detail_button','type':'button'})
    if len(buttons)!=1 or buttons[0].get('onclick')!="gotoBaseJh('"+code+"', '1');":raise ValueError('jpx_detail_binding_invalid')
    links=cells[7].find_all('a',href=True)
    if len(links)!=1:raise ValueError('jpx_quote_binding_invalid')
    u=urlsplit(links[0]['href']);query=parse_qs(u.query)
    if(u.scheme!='https'or u.netloc!='quote.jpx.co.jp'or u.path!='/jpxhp/main/index.aspx'or u.fragment
            or query!={'F':['e_stock_detail'],'disptype':['information'],'qcode':[code[:4]]}):raise ValueError('jpx_quote_binding_invalid')
    return {'code':code,'ticker':code[:4]+'.T','legal_name':labels[1],'market':labels[2],
            'industry':labels[3],'fiscal_year_end_month':labels[4],'listing_alerts':'none displayed'}


def detail_form(raw,code):
    parse_listing(raw,code);soup=page(raw);form=soup.find('form',attrs={'name':'JJK020030Form'})
    url=form_action(form,DETAIL_URL);fields=_hidden(form)
    allowed={'lstDspPg','dspGs','souKnsu','sniMtGmnId','dspJnKbn','dspJnKmkNo','mgrCd','jjHisiFlg',
             *{'ccJjCrpSelKekkLst_st[0].'+s for s in ('eqMgrCd','eqMgrNm','szkbuNm','gyshDspNm','dspYuKssnKi')}}
    if set(fields)!=allowed:raise ValueError('jpx_detail_fields_changed')
    fields.update(BaseJh='BaseJh',mgrCd=code,jjHisiFlg='1')
    return url,fields


def parse_details(raw,listing):
    soup=page(raw);names=[h.get_text(' ',strip=True)for h in soup.find_all('h3')]
    if names!=[listing['legal_name']]*4:raise ValueError('jpx_detail_company_disagrees')
    found=[]
    for table in soup.find_all('table'):
        rows=table.find_all('tr',recursive=False)
        if not rows or [_compact(h.get_text(' ',strip=True))for h in rows[0].find_all('th',recursive=False)]!=DETAIL_HEADINGS:continue
        if len(rows)!=2:raise ValueError('jpx_detail_table_ambiguous')
        values=[c.get_text(' ',strip=True)for c in rows[1].find_all('td',recursive=False)]
        if(len(values)!=6 or values[0]!=listing['code']or not re.fullmatch(r'JP[A-Z0-9]{10}',values[1])
                or values[2:4]!=[listing['market'],listing['industry']]
                or not values[4].startswith(listing['fiscal_year_end_month']+',')or not values[5].isdigit()):
            raise ValueError('jpx_detail_market_disagrees')
        found.append(values)
    if len(found)!=4 or any(v!=found[0]for v in found):raise ValueError('jpx_detail_identity_ambiguous')
    return soup


def annual_document(raw,listing,*,today):
    soup=parse_details(raw,listing);selected=[];corrections=[]
    for link in soup.find_all('a',href=True):
        title=link.get_text(' ',strip=True);row=link.find_parent('tr')
        if row is None:continue
        text=row.get_text(' ',strip=True);match=re.match(r'(20\d{2})/(\d{2})/(\d{2})\b',text)
        if not match:continue
        published=date(*map(int,match.groups()))
        if published>today:continue
        if 'correction'in title.lower()and'financial results'in title.lower()and'presentation'not in title.lower():corrections.append((published,title))
        first=re.fullmatch(r'Fiscal (20\d{2}) Consolidated Financial Results \(Japanese GAAP\)',title,re.I)
        second=re.fullmatch(r'CONSOLIDATED FINANCIAL RESULTS FOR THE FISCAL YEAR ENDED MARCH 31,\s*(20\d{2}) \[JAPANESE GAAP\]',title,re.I)
        fiscal=first or second
        if not fiscal:continue
        year=int(fiscal[1]);end=date(year,3,31);url=urljoin(HOST,link['href']);u=urlsplit(url)
        if(u.scheme!='https'or u.netloc!='www2.jpx.co.jp'or u.query or u.fragment
                or not re.fullmatch('/disc/'+listing['code']+r'/1401\d{14}\.pdf',u.path)
                or not end<=published<=today or not 0<=(today-end).days<=370):continue
        selected.append({'source_url':url,'title':title,'published_at':published.isoformat(),'fiscal_year_end':end.isoformat()})
    if not selected:raise ValueError('jpx_annual_publication_missing')
    latest=max(d['fiscal_year_end']for d in selected);choices=[d for d in selected if d['fiscal_year_end']==latest]
    if len(choices)!=1:raise ValueError('jpx_annual_publication_ambiguous')
    chosen=choices[0]
    if any(p>=date.fromisoformat(chosen['published_at'])and latest[:4]in title for p,title in corrections):raise ValueError('jpx_annual_revision_unqualified')
    return chosen
