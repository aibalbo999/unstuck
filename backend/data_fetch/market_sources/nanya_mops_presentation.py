"""Regulated Nanya prepared originals, separate from meeting/transcript claims."""
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json,math,re,time
from uuid import uuid4

from official_response_evidence import archive_response,read_response
from search_admission import endpoint_admission
from search_provider_runtime import SourceResponseError,cooldown_state,remember_failure,remember_success,record_observation,scope_key
from shared_provider_cache import shared_fetch
from source_pdf_reader import SourcePdfError,extract_pdf_pages
from .official_company_legal_name import read_cached_listed_roster_bytes,parse_roster,select_legal_name
from .nanya_mops_transport import PROVIDER,presentation_url,download

POLICY='nanya-regulated-prepared-original-v1'
ROSTER_URL='https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
INDEX_URL='https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1'
GUARD=scope_key('MOPS',endpoint='mopsov_investor_conference')
PALETTE='R 0\nG 182\nB 214\nR 206\nG 89\nB 132\nR 140\nG 211\nB 231\nR 222\nG 239\nB 247\nR 206\nG 219\nB 41\nR 247\nG 177\nB 37\nR 0\nG 113\nB 198\nR 0\nG 32\nB 99\n'
# Two exact prefix orders occur in the complete original. This is not a
# blanket RGB-line filter; any different prefix remains unqualified.
PALETTES=(PALETTE,'R 0\nG 113\nB 198\n'+PALETTE[:PALETTE.index('R 0\nG 113\nB 198\n')]+'R 0\nG 32\nB 99\n')
NOTE='公開資訊觀測站發布的南亞科準備簡報；活動日期、檔案日期與內容季度分開。不是逐字稿或已完成會議證明，圖像、表格閱讀順序及各項陳述未獨立驗證；原生RGB色碼是版面資訊，不是財務數值。'
AGGREGATE_MESSAGE='optional 外部來源 MOPS 年度資訊與已發布簡報彙總；各次實際請求另列觀測。'


def supports_nanya(ticker):return str(ticker).strip().upper()in {'2408','2408.TW'}


def _freshness():
    from config import SOURCE_FRESHNESS_MAX_AGE_SECONDS
    return max(1,min(86400,int(SOURCE_FRESHNESS_MAX_AGE_SECONDS.get('earnings_call',86400))))


def _stamp(receipt):
    value=receipt.get('retrieved_at')
    if type(value)not in (int,float)or not math.isfinite(value)or not 0<value<=time.time():raise ValueError('Original timestamp invalid')
    if time.time()-value>=_freshness():raise ValueError('Original expired')
    return value


def _saved(receipt,url,*,identity=False):
    if not isinstance(receipt,dict)or receipt.get('status')!='archived'or receipt.get('source_url')!=url or receipt.get('http_status')!=(None if identity else 200):raise ValueError('Original receipt invalid')
    _stamp(receipt);raw=read_response(receipt)
    limit=2_500_000 if identity or url==INDEX_URL else 8*1024*1024
    if type(receipt.get('raw_response_bytes'))is not int or not 0<len(raw)<=limit or len(raw)!=receipt['raw_response_bytes']:raise ValueError('Original length invalid')
    return raw


def _anchor(raw):
    from official_financials_mops_conference import datetime,ZoneInfo
    today=datetime.now(ZoneInfo('Asia/Taipei')).date()
    anchor=select_legal_name(parse_roster(raw,'.TW'),'2408.TW','南亞科',today=today)
    rows=[r for r in json.loads(raw)if r.get('公司代號')=='2408']
    if not anchor or anchor.get('legal_name')!='南亞科技股份有限公司'or anchor.get('official_ubn')!='89390656'or len(rows)!=1 or rows[0].get('網址')not in {'https://www.nanya.com','https://www.nanya.com/','www.nanya.com'}:raise ValueError('Issuer anchor differs')


def _metadata(event):
    from data_fetch.earnings_call_fetcher import FREE_EARNINGS_CALL_COVERAGE_NOTE
    return {'ticker':'2408','date':event['date'],'period':event['date'],'title':event['title'],
            'summary':event['summary'].strip()or FREE_EARNINGS_CALL_COVERAGE_NOTE,'transcript_excerpt':'','transcript_available':False,
            'materials':event['materials'],'source':'MOPS investor conference','source_url':INDEX_URL,
            'coverage_notes':[FREE_EARNINGS_CALL_COVERAGE_NOTE]}


def _selection(index,metadata):
    from official_financials_mops_conference import parse_conference_response
    events=parse_conference_response(_saved(index,INDEX_URL).decode('utf-8'),'2408',http_status=200)
    if not events or metadata!=_metadata(events[0]):raise ValueError('Latest native event differs')
    urls=[r['url']for r in events[0]['materials']if presentation_url(r.get('url'))]
    if not urls:return None
    if len(urls)!=1:raise ValueError('English original ambiguous')
    filename=urls[0].split('/')[-1]
    file_date=date(int(filename[4:8]),int(filename[8:10]),int(filename[10:12]))
    if file_date.isoformat()>events[0]['date']:raise ValueError('Future material date')
    return {'url':urls[0],'event_date':events[0]['date'],'material_file_date':file_date.isoformat()}


def _native(raw,selected,deadline):
    remaining=min(10.,deadline-time.monotonic())
    if remaining<=0:raise SourceResponseError('timeout')
    native=extract_pdf_pages(raw,timeout_seconds=remaining)
    if native['coverage_status']!='complete' or not native['pages'] or any(not p['text'].startswith(PALETTES)or 'Nanya Technology Corporation'not in p['text']for p in native['pages']):raise ValueError('Native prepared content or issuer not verified')
    cover=native['pages'][0]['text'][len(PALETTE):]
    match=re.findall(r'\bQ([1-4])\s+(20[0-9]{2})\b',cover)
    if len(match)!=1 or 'Investor Conference'not in cover:raise ValueError('Prepared period absent')
    quarter,year=map(int,match[0]);end=date(year,quarter*3,(31 if quarter in (1,4)else 30))
    if end>date.fromisoformat(selected['material_file_date']):raise ValueError('Prepared quarter after file date')
    native['content_period']=f'Q{quarter} {year}'
    return native


def _context(metadata,selected,native,proof):
    result=deepcopy(metadata);pdf=proof['pdf'];stamp=_stamp(pdf)
    doc={'document_id':'2408:'+selected['material_file_date']+':'+native['content_sha256'][:16],
         'ticker':'2408.TW','title':native['content_period']+' prepared presentation','source':PROVIDER,'url':selected['url'],
         'source_type':'regulated_issuer_presentation','document_kind':'presentation','event_date':selected['event_date'],
         'material_file_date':selected['material_file_date'],'content_period':native['content_period'],'published_at':None,
         'retrieved_at_epoch':stamp,'content_sha256':native['content_sha256'],'binary_complete':True,
         'page_count':native['page_count'],'pages':native['pages'],'missing_text_pages':native['empty_pages'],
         'garbled_pages':native['garbled_pages'],'native_text_coverage':'complete','text_extraction_complete':True,
         'coverage_status':'partial','full_content_coverage_verified':False,'parser_version':native['parser_version'],
         'projection_policy':'nanya-prepared-role-v1'}
    result.update(ticker='2408.TW',source=PROVIDER,documents=[doc],coverage_status='partial',coverage_notes=[NOTE],
                  fetched_at_epoch=min(_stamp(proof['index']),stamp),nanya_mops_receipt=proof)
    return result


def is_marked(value,ticker):
    if not isinstance(value,dict):return False
    documents=value.get('documents');documents=documents if isinstance(documents,list)else[]
    return (value.get('source')==PROVIDER or 'nanya_mops_receipt'in value
            or any(isinstance(doc,dict)and (doc.get('source')==PROVIDER
                   or doc.get('projection_policy')=='nanya-prepared-role-v1'
                   or presentation_url(doc.get('url')))for doc in documents)
            or supports_nanya(ticker)and bool(documents))


def verify_context(value,ticker,*,deadline=None):
    try:
        if not supports_nanya(ticker)or not is_marked(value,ticker)or value.get('ticker')!='2408.TW':return False
        proof=value['nanya_mops_receipt']
        if proof.get('policy')!=POLICY:return False
        _anchor(_saved(proof['identity'],ROSTER_URL,identity=True))
        selected=_selection(proof['index'],proof['metadata'])
        if not selected or selected!=proof['selected']:return False
        native=_native(_saved(proof['pdf'],selected['url']),selected,deadline or time.monotonic()+10.)
        expected=_context(proof['metadata'],selected,native,proof)
        return all(value.get(k)==v for k,v in expected.items())
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,OSError,EOFError,UnicodeError,SourceResponseError,SourcePdfError):return False


def _original_key(url):
    if not presentation_url(url):raise ValueError('Original URL not admitted')
    return 'nanya_mops_original:v1:'+sha256(url.encode()).hexdigest()


def _retain_original(receipt):
    """Retain a qualified body separately from transient HTTP error state."""
    from cache_store import set_cache_json
    stamp=_stamp(receipt);remaining=math.floor(stamp+_freshness()-time.time())
    if remaining<1:raise ValueError('Original expires before retention')
    row={'policy':POLICY,'pdf':deepcopy(receipt)}
    key=_original_key(receipt['source_url']);set_cache_json(key,row,ttl_seconds=remaining)
    return key,row


def retain_qualified_original(value,*,deadline=None):
    """Explicitly adopt an already archived, fully verified original; no HTTP.

    This does not create an acquisition success, reset an error/cooldown, or
    change the source epoch. Production never reads research/docs files.
    """
    from cache_store import get_cache_json
    deadline=deadline if deadline is not None else time.monotonic()+20.
    with endpoint_admission(GUARD,timeout_seconds=max(.01,min(20.,deadline-time.monotonic())))as owns:
        if not owns:raise SourceResponseError('single_flight_busy')
        if not owns():raise SourceResponseError('lease_lost')
        if time.monotonic()>=deadline:raise SourceResponseError('timeout')
        if not verify_context(value,'2408.TW',deadline=deadline):raise ValueError('Prepared original not qualified')
        if time.monotonic()>=deadline:raise SourceResponseError('timeout')
        if not owns():raise SourceResponseError('lease_lost')
        key,row=_retain_original(value['nanya_mops_receipt']['pdf'])
        if get_cache_json(key)!=row:raise ValueError('Retained original readback differs')
        if time.monotonic()>=deadline:raise SourceResponseError('timeout')
        if not owns():raise SourceResponseError('lease_lost')
        return {'cache_key':key,'original_receipt':row['pdf'],'new_HTTP_or_acquisition_successes':0}


def _retained_original(selected):
    from cache_store import get_cache_json
    try:row=get_cache_json(_original_key(selected['url']))
    except Exception:return None  # Optional cache availability cannot add an outage.
    if row is None:return None
    if not isinstance(row,dict)or row.get('policy')!=POLICY:raise ValueError('Retained original policy differs')
    receipt=row.get('pdf');_saved(receipt,selected['url'])
    return {'pdf':receipt,'diagnostic':{'actual_provider':PROVIDER,'source_url':selected['url'],
            'http_status':200,'http_request_sent':False,'http_request_count':0,'cache_hit':True,
            'event_kind':'cache_hit','endpoint':'prepared_pdf','parser_version':POLICY,
            'original_receipt':receipt,'record_count':1,'fetched_at_epoch':receipt['retrieved_at'],
            'coverage_status':'native_text_complete','original_reused':True}}


def enrich_nanya_context(ticker,metadata,*,diagnostics,deadline):
    if not supports_nanya(ticker)or metadata.get('source')!='MOPS investor conference':return metadata
    years=diagnostics.get('mops_year_observations')or[]
    if not years or not isinstance(years[-1].get('raw_http_receipt'),dict):return metadata
    diagnostics.update(nanya_presentation_workflow=True,message=AGGREGATE_MESSAGE)
    components=dict(diagnostics.get('component_statuses')or{})
    captured={}
    try:
        if time.monotonic()>=deadline:raise SourceResponseError('timeout')
        index=years[-1]['raw_http_receipt'];selected=_selection(index,metadata)
        if selected is None:return metadata
        master=read_cached_listed_roster_bytes()
        if master is None:raise SourceResponseError('identity_anchor_unavailable')
        raw,meta=master;_anchor(raw)
        identity=archive_response(raw,source_url=ROSTER_URL,retrieved_at=meta['fetched_at_epoch'],http_status=None,evidence_kind='cached_complete_source_payload_verified_by_digest')
        _saved(identity,ROSTER_URL,identity=True)
        with endpoint_admission(GUARD,timeout_seconds=max(.01,min(20.,deadline-time.monotonic())))as owns:
            if not owns:raise SourceResponseError('single_flight_busy')
            if not owns():raise SourceResponseError('lease_lost')
            def acquire():
                started=time.monotonic();details={'actual_provider':PROVIDER,'source_url':selected['url'],'http_request_sent':False,'attempt_id':uuid4().hex,'endpoint':'prepared_pdf','parser_version':POLICY}
                try:
                    if time.monotonic()>=deadline:raise SourceResponseError('timeout')
                    if not owns():raise SourceResponseError('lease_lost')
                    retained=_retained_original(selected)
                    if retained is not None:return retained
                    blocked=cooldown_state(GUARD)
                    if blocked:raise SourceResponseError(blocked.get('error_kind')or'cooldown',status_code=blocked.get('http_status'))
                    request_started_at=time.time()
                    raw=download(selected['url'],deadline=deadline,diagnostics=details)
                    receipt=archive_response(raw,source_url=selected['url'],retrieved_at=time.time(),http_status=200)
                    details['original_receipt']=receipt;_native(_saved(receipt,selected['url']),selected,deadline)
                    if time.monotonic()>=deadline:raise SourceResponseError('timeout')
                    if not owns():raise SourceResponseError('lease_lost')
                    if details.get('http_request_sent')is True:
                        remember_success(GUARD,request_started_at=request_started_at)
                except Exception as original:
                    exc=original if isinstance(original,SourceResponseError)else SourceResponseError('timeout'if isinstance(original,SourcePdfError)and original.reason=='timeout'else'parse_error',status_code=details.get('http_status'))
                    if isinstance(original,SourcePdfError):details['pdf_error_kind']=original.reason
                    remote_failure=(isinstance(original,SourceResponseError)
                                    and (original.error_kind in {'authentication','payment_required','access_denied','rate_limited','server_error','http_error','transport_error'}
                                         or original.error_kind=='timeout'and details.get('response_complete')is not True))
                    if remote_failure and details.get('http_request_sent')and owns():details.update(remember_failure(GUARD,exc))
                    details.update(error_kind=exc.error_kind,status='error');captured.update(details)
                    record_observation(PROVIDER,started,outcome='failure',source='earnings_call',details=details,sent=details.get('http_request_sent')is True)
                    exc.diagnostic.update(details)
                    if exc is original:raise
                    raise exc from original
                details.update(status='success',record_count=1,fetched_at_epoch=receipt['retrieved_at'],coverage_status='native_text_complete')
                captured.update(details);record_observation(PROVIDER,started,outcome='results',count=1,source='earnings_call',details=details,sent=True)
                return {'pdf':receipt,'diagnostic':details}
            saved,cache=shared_fetch(POLICY+':'+selected['url'],acquire,freshness_seconds=_freshness(),
                                    result_ttl=lambda value:max(1,math.floor(_stamp(value['pdf'])+_freshness()-time.time())),lock_wait_seconds=0)
            if cache.get('error_kind')or cache.get('stale'):
                # A verified original can satisfy a read while its HTTP error
                # cache remains intact. Never mask current typed lifecycle aborts.
                kind=captured.get('error_kind')or cache.get('error_kind')or'stale_source'
                retained=None if kind in {'lease_lost','timeout','single_flight_busy','guard_storage_unavailable'} else _retained_original(selected)
                if retained is None:
                    exc=SourceResponseError(kind);exc.diagnostic.update(captured);raise exc
                saved=retained
            if not isinstance(saved,dict)or not isinstance(saved.get('pdf'),dict)or not isinstance(saved.get('diagnostic'),dict):raise SourceResponseError('cached_original_unverified')
            native=_native(_saved(saved['pdf'],selected['url']),selected,deadline)
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            if not owns():raise SourceResponseError('lease_lost')
            proof={'policy':POLICY,'identity':identity,'index':index,'metadata':deepcopy(metadata),'selected':selected,'pdf':saved['pdf']}
            context=_context(metadata,selected,native,proof);component=deepcopy(saved['diagnostic'])
            if cache.get('cache_hit')or component.get('original_reused')is True:
                component.update(cache_hit=True,http_request_sent=False,http_request_count=0,event_kind='cache_hit')
                from search_provider_runtime import record_source_audit_entries,current_correlation
                try:
                    record_source_audit_entries([{**current_correlation(),**component,'source':'earnings_call','provider':PROVIDER,'status':'skipped_fresh_cache','record_count':1}])
                except Exception as telemetry_error:
                    component['cache_observation_error_kind']=type(telemetry_error).__name__
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            if not owns():raise SourceResponseError('lease_lost')
            if component.get('http_request_sent')is True:
                try:_retain_original(saved['pdf'])
                except Exception as retention_error:component['original_retention_error_kind']=type(retention_error).__name__
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            if not owns():raise SourceResponseError('lease_lost')
            components['prepared_pdf']=component;count=diagnostics.get('http_request_count',0)+int(component.get('http_request_sent')is True)
            diagnostics.update(actual_provider=PROVIDER,nanya_originals_verified=True,component_statuses=components,
                               http_request_count=count,http_request_sent=bool(count),cache_hit=not count,
                               fetched_at_epoch=context['fetched_at_epoch'],coverage_status='native_text_complete')
            return context
    except (SourceResponseError,ValueError,TypeError,KeyError,OSError,EOFError,SourcePdfError)as original:
        exc=original if isinstance(original,SourceResponseError)else SourceResponseError('timeout'if isinstance(original,SourcePdfError)and original.reason=='timeout'else'original_unverified')
        components['prepared_pdf']={**exc.diagnostic,'error_kind':exc.error_kind,'status':'error'}
        count=diagnostics.get('http_request_count',0)+int(captured.get('http_request_sent')is True)
        diagnostics.update(component_statuses=components,coverage_status='partial',http_request_count=count,http_request_sent=bool(count))
        if exc.error_kind in {'lease_lost','timeout','single_flight_busy','guard_storage_unavailable'}:raise exc
        return metadata
