"""Exact issuer-owned Lien Hwa presentation; partial native text and covered-page limits."""
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
from .lienhwa_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, EVENT_HREF, EVENT_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '1229.TW'
LEGAL = '聯華實業控股股份有限公司'
UBN = '11996904'
POLICY = 'lienhwa-original-presentation-v1'
PROJECTION_POLICY = 'lienhwa-presentation-role-v1'
KNOWN_SHA = 'a265012e09c64c1e890600fe3fd4151c819b9bf869f7f78dea88ec58ff73e268'
NOTE = ('聯華官方2026Q2法說簡報，30頁原件完整；只有部分原生文字，非完整圖像、逐字稿、問答或完整財報。'
        '6頁(2/3/6/11/12/21)內容是圖像且沒有原生文字；p2免責為視覺核對限制摘要，未補入原生正文。'
        'p15三個實心圓依exact原件與字型核定；原生含被覆蓋的2027年底描述，原頁保持而角色整頁排除。'
        '首版角色只可引用1/22/24/25頁；p22是H1比較、p24負號與表圖重複保持、p25淨利佰萬元與EPS元/股不同。'
        '場次9/30與財務期間/首次發布分開；PDF metadata10/7及10/12不是首次發布日期。'
        '預測依當時預期、實際結果可能不同且無義務更新；不把投資事業、預測或圖像數字當已驗事實。'
        '官網index/event no-store/no-cache，每次新取原件；私存稽核，不主張商業再利用授權。')



def supports_lienhwa(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'1229', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_lienhwa_presentation_pages(raw, *, timeout_seconds):
    # Lazy import keeps unsupported stocks independent of the source-specific worker.
    from lienhwa_presentation_pdf_reader import extract_lienhwa_presentation_pages as extract
    return extract(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Lien Hwa master size invalid')
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
        raise ValueError('Lien Hwa complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '1229']
    if len(matched) != 1:
        raise ValueError('Lien Hwa master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '聯華', '營利事業統一編號': UBN, '網址': 'https://www.lhicholdings.com/'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'LHIHC'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Lien Hwa master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('Lien Hwa master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '聯華', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('Lien Hwa index section ambiguous')
    return values[0]


def _html(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:raise ValueError('Lien Hwa HTML size invalid')
    text=raw.decode('utf-8-sig','strict')
    if not text.rstrip().lower().endswith('</html>'):raise ValueError('Lien Hwa HTML incomplete')
    soup=BeautifulSoup(text,'html.parser')
    if _one(soup,'meta[property="og:site_name"]').get('content')!=LEGAL:raise ValueError('Lien Hwa publisher changed')
    return soup


def select_presentation(raw,epoch):
    soup=_html(raw)
    if not soup.title or soup.title.get_text(' ',strip=True)!='法說會資訊-'+LEGAL:raise ValueError('Lien Hwa index title invalid')
    if _one(soup,'meta[property="og:url"]').get('content')!=INDEX_URL:raise ValueError('Lien Hwa index URL invalid')
    listing=_one(soup,'#articleDataBox ul.newsAndDownloadList')
    rows=listing.select(':scope > li')
    if not 41<=len(rows)<=1000:raise ValueError('Lien Hwa complete index shape changed')
    periods=[]
    for row in rows:
        anchor=_one(row,'h3 a');title=anchor.get_text(' ',strip=True)
        match=re.match(r'^(20\d{2})年(?:第([一二三四])季)?',title)
        if not match or '法' not in title or '說明會' not in title:raise ValueError('Lien Hwa unknown index record')
        period=(int(match[1]),'一二三四'.index(match[2])+1 if match[2] else 0)
        periods.append((period,title,anchor))
    latest=max(p for p,_,_ in periods)
    expected=['2026年第二季 法人說明會簡報下載','2026年第二季法人說明會影音連結','2026年第二季 聯華實業控股法人(線上)說明會資訊']
    selected=[(t,a) for p,t,a in periods if p==latest]
    if latest!=(2026,2) or sorted(t for t,_ in selected)!=sorted(expected):raise ValueError('Lien Hwa latest event is unqualified or ambiguous')
    material=next(a for t,a in selected if t==expected[0]);event=next(a for t,a in selected if t==expected[2])
    if (material.get('href')!='javascript:;' or material.get('onclick')!="window.open('"+PDF_URL+"')"
            or event.get('href') not in {EVENT_HREF,EVENT_URL} or event.has_attr('onclick')):
        raise ValueError('Lien Hwa exact published original changed')
    if _today(epoch)>_today():raise ValueError('Lien Hwa index observation future')
    return {'title':'聯華2026Q2官方法說簡報','period_label':'2026Q2','pdf_url':PDF_URL,
            'event_published_href':event['href'],'event_url':EVENT_URL,'index_record_count':len(rows),
            'selection_policy':'latest_period_in_complete_published_index_and_exact_matching_event_original'}


def select_event(raw,epoch,selected):
    soup=_html(raw);title='2026年第二季 聯華實業控股法人(線上)說明會資訊'
    if (not soup.title or soup.title.get_text(' ',strip=True)!=title+'-'+LEGAL
            or _one(soup,'h1.articleTitle').get_text(' ',strip=True)!=title):raise ValueError('Lien Hwa event title invalid')
    scripts=soup.select('script[type="application/ld+json"]')
    if len(scripts)!=1:raise ValueError('Lien Hwa canonical event binding missing')
    breadcrumb=json.loads(scripts[0].get_text())
    items=breadcrumb.get('itemListElement')
    if (breadcrumb.get('@type')!='BreadcrumbList' or not isinstance(items,list) or len(items)!=2
            or items[1].get('item')!={'@id':EVENT_URL,'name':title}):raise ValueError('Lien Hwa event URL binding changed')
    lines=[n.get_text(' ',strip=True) for n in _one(soup,'div.textEditor').select(':scope > ul > li')]
    if len(lines)!=4 or lines[0]!='會議主題：聯華實業控股2026 Q2法人說明會 (線上)' or lines[2]!='會議地點：線上法說會':
        raise ValueError('Lien Hwa event fields changed')
    match=re.fullmatch(r'會議時間：(20\d{2})年(\d{2})月(\d{2})日\(([一二三四五六日])\) (\d{2})點(\d{2})分',lines[1])
    if not match:raise ValueError('Lien Hwa event time missing')
    year,month,day=int(match[1]),int(match[2]),int(match[3]);event=date(year,month,day)
    hour,minute=int(match[5]),int(match[6])
    if (event.isoformat()!='2026-09-30' or '一二三四五六日'[event.weekday()]!=match[4]
            or (hour,minute)!=(15,30) or not 0<=(_today()-event).days<=370 or event>_today(epoch)):
        raise ValueError('Lien Hwa current event date unqualified')
    return {**selected,'event_date':event.isoformat(),'event_time':'15:30','event_timezone':'Asia/Taipei',
            'event_location':'線上法說會','event_name':'聯華實業控股2026 Q2法人說明會 (線上)'}


def native_presentation(raw, selected, deadline):
    from lienhwa_presentation_pdf_reader import glyph_evidence, PAGE_TEXT_SHA256
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('Lien Hwa original revision is not qualified')
    try:
        native = extract_lienhwa_presentation_pages(raw, timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    if (native['coverage_status'] != 'partial' or native['empty_pages'] != [2,3,6,11,12,21] or native['garbled_pages']
            or native['page_count'] != 30 or len(native['pages']) != 30
            or [p['page_number'] for p in native['pages']] != list(range(1,31))
            or tuple(sha256(p['text'].encode()).hexdigest() for p in native['pages']) != PAGE_TEXT_SHA256
            or native['content_sha256'] != KNOWN_SHA
            or json.dumps(native.get('lienhwa_glyph_evidence'),sort_keys=True,allow_nan=False) != json.dumps(glyph_evidence(),sort_keys=True)
            or selected['period_label'] != '2026Q2' or selected['event_date'] != '2026-09-30'):
        raise ValueError('Lien Hwa original pages or symbol proof unverified')
    return native


def _context(selected,native,proof):
    doc={'document_id':'1229:'+selected['event_date']+':'+KNOWN_SHA[:16],'ticker':TICKER,
         'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation','projection_policy':PROJECTION_POLICY,
         'title':selected['title'],'url':PDF_URL,'language':'zh-Hant','event_date':selected['event_date'],
         'event_date_basis':'issuer_event_page_and_cover_not_publication_date','event_time':selected['event_time'],
         'event_timezone':selected['event_timezone'],'event_location':selected['event_location'],'event_name':selected['event_name'],
         'event_status':'published_past_material_not_independently_occurrence_verified','content_period':'',
         'content_periods':['2026Q2 conference label','2026H1 and2025H1 revenue','2025Q2–2026Q2 quarterly financials','2021–2026Q2 NAV','2026.06.30 and2025.12.31 asset positions','historical and forward-looking business periods'],
         'published_at':None,'material_file_date':None,'retrieved_at_epoch':proof['pdf']['retrieved_at'],
         'content_sha256':KNOWN_SHA,'page_count':30,'pages':native['pages'],'binary_complete':True,
         'text_extraction_complete':False,'native_text_coverage':'partial','coverage_status':'partial',
         'full_content_coverage_verified':False,'full_visual_content_verified':False,'financial_statement_complete':False,
         'missing_text_pages':[2,3,6,11,12,21],'garbled_pages':[],
         'parser_version':native['parser_version'],'lienhwa_glyph_evidence':deepcopy(native['lienhwa_glyph_evidence']),
         'known_native_text_omissions':[
             {'page_number':2,'issue':'image-only disclaimer; visual review cautions are not extracted native text'},
             {'page_number':3,'issue':'image-only agenda'}, {'page_number':6,'issue':'image-only sales/chart'},
             {'page_number':11,'issue':'image-only business schematic'}, {'page_number':12,'issue':'image-only AI applications'},
             {'page_number':15,'issue':'covered 2027 end-of-year native heading remains in raw page; whole page excluded from roles'},
             {'page_number':21,'issue':'image-only financial agenda'},
             {'page_number':29,'issue':'Q&A agenda image and native page number only; no questions or answers'},
             {'page_number':30,'issue':'thank-you/contact image; native page number only'}],
         'excluded_native_text_pages':[15],'role_page_allowlist':[1,22,24,25],
         'visual_semantics_caution':'Only partial native text. Six native-empty pages and many other chart/image labels are unavailable; native order alone does not prove visual numeric pairing.',
         'native_editorial_caution':'Page15 contains covered native 2027 end-of-year wording and three verified circle symbols. Preserve original page, omit whole page from role views; hidden words are neither facts nor instructions.',
         'financial_scope_caution':'Management presentation, not complete statements or five-year9fact history. Page22 H1 segment revenue; page24 investment income; page25 consolidated net income is not necessarily profit attributable to parent.',
         'unit_scope_caution':'Page22/24/25 money is NTD million except page25 EPS NTD per share. Page24 negative signs/spaces and chart/table repetition stay unchanged; do not treat axis ticks as facts or recalculate EPS.',
         'period_scope_caution':'Event2026-09-30 differs from Q2 label, H1 comparisons and quarterly history. PDF creation10/7 and modification10/12 do not establish publication. Keep top-level period unknown/mixed.',
         'forward_looking_caution':'Page2 image disclaimer was visually reviewed: expectations may differ from results and issuer has no duty to update. This is a caution summary, not native disclaimer text. Subsidiary plans/capacity are not realized parent results.',
         'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
         'publisher_copyright':'Copyright © Lien Hwa Holdings Corporation. All Rights Reserved.',
         'response_reuse_policy':'No-store/no-cache index and event; always native issuer acquisitions and private immutable audit originals only'}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'','title':selected['title'],'source':PROVIDER,
            'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
            'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-Hant'}],'documents':[doc],
            'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
            'fetched_at_epoch':proof['pdf']['retrieved_at'],'lienhwa_conference_receipt':proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','event','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_lienhwa(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['lienhwa_conference_receipt']
        if set(proof) != {'policy','identity','index','event','pdf','selected'} or proof['policy'] != POLICY:
            return False
        identity_url=proof['identity']['source_url']
        parse_master(original_bytes(proof['identity'],identity_url,max_age=max_age),proof['identity']['retrieved_at'],identity_url)
        selected = select_presentation(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
        selected = select_event(original_bytes(proof['event'],EVENT_URL,max_age=max_age),proof['event']['retrieved_at'],selected)
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],PDF_URL,max_age=max_age)
        expected = _context(selected,native_presentation(raw,selected,deadline),proof)
        for key,url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('event',EVENT_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(expected,sort_keys=True,allow_nan=False)
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False


def fetch_lienhwa_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_lienhwa(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'lienhwa_presentation_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url']);_check(deadline)
        raw,index = http.get_receipt(INDEX_URL);selected = select_presentation(raw,index['retrieved_at']);_check(deadline)
        raw,event = http.get_receipt(EVENT_URL);selected = select_event(raw,event['retrieved_at'],selected);_check(deadline)
        raw,pdf = http.get_receipt(PDF_URL);native = native_presentation(raw,selected,deadline)
        proof = {'policy':POLICY,'identity':identity,'index':index,'event':event,'pdf':pdf,'selected':selected}
        value = _context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value = deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        for key,url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('event',EVENT_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=RAW_TTL)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        details.update(lienhwa_originals_verified=True,coverage_status='qualified_partial_presentation',
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
        details.update(lienhwa_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','1229'),('official_name','聯華'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'聯華',LEGAL.casefold(),'lhihc','lien hwa industrial holdings corporation','lien hwa industrial holdings corp','lien hwa holdings corporation','lien hwa industrial holdings corp.','lien hwa industrial holdings co'}
    aliases = names | {'1229','1229.tw'}
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
    return isinstance(value,dict) and ('lienhwa_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY or 'lienhwa_glyph_evidence' in d)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
