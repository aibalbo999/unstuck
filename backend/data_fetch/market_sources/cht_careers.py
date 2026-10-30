"""Exact-employer public CHT career samples, preserving application-period scope.

A batch's application window is not an individual posting's first publication.
The verified sample is neither hiring headcount nor a whole-site job total.
"""
from datetime import datetime
import re
import unicodedata
from urllib.parse import urlsplit,parse_qs,urlencode,urljoin
from zoneinfo import ZoneInfo
from hashlib import sha256
from bs4 import BeautifulSoup

TICKER='2412.TW'
LEGAL='中華電信股份有限公司'
SHORT='中華電'
UBN='96979933'
PROVIDER='CHT official public careers'
INDEX_URL='https://www.cht.com.tw/zh-tw/home/cht/recruit-and-training/recruit/portal-careerjob'
LIST_URL='https://rmis.cht.com.tw/portal/jobs/joblist.jsp'
MAX_BYTES=500000
MAX_POSTINGS=3
TZ=ZoneInfo('Asia/Taipei')
_DATE=r'20\d{2}/\d{2}/\d{2} \d{2}:\d{2}'


def norm(value):
    return ' '.join(unicodedata.normalize('NFKC',str(value)).split())


def compact(value):
    return re.sub(r'\s','',norm(value))


def _soup(raw,encoding):
    if not isinstance(raw,bytes)or not 0<len(raw)<=MAX_BYTES:raise ValueError('career_body_size')
    return BeautifulSoup(raw.decode(encoding,errors='strict'),'html.parser')


def _one(nodes):
    if len(nodes)!=1:raise ValueError('career_structure_ambiguous')
    return nodes[0]


def canonical_detail_url(value):
    if not isinstance(value,str)or len(value)>300:raise ValueError('career_url_invalid')
    p=urlsplit(urljoin(LIST_URL,value))
    if p.scheme!='https'or p.netloc!='rmis.cht.com.tw'or p.path!='/portal/jobs/jobdetail.jsp'or p.fragment:
        raise ValueError('career_detail_host_or_path')
    try:q=parse_qs(p.query,keep_blank_values=True,strict_parsing=True)
    except ValueError as exc:raise ValueError('career_detail_query')from exc
    if set(q)!={'idno','verno'}or any(len(v)!=1 for v in q.values()):raise ValueError('career_detail_query')
    ident,version=q['idno'][0],q['verno'][0]
    if not re.fullmatch(r'[A-Z]{1,4}[0-9]{2,4}',ident)or not re.fullmatch(r'[0-9]{5}',version):
        raise ValueError('career_detail_identity')
    return 'https://rmis.cht.com.tw/portal/jobs/jobdetail.jsp?'+urlencode({'idno':ident,'verno':version})


def _apply(value,ident,version):
    p=urlsplit(urljoin(LIST_URL,value))
    if p.scheme!='https'or p.netloc!='rmis.cht.com.tw'or p.path!='/portal/jobs/login.jsp'or p.fragment:
        raise ValueError('career_application_identity')
    q=parse_qs(p.query,keep_blank_values=True,strict_parsing=True)
    if q!={'verno':[version],'dutyno':[ident]}:raise ValueError('career_application_identity')


def _copyright(soup):
    expected=compact(LEGAL+'版權所有 Chunghwa Telecom Co., Ltd. All Rights Reserved')
    if len([n for n in soup.select('span')if compact(n.get_text(' ',strip=True))==expected])!=1:
        raise ValueError('career_employer_copyright')


def _period(text,label,separator):
    m=re.fullmatch(re.escape(label)+r'[:：]\s*(?P<start>'+_DATE+r')\s*'+separator+r'\s*(?P<end>'+_DATE+r')',norm(text))
    if not m:raise ValueError('career_application_period')
    return tuple(datetime.strptime(m[k],'%Y/%m/%d %H:%M').replace(tzinfo=TZ)for k in ['start','end'])


def parse_index(raw,*,now):
    soup=_soup(raw,'utf-8')
    if not soup.title or norm(soup.title.get_text())!='所有職缺 | 中華電信 CHT.com.tw':raise ValueError('career_index_identity')
    active=[]
    for card in soup.select('[data-recruit-details]'):
        fields=[norm(n.get_text(' ',strip=True))for n in card.select('.card-content .row > .col')]
        if '用人機構:'+LEGAL not in [compact(x)for x in fields]or '狀態:報名中'not in [compact(x)for x in fields]:continue
        title=norm(_one(card.select('.card-title')).get_text(' ',strip=True))
        m=re.fullmatch(r'中華電信公司(?P<roc>[0-9]{3})年第(?P<serial>[0-9]{1,3})次從業人員\(具工作經驗\)遴選簡章',title)
        if not m:raise ValueError('career_batch_title')
        dates=[x for x in fields if x.startswith('徵才日期')]
        start,end=_period(_one(dates),'徵才日期','-')
        if not start.timestamp()<=now<end.timestamp()or not 0<=now-start.timestamp()<=30*86400:
            continue
        if int(m['roc'])+1911!=start.year or end<=start:raise ValueError('career_batch_year')
        documents=[]
        for button in card.select('.card-content button[onclick]'):
            v=re.fullmatch(r"openLink\('(/home/cht/-/media/web/pdf/recruit-and-training/recruit/(?P<year>[0-9]{4})/(?P<roc>[0-9]{3})(?P<serial>[0-9]{1,3})\.pdf\?sc_lang=zh-tw)',\s*'_blank'\)",button.get('onclick',''))
            if v:documents.append(v)
        doc=_one(documents)
        if int(doc['year'])!=start.year or doc['roc']!=m['roc']or int(doc['serial'])!=int(m['serial']):raise ValueError('career_document_batch_mismatch')
        active.append({'title':title,'roc':m['roc'],'serial':int(m['serial']),'batch_id':doc['roc']+doc['serial'],
                       'application_start':start.isoformat(),'application_end':end.isoformat(),
                       'document_url':'https://www.cht.com.tw'+doc[1]})
    return _one(active)


def parse_listing(raw,batch):
    soup=_soup(raw,'cp950');_copyright(soup)
    if not soup.title or norm(soup.title.get_text())!='中華電信 人才招募網':raise ValueError('career_listing_identity')
    expected=f"{batch['roc']}年第{batch['serial']}次從業人員(具工作經驗)遴選"
    if compact(_one(soup.select('h6')).get_text(' ',strip=True))!=compact(expected):raise ValueError('career_listing_batch')
    period=_period(_one(soup.select('.cht-col-date span')).get_text(' ',strip=True),'徵才時間',r'[~∼]')
    if tuple(x.isoformat()for x in period)!=(batch['application_start'],batch['application_end']):raise ValueError('career_listing_period_mismatch')
    rows=soup.select('.card.cht-Bjob-jobcard')
    if not 1<=len(rows)<=100:raise ValueError('career_listing_size')
    jobs=[];seen=set();start=datetime.fromisoformat(batch['application_start']);version=batch['roc']+f'{start.month:02d}'
    for row in rows:
        code=re.fullmatch(r'代碼:([A-Z]{1,4}[0-9]{2,4})',compact(_one(row.select('.cht-jobcard-code')).get_text(' ',strip=True)))
        if not code:raise ValueError('career_listing_job_code')
        ident=code[1];title=norm(_one(row.select('h5')).get_text(' ',strip=True))
        if not 1<=len(title)<=200 or ident in seen:raise ValueError('career_listing_job_ambiguous')
        seen.add(ident);url=canonical_detail_url(_one(row.select('a.cht-jobcard-action-detail')).get('href'))
        q=parse_qs(urlsplit(url).query)
        if q!={'idno':[ident],'verno':[version]}:raise ValueError('career_listing_detail_binding')
        _apply(_one(row.select('a.cht-jobcard-action-apply')).get('href'),ident,version)
        jobs.append({'job_id':ident,'title':title,'url':url,'version':version})
    return jobs[:MAX_POSTINGS]


def parse_detail(raw,job,batch):
    soup=_soup(raw,'cp950');_copyright(soup)
    if canonical_detail_url(job['url'])!=job['url']:raise ValueError('career_detail_url_noncanonical')
    if norm(_one(soup.select('h2')).get_text(' ',strip=True))!=job['title']:raise ValueError('career_detail_title_mismatch')
    if compact(_one(soup.select('.cht-jobcard-code')).get_text(' ',strip=True))!='代碼:'+job['job_id']:raise ValueError('career_detail_job_mismatch')
    _apply(_one(soup.select('a#idBtnJobApply')).get('href'),job['job_id'],job['version'])
    body=norm(_one(soup.select('.cht-job-detail-row[name="工作內容"] .cht-article-col')).get_text(' ',strip=True))
    if not 20<=len(body)<=20000:raise ValueError('career_detail_description_unavailable')
    return {**job,'employer':LEGAL,'batch_id':batch['batch_id'],'application_start':batch['application_start'],
            'application_end':batch['application_end'],'first_publication_verified':False,
            'description_character_count':len(body),'description_sha256':sha256(body.encode()).hexdigest()}


def assemble(index_raw,listing_raw,detail_bodies,*,now):
    batch=parse_index(index_raw,now=now);jobs=parse_listing(listing_raw,batch)
    if not isinstance(detail_bodies,dict)or set(detail_bodies)!={j['url']for j in jobs}:raise ValueError('career_detail_set_incomplete')
    parsed=[parse_detail(detail_bodies[j['url']],j,batch)for j in jobs]
    return {'status':'success','source':PROVIDER,'source_url':INDEX_URL,'ticker':TICKER,'company_name':LEGAL,
            'official_ubn':UBN,'evidence_kind':'official_company_job_postings','query_scope':'exact_company_current_open_postings',
            'coverage_status':'partial','batch_id':batch['batch_id'],'verified_sample_job_count':len(parsed),
            'current_open_job_count':None,'job_count':None,'job_postings':parsed,'first_publication_verified':False,
            'application_date_policy':'official_current_batch_window_not_first_publication',
            'message':'僅採官方本公司目前可報名批次的逐筆職缺樣本；日期為報名起訖，不是首次刊登日期，不代表招聘人數或全站職缺總數。'}


def valid_context(data):
    if not isinstance(data,dict):return False
    identity=data.get('company_identity')
    if not isinstance(identity,dict):return False
    english=identity.get('english_names',[])
    if not isinstance(english,list)or any(not isinstance(v,str)for v in english):return False
    name=data.get('company_name')
    if not isinstance(name,str)or not name.strip():return False
    legal=identity.get('legal_name')
    if identity.get('official_name')!=SHORT or legal not in(None,'',LEGAL):return False
    names={SHORT,legal,*english}
    return (data.get('ticker')==TICKER and identity.get('ticker')==TICKER
        and identity.get('official_name')==SHORT and data.get('quote_type')=='EQUITY'
        and identity.get('instrument_type')=='EQUITY'
        and all(data.get(k)in(None,'','EQUITY')for k in('quoteType','instrument_type'))
        and all(v in(None,'','2412')for v in(identity.get('stock_id'),data.get('stock_id')))
        and identity.get('official_ubn')in(None,'',UBN)and identity.get('legal_name')in(None,'',LEGAL)
        and all(part.strip() and part.strip()in names for part in name.split(' / ')))


def verified_issuer(receipt,ticker,short_name,*,now=None):
    import time,math,json
    from runtime_paths import current_runtime_paths
    from official_response_evidence import read_response
    from .official_company_legal_name import (verified_legal_name_from_evidence,
        verified_official_ubn_from_evidence,parse_roster,select_legal_name,MAX_BYTES as MASTER_MAX)
    now=time.time()if now is None else now
    try:
        stamp=receipt.get('fetched_at_epoch')if isinstance(receipt,dict)else None
        if not(ticker==TICKER and short_name==SHORT and type(stamp)in(int,float)and math.isfinite(stamp)
                and 0<=now-stamp<86400
                and verified_legal_name_from_evidence(receipt,ticker,short_name)==LEGAL
                and verified_official_ubn_from_evidence(receipt,ticker,short_name)==UBN):return False
        digest=receipt['response_sha256']
        raw=read_response({'raw_response_sha256':digest,'raw_response_path':str(
            current_runtime_paths().cache_dir/'official-response-evidence'/(digest+'.gz'))},max_bytes=MASTER_MAX)
        def pairs(items):
            value={}
            for key,item in items:
                if key in value:raise ValueError('duplicate issuer field')
                value[key]=item
            return value
        rows=json.loads(raw,object_pairs_hook=pairs)
        roster=parse_roster(raw,'.TW')
        if len(roster['entries'])<800:return False
        selected=select_legal_name(roster,TICKER,SHORT,today=datetime.fromtimestamp(now,TZ).date())
        if not selected or any(selected.get(k)!=receipt.get(k)for k in(
                'ticker','legal_name','official_short_name','as_of','official_ubn','source_url','response_sha256')):return False
        row=_one([r for r in rows if str(r.get('公司代號'))=='2412'])
        website=str(row.get('網址')or'').strip()
        host=urlsplit(website if '://'in website else'https://'+website).hostname
        return host in{'cht.com.tw','www.cht.com.tw'}
    except (ValueError,TypeError,KeyError,OverflowError,OSError,UnicodeError,AttributeError,RecursionError):return False


def receipt_body(receipt,url,now):
    import math
    from official_response_evidence import read_response
    if (not isinstance(receipt,dict)or set(receipt)!={'schema','url','method','fetched_at_epoch','encoding','raw_receipt'}
            or receipt.get('schema')!='cht-careers-http.v1'or receipt.get('url')!=url or receipt.get('method')!='GET'
            or receipt.get('encoding')!=('utf-8'if url==INDEX_URL else'cp950')):
        raise ValueError('career_receipt_identity')
    stamp=receipt.get('fetched_at_epoch')
    if type(stamp)not in(int,float)or not math.isfinite(stamp)or not 0<=now-stamp<3600:
        raise ValueError('career_receipt_age')
    proof=receipt.get('raw_receipt')
    if (not isinstance(proof,dict)or proof.get('source_url')!=url or proof.get('http_status')!=200
            or proof.get('evidence_kind')!='raw_http_response_bytes'or proof.get('retrieved_at')!=stamp
            or proof.get('historical_point_in_time_verified')is not False or proof.get('finality_guaranteed')is not False):
        raise ValueError('career_original_identity')
    raw=read_response(proof)
    if not 0<len(raw)<=MAX_BYTES or proof.get('raw_response_bytes')!=len(raw):raise ValueError('career_original_size')
    if sha256(raw).hexdigest()!=proof.get('raw_response_sha256'):raise ValueError('career_original_hash')
    return raw


def parse_receipts(receipts,*,now):
    if not isinstance(receipts,list)or not 3<=len(receipts)<=2+MAX_POSTINGS:raise ValueError('career_receipt_count')
    index_raw=receipt_body(receipts[0],INDEX_URL,now);listing_raw=receipt_body(receipts[1],LIST_URL,now)
    batch=parse_index(index_raw,now=now);jobs=parse_listing(listing_raw,batch)
    if len(receipts)!=2+len(jobs):raise ValueError('career_receipt_count')
    bodies={j['url']:receipt_body(p,j['url'],now)for j,p in zip(jobs,receipts[2:])}
    oldest=min(p['fetched_at_epoch']for p in receipts)
    # A later read cannot admit a batch that was still future at acquisition.
    assemble(index_raw,listing_raw,bodies,now=oldest)
    value=assemble(index_raw,listing_raw,bodies,now=now)
    value.update(fetched_at_epoch=oldest,
                 response_sha256=sha256('|'.join(p['raw_receipt']['raw_response_sha256']for p in receipts).encode()).hexdigest(),
                 source_record_archive={'schema':'cht-careers.v1','receipts':receipts})
    return value


def verified_job_count(value,ticker,legal_name,ubn,issuer_evidence,*,now=None):
    import time,json
    now=time.time()if now is None else now
    if ticker!=TICKER or legal_name!=LEGAL or ubn!=UBN or not verified_issuer(issuer_evidence,ticker,SHORT,now=now):return 0
    try:
        archive=value['source_record_archive']
        if set(archive)!={'schema','receipts'}or archive['schema']!='cht-careers.v1':return 0
        expected=parse_receipts(archive['receipts'],now=now)
        if set(value)!=set(expected):return 0
        if json.dumps(value,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):return 0
        return expected['verified_sample_job_count']
    except (ValueError,TypeError,KeyError,OverflowError,OSError,UnicodeError,RecursionError):return 0
