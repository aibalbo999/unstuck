"""Published STI presentation with explicit native visual and financial scope limits."""
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
from sti_presentation_pdf_reader import extract_sti_presentation_pages, glyph_evidence
from .sti_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, valid_expiry

TICKER = '2480.TW'
LEGAL = '敦陽科技股份有限公司'
UBN = '84218848'
POLICY = 'sti-original-presentation-v1'
PROJECTION_POLICY = 'sti-presentation-role-v1'
KNOWN_SHA = '61a4dececbdb1a30bb4ea6529de24001b4cdf10a26e8a33a85f4feb4378c6e0b'
CONTENT_PERIODS = ['2026Q2','2026H1','2025H1','2025-12-31']
NOTE = ('敦陽科技官方中文115年第二季法說簡報，非逐字稿；第44頁只有Q&A／Thank you，不含實際問答或影音核對。'
        '44頁原生文字取得不等於圖表語意完整；第26頁柱狀圖數值與季度、第37頁圓餅圖標籤與比例不在原生文字中；第26–35、37–38、40–43頁視覺內容未完整核對。'
        '內容含2026Q2、2026及2025上半年、2025年底不同期間；資產負債表、累計損益與季度數不能混用。'
        '第5頁敦陽資訊子公司得獎陳述不能改稱母公司；公司陳述與簡報數字未獨立核對，不覆寫正式財報或TTM。'
        '第2頁明示來源及聲明可能受科技演進等因素影響，建議以公開資訊觀測站公告為準。'
        '實際會議舉行、確切時間及檔案首次公布時間未驗證；不由URL參數、HTTP日期或取得時間推定發布日期。')


def supports_sti(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2480', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('STI master size invalid')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True)
    rows = list(reader); fields = reader.fieldnames
    if (not fields or len(fields) != len(set(fields)) or not 500 <= len(rows) <= 2000
            or any(None in r or any(v is None for v in r.values()) for r in rows)):
        raise ValueError('STI complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2480']
    if len(matched) != 1:
        raise ValueError('STI master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '敦陽科', '營利事業統一編號': UBN, '網址': 'https://www.sti.com.tw/'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'STARK'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('STI master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('STI master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '敦陽科', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('STI index section ambiguous')
    return values[0]


def select_presentation(raw, epoch):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:
        raise ValueError('STI index size invalid')
    soup=BeautifulSoup(raw.decode('utf-8','strict'),'html.parser')
    if (not soup.title or soup.title.get_text(' ',strip=True)!='法人說明會 - 敦陽科技股份有限公司'
            or _one(soup,'link[rel=canonical]').get('href')!=INDEX_URL
            or _one(soup,'meta[property="og:site_name"]').get('content')!=LEGAL
            or _one(soup,'meta[property="og:url"]').get('content')!=INDEX_URL):
        raise ValueError('STI registered publisher unverified')
    table=_one(soup,'.journal-content-article table')
    rows=table.find_all('tr')
    if not 2<=len(rows)<=150 or [c.get_text(' ',strip=True) for c in rows[0].find_all(['td','th'],recursive=False)]!=['日期','活動','簡報檔','影音連結']:
        raise ValueError('STI full event table shape invalid')
    seen=set();eligible=[]
    for row in rows[1:]:
        cells=row.find_all('td',recursive=False)
        if len(cells)!=4:raise ValueError('STI event row shape invalid')
        stamp=cells[0].get_text(' ',strip=True)
        if not re.fullmatch(r'20\d{2}/\d{1,2}/\d{1,2}',stamp):raise ValueError('STI event date invalid')
        year,month,day=map(int,stamp.split('/'));day=date(year,month,day)
        title=cells[1].get_text(' ',strip=True).replace('\u200b','').strip()
        if day in seen or not title or '法人說明會' not in title:raise ValueError('STI event identity ambiguous')
        seen.add(day)
        # Date selection precedes attachment validation: newer empty rows never fall back.
        if day<=_today(epoch) and 0<=(_today()-day).days<=370:eligible.append((day,title,cells))
    if not eligible:raise ValueError('STI current event missing')
    day,title,cells=max(eligible,key=lambda v:v[0])
    if day.isoformat()!='2026-08-05' or title!='受邀參加凱基證券舉辦之2026年第二季法人說明會':
        raise ValueError('STI latest eligible event not qualified')
    links=cells[2].find_all('a')
    if len(links)!=1 or links[0].get('href')!=PDF_URL.removeprefix('https://www.sti.com.tw'):
        raise ValueError('STI exact published presentation unverified')
    return {'event_date':day.isoformat(),'event_time':None,'event_timezone':'Asia/Taipei',
            'period':'2026Q2 / 2026H1','title':'敦陽科技2026年第二季官方中文法說簡報','pdf_url':PDF_URL,
            'selection_policy':'latest_eligible_issuer_event_including_attachment_free_rows_exact_published_PDF_query'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('STI original revision not qualified')
    try:native=extract_sti_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    if json.dumps(native.get('sti_glyph_evidence'),sort_keys=True,allow_nan=False)!=json.dumps(glyph_evidence(),sort_keys=True,allow_nan=False):
        raise ValueError('STI native glyph proof unverified')
    pages=native['pages'];cover=re.sub(r'\s+','',pages[0]['text']);disclaimer=re.sub(r'\s+','',pages[1]['text'])
    if (native['coverage_status']!='complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count']!=44 or len(pages)!=44 or native['content_sha256']!=KNOWN_SHA
            or any(v not in cover for v in ['敦陽科技(2480)','115年第二季法人說明會'])
            or selected['event_date']!='2026-08-05'
            or any(v not in disclaimer for v in ['免責聲明','資料來源及各項聲明','最新科技的演進','公開資訊觀測站的公告資訊'])
            or '敦陽資訊' not in pages[4]['text']
            or '115年1-6月' not in pages[24]['text'] or '114年1-6月' not in pages[24]['text']
            or '年度累計' not in pages[38]['text']
            or re.sub(r'\s+','',pages[43]['text'])!='Q&AThankyou!!44'):
        raise ValueError('STI native issuer period or limitations unverified')
    return native


def _context(selected,native,proof):
    doc={'document_id':'2480:'+selected['event_date']+':'+native['content_sha256'][:16],
         'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
         'projection_policy':PROJECTION_POLICY,'title':selected['title'],'url':PDF_URL,'language':'zh-TW',
         'event_date':selected['event_date'],'event_date_basis':'official_issuer_index_row; cover_period_matches',
         'event_time':None,'event_timezone':'Asia/Taipei',
         'event_status':'published_past_event_not_independently_occurrence_verified',
         'content_periods':CONTENT_PERIODS[:],'published_at':None,'material_file_date':None,
         'retrieved_at_epoch':proof['pdf']['retrieved_at'],'content_sha256':native['content_sha256'],
         'page_count':44,'pages':native['pages'],'binary_complete':True,'text_extraction_complete':True,
         'native_text_coverage':'complete','coverage_status':'partial','full_content_coverage_verified':False,
         'missing_text_pages':native['empty_pages'],'garbled_pages':native['garbled_pages'],'parser_version':native['parser_version'],
         'sti_glyph_evidence':native['sti_glyph_evidence'],
         'known_native_text_omissions':[{'page_number':p,'issue':
                'bar_values_and_quarter_labels_missing_from_native_text' if p==26 else
                'pie_labels_and_percentages_missing_from_native_text' if p==37 else
                'visual_content_not_independently_verified_from_native_text'}
                for p in (*range(26,36),37,38,*range(40,44))],
         'subsidiary_scope_caution':'第5頁敦陽資訊子公司得獎陳述不能當成敦陽科技母公司的獨立事實；其餘合併口徑須保留。',
         'financial_scope_caution':'第24頁合併資產負債日期為2026-06-30、2025-12-31、2025-06-30，單位新台幣千元；第25及39頁為2026/2025上半年累計，第25頁EPS為新台幣元，第26頁為季度，不可混用。法說簡報不是完整年度財報，不覆寫TTM。',
         'forward_looking_caution':'第2頁明示來源及各項聲明可能因科技演進等因素改變，應以公開資訊觀測站公告為準；第36頁尚未履行履約義務、預計完成比率與金額是未來履約資訊，不是已實現營收、新訂單或獲利指引。預期與展望不是已實現事實。',
         'q_and_a_transcript_available':False,'disclaimer_pages':[2],'commercial_reuse_permission_verified':False}
    return {'ticker':TICKER,'date':selected['event_date'],'period':selected['period'],'title':selected['title'],
            'source':PROVIDER,'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
            'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-TW'}],'documents':[doc],
            'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
            'fetched_at_epoch':proof['pdf']['retrieved_at'],'sti_conference_receipt':proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and valid_expiry(proof[k],observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_sti(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['sti_conference_receipt']
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


def fetch_sti_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_sti(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'sti_presentation_workflow':True}
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
        details.update(sti_originals_verified=True,coverage_status='native_presentation_text_complete',
                       cache_hit=pdf['cache_hit'],stale=False,fetched_at_epoch=pdf['retrieved_at'],message=NOTE)
    except Exception as original:
        if time.monotonic() >= deadline:
            exc = SourceResponseError('timeout')
        else:
            exc = original if isinstance(original,SourceResponseError) else SourceResponseError('parse_error')
        details.update(sti_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','2480'),('official_name','敦陽科'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'敦陽科',LEGAL,'敦陽科技','stark','stark technology','stark technology inc.','stark technology inc','stark technology incorporated'}
    aliases = names | {'2480','2480.tw'}
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
    return isinstance(value,dict) and ('sti_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
