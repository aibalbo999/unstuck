"""Dated medical-sector discovery for one current, officially anchored TDR.

Publisher membership supplies leads. Fine industry and numeric availability
remain the existing peer pipeline's responsibility; whole-business comparisons
and automatic valuation stay unverified.
"""
from datetime import date,datetime
from hashlib import sha256
import json,re,time,math
from copy import deepcopy
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from .issuer_news_transport import IssuerNewsHttp,ROSTER_URL
from .official_company_legal_name import parse_roster,select_legal_name
from .moneydj_peer_cohort import _current_identity,_today
from .peer_recovery import NON_EQUITY_CATEGORIES,current_master_industry_categories
from official_response_evidence import archive_response,read_response
from source_observation_freshness import parse_observation_date

TARGET='9103.TW'
SHORT='美德醫療-DR'
LEGAL='美德向邦醫療國際股份有限公司'
URL='https://m.moneydj.com/z/zh/zha/zh00.djhtm?A=C017137&B=5'
TITLE='同業股價表現-生技醫療保健-其他醫療器材-台股-MoneyDJ理財網'
POLICY='moneydj-current-other-medical-cohort-v1'
SCOPE='publisher_other_medical_candidates'
PROVIDER='MoneyDJ/TWSE published medical cohort'
DISCOVERY_TYPE='published_medical_industry_peer_cohort'
LINK=re.compile(r"javascript:Link2Stk\('AS([1-9][0-9]{3})'\);\Z")
LABEL=re.compile(r'([1-9][0-9]{3})(.+)\Z')

class MedicalCohortHttp(IssuerNewsHttp):
    @staticmethod
    def route_contract(url):
        if url==ROSTER_URL:return 2_500_000,{'application/json','text/json'}
        if url==URL:return 200_000,{'text/html','application/xhtml+xml'}
        raise ValueError('Unknown medical cohort URL')

def _context_valid(ticker,identity):
    return (ticker==TARGET and isinstance(identity,dict)
            and identity.get('ticker')==TARGET and identity.get('stock_id')=='9103'
            and identity.get('official_name')==SHORT and identity.get('instrument_type')=='EQUITY'
            and identity.get('legal_name') in (None,LEGAL))

def _anchor(raw,*,today,fetched_at_epoch):
    anchor=select_legal_name(parse_roster(raw,'.TW'),TARGET,SHORT,today=today)
    rows=[r for r in json.loads(raw) if str(r.get('公司代號'))=='9103']
    if not anchor or anchor['legal_name']!=LEGAL or len(rows)!=1:
        raise ValueError('Current TDR issuer not verified')
    row=rows[0]
    if (str(row.get('英文簡稱')or'').strip()!='MEDTECS'
            or str(row.get('網址')or'').strip() not in {'www.medtecs.com','https://www.medtecs.com'}
            or not str(row.get('外國企業註冊地國')or'').strip().startswith('BM ')):
        raise ValueError('Current TDR issuer profile mismatch')
    return {**anchor,'fetched_at_epoch':fetched_at_epoch}

def parse_medical_cohort(raw,master_rows,anchor,*,today):
    if not isinstance(raw,bytes) or not 0<len(raw)<=200_000:
        raise ValueError('Medical cohort response size invalid')
    soup=BeautifulSoup(raw.decode('big5'),'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True)!=TITLE:
        raise ValueError('Medical cohort title changed')
    tables=soup.find_all('table',id='oMainTable')
    if len(tables)!=1:raise ValueError('Medical cohort table missing or ambiguous')
    parsed={}
    for tr in tables[0].find_all('tr'):
        links=[a for a in tr.find_all('a',href=True) if LINK.fullmatch(a['href'])]
        if not links:continue
        if len(links)!=1:raise ValueError('Medical cohort row ambiguous')
        link=links[0];code=LINK.fullmatch(link['href'])[1];label=LABEL.fullmatch(link.get_text(' ',strip=True))
        dates=re.findall(r'20[0-9]{2}/[0-9]{2}/[0-9]{2}',tr.get_text(' ',strip=True))
        if not label or label[1]!=code or len(dates)!=1 or code in parsed:
            raise ValueError('Medical cohort identity or date ambiguous')
        stamp=date.fromisoformat(dates[0].replace('/','-'))
        if not 0<=(today-stamp).days<=7:raise ValueError('Medical cohort date stale or future')
        parsed[code]=(label[2].strip(),stamp)
    if len(parsed)>64 or parsed.get('9103',(None,))[0]!=SHORT:
        raise ValueError('TDR absent or wrong issuer in medical cohort')
    records=[];rejected=[]
    for code in sorted(parsed):
        if code=='9103':continue
        name,stamp=parsed[code];current=_current_identity(code,master_rows,today)
        if not current:
            rejected.append({'stock_id':code,'reason':'current_master_identity_unavailable'});continue
        if current[0]!=name:raise ValueError('Medical cohort and current master names differ')
        symbol=code+('.TW' if current[1]=='twse' else '.TWO')
        categories=current_master_industry_categories(symbol,master_rows,today=today)
        if not categories or set(categories)&NON_EQUITY_CATEGORIES:
            rejected.append({'stock_id':code,'reason':'not_current_ordinary_equity'});continue
        master_day=max(day for row in master_rows if str(row.get('stock_id'))==code
                       if (day:=parse_observation_date(row.get('date'))) is not None and 0<=(today-day).days<=7)
        records.append({'name':name,'ticker':symbol,'identity_status':'current_master_and_dated_publisher_cohort',
            'comparison_status':'industry_candidate_only','comparison_scope':SCOPE,
            'business_comparability_verified_current':False,
            'relationship_basis':'current_official_target_and_dated_publisher_cohort',
            'comparison_limitations':['publisher_classification_only','whole_company_business_mix_not_verified','financial_period_comparability_not_verified'],
            'cohort_source_url':URL,'cohort_response_sha256':sha256(raw).hexdigest(),
            'cohort_observed_at':stamp.isoformat(),'issuer_cohort_observed_at':parsed['9103'][1].isoformat(),
            'issuer_official_anchor':dict(anchor),'master_observed_at':master_day.isoformat(),
            'industry_categories':categories})
    return records[:10],{'raw_candidate_count':len(parsed)-1,'eligible_candidate_count':len(records),
                        'excluded_candidate_rows':rejected,'publisher_classification_is_not_business_comparability':True}

def get_medical_cohort_candidates(ticker,identity,master_rows,*,today):
    if not _context_valid(ticker,identity):return {'candidates':[],'status':'not_applicable'}
    started=time.time();deadline=time.monotonic()+12;http=MedicalCohortHttp(deadline)
    details={'policy':POLICY,'source_url':URL,'components':http.components,'transport_attempts':0,'original_receipts':{}}
    def original(url):
        raw=http.get(url);component=http.components[-1]
        component.update(response_sha256=sha256(raw).hexdigest(),response_bytes=len(raw))
        receipt=archive_response(raw,source_url=url,retrieved_at=component['fetched_at_epoch'],http_status=200)
        component['original_archive_status']=receipt.get('status')
        if receipt.get('status')!='archived':raise ValueError('Medical cohort original not archived')
        details['original_receipts']['issuer' if url==ROSTER_URL else 'publisher']=receipt
        return raw
    try:
        roster=original(ROSTER_URL);anchor=_anchor(roster,today=today,fetched_at_epoch=http.components[-1]['fetched_at_epoch'])
        http.components[-1]['status']='identity_verified'
        raw=original(URL);records,audit=parse_medical_cohort(raw,master_rows,anchor,today=today)
        publisher_acquired=datetime.fromtimestamp(http.components[1]['fetched_at_epoch'],ZoneInfo('Asia/Taipei')).date()
        issuer_acquired=datetime.fromtimestamp(http.components[0]['fetched_at_epoch'],ZoneInfo('Asia/Taipei')).date()
        if (issuer_acquired<date.fromisoformat(anchor['as_of']) or issuer_acquired>today
                or publisher_acquired>today
                or any(publisher_acquired<date.fromisoformat(r[k]) for r in records
                       for k in ('cohort_observed_at','issuer_cohort_observed_at'))):
            raise ValueError('Medical original acquired before its observed date')
        if time.monotonic()>=deadline:raise TimeoutError('Medical cohort deadline exhausted')
        http.components[-1]['status']='cohort_validated'
        for record in records:record.update(cohort_acquired_at_epoch=http.components[1]['fetched_at_epoch'],cohort_cache_hit=bool(http.components[1].get('cache_hit')))
        details.update(audit,response_sha256=sha256(raw).hexdigest(),issuer_official_anchor=anchor)
        result={'candidates':records,'status':'success' if records else 'no_current_ordinary_candidates','details':details}
    except (ValueError,TypeError,KeyError,RuntimeError,TimeoutError,OverflowError) as exc:
        details.update(error_kind=getattr(exc,'error_kind',type(exc).__name__))
        result={'candidates':[],'status':'unavailable','details':details}
    finally:details['transport_attempts']=http.http_request_count
    result['source_audit']=medical_cohort_source_audit(result,started_at_epoch=started)
    return result


def medical_cohort_source_audit(result,*,started_at_epoch):
    """One candidate operation, with both prerequisite receipts preserved.

    Identity rows are not numeric peers. A warm original page keeps its own
    acquisition epoch even when the prerequisite issuer profile is cold.
    """
    from source_audit import build_source_audit_entry
    details=result['details'];components=details['components'];rows=result['candidates']
    sent=any(c.get('http_request_sent') is True for c in components)
    cached=bool(components) and all(c.get('cache_hit') is True for c in components)
    status=('error' if details.get('error_kind') else
            'skipped_fresh_cache' if cached and rows else 'success' if rows else 'unavailable')
    stamp=components[-1].get('fetched_at_epoch') if components else None
    audit=build_source_audit_entry('peer_discovery',PROVIDER,status,
        fetched_at_epoch=stamp,started_at_epoch=started_at_epoch,finished_at_epoch=time.time(),
        record_count=len(rows),cache_hit=cached,stale=False,error_kind=details.get('error_kind',''),
        message='取得當期醫材研究候選；整體業務與財期可比性未驗證。' if rows else '未取得可核對的醫材研究候選。')
    observed={}
    for c in components:
        name='official_issuer_identity' if c['url']==ROSTER_URL else 'medical_candidate_cohort'
        observed[name]={k:c[k] for k in ('status','error_kind','fetched_at_epoch','cache_hit','response_sha256','response_bytes') if k in c}
        observed[name].update(status=c.get('status') or ('error' if c.get('error_kind') else 'not_completed'),
            provider='TWSE issuer identity' if c['url']==ROSTER_URL else 'MoneyDJ medical candidates',
            observation_status='http_request' if c.get('http_request_sent') is True else 'cache_hit' if c.get('cache_hit') is True else 'local_block')
    audit.update(selection_policy=POLICY,source_url=URL,fetched_at_epoch=stamp,
        response_sha256=details.get('response_sha256'),raw_count=details.get('raw_candidate_count',0),
        usable_count=len(rows),quality_status='candidate_relationship_only',component_statuses=observed,
        http_request_sent=sent,event_kind='http_request' if sent else 'cache_hit' if cached else 'local_block')
    return audit


def _discovery_record(candidate,originals):
    symbol=candidate['ticker'];code,market=symbol.split('.')
    master=[{'date':candidate['master_observed_at'],'stock_id':code,'stock_name':candidate['name'],
             'type':'twse' if market=='TW' else 'tpex','industry_category':category}
            for category in candidate['industry_categories']]
    return {'title':f"MoneyDJ 其他醫療器材同頁名單：{SHORT}、{candidate['name']}",
        'source':'MoneyDJ 理財網','source_type':DISCOVERY_TYPE,'link':URL,'selection_policy':POLICY,
        'relationship_kind':'publisher_listed_industry_candidate',
        'relationship_basis':'current_official_target_and_dated_publisher_cohort','industry_category':'其他醫療器材',
        'observed_at':candidate['cohort_observed_at'],'issuer_observed_at':candidate['issuer_cohort_observed_at'],
        'response_sha256':candidate['cohort_response_sha256'],
        'business_comparability_verified':False,'business_comparability_verified_current':False,
        'numeric_comparability_verified':False,
        'issuer':{'ticker':TARGET,'official_name':SHORT},
        'counterparty':{'ticker':symbol,'official_name':candidate['name']},
        'source_record_archive':[{'reason':'accepted_medical_publisher_originals',
            'medical_originals':deepcopy(originals),'counterparty_master':master}]}


def medical_discovery_records(result):
    """Project at most five acquired leads without creating numeric comparisons."""
    originals=result.get('details',{}).get('original_receipts',{})
    if set(originals)!={'issuer','publisher'}:return []
    return [_discovery_record(c,originals) for c in result.get('candidates',[])[:5]]


def _read_original(receipt,url,limit):
    stamp=receipt.get('retrieved_at');size=receipt.get('raw_response_bytes')
    if (receipt.get('status')!='archived' or receipt.get('source_url')!=url
            or receipt.get('evidence_kind')!='raw_http_response_bytes'
            or type(receipt.get('http_status')) is not int or receipt['http_status']!=200
            or type(stamp) not in (int,float) or not math.isfinite(stamp) or not 0<stamp<=time.time()
            or type(size) is not int or not 0<size<=limit):
        raise ValueError('Medical original receipt invalid')
    raw=read_response(receipt)
    if len(raw)!=size:raise ValueError('Medical original size mismatch')
    return raw


def is_medical_peer_record(record,ticker,*,today=None):
    """Recheck both complete originals locally after snapshot serialization.

    Selected SDK master identity is recorded as such, not called a complete
    raw master response. Its market/name/date must still agree with the page.
    The source archive is excluded by the existing prompt evidence boundary.
    """
    if not isinstance(record,dict) or ticker!=TARGET:return False
    if any(record.get(k) is not False for k in ('business_comparability_verified',
            'business_comparability_verified_current','numeric_comparability_verified')):return False
    today=today or _today()
    try:
        archives=record['source_record_archive']
        if not isinstance(archives,list) or len(archives)!=1 or archives[0]['reason']!='accepted_medical_publisher_originals':return False
        originals=archives[0]['medical_originals']
        if set(originals)!={'issuer','publisher'}:return False
        issuer_raw=_read_original(originals['issuer'],ROSTER_URL,2_500_000)
        publisher_raw=_read_original(originals['publisher'],URL,200_000)
        anchor=_anchor(issuer_raw,today=today,fetched_at_epoch=originals['issuer']['retrieved_at'])
        issuer_acquired=datetime.fromtimestamp(originals['issuer']['retrieved_at'],ZoneInfo('Asia/Taipei')).date()
        if issuer_acquired<date.fromisoformat(anchor['as_of']) or issuer_acquired>today:return False
        candidates,_=parse_medical_cohort(publisher_raw,archives[0]['counterparty_master'],anchor,today=today)
        for candidate in candidates:
            if candidate['ticker']!=record.get('counterparty',{}).get('ticker'):continue
            observed=max(date.fromisoformat(candidate[k]) for k in ('cohort_observed_at','issuer_cohort_observed_at'))
            acquired=datetime.fromtimestamp(originals['publisher']['retrieved_at'],ZoneInfo('Asia/Taipei')).date()
            if acquired<observed or acquired>today:return False
            expected=_discovery_record(candidate,originals)
            return all(record.get(k)==v for k,v in expected.items() if k!='source_record_archive')
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,OSError,EOFError,OverflowError):
        return False
    return False


def medical_record_hint(record):
    if not isinstance(record,dict):return False
    archive=record.get('source_record_archive')
    return (record.get('source_type')==DISCOVERY_TYPE or record.get('selection_policy')==POLICY
            or isinstance(archive,list) and any(isinstance(r,dict) and r.get('reason')=='accepted_medical_publisher_originals'
                                               for r in archive))
