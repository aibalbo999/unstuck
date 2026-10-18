"""Observed official segment membership, never whole-company valuation peers.

The original pages have no membership effective date. Retain that limitation,
original retrieval times, current SDK identity mapping and complete HTTP bytes.
"""
from datetime import date,datetime
import base64,math,re,time
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp

POLICY='tpex-observed-undated-segment-discovery.v1'
PROVIDER='TPEx official segment discovery'
TYPE='official_industry_segment_peer_candidate'
HOST='https://ic.tpex.org.tw/'
TAIPEI=ZoneInfo('Asia/Taipei')
PROFILES={
    '9945.TW':{'name':'潤泰新','chain':'S000','group_id':'companyList_S600','segment':'營造業','root':'建材營造',
               'scope':'construction_segment','category':'其他','peers':{'2535':'達欣工','2546':'根基','5515':'建國','2597':'潤弘'},'peer_category':'建材營造'},
    '1216.TW':{'name':'統一','chain':'M000','group_id':'companyList_M200','segment':'加工食品','root':'食品',
               'scope':'food_processing_segment','category':'食品工業','peers':{'1229':'聯華','1225':'福懋油','1232':'大統益','1702':'南僑'},'peer_category':'食品工業'},
}
for _ticker,_profile in PROFILES.items():
    _profile.update(issuer_url=HOST+'company_chain.php?stk_code='+_ticker[:4],segment_url=HOST+'introduce.php?ic='+_profile['chain'])


def _page(raw):
    if not isinstance(raw,bytes) or not 100<=len(raw)<=250_000:raise ValueError('invalid segment original size')
    return BeautifulSoup(raw.decode('utf-8'),'html.parser')


def _compact(text):return re.sub(r'\s+','',text)


def _issuer_member(raw,ticker):
    p=PROFILES[ticker];soup=_page(raw)
    headings=[h for h in soup.find_all('h4') if _compact(h.get_text())==f'{ticker[:4]}{p["name"]}所屬產業鏈如下:']
    if len(headings)!=1:raise ValueError('issuer heading unverified')
    section=headings[0].find_parent('div',class_='content')
    if (section is None or len([h for h in section.find_all('h3')if h.get_text(' ',strip=True)=='個體公司所屬產業鏈'])!=1
            or len([h for h in section.find_all('h4')if re.fullmatch(r'[0-9]{4}.+所屬產業鏈如下:',_compact(h.get_text()))])!=1):
        raise ValueError('issuer section ambiguous')
    headings=[h for h in section.find_all('h4')if _compact(h.get_text())==f'►{p["root"]}>{p["segment"]}']
    if len(headings)!=1 or len(headings[0].find_all('a',href='introduce.php?ic='+p['chain']))!=1:
        raise ValueError('issuer segment unverified')


def _group_codes(raw,ticker):
    p=PROFILES[ticker];groups=_page(raw).select(f'div#{p["group_id"]}[title="{p["segment"]}"]')
    # The native desktop panel has only a title attribute; the mobile panel
    # also repeats the segment in bold. Require the latter when both exist.
    if not 1<=len(groups)<=2 or not any(b.get_text(' ',strip=True)==p['segment']for g in groups for b in g.find_all('b')):
        raise ValueError('segment group unverified')
    panels=[]
    for group in groups:
        found={}
        for a in group.find_all('a',href=True):
            match=re.fullmatch(r'company_basic\.php\?stk_code=([1-9]\d{3})',a['href'])
            if match:found.setdefault(match[1],[]).append((a.get_text(' ',strip=True),a.get('title')))
        if found.get(ticker[:4])!=[(p['name'],p['name'])]:raise ValueError('issuer absent from exact segment')
        panels.append(found)
    return [code for code,name in p['peers'].items()if all(g.get(code)==[(name,name)]for g in panels)]


class SegmentHttp(IssuerNewsHttp):
    @staticmethod
    def route_contract(url):
        if url in {p[k]for p in PROFILES.values()for k in ('issuer_url','segment_url')}:
            return 250_000,{'text/html','application/xhtml+xml'}
        raise SourceResponseError('transport_url_invalid')

    def _download(self,url,diagnostic):
        value=super()._download(url,diagnostic);raw=base64.b64decode(value['body_b64'])
        # Validate the original before assigning its successful raw-cache TTL.
        try:
            for ticker,p in PROFILES.items():
                if url==p['issuer_url']:_issuer_member(raw,ticker)
                elif url==p['segment_url']:_group_codes(raw,ticker)
        except (ValueError, UnicodeError) as exc:
            diagnostic['error_kind']='official_segment_original_invalid'
            raise SourceResponseError(diagnostic['error_kind']) from exc
        return value


def _mapping(rows,ticker,today):
    p=PROFILES[ticker];names={ticker[:4]:p['name'],**p['peers']};dated=[]
    for row in rows:
        if not isinstance(row,dict):continue
        try:day=date.fromisoformat(str(row.get('date')))
        except (ValueError,TypeError):continue
        if day<=today:dated.append((day,row))
    if not dated:raise ValueError('no current SDK identity mapping')
    latest=max(day for day,row in dated)
    if not 0<=(today-latest).days<=7:raise ValueError('stale SDK mapping')
    selected=[]
    for code,name in names.items():
        matching=[row for day,row in dated if day==latest and str(row.get('stock_id'))==code]
        category=p['category'] if code==ticker[:4] else p['peer_category']
        if not matching or any(r.get('stock_name')!=name or r.get('type')!='twse' or r.get('industry_category')!=category for r in matching):
            if code==ticker[:4]:raise ValueError('target SDK identity unverified')
            continue
        selected.append({k:matching[0][k]for k in ('stock_id','stock_name','industry_category','type','date')})
    return latest,selected


def _build(ticker,mapping,originals,today):
    p=PROFILES[ticker];master_day,selected=_mapping(mapping,ticker,today)
    raw={};stamps=[]
    for key,url in (('issuer',p['issuer_url']),('segment',p['segment_url'])):
        receipt=originals[key];stamp=receipt['retrieved_at']
        if (receipt.get('status')!='archived' or receipt.get('http_status')!=200 or receipt.get('source_url')!=url
                or receipt.get('evidence_kind')!='raw_http_response_bytes' or type(stamp) not in (int,float)
                or not math.isfinite(stamp) or not 0<=time.time()-stamp<=1800):raise ValueError('stale or unverified segment receipt')
        raw[key]=read_response(receipt);stamps.append(stamp)
    observed=min(datetime.fromtimestamp(stamp,TAIPEI).date()for stamp in stamps)
    if observed<master_day or observed>today:raise ValueError('original chronology unverified')
    _issuer_member(raw['issuer'],ticker);codes=_group_codes(raw['segment'],ticker)
    current={r['stock_id'] for r in selected};records=[]
    for code,name in p['peers'].items():
        if code not in current or code not in codes:continue
        records.append({'title':f'櫃買產業鏈{p["segment"]}候選：{p["name"]}、{name}',
            'source':'櫃買中心產業價值鏈資訊平台','source_type':TYPE,'link':p['segment_url'],
            'selection_policy':POLICY,'relationship_kind':'observed_same_undated_segment_membership',
            'relationship_basis':'exact_official_issuer_section_and_same_segment_listing',
            'comparison_scope':p['scope'],'business_comparability_verified':False,
            'business_comparability_verified_current':False,'numeric_comparability_verified':False,
            'membership_effective_date_verified':False,'observation_date_basis':'original_page_retrieved_at',
            'observed_at':observed.isoformat(),'comparison_limitations':['undated_segment_membership',
                'whole_company_business_mix_not_verified','financial_period_comparability_not_verified'],
            'issuer':{'ticker':ticker,'official_name':p['name']},
            'counterparty':{'ticker':code+'.TW','official_name':name,'source_url':HOST+'company_basic.php?stk_code='+code},
            'source_record_archive':{'official_segment_originals':originals,'sdk_master_mapping':selected,
                'sdk_mapping_is_not_complete_raw_http':True}})
    return records[:5]


def segment_record_hint(record):
    return isinstance(record,dict) and (record.get('source_type')==TYPE or record.get('selection_policy')==POLICY
        or isinstance(record.get('source_record_archive'),dict) and 'official_segment_originals' in record['source_record_archive'])


def is_segment_discovery_record(record,ticker,*,today=None):
    try:
        if ticker not in PROFILES or not isinstance(record,dict) or record.get('source_type')!=TYPE or record.get('selection_policy')!=POLICY:return False
        for key in ('business_comparability_verified','business_comparability_verified_current','numeric_comparability_verified','membership_effective_date_verified'):
            if record.get(key) is not False:return False
        archive=record['source_record_archive']
        if not isinstance(archive,dict) or archive.get('sdk_mapping_is_not_complete_raw_http') is not True:return False
        expected=_build(ticker,archive['sdk_master_mapping'],archive['official_segment_originals'],today or datetime.now(TAIPEI).date())
        return record in expected
    except (ValueError,KeyError,TypeError,AttributeError,OSError,EOFError,OverflowError):return False


def fetch_segment_discovery(ticker,master_rows,*,today=None,http_cls=SegmentHttp):
    today=today or datetime.now(TAIPEI).date();started=time.time();deadline=time.monotonic()+12
    audit={'source':'peer_discovery','provider':PROVIDER,'selection_policy':POLICY,'record_count':0,'status':'not_applicable',
           'http_request_sent':False,'cache_hit':False,'stale':False,'membership_effective_date_verified':False}
    if ticker not in PROFILES:return {'records':[],'audit':audit}
    try:_,mapping=_mapping(master_rows,ticker,today)
    except (ValueError,KeyError,TypeError) as exc:
        audit.update(status='unavailable',event_kind='local_block',error_kind=type(exc).__name__)
        return {'records':[],'audit':audit}
    p=PROFILES[ticker];http=http_cls(deadline);originals={}
    try:
        for key,url in (('issuer',p['issuer_url']),('segment',p['segment_url'])):
            raw=http.get(url);component=http.components[-1]
            originals[key]=archive_response(raw,source_url=url,retrieved_at=component['fetched_at_epoch'],http_status=200)
            if time.monotonic()>=deadline:raise TimeoutError('official segment deadline exhausted')
        records=_build(ticker,mapping,originals,today)
        if not all(is_segment_discovery_record(r,ticker,today=today)for r in records):raise ValueError('segment saved receipt invalid')
        if time.monotonic()>=deadline:raise TimeoutError('official segment revalidation deadline exhausted')
        cached=all(c.get('cache_hit') is True for c in http.components)
        audit.update(status='skipped_fresh_cache' if cached and records else 'success' if records else 'unavailable',
            record_count=len(records),usable_count=len(records),cache_hit=cached,http_request_sent=bool(http.http_request_count),
            event_kind='cache_hit' if cached else 'aggregate',fetched_at_epoch=originals['segment']['retrieved_at'],
            coverage_status='observed_segment_candidate_subset',source_url=p['segment_url'],
            original_receipts=originals,component_statuses={'issuer':http.components[0],'segment':http.components[1]},
            message='取得官方細分產業鏈候選；未標成員生效日，整體業務與財期可比性未驗證。')
        return {'records':records,'audit':audit}
    except Exception as exc:
        audit.update(status='error',error_kind=getattr(exc,'error_kind',type(exc).__name__),
            http_request_sent=bool(http.http_request_count),component_statuses={'attempts':http.components},
            message='未取得可重驗的官方細分產業链候選。')
        return {'records':[],'audit':audit}
    finally:audit['duration_ms']=max(0,round((time.time()-started)*1000))
