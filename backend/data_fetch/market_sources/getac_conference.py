"""Getac official presentation with distinct event and document dates."""
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
from .getac_conference_transport import ConferenceHttp, MASTER_URL, ROOT_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '3005.TW'
LEGAL = '神基控股股份有限公司'
UBN = '22099532'
POLICY = 'getac-original-presentation-v1'
PROJECTION_POLICY = 'getac-presentation-role-v1'
KNOWN_SHA = '520a6e06a5679406000966075a004b9f40a47d8545f3f0311459a0b4d080969e'
PAGE_TEXT_SHA256 = ('270763576b51216a84563d50b5bc815244798235787afb5f99fae42c21e77233', '6f146c654ca0eae2496626392809d0dc5307a9c5cb03e8be3e9df4f6912786f4', '01096bf46aac6d9370659bc40cb7fbeafface690621f774249ec2f642e895418', '1f814a69fa876ef0424a0eb70e21843333d1b9d3d121475ed9bbea41201f3b86', '45daaa25f74aff4d171d605293efb6650bf5c619525ff63e2aeb18a935626181', 'fc315a3c5f6b32f6f2971e4a7dbe584ba106c85a0563e40837537321b9a0ea09', '6536f4309cbf623c0964da5a8aab696cca9328c5719f87854f38638d3f4984ab', '82e9f5b393b9ea71acf806444e7b9643bdd7f05897f4e7c526081c21cfa921df', 'fc034b3a47578fa262d8917d6520878920f302dcd0a31b1358d82758d788f3a4', 'a2c79127ad9f66aef38f800d4f6e4ff18a574b0931c8b3bc4b7ed69c66291752', '007b81c02fc3f135bcf0a5d0dd641b6dfd18f6c95a6cc6e5aeb01a1e1a9c1383', 'd5a1328ad3bb4b8861282b465be57bd473c65ddb8c7a07bd56302b68dda9980f', '8027e9c34e131345527ede7e821eddfc8e57aa49808750a5bc8570194a00f81d', '7e231498d061b653f02a5a0ebd9531920cf3ee3cb0536e3590a90954d7e66115', '57ecf547da56fd98cbf08a80492dc20a8d8bcda7bf6c6e1c8cb584f8446ef168', '3576345f0c30371bc9665fc556ab676df107baeb1f425533290402d327c67229', '8ca293b60b3eeabebe3797eeee9c103e925db7fd855e5177d77d8e56cef73e39', 'd792f6c90bab27538c2a174359ff834ecc527cea99669ae8bbce6afe8c35d1e8', 'aa0e1260dfede9b7c469e7a7ae5b14d55b1a5e794f3e9855e804a3341efcfaba', 'd29b7436b22867901a5939afb16206d421144407d0f52d839dc718a7c486cf47', '6e3f7a2e0beb603d76cda27c128535d3f1bf25fb3a9b4c5316cbaaa2ffa853f1')
ROLE_PAGES = (1,2,7,8)
NOTE = '神基官方21頁完整簡報，8/14活動及封面，Q2／H1內容，首次發布日未知。原生文字complete但整體partial，非逐字稿或五年查核財報。角色僅1/2/7/8完整頁；p7兩個事業群段落、p8三個事業須保留各自標題及3004持股35.37%界線，領先／認證／全球供應40%都是文件當時公司主張，未獨立查證。p13/20綜合損益標籤不可改稱淨利；p20空白Q3/Q4不是零，兩年YTD期間不同；p5歷史市值、p18四年摘要及圖表未作完整財報或即時資料。'

def supports_getac(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'3005', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_getac_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Getac master size invalid')
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
        raise ValueError('Getac complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '3005']
    if len(matched) != 1:
        raise ValueError('Getac master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '神基', '營利事業統一編號': UBN, '網址': ROOT_URL}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'Getac'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Getac master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Getac master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '神基', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}



def _html(raw, limit):
    if not isinstance(raw,bytes) or not 0<len(raw)<=limit:raise ValueError('Getac HTML size invalid')
    text=raw.decode('utf-8-sig','strict');body,closing,trailer=text.rpartition('</html>')
    if not closing or '</html>'in body or trailer.strip() or '</body>'not in body:raise ValueError('Getac complete HTML required')
    return BeautifulSoup(text,'html.parser')


def parse_bridge(raw):
    soup=_html(raw,2_500_000)
    if not soup.title or not soup.title.get_text(' ',strip=True).startswith('Getac Holdings Corporation｜Corporate Profile,'):raise ValueError('Getac registered publisher changed')
    english=[a.get('href')for a in soup.select('a[href]')if a.get_text(' ',strip=True)=='ENGLISH']
    if english!=['//en.getacgroup.com/','http://en.getacgroup.com']:raise ValueError('Getac official English host bridge changed')
    return True


INDEX_ROW_TEXTS = ("2026-08-14 Getac Q2'26 Investor Conference- hosted by Yuanta Securities.",
                   "2026-05-15 Getac Q1'26 Investor Conference- hosted by KGI securities.",
                   "2026-03-02 Getac Q4'25 Investor Conference- hosted by Yuanta Securities.")


def select_presentation(raw, epoch, *, as_of_epoch=None):
    from urllib.parse import urljoin
    soup=_html(raw,1_048_576)
    if not soup.title or soup.title.get_text(' ',strip=True)!='Getac Technology Corporation│Investor Relations│IR Calendar, Investor conference date, venue announcement, IR presentation file download':raise ValueError('Getac publisher changed')
    if 'Copyright © Getac Technology Corporation. All Rights Reserved.'not in soup.get_text(' ',strip=True):raise ValueError('Getac owner changed')
    tables=soup.select('table.calendarTable')
    if len(tables)!=2 or [x.get_text(' ',strip=True)for x in tables[1].select('thead th')]!=['Date','Title','Add to Calendar','Download','Video Link']:raise ValueError('Getac table shape changed')
    rows=tables[1].select('tbody > tr')
    if len(rows)!=3 or tuple(r.get_text(' ',strip=True)for r in rows)!=INDEX_ROW_TEXTS:raise ValueError('Getac current event history changed')
    paths=['a595874cfc02bb78ae85a5d21150c0b0','265b5be02d8ef7190fc2573fc3d66a9e','3ef4056c4537e6d23d84d98a0f6636b1']
    for row,path in zip(rows,paths):
        cells=row.find_all('td',recursive=False)
        if len(cells)!=5 or cells[4].get_text(strip=True) or cells[4].select('a'):raise ValueError('Getac row malformed')
        expected="window.open('../upload/document_investor_calendar_list_files/"+path+".pdf');"
        for cell in (cells[1],cells[3]):
            links=cell.select('a')
            if len(links)!=1 or links[0].get('onclick')!=expected or links[0].has_attr('href'):raise ValueError('Getac published attachment changed')
    day=date(2026,8,14)
    if not day<=_today(epoch)<=_today(as_of_epoch) or not 0<=(_today(as_of_epoch)-day).days<=370:raise ValueError('Getac event date invalid')
    return {'title':"Getac Q2'26 Investor Conference- hosted by Yuanta Securities.",'pdf_url':PDF_URL,'event_date':'2026-08-14',
        'document_date':'2026-08-14','cover_month':'2026-08','period_label':'2026H1','index_record_count':3,
        'selection_policy':'latest_exact_published_event_in_complete_current_year_table',
        'history_scope':'three visible2026 conference rows; earlier years not claimed complete; changed event requires qualification'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('Getac original revision is not qualified')
    try:native=extract_getac_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count']!=21 or len(native['pages'])!=21
            or [p['page_number']for p in native['pages']]!=list(range(1,22))
            or tuple(sha256(p['text'].encode()).hexdigest()for p in native['pages'])!=PAGE_TEXT_SHA256
            or native['content_sha256']!=KNOWN_SHA or selected['period_label']!='2026H1'
            or selected['event_date']!='2026-08-14' or selected['document_date']!='2026-08-14' or selected['cover_month']!='2026-08'):
        raise ValueError('Getac complete original projection invalid')
    return native


def _context(selected,native,proof):
    doc={'document_id':'3005:2026-08-14:'+KNOWN_SHA[:16],'ticker':TICKER,'source':PROVIDER,
        'source_type':'issuer_official','document_kind':'presentation','projection_policy':PROJECTION_POLICY,
        'title':selected['title'],'url':PDF_URL,'language':'en','event_date':selected['event_date'],
        'event_date_basis':'exact_issuer_event_and_original_cover_date',
        'event_status':'published_past_material_not_independently_occurrence_verified',
        'event_time':None,'event_timezone':'Asia/Taipei','published_at':None,'material_file_date':'2026-08-14',
        'presentation_cover_month':'2026-08','content_period':'2026H1',
        'content_periods':['2026Q2 and H1 financials','2025 and earlier historical figures','issuer business descriptions and forward-looking statements'],
        'retrieved_at_epoch':proof['pdf']['retrieved_at'],'content_sha256':KNOWN_SHA,'page_count':21,'pages':native['pages'],
        'binary_complete':True,'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
        'full_content_coverage_verified':False,'full_visual_content_verified':False,'financial_statement_complete':False,
        'missing_text_pages':[],'garbled_pages':[],'parser_version':native['parser_version'],'role_page_allowlist':list(ROLE_PAGES),
        'excluded_native_text_pages':[n for n in range(1,22)if n not in ROLE_PAGES],
        'native_editorial_caution':'Pages13/20 label comprehensive income attributable to owners, not audited net income. Page20 blankQ3/Q4 are not zeros;2026YTD is H1 whereas2025YTD is full-year. Exclude financial tables/charts from roles; preserve all originals.',
        'index_reuse_caution':'August14 event and cover match; actual event occurrence and first publication date are not independently verified. Business-report and conference attachments are byte-identical, not independent sources.',
        'forward_looking_caution':'Original disclaimer remains with role pages. Leadership, certification and40percent global supply are issuer claims at document time, not independently verified facts or current events.',
        'period_scope_caution':'August14 presentation describesQ2/H1. Page5 market cap is based on June2026 average prices, not current quote. Page18 has four years, not five-year complete financials.',
        'financial_scope_caution':'Management presentation is not a five-year audited statement source. Do not overwrite annual,TTM,FCF or existing financial facts.',
        'unit_scope_caution':'Preserve group and subsidiary scope. Page8 Aerospace Fasteners TWSE3004 and35.37percent ownership must not be relabeled wholly owned3005. Global supply40percent refers to seatbelt spindles/spools, not total automotive market.',
        'visual_semantics_caution':'Only complete pages1/2/7/8 are role-qualified. Page7 paragraph beginning A professional OEM supplier belongs to Mechatronic and Energy BG; preserve its original page and this assignment. All21 original pages retained; images and other tables/charts not asserted verified.',
        'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
        'response_reuse_policy':'Always native registered-root/index/PDF acquisition; immutable private originals, no success-cache reuse'}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026H1','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'en'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'getac_conference_receipt':proof}


def role_pages(document):
    if not isinstance(document,dict):return []
    try:
        selected={'title':"Getac Q2'26 Investor Conference- hosted by Yuanta Securities.",'event_date':'2026-08-14',
                  'selection_policy':'latest_exact_published_event_in_complete_current_year_table'}
        expected=_context(selected,{'pages':document['pages'],'parser_version':document['parser_version']},
                          {'pdf':{'retrieved_at':document['retrieved_at_epoch']}})['documents'][0]
        if json.dumps(document,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):return []
    except (KeyError,TypeError,ValueError):return []
    pages=document.get('pages')
    if not isinstance(pages,list)or len(pages)!=21:return []
    for n,p in enumerate(pages,1):
        if not isinstance(p,dict)or type(p.get('page_number'))is not int or p['page_number']!=n or not isinstance(p.get('text'),str)or sha256(p['text'].encode()).hexdigest()!=PAGE_TEXT_SHA256[n-1]:return []
    return deepcopy([p for p in pages if p['page_number']in ROLE_PAGES])


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','bridge','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_getac(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['getac_conference_receipt']
        if set(proof) != {'policy','identity','bridge','index','pdf','selected'} or proof['policy'] != POLICY:
            return False
        identity_url=proof['identity']['source_url']
        parse_master(original_bytes(proof['identity'],identity_url,max_age=max_age),proof['identity']['retrieved_at'],identity_url)
        parse_bridge(original_bytes(proof['bridge'],ROOT_URL,max_age=max_age))
        selected = select_presentation(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],PDF_URL,max_age=max_age)
        expected = _context(selected,native_presentation(raw,selected,deadline),proof)
        for key,url in [('identity',proof['identity']['source_url']),('bridge',ROOT_URL),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(expected,sort_keys=True,allow_nan=False)
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False


def fetch_getac_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_getac(ticker):return {}
    deadline = time.monotonic()+30.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'getac_presentation_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url']);_check(deadline)
        raw,bridge = http.get_receipt(ROOT_URL);parse_bridge(raw);_check(deadline)
        raw,index = http.get_receipt(INDEX_URL);selected = select_presentation(raw,index['retrieved_at']);_check(deadline)
        raw,pdf = http.get_receipt(PDF_URL);native = native_presentation(raw,selected,deadline)
        proof = {'policy':POLICY,'identity':identity,'bridge':bridge,'index':index,'pdf':pdf,'selected':selected}
        value = _context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value = deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        for key,url in [('identity',proof['identity']['source_url']),('bridge',ROOT_URL),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=RAW_TTL)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        details.update(getac_originals_verified=True,coverage_status='native_text_complete',
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
        details.update(getac_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','3005'),('official_name','神基'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'神基',LEGAL.casefold(),'getac','getac holdings corporation','getac holdings corp','getac holdings corp.'}
    aliases = names | {'3005','3005.tw'}
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
    return isinstance(value,dict) and ('getac_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
