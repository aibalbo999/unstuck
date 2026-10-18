"""Verified PSC issuer presentation originals; never a call transcript."""
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
from .psc_conference_transport import PROVIDER, INDEX_URL, HOME_URL, presentation_url, announcement_url, download

POLICY = 'psc-original-presentation-v1'
GUARD = scope_key(PROVIDER, endpoint='www.pscnet.com.tw')
ROSTER_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
NOTE = '統一證券原公告日期時間與同月官網簡報、PDF封面相互核對；所列場次開始時間已過，不以此證明活動實際舉行或首次發布日。原生文字已取得，但非逐字稿，未讀取影音、未驗完整圖像或圖表順序。簡報財務資訊未完全經會計師核閱，不覆寫年度財報或TTM。'


def supports_psc(ticker):
    return str(ticker).strip().upper() in {'2855', '2855.TW'}


def _today(now=None):
    return datetime.fromtimestamp(time.time() if now is None else now, ZoneInfo('Asia/Taipei')).date()


def _guard():
    from cache_store import get_cache_json
    from provider_resilience import provider_circuit_state
    try:
        row=get_cache_json(GUARD)
        if row is not None:
            stamp=row.get('retry_at')if isinstance(row,dict)else None
            if type(stamp)not in(int,float)or not math.isfinite(stamp)or stamp<0:
                raise ValueError('PSC guard state invalid')
            if stamp>time.time():return row
        circuit=provider_circuit_state(GUARD)
        return {'error_kind':'circuit_open'}if circuit.get('open')else {}
    except Exception:
        return {'error_kind':'guard_storage_unavailable'}


def _anchor(raw, today, epoch=None):
    roster = parse_roster(raw, '.TW')
    anchor = select_legal_name(roster, '2855.TW', '統一證', today=today)
    rows = [r for r in json.loads(raw) if r.get('公司代號') == '2855']
    if (not anchor or anchor.get('legal_name') != '統一綜合證券股份有限公司'
            or anchor.get('official_ubn') != '23218183' or len(rows) != 1
            or rows[0].get('網址') != 'https://www.pscnet.com.tw/' or rows[0].get('英文簡稱') != 'PSC'):
        raise ValueError('PSC official identity differs')
    if epoch is not None and date.fromisoformat(anchor['as_of'])>_today(epoch):raise ValueError('PSC master is newer than receipt')
    return anchor


def _html(raw):
    if not isinstance(raw,bytes)or not 0<len(raw)<=700000:raise ValueError('PSC page size invalid')
    soup=BeautifulSoup(raw.decode('utf8',errors='strict'),'html.parser')
    if ('股利資訊(股票代號2855)' not in soup.get_text(' ',strip=True)
            or '統一綜合證券' not in soup.get_text(' ',strip=True)):
        raise ValueError('PSC page issuer absent')
    return soup


def select_announcement_link(raw):
    soup=_html(raw)
    links=[]
    for a in soup.find_all('a',href=True):
        if a.get_text(' ',strip=True).rstrip('_')=='公告本公司召開法人說明會相關資訊':
            url=urljoin(HOME_URL,a['href'])
            if not announcement_url(url):raise ValueError('PSC announcement link invalid')
            if url not in links:links.append(url)
    if len(links)!=1:raise ValueError('PSC latest announcement absent or ambiguous')
    return links[0]


def select_index(raw,*,today=None):
    soup=_html(raw);today=today or _today();rows={}
    for panel in soup.select('div.intro > ul.blu'):
        h=panel.find('h6');match=re.fullmatch(r'(20[0-9]{2})年(0?[1-9]|1[0-2])月',h.get_text(' ',strip=True)if h else '')
        if not match:continue
        month=(int(match[1]),int(match[2]))
        if month>(today.year,today.month):continue
        candidates=[a for a in panel.find_all('a',href=True)if a.get_text(' ',strip=True)=='法說會資料']
        if len(candidates)!=1:raise ValueError('PSC month presentation ambiguous')
        link=urljoin(INDEX_URL,candidates[0]['href'])
        # Older UAT links remain intact in the original. They are never mirrored.
        if not presentation_url(link):continue
        if month in rows:raise ValueError('PSC month duplicated')
        rows[month]={'url':link,'month_label':h.get_text(' ',strip=True),
                     'year':month[0],'month':month[1],'label':'統一證券'+h.get_text(' ',strip=True)+'法說會簡報'}
    return rows[max(rows)]if rows else None


def parse_announcement(raw,selected):
    soup=_html(raw);roots=soup.select('div.editZone > div.tabTyp1')
    if len(roots)!=1:raise ValueError('PSC announcement content root invalid')
    text=roots[0].get_text(' ',strip=True)
    def only(pattern):
        found=re.findall(pattern,text)
        if len(found)!=1:raise ValueError('PSC announced event missing or ambiguous')
        return found[0]
    roc,month,day=map(int,only(r'1\.召開法人說明會之日期[：:]\s*(\d{3})/(\d{2})/(\d{2})'))
    hour,minute=map(int,only(r'2\.召開法人說明會之時間[：:]\s*(\d{1,2})\s*時\s*(\d{1,2})\s*分'))
    event=datetime(roc+1911,month,day,hour,minute,tzinfo=ZoneInfo('Asia/Taipei'))
    if (event.year,event.month)!=(selected['year'],selected['month']):raise ValueError('PSC event month differs from material index')
    if event>datetime.fromtimestamp(time.time(),ZoneInfo('Asia/Taipei')):return None
    info=only(r'4\.法人說明會擇要訊息[：:]\s*(.*?)\s*5\.')
    reported=re.fullmatch(r'說明本公司(\d{3})年度Q([1-4])財務暨營運報告',info)
    if not reported:raise ValueError('PSC prepared period unverified')
    year=int(reported[1])+1911;quarter=int(reported[2]);period=f'{year}Q{quarter}'
    from calendar import monthrange
    if date(year,quarter*3,monthrange(year,quarter*3)[1])>event.date():raise ValueError('PSC prepared period after announced date')
    return {'event_date':event.date().isoformat(),'event_time':event.strftime('%H:%M'),
            'event_timezone':'Asia/Taipei','content_period':period,'description':info}


def _check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def _native_pdf(raw,selected,deadline):
    _check_deadline(deadline)
    try:
        native=extract_pdf_pages(raw,timeout_seconds=min(10.,max(.01,deadline-time.monotonic())))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check_deadline(deadline)
    if native['coverage_status']!='complete' or len(native['pages'])<2:raise ValueError('PSC native text coverage incomplete')
    cover=native['pages'][0]['text'];matches=re.findall(r'(?<!\d)(20\d{2})\.(\d{2})\.(\d{2})(?!\d)',cover)
    legal=re.sub(r'\s+','',native['pages'][1]['text'])
    if len(matches)!=1 or date(*map(int,matches[0])).isoformat()!=selected['event_date']or '統一綜合證券股份有限公司'not in legal:
        raise ValueError('PSC native cover event or legal issuer differs')
    year,q=selected['content_period'].split('Q')
    if not any(re.search(r'(?<!\d)'+year+r'\s+Q'+q+r'(?!\d)',p['text'])for p in native['pages']):
        raise ValueError('PSC prepared period not visible in original')
    _check_deadline(deadline)
    return native


def _stamp(receipt):
    stamp = receipt.get('retrieved_at')
    if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp <= 0 or stamp > time.time():
        raise ValueError('PSC original timestamp invalid')
    return stamp


def _saved(receipt, url, *, identity=False):
    if (not isinstance(receipt,dict)or receipt.get('status')!='archived'or receipt.get('source_url')!=url):raise ValueError('PSC original receipt invalid')
    stamp=_stamp(receipt)
    if not 0<=time.time()-stamp<=86400:raise ValueError('PSC original expired')
    if identity:
        if (receipt.get('http_status')is not None or receipt.get('http_status_observed')is not False
                or receipt.get('evidence_kind')!='cached_complete_source_payload_verified_by_digest'
                or receipt.get('cache_source')!='official-company-roster:v2:.TW'
                or receipt.get('source_payload_sha256')!=receipt.get('raw_response_sha256')
                or type(receipt.get('source_payload_bytes'))is not int or receipt['source_payload_bytes']!=receipt.get('raw_response_bytes')):raise ValueError('PSC cached master receipt invalid')
    elif (type(receipt.get('http_status'))is not int or receipt['http_status']!=200
            or receipt.get('evidence_kind')!='raw_http_response_bytes'
            or receipt.get('http_status_observed',True)is not True
            or any(k in receipt for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):raise ValueError('PSC native receipt invalid')
    raw=read_response(receipt);limit=2_500_000 if identity else 700_000 if url==INDEX_URL or url==HOME_URL or announcement_url(url) else 8*1024*1024
    if type(receipt.get('raw_response_bytes'))is not int or not 0<len(raw)<=limit or receipt['raw_response_bytes']!=len(raw):raise ValueError('PSC original length invalid')
    return raw


def _context(selected, native, receipt):
    pdf = receipt['pdf']
    doc = {'document_id': '2855:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': '2855.TW', 'title': selected['label'], 'url': selected['url'], 'source': PROVIDER,
           'source_type': 'issuer_official', 'document_kind': 'presentation',
           'event_date': selected['event_date'], 'event_date_basis':'issuer_announcement_date_time_and_PDF_cover_match', 'event_status':'announced_past_start_not_independently_occurrence_verified', 'event_time':selected['event_time'], 'event_timezone':'Asia/Taipei', 'published_at':None, 'material_file_date':None, 'content_period':selected['content_period'],
           'retrieved_at_epoch': pdf['retrieved_at'], 'content_sha256': native['content_sha256'],
           'binary_complete': True, 'page_count': native['page_count'], 'pages': native['pages'],
           'missing_text_pages': native['empty_pages'], 'garbled_pages': native['garbled_pages'],
           'text_extraction_complete': True, 'native_text_coverage': 'complete',
           'coverage_status': 'partial', 'full_content_coverage_verified': False,
           'parser_version': native['parser_version']}
    if native.get('symbol_mapping_evidence'):
        doc['symbol_mapping_evidence'] = deepcopy(native['symbol_mapping_evidence'])
    return {'ticker': '2855.TW', 'date':selected['event_date'],'time':selected['event_time'],'period':selected['content_period'],
            'title': selected['label'], 'summary': '', 'transcript_excerpt': '',
            'transcript_available': False, 'source': PROVIDER, 'source_url': INDEX_URL,
            'materials': [{'url': selected['url'], 'kind': 'presentation'}], 'documents': [doc],
            'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'fetched_at_epoch':min(receipt[k]['retrieved_at']for k in ('home','index','announcement','pdf')), 'psc_conference_receipt': receipt}


def verify_context(value, ticker, *, deadline=None):
    deadline = deadline if deadline is not None else time.monotonic() + 10.
    try:
        _check_deadline(deadline)
        if not supports_psc(ticker) or not isinstance(value, dict) or value.get('ticker') != '2855.TW':
            return False
        proof = value['psc_conference_receipt']
        if proof.get('policy') != POLICY:
            return False
        _anchor(_saved(proof['identity'], ROSTER_URL, identity=True), _today(), _stamp(proof['identity']))
        selected=select_index(_saved(proof['index'],INDEX_URL))
        if not selected:return False
        link=select_announcement_link(_saved(proof['home'],HOME_URL))
        event=parse_announcement(_saved(proof['announcement'],link),selected)
        if not event:return False
        selected={**selected,**event,'announcement_url':link}
        if selected!=proof['selected']:return False
        raw = _saved(proof['pdf'], selected['url'])
        if not 0 <= time.time() - _stamp(proof['pdf']) <= 86400:
            return False
        native = _native_pdf(raw, selected, deadline)
        expected = _context(selected, native, proof)
        verified = set(value)==set(expected) and all(value.get(k)==v for k,v in expected.items())
        _check_deadline(deadline)
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
        blocked=_guard()
        if blocked:
            raise SourceResponseError(blocked.get('error_kind','cooldown'))
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
        _check_deadline(deadline)
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
        link,home=_operation(HOME_URL,select_announcement_link,'home',deadline,components,owns)
        selected,index=_operation(INDEX_URL,select_index,'index',deadline,components,owns)
        if selected is None:
            return {'context':{},'diagnostic':{'actual_provider':PROVIDER,'coverage_status':'partial',
                    'component_statuses':components,'http_request_sent':True,'http_request_count':len(components)}}
        event,announcement=_operation(link,lambda raw:parse_announcement(raw,selected),'announcement',deadline,components,owns)
        if event is None:
            return {'context':{},'diagnostic':{'actual_provider':PROVIDER,'coverage_status':'partial',
                    'component_statuses':components,'http_request_sent':True,'http_request_count':len(components)}}
        selected={**selected,**event,'announcement_url':link}
        native,pdf=_operation(selected['url'],lambda raw:_native_pdf(raw,selected,deadline),'pdf',deadline,components,owns)
        proof={'policy':POLICY,'identity':identity,'home':home,'index':index,
               'announcement':announcement,'pdf':pdf,'selected':selected}
        context = _context(selected, native, proof)
        if not verify_context(context, '2855.TW', deadline=deadline) or not owns():
            raise SourceResponseError('original_unverified' if owns() else 'lease_lost')
        _check_deadline(deadline)
        return {'context': context, 'diagnostic': {'actual_provider': PROVIDER,
                'coverage_status': 'native_text_complete', 'psc_originals_verified': True,
                'component_statuses': components, 'http_request_sent': True,
                'http_request_count':4,'fetched_at_epoch':context['fetched_at_epoch'],
                'message': NOTE}}


def fetch_psc_context(ticker, *, diagnostics=None):
    if not supports_psc(ticker):
        return {}
    deadline = time.monotonic() + 20.
    captured = {}
    def collect():
        try:
            return _fetch(deadline=deadline)
        except SourceResponseError as exc:
            captured.update(exc.diagnostic)
            raise
    def ttl(row):
        if not row['context']:return 600
        oldest=min(_stamp(row['context']['psc_conference_receipt'][k])for k in ('identity','home','index','announcement','pdf'))
        remaining=math.floor(oldest+86400-time.time())
        if remaining<1:raise SourceResponseError('original_expired')
        return min(86400,remaining)
    result, meta = shared_fetch(POLICY + ':2855.TW', collect, freshness_seconds=86400,
                               result_ttl=ttl,
                               lock_wait_seconds=0)
    if meta.get('error_kind') or meta.get('stale'):
        details = {**meta, **captured}
        exc = SourceResponseError(details['error_kind'], status_code=details.get('http_status'))
        exc.diagnostic.update(details)
        raise exc
    _check_deadline(deadline)
    if (not isinstance(result, dict) or not isinstance(result.get('context'), dict)
            or not isinstance(result.get('diagnostic'), dict)):
        raise SourceResponseError('cached_original_unverified')
    context = result['context']
    if context and not verify_context(context, '2855.TW', deadline=deadline):
        exc = SourceResponseError('cached_original_unverified')
        exc.diagnostic.update(http_request_sent=False, cache_hit=bool(meta.get('cache_hit')))
        raise exc
    details = {**result['diagnostic'], **meta}
    if context:
        details['fetched_at_epoch'] = context['fetched_at_epoch']
    if meta.get('cache_hit'):
        details.update(http_request_sent=False, http_request_count=0)
        details['component_statuses'] = {k: {**v, 'http_request_sent': False,
                                            'cache_hit': True, 'event_kind': 'cache_hit'}
                                        for k, v in details['component_statuses'].items()}
    value = deepcopy(context)
    _check_deadline(deadline)
    if diagnostics is not None:
        diagnostics.update(details)
    _check_deadline(deadline)
    return value


def validate_context(data,ticker):
    from source_applicability import instrument_type
    if (ticker!='2855.TW'or not isinstance(data,dict)or data.get('ticker')!=ticker or instrument_type(data)!='EQUITY'
            or any(data.get(k)not in(None,'','EQUITY')for k in ('instrument_type','quote_type','quoteType'))):return False
    context=data.get('company_identity')
    if context is None:context={}
    if not isinstance(context,dict):return False
    if data.get('company_name') is not None:
        from source_content_selection import company_aliases
        if not isinstance(data['company_name'],str)or not {'統一證','統一綜合證券股份有限公司','psc','president securities corp.','president securities corp','president securities corporation'}&{v.casefold()for v in company_aliases(data)}:
            return False
    for key,expected in (('ticker','2855.TW'),('stock_id','2855'),('official_name','統一證'),('legal_name','統一綜合證券股份有限公司'),('official_ubn','23218183'),('instrument_type','EQUITY')):
        if context.get(key)not in(None,'',expected):return False
    forbidden=context.get('forbidden_aliases',[])
    return isinstance(forbidden,(list,tuple)) and all(isinstance(s,str)for s in forbidden) and not {'統一證','統一綜合證券股份有限公司','psc'}&{s.casefold().strip('* ').strip()for s in forbidden}


def is_marked(value):
    if not isinstance(value,dict):return False
    if 'psc_conference_receipt'in value or value.get('source')==PROVIDER or value.get('source_url')==INDEX_URL:return True
    return any(isinstance(d,dict)and(d.get('source')==PROVIDER or presentation_url(d.get('url')))for k in ('documents','materials')for d in (value.get(k)if isinstance(value.get(k),list)else []))
