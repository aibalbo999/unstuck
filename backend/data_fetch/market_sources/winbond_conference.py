"""Published Winbond presentation with explicit native visual and financial scope limits."""
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
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .winbond_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, valid_expiry

TICKER = '2344.TW'
LEGAL = '華邦電子股份有限公司'
UBN = '22099218'
POLICY = 'winbond-original-presentation-v1'
PROJECTION_POLICY = 'winbond-presentation-role-v1'
KNOWN_SHA = '8fea53d7b591124ce63c2ae1ae623d9494fece1dd052979812b75f166cc1ff3a'
NOTE = ('華邦電官方中文2026Q2法說簡報，並非逐字稿；第30頁僅Q&A標題，不含問答內容或影音核對。'
        '31頁原生文字完整取得不等於圖表語意完整；第18、24、29頁之顏色、圖形、座標及關聯不能由文字完整還原。'
        '第2頁免責明示財務資訊包含未經查核內容、僅供參考，展望受風險及假設影響且不保證實現或更新。'
        '母公司合併數、記憶體事業及第12–13頁新唐子公司口徑必須分開；Q2與上半年EPS不得混用。'
        '發布日及檔案首次公布時間未知；不由HTTP Last-Modified或取得時間推定。不覆寫正式年度財報或TTM。')


def supports_winbond(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2344', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Winbond master size invalid')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True)
    rows = list(reader); fields = reader.fieldnames
    if (not fields or len(fields) != len(set(fields)) or not 500 <= len(rows) <= 2000
            or any(None in r or any(v is None for v in r.values()) for r in rows)):
        raise ValueError('Winbond complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2344']
    if len(matched) != 1:
        raise ValueError('Winbond master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '華邦電', '營利事業統一編號': UBN, '網址': 'WWW.WINBOND.COM'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'WEC'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Winbond master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('Winbond master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '華邦電', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('Winbond index section ambiguous')
    return values[0]


def _period(title):
    match = re.fullmatch(r'(20\d{2})年第([一二三四])季法人說明會', title)
    if not match:
        raise ValueError('Winbond event period unverified')
    return match[1]+'Q'+str('一二三四'.index(match[2])+1)


def _event_day(value):
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', value):
        raise ValueError('Winbond event date malformed')
    return date.fromisoformat(value)


def _pdf_link(node):
    links = [a for a in node.select(':scope > div.download a[href]')
             if a.get_text(' ',strip=True) == '簡報' or a.get('title') == '簡報']
    if len(links) != 1 or links[0].get_text(' ',strip=True) != '簡報' or links[0].get('title') != '簡報':
        raise ValueError('Winbond presentation role unverified')
    if links[0]['href'] != '/export/sites/winbond/about-winbond/investor/investor-conference/2Q26-investor-conference_CH_Final.pdf':
        raise ValueError('Winbond exact published original unverified')
    return PDF_URL


def select_presentation(raw, epoch):
    if not isinstance(raw,bytes) or not 0 < len(raw) <= 1_048_576:
        raise ValueError('Winbond index size invalid')
    soup = BeautifulSoup(raw.decode('utf-8','strict'),'html.parser')
    if (not soup.title or soup.title.get_text(' ',strip=True) != '法人說明會 - 華邦電子'
            or _one(soup,'link[rel=canonical]').get('href') != 'https://www.winbond.com/hq/about-winbond/investor/investor-conference/?__locale=zh_TW'
            or _one(soup,'#ContentTitle > h1').get_text(' ',strip=True) != '法人說明會'):
        raise ValueError('Winbond registered publisher unverified')
    root = _one(soup,'article.containerBlk > div.investorBlk')
    hero = _one(root,':scope > div.d-flex > div.col-md-6:nth-child(2)')
    title = _one(hero,':scope > div.title').get_text(' ',strip=True)
    period = _period(title)
    details = hero.select(':scope > div.bg_grayblue > div.d-flex > div.col-md-4 > p')
    if len(details) != 3 or [p.find('span').get_text(strip=True) if p.find('span') else None for p in details] != ['日期','時間','地點']:
        raise ValueError('Winbond event metadata invalid')
    texts = [p.get_text(' ',strip=True) for p in details]
    day = _event_day(texts[0].removeprefix('日期 '));clock = texts[1].removeprefix('時間 ');place = texts[2].removeprefix('地點 ')
    if clock != '15:00' or not place:
        raise ValueError('Winbond event time or location invalid')
    _pdf_link(hero)
    announcement = _one(root,':scope > div.bg_grayblue').get_text(' ',strip=True)
    if ('華邦電子舉辦一一五年第二季法人說明會' not in announcement
            or re.findall(r'20\d{2}-\d{2}-\d{2}',announcement) != [day.isoformat()]
            or '時間： 下午 3:00' not in announcement or '地點： '+place not in announcement
            or 'IR@winbond.com' not in announcement):
        raise ValueError('Winbond event announcement disagrees')
    cards = _one(root,':scope > div.investor-list > ul').find_all('li',recursive=False)
    if not 1 <= len(cards) <= 100:
        raise ValueError('Winbond conference list invalid')
    events = {};eligible = []
    for card in cards:
        other_title = _one(card,':scope > div.title').get_text(' ',strip=True)
        other_period = _period(other_title)
        info = card.select(':scope > div.info > div.item')
        if len(info) != 2 or [p.find('span').get_text(strip=True) if p.find('span') else None for p in info] != ['時間:','地點:']:
            raise ValueError('Winbond conference row fields invalid')
        stamp = info[0].get_text(' ',strip=True).removeprefix('時間: ')
        m = re.fullmatch(r'(20\d{2}-\d{2}-\d{2}) (\d{2}:\d{2})',stamp)
        if not m:
            raise ValueError('Winbond listed event timestamp invalid')
        other_day = _event_day(m[1]);hour,minute = map(int,m[2].split(':'))
        if not 0 <= hour < 24 or not 0 <= minute < 60 or other_period[:4] != str(other_day.year) or other_day in events:
            raise ValueError('Winbond event identity ambiguous')
        event = {'day':other_day,'clock':m[2],'period':other_period,'title':other_title,
                 'place':info[1].get_text(' ',strip=True).removeprefix('地點: '),'node':card}
        events[other_day] = event
        # Include attachment-free events so newer published metadata cannot select the old deck.
        if other_day <= _today(epoch) and 0 <= (_today()-other_day).days <= 370:
            eligible.append(event)
    if not eligible:
        raise ValueError('Winbond eligible current event absent')
    latest = max(eligible,key=lambda e:e['day'])
    if (day.isoformat() != '2026-08-06' or period != '2026Q2' or latest['day'] != day
            or latest['clock'] != clock or latest['period'] != period or latest['title'] != title
            or latest['place'] != place or _pdf_link(latest['node']) != PDF_URL):
        raise ValueError('Winbond latest eligible event differs from qualified presentation')
    return {'event_date':day.isoformat(),'event_time':clock,'event_timezone':'Asia/Taipei','event_location':place,
            'period':period,'title':'華邦電2026年第二季官方法說簡報','pdf_url':PDF_URL,
            'selection_policy':'latest_eligible_published_event_including_attachment_free_rows_matches_hero_announcement_and_exact_PDF'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('Winbond original revision is not qualified')
    try:
        native = extract_pdf_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    pages = native['pages'];cover = re.sub(r'\s+',' ',pages[0]['text']);disclaimer = re.sub(r'\s+',' ',pages[1]['text'])
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 31 or len(pages) != 31 or native['content_sha256'] != KNOWN_SHA
            or '2026年第二季法說會' not in cover or 'Aug. 6th, 2026' not in cover
            or selected['period'] != '2026Q2' or selected['event_date'] != '2026-08-06'
            or any(s not in disclaimer for s in ['免責聲明','forward-looking statements','unaudited information',
                'for reference only','undertake no obligation','actual results could differ materially','shall also not constitute an offer'])
            or '新唐' not in pages[11]['text'] or '新唐' not in pages[12]['text']
            or re.sub(r'\s+',' ',pages[29]['text']).strip() != '30 Q & A'):
        raise ValueError('Winbond native period or limitations unverified')
    return native


def _context(selected, native, proof):
    doc = {'document_id':'2344:'+selected['event_date']+':'+native['content_sha256'][:16],
           'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
           'projection_policy':PROJECTION_POLICY,'title':selected['title'],'url':PDF_URL,'language':'zh-TW',
           'event_date':selected['event_date'],'event_date_basis':'official_index_hero_list_announcement_and_PDF_cover',
           'event_time_Taipei':'15:00','event_timezone':'Asia/Taipei','event_location':selected['event_location'],
           'event_status':'published_past_event_not_independently_occurrence_verified',
           'content_period':'2026Q2','published_at':None,'material_file_date':None,
           'retrieved_at_epoch':proof['pdf']['retrieved_at'],'content_sha256':native['content_sha256'],
           'page_count':native['page_count'],'pages':native['pages'],'binary_complete':True,
           'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
           'full_content_coverage_verified':False,'missing_text_pages':native['empty_pages'],
           'garbled_pages':native['garbled_pages'],'parser_version':native['parser_version'],
           'known_native_text_omissions':[{'page_number':p,'issue':'visual_content_not_fully_represented_in_native_text'} for p in (18,24,29)],
           'subsidiary_scope_caution':'合併母公司、記憶體事業及第12–13頁新唐子公司數據不可混同；Q2與上半年EPS不同。',
           'unaudited_financial_caution':'第2頁明示財務資訊包含未經查核資訊、僅供參考；不是經核對的年度財報。',
           'forward_looking_caution':'第15、21、22、29頁展望與預估不是已實現事實，公司不保證更新或實現。',
           'q_and_a_transcript_available':False,'disclaimer_pages':[2],'commercial_reuse_permission_verified':False}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026Q2','title':selected['title'],
            'source':PROVIDER,'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
            'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-TW'}],'documents':[doc],
            'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
            'fetched_at_epoch':proof['pdf']['retrieved_at'],'winbond_conference_receipt':proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and valid_expiry(proof[k],observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_winbond(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['winbond_conference_receipt']
        if set(proof) != {'policy','identity','index','pdf','selected'} or proof['policy'] != POLICY:
            return False
        parse_master(original_bytes(proof['identity'],MASTER_URL,max_age=max_age),proof['identity']['retrieved_at'])
        selected = select_presentation(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],PDF_URL,max_age=max_age)
        expected = _context(selected,native_presentation(raw,selected,deadline),proof)
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


def fetch_winbond_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_winbond(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'winbond_presentation_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at']);_check(deadline)
        raw,index = http.get_receipt(INDEX_URL);selected = select_presentation(raw,index['retrieved_at']);_check(deadline)
        raw,pdf = http.get_receipt(PDF_URL);native = native_presentation(raw,selected,deadline)
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
        details.update(winbond_originals_verified=True,coverage_status='native_presentation_text_complete',
                       cache_hit=pdf['cache_hit'],stale=False,fetched_at_epoch=pdf['retrieved_at'],message=NOTE)
    except Exception as original:
        if time.monotonic() >= deadline:
            exc = SourceResponseError('timeout')
        else:
            exc = original if isinstance(original,SourceResponseError) else SourceResponseError('parse_error')
        details.update(winbond_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','2344'),('official_name','華邦電'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'華邦電',LEGAL,'winbond','wec','winbond electronics corporation','winbond electronic corp','winbond electronics corp.','winbond electronics corp'}
    aliases = names | {'2344','2344.tw'}
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
    return isinstance(value,dict) and ('winbond_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
