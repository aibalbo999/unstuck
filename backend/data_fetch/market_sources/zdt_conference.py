"""ZDT official presentation with distinct event and document dates."""
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
from .zdt_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '4958.TW'
LEGAL = '臻鼎科技控股股份有限公司'
UBN = '26392564'
POLICY = 'zdt-original-presentation-v1'
PROJECTION_POLICY = 'zdt-presentation-role-v1'
KNOWN_SHA = '3c4d6c0cc2446b8309a9d6ed4dcd2310a5c5f6b65ef53bb763fd1155b33a006c'
PAGE_TEXT_SHA256 = ('1a358ff9b8cd6d414e92565dbd8e867129d30a90b9d144514aec90284c93f7d8', 'd4858e2129fe6996eb3240bdf0c04050f1ed596d0c627f42664d80f5b06eeda2', '81841b2754dc873bba1ec5bab37255234c6621ed73db37a9d63db0ec2161a148', '43549bbc2b5b65f2b8f767cb93e2bab4c8f711ed9173c5785d1d821b87bbab05', '381c909253d27430913b31fd1ea31cc92bf2cad43fed0dd2e3bfbbc748d0f060', '5fbd234c1e5fecd14e14f6874739237323dc2236eae29f54ff774d0d059cb09d', 'c61c8d27431b84cf87b144595b4195476819d92eca17a3186a377d6b8398f81f', '34f0efe7e953502286b7685ad555d2aef64a5c8ee0253374a144178c74dbdaf5', '6e6d8c116c252f6ff40931b10ccb46dc1b34bbceff4544de033b76b4d88e621d', '2a82a5cb980be9d5f8a2506b8a193bb218216c5bf050fe277e3fa0428db46e3f', '82100a5946defbdacdfb4abb73d6f1d7d837e77c915f9f4c8f919006c294a244', '5f2997b84d43dcf9d88176f84e00ef38f8e0965f9c26fa2459ecee11f5e7c2b3', 'b70a49500e54da62146c3a051694907332437e7bfe70d204568ff9d310dbc2a5', '1389cd6654f3aeb3dc89c29b5c682f271cabce12761407bdd515b2ec807a5f0b', 'c68575f8696cba40d9dcf1f68834b251d6fd7c7d5f43c63236f5a52e91c38b94', '46693453170e9770ca1eff8553a8c12c097caf83e08287e2006c69adc81573c1', '9155f5f40c222ba507bada19d89c261619e04b3a745fc10fddde0035e30ede00', '97cc1439ed9340c15d075aa6c717f995572614993f40096a1ef1f349342d6391', 'edce8093e16e2652367c2151b4317d208abb5fae8f6d809324ce5e25f4f8b0ba', '2ca9c6b839d906466dccc748d2080ec90e37a500aa9af381672e3c964f561216', '0fb1c5bcc4b6406765554b2f2fe560aac0a2833aa2554a5ff083c3043355e685', 'ed918277b6033fa3bb82d703732ac5e99ec6daf3a20b0a0cf3cd73e7e4b3375e', '578b4996fc50a5bb5becf454e5f11849c42f95a58aa8d1f4a5cc7fa4e3943670', '5b8783a04cecb42217edadf02c9ead8b116b9d3f3d0688f62620ad6a54c3dc8b', 'd2fd998d105598b3bcc79f0f4ba24d348351d116aad0ac897e935d6f71be790e', '1e0ce06421e571460b3d0c8c0b429592ac9e2bceddf5dc78f33f0a19a8b74a18', 'f3c2ef953ca6155d49df8f3245cdfd38cc9e7d7caca464605162bd7e2450b209', '3879e1cc490ca595bb8fa1d0cf19c485dcecd458aba4a04cfa9cc81da6ee67d2', '91dc0b914fbffd0291fc378eac75da99883cf93184b4ff86d6b8ec4176c076fd', 'dfc2e58769bb357b7451fc4cc3ad9e0b4e909dcc1b5417fb7a6f4e39c9bcca2f', '8bdab6047d7c8554850790daa360bed350a14f4ec5d679b6dde2b188f6fa3690', '738ce687092ae058349f0c4072da1cb3d188ab79fb8f9d0890db1d6bec5b99d9', '2483dd8fd32201e67391c5ef74b9745021b55fb47d2f7b7414f73e8ffadbc96c', '4545e2adab82aa6fe86840ab33561ba8a2d772d2b5ba0c9a4916589f30f30978', 'cfde1025439b573a462b9bcaea3abf4d0ae2f9ec68c590cfb004837945bb9a0b', '036f7c749032f86f9a5893a81a0f43fc3b9ae38745932f89e7bb4240835b9257', '4072357f8f8b9b365cb6fe3aa2c04db29bc7627330deb790a605f6035e7e6506', '3f4f84bee18282827fbd9c8a36db8e6d34ef66d168cccae5fb9fb86a3696caf4')
ROLE_PAGES = (1,2,5,22)
NOTE = '臻鼎10月13–14日論壇公開38頁投資人簡報，封面僅標2026年10月，首次發布日未知。原件及原生文字完整，但整體partial，非逐字稿或查核財報。角色只讀1/2/5/22完整原文頁；32/33頁含不可視第四季模板字，36頁借款比例與股數附註有疑義，均整頁排除；其他圖表未完成語意驗證。H1實績、10月營運更新及2026–2030年預測分開；禮鼎子公司上市申請非核准，擴產與支出計畫非已實現。新台幣億元與人民幣億元不可混用。'

def supports_zdt(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'4958', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_zdt_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('ZDT master size invalid')
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
        raise ValueError('ZDT complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '4958']
    if len(matched) != 1:
        raise ValueError('ZDT master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '臻鼎-KY', '營利事業統一編號': UBN, '網址': 'https://www.zdtco.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'ZDT'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('ZDT master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('ZDT master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '臻鼎-KY', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}



INDEX_ROWS_SHA256 = 'bcf64faf81d4255c084bc6b5c7fc43b279e081509afcc747a663bbea8159ebf7'

def select_presentation(raw, epoch, *, as_of_epoch=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:raise ValueError("ZDT index size invalid")
    text=raw.decode("utf-8-sig","strict");body,closing,trailer=text.rpartition("</html>")
    if not closing or "</html>" in body or trailer.strip() or "</body>" not in body:raise ValueError("ZDT complete index required")
    soup=BeautifulSoup(text,"html.parser")
    if not soup.title or soup.title.get_text(" ",strip=True)!="臻鼎科技集團":raise ValueError("ZDT publisher changed")
    if "Copyright © 2020 臻鼎科技控股股份有限公司 著作權所有" not in soup.get_text(" ",strip=True):raise ValueError("ZDT owner changed")
    if [r.get_text(" ",strip=True)for r in soup.select("li.FilterYear")]!=["2026","2025","2024","2023","2022","2021","2020"]:raise ValueError("ZDT history years changed")
    rows=soup.select(".each-event")
    if len(rows)!=215 or len(soup.select(".each-event.Leon-Year2026"))!=31:raise ValueError("ZDT complete event history changed")
    records=[{"classes":r.get("class"),"text":r.get_text(" ",strip=True),"links":[{"text":a.get_text(" ",strip=True),"href":a.get("href")}for a in r.select("a")]}for r in rows]
    digest=sha256(json.dumps(records,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    if digest!=INDEX_ROWS_SHA256 or any(a.has_attr("onclick")for r in rows for a in r.select("a")):raise ValueError("ZDT current event or attachment changed")
    # All published rows are verified, so a newer event without attachments
    # cannot silently fall back to the qualified October original.
    day=date(2026,10,13);end=date(2026,10,14)
    if not end<=_today(epoch)<=_today(as_of_epoch) or not 0<=(_today(as_of_epoch)-day).days<=370:raise ValueError("ZDT event date invalid")
    return {"title":"臻鼎科技控股2026年10月投資人簡報（20th QIC CEO Week）","pdf_url":PDF_URL,
        "event_date":"2026-10-13","event_end_date":"2026-10-14","document_date":None,"cover_month":"2026-10",
        "period_label":"2026H1 financials and October operational outlook","index_record_count":215,
        "selection_policy":"latest_exact_published_event_in_complete_2020_2026_index",
        "history_scope":"215 complete visible rows; 31 current-year rows; newer publication requires qualification"}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('ZDT original revision is not qualified')
    try:native=extract_zdt_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count']!=38 or len(native['pages'])!=38
            or [p['page_number']for p in native['pages']]!=list(range(1,39))
            or tuple(sha256(p['text'].encode()).hexdigest()for p in native['pages'])!=PAGE_TEXT_SHA256
            or native['content_sha256']!=KNOWN_SHA or selected['period_label']!='2026H1 financials and October operational outlook'
            or selected['event_date']!='2026-10-13' or selected['document_date']!=None):
        raise ValueError('ZDT complete original projection invalid')
    return native


def _context(selected,native,proof):
    doc={"document_id":"4958:2026-10-13:"+KNOWN_SHA[:16],"ticker":TICKER,"source":PROVIDER,
        "source_type":"issuer_official","document_kind":"presentation","projection_policy":PROJECTION_POLICY,
        "title":selected["title"],"url":PDF_URL,"language":"zh-TW","event_date":selected["event_date"],
        "event_end_date":selected["event_end_date"],"event_date_basis":"exact_official_event_range_and_linked_October_cover",
        "event_status":"published_past_material_not_independently_occurrence_verified",
        "event_time":"12:00","event_timezone":"Asia/Taipei","published_at":None,"material_file_date":None,
        "presentation_cover_month":"2026-10","content_period":selected["period_label"],
        "content_periods":["2026Q2 and H1 financial comparisons","October operational update","2026-2030 issuer outlook"],
        "retrieved_at_epoch":proof["pdf"]["retrieved_at"],"content_sha256":KNOWN_SHA,"page_count":38,"pages":native["pages"],
        "binary_complete":True,"text_extraction_complete":True,"native_text_coverage":"complete","coverage_status":"partial",
        "full_content_coverage_verified":False,"full_visual_content_verified":False,"financial_statement_complete":False,
        "missing_text_pages":[],"garbled_pages":[],"parser_version":native["parser_version"],"role_page_allowlist":list(ROLE_PAGES),
        "excluded_native_text_pages":[n for n in range(1,39)if n not in ROLE_PAGES],
        "native_editorial_caution":"Pages32/33 include invisible fourth-quarter template text. Page36 borrowing percentage and share-count footnote are questionable. Exclude entire pages, preserve originals unchanged.",
        "index_reuse_caution":"Official October13-14 event links October cover material. First publication date and event occurrence are not independently verified; URL and Last-Modified are not publication proof.",
        "forward_looking_caution":"Forecasts, capital spending and expansion schedules are issuer claims as of October2026, not completed results or independent guarantees. No update obligation. Liding listing application is not approval.",
        "period_scope_caution":"Separate October event and cover month, Q2/H1 results, and 2026-2030 future plans. Do not claim Q3/Q4 financial results.",
        "financial_scope_caution":"Management presentation, not audited statements or five-year financial history. Group, parent and Liding subsidiary scopes differ; no annual/TTM replacements.",
        "unit_scope_caution":"Selected page5 amounts are TWD hundred-millions; page22 Liding investment is RMB hundred-millions. Do not combine currencies or replace plans with actual expenses.",
        "visual_semantics_caution":"Only whole pages1/2/5/22 selected after visual checks. All38 native pages retained; other tables, charts and column associations remain unqualified.",
        "q_and_a_transcript_available":False,"commercial_reuse_permission_verified":False,
        "response_reuse_policy":"Always native issuer index/PDF acquisition; immutable private originals, no success-cache reuse"}
    return {"ticker":TICKER,"date":selected["event_date"],"period":selected["period_label"],"title":selected["title"],"source":PROVIDER,"source_url":INDEX_URL,
        "summary":"","transcript_excerpt":"","transcript_available":False,"materials":[{"url":PDF_URL,"kind":"presentation","language":"zh-TW"}],
        "documents":[doc],"coverage_status":"partial","coverage_notes":[NOTE],"selection_policy":selected["selection_policy"],
        "fetched_at_epoch":proof["pdf"]["retrieved_at"],"zdt_conference_receipt":proof}


def role_pages(document):
    expected={'source':PROVIDER,'ticker':TICKER,'projection_policy':PROJECTION_POLICY,'content_sha256':KNOWN_SHA,
        'document_kind':'presentation','event_date':'2026-10-13','material_file_date':None,'content_period':'2026H1 financials and October operational outlook','page_count':38,
        'native_text_coverage':'complete','text_extraction_complete':True,'binary_complete':True,'coverage_status':'partial',
        'q_and_a_transcript_available':False,'financial_statement_complete':False,'full_visual_content_verified':False,
        'role_page_allowlist':list(ROLE_PAGES),'excluded_native_text_pages':[n for n in range(1,39)if n not in ROLE_PAGES]}
    if any(document.get(k)!=v or type(document.get(k))is not type(v)for k,v in expected.items()):return []
    try:
        selected={"title":"臻鼎科技控股2026年10月投資人簡報（20th QIC CEO Week）","event_date":"2026-10-13","event_end_date":"2026-10-14","period_label":"2026H1 financials and October operational outlook","selection_policy":"latest_exact_published_event_in_complete_2020_2026_index"}
        expected_doc=_context(selected,{"pages":document["pages"],"parser_version":document["parser_version"]},{"pdf":{"retrieved_at":document["retrieved_at_epoch"]}})["documents"][0]
        if json.dumps(document,sort_keys=True,allow_nan=False)!=json.dumps(expected_doc,sort_keys=True,allow_nan=False):return []
    except (KeyError,TypeError,ValueError):return []
    pages=document.get('pages')
    if not isinstance(pages,list)or len(pages)!=38:return []
    for n,p in enumerate(pages,1):
        if not isinstance(p,dict)or type(p.get('page_number'))is not int or p['page_number']!=n or not isinstance(p.get('text'),str)or sha256(p['text'].encode()).hexdigest()!=PAGE_TEXT_SHA256[n-1]:return []
    return deepcopy([p for p in pages if p['page_number']in ROLE_PAGES])


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_zdt(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['zdt_conference_receipt']
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


def fetch_zdt_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_zdt(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'zdt_presentation_workflow':True}
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
        details.update(zdt_originals_verified=True,coverage_status='native_text_complete',
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
        details.update(zdt_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','4958'),('official_name','臻鼎-KY'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'臻鼎-KY'.casefold(),LEGAL.casefold(),'zdt','zhen ding technology holding limited','zhen ding technology holding lt'}
    aliases = names | {'4958','4958.tw'}
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
    return isinstance(value,dict) and ('zdt_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
