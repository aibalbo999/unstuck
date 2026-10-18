"""Exact declared Hon Hai call transcript; never assume it is the latest call."""
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import re
import time
import zlib
from uuid import uuid4
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from official_response_evidence import archive_response, read_response
from search_admission import endpoint_admission
from search_provider_runtime import (SourceResponseError, cooldown_state, remember_failure,
                                     record_observation, scope_key)
from shared_provider_cache import shared_fetch
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .official_company_legal_name import (read_cached_listed_roster_bytes,
                                         parse_roster, select_legal_name)
from .honhai_conference_transport import PROVIDER, PAGE_URL, TRANSCRIPT_URL, transcript_url, download

POLICY = 'honhai-original-transcript-v1'
GUARD = scope_key(PROVIDER, endpoint='www.honhai.com')
ROSTER_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
EVENT_DATE = '2026-08-12'
NOTE = '鴻海官方單場頁與完整法說會逐字稿、原生文字已取得；會議日及15:00時間依PDF封面，頁面顯示7/29不等於PDF首次發布日，檔名8/18亦不推定首次發布。逐字稿準確性、實際會議及各項陳述未由影音或獨立來源驗證。'



def supports_honhai(ticker):
    return str(ticker).strip().upper() in {'2317', '2317.TW'}


def _today(now=None):
    return datetime.fromtimestamp(time.time() if now is None else now, ZoneInfo('Asia/Taipei')).date()


def _anchor(raw, today, epoch=None):
    roster = parse_roster(raw, '.TW')
    anchor = select_legal_name(roster, '2317.TW', '鴻海', today=today)
    rows = [r for r in json.loads(raw) if r.get('公司代號') == '2317']
    if (not anchor or anchor.get('legal_name') != '鴻海精密工業股份有限公司'
            or anchor.get('official_ubn') != '04541302' or len(rows) != 1
            or rows[0].get('網址') != 'https://www.honhai.com/zh-tw' or rows[0].get('英文簡稱') != 'HON HAI'):
        raise ValueError('Hon Hai official identity differs')
    if epoch is not None and date.fromisoformat(anchor['as_of'])>_today(epoch):raise ValueError('Hon Hai master is newer than receipt')
    return anchor


def select_page(raw, *, today=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_000_000:raise ValueError('Hon Hai page size invalid')
    soup=BeautifulSoup(raw.decode('utf8',errors='strict'),'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True)!='2026年第二季法人說明會 - 鴻海科技集團':raise ValueError('Hon Hai title absent')
    roots=soup.select('div.hh-content-inner-wrapper')
    roots=[r for r in roots if r.select_one('div.hh-title-content')]
    if len(roots)!=1:raise ValueError('Hon Hai source content root invalid')
    root=roots[0];title=root.select('div.hh-title-content');dates=root.select('div.hh-news-detail-attr div.hh-description-detail')
    if len(title)!=1 or title[0].get_text(' ',strip=True)!='2026年第二季法人說明會' or len(dates)!=1:raise ValueError('Hon Hai native title or date invalid')
    day=dates[0].get_text(' ',strip=True)
    if day!='2026/07/29' or date.fromisoformat(EVENT_DATE)>=(today or _today()):raise ValueError('Hon Hai exact supported event or displayed date invalid')
    sections=root.select('div.hh-relation-media-download > div.info')
    files=[r for r in sections if r.select_one('div.title')and r.select_one('div.title').get_text(' ',strip=True)=='文件下載']
    if len(files)!=1:raise ValueError('Hon Hai download section invalid')
    links=files[0].select('div.files > a.hh-table-pdf-download[href]')
    transcripts=[a for a in links if a.get_text(' ',strip=True)=='Hon_Hai_2Q26_Results_Transcript_Chinese_20260818_4465.pdf']
    copyrights=soup.select('div.copyright')
    if len(copyrights)!=1 or copyrights[0].get_text(' ',strip=True)!='Copyright © 2025 鴻海精密工業股份有限公司著作權所有':raise ValueError('Hon Hai legal owner absent')
    if len(transcripts)!=1 or transcripts[0]['href']!=TRANSCRIPT_URL:raise ValueError('Hon Hai official transcript route invalid')
    return {'event_date':EVENT_DATE,'url':TRANSCRIPT_URL,'label':'2026年第二季法人說明會官方逐字稿','source_page_displayed_date':'2026-07-29'}


def _native_pdf(raw, selected, deadline):
    remaining=min(10.,deadline-time.monotonic())
    if remaining<=0:raise SourceResponseError('timeout')
    try:native=extract_pdf_pages(raw,timeout_seconds=remaining)
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    if time.monotonic() >= deadline:raise SourceResponseError('timeout')
    cover=re.sub(r'\s+','',native['pages'][0]['text'])
    if (native['coverage_status']!='complete' or '鴻海精密工業股份有限公司'not in cover or '法說會逐字稿'not in cover
            or '2026年第二季法人說明會'not in cover or '會議日期及時間：2026年8月12日台北時間下午3點'not in cover
            or 'https://www.honhai.com/zh-tw/'not in cover):raise ValueError('Hon Hai cover owner, declared call and original transcript not verified')
    if time.monotonic() >= deadline:raise SourceResponseError('timeout')
    return native


def _stamp(receipt):
    stamp = receipt.get('retrieved_at')
    if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp <= 0 or stamp > time.time():
        raise ValueError('Hon Hai original timestamp invalid')
    return stamp


def _saved(receipt, url, *, identity=False):
    if (not isinstance(receipt,dict)or receipt.get('status')!='archived'or receipt.get('source_url')!=url):raise ValueError('Hon Hai original receipt invalid')
    stamp=_stamp(receipt)
    if not 0<=time.time()-stamp<=86400:raise ValueError('Hon Hai original expired')
    if identity:
        if (receipt.get('http_status')is not None or receipt.get('http_status_observed')is not False
                or receipt.get('evidence_kind')!='cached_complete_source_payload_verified_by_digest'
                or receipt.get('cache_source')!='official-company-roster:v2:.TW'
                or receipt.get('source_payload_sha256')!=receipt.get('raw_response_sha256')
                or type(receipt.get('source_payload_bytes'))is not int or receipt['source_payload_bytes']!=receipt.get('raw_response_bytes')):raise ValueError('Hon Hai cached master receipt invalid')
    elif (type(receipt.get('http_status'))is not int or receipt['http_status']!=200
            or receipt.get('evidence_kind')!='raw_http_response_bytes'
            or receipt.get('http_status_observed',True)is not True
            or any(k in receipt for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):raise ValueError('Hon Hai native receipt invalid')
    raw=read_response(receipt);limit=2_500_000 if identity else 1_000_000 if url==PAGE_URL else 8*1024*1024
    if type(receipt.get('raw_response_bytes'))is not int or not 0<len(raw)<=limit or receipt['raw_response_bytes']!=len(raw):raise ValueError('Hon Hai original length invalid')
    return raw


def _context(selected, native, receipt):
    pdf = receipt['pdf']
    doc = {'document_id': '2317:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': '2317.TW', 'title': selected['label'], 'url': selected['url'], 'source': PROVIDER,
           'source_type': 'issuer_official', 'document_kind': 'transcript', 'projection_policy':'honhai-transcript-role-v1',
           'event_date': selected['event_date'], 'event_date_basis':'official_transcript_cover_declared_date_time', 'event_time_Taipei':'15:00', 'published_at': None, 'material_file_date':None, 'content_period':'2026 Q2', 'source_page_displayed_date':selected['source_page_displayed_date'], 'transcript_accuracy_independently_verified':False,
           'retrieved_at_epoch': pdf['retrieved_at'], 'content_sha256': native['content_sha256'],
           'binary_complete': True, 'page_count': native['page_count'], 'pages': native['pages'],
           'missing_text_pages': native['empty_pages'], 'garbled_pages': native['garbled_pages'],
           'text_extraction_complete': True, 'native_text_coverage': 'complete',
           'coverage_status': 'partial', 'full_content_coverage_verified': False,
           'parser_version': native['parser_version']}
    if native.get('symbol_mapping_evidence'):
        doc['symbol_mapping_evidence'] = deepcopy(native['symbol_mapping_evidence'])
    return {'ticker': '2317.TW', 'date': selected['event_date'], 'period': selected['event_date'],
            'title': selected['label'], 'summary': '', 'transcript_excerpt': '',
            'transcript_available': True, 'source': PROVIDER, 'source_url': PAGE_URL,
            'materials': [{'url': selected['url'], 'kind': 'transcript'}], 'documents': [doc],
            'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'fetched_at_epoch': pdf['retrieved_at'], 'honhai_conference_receipt': receipt}


def verify_context(value, ticker, *, deadline=None):
    deadline = time.monotonic() + 10. if deadline is None else deadline
    try:
        if time.monotonic() >= deadline:raise SourceResponseError('timeout')
        if not supports_honhai(ticker) or not isinstance(value, dict) or value.get('ticker') != '2317.TW':
            return False
        proof = value['honhai_conference_receipt']
        if proof.get('policy') != POLICY:
            return False
        _anchor(_saved(proof['identity'], ROSTER_URL, identity=True), _today(), _stamp(proof['identity']))
        selected = select_page(_saved(proof['page'], PAGE_URL))
        if not selected or selected != proof['selected']:
            return False
        raw = _saved(proof['pdf'], selected['url'])
        if not 0 <= time.time() - _stamp(proof['pdf']) <= 86400:
            return False
        native = _native_pdf(raw, selected, deadline)
        expected = _context(selected, native, proof)
        verified = set(value)==set(expected) and all(value.get(k)==v for k,v in expected.items())
        if time.monotonic() >= deadline:raise SourceResponseError('timeout')
        return verified
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout':
            raise
        return False
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, OSError, EOFError, UnicodeError, zlib.error, SourcePdfError):
        return False


def _operation(url, parser, endpoint, deadline, components, owns):
    started = time.monotonic()
    diagnostic = {'source_url': url, 'endpoint': endpoint, 'actual_provider': PROVIDER,
                  'parser_version': POLICY, 'attempt_id': uuid4().hex, 'http_request_sent': False}
    try:
        if not owns():
            raise SourceResponseError('lease_lost')
        if cooldown_state(GUARD):
            raise SourceResponseError('cooldown')
        raw = download(url, deadline=deadline, diagnostics=diagnostic)
        parsed = parser(raw)
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout')
        if not owns():
            raise SourceResponseError('lease_lost')
        stamp = time.time()
        receipt = archive_response(raw, source_url=url, retrieved_at=stamp)
        if receipt.get('status') != 'archived':
            raise SourceResponseError('original_archive_unavailable')
        if _saved(receipt, url) != raw:
            raise SourceResponseError('original_unverified')
    except Exception as original:
        exc = original if isinstance(original, SourceResponseError) else SourceResponseError('parse_error')
        if diagnostic.get('http_request_sent') and owns():
            diagnostic.update(remember_failure(GUARD, exc))
        diagnostic.update(error_kind=exc.error_kind, status='error')
        components[endpoint] = deepcopy(diagnostic)
        record_observation(PROVIDER, started, outcome='failure', details=diagnostic,
                           source='earnings_call', sent=diagnostic.get('http_request_sent') is True)
        exc.diagnostic.update(diagnostic, component_statuses=deepcopy(components))
        if exc is original:
            raise
        raise exc from original
    diagnostic.update(record_count=1 if parsed else 0, fetched_at_epoch=stamp,
                      coverage_status='native_text_complete' if endpoint == 'pdf' else 'metadata_only',
                      original_receipt=receipt, status='success' if parsed else 'degraded_enrichment')
    components[endpoint] = deepcopy(diagnostic)
    record_observation(PROVIDER, started, outcome='results' if parsed else 'valid_empty',
                       count=1 if parsed else 0, details=diagnostic, source='earnings_call', sent=True)
    return parsed, receipt


def _fetch(*, deadline=None):
    deadline = deadline if deadline is not None else time.monotonic() + 20.
    with endpoint_admission(GUARD, timeout_seconds=20.) as owns:
        if not owns:
            raise SourceResponseError('single_flight_busy')
        master = read_cached_listed_roster_bytes()
        if master is None:
            raise SourceResponseError('identity_anchor_unavailable')
        raw, meta = master
        try:
            _anchor(raw, _today(), meta['fetched_at_epoch'])
        except (ValueError, TypeError, KeyError) as exc:
            raise SourceResponseError('identity_anchor_unverified') from exc
        identity = archive_response(raw, source_url=ROSTER_URL,
                                    retrieved_at=meta['fetched_at_epoch'], http_status=None,
                                    evidence_kind='cached_complete_source_payload_verified_by_digest')
        identity.update({k:meta[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
        if _saved(identity,ROSTER_URL,identity=True)!=raw:raise SourceResponseError('identity_anchor_unverified')
        if identity.get('status') != 'archived':
            raise SourceResponseError('original_archive_unavailable')
        components = {}
        selected, index = _operation(PAGE_URL, select_page, 'page', deadline, components, owns)
        if selected is None:
            return {'context': {}, 'diagnostic': {'actual_provider': PROVIDER,
                    'coverage_status': 'partial', 'component_statuses': components,
                    'http_request_sent': True, 'http_request_count': 1}}
        native, pdf = _operation(selected['url'], lambda raw: _native_pdf(raw, selected, deadline),
                                 'pdf', deadline, components, owns)
        proof = {'policy': POLICY, 'identity': identity, 'page': index,
                 'pdf': pdf, 'selected': selected}
        context = _context(selected, native, proof)
        try:
            if not verify_context(context, '2317.TW', deadline=deadline) or not owns():
                raise SourceResponseError('original_unverified' if owns() else 'lease_lost')
        except SourceResponseError as exc:
            exc.diagnostic.update(component_statuses=deepcopy(components))
            raise
        return {'context': context, 'diagnostic': {'actual_provider': PROVIDER,
                'coverage_status': 'native_text_complete', 'honhai_originals_verified': True, 'honhai_transcript_workflow':True,
                'component_statuses': components, 'http_request_sent': True,
                'http_request_count': 2, 'fetched_at_epoch': pdf['retrieved_at'],
                'message': NOTE}}


def fetch_honhai_context(ticker, *, expected_event_date, diagnostics=None, deadline=None):
    if not supports_honhai(ticker) or expected_event_date != EVENT_DATE:
        return {}
    deadline = min(deadline if deadline is not None else time.monotonic()+20., time.monotonic()+20.)
    captured = {}
    def collect():
        try:
            return _fetch(deadline=deadline)
        except SourceResponseError as exc:
            components=exc.diagnostic.get('component_statuses')or{}
            exc.diagnostic.update(actual_provider=PROVIDER,honhai_transcript_workflow=True,
                                  http_request_sent=any(d.get('http_request_sent')is True for d in components.values()),
                                  http_request_count=sum(d.get('http_request_sent')is True for d in components.values()))
            captured.update(exc.diagnostic)
            raise
    result, meta = shared_fetch(POLICY + ':2317.TW', collect, freshness_seconds=86400,
                               result_ttl=lambda row: min(86400,max(1,int(row['context']['honhai_conference_receipt']['identity']['retrieved_at']+86400-time.time()))) if row['context'] else 600,
                               lock_wait_seconds=0)
    if meta.get('error_kind'):
        details = {**meta, **captured}
        details.update(actual_provider=PROVIDER,honhai_transcript_workflow=True)
        details.setdefault('http_request_sent',False)
        details.setdefault('http_request_count',0)
        exc = SourceResponseError(details['error_kind'], status_code=details.get('http_status'))
        exc.diagnostic.update(details)
        raise exc
    if (not isinstance(result, dict) or not isinstance(result.get('context'), dict)
            or not isinstance(result.get('diagnostic'), dict)):
        exc=SourceResponseError('cached_original_unverified')
        exc.diagnostic.update(actual_provider=PROVIDER,honhai_transcript_workflow=True,http_request_sent=False,http_request_count=0,cache_hit=bool(meta.get('cache_hit')))
        raise exc
    context = result['context']
    details = {**result['diagnostic'], **meta}
    if context:
        details['fetched_at_epoch'] = context['fetched_at_epoch']
    if meta.get('cache_hit'):
        details.update(http_request_sent=False, http_request_count=0)
        details['component_statuses'] = {k: {**v, 'http_request_sent': False,
                                            'cache_hit': True, 'event_kind': 'cache_hit'}
                                        for k, v in details['component_statuses'].items()}
    try:
        verified=not context or verify_context(context,'2317.TW',deadline=deadline)
        if not verified:raise SourceResponseError('cached_original_unverified')
        value = deepcopy(context)
        if time.monotonic() >= deadline:raise SourceResponseError('timeout')
    except SourceResponseError as exc:
        exc.diagnostic.update(details)
        # Saved native children remain evidence; this consumer did not verify them.
        for key in ('coverage_status', 'message'):
            exc.diagnostic.pop(key, None)
        exc.diagnostic.update(actual_provider=PROVIDER,honhai_transcript_workflow=True,
                              honhai_originals_verified=False,error_kind=exc.error_kind,
                              cache_hit=bool(meta.get('cache_hit')))
        raise
    if diagnostics is not None:
        diagnostics.update(details)
    return value


def validate_identity(data,ticker):
    from source_applicability import instrument_type
    if (ticker!='2317.TW'or not isinstance(data,dict)or data.get('ticker')!=ticker or instrument_type(data)!='EQUITY'
            or any(data.get(k)not in(None,'','EQUITY')for k in ('instrument_type','quote_type','quoteType'))):return False
    if data.get('company_name')not in(None,'','鴻海','鴻海精密工業股份有限公司','Hon Hai Precision Industry Co., Ltd.','鴻海 / Hon Hai Precision Industry Co., Ltd.'):return False
    context=data.get('company_identity')
    if context is None:context={}
    if not isinstance(context,dict):return False
    for key,expected in (('ticker','2317.TW'),('stock_id','2317'),('official_name','鴻海'),('legal_name','鴻海精密工業股份有限公司'),('official_ubn','04541302'),('instrument_type','EQUITY')):
        if context.get(key)not in(None,'',expected):return False
    forbidden=context.get('forbidden_aliases',[])
    return isinstance(forbidden,(list,tuple)) and all(isinstance(s,str)for s in forbidden) and not {'鴻海','鴻海精密工業股份有限公司','hon hai'}&{s.casefold().strip('* ').strip()for s in forbidden}


def validate_context(data,ticker):
    if not validate_identity(data,ticker):return False
    call=data.get('earnings_call')
    return isinstance(call,dict)and call.get('date')==EVENT_DATE and call.get('ticker',ticker)in{ticker,'2317'}


def is_marked(value):
    if not isinstance(value,dict):return False
    if 'honhai_conference_receipt'in value or value.get('source')==PROVIDER or value.get('source_url')==PAGE_URL:return True
    return any(isinstance(d,dict)and(d.get('source')==PROVIDER or transcript_url(d.get('url')))for k in ('documents','materials')for d in (value.get(k)if isinstance(value.get(k),list)else []))


def enrich_honhai_context(ticker, value, *, diagnostics=None, deadline=None):
    if not supports_honhai(ticker)or not isinstance(value,dict)or value.get('date')!=EVENT_DATE:return value
    if value.get('ticker','2317.TW')not in{'2317.TW','2317'}:raise SourceResponseError('context_unverified')
    try:
        return fetch_honhai_context(ticker,expected_event_date=value['date'],diagnostics=diagnostics,deadline=deadline)
    except SourceResponseError as exc:
        if exc.error_kind in {'timeout','lease_lost','single_flight_busy','guard_storage_unavailable'}:raise
        if diagnostics is not None:
            components=dict(diagnostics.get('component_statuses')or{})
            components['HonHaiTranscript']=dict(exc.diagnostic)
            diagnostics.update(component_statuses=components,coverage_status='partial',
                               actual_provider=value.get('source')or'MOPS investor conference',
                               message='optional 外部來源 鴻海逐字稿未取得；原索引資料與失敗觀測保留。')
        return value
