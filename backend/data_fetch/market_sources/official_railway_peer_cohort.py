"""Exact THSRC railway references; current listing is not valuation equivalence."""
from datetime import date,datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
import re,time

from bs4 import BeautifulSoup

from official_response_evidence import archive_response,read_response
from source_pdf_reader import extract_pdf_pages,SourcePdfError
from .issuer_news_transport import IssuerNewsHttp
from .official_thermal_peer_cohort import ThermalHttp,_receipt_current,_roster
from .official_company_legal_name import URLS,select_legal_name
from .jpx_company_transport import JpxCompanyGateway,verify_bundle
from .jpx_company_schema import annual_document

TARGET='2633.TW'
SHORT='台灣高鐵'
LEGAL='台灣高速鐵路股份有限公司'
UBN='16446274'
MASTER=URLS['.TW']
ISSUER_URL='https://www.thsrc.com.tw/corp/a021c60f-4a63-44df-8332-1f0920615c48'
CENTRAL_URL='https://global.jr-central.co.jp/en/company/about/area.html'
KYUSHU_COMPANY='https://www.jrkyushu.co.jp/english/company.html'
KYUSHU_TRAINS='https://www.jrkyushu.co.jp/english/train/index.html'
IDENTITIES={'9020.T':'East Japan Railway Company','9021.T':'West Japan Railway Company',
            '9022.T':'Central Japan Railway Company','9142.T':'Kyushu Railway Company'}
SCOPE='cross_market_high_speed_rail_reference'
POLICY='official-thsrc-jpx-rail-reference-v1'
RECEIPT_KEY='railway_membership_originals'


class RailHttp(ThermalHttp):
    def __init__(self,deadline):IssuerNewsHttp.__init__(self,deadline)

    @staticmethod
    def route_contract(url):
        if url==MASTER:return 2_500_000,{'application/json','text/json'}
        if url in{ISSUER_URL,CENTRAL_URL,KYUSHU_COMPANY,KYUSHU_TRAINS}:return 500_000,{'text/html','application/xhtml+xml'}
        if isinstance(url,str)and re.fullmatch(r'https://www2\.jpx\.co\.jp/disc/(?:90200|90210)/1401\d{14}\.pdf',url):
            return 2_000_000,{'application/pdf','application/octet-stream'}
        raise ValueError('rail_source_url_invalid')

    def _download(self,url,diagnostic):
        value=IssuerNewsHttp._download(self,url,diagnostic)
        return {**value,'request_method':'GET','http_status':200,'http_status_observed':True,
                'response_complete':True,'fetched_at_epoch':time.time()}

    def original(self,url):
        from cache_store import get_cache_json
        raw=self.get(url);part=self.components[-1];shared=part.get('evidence_kind')=='cached_complete_source_payload_verified_by_digest'
        stamp=part['fetched_at_epoch'];until=part['fresh_until_epoch']
        if not shared:
            cached=get_cache_json('shared_provider:v1:'+sha256(('issuer-news-raw:v1:'+url).encode()).hexdigest())
            value=cached.get('value')if isinstance(cached,dict)else None
            if(not isinstance(value,dict)or value.get('request_method')!='GET'or value.get('http_status')!=200
                    or value.get('http_status_observed')is not True or value.get('response_complete')is not True):
                raise ValueError('rail_retained_http_receipt_missing')
            stamp=value['fetched_at_epoch'];until=min(until,stamp+1800)
        proof=archive_response(raw,source_url=url,retrieved_at=stamp,evidence_kind=part['evidence_kind'],
                               http_status=None if shared else 200)
        proof.update(fresh_until_epoch=until,http_status_observed=not shared,
                     cache_hit=bool(part.get('cache_hit')))
        if not shared:proof.update(request_method='GET',response_complete=True)
        return proof


def _raw(proof,url):
    if not _receipt_current(proof,url):raise ValueError('rail_original_unverified_or_expired')
    raw=read_response(proof);limit,_=RailHttp.route_contract(url)
    if type(proof.get('raw_response_bytes'))is not int or not 0<len(raw)<=limit or len(raw)!=proof['raw_response_bytes']:
        raise ValueError('rail_original_size_invalid')
    if proof.get('evidence_kind')=='raw_http_response_bytes'and(proof.get('request_method')!='GET'or proof.get('response_complete')is not True):
        raise ValueError('rail_native_original_incomplete')
    return raw


def _html(raw):return BeautifulSoup(raw.decode('utf-8',errors='strict'),'html.parser')


def _issuer(originals,today):
    raw=_raw(originals['master'],MASTER);roster=_roster(raw,'.TW')
    anchor=select_legal_name(roster,TARGET,SHORT,today=today)
    day=datetime.fromtimestamp(originals['master']['retrieved_at'],ZoneInfo('Asia/Taipei')).date()
    if(not anchor or anchor['legal_name']!=LEGAL or anchor['official_ubn']!=UBN
            or not date.fromisoformat(anchor['as_of'])<=day<=today
            or not 0<=(today-date.fromisoformat(anchor['as_of'])).days<=7):raise ValueError('rail_current_issuer_unverified')
    soup=_html(_raw(originals['issuer'],ISSUER_URL));required={'股票代號':'2633','公司名稱':LEGAL,'營利事業統一編號':UBN,'主要經營業務':'高速鐵路之經營'}
    for label,value in required.items():
        rows=[r.find_all('td',recursive=False)for r in soup.find_all('tr')]
        rows=[cells for cells in rows if len(cells)==2 and cells[0].get('scope')=='row'and cells[0].get_text(' ',strip=True)==label]
        if len(rows)!=1 or rows[0][1].get_text(' ',strip=True)!=value:raise ValueError('rail_issuer_business_unverified')
    return anchor


def _filed_business(originals,listing,today):
    gateway=originals['jpx'];details=read_response(gateway['originals'][2])
    selected=annual_document(details,listing,today=today)
    if originals.get('material_selection')!=selected:raise ValueError('rail_filing_index_disagrees')
    raw=_raw(originals['material'],selected['source_url']);parsed=extract_pdf_pages(raw)
    if parsed['coverage_status']!='complete':raise ValueError('rail_filing_native_text_partial')
    first=parsed['pages'][0]['text'];compact=re.sub(r'\s+','',first);year=selected['fiscal_year_end'][:4]
    if(listing['legal_name']not in first or not re.search(r'(?:Securities\s*Code|Code\s*number:)\s*'+listing['code'][:4]+r'\b',first,re.I)
            or 'March31,'+year not in compact or 'consolidated'not in first.casefold()
            or 'japanesegaap'not in compact.casefold()or'millionsofyen'not in compact.casefold()
            or not any('Shinkansen'in p['text']for p in parsed['pages'])):raise ValueError('rail_filing_business_or_period_unverified')
    return {'kind':'official_filed_annual_result_business_reference','fiscal_year_end':selected['fiscal_year_end'],
            'published_at':selected['published_at'],'standard':'Japanese GAAP','reporting_currency':'JPY',
            'audit_status':'explicitly_unaudited'if'unaudited'in first.casefold()else'not_qualified',
            'native_page_count':parsed['page_count'],'numeric_facts_admitted':False,
            'source_url':selected['source_url']}


def _row(symbol,originals,today):
    if symbol not in IDENTITIES or not isinstance(originals,dict):raise ValueError('rail_symbol_invalid')
    anchor=_issuer(originals,today);code=symbol[:4]+'0';jpx=originals['jpx'];detailed=symbol in{'9020.T','9021.T'}
    verify_bundle(jpx,code,details=detailed);listing=jpx['listing']
    if(listing['legal_name']!=IDENTITIES[symbol]or listing['industry']!='Land Transportation'
            or listing['fiscal_year_end_month']!='March'):raise ValueError('rail_jpx_identity_or_industry_disagrees')
    if detailed:business=_filed_business(originals,listing,today)
    elif symbol=='9022.T':
        soup=_html(_raw(originals['material'],CENTRAL_URL));text=soup.get_text(' ',strip=True)
        if(not soup.title or'Central Japan Railway Company'not in soup.title.get_text()
                or"The core of JR Central's operations is the Tokaido Shinkansen"not in text):raise ValueError('rail_central_business_unverified')
        business={'kind':'undated_official_operating_area_reference','source_url':CENTRAL_URL,'numeric_facts_admitted':False}
    else:
        company=_html(_raw(originals['company'],KYUSHU_COMPANY));pairs=[r for r in company.find_all('tr')if r.find('th')and r.find('th').get_text(' ',strip=True)=='Company name']
        if len(pairs)!=1 or pairs[0].find('td').get_text(' ',strip=True)!=IDENTITIES[symbol]:raise ValueError('rail_kyushu_company_unverified')
        soup=_html(_raw(originals['material'],KYUSHU_TRAINS));text=soup.get_text(' ',strip=True)
        if(not soup.find('h1')or soup.find('h1').get_text(' ',strip=True)!='Train Varieties'
                or not all(t in text for t in ('JR Kyushu trains','Kyushu Shinkansen','N700'))):raise ValueError('rail_kyushu_services_unverified')
        windows=re.findall(r'Timetables\s*\(major trains,\s*(20\d{2})\.(\d{1,2})\.(\d{1,2})-(20\d{2})\.(\d{1,2})\.(\d{1,2})\)',text)
        if len(windows)!=1:raise ValueError('rail_kyushu_timetable_unverified')
        values=list(map(int,windows[0]));start,end=date(*values[:3]),date(*values[3:])
        if not start<=today<=end:raise ValueError('rail_kyushu_timetable_not_current')
        business={'kind':'official_train_services_reference','source_url':KYUSHU_TRAINS,
                  'published_timetable_start':start.isoformat(),'published_timetable_end':end.isoformat(),'numeric_facts_admitted':False}
    return {'name':IDENTITIES[symbol],'ticker':symbol,'identity_status':'current_jpx_prime_equity_and_official_operator_originals',
            'comparison_status':'official_segment_candidate','comparison_scope':SCOPE,'selection_policy':POLICY,
            'relationship_basis':'published_shinkansen_operations_reference_not_valuation_equivalence',
            'business_comparability_verified_current':False,'membership_effective_date_verified':False,
            'numeric_comparability_verified':False,'currency_comparability_verified':False,
            'market_currency':'JPY','target_market_currency':'TWD',
            'comparison_limitations':['cross_market_Taiwan_Japan','JPY_TWD_not_normalized','different_fiscal_year_ends',
                'whole_company_business_mix_not_verified','provider_quote_reporting_periods_unspecified','code_order_is_not_economic_rank'],
            'issuer_master_anchor':anchor,'jpx_master_anchor':listing,'business_reference':business,RECEIPT_KEY:originals}


def verified_candidates(records,ticker,*,today):
    try:
        if ticker!=TARGET or not isinstance(records,list)or not 1<=len(records)<=len(IDENTITIES):return False
        symbols=[r.get('ticker')for r in records if isinstance(r,dict)]
        if len(symbols)!=len(records)or len(set(symbols))!=len(symbols):return False
        for record,symbol in zip(records,symbols):
            expected=_row(symbol,record.get(RECEIPT_KEY),today)
            if(any(record.get(k)!=v for k,v in expected.items())or any(record.get(k)is not False for k in
                    ('business_comparability_verified_current','membership_effective_date_verified','numeric_comparability_verified','currency_comparability_verified'))):return False
        return True
    except(ValueError,TypeError,KeyError,OSError,EOFError,OverflowError,SourcePdfError):return False


def get_candidates(ticker,*,today):
    if ticker!=TARGET:return {'candidates':[],'status':'not_applicable'}
    deadline=time.monotonic()+25;http=RailHttp(deadline);gateway=JpxCompanyGateway(deadline);rows=[];errors={}
    try:
        common={'master':http.original(MASTER),'issuer':http.original(ISSUER_URL)}
        _issuer(common,today)
    except Exception as exc:
        return {'candidates':[],'status':'official_rail_issuer_unavailable','error_kind':_error_kind(exc),
                'http_request_count':http.http_request_count,'components':http.components}
    for symbol in IDENTITIES:
        try:
            originals={**common,'jpx':gateway.get(symbol[:4]+'0',details=symbol in{'9020.T','9021.T'})}
            listing=originals['jpx']['listing']
            if symbol in{'9020.T','9021.T'}:
                selected=annual_document(read_response(originals['jpx']['originals'][2]),listing,today=today)
                originals.update(material=http.original(selected['source_url']),material_selection=selected)
            elif symbol=='9022.T':originals['material']=http.original(CENTRAL_URL)
            else:originals.update(company=http.original(KYUSHU_COMPANY),material=http.original(KYUSHU_TRAINS))
            rows.append(_row(symbol,originals,today))
        except Exception as exc:errors[symbol]=_error_kind(exc)
    return {'candidates':rows,'status':'success'if len(rows)==len(IDENTITIES)else'partial_membership'if rows else'official_rail_originals_unavailable',
            'expected_candidate_count':len(IDENTITIES),'unqualified_members':errors,
            'http_request_count':http.http_request_count+gateway.http_request_count,'components':http.components+gateway.components}


def _error_kind(exc):
    kind=getattr(exc,'error_kind',None)
    if isinstance(kind,str)and re.fullmatch(r'[a-z][a-z0-9_]{0,80}',kind):return kind
    if isinstance(exc,ValueError)and re.fullmatch(r'[a-z][a-z0-9_]{0,80}',str(exc)):return str(exc)
    return type(exc).__name__
