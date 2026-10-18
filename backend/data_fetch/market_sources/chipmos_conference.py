"""Exact published ChipMOS translated transcript, with original-language limits."""
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
from .chipmos_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, valid_expiry

TICKER = '8150.TW'
LEGAL = '南茂科技股份有限公司'
UBN = '16130042'
POLICY = 'chipmos-original-translated-transcript-v1'
PROJECTION_POLICY = 'chipmos-translated-transcript-role-v1'
KNOWN_SHA = '712d554e7f3878cbcb7705bdfc7f9977f410661e176af6288f74fc3e81371d7a'
NOTE = ('南茂官方英文翻譯逐字稿，原會議語言為普通話；翻譯、實際會議及公司陳述未由影音或獨立來源驗證。'
        '原8頁及第7–8頁免責聲明完整保留：官方提示文字可能有重大錯誤、遺漏或不準確，應核原會議與申報文件。'
        '全8頁原生文字取得不代表所有視覺、口述內容或翻譯正確。主期別2026Q2，文內比較與展望另有期間，預測不得當成已實現。'
        '官網發布時間及檔名時間未知；不由下載時間推算發布日，不覆寫經核對的年度財報或TTM。')


def supports_chipmos(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'8150', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('ChipMOS master size invalid')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True)
    rows = list(reader); fields = reader.fieldnames
    if (not fields or len(fields) != len(set(fields)) or not 500 <= len(rows) <= 2000
            or any(None in r or any(v is None for v in r.values()) for r in rows)):
        raise ValueError('ChipMOS complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '8150']
    if len(matched) != 1:
        raise ValueError('ChipMOS master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '南茂', '營利事業統一編號': UBN, '網址': 'www.chipmos.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'ChipMOS'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('ChipMOS master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('ChipMOS master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '南茂', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _clock(text):
    return datetime.strptime(text, '%I:%M%p').strftime('%H:%M')


def select_transcript(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 200_000:
        raise ValueError('ChipMOS index size invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    canonical = soup.select('link[rel=canonical]')
    descriptions = soup.select('meta[name=description]')
    if (not soup.title or not soup.title.get_text().startswith('ChipMOS TECHNOLOGIES INC.')
            or len(canonical) != 1 or canonical[0].get('href') != 'https://www.chipmos.com/'
            or len(descriptions) != 1 or '(TWSE: 8150)' not in descriptions[0].get('content', '')):
        raise ValueError('ChipMOS index publisher unverified')
    roots = soup.select('div.page div.wrap-fs.inpage > div.wrap1140.page-content')
    if len(roots) != 1:
        raise ValueError('ChipMOS conference root ambiguous')
    root = roots[0]; headings = root.select(':scope > div.editbox > h4')
    boxes = root.select(':scope > div.editbox > div.meetingbox')
    if len(headings) != 1 or len(boxes) != 1 or headings[0].get_text(' ', strip=True) != 'Second Quarter 2026 Results Conference Call':
        raise ValueError('ChipMOS qualified event role absent')
    rows = boxes[0].find_all('ul', recursive=False)
    if len(rows) != 3:
        raise ValueError('ChipMOS current event metadata ambiguous')
    cells = [r.find_all('li', recursive=False) for r in rows]
    if any(len(r) != 2 for r in cells):
        raise ValueError('ChipMOS event field malformed')
    labels = [r[0].get_text(' ', strip=True) for r in cells]
    if labels != ['Date / Time：', 'Language：', 'English Translated Transcript:']:
        raise ValueError('ChipMOS transcript role or language unverified')
    if cells[1][1].get_text(' ', strip=True) != 'Mandarin (English Translated Replay)':
        raise ValueError('ChipMOS original language unverified')
    stamp = re.fullmatch(r'(20\d{2})-(\d{1,2})-(\d{1,2}) (\d{2}:\d{2}[AP]M) \(Taiwan time\)', cells[0][1].get_text(' ', strip=True))
    links = cells[2][1].find_all('a', href=True)
    if not stamp or len(links) != 1 or links[0]['href'] != '../../upfiles/ADUpload/english/en_pdf_1857263878.pdf':
        raise ValueError('ChipMOS transcript date or exact published URL invalid')
    day = date(*map(int, stamp.groups()[:3])); clock = _clock(stamp[4])
    headers = root.select('ul.ir-table.table-header.meeting')
    if len(headers) != 1 or [n.get_text(' ', strip=True) for n in headers[0].find_all('li', recursive=False)] != ['Event','Date','Time','Message','Press Release','Presentation','Audio Replay']:
        raise ValueError('ChipMOS conference table header invalid')
    cards = root.select('ul.ir-table.meeting:not(.table-header)')
    if not 1 <= len(cards) <= 100:
        raise ValueError('ChipMOS event table invalid')
    events = {}; eligible = []
    for card in cards:
        c = card.find_all('li', recursive=False)
        if len(c) != 7:
            raise ValueError('ChipMOS event row invalid')
        title, stamp2, clock2 = [n.get_text(' ', strip=True) for n in c[:3]]
        m = re.fullmatch(r'(20\d{2}) Q([1-4]) Results(?: Conference Call)?', title)
        if not m or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', stamp2):
            raise ValueError('ChipMOS event period or date invalid')
        other_day = date.fromisoformat(stamp2)
        if int(m[1]) != other_day.year:
            raise ValueError('ChipMOS event year mismatch')
        other_clock = _clock(clock2) if clock2 else None
        if other_day in events:
            raise ValueError('ChipMOS same-day event ambiguous')
        event = {'date': other_day, 'clock': other_clock, 'period': m[1] + 'Q' + m[2]}
        events[other_day] = event
        # Include even attachment-free rows: a newer event cannot silently use an old transcript.
        if other_day <= _today(epoch) and 0 <= (_today() - other_day).days <= 370:
            eligible.append(event)
    if not eligible:
        raise ValueError('ChipMOS eligible current event absent')
    latest = max(eligible, key=lambda e:e['date'])
    if (latest != {'date':day,'clock':clock,'period':'2026Q2'} or day.isoformat() != '2026-08-11'
            or clock != '15:00' or day > _today(epoch)):
        raise ValueError('ChipMOS current table/transcript mismatch or newer event')
    return {'event_date':day.isoformat(),'event_time':'15:00','event_timezone':'Asia/Taipei','period':'2026Q2',
            'title':'ChipMOS 2026Q2 official English translated conference transcript','pdf_url':PDF_URL,
            'selection_policy':'latest_eligible_published_event_even_without_attachment_matches_exact_transcript_metadata'}


def extract_chipmos_transcript_pages(raw, *, timeout_seconds=10):
    from chipmos_transcript_pdf_reader import extract_chipmos_transcript_pages as extract
    return extract(raw, timeout_seconds=timeout_seconds)


def native_transcript(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('ChipMOS original revision is not qualified')
    try:
        native = extract_chipmos_transcript_pages(raw, timeout_seconds=min(10., deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    pages = native['pages']; cover = re.sub(r'\s+', ' ', pages[0]['text']); disclaimer = re.sub(r'\s+', ' ', pages[6]['text'] + pages[7]['text'])
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 8 or len(pages) != 8
            or 'ChipMOS TECHNOLOGIES INC. 2Q 2026 Earnings Conference Call' not in cover
            or 'August 11, 2026, 3:00 PM Taiwan' not in cover
            or selected['period'] != '2026Q2' or selected['event_date'] != '2026-08-11'
            or any(s not in disclaimer for s in ['DISCLAIMER','in English of its Mandarin conference call',
                'forward-', 'Actual results may differ materially', 'MATERIAL ERRORS, OMISSIONS, OR INACCURACIES',
                'USERS ARE ADVISED TO REVIEW THE COMPANY\'S CONFERENCE CALL ITSELF'])):
        raise ValueError('ChipMOS native identity, period or disclaimer unverified')
    evidence = native.get('xref_validation_evidence')
    if (not isinstance(evidence,dict) or evidence.get('policy') != 'chipmos-2026q2-exact-xref-lf.v1'
            or evidence.get('complete_original_sha256') != KNOWN_SHA
            or evidence.get('raw_bytes_rewritten') is not False or evidence.get('xref_table_rewritten') is not False
            or evidence.get('other_parser_warnings_fatal') is not True or native['content_sha256'] != KNOWN_SHA):
        raise ValueError('ChipMOS exact-original xref qualification absent')
    return native


def _context(selected, native, proof):
    doc = {'document_id':'8150:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'transcript',
           'projection_policy':PROJECTION_POLICY,'title':selected['title'],'url':PDF_URL,'language':'en',
           'translated_from_language':'zh-TW','translation_accuracy_verified':False,
           'transcript_accuracy_independently_verified':False,'event_date':selected['event_date'],
           'event_date_basis':'official_index_metadata_table_and_transcript_cover','event_time_Taipei':'15:00',
           'event_timezone':'Asia/Taipei','event_status':'published_past_event_not_independently_occurrence_verified',
           'content_period':'2026Q2','published_at':None,'material_file_date':None,
           'retrieved_at_epoch':proof['pdf']['retrieved_at'],'content_sha256':native['content_sha256'],
           'page_count':native['page_count'],'pages':native['pages'],'binary_complete':True,
           'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
           'full_content_coverage_verified':False,'missing_text_pages':native['empty_pages'],
           'garbled_pages':native['garbled_pages'],'parser_version':native['parser_version'],
           'disclaimer_pages':[7,8],'commercial_reuse_permission_verified':False}
    # The specialized reader's exact-original xref proof is replayed, never guessed.
    doc['xref_validation_evidence'] = deepcopy(native['xref_validation_evidence'])
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026Q2','title':selected['title'],
            'source':PROVIDER,'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':True,
            'materials':[{'url':PDF_URL,'kind':'transcript','language':'en'}],'documents':[doc],
            'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
            'fetched_at_epoch':proof['pdf']['retrieved_at'],'chipmos_conference_receipt':proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and valid_expiry(proof[k],observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_chipmos(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['chipmos_conference_receipt']
        if set(proof) != {'policy','identity','index','pdf','selected'} or proof['policy'] != POLICY:
            return False
        parse_master(original_bytes(proof['identity'],MASTER_URL,max_age=max_age),proof['identity']['retrieved_at'])
        selected = select_transcript(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],PDF_URL,max_age=max_age)
        expected = _context(selected,native_transcript(raw,selected,deadline),proof)
        for key,url in [('identity',MASTER_URL),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(expected,sort_keys=True,allow_nan=False)
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False


def fetch_chipmos_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_chipmos(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'chipmos_transcript_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at']);_check(deadline)
        raw,index = http.get_receipt(INDEX_URL);selected = select_transcript(raw,index['retrieved_at']);_check(deadline)
        raw,pdf = http.get_receipt(PDF_URL);native = native_transcript(raw,selected,deadline)
        proof = {'policy':POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected}
        value = _context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value = deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        for key,url in [('identity',MASTER_URL),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=RAW_TTL)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        details.update(chipmos_originals_verified=True,coverage_status='native_translated_text_complete',
                       cache_hit=pdf['cache_hit'],stale=False,fetched_at_epoch=pdf['retrieved_at'],message=NOTE)
    except Exception as original:
        if time.monotonic() >= deadline:
            exc = SourceResponseError('timeout')
        else:
            exc = original if isinstance(original,SourceResponseError) else SourceResponseError('parse_error')
        details.update(chipmos_originals_verified=False,error_kind=exc.error_kind,status='error',
                       component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original
    if diagnostics is not None:diagnostics.update(details)
    return value


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data,dict) or data.get('ticker') != ticker or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):return False
    identity = data.get('company_identity')
    if identity is None:identity = {}
    if not isinstance(identity,dict):return False
    for key,expected in [('ticker',TICKER),('stock_id','8150'),('official_name','南茂'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'南茂',LEGAL,'chipmos','chipmos technologies inc.','chipmos technologies inc'}
    aliases = names | {'8150','8150.tw'}
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
    return isinstance(value,dict) and ('chipmos_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
