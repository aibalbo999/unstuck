"""Bounded issuer transcript with explicit original-language and translation limits."""
from . import conference_issuer_master as master_identity
from copy import deepcopy
from datetime import date,datetime
import re,time,zlib
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import extract_pdf_pages,SourcePdfError
from .delta_conference_transport import ConferenceHttp,MASTER_URL,INDEX_URL,PROVIDER,RAW_TTL,original_bytes,route_kind

TICKER='2308.TW'
LEGAL='台達電子工業股份有限公司'
LEGACY_POLICY = 'delta-original-translated-transcript-v1'
POLICY = 'delta-original-translated-transcript-v2'
NOTE=('台達電官方英文法說逐字稿依中文口述編製，官方明示可能有翻譯錯漏，應以中文原音為準；未由影音或獨立來源驗證翻譯、實際會議及陳述。'
      '原生文字取得不代表翻譯正確或所有圖像完整；展望、問題與回答須分開，不覆寫經核對的年度財報或TTM。')

def supports_delta(ticker):return str(ticker).strip().upper()in{'2308',TICKER}
def _today(epoch=None):return datetime.fromtimestamp(time.time()if epoch is None else epoch,ZoneInfo('Asia/Taipei')).date()
def _check(deadline):
    if time.monotonic()>=deadline:raise SourceResponseError('timeout')

def parse_master(raw, epoch, url=MASTER_URL, *, as_of_epoch=None):
    observed = master_identity.reference_epoch(epoch, as_of_epoch=as_of_epoch)
    rows = master_identity.master_rows(raw, epoch, url)
    selected=[r for r in rows if r.get('公司代號')=='2308']
    if len(selected)!=1:raise ValueError('Delta master issuer not unique')
    row=selected[0]
    expected={'公司名稱':LEGAL,'公司簡稱':'台達電','營利事業統一編號':'34051920','英文簡稱':'DELTA','網址':'https://www.deltaww.com/zh-TW/index'}
    if any(row.get(k)!=v for k,v in expected.items())or not re.fullmatch(r'\d{7}',row.get('出表日期','')):raise ValueError('Delta master identity invalid')
    d=row['出表日期'];day=date(int(d[:3])+1911,int(d[3:5]),int(d[5:]))
    if not 0<=(_today(observed)-day).days<=14 or day>_today(epoch):raise ValueError('Delta master date invalid')
    return {'ticker':TICKER,'legal_name':LEGAL,'official_ubn':'34051920','as_of':day.isoformat()}

def _future_webcast(card, soup, observed):
    """Only skip an explicitly future webcast bound to its official year section."""
    markers = [s.get_text(' ', strip=True) for s in card.select('span')
               if not s.find('span') and 'Live webcast will start' in s.get_text()]
    if len(markers) != 1:
        raise ValueError('Delta scheduled event date ambiguous')
    match = re.fullmatch(
        r'Live webcast will start on (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) '
        r'([1-9]|[12]\d|3[01]), (1[0-2]|[1-9]) (AM|PM)', markers[0])
    region = card.find_parent(attrs={'role': 'region'})
    if not match or region is None:
        raise ValueError('Delta scheduled event unverified')
    region_id, label_id = region.get('id'), region.get('aria-labelledby')
    if not isinstance(region_id, str) or not region_id or not isinstance(label_id, str) or not label_id:
        raise ValueError('Delta scheduled event year unverified')
    labels = soup.find_all(id=label_id)
    if (len(soup.find_all(id=region_id)) != 1 or len(labels) != 1
            or labels[0].name != 'button' or labels[0].get('aria-controls') != region_id
            or labels[0].find_parent('div') is not region.parent):
        raise ValueError('Delta scheduled event year ambiguous')
    year = labels[0].get_text(' ', strip=True)
    if not re.fullmatch(r'20\d{2}', year):
        raise ValueError('Delta scheduled event year invalid')
    month = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec').index(match[1]) + 1
    scheduled = date(int(year), month, int(match[2]))
    # Same-day and past announcements without published material must not
    # silently select an older transcript as the latest completed meeting.
    if scheduled <= _today(observed):
        raise ValueError('Delta scheduled event is no longer future')
    return True


def select_transcript(raw, *, as_of_epoch=None):
    observed = master_identity.reference_epoch(as_of_epoch=as_of_epoch)
    soup=BeautifulSoup(raw.decode('utf-8','strict'),'html.parser')
    text=soup.get_text(' ',strip=True)
    if (not soup.title or soup.title.get_text()!='Investors - Analyst Meetings - Delta'
            or not re.search(r'© 20\d{2} Delta Electronics, Inc\. All Rights Reserved\.',text)
            or 'Taiwan Stock Exchange (Stock ticker:2308)'not in text):raise ValueError('Delta index owner unverified')
    events={}
    for label in soup.select('span'):
        if not re.fullmatch(r'[1-4]Q Analyst Meeting',label.get_text(' ',strip=True)):continue
        card=label.parent.parent;labels=[s.get_text(' ',strip=True)for s in card.select('span')if re.fullmatch(r'[1-4]Q Analyst Meeting',s.get_text(' ',strip=True))]
        dates=[s.get_text(' ',strip=True)for s in card.select('span')if not s.find('span') and re.fullmatch(r'\d{2}/\d{2}/20\d{2}',s.get_text(' ',strip=True))]
        if len(labels)!=1:raise ValueError('Delta event label/date ambiguous')
        if not dates and _future_webcast(card, soup, observed):continue
        if len(dates)!=1 or any('Live webcast will start' in s.get_text() for s in card.select('span')):
            raise ValueError('Delta event label/date ambiguous')
        day=datetime.strptime(dates[0],'%m/%d/%Y').date();q=int(labels[0][0]);year=day.year
        if day>_today(observed):continue
        if (_today(observed)-day).days>370:continue
        links=[a['href']for a in card.select('a[href]')if a.get_text(' ',strip=True)=='Transcript']
        if len(links)>1 or (links and links[0]!=f'https://filecenter.deltaww.com/IR/download/calendar/{q}Q{year%100:02d}_Transcript.pdf'):raise ValueError('Delta attachment/period mismatch')
        if day in events:raise ValueError('Delta event ambiguous')
        events[day]={'event_date':day.isoformat(),'period':f'{year}Q{q}','url':links[0]if links else None,'title':f'Delta Electronics {q}Q {year} Results Meeting translated transcript'}
    if not events:raise ValueError('Delta current event absent')
    selected=events[max(events)]
    return selected if selected['url']else None

def native_transcript(raw,selected,deadline):
    _check(deadline)
    try:native=extract_pdf_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline);cover=re.sub(r'\s+','',native['pages'][0]['text']);year,q=selected['period'].split('Q');day=date.fromisoformat(selected['event_date'])
    if (native['coverage_status']!='complete'or native['empty_pages']or native['garbled_pages']or not 1<=native['page_count']<=40
            or f'DeltaElectronics{q}Q{year}ResultsMeeting'not in cover
            or day.strftime('%B')+str(day.day)+','+year+',3:00pmTaiwanTime'not in cover
            or 'ThisEnglishtranscriptiscompiledbasedontheoralMandarinChinese'not in cover
            or 'originalMandarinChineseremarksshallprevail.'not in cover):raise ValueError('Delta native transcript/translation disclaimer unverified')
    return native

def _context(selected,native,proof):
    doc={'document_id':'2308:'+selected['event_date']+':'+native['content_sha256'][:16],
         'ticker':TICKER,'title':selected['title'],'url':selected['url'],'source':PROVIDER,'source_type':'issuer_official',
         'document_kind':'transcript','projection_policy':'delta-translated-transcript-role-v1',
         'language':'en','translated_from_language':'zh-TW','translation_accuracy_verified':False,
         'event_date':selected['event_date'],'event_date_basis':'official_index_and_transcript_cover',
         'event_time_Taipei':'15:00','published_at':None,'material_file_date':None,'content_period':selected['period'],
         'transcript_accuracy_independently_verified':False,'retrieved_at_epoch':proof['transcript']['retrieved_at'],
         'content_sha256':native['content_sha256'],'binary_complete':True,'page_count':native['page_count'],'pages':native['pages'],
         'missing_text_pages':native['empty_pages'],'garbled_pages':native['garbled_pages'],'text_extraction_complete':True,
         'native_text_coverage':'complete','coverage_status':'partial','full_content_coverage_verified':False,'parser_version':native['parser_version']}
    if native.get('native_font_mapping_evidence'):doc['native_font_mapping_evidence']=deepcopy(native['native_font_mapping_evidence'])
    return {'ticker':TICKER,'date':selected['event_date'],'period':selected['period'],'title':selected['title'],
            'summary':'','transcript_excerpt':'','transcript_available':True,'source':PROVIDER,'source_url':INDEX_URL,
            'materials':[{'url':selected['url'],'kind':'transcript'}],'documents':[doc],'coverage_status':'partial',
            'coverage_notes':[NOTE],'fetched_at_epoch':proof['transcript']['retrieved_at'],'delta_transcript_receipt':proof}

def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(master_identity.current_at(proof[key], max_age, observed)
               for key in ('identity', 'index', 'transcript'))

def verify_context(value,ticker,*,deadline=None,max_age=86400):
    deadline=time.monotonic()+10. if deadline is None else deadline
    try:
        _check(deadline)
        if not supports_delta(ticker)or not isinstance(value,dict)or value.get('ticker')!=TICKER:return False
        proof=value['delta_transcript_receipt']
        if set(proof)!={'policy','identity','index','transcript','selected'}or not master_identity.valid_master_policy(proof['policy'],proof['identity'],POLICY,LEGACY_POLICY):return False
        parse_master(original_bytes(proof['identity'],proof['identity']['source_url'],max_age=max_age),proof['identity']['retrieved_at'],proof['identity']['source_url'])
        selected=select_transcript(original_bytes(proof['index'],INDEX_URL,max_age=max_age))
        if not selected or selected!=proof['selected']or date.fromisoformat(selected['event_date'])>_today(proof['index']['retrieved_at']):return False
        raw=original_bytes(proof['transcript'],selected['url'],max_age=max_age)
        expected=_context(selected,native_transcript(raw,selected,deadline),proof);_check(deadline)
        # Extraction time must not extend any original receipt's validity.
        for key,url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('transcript',selected['url'])]:original_bytes(proof[key],url,max_age=max_age)
        _check(deadline);return value==expected and _originals_fresh(proof, max_age)
    except SourceResponseError as exc:
        if exc.error_kind=='timeout':raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):return False

def fetch_delta_context(ticker,*,diagnostics=None,force_refresh=False,use_cache=True):
    if not supports_delta(ticker):return {}
    deadline=time.monotonic()+20.;http=ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details={'actual_provider':PROVIDER,'delta_transcript_workflow':True}
    try:
        raw,identity=http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url'])
        raw,index=http.get_receipt(INDEX_URL);selected=select_transcript(raw)
        if selected is None:raise SourceResponseError('transcript_not_published')
        raw,transcript=http.get_receipt(selected['url']);native=native_transcript(raw,selected,deadline)
        proof={'policy':POLICY,'identity':identity,'index':index,'transcript':transcript,'selected':selected};context=_context(selected,native,proof)
        if not verify_context(context,TICKER,deadline=deadline,max_age=RAW_TTL):raise SourceResponseError('original_unverified')
        details.update(coverage_status='native_translated_text_complete',delta_originals_verified=True,
                       cache_hit=transcript['cache_hit'],fetched_at_epoch=transcript['retrieved_at'],message=NOTE);_check(deadline)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),http_request_count=http.http_request_count)
        _check(deadline)
        if not _originals_fresh(proof, RAW_TTL):raise SourceResponseError('original_expired')
    except Exception as original:
        exc=original if isinstance(original,SourceResponseError)else SourceResponseError('parse_error')
        details.update(delta_originals_verified=False,error_kind=exc.error_kind,status='error',component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original
    if diagnostics is not None:diagnostics.update(details)
    return context

def validate_context(data,ticker):
    from source_applicability import instrument_type
    if (ticker!=TICKER or not isinstance(data,dict)or data.get('ticker')!=ticker or instrument_type(data)!='EQUITY'
            or any(data.get(k)not in(None,'','EQUITY')for k in('instrument_type','quote_type','quoteType'))):return False
    identity=data.get('company_identity')
    if identity is None:identity={}
    if not isinstance(identity,dict):return False
    for k,v in [('ticker',TICKER),('stock_id','2308'),('official_name','台達電'),('legal_name',LEGAL),('official_ubn','34051920'),('instrument_type','EQUITY')]:
        if identity.get(k)not in(None,'',v):return False
    for k in ('allowed_aliases','english_names','forbidden_aliases'):
        values=identity.get(k,[])
        if not isinstance(values,(list,tuple))or any(not isinstance(v,str)for v in values):return False
    names={'台達電',LEGAL,'delta electronics, inc.','delta electronics inc.','delta electronics inc'}
    name=data.get('company_name')
    if name is not None and (not isinstance(name,str)or not all(v.strip().casefold()in names for v in name.split(' / '))):return False
    if {'台達電',LEGAL}&{s.strip('* ').strip()for s in identity.get('forbidden_aliases',[])}:return False
    return True

def is_marked(value):
    return isinstance(value,dict)and('delta_transcript_receipt'in value or value.get('source')==PROVIDER or value.get('source_url')==INDEX_URL
        or any(isinstance(d,dict)and(d.get('source')==PROVIDER or route_kind(d.get('url'))=='transcript')for k in('documents','materials')for d in(value.get(k)if isinstance(value.get(k),list)else[])))
