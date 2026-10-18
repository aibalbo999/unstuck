"""Common published-material workflow, enabled for qualified issuer profiles."""
from copy import deepcopy
import csv
from datetime import date, datetime
from hashlib import sha256
import io
import math
import re
import time
import unicodedata
import zlib
from zoneinfo import ZoneInfo

from search_admission import endpoint_admission
from search_provider_runtime import SourceResponseError
from source_pdf_reader import extract_pdf_pages, SourcePdfError
from source_pptx_reader import extract_pptx_pages, SourcePptxError
from mops_published_materials import select_published_material
from mops_material_transport import (index_request, download_conference_index, download_published_material, static_material_request, PROVIDER)
from mops_material_originals import get_original, original_bytes, RAW_TTL, GUARD, _check
from mops_previous_year import POLICY as PREVIOUS_POLICY, exact_no_results, eligible_previous
from .official_issuer_master_transport import IssuerMasterHttp as MasterHttp, MASTER_URL, JSON_URL, original_bytes as master_bytes

from .mops_otc_master import OtcMasterHttp, OTC_MASTER, original_bytes as otc_master_bytes

POLICY = 'mops-published-presentation-v1'
STATIC_POLICY = 'mops-published-presentation-static-get-v1'
# Identity/format qualification is staged, not a promise that every MOPS file
# has readable or reusable text. URLs, filenames, years and hashes are dynamic.
PROFILES = {
    '6669.TW': {'short':'緯穎','legal':'緯穎科技服務股份有限公司','ubn':'53687704',
                'master_english':'Wiwynn','website':'https://www.wiwynn.com','format':'pdf',
                'native_name':'Wiwynn Corporation','previous_year_fallback':True,
                'aliases':{'wiwynn','wiwynn corporation'}},
    '2606.TW': {'short':'裕民','legal':'裕民航運股份有限公司','ubn':'47067419',
                'master_english':'U-MING','website':'http://www.uming.com.tw','format':'pdf',
                'native_name':'U-Ming Marine Transport Corporation','previous_year_fallback':True,
                'aliases':{'u-ming','u-ming marine transport corporation','u-ming marine transport corp.','u-ming marine transport corp'}},
    '6282.TW': {'short':'康舒','legal':'康舒科技股份有限公司','ubn':'12341051',
                'master_english':'Acbel','website':'http://www.acbel.com','format':'pdf',
                'native_name':'Acbel Polytech Inc.','previous_year_fallback':True,
                'aliases':{'acbel','acbel polytech inc.','acbel polytech inc'}},
    '9945.TW': {'short':'潤泰新','legal':'潤泰創新國際股份有限公司','ubn':'12139612',
                'master_english':'RUENTEX DEVELOP','website':'www.rt-develop.com.tw','format':'pdf',
                'native_name':'RUENTEX DEVELOPMENT Co. Ltd','previous_year_fallback':True,
                'aliases':{'ruentex develop','ruentex development co.,ltd.','ruentex development co ltd','ruentex development co. ltd'}},
    '2441.TW': {'short':'超豐','legal':'超豐電子股份有限公司','ubn':'05126366',
                'master_english':'GTK','website':'www.greatek.com.tw','format':'pdf',
                'native_name':'Greatek Electronics','previous_year_fallback':True,
                'aliases':{'gtk','greatek electronics inc.','greatek electronics inc'}},
    '2338.TW': {'short':'光罩','legal':'台灣光罩股份有限公司','ubn':'22099408',
                'master_english':'TMC','website':'http://www.tmcnet.com.tw','format':'pdf',
                'native_name':'TAIWAN MASK CORPORATION','previous_year_fallback':True,
                'aliases':{'tmc','taiwan mask corporation','taiwan mask corp'}},
    '1312.TW': {'short':'國喬','legal':'國喬石油化學股份有限公司','ubn':'04212250',
                'master_english':'GPPC','website':'http://www.gppc.com.tw','format':'pdf',
                'native_name':'GRAND PACIFIC PETROCHEMICAL CORPORATION',
                'aliases':{'gppc','grand pacific petrochemical corporation','grand pacific petrochemical'}},
    '2354.TW': {'short':'鴻準','legal':'鴻準精密工業股份有限公司','ubn':'23707801',
                'master_english':'FTC','website':'www.foxconntech.com.tw','format':'pdf',
                'native_name':'Foxconn Technology Corp.',
                'aliases':{'ftc','foxconn technology corp.','foxconn technology co., ltd.','foxconn tech co'}},
    '6269.TW': {'short':'台郡','legal':'台郡科技股份有限公司','ubn':'16347324',
                'master_english':'FLEXIUM','website':'https://www.flexium.com.tw','format':'pdf',
                'native_name':'Flexium Interconnect Inc.',
                'aliases':{'flexium','flexium interconnect, inc.','flexium interconnect inc','flexium interconnect inc.'}},
    '2313.TW': {'short':'華通','legal':'華通電腦股份有限公司','ubn':'04401392',
                'master_english':'COMPEQ','website':'www.compeq.com.tw','format':'pdf',
                'native_name':'COMPEQ MANUFACTURING CO., LTD.',
                'aliases':{'compeq','compeq manufacturing co., ltd.','compeq mfg co','compeq manufacturing'}},
    '2353.TW': {'short':'宏碁','legal':'宏碁股份有限公司','ubn':'20828393',
                'master_english':'ACER','website':'http://www.acer.com','format':'pdf',
                'native_name':'Acer','aliases':{'acer','acer incorporated','acer inc'}},
    '2382.TW': {'short':'廣達','legal':'廣達電腦股份有限公司','ubn':'22822281',
                'master_english':'QCI','website':'www.quantatw.com','format':'pdf',
                'native_name':'Quanta Computer Inc.','aliases':{'qci','quanta computer inc.','quanta computer'}},
    '1301.TW': {'short': '台塑', 'legal': '台灣塑膠工業股份有限公司', 'ubn': '75708007',
                'master_english': 'FPC', 'website': 'http://www.fpc.com.tw', 'format': 'pdf',
                'native_name': 'Formosa Plastics Corporation',
                'aliases': {'fpc','formosa plastics corporation','formosa plastics corp','formosa plastic'}},
    '1102.TW': {'short': '亞泥', 'legal': '亞洲水泥股份有限公司', 'ubn': '03244509',
                'master_english': 'ACC', 'website': 'www.acc.com.tw', 'format': 'pdf',
                'native_name': 'Asia Cement Corporation',
                'aliases': {'acc','asia cement corporation','asia cement corp'}},
    '1216.TW': {'short': '統一', 'legal': '統一企業股份有限公司', 'ubn': '73251209',
                'master_english': 'UNI-PRESIDENT', 'website': 'https://www.uni-president.com.tw', 'format': 'pdf',
                'native_name': 'Uni-President (1216TT)',
                'aliases': {'uni-president','uni-president enterprises corp.','uni-president enterprises corp'}},
    '3531.TWO': {'short': '先益', 'legal': '先益電子工業股份有限公司', 'ubn': '52543363',
                'master_english': 'Shian Yih', 'website': 'www.shianyih.com.tw', 'format': 'pptx',
                'native_name': 'Shian Yih Electronic Industry Co., Ltd.',
                'aliases': {'shian yih', 'shian yih electronic industry co., ltd.'}},
    '1104.TW': {'short': '環泥', 'legal': '環球水泥股份有限公司', 'ubn': '07568009',
                'master_english': 'UCC', 'website': 'www.ucctw.com', 'format': 'pdf',
                'native_name': 'Universal Cement Corporation',
                'aliases': {'ucc', 'universal cement corporation', 'universal cement corp'}},
    '2845.TW': {'short': '遠東銀', 'legal': '遠東國際商業銀行股份有限公司', 'ubn': '86517096',
                'master_english': 'FEIB', 'website': 'http://www.feib.com.tw', 'format': 'pdf',
                'aliases': {'feib', 'far eastern international bank ltd.', 'far eastern international bank'}},
    '2330.TW': {'short': '台積電', 'legal': '台灣積體電路製造股份有限公司', 'ubn': '22099131',
                'master_english': 'TSMC', 'website': 'https://www.tsmc.com', 'format': 'pdf',
                'native_name': 'TSMC', 'aliases': {'tsmc', 'taiwan semiconductor manufacturing company limited', 'taiwan semiconductor manufactur'}},
    '2838.TW': {'short': '聯邦銀', 'legal': '聯邦商業銀行股份有限公司', 'ubn': '86380802',
                'master_english': 'UBOT', 'website': 'www.ubot.com.tw', 'format': 'pdf',
                'native_name': 'Union Bank of Taiwan',
                'aliases': {'ubot', 'union bank of taiwan', 'union bank of taiwan co., ltd.'},
                # Preserve the exact private-use glyphs; do not infer or rewrite their meaning.
                'allowed_private_use_symbols': {'\uf06e', '\uf070', '\uf0d8'}},
    '3703.TW': {'short': '欣陸', 'legal': '欣陸投資控股股份有限公司', 'ubn': '28993629',
                'master_english': 'CHC', 'website': 'http://www.continental-holdings.com', 'format': 'pdf',
                'native_name': 'Continental Holdings Corporation',
                'aliases': {'chc', 'continental holdings corporation', 'continental holdings corp.', 'continental hldgs corp'},
                # This private-use character renders as a bullet in the source PDF.
                # Keep it intact and retain the partial-coverage warning in reports.
                'allowed_private_use_symbols': {'\uf06c'}},
    '2023.TW': {'short': '燁輝', 'legal': '燁輝企業股份有限公司', 'ubn': '75947936',
                'master_english': 'YP', 'website': 'http://www.yiehphui.com.tw', 'format': 'pdf',
                'native_name': 'Yieh Phui',
                'aliases': {'yp', 'yieh phui', 'yieh phui enterprise co., ltd.', 'yieh phui enterprise co'}},
    '1229.TW': {'short': '聯華', 'legal': '聯華實業控股股份有限公司', 'ubn': '11996904',
                'master_english': 'LHIHC', 'website': 'https://www.lhicholdings.com/', 'format': 'pptx',
                'native_name': 'Lien Hwa Industrial Holdings Corporation',
                'aliases': {'lhihc', 'lien hwa industrial holdings corporation', 'lien hwa industrial holdings co'}},
}
NOTE = ('公開資訊觀測站已發布的公司法說準備簡報，不是逐字稿、會議實際發生證明或年度查核財報。'
        '場次日期、檔名日期、內容季度與首次發布時間分開；圖像、圖表、閱讀順序及空文字頁未完整驗證。'
        'PPTX隱藏投影片不供分析，外部關係與內嵌物不讀取；圖片中的聲明與期間亦可能未抽出。'
        '母公司、子公司、單季及累計數不得混用，展望與預估不是已實現事實，不覆寫經核定的財報。')


def supports(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in PROFILES


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker not in PROFILES or not isinstance(data,dict) or data.get('ticker') != ticker
            or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):
        return False
    p = PROFILES[ticker];identity = data.get('company_identity', {})
    if identity is None:identity = {}
    if not isinstance(identity,dict):return False
    for key, expected in [('ticker',ticker),('stock_id',ticker.split('.')[0]),('official_name',p['short']),
                          ('legal_name',p['legal']),('official_ubn',p['ubn']),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected) or data.get(key) not in (None,'',expected):return False
    names = p['aliases'] | {p['short'],p['legal']}
    aliases = names | {ticker.casefold(),ticker.split('.')[0]}
    def accepted(value, allowed):
        return isinstance(value,str) and all(part.strip().casefold() in allowed for part in value.split(' / '))
    for key in ('company_name','raw_company_name'):
        if data.get(key) is not None and not accepted(data[key],names):return False
    for key in ('display_name','company_name'):
        if identity.get(key) not in (None,'') and not accepted(identity[key],names):return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        values = identity.get(key,[])
        if not isinstance(values,(list,tuple)) or any(not isinstance(s,str) for s in values):return False
        if key != 'forbidden_aliases' and any(not accepted(s, aliases if key == 'allowed_aliases' else names) for s in values):return False
    forbidden = {s.strip().casefold() for item in identity.get('forbidden_aliases',[]) for s in item.split(' / ')}
    return not (forbidden & aliases)


def parse_master(raw, ticker, epoch, source_url=MASTER_URL):
    if ticker not in PROFILES or not isinstance(raw,bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('master identity unqualified')
    if ticker.endswith('.TWO'):
        if source_url != OTC_MASTER:raise ValueError('OTC master URL mismatch')
        from .mops_otc_master import parse_rows
        rows = parse_rows(raw)
    elif source_url == OTC_MASTER:
        raise ValueError('listed issuer cannot use OTC master')
    elif source_url == JSON_URL:
        from .official_issuer_master_json import parse_rows
        rows = parse_rows(raw,epoch)
    elif source_url == MASTER_URL:
        # Keep the established CSV projection for historical receipt replay.
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig','strict')),strict=True)
        rows = list(reader)
        if (not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not 500 <= len(rows) <= 2000
                or any(None in r or any(v is None for v in r.values()) for r in rows)):
            raise ValueError('complete master shape invalid')
    else:
        raise ValueError('master URL unqualified')
    matches = [r for r in rows if r.get('公司代號') == ticker.split('.')[0]]
    if len(matches) != 1:raise ValueError('issuer not unique')
    r = matches[0];p = PROFILES[ticker]
    expected = {'公司名稱':p['legal'],'公司簡稱':p['short'],'營利事業統一編號':p['ubn'],'網址':p['website']}
    if any(r.get(k) != v for k,v in expected.items()) or r.get('英文簡稱','').replace('\\u3000','\u3000').strip() != p['master_english']:
        raise ValueError('master issuer mismatch')
    s = r.get('出表日期','')
    if not re.fullmatch(r'\d{7}',s):raise ValueError('master date missing')
    day = date(int(s[:3])+1911,int(s[3:5]),int(s[5:]));today = datetime.fromtimestamp(time.time(),ZoneInfo('Asia/Taipei')).date()
    if not 0 <= (today-day).days <= 14 or day > datetime.fromtimestamp(epoch,ZoneInfo('Asia/Taipei')).date():
        raise ValueError('master date stale')
    return {'ticker':ticker,'short_name':p['short'],'legal_name':p['legal'],'official_ubn':p['ubn'],'as_of':day.isoformat()}


def native_material(raw, selected, deadline):
    _check(deadline)
    p = PROFILES[selected['ticker']]
    if selected['format'] != p['format']:
        raise ValueError('new document format needs qualification')
    timeout = min(10.,deadline-time.monotonic())
    native = (extract_pdf_pages if selected['format'] == 'pdf' else extract_pptx_pages)(raw,timeout_seconds=timeout)
    _check(deadline)
    if selected['ticker'] == '2845.TW':
        from .feib_presentation_qualification import validate_native
        period = validate_native(raw, native, selected)
        _check(deadline)
        return native, period
    if not native['pages']:
        raise ValueError('native text empty')
    if (native['coverage_status'] not in {'complete','partial'}
            or selected['format']=='pdf' and native['coverage_status']=='partial'
            and (native['empty_pages'] or not native['garbled_pages'])):
        raise ValueError('native text coverage invalid')
    if native['garbled_pages']:
        allowed_symbols = p.get('allowed_private_use_symbols')
        if not isinstance(allowed_symbols, set):
            raise ValueError('native text garbled')
        expected_garbled = []
        for page in native['pages']:
            text = page['text']
            private_use = {char for char in text if 0xE000 <= ord(char) <= 0xF8FF}
            if (private_use - allowed_symbols or '\ufffd' in text
                    or re.search(r'\(cid:\d+\)', text)
                    or any(unicodedata.category(char) == 'Cc' and char not in '\n\r\t\f' for char in text)):
                raise ValueError('native text garbled')
            if private_use:
                expected_garbled.append(page['page_number'])
        if (native['empty_pages'] or native['garbled_pages'] != expected_garbled
                or native['coverage_status'] != 'partial'):
            raise ValueError('native text coverage invalid')
    cover = re.sub(r'\s+',' ',native['pages'][0]['text']).strip()
    all_text = '\n'.join(page['text'] for page in native['pages'])
    issuer_text = all_text if selected['ticker'] in {'2023.TW','1216.TW','2353.TW','2338.TW','2441.TW'} else cover
    if p['native_name'].casefold() not in issuer_text.casefold():
        raise ValueError('native issuer mismatch')
    if selected['ticker'] in {'6669.TW','2606.TW'}:
        from .mops_datacenter_shipping import qualify
        period=qualify(native,selected)
        _check(deadline)
        return native,period
    period = None
    if selected['ticker'] == '2441.TW':
        matches=re.findall(r'\bFirst Half of Year (20\d{2})\b',cover)
        dates=re.findall(r'\b([A-Z][a-z]{2}\.\d{1,2}, 20\d{2})\b',cover)
        text=re.sub(r'\s+',' ',all_text)
        if len(matches)!=1 or len(dates)!=1:raise ValueError('native half-year cover ambiguous')
        year=int(matches[0]);day=datetime.strptime(dates[0],'%b.%d, %Y').date();yy=f'{year%100:02}'
        if (native['coverage_status']!='complete' or day!=date.fromisoformat(selected['material_file_date'])
                or day!=date.fromisoformat(selected['event_date']) or day.year!=year or date(year,6,30)>day
                or 'www.greatek.com.tw' not in text or not re.search(r'Greatek Electronics Inc\s*\.',text)
                or set(re.findall(r'\b1H(\d{2}) Financial Results\b',text))!={yy}
                or f'Comparison of 1H{yy} and 2H{(year-1)%100:02} Consolidated' not in text
                or f'The financial statement of 1H{yy} was un-audited.' not in text):
            raise ValueError('native half-year period or issuer binding mismatch')
        return native,f'{year}H1'
    if selected['ticker'] == '1312.TW':
        dates=re.findall(r'(?<!\d)(\d{3})\.(\d{2})\.(\d{2})(?!\d)',re.sub(r'\s+','',cover))
        if len(dates)!=1:raise ValueError('native cover date ambiguous')
        roc,month,day=map(int,dates[0]);cover_day=date(roc+1911,month,day)
        if (cover_day!=date.fromisoformat(selected['material_file_date'])
                or cover_day!=date.fromisoformat(selected['event_date'])):
            raise ValueError('native cover date mismatch')
        text=re.sub(r'\s+',' ',all_text)
        matches=re.findall(r'Consolidated Statements of Income \(NT\$ M\) Item H1(\d{2}) H1(\d{2}) Diff\.',text)
        if len(matches)!=1:raise ValueError('native half-year financial period ambiguous')
        year,comparison=(2000+int(v)for v in matches[0])
        if (native['coverage_status']!='complete' or comparison!=year-1
                or year!=cover_day.year or date(year,6,30)>cover_day
                or f'{year}H1' not in text or f'6M{year%100:02}' not in text
                or 'The forward-looking statements contained in this presentation' not in text):
            raise ValueError('native half-year financial scope mismatch')
        return native,f'{year}H1'
    if selected['ticker'] == '2313.TW':
        # The cover dates the prepared material; the operating figures contain
        # both H1 cumulative and Q2 comparisons. Never use the forum's Q3 label.
        months = re.findall(r'\b(20\d{2}) 年 (\d{1,2}) 月\b',cover)
        material_day = date.fromisoformat(selected['material_file_date'])
        if ('2313.TW' not in cover or len(months)!=1
                or tuple(map(int,months[0]))!=(material_day.year,material_day.month)):
            raise ValueError('native issuer or material month mismatch')
        if (native['coverage_status']!='complete'
                or 'not been reviewed by independent accountants' not in re.sub(r'\s+',' ',all_text)
                or 'tw2313@compeq.com.tw' not in all_text):
            raise ValueError('native disclaimer or official contact absent')
        matches = re.findall(r'\bCompeq Revenue and Gross Margin from (20\d{2}) to (20\d{2})H1\b',all_text)
        if len(matches)!=1:raise ValueError('native half-year period ambiguous')
        start,year=map(int,matches[0])
        if start>year or year!=material_day.year or date(year,6,30)>material_day:
            raise ValueError('native half-year period mismatch')
        return native,f'{year}H1'
    if selected['ticker'] in {'1102.TW','1216.TW'}:
        if native['coverage_status'] != 'complete':raise ValueError('native PDF incomplete')
        if selected['ticker'] == '1102.TW':
            matches = re.findall(r'\bAsia Cement (20\d{2})H1 Results\b',cover)
            code = re.findall(r'\(Stock code: (\d{4}) TT\)',cover)
            months = re.findall(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (20\d{2})\b',cover)
            if not code or set(code)!={'1102'} or len(months)!=1:raise ValueError('native issuer or event month ambiguous')
            month,year=months[0]
            event=date.fromisoformat(selected['event_date'])
            if event.year!=int(year) or event.month!=datetime.strptime(month,'%b').month:raise ValueError('native event month mismatch')
        else:
            matches = re.findall(r'\b(20\d{2})H1 RESULTS\b',cover)
            code = re.findall(r'TWSE stock code:(\d{4})\b',cover)
            dates = re.findall(r'\b(\d{1,2} [A-Za-z]+, 20\d{2})\b',cover)
            if code!=['1216'] or len(dates)!=1:raise ValueError('native issuer or event date ambiguous')
            if datetime.strptime(dates[0],'%d %B, %Y').date()!=date.fromisoformat(selected['event_date']):
                raise ValueError('native event date mismatch')
        if len(matches)!=1:raise ValueError('native half-year period ambiguous')
        year=int(matches[0]);period=f'{year}H1'
        if date(year,6,30)>date.fromisoformat(selected['material_file_date']):raise ValueError('content period after original date')
        return native,period
    if selected['format'] == 'pdf':
        if native['coverage_status'] != 'complete' and not p.get('allowed_private_use_symbols'):
            raise ValueError('native PDF incomplete')
        if selected['ticker'] == '6282.TW':
            text=re.sub(r'\s+',' ',all_text)
            months=re.findall(r'\b([A-Z][a-z]+) (20\d{2})\b',cover)
            matches=re.findall(r'\b([1-4])Q(\d{2}) Results Overview\b',text)
            if len(months)!=1 or len(matches)!=1:raise ValueError('native material month or quarter ambiguous')
            month,cover_year=months[0];quarter,year=matches[0];q=int(quarter);year=2000+int(year)
            material_day=date.fromisoformat(selected['material_file_date'])
            if ('6282.TW' not in cover or 'www.acbel.com' not in cover
                    or (int(cover_year),datetime.strptime(month,'%B').month)!=(material_day.year,material_day.month)
                    or year!=int(cover_year) or f'{year} 01-06 Results Overview' not in text
                    or 'Acbel confidential information' not in text or 'Safe Harbor Notice' not in text):
                raise ValueError('native financial scope or issuer binding mismatch')
            period=f'{year}Q{q}'
        elif selected['ticker'] == '9945.TW':
            text=re.sub(r'\s+',' ',all_text)
            matches=re.findall(r'\bRUENTEX DEVELOPMENT (20\d{2})Q([1-4]) Financial Report\b',text)
            parent=re.findall(r'\bItem(?: 20\d{2}){4,8} (20\d{2})Q([1-4])\b',text)
            if (len(matches)!=1 or parent!=matches or '(TICKER: 9945TW)' not in cover
                    or 'This brief shall not be acquired or used by any third party without our permission.' not in text):
                raise ValueError('native parent financial scope or issuer binding mismatch')
            year,quarter=matches[0];q=int(quarter);period=f'{year}Q{q}'
            if int(year)!=date.fromisoformat(selected['material_file_date']).year:raise ValueError('native financial year mismatch')
        elif selected['ticker'] == '2338.TW':
            text=re.sub(r'\s+',' ',all_text)
            dates=re.findall(r'\b([A-Z][a-z]{2}\.\d{1,2}, 20\d{2})\b',cover)
            if len(dates)!=1:raise ValueError('native cover date ambiguous')
            cover_day=datetime.strptime(dates[0],'%b.%d, %Y').date()
            if (cover_day!=date.fromisoformat(selected['material_file_date'])
                    or cover_day!=date.fromisoformat(selected['event_date'])
                    or 'Without the permission of the company' not in text
                    or 'Proprietary' not in cover):
                raise ValueError('native event date or ownership notice mismatch')
            matches=re.findall(r'QoQ YoYNT\$ M ([1-4])Q (\d{2}) ([1-4])Q (\d{2}) ([1-4])Q (\d{2})',text)
            if len(matches)!=1:raise ValueError('native quarterly financial period ambiguous')
            q,year,pq,py,yq,yy=map(int,matches[0]);year+=2000;py+=2000;yy+=2000
            previous_q,previous_year=(q-1,year) if q>1 else (4,year-1)
            if (year!=cover_day.year or (pq,py)!=(previous_q,previous_year)
                    or (yq,yy)!=(q,year-1)
                    or f'{year} {year-1} 1/1-{q*3}/{31 if q in (1,4) else 30} 1/1-{q*3}/{31 if q in (1,4) else 30}' not in text):
                raise ValueError('native quarterly and year-to-date scope mismatch')
            period=f'{year}Q{q}'
        elif selected['ticker'] == '2354.TW':
            text = re.sub(r'\s+',' ',all_text)
            meetings = re.findall(r'\b(20\d{2}) Q([1-4]) Investor Conference\b',cover)
            matches = re.findall(r"\bThe company's Earnings per share of (20\d{2})Q([1-4]) was NT\$",text)
            if (len(meetings)!=1 or len(matches)!=1 or '2354.TW' not in all_text
                    or 'www.foxconntech.com.tw' not in all_text.lower()
                    or 'unaudited and unreviewed information' not in text):
                raise ValueError('native financial period or issuer binding absent')
            year,quarter=matches[0];q=int(quarter);period=f'{year}Q{q}'
            meeting_year,meeting_quarter=map(int,meetings[0])
            material_day=date.fromisoformat(selected['material_file_date'])
            if (int(year)!=meeting_year or meeting_year!=material_day.year
                    or q>meeting_quarter or meeting_quarter!=(material_day.month-1)//3+1):
                raise ValueError('native meeting and financial periods inconsistent')
        elif selected['ticker'] == '6269.TW':
            matches = re.findall(r'\b([1-4])Q (20\d{2}) Earnings Conference\b',cover)
            dates = re.findall(r'\b([A-Z][a-z]+ \d{1,2}, 20\d{2})\b',cover)
            if (len(matches)!=1 or len(dates)!=1 or 'ir@flexium.com.tw' not in all_text
                    or 'Consolidated Income Statement (Quarterly)' not in all_text
                    or 'Consolidated Income Statement (YTD)' not in all_text):
                raise ValueError('native financial scope or issuer binding absent')
            quarter,year=matches[0];q=int(quarter);period=f'{year}Q{q}'
            if (datetime.strptime(dates[0],'%B %d, %Y').date()!=date.fromisoformat(selected['material_file_date'])
                    or f'{year}年第'+('一','二','三','四')[q-1]+'季法人說明會' not in cover):
                raise ValueError('native cover period or material date mismatch')
        elif selected['ticker'] == '2353.TW':
            if (not re.search(r'\bissued by Acer or other entities\b',all_text)
                    or 'https://www.acer.com/corporate/en/investor-relations' not in all_text):
                raise ValueError('native issuer disclaimer or official contact absent')
            matches = re.findall(r'\b(20\d{2}) (First|Second|Third|Fourth) Quarter Earnings\b',cover)
            if len(matches)!=1:raise ValueError('native quarterly period ambiguous')
            year,quarter=matches[0];q=('First','Second','Third','Fourth').index(quarter)+1
            period=f'{year}Q{q}'
        elif selected['ticker'] == '2382.TW':
            if '(2382.TW/2382.TT)' not in cover:raise ValueError('native issuer stock code mismatch')
            matches=re.findall(r'\bFY(20\d{2}) Q([1-4]) Financial Results\b',cover)
            if len(matches)!=1:raise ValueError('native quarterly period ambiguous')
            year,quarter=matches[0];q=int(quarter);period=f'{year}Q{q}'
        elif selected['ticker'] == '1301.TW':
            matches = re.findall(r'\b(20\d{2}) Q([1-4]) Operation Performance Highlights\b',cover)
            if len(matches)!=1:raise ValueError('native quarterly period ambiguous')
            year,quarter=matches[0];q=int(quarter);period=f'{year}Q{q}'
            end_name={1:'March 31',2:'June 30',3:'September 30',4:'December 31'}[q]
            if cover.count(f'{end_name}, {year}')!=1:raise ValueError('native cover quarter-end mismatch')
        elif selected['ticker'] == '2838.TW':
            matches = re.findall(r'\bFinancial Results of ([1-4])Q(\d{2}|20\d{2})\b',cover,re.I)
            if len(matches) != 1:raise ValueError('native quarterly period ambiguous')
            quarter,year = matches[0]
            year = int(year) + 2000 if len(year) == 2 else int(year)
            period = f'{year}Q{int(quarter)}'
            q = int(quarter)
        elif selected['ticker'] == '1104.TW':
            matches = re.findall(r'\bInvestor Conference Q([1-4]) (20\d{2})\b',cover)
            if len(matches) != 1:raise ValueError('native quarterly period ambiguous')
            quarter,year = matches[0];q = int(quarter)
            period = f'{year}Q{q}'
        elif selected['ticker'] == '2023.TW':
            matches = re.findall(r'\bTo\s+(20\d{2})\s+Q([1-4]),\s+the consolidated revenue is\b',all_text,re.I)
            if len(matches) != 1:raise ValueError('native quarterly period ambiguous')
            year,quarter = matches[0];q = int(quarter)
            period = f'{year}Q{q}'
        else:
            matches = re.findall(r'\b(20\d{2}) (First|Second|Third|Fourth) Quarter Earnings Conference\b',cover)
            if len(matches) != 1:raise ValueError('native quarterly period ambiguous')
            year,quarter = matches[0];q = ('First','Second','Third','Fourth').index(quarter)+1
            period = f'{year}Q{q}'
        end = date(int(period[:4]),q*3,31 if q in (1,4) else 30)
        if end > date.fromisoformat(selected['material_file_date']):raise ValueError('content period after original date')
    if selected['ticker'] == '3531.TWO':
        matches = re.findall(r'\b(20\d{2}) Q([1-4]) Investor Conference\b',cover)
        if len(matches) != 1:raise ValueError('native quarterly period ambiguous')
        year,quarter = matches[0];q=int(quarter);period=f'{year}Q{q}'
        end=date(int(year),q*3,31 if q in (1,4) else 30)
        if end > date.fromisoformat(selected['material_file_date']):raise ValueError('content period after original date')
    # The legacy 1229 PPTX cover's quarter/date is an image. Do not infer it from a file
    # date or a historical fixture, even though this observed image was read.
    return native, period


def _context(selected, native, period, proof):
    stamp = proof['material']['retrieved_at'];ticker = selected['ticker']
    wire = proof['material_request'] if proof.get('policy') == STATIC_POLICY else selected
    doc = {'document_id':ticker+':'+selected['material_file_date']+':'+native['content_sha256'][:16],
           'ticker':ticker,'source':PROVIDER,'source_type':'regulated_issuer_presentation','document_kind':'presentation',
           'projection_policy':POLICY,'title':selected['company_name']+' 已發布法說簡報','url':wire['url'],
           'filename':selected['filename'],'file_format':selected['format'],'language':selected['language'],
           'event_date':selected['event_date'],'event_end_date':selected['event_end_date'],
           'event_time':selected['event_time'],'event_timezone':'Asia/Taipei',
           'event_status':'published_past_event_not_independently_occurrence_verified',
           'event_date_basis':'exact_published_MOPS_row','material_file_date':selected['material_file_date'],
           'content_period':period,'published_at':None,'retrieved_at_epoch':stamp,
           'content_sha256':native['content_sha256'],'binary_complete':True,'page_count':native['page_count'],
           'pages':native['pages'],'missing_text_pages':native['empty_pages'],'garbled_pages':native['garbled_pages'],
           'text_extraction_complete':native['coverage_status']=='complete','native_text_coverage':native['coverage_status'],
           'coverage_status':'partial','full_content_coverage_verified':False,'financial_statement_complete':False,
           'parser_version':native['parser_version'],
           'hidden_pages':native.get('hidden_pages',[]),'total_slide_count':native.get('total_slide_count',native['page_count']),
           'known_native_text_omissions':[{'page_number':n,'issue':'empty_native_text_not_empty_source_page'} for n in native['empty_pages']],
           'unresolved_native_glyphs':[
               {'page_number':page['page_number'],'codepoints':sorted({f'U+{ord(char):04X}' for char in page['text'] if 0xE000<=ord(char)<=0xF8FF})}
               for page in native['pages'] if any(0xE000<=ord(char)<=0xF8FF for char in page['text'])],
           'visual_semantics_caution':'All image, chart, table geometry and slide-layout relations remain unverified, including nonempty pages.',
           'financial_scope_caution':'Parent and subsidiaries, currency/units, single-quarter and year-to-date figures must stay distinct. This is not a verified annual financial statement.',
           'forward_looking_caution':'Prepared forecasts, targets and guidance are issuer statements, not realized results; image-only disclaimers may be missing.',
           'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False}
    if ticker == '2313.TW':
        doc['period_scope_caution'] = 'H1為半年累計；營收組合頁另含Q2單季及歷季比較，不能混用。封面資料月份、檔名日期與MOPS場次分開；聲明指出歷史資料可能未經獨立會計師覆核。產業預測與公司展望不是已實現成果，外部來源及圖表關係未獨立驗證。'
    if ticker == '1312.TW':
        doc['period_scope_caution'] = 'H1／H1兩位年號及6M為上半年累計，不是Q2單季；FY為全年比較。Q3(E)等帶E項目屬預估，不能當已實現結果；員工人數頁的季度也不是財務表期間。圖表座標與圖例未做視覺核驗，不能由零散軸值推填數字；展望及投資持股均屬公司自行陳述，未獨立證實，Q&A章節標題不等於問答紀錄。'
    if ticker == '2338.TW':
        doc['period_scope_caution'] = 'QoQ表為單季，YoY表的年初至季末為累計，兩者EPS不能混用。集團與子公司範圍、預測及圖表幾何需分開；頁尾模板日期與封面日期不同，不推定首次發布。原件Proprietary及未經允許不得複製／傳播／商業使用聲明保持，未驗證商業重用授權。Q&A章節標題不等於問答紀錄。'
    if ticker == '6282.TW':
        doc['period_scope_caution'] = 'Q季為單季，01-06為H1累計，合併範圍／幣別／單位分開；Business Performance頁期間欄位未核對，角色排除此頁及營收圖表，不由圖形推填數字。公司聲明財報依IFRS經核閱，簡報非完整經查核年度財報；Confidential與禁止未授權揭露聲明保留，商業重用授權未驗證。'
    if ticker == '6669.TW':
        doc['period_scope_caution'] = 'Q2為單季，Q1-Q2為上半年累計，EPS及股數口徑未與目前股本／行情股數對齊，不得直接重算價格、目標價或TTM，也不年化累計數。封面資料日期、檔名日期與場次分開，非完整查核財報。Copyright／Confidential及未經書面同意禁止複製、散布或商業使用之聲明保留，重用授權未驗證。未提供已核驗的業務策略／展望正文，角色5／12只保留封面與聲明，不據此推論策略。'
    if ticker == '2606.TW':
        doc['period_scope_caution'] = '封面Q3是會議標籤，財務表為Q2單季，不是Q3財務結果；不同財務、貿易量及運價期間分開。船隊頁只可引用明列Vessel Type／Owned／Managed／JV表格，圖形軸值與新造船不得推算為已實現運力；圖表幾何未核驗。市場、地緣政治、氣候及政策屬公司引用或情境假設，未獨立證實；基準、上行及下行情境須同時保留，不能當成已發生事件。聲明與未經獨立驗證限制保留；Q&A章節不是逐字稿。'
    if ticker == '9945.TW':
        doc['period_scope_caution'] = '角色財務頁只用RUENTEX DEVELOPMENT Consolidated I/S的母公司合併資料，歷年全年與當期Q季分開，不把投資公司／子公司EPS與母公司EPS混用。工程合約與預估總銷不是已認列營收，未來完工／展望均是公司估計；持股與市值依各頁日期分開。Permission限制保留，商業重用授權未驗證；圖表幾何未核驗。'
    if ticker == '2441.TW':
        doc['period_scope_caution'] = '1H為上半年累計、2H為下半年，合併範圍與單位分開；比較前半年的頁面仍有YoY欄名，須依原1H／2H欄位保留，不能當去年同半年度。圖表頁零散EPS／軸值未核對，角色只用完整財務表與營運／展望正文；未查核聲明保留，2H展望不是已實現成果。'
    if ticker == '2354.TW':
        cover=re.sub(r'\s+',' ',native['pages'][0]['text'])
        meeting_q=re.findall(r'\b20\d{2} Q([1-4]) Investor Conference\b',cover)[0]
        doc['period_scope_caution'] = f'封面Q{meeting_q}為會議標籤，不是Q{meeting_q}財務結果。EPS頁{period[-2:]}是單季，其他頁的累計（如H1）須按各自標題分開；未查核及未覆核聲明保持，各頁期間與預測不能混用。只有標題的財務表、EPS及認證頁沒有可讀正文，不能推填圖中數字。Q&A僅章節標題，不是問答紀錄。'
        titles={'Operations, Manufacturing & Services','Income Statement','Balance Sheet',
                'Cash Flow Statement','Key Ratios','EPS','Certification'}
        doc['known_native_text_omissions'].extend(
            {'page_number':page['page_number'],'issue':'title_only_native_text_visual_content_unverified'}
            for page in native['pages'] if re.sub(r'\s+',' ',page['text']).strip() in titles)
    if ticker == '6269.TW':
        quarter=period[-2:]
        cumulative='H1累計' if quarter=='Q2' else f'截至{quarter}的年初至今累計'
        labels=[tuple(map(int,m)) for page in native['pages']
                for m in re.findall(r'Page (\d+) of\s+(\d+)',page['text'])
                if int(m[1])!=native['page_count']]
        footer=('頁尾有Page %s of %s矛盾，以PDF實際頁數為準。' % max(labels)
                if labels else '頁尾印刷頁碼不取代PDF實際頁數。')
        doc['period_scope_caution'] = f'封面{quarter}為單季；YTD表是{cumulative}，不可混用。各頁Rafael included或not included須按原文區分，不推定範圍一致。{footer}圖表幾何及閱讀順序未核驗，Q&A只有議程。'
    if ticker in {'2353.TW','2382.TW'}:
        doc['period_scope_caution'] = 'Q季為單季，H1為半年累計，不能混用；各頁的比較期間、合併範圍、幣別與單位須按原標題保留。封面資料月份、檔名日期及MOPS場次日期各自保留，不推定首次發布日。'
    if ticker == '1301.TW':
        doc['period_scope_caution'] = 'Q季為單季；封面期末日、MOPS場次日期與檔名日期分開。其他頁去年同季及前季比較須保留原期間，不能把稅前利益或投資收益當成全部營業利益；圖表幾何與顏色關係未核驗。'
    if ticker in {'1102.TW','1216.TW'}:
        doc['period_scope_caution'] = '封面H1為上半年累計，不是Q2單季。其他頁各自的期間、合併範圍、幣別與單位須分開；簡報不是完整年度財報。'
    if ticker == '3531.TWO':
        doc['embedded_object_count'] = native['embedded_object_count']
        doc['external_relationship_count'] = native['external_relationship_count']
    if ticker in {'1104.TW','1301.TW'}:
        # Preserve font/cmap proof for any deterministic source-reader mapping.
        doc['symbol_mapping_evidence'] = deepcopy(native.get('symbol_mapping_evidence',[]))
    if ticker == '2845.TW':
        from .feib_presentation_qualification import metadata
        doc.update(metadata())
    elif ticker == '2838.TW':
        doc['content_periods'] = ['封面標示2026Q2；第3頁含2026H1與2Q26數字，各頁原始期間和未查核聲明需分別保留。']
        doc['period_scope_caution'] = '封面標示Financial Results of 2Q26；第3頁另有1H26摘要。不要把半年數字當成單季，也不要把簡報視為查核財報。'
    elif ticker == '2023.TW':
        doc['period_scope_caution'] = (
            '原文 To 年度／季度的合併營收為截至該季度的表述；各頁原始期間須分別保留，不能據此推導單季財務數字，圖表亦未做視覺核驗。'
            if proof.get('policy')==STATIC_POLICY else
            '第11頁標示To 2026 Q2的合併營收；這是截至季度的表述，不能據此推導單季財務數字，圖表亦未做視覺核驗。')
    if proof.get('policy') == PREVIOUS_POLICY:
        doc['period_scope_caution'] += ' 當年官方索引明確無結果，本件為前一年已發布的歷史材料，不代表當期營運或最新財報；僅限370日內場次。'
    from mops_qualified_role_pages import projection
    doc.update(projection(ticker,native['pages']))
    return {'ticker':ticker,'date':selected['event_date'],'period':period or '',
            'source':PROVIDER,'source_url':proof['index']['source_url'],'title':doc['title'],
            'summary':selected['event_summary'],'transcript_excerpt':'','transcript_available':False,
            'materials':[{'url':wire['url'],'filename':selected['filename'],'request_method':wire['method'],
                          'language':selected['language'],'kind':'presentation'}],
            'documents':[doc],'coverage_status':'partial',
            'coverage_notes':[NOTE] + ([
                '部分Wingdings項目符號保持原始私用區碼；受影響頁面保留在garbled_pages中，不映射或猜測其語意。'
            ] if doc['unresolved_native_glyphs'] else []),
            'fetched_at_epoch':stamp,'mops_material_receipt':proof}


def is_marked(value):
    if not isinstance(value,dict):return False
    documents = value.get('documents')
    return ('mops_material_receipt' in value or value.get('source') == PROVIDER
        or isinstance(documents,list) and any(isinstance(d,dict) and
            (d.get('source') == PROVIDER or d.get('projection_policy') == POLICY) for d in documents))


def _originals_current_at_handoff(proof, max_age=RAW_TTL):
    """Pure final check: every required verified receipt shares one clock."""
    observed = time.time()
    if type(max_age) not in (int,float) or not math.isfinite(max_age) or max_age <= 0:
        return False
    keys=('master','index','material') + (('absence_current_index',) if proof.get('policy')==PREVIOUS_POLICY else ())
    for key in keys:
        stamp = proof[key]['retrieved_at']
        expiry = (stamp+RAW_TTL if key=='master' and proof[key]['source_url']==OTC_MASTER
                  else proof[key]['fresh_until_epoch'])
        if (any(type(v) not in (int,float) or not math.isfinite(v) for v in (stamp,expiry))
                or not 0 < stamp <= observed < expiry <= stamp+RAW_TTL
                or not observed-stamp < min(max_age,RAW_TTL)):
            return False
    return True


def _master_bytes(receipt, ticker, max_age=RAW_TTL):
    url=receipt['source_url']
    if ticker.endswith('.TWO'):
        return otc_master_bytes(receipt,url,max_age=max_age)
    if url not in (MASTER_URL,JSON_URL):raise ValueError('listed master URL mismatch')
    return master_bytes(receipt,url,max_age=max_age)


def verify_context(value, ticker, *, deadline=None, max_age=RAW_TTL, diagnostics=None):
    deadline = time.monotonic()+10. if deadline is None else deadline
    stage = 'context'
    def verdict(accepted, reason, at=None):
        if isinstance(diagnostics,dict):
            diagnostics.update(verification_status='verified' if accepted else 'rejected',
                verification_stage='complete' if accepted else (at or stage),
                verification_reason=reason)
        return accepted
    try:
        if not supports(ticker) or not is_marked(value) or value.get('ticker') != ticker:
            return verdict(False,'unsupported_context')
        stage='proof'
        proof = value['mops_material_receipt']
        fields={'policy','ticker','master','index','material','selected','index_request'}
        previous = proof.get('policy') == PREVIOUS_POLICY
        if previous:
            if PROFILES[ticker].get('previous_year_fallback') is not True:return verdict(False,'invalid_proof')
            fields=fields|{'absence_current_index','absence_current_request'}
        elif proof.get('policy') == STATIC_POLICY:
            fields=fields|{'material_request'}
            if ticker!='2023.TW':return verdict(False,'invalid_proof')
        elif proof.get('policy') != POLICY:return verdict(False,'invalid_proof')
        if set(proof)!=fields or proof['ticker']!=ticker:return verdict(False,'invalid_proof')
        stage='master_original'
        master_url = proof['master']['source_url']
        master_raw=_master_bytes(proof['master'],ticker,max_age=min(max_age,RAW_TTL))
        stage='master_identity'
        anchor = parse_master(master_raw,ticker,proof['master']['retrieved_at'],master_url)
        stage='index_request'
        spec = proof['index_request'];year = datetime.fromtimestamp(proof['index']['retrieved_at'],ZoneInfo('Asia/Taipei')).year
        if spec != index_request(ticker,year=year-1 if previous else year):return verdict(False,'request_mismatch')
        if previous:
            absence_spec=proof['absence_current_request']
            absence_year=datetime.fromtimestamp(proof['absence_current_index']['retrieved_at'],ZoneInfo('Asia/Taipei')).year
            if absence_year!=year or absence_spec!=index_request(ticker,year=year):return verdict(False,'request_mismatch')
        stage='index_original'
        if previous and not exact_no_results(original_bytes(proof['absence_current_index'],absence_spec)):
            return verdict(False,'selection_mismatch')
        raw = original_bytes(proof['index'],spec)
        stage='index_selection'
        selected = select_published_material(raw,ticker,as_of_epoch=proof['index']['retrieved_at'],company_name=anchor['short_name'])
        if not selected or selected != proof['selected']:return verdict(False,'selection_mismatch')
        if previous and (not eligible_previous(selected,year,proof['index']['retrieved_at'])
                         or not eligible_previous(selected,year,time.time())):return verdict(False,'selection_mismatch')
        if not previous and PROFILES[ticker].get('previous_year_fallback') and selected['event_date'][:4]!=str(year):
            return verdict(False,'selection_mismatch')
        stage='index_current'
        if selected != select_published_material(raw,ticker,as_of_epoch=time.time(),company_name=anchor['short_name']):
            return verdict(False,'selection_mismatch')
        stage='material_request'
        material_spec=selected
        if proof['policy']==STATIC_POLICY:
            material_spec=static_material_request(selected)
            if material_spec!=proof['material_request']:return verdict(False,'request_mismatch')
        stage='material_original'
        material_raw=original_bytes(proof['material'],material_spec)
        stage='native_material'
        native,period = native_material(material_raw,selected,deadline)
        stage='projection'
        expected = _context(selected,native,period,proof)
        valid = value == expected
        stage='receipt_age'
        for key in ('master','index','material') + (('absence_current_index',) if previous else ()):
            if not 0 <= time.time()-proof[key]['retrieved_at'] < min(max_age,RAW_TTL):return verdict(False,'expired')
        stage='index_handoff'
        original_bytes(proof['index'],spec)
        if previous:original_bytes(proof['absence_current_index'],absence_spec)
        stage='material_handoff'
        original_bytes(proof['material'],material_spec)
        stage='master_handoff'
        _master_bytes(proof['master'],ticker,max_age=min(max_age,RAW_TTL))
        stage='deadline'
        _check(deadline)
        if not valid:return verdict(False,'projection_mismatch',at='projection')
        stage='freshness'
        if not _originals_current_at_handoff(proof,max_age):return verdict(False,'expired')
        return verdict(True,'none')
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,OSError,EOFError,UnicodeError,zlib.error,SourceResponseError,SourcePdfError,SourcePptxError) as exc:
        if isinstance(exc,(SourcePdfError,SourcePptxError)):
            kind=getattr(exc,'reason',None)
            reason=('memory_accounting_unavailable' if kind=='memory_accounting_unavailable' else
                    'parser_timeout' if kind=='timeout' else 'parser_warning' if kind=='parser_warning'
                    else 'document_restricted' if kind in {'encrypted_pdf','encrypted_package'}
                    else 'document_limit' if kind in {'page_limit','character_limit','stream_limit','memory_limit'}
                    else 'document_rejected')
        elif isinstance(exc,SourceResponseError):
            reason='source_timeout' if exc.error_kind=='timeout' else 'source_rejected'
        elif isinstance(exc,(OSError,EOFError,zlib.error)):reason='original_unreadable'
        elif isinstance(exc,(KeyError,TypeError,AttributeError)):reason='invalid_structure'
        else:reason='validation_error'
        return verdict(False,reason)


def fetch_presentation_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports(ticker):return {}
    ticker = ticker.strip().upper()
    deadline = time.monotonic()+25.;details = {'actual_provider':PROVIDER,'mops_material_workflow':True}
    master_url = OTC_MASTER if ticker.endswith('.TWO') else MASTER_URL
    http_class = OtcMasterHttp if ticker.endswith('.TWO') else MasterHttp
    http = http_class(deadline,force_refresh=force_refresh,use_cache=use_cache);components = http.components
    try:
        raw,master = http.get_receipt(master_url);anchor = parse_master(raw,ticker,master['retrieved_at'],master['source_url']);_check(deadline)
        with endpoint_admission(GUARD,timeout_seconds=max(.01,deadline-time.monotonic())) as owns:
            if not owns:raise SourceResponseError('single_flight_busy')
            _check(deadline,owns)
            year = datetime.fromtimestamp(time.time(),ZoneInfo('Asia/Taipei')).year
            spec = index_request(ticker,year=year);detail = {};components.append(detail)
            def select_current(raw,receipt):
                if PROFILES[ticker].get('previous_year_fallback') and exact_no_results(raw):return None
                selected=select_published_material(raw,ticker,as_of_epoch=receipt['retrieved_at'],company_name=anchor['short_name'])
                if (PROFILES[ticker].get('previous_year_fallback') and selected
                        and selected['event_date'][:4]!=str(year)):
                    raise ValueError('current index event year mismatch')
                return selected
            selected,index = get_original(spec,lambda d:download_conference_index(ticker,year=year,deadline=deadline,diagnostics=d),
                deadline=deadline,owns=owns,diagnostic=detail,force_refresh=force_refresh,use_cache=use_cache,
                parser=select_current)
            absence=None;absence_spec=None
            if (selected is None and PROFILES[ticker].get('previous_year_fallback')
                    and exact_no_results(original_bytes(index,spec))):
                absence,absence_spec=index,spec
                spec=index_request(ticker,year=year-1);detail={};components.append(detail)
                selected,index=get_original(spec,lambda d:download_conference_index(ticker,year=year-1,deadline=deadline,diagnostics=d),
                    deadline=deadline,owns=owns,diagnostic=detail,force_refresh=force_refresh,use_cache=use_cache,
                    parser=lambda raw,receipt:select_published_material(raw,ticker,as_of_epoch=receipt['retrieved_at'],company_name=anchor['short_name']))
                if not eligible_previous(selected,year,time.time()):raise SourceResponseError('published_material_unavailable')
            if not selected:raise SourceResponseError('published_material_unavailable')
            material_spec=static_material_request(selected) if ticker=='2023.TW' else selected
            detail = {};components.append(detail)
            (native,period),material = get_original(material_spec,lambda d:download_published_material(material_spec,deadline=deadline,diagnostics=d),
                deadline=deadline,owns=owns,diagnostic=detail,force_refresh=force_refresh,use_cache=use_cache,
                parser=lambda raw,receipt:native_material(raw,selected,deadline))
            proof = {'policy':POLICY,'ticker':ticker,'master':master,'index':index,'material':material,
                     'selected':selected,'index_request':spec}
            if absence is not None:
                proof.update(policy=PREVIOUS_POLICY,absence_current_index=absence,absence_current_request=absence_spec)
            if material_spec is not selected:
                proof.update(policy=STATIC_POLICY,material_request=material_spec)
            value = deepcopy(_context(selected,native,period,proof))
            verification={}
            verified=verify_context(value,ticker,deadline=deadline,diagnostics=verification)
            details.update(verification)
            if not verified:raise SourceResponseError('original_unverified')
            _check(deadline,owns)
        details.update(mops_material_originals_verified=True,coverage_status='native_presentation_text_'+native['coverage_status'],
                       cache_hit=material['cache_hit'],stale=False,fetched_at_epoch=material['retrieved_at'],message=NOTE)
        details.update(component_statuses=deepcopy(components),http_request_sent=any(c.get('http_request_sent') is True for c in components),
                       http_request_count=sum(c.get('http_request_sent') is True for c in components))
        if diagnostics is not None:diagnostics.update(details)
        from mops_body_cache import publish_body_hint
        publish_body_hint(value)
        # The external admission cleanup and diagnostic projection can consume
        # the remaining lifetime. Check at handoff after both have completed.
        _check(deadline)
        _master_bytes(master,ticker,max_age=RAW_TTL)
        original_bytes(index,spec);original_bytes(material,material_spec)
        if absence is not None:original_bytes(absence,absence_spec)
        _check(deadline)
        if not _originals_current_at_handoff(proof):raise SourceResponseError('original_expired')
        return value
    except Exception as original:
        kind = 'timeout' if time.monotonic() >= deadline or getattr(original,'error_kind',None) == 'timeout' else 'parse_error'
        exc = original if isinstance(original,SourceResponseError) and kind != 'timeout' else SourceResponseError(kind)
        details.update(mops_material_originals_verified=False,error_kind=exc.error_kind,status='error',
                       component_statuses=deepcopy(components),http_request_sent=any(c.get('http_request_sent') is True for c in components),
                       http_request_count=sum(c.get('http_request_sent') is True for c in components))
        if isinstance(original,(SourcePdfError,SourcePptxError)):details['document_error_kind']=original.reason
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original
