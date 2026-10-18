"""Verified TXC issuer presentation originals; never a call transcript."""
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
from .txc_conference_transport import PROVIDER, INDEX_URL, presentation_url, download

POLICY = 'txc-original-presentation-v1'
GUARD = scope_key(PROVIDER, endpoint='www.txccorp.com')
ROSTER_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
NOTE = '晶技官方索引所連結的完整法說簡報及原生文字已取得；活動日僅由索引提供，PDF封面無場次日，不推定實際開會或首次發布日。不是逐字稿，影像、圖表數字與阅读順序、各項陳述未獨立驗證。'


def supports_txc(ticker):
    return str(ticker).strip().upper() in {'3042', '3042.TW'}


def _today(now=None):
    return datetime.fromtimestamp(time.time() if now is None else now, ZoneInfo('Asia/Taipei')).date()


def _anchor(raw, today, epoch=None):
    roster = parse_roster(raw, '.TW')
    anchor = select_legal_name(roster, '3042.TW', '晶技', today=today)
    rows = [r for r in json.loads(raw) if r.get('公司代號') == '3042']
    if (not anchor or anchor.get('legal_name') != '台灣晶技股份有限公司'
            or anchor.get('official_ubn') != '21204867' or len(rows) != 1
            or rows[0].get('網址') != 'www.txccorp.com' or rows[0].get('英文簡稱') != 'TXC'):
        raise ValueError('TXC official identity differs')
    if epoch is not None and date.fromisoformat(anchor['as_of'])>_today(epoch):raise ValueError('TXC master is newer than receipt')
    return anchor


def select_index(raw, *, today=None):
    if not isinstance(raw,bytes)or not 0<len(raw)<=200_000:raise ValueError('TXC index size invalid')
    soup=BeautifulSoup(raw.decode('utf8',errors='strict'),'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True)!='法人說明會-投資人專區-台灣晶技股份有限公司 TXC Corporation.':raise ValueError('TXC index owner absent')
    roots=soup.select('div.mainArea > div.contentBox.clearfix > div.typeLayout.type9_3 > div.wrap.articleList > div.articleItem > div.textEditor')
    if len(roots)!=1:raise ValueError('TXC index content root invalid')
    tables=roots[0].find_all('table')
    if len(tables)!=1:raise ValueError('TXC conference table invalid')
    table=tables[0];header=table.find('thead')
    if not header or re.sub(r'\s+','',header.get_text())!='日期(DD/MM/YYYY)檔案下載影音連結':raise ValueError('TXC table header invalid')
    body=table.find('tbody')
    if not body:raise ValueError('TXC conference rows missing')
    today=today or _today();candidates={}
    for row in body.find_all('tr',recursive=False):
        cells=row.find_all('td',recursive=False)
        if len(cells)!=4:raise ValueError('TXC conference cell count invalid')
        values=[c.get_text(' ',strip=True)for c in cells]
        if not any(values)and not row.find('a'):continue
        if not re.fullmatch(r'\d{2}/\d{2}/20\d{2}',values[0]):raise ValueError('TXC event date invalid')
        event=datetime.strptime(values[0],'%d/%m/%Y').date();links=cells[2].find_all('a',href=True)
        if len(links)!=1 or not presentation_url(links[0]['href'])or not 1<=len(values[1])<=200:raise ValueError('TXC presentation link or label invalid')
        # Same-day event start is unknown in this day-only index.
        if event>=today:continue
        selected={'event_date':event.isoformat(),'url':links[0]['href'],'label':values[1]}
        if event in candidates and candidates[event]!=selected:raise ValueError('TXC latest conference ambiguous')
        candidates[event]=selected
    return candidates[max(candidates)]if candidates else None


def _native_pdf(raw, selected, deadline):
    remaining=min(10.,deadline-time.monotonic())
    if remaining<=0:raise SourceResponseError('timeout')
    try:
        native=extract_pdf_pages(raw,timeout_seconds=remaining)
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    cover=re.sub(r'\s+','',native['pages'][0]['text']);year=date.fromisoformat(selected['event_date']).year
    if (native['coverage_status']!='complete' or '台灣晶技股份有限公司'not in cover or '法人說明會'not in cover
            or f'©{year}台灣晶技股份有限公司'not in cover):raise ValueError('TXC native issuer and material year not verified')
    # The PDF has no explicit cover date. Bind the original through the native
    # issuer index link; keep event and first publication assertions distinct.
    return native


def _stamp(receipt):
    stamp = receipt.get('retrieved_at')
    if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp <= 0 or stamp > time.time():
        raise ValueError('TXC original timestamp invalid')
    return stamp


def _saved(receipt, url, *, identity=False):
    if (not isinstance(receipt,dict)or receipt.get('status')!='archived'or receipt.get('source_url')!=url):raise ValueError('TXC original receipt invalid')
    stamp=_stamp(receipt)
    if not 0<=time.time()-stamp<=86400:raise ValueError('TXC original expired')
    if identity:
        if (receipt.get('http_status')is not None or receipt.get('http_status_observed')is not False
                or receipt.get('evidence_kind')!='cached_complete_source_payload_verified_by_digest'
                or receipt.get('cache_source')!='official-company-roster:v2:.TW'
                or receipt.get('source_payload_sha256')!=receipt.get('raw_response_sha256')
                or type(receipt.get('source_payload_bytes'))is not int or receipt['source_payload_bytes']!=receipt.get('raw_response_bytes')):raise ValueError('TXC cached master receipt invalid')
    elif (type(receipt.get('http_status'))is not int or receipt['http_status']!=200
            or receipt.get('evidence_kind')!='raw_http_response_bytes'
            or receipt.get('http_status_observed',True)is not True
            or any(k in receipt for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):raise ValueError('TXC native receipt invalid')
    raw=read_response(receipt);limit=2_500_000 if identity else 200_000 if url==INDEX_URL else 8*1024*1024
    if type(receipt.get('raw_response_bytes'))is not int or not 0<len(raw)<=limit or receipt['raw_response_bytes']!=len(raw):raise ValueError('TXC original length invalid')
    return raw


def _context(selected, native, receipt):
    pdf = receipt['pdf']
    doc = {'document_id': '3042:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': '3042.TW', 'title': selected['label'], 'url': selected['url'], 'source': PROVIDER,
           'source_type': 'issuer_official', 'document_kind': 'presentation',
           'event_date': selected['event_date'], 'event_date_basis':'issuer_index_linked_date_not_PDF_cover_confirmation', 'published_at': None, 'material_file_date':None, 'content_period':None,
           'retrieved_at_epoch': pdf['retrieved_at'], 'content_sha256': native['content_sha256'],
           'binary_complete': True, 'page_count': native['page_count'], 'pages': native['pages'],
           'missing_text_pages': native['empty_pages'], 'garbled_pages': native['garbled_pages'],
           'text_extraction_complete': True, 'native_text_coverage': 'complete',
           'coverage_status': 'partial', 'full_content_coverage_verified': False,
           'parser_version': native['parser_version']}
    if native.get('symbol_mapping_evidence'):
        doc['symbol_mapping_evidence'] = deepcopy(native['symbol_mapping_evidence'])
    return {'ticker': '3042.TW', 'date': selected['event_date'], 'period': selected['event_date'],
            'title': selected['label'], 'summary': '', 'transcript_excerpt': '',
            'transcript_available': False, 'source': PROVIDER, 'source_url': INDEX_URL,
            'materials': [{'url': selected['url'], 'kind': 'presentation'}], 'documents': [doc],
            'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'fetched_at_epoch': pdf['retrieved_at'], 'txc_conference_receipt': receipt}


def verify_context(value, ticker, *, deadline=None):
    try:
        if not supports_txc(ticker) or not isinstance(value, dict) or value.get('ticker') != '3042.TW':
            return False
        proof = value['txc_conference_receipt']
        if proof.get('policy') != POLICY:
            return False
        _anchor(_saved(proof['identity'], ROSTER_URL, identity=True), _today(), _stamp(proof['identity']))
        selected = select_index(_saved(proof['index'], INDEX_URL))
        if not selected or selected != proof['selected']:
            return False
        raw = _saved(proof['pdf'], selected['url'])
        if not 0 <= time.time() - _stamp(proof['pdf']) <= 86400:
            return False
        native = _native_pdf(raw, selected, deadline or time.monotonic() + 10.)
        expected = _context(selected, native, proof)
        return set(value)==set(expected) and all(value.get(k)==v for k,v in expected.items())
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
        selected, index = _operation(INDEX_URL, select_index, 'index', deadline, components, owns)
        if selected is None:
            return {'context': {}, 'diagnostic': {'actual_provider': PROVIDER,
                    'coverage_status': 'partial', 'component_statuses': components,
                    'http_request_sent': True, 'http_request_count': 1}}
        native, pdf = _operation(selected['url'], lambda raw: _native_pdf(raw, selected, deadline),
                                 'pdf', deadline, components, owns)
        proof = {'policy': POLICY, 'identity': identity, 'index': index,
                 'pdf': pdf, 'selected': selected}
        context = _context(selected, native, proof)
        if not verify_context(context, '3042.TW', deadline=deadline) or not owns():
            raise SourceResponseError('original_unverified' if owns() else 'lease_lost')
        return {'context': context, 'diagnostic': {'actual_provider': PROVIDER,
                'coverage_status': 'native_text_complete', 'txc_originals_verified': True,
                'component_statuses': components, 'http_request_sent': True,
                'http_request_count': 2, 'fetched_at_epoch': pdf['retrieved_at'],
                'message': NOTE}}


def fetch_txc_context(ticker, *, diagnostics=None):
    if not supports_txc(ticker):
        return {}
    deadline = time.monotonic() + 20.
    captured = {}
    def collect():
        try:
            return _fetch(deadline=deadline)
        except SourceResponseError as exc:
            captured.update(exc.diagnostic)
            raise
    result, meta = shared_fetch(POLICY + ':3042.TW', collect, freshness_seconds=86400,
                               result_ttl=lambda row: min(86400,max(1,int(row['context']['txc_conference_receipt']['identity']['retrieved_at']+86400-time.time()))) if row['context'] else 600,
                               lock_wait_seconds=0)
    if meta.get('error_kind'):
        details = {**meta, **captured}
        exc = SourceResponseError(details['error_kind'], status_code=details.get('http_status'))
        exc.diagnostic.update(details)
        raise exc
    if (not isinstance(result, dict) or not isinstance(result.get('context'), dict)
            or not isinstance(result.get('diagnostic'), dict)):
        raise SourceResponseError('cached_original_unverified')
    context = result['context']
    if context and not verify_context(context, '3042.TW', deadline=deadline):
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
    if diagnostics is not None:
        diagnostics.update(details)
    return deepcopy(context)


def validate_context(data,ticker):
    from source_applicability import instrument_type
    if (ticker!='3042.TW'or not isinstance(data,dict)or data.get('ticker')!=ticker or instrument_type(data)!='EQUITY'
            or any(data.get(k)not in(None,'','EQUITY')for k in ('instrument_type','quote_type','quoteType'))):return False
    context=data.get('company_identity')
    if context is None:context={}
    if not isinstance(context,dict):return False
    for key,expected in (('ticker','3042.TW'),('stock_id','3042'),('official_name','晶技'),('legal_name','台灣晶技股份有限公司'),('official_ubn','21204867'),('instrument_type','EQUITY')):
        if context.get(key)not in(None,'',expected):return False
    forbidden=context.get('forbidden_aliases',[])
    return isinstance(forbidden,(list,tuple)) and all(isinstance(s,str)for s in forbidden) and not {'晶技','台灣晶技股份有限公司','txc'}&{s.casefold().strip('* ').strip()for s in forbidden}


def is_marked(value):
    if not isinstance(value,dict):return False
    if 'txc_conference_receipt'in value or value.get('source')==PROVIDER or value.get('source_url')==INDEX_URL:return True
    return any(isinstance(d,dict)and(d.get('source')==PROVIDER or presentation_url(d.get('url')))for k in ('documents','materials')for d in (value.get(k)if isinstance(value.get(k),list)else []))
