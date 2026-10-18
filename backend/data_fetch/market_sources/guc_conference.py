"""Discover dated issuer presentations, without upgrading visual or date claims."""
from copy import deepcopy
from datetime import date, datetime
import re
import time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .guc_conference_transport import GucConferenceHttp, MASTER_URL, INDEX_URL, PROVIDER, pdf_url, original_bytes
from .conference_issuer_master import master_rows, reference_epoch, is_shared, current_at
from .tcfhc_conference_transport import valid_epoch

TICKER = '3443.TW'
LEGAL = '創意電子股份有限公司'
UBN = '16299879'
POLICY = 'guc-dated-presentation-v1'
NOTE = ('創意官方季度準備簡報，非逐字稿；法說日期與簡報日期分開保存，清單日期並非首次發布或實際舉行的獨立證明。'
        '公司前瞻陳述受風險與不確定性影響，不是已實現結果；公司說法未獨立查證。'
        '僅投影含完整當季、前季、去年同季欄頭與NT$M單位的季度損益表，EPS另為NT$；不可當年度查核財報。'
        '完整原生頁面保留；未映射符號、年度表格期間欄頭與未資格化圖表的限制依逐頁旗標保存，不能作完整圖表或財務宣稱。'
        '新版本僅接受相同可驗的季度表契約，其他頁面未資格化，不將圖表標題當展望或問答正文。'
        '官網允許資訊用途的單份下載，不代表公開重製或散布授權；引用限必要片段並附來源。')


def supports_guc(ticker):
    return str(ticker).strip().upper() == TICKER


def _today(epoch):
    return datetime.fromtimestamp(epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    observed = reference_epoch(epoch, as_of_epoch=as_of_epoch)
    rows = master_rows(raw, epoch, source_url)
    matched = [r for r in rows if r.get('公司代號') == '3443']
    if len(matched) != 1:
        raise ValueError('Guc master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '創意', '營利事業統一編號': UBN,
                '網址': 'www.guc-asic.com'}
    if (any(row.get(k) != v for k, v in expected.items()) or row.get('英文簡稱', '').strip() != 'GUC'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Guc master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(observed) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Guc master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_ubn': UBN, 'as_of': day.isoformat()}


def select_presentation(raw, epoch, *, as_of_epoch=None):
    today = min(_today(reference_epoch(epoch, as_of_epoch=as_of_epoch)), _today(epoch))
    if not isinstance(raw,bytes) or not 0 < len(raw) <= 500_000:
        raise ValueError('invalid index size')
    text=raw.decode('utf-8-sig','strict'); soup=BeautifulSoup(text,'html.parser')
    if (text.count('</html>') != 1 or text.count('</body>') != 1 or not soup.title
            or soup.title.get_text(' ',strip=True) != 'GUC - Financial'):
        raise ValueError('complete issuer index required')
    events={}
    for row in soup.select('.tr'):
        cells=row.find_all('div',class_='td',recursive=False)
        if len(cells)!=2:continue
        title=cells[1].get_text(' ',strip=True)
        m=re.fullmatch(r'Quarterly Results & (Business Report|Investor Conference) - Q([1-4]) (20[0-9]{2})',title)
        if not m:continue
        d=re.fullmatch(r'(20[0-9]{2})/([0-9]{2})/([0-9]{2})\([A-Za-z]{3}\) ([0-9]{2}):([0-9]{2})',cells[0].get_text(' ',strip=True))
        if not d:raise ValueError('calendar date ambiguous')
        day=date(*map(int,d.groups()[:3]));hour,minute=map(int,d.groups()[3:])
        if hour>23 or minute>59:raise ValueError('calendar time invalid')
        year,quarter=int(m[3]),int(m[2])
        following=date(year+1,1,1) if quarter==4 else date(year,quarter*3+1,1)
        if not 0 <= (day-following).days <= 100:raise ValueError('calendar quarter inconsistent')
        key=(year,quarter);kind=m[1]
        if kind in events.setdefault(key,{}):raise ValueError('duplicate quarterly event')
        events[key][kind]=(day,title)
    past=[key for key,rows in events.items() if any(day<today for day,_ in rows.values())]
    if not past:raise ValueError('no past quarterly event')
    period=max(past); rows=events[period]
    if set(rows) != {'Business Report','Investor Conference'}:
        raise ValueError('latest quarter has no uniquely paired investor conference')
    doc_day,_=rows['Business Report']; event,title=rows['Investor Conference']
    if not doc_day <= event < today or not 0 <= (event-doc_day).days <= 7 or (today-event).days>370:
        raise ValueError('latest quarter event not current and past')
    candidates=[];seen=set()
    for group in soup.select('.quarterly-list[data-year]'):
        if not re.fullmatch(r'20[0-9]{2}',group['data-year']):raise ValueError('invalid quarterly year')
        for item in group.select('.quarterly-item'):
            label=item.select_one('.quarterly-title')
            m=re.fullmatch(r'(20[0-9]{2}) Q([1-4])',label.get_text(' ',strip=True) if label else '')
            if not m or m[1] != group['data-year']:raise ValueError('quarterly attachment label invalid')
            key=(int(m[1]),int(m[2]))
            if key in seen:raise ValueError('duplicate attachment quarter')
            seen.add(key)
            if key != period:continue
            links=[]
            for row in item.select('.tbody .tr'):
                label=row.select_one('.paragraph-bold')
                if label and label.get_text(' ',strip=True)=='Quarterly Result Presentation Material':
                    links.extend(row.select('a[href]'))
            if len(links)!=1:raise ValueError('latest quarter requires unique presentation')
            url=urljoin(INDEX_URL,links[0]['href'])
            if not pdf_url(url):raise ValueError('invalid presentation route')
            if '/upload/'+doc_day.strftime('%Y_%m_%d')+'/' not in url:
                raise ValueError('attachment date differs from quarterly business report')
            candidates.append(url)
    if len(candidates)!=1:raise ValueError('latest quarter presentation unavailable')
    return {'event_date':event.isoformat(),'event_end_date':event.isoformat(),'event_title':title,
            'document_date':doc_day.isoformat(),'year':period[0],'quarter':period[1],
            'period_label':str(period[0])+'Q'+str(period[1]),'pdf_url':candidates[0],
            'selection_policy':'latest_past_quarter_with_unique_calendar_and_presentation_pair'}


def _quarter_table(text, selected):
    year,quarter=selected['year'],selected['quarter']
    previous=quarter-1 if quarter>1 else 4
    previous_year=year if quarter>1 else year-1
    q=f'{quarter}Q{year%100:02d}';p=f'{previous}Q{previous_year%100:02d}';y=f'{quarter}Q{(year-1)%100:02d}'
    number=r'(?:-?\d[\d,]*(?:\.\d+)?|\(\d[\d,]*(?:\.\d+)?\))'
    percent=r'-?\d+(?:\.\d+)?%'
    def row(label):
        return rf'{re.escape(label)}\s+{number}\s+{percent}\s+{number}\s+{number}\s+{percent}'
    percentages=rf'%\s+{percent}\s+{percent}\s+{percent}'
    # We project this page whole, so every nonempty line must belong to the
    # qualified table or its exact known footer/page-number layout. Merely
    # finding required rows would also admit an adjacent unqualified table.
    patterns=[r'\d{2}/\d{2}/20\d{2} © 20\d{2} GUC Proprietary & Security B',
              r'\d{1,2}', rf'{q} Statements of Comprehensive Income',
              rf'Unit: NT\$M {q} QoQ {p} {y} YoY',
              row('Revenues'),row('NRE & IP'),row('Turnkey'),row('Gross Margin'),percentages,
              row('SG&A Exp'),row('R&D Exp'),row('Operating Income'),percentages,
              rf'Non-Operating Items\s+{number}\s+{number}\s+{number}',
              rf'Income Tax\s+{number}\s+{number}\s+{number}',
              row('Net Income'),percentages,row('EPS (NT$)')]
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    return len(lines)==len(patterns) and all(re.fullmatch(pattern,line) for pattern,line in zip(patterns,lines))


def native_presentation(raw, selected, deadline):
    _check(deadline)
    native=extract_pdf_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    _check(deadline)
    pages=native['pages'];bad=set(native['empty_pages'])|set(native['garbled_pages'])
    name=('First','Second','Third','Fourth')[selected['quarter']-1]
    cover=f"{selected['year']} {name} Quarter Results"
    stamp=date.fromisoformat(selected['document_date']).strftime('%m/%d/%Y')
    if (not 3<=native['page_count']<=50 or any('GUC Proprietary & Security B' not in p['text'] for p in pages)
            or sum(cover in p['text'] and 'IR Conference' in p['text'] and stamp in p['text'] and p['page_number'] not in bad for p in pages)!=1):
        raise ValueError('native presentation identity, date or quarter unverified')
    qualified=[p['page_number'] for p in pages if p['page_number'] not in bad and _quarter_table(p['text'],selected)]
    if len(qualified)!=1:raise ValueError('unique full quarterly table unavailable')
    # Original 20-page text is kept untouched. Only the native table contract
    # is qualified for role use, never annual mixed columns or chart values.
    excluded=[p['page_number'] for p in pages if p['page_number'] not in qualified]
    return native,excluded


def _context(selected, native, conflicts, proof):
    doc = {'document_id': '3443:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': TICKER, 'source': PROVIDER, 'source_type': 'issuer_official', 'document_kind': 'presentation',
           'title': selected['event_title'], 'url': selected['pdf_url'], 'event_date': selected['event_date'],
           'event_date_basis': 'issuer_published_quarterly_calendar_and_attachment_pair', 'event_end_date': selected['event_end_date'], 'published_at': None,
           'event_status': 'announced_past_date_not_independently_occurrence_verified',
           'document_date': selected['document_date'], 'content_period': selected['period_label'],
           'projection_policy': 'guc-complete-quarterly-native-table-v1', 'selected_quarter': {'year': selected['year'], 'quarter': selected['quarter']},
           'retrieved_at_epoch': proof['pdf']['retrieved_at'], 'content_sha256': native['content_sha256'],
           'page_count': native['page_count'], 'pages': native['pages'], 'binary_complete': True,
           'text_extraction_complete': native['coverage_status'] == 'complete', 'native_text_coverage': native['coverage_status'], 'coverage_status': 'partial',
           'full_content_coverage_verified': False, 'missing_text_pages': native['empty_pages'], 'garbled_pages': native['garbled_pages'],
           'projection_excluded_pages': conflicts,
           'known_native_text_omission_pages': sorted(set(native['garbled_pages']) | {p['page_number'] for p in native['pages'] if any(t in p['text'] for t in ('Breakdown','Revenue & Gross Margin','OPEX & OPM','NPM & EPS'))}),
           'native_period_alignment_unverified_pages': [p['page_number'] for p in native['pages'] if 'Statements of Comprehensive Income' in p['text'] and not _quarter_table(p['text'],selected)],
           'parser_version': native['parser_version'],
           'financial_scope_caution': NOTE, 'commercial_reuse_permission_verified': False}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': selected['period_label'],
            'title': selected['event_title'], 'source': PROVIDER, 'source_url': INDEX_URL,
            'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'url': selected['pdf_url'], 'kind': 'presentation', 'language': 'en'}],
            'documents': [doc], 'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'guc_conference_receipt': proof}


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = time.monotonic()+10. if deadline is None else deadline
    try:
        _check(deadline)
        if not supports_guc(ticker) or not isinstance(value, dict) or value.get('ticker') != TICKER:
            return False
        proof = value['guc_conference_receipt']
        if set(proof) != {'policy', 'identity', 'index', 'pdf', 'selected'} or proof['policy'] != POLICY or not is_shared(proof['identity']):
            return False
        if proof['index'].get('cache_hit') is not False:return False
        identity = proof['identity']; url = identity['source_url']
        parse_master(original_bytes(identity, url, max_age=max_age), identity['retrieved_at'], url)
        selected = select_presentation(original_bytes(proof['index'], INDEX_URL, max_age=max_age), proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        native, conflicts = native_presentation(original_bytes(proof['pdf'], selected['pdf_url'], max_age=max_age), selected, deadline)
        expected = _context(selected, native, conflicts, proof)
        _check(deadline)
        verified = value == expected and current_at(identity, max_age, time.time()) and all(valid_epoch(proof[k]['retrieved_at'], max_age) for k in ('index','pdf'))
        _check(deadline)
        return verified
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, OverflowError, SourcePdfError):
        return False


def fetch_guc_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_guc(ticker): return {}
    deadline = time.monotonic()+20.
    http = GucConferenceHttp(deadline, force_refresh=force_refresh, use_cache=use_cache)
    details = {'actual_provider': PROVIDER, 'guc_presentation_workflow': True}
    try:
        raw, identity = http.get_receipt(MASTER_URL); parse_master(raw, identity['retrieved_at'], identity['source_url'])
        raw, index = http.get_receipt(INDEX_URL); selected = select_presentation(raw, index['retrieved_at'])
        raw, pdf = http.get_receipt(selected['pdf_url']); native, conflicts = native_presentation(raw, selected, deadline)
        proof = {'policy': POLICY, 'identity': identity, 'index': index, 'pdf': pdf, 'selected': selected}
        value = _context(selected, native, conflicts, proof)
        if not verify_context(value, ticker, deadline=deadline, max_age=1800):
            raise SourceResponseError('original_unverified')
        _check(deadline)
        details.update(guc_originals_verified=True, coverage_status='native_presentation_text_partial',
                       cache_hit=pdf['cache_hit'], fetched_at_epoch=pdf['retrieved_at'], message=NOTE)
        details.update(component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count)
        if diagnostics is not None: diagnostics.update(details)
        # Diagnostics serialization and lock cleanup are part of this delivery.
        _check(deadline)
        observed=time.time()
        if (not current_at(identity,1800,observed) or any(
                type(proof[k]['retrieved_at']) not in (int,float)
                or not 0 <= observed-proof[k]['retrieved_at'] < 1800 for k in ('index','pdf'))):
            raise SourceResponseError('original_expired')
        return value
    except Exception as original:
        exc = original if isinstance(original, SourceResponseError) else SourceResponseError('parse_error')
        # A late delivery failure must not retain successful body/cache markers.
        # Keep the actual HTTP/component evidence so the failed attempt is counted.
        for target in (details, diagnostics, exc.diagnostic):
            if target is not None:
                for key in ('cache_hit', 'coverage_status', 'fetched_at_epoch', 'message'):
                    target.pop(key, None)
        details.update(error_kind=exc.error_kind, status='error', guc_originals_verified=False,
                       component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None: diagnostics.update(details)
        if exc is original: raise
        raise exc from original


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data, dict) or data.get('ticker') != ticker
            or data.get('stock_id') not in (None, '', '3443')
            or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type','quote_type','quoteType'))): return False
    identity = data.get('company_identity')
    if identity is None: identity = {}
    if not isinstance(identity, dict): return False
    for k, expected in [('ticker',TICKER),('stock_id','3443'),('official_name','創意'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY'),('quote_type','EQUITY'),('quoteType','EQUITY')]:
        if identity.get(k) not in (None, '', expected): return False
    name = data.get('company_name')
    names = {'創意', '創意電子', LEGAL, 'global unichip corp.', 'global unichip corporation', 'guc'}
    if name is not None and (not isinstance(name,str) or any(s.strip().casefold() not in names for s in name.split(' / '))): return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows = identity.get(key, [])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows): return False
    return not ({'創意', LEGAL} & {s.strip('* ').strip() for s in identity.get('forbidden_aliases',[])})


def is_marked(value):
    return isinstance(value,dict) and ('guc_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or pdf_url(d.get('url')))
        for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))


def role_pages(document):
    if (document.get('ticker') != TICKER or document.get('source') != PROVIDER
            or document.get('coverage_status') != 'partial'
            or document.get('projection_policy') != 'guc-complete-quarterly-native-table-v1'):
        return []
    selected=document.get('selected_quarter',{})
    if type(selected.get('year')) is not int or type(selected.get('quarter')) is not int or not 1<=selected['quarter']<=4:return []
    excluded=set(document.get('missing_text_pages',[]))|set(document.get('garbled_pages',[]))|set(document.get('projection_excluded_pages',[]))
    return [deepcopy(p) for p in document.get('pages',[]) if isinstance(p,dict) and isinstance(p.get('text'),str)
            and p.get('page_number') not in excluded and _quarter_table(p['text'],selected)]
