"""InnoCare exact issuer originals with conflicting-page and chart exclusions."""
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
from .innocare_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '6861.TW'
LEGAL = '睿生光電股份有限公司'
UBN = '69764396'
POLICY = 'innocare-original-presentation-v1'
PROJECTION_POLICY = 'innocare-presentation-role-v1'
KNOWN_SHA = 'a702ecdd7db0fd322885b2627de483508ae9a3ee7250aa4d5c3d50879eb15dad'
PAGE_TEXT_SHA256 = ('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', '0b63870333dcb90930a81a8ae102edf6986842fad26df6fca1b0432bbde1f900', 'bb997446fa713f91cd00b711170f99d4534a14b3deea98c9ae5507561da657ee', '0a9e6abe7032601815633fd9d385788c31a5e39b25391b17eb59f87d37b1a922', '90e93aff6a1d82bf9988ff6de8ae31717ae2fa0d6666937e9014f659fe7edd18', 'e895a81972179aa2f1df4db6fa8984fc9229dff2605bbf4b31942473239e240a', '6117010e54836cd9727f9f2c2be7ec40bafdbd47ebeac30a85a0c86aff29b5a5', 'dca15a4c52f82abc41f85b6df105f1bd931db3199477d91b8012cc067b4b5af7', 'a4aab945be2b2b5e4ed63b04f2ecc3e0eccb5af65bbfe0f1c826b95db8330de9', '18ae7e8d9a9b1c3d053dae973d4fd25b6b30ad7ba9a566d54b120cfba795dcac', 'f340b6aacef67ff26527bbd6ceff740f15834de9c072ffb69d969e1194c6c42c', 'ed7bfdd901bd37fd66ba19d4e6dc9431d83a5608e4b7ef165bb50289e3cef9e6', '833198eb449ae5a10d9b87645b363a53cb8f373a72c6eb3ab3fcfc41d4823457', 'ba92067758d23443f6da692a09e91f37bbfaef0fb905f6b1e2754ece4257eeae', 'de90883301b09a647e79cc3423c7c709987667dac4c076974a4858dd874ad240', '574439a29d5adc35c3757eb03aa9988d77e85a6ce0f196a0fa37b37fe1f19254', 'ce99c6306f97d9b6c95d9e0d014fd7761459f8c54322d65357d21abc15f8351f', 'dbf5e53195f23052051f1804c3bc96e125082af46df39c048a3b0353ec5618a3', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
ROLE_PAGES = (2,3,4,15)
NOTE = ('睿生光電2026/9/10官方法說19頁原件完整，原生文字partial；第1/19頁無文字，封面圖像解析有警示。'
 '角色僅採2/3/4/15頁已核文字；4/15頁圖表百分比整段排除，其餘表格及移轉時程圖不提供角色。'
 '資料含H1/Q2實績與當時2H展望，不是逐字稿、實際問答或完整查核財報；9月底搬遷及11月量產是當時預期，未驗證現在已完成。'
 '公開原件標示INCX confidential；私存原件供內部稽核，不主張再利用授權。')


def supports_innocare(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'6861', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_innocare_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('InnoCare master size invalid')
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
        raise ValueError('InnoCare complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '6861']
    if len(matched) != 1:
        raise ValueError('InnoCare master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '睿生光電', '營利事業統一編號': UBN, '網址': 'http://www.innocare-x.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'INCX'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('InnoCare master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('InnoCare master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '睿生光電', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('InnoCare index section ambiguous')
    return values[0]


def select_presentation(raw, epoch, *, as_of_epoch=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:raise ValueError('InnoCare index size invalid')
    text=raw.decode('utf-8-sig','strict');body,closing,trailer=text.rpartition('</html>')
    if not closing or '</html>' in body:raise ValueError('InnoCare index incomplete')
    # This server appends its public cache-generation comment; never use it as
    # an event date or retrieval epoch. No script or arbitrary trailing markup.
    if trailer.strip() and not re.fullmatch(r'<!-- Page cached by LiteSpeed Cache [0-9.]+ on 20\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} -->',trailer.strip()):
        raise ValueError('InnoCare index trailing content unqualified')
    soup=BeautifulSoup(body+closing,'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True)!='法人說明會 - InnoCare Optoelectronics Corp.':raise ValueError('InnoCare publisher changed')
    if _one(soup,'link[rel="canonical"]').get('href')!=INDEX_URL:raise ValueError('InnoCare canonical changed')
    root=_one(soup,'[data-elementor-type="wp-page"]')
    if root.get('data-elementor-id')!='6463':raise ValueError('InnoCare index identity changed')
    sections=[v for v in root.find_all(recursive=False)if v.name]
    if [v.get('data-id')for v in sections]!=['cbe8b27','7546ce0','9a9ebe8','55fb516']:raise ValueError('InnoCare event structure changed')
    if sections[0].get_text(' ',strip=True)!='法人說明會':raise ValueError('InnoCare event header changed')
    event_a=_one(sections[1],'a')
    event_text='2026/9/10 受邀參加福邦證券舉辦之法人說明會'
    from urllib.parse import unquote
    expected_path='https://www.innocare-x.com/2026/08/27/2026-9-10-受邀參加福邦證券舉辦之法人說明會/'
    if (event_a.get_text(' ',strip=True)!=event_text or unquote(event_a.get('href',''))!=expected_path
            or event_a.has_attr('onclick') or sections[1].get_text(' ',strip=True)!=event_text):raise ValueError('InnoCare current event changed')
    pdf=_one(sections[2],'a')
    if pdf.get('href')!=PDF_URL or pdf.get_text(' ',strip=True)!='法說會簡報下載' or pdf.has_attr('onclick'):raise ValueError('InnoCare current original changed')
    # The list presents three historical cards, including the current event.
    # Never silently select the old PDF when a newer or unqualified card exists.
    history=sections[3];cards=history.select('article')
    if len(cards)!=3 or _one(history,'h2').get_text(' ',strip=True)!='過往年度法人說明會':raise ValueError('InnoCare visible history changed')
    titles=[_one(c,'h3 a').get_text(' ',strip=True)for c in cards]
    if titles!=[event_text,'2025/12/16 受邀參加福邦證券舉辦之法人說明會','2025年上半年實體及線上法人說明會']:raise ValueError('InnoCare newer or ambiguous history')
    if _one(cards[0],'h3 a').get('href')!=event_a.get('href'):raise ValueError('InnoCare history link mismatch')
    event=date(2026,9,10)
    if not 0<=(_today(as_of_epoch)-event).days<=370 or not event<=_today(epoch)<=_today(as_of_epoch):raise ValueError('InnoCare event date invalid')
    return {'title':'睿生光電2026年下半年官方法說簡報','period_label':'2026H1_Q2_and_2H_outlook','pdf_url':PDF_URL,
        'event_date':event.isoformat(),'event_time':None,'event_timezone':'Asia/Taipei','index_record_count':3,
        'selection_policy':'issuer_current_section_exact_original_and_visible_history',
        'history_scope':'three visible cards; not a complete all-year history','event_url':event_a['href']}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('InnoCare original revision is not qualified')
    try:
        native = extract_innocare_presentation_pages(raw, timeout_seconds=min(10., deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    if (native['coverage_status'] != 'partial' or native['empty_pages'] != [1,19] or native['garbled_pages']
            or native['page_count'] != 19 or len(native['pages']) != 19
            or [p['page_number'] for p in native['pages']] != list(range(1, 20))
            or tuple(sha256(p['text'].encode()).hexdigest() for p in native['pages']) != PAGE_TEXT_SHA256
            or native['content_sha256'] != KNOWN_SHA or selected['period_label'] != '2026H1_Q2_and_2H_outlook'
            or selected['event_date'] != '2026-09-10'):
        raise ValueError('InnoCare original pages unverified')
    return native


def _context(selected,native,proof):
    doc={'document_id':'6861:'+selected['event_date']+':'+KNOWN_SHA[:16],'ticker':TICKER,
        'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
        'projection_policy':PROJECTION_POLICY,'title':selected['title'],'url':PDF_URL,'language':'zh-TW',
        'event_date':selected['event_date'],'event_date_basis':'current_issuer_index_and_research_verified_image_cover',
        'event_status':'published_past_material_not_independently_occurrence_verified','event_time':None,'event_timezone':'Asia/Taipei',
        'content_period':'','content_periods':['2026H1','2026Q2 and comparisons','2026H2 outlook and longer-term plans'],
        'published_at':None,'material_file_date':None,'retrieved_at_epoch':proof['pdf']['retrieved_at'],
        'content_sha256':KNOWN_SHA,'page_count':19,'pages':native['pages'],'binary_complete':True,
        'text_extraction_complete':False,'native_text_coverage':'partial','coverage_status':'partial',
        'full_content_coverage_verified':False,'full_visual_content_verified':False,'financial_statement_complete':False,
        'missing_text_pages':[1,19],'garbled_pages':[],'parser_version':native['parser_version'],
        'known_native_text_omissions':['pages1/19 image-only; cover image operators unqualified'],
        'excluded_native_text_pages':[n for n in range(1,20)if n not in ROLE_PAGES],'role_page_allowlist':list(ROLE_PAGES),
        'role_chart_text_omission_pages':[4,15],
        'visual_semantics_caution':'Only qualified text blocks on pages2/3/4/15 enter roles. Chart labels/percentages on4/15 removed from role view; originals unchanged. Cover renderer warnings and other chart/table geometry unqualified.',
        'financial_scope_caution':'Selected management presentation, not audited financial statements or five-year nine-fact history. Financial tables16/17/18 excluded from role excerpts.',
        'unit_scope_caution':'Original financial tables use TWD thousands; EPS and ratios have other units. No extracted chart number pairing is admitted.',
        'period_scope_caution':'Event2026-09-10, H1/Q2 results and H2 outlook differ. A 2H presentation is not completed H2 results.',
        'forward_looking_caution':'Statements are issuer claims as of2026-09-10. End-September relocation and early-November production are forecasts; the passage of time does not verify completion. No independent verification or update duty.',
        'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,'publisher_notice':'INCX confidential',
        'response_reuse_policy':'Always native issuer index/PDF acquisition; immutable private audit originals, no success-cache reuse'}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-TW'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'innocare_conference_receipt':proof}


def role_pages(document):
    """Only exact original text can produce this non-mutating role view."""
    if (document.get('projection_policy')!=PROJECTION_POLICY or document.get('content_sha256')!=KNOWN_SHA
            or document.get('source')!=PROVIDER or document.get('ticker')!=TICKER):return []
    pages=document.get('pages')
    if not isinstance(pages,list)or len(pages)!=19:return []
    try:
        if any(type(p['page_number'])is not int or p['page_number']!=i or not isinstance(p['text'],str)
               or sha256(p['text'].encode()).hexdigest()!=PAGE_TEXT_SHA256[i-1] for i,p in enumerate(pages,1)):return []
    except (TypeError,KeyError):return []
    selected=[dict(p)for p in pages if p['page_number']in ROLE_PAGES]
    for p in selected:
        if p['page_number']==4:
            start=p['text'].index('28% 29% 27%')
            end=p['text'].index('TFT供應鏈移轉進展順利:')
            p['text']=p['text'][:start]+p['text'][end:]
            p['text']=p['text'].removesuffix('營收占比')
        elif p['page_number']==15:p['text']=p['text'][:p['text'].index('14% 12% 13%')]
    return selected


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_innocare(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['innocare_conference_receipt']
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


def fetch_innocare_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_innocare(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'innocare_presentation_workflow':True}
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
        details.update(innocare_originals_verified=True,coverage_status='qualified_partial_presentation',
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
        details.update(innocare_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','6861'),('official_name','睿生光電'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'睿生光電',LEGAL.casefold(),'innocare','innocare optoelectronics corporation','innocare optoelectronics corp','innocare optoelectronics corp.','innocare optoelectronics corpor','incx'}
    aliases = names | {'6861','6861.tw'}
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
    return isinstance(value,dict) and ('innocare_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
