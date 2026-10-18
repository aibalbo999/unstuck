"""Qualified CSC September presentation, preserving mixed financial and visual scopes."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
import re
import time
import unicodedata
import zlib
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError
from .csc_conference_transport import (
    ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, CHINESE_INDEX_URL, CHINESE_PDF_URL,
    MOPS_IIH_URL, PROVIDER,
    RAW_TTL, original_bytes, valid_expiry, is_legacy_master,
)
from . import conference_issuer_master as master_identity

TICKER = '2002.TW'
LEGAL = '中國鋼鐵股份有限公司'
UBN = '30414175'
LEGACY_POLICY = 'csc-original-presentation-v1'
POLICY = 'csc-original-presentation-v2'
MOPS_POLICY = 'csc-mops-month-index-presentation-v1'
MOPS_PROVIDER = 'MOPS published presentation'
CHINESE_POLICY = 'csc-chinese-issuer-archive-presentation-v1'
CHINESE_PROVIDER = 'CSC Chinese official conference presentation'
PROJECTION_POLICY = 'csc-presentation-role-v1'
KNOWN_SHA = 'e0f2551660c648e950242d8a8de0c40225d43c5c7409149788a721765e98dc05'
CHINESE_SHA = 'f801da2a4a8fa92512c1d4265c2a6a35c70164bcae909fea45837665a94883e4'
NOTE = ('中鋼官方2026年9月23日英文法說簡報，35頁，並非逐字稿或問答紀錄。'
        '主要財务口徑為2026上半年；第11頁2026年1–7月及7月為preliminary results，不是2026第三季實績或經查核年度財報。'
        '中鋼單體、合併集團、子公司、部門及外部產業資料不可混用；各頁期間、as-of日期、單位與預測必須保留。'
        '原生文字與已核實字形轉換不代表圖表顏色、位置及關聯完整，第26頁原文同時存在May與Aug口徑，不能自動調和。'
        '第3頁Safe Harbor聲明展望受風險及假設影響且不保證更新；不將2026–2029等計畫及預測寫為已發生。'
        '發布日及首次公布時間未知，不由HTTP Last-Modified、檔名或取得時間推定。')
CHINESE_NOTE = ('中鋼官方2026年9月23日中文法說簡報，35頁，並非逐字稿或問答紀錄。'
                '主要財務口徑為2026上半年；第11頁2026年7月及累計自結數不是2026第三季實績或經查核年度財報。'
                '中鋼個體、合併集團、子公司、部門及外部產業資料不可混用；各頁期間、單位與預測必須保留。'
                '原生文字完整不代表圖表顏色、位置及關聯完整。第3頁前瞻性聲明適用全份簡報，不把計畫及預測寫成已發生。'
                '發布日及首次公布時間未知，不由HTTP Last-Modified、檔名或取得時間推定。')


def supports_csc(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2002', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_csc_presentation_pages(raw, *, timeout_seconds):
    # Lazy import keeps unsupported stocks independent of the source-specific worker.
    from csc_presentation_pdf_reader import extract_csc_presentation_pages as extract
    return extract(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, url=MASTER_URL):
    rows = master_identity.master_rows(raw,epoch,url)
    matched = [r for r in rows if r.get('公司代號') == '2002']
    if len(matched) != 1:
        raise ValueError('CSC master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '中鋼', '營利事業統一編號': UBN, '網址': 'http://www.csc.com.tw'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'CSC'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('CSC master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('CSC master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '中鋼', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('CSC index section ambiguous')
    return values[0]


def select_presentation(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1_048_576:
        raise ValueError('CSC index size invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    if not soup.title or soup.title.get_text(' ', strip=True) != 'CSC':
        raise ValueError('CSC registered publisher unverified')
    if _one(soup, '#pst_tit_content .pst_tit h1').get_text(' ', strip=True) != 'Latest Presentation':
        raise ValueError('CSC latest presentation role unverified')
    root = _one(soup, '#pst_ctn_main')
    card = _one(root, ':scope > .pst_top_r')
    if _one(card, '.pst_top_wTitle').get_text(' ', strip=True) != 'Latest Presentation':
        raise ValueError('CSC latest presentation marker unverified')
    displayed = _one(card, '.pst_top_wDay').get_text(' ', strip=True)
    # Bind the exact, qualified revision; a new latest event needs new body qualification.
    if displayed != 'September 23, 2026.':
        raise ValueError('CSC latest event differs from qualified original')
    day = date(2026, 9, 23)
    if day > _today(epoch) or not 0 <= (_today() - day).days <= 370:
        raise ValueError('CSC event future or stale')
    announcement = _one(root, ':scope > .pst_top_l .pst_top_lText').get_text(' ', strip=True)
    expected = 'CSC attends online investor conference held by IBF Securities Co., Ltd. on September 23, 2026.'
    if not announcement.startswith(expected) or 'Welcome downloading.' not in announcement:
        raise ValueError('CSC event announcement or public-download basis unverified')
    if re.findall(r'[A-Z][a-z]+ \d{1,2}, 20\d{2}', announcement) != ['September 23, 2026']:
        raise ValueError('CSC announcement dates ambiguous')
    link = _one(card, ':scope > .pst_top_rDownlaod a[href]')
    if link['href'] != 'pdf/2026Sep23.pdf' or link.get_text(' ', strip=True) != 'Download':
        raise ValueError('CSC exact published original unverified')
    return {'event_date': day.isoformat(), 'event_time': None, 'event_timezone': None,
            'event_location': 'Online; hosted by IBF Securities Co., Ltd.',
            'title': '中鋼2026年9月23日官方英文法說簡報', 'pdf_url': PDF_URL,
            'language': 'en',
            'period': '',
            'selection_policy': 'issuer_latest_presentation_card_and_announcement_match_exact_qualified_PDF'}


def select_chinese_presentation(raw, epoch):
    """Select only the exact archived Chinese copy of the qualified CSC event."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1_048_576:
        raise ValueError('CSC Chinese archive size invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    if not soup.title or soup.title.get_text(' ', strip=True) != '中鋼公司-CSC':
        raise ValueError('CSC Chinese archive publisher unverified')
    main = _one(soup, '#pst_ctn_main')
    heading = _one(main, ':scope > #pst_ctn_tit')
    heading_text = re.sub(r'\s+', ' ', heading.get_text(' ', strip=True))
    if not heading_text.startswith('近期法說簡報') or '點擊下載法說簡報' not in heading_text:
        raise ValueError('CSC Chinese archive role unverified')
    links = main.find_all('a', href='pdf/2026Sep23.pdf')
    if len(links) != 1:
        raise ValueError('CSC Chinese archive original link ambiguous')
    year_row = links[0].find_parent('li')
    if year_row is None:
        raise ValueError('CSC Chinese archive original row missing')
    year_heading = _one(year_row, ':scope > .pst_ctn_textYy')
    if re.sub(r'\s+', '', year_heading.get_text(' ', strip=True)) != '115年度':
        raise ValueError('CSC Chinese archive year mismatch')
    row = links[0].find_parent('tr')
    if row is None:
        raise ValueError('CSC Chinese archive original row missing')
    cells = row.find_all('td', recursive=False)
    if (len(cells) != 3 or cells[0].get_text(' ', strip=True) != '線上'
            or cells[1].get_text(' ', strip=True) != '09月23日'
            or cells[2].find_all('a', href=True) != [links[0]]):
        raise ValueError('CSC Chinese archive event row mismatch')
    day = date(2026, 9, 23)
    if day > _today(epoch) or not 0 <= (_today() - day).days <= 370:
        raise ValueError('CSC Chinese archive event future or stale')
    return {'event_date': day.isoformat(), 'event_time': None, 'event_timezone': None,
            'event_location': '線上', 'title': '中鋼2026年9月23日中文法說簡報',
            'source_provider': CHINESE_PROVIDER, 'source_url': CHINESE_INDEX_URL,
            'pdf_url': CHINESE_PDF_URL, 'language': 'zh', 'period': '',
            'event_date_basis': 'CSC Chinese issuer archive year/date row and exact PDF cover',
            'selection_policy': 'issuer_archive_2026_year_and_exact_20260923_original'}


def _mops_month_candidates(iih_raw, epoch):
    from .twse_iih_conference_notice import parse_iih_candidates

    payload = json.loads(iih_raw.decode('utf-8-sig', 'strict'))
    parsed = parse_iih_candidates(payload, TICKER, today=_today(epoch))
    if not parsed['month_candidates']:
        raise ValueError('MOPS conference month index unavailable')
    return parsed


def select_mops_presentation(iih_raw, month_raw, iih_epoch, month_epoch):
    """Select the latest completed CSC PDF from exact official MOPS index rows."""
    from .twse_iih_conference_notice import parse_month_index_page

    parsed = _mops_month_candidates(iih_raw, iih_epoch)
    candidate = parsed['month_candidates'][0]
    records = parse_month_index_page(
        month_raw, ticker=TICKER, issuer_name=parsed['issuer_name'], candidate=candidate,
        today=_today(month_epoch),
    )
    if not records:
        raise ValueError('MOPS conference month contains no completed event')
    event = records[0]
    materials = [item for item in event.get('materials', [])
                 if isinstance(item, dict) and item.get('label') == '英文簡報檔案']
    if len(materials) != 1:
        raise ValueError('MOPS English presentation link is ambiguous')
    pdf_url = str(materials[0].get('url') or '')
    filename = pdf_url.rsplit('/', 1)[-1]
    match = re.fullmatch(r'2002(20\d{6})E\d{3}\.pdf', filename)
    if (not match or pdf_url != 'https://emops.twse.com.tw/nas/STR/' + filename
            or match[1] != candidate['announcement_date'].replace('-', '')):
        raise ValueError('MOPS presentation file does not match the announced issuer row')
    return {
        'event_date': event['date'], 'event_time': event.get('time'),
        'event_timezone': 'Asia/Taipei', 'event_location': None,
        'title': f"{event['title']} {event['date']} (English presentation)",
        'pdf_url': pdf_url, 'period': '',
        'source_provider': MOPS_PROVIDER,
        'event_date_basis': 'TWSE English IIH issuer index and exact MOPS month row',
        'selection_policy': 'official_TWSE_IIH_and_MOPS_month_row_match_exact_English_PDF',
    }, candidate['month_index_url']


def native_presentation(raw, selected, deadline):
    _check(deadline)
    language = selected.get('language', 'en')
    expected_sha = CHINESE_SHA if language == 'zh' else KNOWN_SHA
    if sha256(raw).hexdigest() != expected_sha:
        raise ValueError('CSC original revision is not qualified')
    try:
        native = extract_csc_presentation_pages(raw, timeout_seconds=min(10., deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    pages = native['pages']
    def compact(text):
        return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))
    cover = '2026年9月23日' if language == 'zh' else 'September 23, 2026'
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 35 or len(pages) != 35
            or [p['page_number'] for p in pages] != list(range(1, 36))
            or native['content_sha256'] != expected_sha
            or not isinstance(native.get('csc_glyph_evidence'), dict) or not native['csc_glyph_evidence']
            or cover not in re.sub(r'\s+', ' ', pages[0]['text']).strip()
            or selected['period'] != '' or selected['event_date'] != '2026-09-23'):
        raise ValueError('CSC qualified native pages or glyph evidence unverified')
    disclaimer = re.sub(r'\s+', ' ', pages[2]['text'])
    if language == 'zh':
        chinese_disclaimer = compact(pages[2]['text'])
        if (any(compact(s) not in chinese_disclaimer for s in ['本節所述的警告聲明適用於本簡報所載的所有前瞻性陳述',
                '受到風險及不確定性因素影響', '本公司並不負責隨時提醒或更新'])
                or any(compact(s) not in compact(pages[10]['text']) for s in ['2026Q1', '2026Q2', '2026年7月', '*自結數'])
                or '2026.H1' not in compact(pages[11]['text']) or '中鋼個體' not in compact(pages[11]['text'])
                or '中鋼集團' not in compact(pages[31]['text']) or '2026.H1' not in compact(pages[33]['text'])
                or '新臺幣仟元' not in compact(pages[33]['text'])
                or '營運實績' not in compact(pages[25]['text']) or '累計至2026年8月' not in compact(pages[25]['text'])
                or '5月' in compact(pages[25]['text'])):
            raise ValueError('CSC Chinese content period, issuer scopes or limitations unverified')
    elif (any(s not in disclaimer for s in ['Safe Harbor Statement', 'forward-looking statements',
            'actual outcomes and results to differ materially', 'disclaim any obligation to update or alter'])
            or any(s not in pages[10]['text'] for s in ['2026.1~7', '*preliminary results', 'Consolidated Financial Performance'])
            or 'Standalone' not in pages[11]['text'] or 'CSC' not in pages[31]['text']
            or '2026. H1' not in pages[33]['text'] or 'NTD Thousands' not in pages[33]['text']
            or 'until the end of May 2026' not in pages[25]['text'] or 'as of Aug.' not in pages[25]['text']):
        raise ValueError('CSC content period, issuer scopes or limitations unverified')
    return native


def _context(selected, native, proof):
    provider = selected.get('source_provider', PROVIDER)
    source_url = selected.get('source_url', INDEX_URL)
    pdf_url = selected.get('pdf_url', PDF_URL)
    language = selected.get('language', 'en')
    chinese = language == 'zh'
    note = CHINESE_NOTE if chinese else NOTE
    doc = {'document_id': '2002:'+selected['event_date']+':'+native['content_sha256'][:16],
           'ticker': TICKER, 'source': provider, 'source_type': 'issuer_official', 'document_kind': 'presentation',
           'projection_policy': PROJECTION_POLICY, 'title': selected['title'], 'url': pdf_url, 'language': language,
           'event_date': selected['event_date'], 'event_date_basis': selected.get('event_date_basis', 'official_latest_index_announcement_and_PDF_cover'),
           'event_time_Taipei': selected.get('event_time'), 'event_timezone': selected.get('event_timezone'), 'event_location': selected.get('event_location'),
           'event_status': 'published_past_event_not_independently_occurrence_verified',
           'content_period': '',
           'content_periods': (['2026H1', '2026 July and YTD preliminary self-reported values', 'historical and forward-looking periods']
                               if chinese else ['2026H1', '2026 Jan-Jul preliminary', 'historical and forward-looking periods']),
           'financial_scope_caution': ('Mixed presentation periods: H1 financials, July and YTD preliminary self-reported values, page-specific observations, history and forward-looking plans; not Q3 actual.'
                                       if chinese else 'Mixed presentation periods: H1 financials, January-July preliminary results, page-specific observations, history and forward-looking plans; not Q3 actual.'), 'published_at': None, 'material_file_date': None,
           'retrieved_at_epoch': proof['pdf']['retrieved_at'], 'content_sha256': native['content_sha256'],
           'page_count': native['page_count'], 'pages': native['pages'], 'binary_complete': True,
           'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial',
           'full_content_coverage_verified': False, 'missing_text_pages': native['empty_pages'],
           'garbled_pages': native['garbled_pages'], 'parser_version': native['parser_version'],
           'csc_glyph_evidence': deepcopy(native['csc_glyph_evidence']),
           'known_native_text_omissions': [{'page_number': p, 'issue': 'visual_chart_color_geometry_or_relations_not_fully_represented_in_text'}
                                         for p in (5,6,7,8,9,10,11,12,13,14,15,16,17,20,21,22,23,25,26,27,28,32,34,35)],
           'subsidiary_scope_caution': 'CSC standalone, consolidated group, subsidiaries, departments and external industry statistics are distinct.',
           'unaudited_financial_caution': ('Page11 July and YTD amounts are self-reported; H1 slide data is not an audited annual financial statement or Q3 actual.'
                                           if chinese else 'Page11 2026.7 and 2026.1~7 are preliminary results; H1 slide data is not an audited annual financial statement or Q3 actual.'),
           'forward_looking_caution': ('Page3 forward-looking statement applies to projections and plans; future capacity, sales, earnings and green energy targets are not realized facts.'
                                       if chinese else 'Page3 Safe Harbor applies to projections and plans; future capacity, sales, earnings and green energy targets are not realized facts.'),
           'period_scope_caution': ('Main financial period is 2026H1; July and YTD self-reported values and page-specific dates differ. Page26 reports solar operating figures accumulated through August 2026.'
                                   if chinese else 'Main financial period is 2026H1; page11 preliminary January-July and page-specific as-of dates differ. Page26 May and August labels remain unreconciled.'),
           'q_and_a_transcript_available': False, 'disclaimer_pages': [3], 'commercial_reuse_permission_verified': False}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': '', 'title': selected['title'],
            'source': provider, 'source_url': source_url, 'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'url': pdf_url, 'kind': 'presentation', 'language': language}], 'documents': [doc],
            'coverage_status': 'partial', 'coverage_notes': [note], 'selection_policy': selected['selection_policy'],
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'csc_conference_receipt': proof}


def _fetch_mops_mirror(http, identity, deadline):
    raw_iih,iih = http.get_receipt(MOPS_IIH_URL)
    candidates = _mops_month_candidates(raw_iih,iih['retrieved_at'])['month_candidates']
    if not candidates:
        raise SourceResponseError('conference_month_index_empty')
    month_url = candidates[0]['month_index_url']
    raw_month,month = http.get_receipt(month_url)
    selected,selected_month_url = select_mops_presentation(
        raw_iih,raw_month,iih['retrieved_at'],month['retrieved_at'])
    if selected_month_url != month_url:
        raise SourceResponseError('conference_month_candidate_mismatch')
    raw_pdf,pdf = http.get_receipt(selected['pdf_url'])
    native = native_presentation(raw_pdf,selected,deadline)
    selected = {**selected,'source_url':month_url}
    proof = {'policy':MOPS_POLICY,'identity':identity,'iih_index':iih,'index':month,
             'pdf':pdf,'selected':selected}
    return selected,native,proof


def _fetch_chinese_archive(http, identity, deadline):
    raw_index,index = http.get_receipt(CHINESE_INDEX_URL)
    selected = select_chinese_presentation(raw_index,index['retrieved_at'])
    raw_pdf,pdf = http.get_receipt(selected['pdf_url'])
    native = native_presentation(raw_pdf,selected,deadline)
    selected = {**selected,'source_url':CHINESE_INDEX_URL}
    proof = {'policy':CHINESE_POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected}
    return selected,native,proof


def _recover_presentation(http, identity, deadline, details, primary_error):
    """Use MOPS first; a pinned issuer-archive copy may recover strict index mismatch."""
    details.update(csc_mops_fallback=True,csc_fallback_trigger_kind=primary_error.error_kind)
    try:
        selected,native,proof = _fetch_mops_mirror(http,identity,deadline)
    except SourceResponseError as exc:
        recoverable = {'timeout','transport_error','server_error','conference_month_issuer_or_period_mismatch',
                       'conference_month_candidate_mismatch','conference_month_index_empty','conference_month_page_unrecognized'}
        if exc.error_kind not in recoverable:
            raise
        selected,native,proof = _fetch_chinese_archive(http,identity,deadline)
        details.update(actual_provider=CHINESE_PROVIDER,csc_chinese_fallback=True,
                       csc_mops_fallback_error_kind=exc.error_kind)
    else:
        details.update(actual_provider=MOPS_PROVIDER)
    return selected,native,proof


def _originals_fresh(proof, max_age):
    observed = time.time()
    keys = ('identity','iih_index','index','pdf') if proof.get('policy') == MOPS_POLICY else ('identity','index','pdf')
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and valid_expiry(proof[k],observed)
               for k in keys)


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_csc(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['csc_conference_receipt']
        if proof.get('policy') == MOPS_POLICY:
            if set(proof) != {'policy','identity','iih_index','index','pdf','selected'}:
                return False
        elif proof.get('policy') in (POLICY,LEGACY_POLICY,CHINESE_POLICY):
            if set(proof) != {'policy','identity','index','pdf','selected'}:
                return False
        else:
            return False
        identity=proof['identity']
        legacy=is_legacy_master(identity)
        if (proof['policy']==LEGACY_POLICY and not legacy
                or proof['policy'] in (POLICY,MOPS_POLICY,CHINESE_POLICY) and (legacy or not master_identity.is_shared(identity))
                or proof['policy'] not in (POLICY,LEGACY_POLICY,MOPS_POLICY,CHINESE_POLICY)):
            return False
        master_url=identity['source_url']
        parse_master(original_bytes(identity,master_url,max_age=max_age),identity['retrieved_at'],master_url)
        if proof['policy'] == MOPS_POLICY:
            iih_raw = original_bytes(proof['iih_index'],MOPS_IIH_URL,max_age=max_age)
            month_candidate = _mops_month_candidates(iih_raw,proof['iih_index']['retrieved_at'])['month_candidates'][0]
            month_url = month_candidate['month_index_url']
            month_raw = original_bytes(proof['index'],month_url,max_age=max_age)
            selected, selected_month_url = select_mops_presentation(
                iih_raw,month_raw,proof['iih_index']['retrieved_at'],proof['index']['retrieved_at'])
            if selected_month_url != month_url:
                return False
            selected['source_url'] = month_url
            pdf_url = selected['pdf_url']
        elif proof['policy'] == CHINESE_POLICY:
            selected = select_chinese_presentation(
                original_bytes(proof['index'],CHINESE_INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
            selected['source_url'] = CHINESE_INDEX_URL
            pdf_url = selected['pdf_url']
        else:
            selected = select_presentation(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
            pdf_url = PDF_URL
        selected_matches = selected == proof['selected']
        if not selected_matches and proof['policy'] == LEGACY_POLICY:
            # v1 receipts predate the explicit language label. Preserve exact
            # replay of that stored selection while keeping all other fields pinned.
            selected_matches = {k:v for k,v in selected.items() if k != 'language'} == proof['selected']
        if not selected_matches or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],pdf_url,max_age=max_age)
        expected = _context(selected,native_presentation(raw,selected,deadline),proof)
        originals = [('identity',proof['identity']['source_url']),('pdf',pdf_url)]
        originals += ([('iih_index',MOPS_IIH_URL),('index',month_url)] if proof['policy'] == MOPS_POLICY
                      else [('index',CHINESE_INDEX_URL)] if proof['policy'] == CHINESE_POLICY
                      else [('index',INDEX_URL)])
        for key,url in originals:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(expected,sort_keys=True,allow_nan=False)
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False


def fetch_csc_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_csc(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'csc_presentation_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url']);_check(deadline)
        primary_error = None
        try:
            raw,index = http.get_receipt(INDEX_URL)
        except SourceResponseError as exc:
            if exc.error_kind not in {'timeout','transport_error','server_error'}:
                raise
            primary_error = exc
        if primary_error is not None:
            selected,native,proof = _recover_presentation(http,identity,deadline,details,primary_error)
        else:
            selected = select_presentation(raw,index['retrieved_at'])
            _check(deadline)
            try:
                raw,pdf = http.get_receipt(PDF_URL)
            except SourceResponseError as exc:
                if exc.error_kind not in {'timeout','transport_error','server_error'}:
                    raise
                primary_error = exc
                selected,native,proof = _recover_presentation(http,identity,deadline,details,primary_error)
            else:
                native = native_presentation(raw,selected,deadline)
                proof = {'policy':POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected}
        value = _context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value = deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        pdf_url = selected.get('pdf_url',PDF_URL)
        originals = [('identity',proof['identity']['source_url']),('pdf',pdf_url)]
        originals += ([('iih_index',MOPS_IIH_URL),('index',selected['source_url'])]
                      if proof['policy'] == MOPS_POLICY else
                      [('index',CHINESE_INDEX_URL)] if proof['policy'] == CHINESE_POLICY else [('index',INDEX_URL)])
        for key,url in originals:
            original_bytes(proof[key],url,max_age=RAW_TTL)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        pdf_receipt = proof['pdf']
        details.update(csc_originals_verified=True,coverage_status='native_presentation_text_complete',
                       cache_hit=pdf_receipt['cache_hit'],stale=False,fetched_at_epoch=pdf_receipt['retrieved_at'],
                       message=CHINESE_NOTE if proof['policy'] == CHINESE_POLICY else NOTE)
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
        details.update(csc_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','2002'),('official_name','中鋼'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'中鋼',LEGAL,'csc','china steel corporation','china steel corp','china steel corp.'}
    aliases = names | {'2002','2002.tw'}
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
    return isinstance(value,dict) and ('csc_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
