"""Qualified KINIK Q2 presentation selected by event dates, with financial-period limits."""
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
from .kinik_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '1560.TW'
LEGAL = '中國砂輪企業股份有限公司'
UBN = '03089008'
POLICY = 'kinik-original-presentation-v1'
PROJECTION_POLICY = 'kinik-presentation-role-v1'
KNOWN_SHA = '4490a76682ab9655cbe78c30736ede3749c31577c35eaa95ef187f7af8511d4c'
NOTE = ('中砂官方2026Q2法說簡報，36頁；非逐字稿、問答紀錄或完整財報。'
        '以完整官網內嵌資料的實際日期選最新場次，不用Seq排序；場次日期與簡報財務期間分開。'
        '僅已核定原檔、嵌入字型及符號可映射，原bytes、其他文字數字與順序保持。'
        '原生文字完整不代表圖表、圖片或數字配對完整；第18頁只有頁碼，其他圖像內容亦不由文字推斷。'
        '第5頁原表頭1Q25/QoQ與周邊季度口徑存在歧義，不自行修成1Q26或引用為已核表格。'
        '第6/10頁36萬片與第13頁6月起40萬片存在來源內差異，不消除或推定已完成產能。'
        '第9頁61.2%僅單一最大客戶；第26頁市占含公司估計，不視為獨立來源驗證。'
        'NT$億、佰萬、thousands TWD、USD thousand、EPS元、%及ppt不同，合併財報與子公司範圍須保留。'
        '第2頁展望不確定且不保證更新；2026/2027產能與資本支出目標不是未來已實現結果。'
        'index meta no-cache；新取得每次原生HTTP，原件私存稽核，不主張商業再利用授權。')


def supports_kinik(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'1560', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_kinik_presentation_pages(raw, *, timeout_seconds):
    # Lazy import keeps unsupported stocks independent of the source-specific worker.
    from kinik_presentation_pdf_reader import extract_kinik_presentation_pages as extract
    return extract(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('KINIK master size invalid')
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
        raise ValueError('KINIK complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '1560']
    if len(matched) != 1:
        raise ValueError('KINIK master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '中砂', '營利事業統一編號': UBN, '網址': 'www.kinik.com.tw'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'KINIK'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('KINIK master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('KINIK master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '中砂', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('KINIK index section ambiguous')
    return values[0]


def _unique_json_pairs(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('KINIK duplicate embedded JSON key')
        value[key]=item
    return value


def _text(value, limit, *, multiline=False):
    return isinstance(value,str) and 0<len(value)<=limit and all(ord(c)>=32 or multiline and c=='\n' for c in value)


def embedded_events(soup):
    scripts=[node.get_text() for node in soup.select('script') if '$scope.Items' in node.get_text()]
    if len(scripts)!=1:raise ValueError('KINIK embedded event data ambiguous')
    script=scripts[0]
    matches=list(re.finditer(r'\$scope\.Items\s*=\s*',script))
    if len(matches)!=1:raise ValueError('KINIK event assignment ambiguous')
    match=matches[0]
    if not re.fullmatch(r"""\s*//Controller\s+app\.controller\("dataCtrl",\s*\['\$scope',\s*function\s*\(\$scope\)\s*\{\s*""",script[:match.start()]):
        raise ValueError('KINIK event controller changed')
    # The original has two literal TAB characters inside Date strings. No JS
    # execution: decode the single data literal, then reject every other raw
    # control character and validate Date independently. Duplicate keys fail.
    literal=script[match.end():]
    quoted=escaped=False
    for char in literal:
        if quoted:
            if ord(char)<32 and char!='\t':
                raise ValueError('KINIK unqualified raw JSON control character')
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='"':quoted=True
    def bad_constant(value):raise ValueError('nonfinite JSON constant')
    decoder=json.JSONDecoder(strict=False,object_pairs_hook=_unique_json_pairs,parse_constant=bad_constant)
    rows,end=decoder.raw_decode(literal)
    if not re.fullmatch(r'\s*\}\s*\]\);\s*',literal[end:]):
        raise ValueError('KINIK trailing event code changed')
    if not isinstance(rows,list) or not 38<=len(rows)<=500:raise ValueError('KINIK complete event index shape changed')
    seen=set();events=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'Seq','Date','Name','Place','Files'}:
            raise ValueError('KINIK event fields invalid')
        seq=row['Seq']
        if type(seq) is not int or not 0<seq<10000 or seq in seen:raise ValueError('KINIK duplicate or invalid event sequence')
        seen.add(seq)
        if (not _text(row['Name'],500) or not _text(row['Place'],1024,multiline=True)
                or not isinstance(row['Date'],str) or not re.fullmatch(r'\d{3}\.\d{2}\.\d{2}(?:\n\t?\d{3}\.\d{2}\.\d{2})?',row['Date'])):
            raise ValueError('KINIK event values invalid')
        days=[]
        for text in row['Date'].splitlines():
            year,month,day=map(int,text.strip().split('.'));days.append(date(year+1911,month,day))
        if days!=sorted(set(days)) or (days[-1]-days[0]).days>7:raise ValueError('KINIK event date range invalid')
        files=row['Files']
        if not isinstance(files,list) or not 1<=len(files)<=5:raise ValueError('KINIK event attachments missing')
        paths=[]
        for item in files:
            if (not isinstance(item,dict) or set(item)!={'Name','Path'} or not _text(item['Name'],100)
                    or not _text(item['Path'],300) or not re.fullmatch(r'[^/\\?#]+\.(?:pdf|mp4)',item['Path'])):
                raise ValueError('KINIK attachment invalid')
            paths.append(item['Path'])
        if len(paths)!=len(set(paths)):raise ValueError('KINIK duplicate attachment')
        events.append((days[-1],days[0],row))
    return sorted(events,key=lambda r:(r[0],r[1]),reverse=True)


def select_presentation(raw, epoch):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:raise ValueError('KINIK index size invalid')
    soup=BeautifulSoup(raw.decode('utf-8-sig','strict'),'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True)!='法說會資料-中國砂輪企業股份有限公司':
        raise ValueError('KINIK index publisher invalid')
    section=_one(soup,'section#Investors')
    if section.get('ng-controller')!='dataCtrl':raise ValueError('KINIK conference controller missing')
    table=_one(section,'table')
    if [n.get_text(' ',strip=True) for n in table.select('thead th')]!=['日期','活動','地點','法人說明會資料']:
        raise ValueError('KINIK conference table invalid')
    if _one(table,'tbody tr').get('ng-repeat')!="x in Items | orderBy:['-Seq']":raise ValueError('KINIK event binding changed')
    links=table.select('a[ng-href]')
    if len(links)!=2 or [a['ng-href']for a in links]!=['../../upload/Investors/Conference/{{f.Path}}','{{f.Path}}']:
        raise ValueError('KINIK published attachment template changed')
    controls={}
    for meta in soup.select('meta[http-equiv]'):
        key=meta['http-equiv'].lower()
        if key in {'pragma','expires','cache-control'}:
            if key in controls:raise ValueError('KINIK cache meta ambiguous')
            controls[key]=meta.get('content','').lower()
    if controls!={'pragma':'no-cache','expires':'0','cache-control':'no-cache'}:raise ValueError('KINIK index cache contract changed')
    events=embedded_events(soup);end,start,row=events[0]
    if (len(events)>1 and events[1][:2]==events[0][:2] or end>_today(epoch)
            or not 0<=(_today()-end).days<=370):raise ValueError('KINIK latest date ambiguous or future')
    files=[f for f in row['Files']if f['Name']=='法說會簡報' and f['Path'].endswith('.pdf')]
    if len(files)!=1 or files[0]['Path']!='2026Q2 KINIK 中砂公司法說會.pdf':
        raise ValueError('KINIK latest PDF revision is not qualified')
    return {'event_date':start.isoformat(),'event_end_date':end.isoformat(),'event_time':None,'event_timezone':None,
            'event_location':row['Place'],'event_name':row['Name'],'event_seq':row['Seq'],
            'title':'中砂2026Q2官方法說簡報','pdf_url':PDF_URL,'period':'2026Q2','index_record_count':len(events),
            'selection_policy':'latest_actual_event_date_range_from_complete_published_literal_not_sequence_number'}


def native_presentation(raw, selected, deadline):
    from kinik_presentation_pdf_reader import glyph_evidence, PAGE_TEXT_SHA256
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('KINIK original revision is not qualified')
    try:
        native = extract_kinik_presentation_pages(raw, timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 36 or len(native['pages']) != 36
            or [p['page_number'] for p in native['pages']] != list(range(1,37))
            or tuple(sha256(p['text'].encode()).hexdigest() for p in native['pages']) != PAGE_TEXT_SHA256
            or native['content_sha256'] != KNOWN_SHA
            or json.dumps(native.get('kinik_glyph_evidence'),sort_keys=True,allow_nan=False) != json.dumps(glyph_evidence(),sort_keys=True)
            or selected['period'] != '2026Q2'):
        raise ValueError('KINIK original pages or symbol proof unverified')
    return native


def _context(selected, native, proof):
    doc = {'document_id':'1560:'+selected['event_date']+':'+KNOWN_SHA[:16],
           'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
           'projection_policy':PROJECTION_POLICY,'title':selected['title'],'url':PDF_URL,'language':'zh-Hant with English tables and appendices',
           'event_date':selected['event_date'],'event_end_date':selected['event_end_date'],'event_date_basis':'issuer_index_event_dates_cover_financial_period_only',
           'event_time':selected['event_time'],'event_timezone':None,'event_location':selected['event_location'],
           'event_name':selected['event_name'],'event_status':'published_past_material_not_independently_occurrence_verified',
           'content_period':'2026Q2','content_periods':['2026Q2','2026H1','2025 comparisons','2026-08-11 capital date','2026/2027 forward-looking targets'],
           'published_at':None,'material_file_date':None,'retrieved_at_epoch':proof['pdf']['retrieved_at'],
           'content_sha256':KNOWN_SHA,'page_count':36,'pages':native['pages'],'binary_complete':True,
           'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
           'full_content_coverage_verified':False,'missing_text_pages':[],'garbled_pages':[],
           'parser_version':native['parser_version'],'kinik_glyph_evidence':deepcopy(native['kinik_glyph_evidence']),
           'known_native_text_omissions':[
               {'page_number':1,'issue':'ticker1560 and logo are visual, not all native text'},
               {'page_number':5,'issue':'native table label1Q25 under QoQ is ambiguous; no guessed correction or verified table promotion'},
               {'page_number':8,'issue':'customer share chart lacks native chart values'},
               {'page_number':14,'issue':'Q&A heading only; no questions or answers'},
               {'page_number':18,'issue':'page number only; image content unavailable'},
               {'page_number':26,'issue':'chart numbers and geometry unavailable; company-compiled market estimates not independent publisher evidence'},
               {'page_number':36,'issue':'image obscures part of native Copyright footer; exact footer omitted from role view only'}],
           'excluded_native_text_pages':[18],'native_footer_omission_pages':[36],
           'visual_semantics_caution':'Charts, images and table geometry are not fully verified; do not infer numeric pairing or calculations from native text order.',
           'financial_scope_caution':'Consolidated quarterly/H1 financial statements in management presentation; no complete financial-history replacement. Page5 table header1Q25/QoQ ambiguous, never silently correct to1Q26.',
           'subsidiary_scope_caution':'ABU includes subsidiaries; MKS/MGT consolidated from April2025. Page9 advanced-process share61.2% concerns one largest customer only.',
           'unit_scope_caution':'TWD hundred million/million/thousand, USD thousand, EPS per-share, growth percentages and ppt differ.',
           'period_scope_caution':'Event dates differ from2026Q2/H1 performance and2025 comparisons. Page4 capital as of2026-08-11. Pages6/10 360K versus page13 400K capacity claims remain unresolved.',
           'forward_looking_caution':'Page2 disclaims uncertain projections and updating duty;2026/2027 capacity, capital budget and growth targets are not independently realized results. Page26 mixes external studies and company estimates, all presented by one issuer.',
           'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
           'response_reuse_policy':'Index meta no-cache; source acquisitions require fresh HTTP for index and PDF; private immutable evidence only'}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026Q2','title':selected['title'],'source':PROVIDER,
            'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
            'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-Hant with English tables and appendices'}],'documents':[doc],
            'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
            'fetched_at_epoch':proof['pdf']['retrieved_at'],'kinik_conference_receipt':proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_kinik(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['kinik_conference_receipt']
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


def fetch_kinik_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_kinik(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'kinik_presentation_workflow':True}
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
        details.update(kinik_originals_verified=True,coverage_status='native_presentation_text_complete',
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
        details.update(kinik_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','1560'),('official_name','中砂'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'中砂',LEGAL.casefold(),'kinik','kinik company','kinik co','kinik co.','china grinding wheel corporation'}
    aliases = names | {'1560','1560.tw'}
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
    return isinstance(value,dict) and ('kinik_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
