"""Walsin exact issuer originals with conflicting-page and chart exclusions."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import csv
import io
import json
import re
import time
import zlib
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError
from .official_issuer_master import JSON_URL
from .walsin_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '1605.TW'
LEGAL = '華新麗華股份有限公司'
UBN = '35412204'
POLICY = 'walsin-original-presentation-v1'
PROJECTION_POLICY = 'walsin-presentation-role-v1'
KNOWN_SHA = '8cd60978a0130763166c32c4854e697575445b7c8891f20c7f12bd9cd2534dcd'
PAGE_TEXT_SHA256 = (
    '2cc7bb960940c3c8dac87ec74bca783033f487a3e65c628edae0ae73d45f55f4',
    '216df98515418778aacd389ddf96de9635e17e31f4ed16047010602748b03670',
    'e928045ed5d4a61b68010a9f03f45760e558e624e26cf0f5ac9eae0843f06a27',
    '9cb7016b7be1f4f28ed1d0a5e0f7d2a7d061968abb970215a8b23f422efbbb70',
    '2c63d5414f0befcb102b163e2da586ee8a15022b91178729834593c44afc2107',
    'afd33c76b12e0277ca8311d609a0660810389264c7a824feef51c7b5a39d4e6e',
    '6d51937bd62b7591aa7776b108ab32178ea429ed318f9e7ef7545866aa76c91c',
    '8059461808e59c3a4a647ab04216aeb0a54b0868846b08bdb6b87f9bff1cdf41',
    '0977932695c4956f1cce350ba3b2d18a50f1e8ce28e9bc99a316d3f699291a2d',
    'b5cecb9c7ca35604bba69cb5e920f6ae3070da7467e2b387607bdad40e7b9fcb',
    '5a91f8de1f5ab182f29beb065c35eb2545b50c15a1e59bc96b56fedbfb3fc025',
)
NOTE = ('華新官方2026Q2法說簡報，11頁原件與原生文字完整，但非完整圖像語意、逐字稿、實際問答或完整財報。'
        '原件p4上年EBITDA 27與YoY26%不一致，保留原文、不改成2.7，角色整頁排除。'
        '首版角色僅使用1/2/3/8/9/10頁；圖表5–7與問答加入方式11頁不供分析。'
        'p8金額為新台幣十億元，PPE含無形資產、存貨含預付款；p9括號為流出，破折號不當零。'
        'p9現金17.9含避險金融資產0.2，與資產負債表17.7範圍不同。'
        '8/7場次、Q2財務與Q3展望分開，首次發布日未知；展望為當時公司說法，非已實現結果。'
        '官網Video Link文字連至Q1，不能據以當Q2影音或逐字稿；只使用明確公布且核定的Q2 PDF。'
        '私存原件供稽核，不主張商業再利用授權。')


def supports_walsin(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'1605', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_walsin_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Walsin master size invalid')
    if source_url == JSON_URL:
        from .official_issuer_master_json import parse_rows
        rows = parse_rows(raw, epoch); fields = list(rows[0])
    elif source_url == MASTER_URL:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True)
        rows = list(reader); fields = reader.fieldnames
    else:
        raise ValueError('unqualified master URL')
    if (not fields or len(fields) != len(set(fields)) or not 500 <= len(rows) <= 2000
            or any(None in r or any(v is None for v in r.values()) for r in rows)):
        raise ValueError('Walsin complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '1605']
    if len(matched) != 1:
        raise ValueError('Walsin master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '華新', '營利事業統一編號': UBN, '網址': 'https://www.walsin.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'WALSIN'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Walsin master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Walsin master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '華新', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('Walsin index section ambiguous')
    return values[0]


def select_presentation(raw, epoch, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1_048_576:
        raise ValueError('Walsin index size invalid')
    text = raw.decode('utf-8-sig', 'strict')
    body, closing, trailer = text.rpartition('</html>')
    if not closing or '</html>' in body:
        raise ValueError('Walsin index incomplete')
    # The observed F5 timing script follows </html>. Do not execute it or use
    # its cookies; permit only this closed trailing element, not another page.
    if trailer.strip():
        tail = BeautifulSoup(trailer, 'html.parser')
        nodes = [n for n in tail.contents if str(n).strip()]
        if (len(nodes) != 1 or nodes[0].name != 'script' or nodes[0].get('id') != 'f5_cspm'
                or set(nodes[0].attrs) != {'id'} or not trailer.rstrip().endswith('</script>')):
            raise ValueError('Walsin index trailing content unqualified')
    soup = BeautifulSoup(body+closing, 'html.parser')
    if not soup.title or soup.title.get_text(' ', strip=True) != 'Investor Conference – Walsin Lihwa':
        raise ValueError('Walsin index publisher changed')
    current = _one(soup, '#investor-conference-tabContent > #pills-investor-conference')
    if _one(current, 'h3').get_text(' ', strip=True) != 'Quarterly Conference Info':
        raise ValueError('Walsin current section changed')
    rows = current.select('table > tbody > tr')
    fields = {}
    for row in rows:
        cells = row.select(':scope > td')
        if len(cells) != 2:
            raise ValueError('Walsin event shape invalid')
        key = cells[0].get_text(' ', strip=True)
        if key in fields:
            raise ValueError('Walsin duplicate event field')
        fields[key] = cells[1]
    if set(fields) != {'Event Title', 'Event Date', 'Event Time', 'Video Link', 'Conference Files'}:
        raise ValueError('Walsin event fields changed')
    if (fields['Event Title'].get_text(' ', strip=True) != 'Quarterly Conference Info'
            or fields['Event Date'].get_text(' ', strip=True) != '2026-08-07'
            or fields['Event Time'].get_text(' ', strip=True) != '4:00 pm Taipei Time Zone'):
        raise ValueError('Walsin current event unqualified')
    event = date(2026, 8, 7)
    if not 0 <= (_today(as_of_epoch)-event).days <= 370 or not event <= _today(epoch) <= _today(as_of_epoch):
        raise ValueError('Walsin current event date invalid')
    from urllib.parse import quote
    materials = fields['Conference Files'].select('a')
    presentations = [a for a in materials if a.get_text(' ', strip=True) == 'Presentation']
    if (len(presentations) != 1 or presentations[0].has_attr('onclick')
            or quote(presentations[0].get('href', ''), safe=':/%') != PDF_URL):
        raise ValueError('Walsin published original changed')
    history = _one(soup, '#pills-investor-conference-history')
    history_rows = history.select('table > tbody > tr')
    if not 30 <= len(history_rows) <= 1000:
        raise ValueError('Walsin historical listing incomplete')
    # Do not silently pick the old qualified PDF if another newer event appears.
    for row in history_rows:
        cells = row.select(':scope > td')
        day = cells[0].get_text(' ', strip=True) if cells else ''
        if len(cells) != 4 or not re.fullmatch(r'20\d{2}/\d{2}/\d{2}', day):
            raise ValueError('Walsin history shape changed')
        if date.fromisoformat(day.replace('/', '-')) >= event:
            raise ValueError('Walsin newer or ambiguous history event')
    return {'title': '華新2026Q2官方法說簡報', 'period_label': '2026Q2', 'pdf_url': PDF_URL,
            'event_date': event.isoformat(), 'event_time': '16:00', 'event_timezone': 'Asia/Taipei',
            'index_record_count': len(history_rows)+1,
            'selection_policy': 'current_issuer_event_table_exact_original_and_no_newer_history'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('Walsin original revision is not qualified')
    try:
        native = extract_walsin_presentation_pages(raw, timeout_seconds=min(10., deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 11 or len(native['pages']) != 11
            or [p['page_number'] for p in native['pages']] != list(range(1, 12))
            or tuple(sha256(p['text'].encode()).hexdigest() for p in native['pages']) != PAGE_TEXT_SHA256
            or native['content_sha256'] != KNOWN_SHA or selected['period_label'] != '2026Q2'
            or selected['event_date'] != '2026-08-07'):
        raise ValueError('Walsin original pages unverified')
    return native


def _context(selected, native, proof):
    doc = {'document_id': '1605:'+selected['event_date']+':'+KNOWN_SHA[:16], 'ticker': TICKER,
           'source': PROVIDER, 'source_type': 'issuer_official', 'document_kind': 'presentation',
           'projection_policy': PROJECTION_POLICY, 'title': selected['title'], 'url': PDF_URL, 'language': 'en',
           'event_date': selected['event_date'], 'event_date_basis': 'issuer_current_event_table_and_pdf_cover',
           'event_time': selected['event_time'], 'event_timezone': selected['event_timezone'],
           'event_status': 'published_past_material_not_independently_occurrence_verified',
           'content_period': '', 'content_periods': ['2026Q2', '2026Q1 and2025Q2 comparisons', '2026Q3 and longer-term outlook'],
           'published_at': None, 'material_file_date': None, 'retrieved_at_epoch': proof['pdf']['retrieved_at'],
           'content_sha256': KNOWN_SHA, 'page_count': 11, 'pages': native['pages'], 'binary_complete': True,
           'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial',
           'full_content_coverage_verified': False, 'full_visual_content_verified': False,
           'financial_statement_complete': False, 'missing_text_pages': [], 'garbled_pages': [],
           'parser_version': native['parser_version'], 'known_native_text_omissions': [],
           'excluded_native_text_pages': [4, 5, 6, 7, 11], 'role_page_allowlist': [1, 2, 3, 8, 9, 10],
           'visual_semantics_caution': 'Complete native text is not complete visual semantics. Chart pages5–7 have not been qualified for numeric pairing; excluded from role views.',
           'native_editorial_caution': 'Page4 original shows25Q2 EBITDA27 but26Q2 EBITDA3.4 with statedYoY+26%. Preserve original; do not correct27 to2.7 or infer a ratio. Entire page excluded.',
           'financial_scope_caution': 'Management presentation selected items, not complete statements or five-year9fact history. Page8 inventory includes purchase prepayments; PPE includes intangible assets.',
           'unit_scope_caution': 'Pages8–9 amounts are NTD billions, not millions; percentages and days/ratios are separate. Page9 parentheses are outflows; dash is not verified zero. Keep positive1.5 beside original Cash used in Operating Activities label.',
           'cash_scope_caution': 'Page9 ending cash17.9 equals balance-sheet cash17.7 plus designated hedging financial assets0.2; do not conflate balances or infer free cash flow from selected items.',
           'period_scope_caution': 'Event2026-08-07 differs from Q2 financials and Q3 outlook. HTTP modification and upload directory are not first publication. Scope is mixed, not a complete fiscal year.',
           'forward_looking_caution': 'Page2: current expectations carry uncertainty and no update duty except law. Page10 statements are company expectations as of event, not current verified outcomes; subsidiary claims keep their scope.',
           'index_video_caution': 'Video Link points to26Q1 although current event/PDF are26Q2. Video and actual Q&A have not been acquired or verified.',
           'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False,
           'publisher_copyright': 'Copyright © 2026 Walsin Lihwa Corp. All Rights Reserved.',
           'response_reuse_policy': 'Always native issuer index/PDF acquisition; immutable private audit originals, no success-cache reuse'}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': '', 'title': selected['title'],
            'source': PROVIDER, 'source_url': INDEX_URL, 'summary': '', 'transcript_excerpt': '',
            'transcript_available': False, 'materials': [{'url': PDF_URL, 'kind': 'presentation', 'language': 'en'}],
            'documents': [doc], 'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'selection_policy': selected['selection_policy'], 'fetched_at_epoch': proof['pdf']['retrieved_at'],
            'walsin_conference_receipt': proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_walsin(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['walsin_conference_receipt']
        if set(proof) != {'policy','identity','index','pdf','selected'} or proof['policy'] != POLICY:
            return False
        identity_url=proof['identity']['source_url']
        parse_master(original_bytes(proof['identity'],identity_url,max_age=max_age),proof['identity']['retrieved_at'],identity_url)
        selected = select_presentation(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],PDF_URL,max_age=max_age)
        expected = _context(selected,native_presentation(raw,selected,deadline),proof)
        for key,url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(expected,sort_keys=True,allow_nan=False)
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False


def fetch_walsin_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_walsin(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'walsin_presentation_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url']);_check(deadline)
        raw,index = http.get_receipt(INDEX_URL);selected = select_presentation(raw,index['retrieved_at']);_check(deadline)
        raw,pdf = http.get_receipt(PDF_URL);native = native_presentation(raw,selected,deadline)
        proof = {'policy':POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected}
        value = _context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value = deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        for key,url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=RAW_TTL)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        details.update(walsin_originals_verified=True,coverage_status='qualified_partial_presentation',
                       cache_hit=pdf['cache_hit'],stale=False,fetched_at_epoch=pdf['retrieved_at'],message=NOTE)
        if diagnostics is not None:diagnostics.update(details)
        # Diagnostic delivery and scheduler delay belong to the same budget.
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        _check(deadline)
    except Exception as original:
        if time.monotonic() >= deadline:
            exc = SourceResponseError('timeout')
        else:
            exc = original if isinstance(original,SourceResponseError) else SourceResponseError('parse_error')
        for key in ('coverage_status','cache_hit','stale','fetched_at_epoch'):
            details.pop(key,None)
            exc.diagnostic.pop(key,None)
            if diagnostics is not None:diagnostics.pop(key,None)
        details.update(walsin_originals_verified=False,error_kind=exc.error_kind,status='error',
                       component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original
    return value


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data,dict) or data.get('ticker') != ticker or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):return False
    identity = data.get('company_identity')
    if identity is None:identity = {}
    if not isinstance(identity,dict):return False
    for key,expected in [('ticker',TICKER),('stock_id','1605'),('official_name','華新'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'華新',LEGAL.casefold(),'walsin','walsin lihwa corporation','walsin lihwa corp','walsin lihwa corp.'}
    aliases = names | {'1605','1605.tw'}
    def good_name(name, allowed):
        return isinstance(name,str) and all(s.strip().casefold() in allowed for s in name.split(' / '))
    for key in ('company_name','raw_company_name'):
        if data.get(key) is not None and not good_name(data[key],names):return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows = identity.get(key,[])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows):return False
        if key != 'forbidden_aliases' and any(not good_name(s,aliases if key=='allowed_aliases' else names) for s in rows):return False
    for key in ('display_name','company_name'):
        if identity.get(key) not in (None,'') and not good_name(identity[key],names):return False
    forbidden = {part.strip('* ').strip().casefold() for s in identity.get('forbidden_aliases',[]) for part in s.split(' / ')}
    return not (aliases & forbidden)


def is_marked(value):
    return isinstance(value,dict) and ('walsin_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
