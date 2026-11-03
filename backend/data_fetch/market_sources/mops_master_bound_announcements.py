"""Dynamic MOPS announcement admission bound to the complete official master.

The master proves issuer eligibility, the native index alone publishes actions,
and each complete body proves its own issuer, publication and content. No model
or browser identity is used and no legacy cache namespace is replaced.
"""
from copy import deepcopy
from datetime import datetime
import csv
import io
import json
import re
import time
from zoneinfo import ZoneInfo

POLICY = 'mops-company-json-master-bound-v1'



def prefer_master_bound_route(ticker):
    """Learn a recovery route from actual saved observations, read-only.

    Healthy legacy protocols keep their route. The same outer cache key and
    its original freshness/cooldown remain authoritative before any download.
    """
    import sqlite3
    from pathlib import Path
    from provider_sla import TASK_DB_PATH
    from .mops_json_company_history import TICKERS
    if (not isinstance(ticker,str) or not re.fullmatch(r'[1-9]\d{3,5}\.TW',ticker)
            or ticker.startswith('91')or ticker in TICKERS):return False
    path=Path(TASK_DB_PATH)
    if not path.exists():return False
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)as db:
            rows=db.execute("SELECT status,record_count,details_json FROM provider_sla_events WHERE source=? AND provider=? ORDER BY id DESC LIMIT 512",
                ('recent_catalysts','TWSE company announcement history')).fetchall()
        for status,count,raw in rows:
            try:details=json.loads(raw or '{}')
            except (ValueError,TypeError):continue
            if not isinstance(details,dict)or details.get('ticker')!=ticker:continue
            if type(count)is not int or count<0:return False
            if details.get('parser_version')==POLICY:return True
            if count>0:return False
            # Cache/cooldown observations do not replace the last real route
            # result, and the outer shared cache still enforces their expiry.
            if details.get('cache_hit')is True or details.get('cooldown')is True:
                continue
            if details.get('http_request_sent')is not True:return False
            def refused(code):
                return code is not None and (type(code)is not int or not 100<=code<=599 or code in {401,403,429})
            if refused(details.get('http_status')):return False
            attempts=details.get('request_observations')
            if isinstance(attempts,list) and (len(attempts)>70 or any(not isinstance(a,dict)or refused(a.get('http_status'))for a in attempts)):
                return False
            recoverable={None,'','timeout','transport_error','server_error','TimeoutError','ConnectError','ReadTimeout','ConnectTimeout'}
            return status in {'error','unavailable'}and count==0 and (details.get('error_kind')is None or isinstance(details.get('error_kind'),str))and details.get('error_kind')in recoverable
    except (OSError,sqlite3.Error):
        pass
    return False


def master_identity(receipt, ticker, data=None, *, historical=False):
    from . import official_issuer_master as master
    from news_record_utils import clean_text
    if (not isinstance(ticker,str) or not re.fullmatch(r'[1-9]\d{3,5}\.TW',ticker)
            or not isinstance(receipt,dict)):
        raise ValueError('MOPS master issuer invalid')
    stamp = receipt.get('retrieved_at')
    age = max(86400,time.time()-stamp+1) if historical and master._number(stamp) else master.RAW_TTL
    raw = master.original_bytes(receipt,max_age=age)
    if receipt['source_url'] == master.MASTER_URL:
        rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig','strict')),strict=True))
    else:
        from .official_issuer_master_json import parse_rows
        rows = parse_rows(raw,receipt['retrieved_at'])
    code = ticker.split('.')[0]
    found = [row for row in rows if row.get('公司代號')==code]
    if len(found)!=1:
        raise ValueError('MOPS issuer absent from complete official master')
    row = found[0]
    short, legal = (clean_text(row.get(k)).strip() for k in ('公司簡稱','公司名稱'))
    if (not short or not legal or max(len(short),len(legal))>256
            or re.search(r'-DR(?:\b|$)',short,re.IGNORECASE) or code.startswith('91')):
        raise ValueError('MOPS ordinary issuer eligibility unverified')
    identity = {'ticker':ticker,'stock_id':code,'official_name':short,'legal_name':legal,'instrument_type':'EQUITY'}
    if data is not None:
        if (not isinstance(data,dict) or data.get('ticker')!=ticker
                or data.get('stock_id')not in (None,'',code)
                or any(data.get(k)not in(None,'','EQUITY')for k in('instrument_type','quote_type','quoteType'))):
            raise ValueError('MOPS data issuer/instrument mismatch')
        actual = data.get('company_identity')
        if actual is not None:
            if not isinstance(actual,dict):raise ValueError('MOPS company identity invalid')
            if (any(actual.get(k)not in(None,'',v)for k,v in identity.items())
                    or any(actual.get(k)not in(None,'','EQUITY')for k in('quote_type','quoteType'))):
                raise ValueError('MOPS company identity differs from master')
            aliases = actual.get('forbidden_aliases',[])
            if (not isinstance(aliases,(list,tuple)) or any(not isinstance(a,str)
                    or clean_text(a).strip().strip('*').strip().casefold()in{short.casefold(),legal.casefold()}for a in aliases)):
                raise ValueError('MOPS forbidden issuer identity')
    return identity


def fetch_master_bound_announcements(ticker):
    from . import mops_json_company_history as source
    from .official_issuer_master_transport import IssuerMasterHttp
    from .official_issuer_master import MASTER_URL
    from .twse_history_transport import BoundedHistoryHttp
    from .twse_company_history import FETCH_BUDGET_SECONDS
    started = time.monotonic();deadline = started+FETCH_BUDGET_SECONDS
    master_http = IssuerMasterHttp(deadline)
    transport = BoundedHistoryHttp(deadline)
    audit = {'status':'error','record_count':0,'coverage_status':'partial','parser_version':POLICY}
    records = []
    try:
        if (not isinstance(ticker,str) or not re.fullmatch(r'[1-9]\d{3,5}\.TW',ticker)
                or ticker.startswith('91') or ticker in source.TICKERS):
            raise ValueError('existing MOPS protocol must retain its original admission')
        _, receipt = master_http.get_receipt(MASTER_URL)
        master_identity(receipt,ticker)
        def publish(response,query):
            transport.register_published_json_index(response,query,receipt)
        records,audit = source.fetch_json_announcements(ticker,now=datetime.now(ZoneInfo('Asia/Taipei')),
            post=transport.post,deadline=deadline,issuer_master=receipt,publish_index=publish)
        # Producer handoff is live; persisted per-document evidence is separately
        # historical and cannot renew this acquisition's eligibility or timestamp.
        master_identity(receipt,ticker)
        if time.monotonic()>=deadline:raise TimeoutError('MOPS shared deadline')
        stamps = [row['mops_json_receipt']['detail_receipt']['retrieved_at']for row in records]
        audit.update(progress_fresh_until_epoch=min([receipt['fresh_until_epoch'],*[s+1800 for s in stamps]]),
            progress_resume_possible=False,issuer_master_receipt=deepcopy(receipt))
    except Exception as exc:
        # No fallback to a looser identity/body protocol after a master refusal.
        audit.update(status='error',coverage_status='partial',record_count=0,
            error_kind=getattr(exc,'error_kind',type(exc).__name__),
            http_status=getattr(exc,'status_code',None),message='獨立官方主檔或MOPS公告原件未通過；保留既有資料。')
        records = []
    audit.update(record_count=len(records),http_request_sent=bool(master_http.http_request_count+transport.http_request_count),
        http_request_count=master_http.http_request_count+transport.http_request_count,
        request_observations=[dict(x)for x in transport.request_observations],
        component_statuses=[deepcopy(x)for x in master_http.components],
        duration_ms=int((time.monotonic()-started)*1000))
    return records,audit
