"""Complete issuer publication catalogues, never financial numeric evidence.

The same full year selector must occur on every response. A five-year window
also retains all intervening annual absences, including newer listed years.
"""
from datetime import datetime
import csv
import io
import math
import re
import time
from urllib.parse import urljoin,urlsplit,parse_qs
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

HOST='https://www.megaholdings.com.tw'
ROOT=HOST+'/tc/investors_1.aspx'
POLICY='mega-published-holding-catalogue:v1'
LIMIT=1024*1024
LEGAL='兆豐金融控股股份有限公司'


def page_url(identifier):
    if not isinstance(identifier,str)or not re.fullmatch('[0-9]{1,8}',identifier):
        raise ValueError('Mega catalogue identifier invalid')
    return ROOT+'?trclassify='+identifier


def parse_page(raw,retrieved_at,*,year=None,options=None):
    if (not isinstance(raw,bytes)or not 0<len(raw)<=LIMIT
            or type(retrieved_at)not in(int,float)or not math.isfinite(retrieved_at)
            or not 0<retrieved_at<=time.time()+300):
        raise ValueError('Mega catalogue original or epoch invalid')
    text=raw.decode('utf-8-sig','strict');lower=text.lower()
    if (len(re.findall(r'<html(?:\s[^<>]*)?>',text,re.I))!=1
            or lower.count('</html>')!=1 or not lower.rstrip().endswith('</html>')
            or len(re.findall(r'<body(?:\s[^<>]*)?>',text,re.I))!=1 or lower.count('</body>')!=1):
        raise ValueError('Mega complete catalogue required')
    soup=BeautifulSoup(text,'html.parser')
    if not soup.title or soup.title.get_text(strip=True)!='兆豐金控'or LEGAL not in soup.get_text():
        raise ValueError('Mega parent issuer catalogue identity invalid')
    selectors=soup.find_all('select',attrs={'name':'ctl00$ContentPlaceHolder1$classifyID'})
    blocks=soup.find_all('div',id='download_box')
    if len(selectors)!=1 or len(blocks)!=1 or '兆豐金控會計師查核(核閱)財務報告'not in blocks[0].get_text():
        raise ValueError('Mega annual report selector ambiguous')
    selector=selectors[0];found={};selected=[]
    asof_year=datetime.fromtimestamp(retrieved_at,ZoneInfo('Asia/Taipei')).year
    for option in selector.find_all('option'):
        label=option.get_text(strip=True);identifier=option.get('value')
        if label=='請選擇年度'and identifier=='':continue
        match=re.fullmatch('([0-9]{2,3})年度',label)
        if not match or not isinstance(identifier,str)or not re.fullmatch('[0-9]{1,8}',identifier):
            raise ValueError('Mega year option invalid')
        fiscal=int(match[1])+1911
        if not 2000<=fiscal<=asof_year or fiscal in found or identifier in found.values():
            raise ValueError('Mega year option identity ambiguous')
        found[fiscal]=identifier
        if option.has_attr('selected'):selected.append(fiscal)
    if not 6<=len(found)<=100 or max(found)<asof_year-1 or len(selected)>1:
        raise ValueError('Mega year catalogue coverage unverified')
    if options is not None and found!=options:raise ValueError('Mega year options changed across originals')
    selected_year=selected[0]if selected else None
    form=selector.find_parent('form')
    if not form or form.get('method','').lower()!='post':raise ValueError('Mega public form missing')
    action=urlsplit(urljoin(ROOT,form.get('action','')))
    if action.scheme!='https'or action.netloc!='www.megaholdings.com.tw'or action.path!='/tc/investors_1.aspx'or action.fragment:
        raise ValueError('Mega form route invalid')
    query=parse_qs(action.query,keep_blank_values=True,strict_parsing=True)
    if query and (set(query)!={'trclassify'}or len(query['trclassify'])!=1
            or query['trclassify'][0]not in found.values()):raise ValueError('Mega selected form identity invalid')
    annual=None
    if year is not None:
        if type(year)is not int or selected_year!=year or year not in found or query!={'trclassify':[found[year]]}:
            raise ValueError('Mega selected year does not match original')
        label='兆豐金控'+str(year-1911)+'年度IFRSs合併財報'
        annuals=[a for a in blocks[0].find_all('a',href=True)
            if re.fullmatch('兆豐金控[0-9]{2,3}年度IFRSs合併財報',a.get_text(strip=True))]
        if any(a.get_text(strip=True)!=label for a in annuals):
            raise ValueError('Mega selected catalogue contains another annual period')
        anchors=[a for a in annuals if a.get_text(strip=True)==label]
        if len(anchors)>1:raise ValueError('Mega annual publication ambiguous')
        if anchors:
            href=anchors[0]['href']
            if not re.fullmatch('/upload/38/[0-9]{14,24}[.]pdf',href):
                raise ValueError('Mega published annual document route invalid')
            if year>=asof_year:raise ValueError('Mega annual period has not closed')
            annual={'title':label,'url':HOST+href,'fiscal_year':year,'report_scope':'consolidated'}
    return {'options':found,'selected_year':selected_year,'annual_document':annual}


def publication_window(root_raw,root_epoch,pages):
    root=parse_page(root_raw,root_epoch);options=root['options']
    if not isinstance(pages,list)or not 5<=len(pages)<=7:raise ValueError('Mega bounded publication window missing')
    parsed={}
    for page in pages:
        if not isinstance(page,dict)or type(page.get('year'))is not int or page['year']in parsed:
            raise ValueError('Mega duplicate or malformed year original')
        year=page['year'];parsed[year]=parse_page(page['raw'],page['retrieved_at'],year=year,options=options)
        if page['retrieved_at']<root_epoch:raise ValueError('Mega year original predates its option discovery')
    if sorted(parsed)!=list(range(min(parsed),max(options)+1)):
        raise ValueError('Mega publication window has missing/newer years')
    annual=sorted(y for y,p in parsed.items()if p['annual_document'])
    if len(annual)!=5 or annual!=list(range(min(annual),max(annual)+1))or min(parsed)!=min(annual):
        raise ValueError('Mega five annual publications incomplete')
    if len({parsed[y]['annual_document']['url']for y in annual})!=5:
        raise ValueError('Mega annual publications do not have distinct documents')
    return {'years':annual,'annual_absence_years':sorted(set(parsed)-set(annual)),
            'documents':[parsed[y]['annual_document']for y in annual],'options':options}


def master_identity(receipt,*,historical=False):
    from . import official_issuer_master as master
    stamp=receipt.get('retrieved_at')if isinstance(receipt,dict)else None
    age=max(86400,time.time()-stamp+1)if historical and type(stamp)in(int,float)and math.isfinite(stamp)else master.RAW_TTL
    raw=master.original_bytes(receipt,max_age=age)
    if receipt['source_url']==master.MASTER_URL:
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig','strict')),strict=True))
    else:
        from .official_issuer_master_json import parse_rows
        rows=parse_rows(raw,stamp)
    rows=[r for r in rows if r.get('公司代號')=='2886']
    if (len(rows)!=1 or rows[0].get('公司名稱')!=LEGAL or rows[0].get('公司簡稱')!='兆豐金'
            or rows[0].get('營利事業統一編號')!='70796754'
            or rows[0].get('網址')not in('www.megaholdings.com.tw','https://www.megaholdings.com.tw','http://www.megaholdings.com.tw')):
        raise ValueError('Mega complete official master identity/site invalid')
    return rows[0]


def replay_catalogue(proof,*,years=None):
    from .mega_catalog_transport import original_bytes
    if (not isinstance(proof,dict)or set(proof)!={'policy','ticker','master','root','catalogues'}
            or proof['policy']!=POLICY or proof['ticker']!='2886.TW'):
        raise ValueError('Mega publication proof invalid')
    master_identity(proof['master'],historical=True)
    root=proof['root'];raw=original_bytes(root,ROOT);options=parse_page(raw,root['retrieved_at'])['options'];pages=[]
    if (not isinstance(proof['catalogues'],list)or not 5<=len(proof['catalogues'])<=7
            or proof['master']['retrieved_at']>root['retrieved_at']):raise ValueError('Mega catalogue discovery order invalid')
    for item in proof['catalogues']:
        if not isinstance(item,dict)or set(item)!={'year','receipt'}or type(item['year'])is not int or item['year']not in options:
            raise ValueError('Mega catalogue year proof invalid')
        receipt=item['receipt'];url=page_url(options[item['year']])
        body=original_bytes(receipt,url,root_sha=root['raw_response_sha256'])
        pages.append({'year':item['year'],'raw':body,'retrieved_at':receipt['retrieved_at']})
    result=publication_window(raw,root['retrieved_at'],pages)
    if years is not None and [str(y)for y in result['years']]!=years:raise ValueError('Mega publication/fact years differ')
    close=datetime(max(result['years'])+1,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    if min(proof['master']['retrieved_at'],root['retrieved_at'],*(p['retrieved_at']for p in pages))<close:
        raise ValueError('Mega publication evidence predates annual close')
    return result


def fetch_catalogue(deadline,*,diagnostics=None):
    from .official_issuer_master_transport import IssuerMasterHttp
    from .official_issuer_master import MASTER_URL,RAW_TTL
    from .mega_catalog_transport import MegaCatalogHttp
    from search_provider_runtime import SourceResponseError
    master_http=IssuerMasterHttp(deadline,force_refresh=False,use_cache=True);http=MegaCatalogHttp(deadline)
    try:
        _,master=master_http.get_receipt(MASTER_URL);master_identity(master)
        raw,root=http.get_receipt(ROOT);options=parse_page(raw,root['retrieved_at'])['options']
        pages=[];annual=0
        for year in sorted(options,reverse=True)[:7]:
            body,receipt=http.get_receipt(page_url(options[year]));parsed=parse_page(body,receipt['retrieved_at'],year=year,options=options)
            pages.append({'year':year,'receipt':receipt});annual+=int(parsed['annual_document']is not None)
            if annual==5:break
        proof={'policy':POLICY,'ticker':'2886.TW','master':master,'root':root,'catalogues':pages}
        replay_catalogue(proof);master_identity(master)
        if (time.monotonic()>=deadline or any(time.time()-r['retrieved_at']>=RAW_TTL
                for r in[root,*[p['receipt']for p in pages]])):raise SourceResponseError('timeout')
        return proof
    finally:
        if diagnostics is not None:diagnostics.extend(master_http.components+http.components)


def verify_live_catalogue(proof):
    """Saved replay is historical; a new acquisition still needs live originals."""
    from .official_issuer_master import RAW_TTL
    replay_catalogue(proof)
    master_identity(proof['master'])
    observed=time.time()
    receipts=[proof['master'],proof['root'],*[p['receipt']for p in proof['catalogues']]]
    if any(not 0<=observed-r['retrieved_at']<RAW_TTL for r in receipts):
        raise ValueError('Mega live publication originals expired at handoff')


def prefer_catalogue(ticker):
    """A subsequent demand may replace only a proven failed publication index."""
    if ticker!='2886.TW':return False
    import sqlite3
    from pathlib import Path
    from hashlib import sha256
    import json
    from provider_sla import TASK_DB_PATH
    from .official_xbrl_financial import INDEX_URL
    from .mops_public_holding import PROVIDER
    path=Path(TASK_DB_PATH)
    if not path.exists():return False
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)as db:
            rows=db.execute('SELECT created_at,status,record_count,details_json FROM provider_sla_events '
                'WHERE source=? AND provider=? ORDER BY id DESC LIMIT 512',('financial_statements',PROVIDER)).fetchall()
        for created,status,count,raw in rows:
            try:d=json.loads(raw or'{}')
            except (ValueError,TypeError):continue
            if not isinstance(d,dict)or d.get('ticker')!=ticker:continue
            if d.get('cache_hit')is True or d.get('http_request_sent')is False:continue
            if type(created)not in(int,float)or not math.isfinite(created)or not 0<=time.time()-created<86400:return False
            parts=d.get('component_statuses')
            if isinstance(parts,dict):
                if not all(isinstance(k,str)and k.isdigit()for k in parts):return False
                parts=[parts[k]for k in sorted(parts,key=int)]
            if d.get('selection_policy')==POLICY:
                # Remember a recent native route, never an unqualified marker.
                # Keeping a failed catalogue route also preserves that host's
                # refusal/cooldown rather than silently falling back to MOPS.
                if d.get('http_request_sent')is not True or not isinstance(parts,list):continue
                roots=[p for p in parts if isinstance(p,dict)and p.get('http_request_sent')is True
                    and p.get('request_method')=='GET'and p.get('request_url_sha256')==sha256(ROOT.encode()).hexdigest()
                    and type(p.get('http_status'))is int and 100<=p['http_status']<=599]
                if not roots:continue
                if status=='success':
                    return type(count)is int and count==5 and any(p.get('response_complete')is True and p['http_status']==200 for p in roots)
                return status=='error'and type(count)is int and count==0
            if (status!='error'or type(count)is not int or count!=0 or not isinstance(parts,list)
                    or len(parts)!=1 or not isinstance(parts[0],dict)
                    or d.get('http_status')in(401,402,403,429)):return False
            last=parts[0]
            return (last.get('error_kind')in{'timeout','transport_error','server_error'}
                and last.get('http_request_sent')is True and last.get('response_complete')is False
                and last.get('request_method')=='POST'and last.get('http_status')not in(401,402,403,429)
                and last.get('request_url_sha256')==sha256(INDEX_URL.encode()).hexdigest())
    except (sqlite3.Error,OSError,ValueError,TypeError,OverflowError):pass
    return False
