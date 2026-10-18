"""Published ordinary MOPS POST originals, with replayable issuer/date evidence."""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
import json
import math
import re
import time

from news_record_utils import parse_news_datetime, clean_text
from official_response_evidence import archive_response, read_response
from .twse_history_transport import JSON_URL, ORDINARY_DETAIL_URL, ORDINARY_DETAIL_CODES

PROVIDER = 'TWSE company announcement history'
POLICY = 'mops-company-json-original-v1'
TICKERS = frozenset(code + '.TW' for code in ORDINARY_DETAIL_CODES)
PAGE_URL = 'https://mops.twse.com.tw/mops/#/web/t05st01'
INDEX_TITLES = ['公司代號', '公司名稱', '發言日期', '發言時間', '主旨', '詳細資料']
DETAIL_TITLES = ['序號', '發言日期', '發言時間', '發言人', '發言人職稱', '發言人電話',
                 '主旨', '符合條款', '事實發生日', '說明']
CONTENT_FIELDS = ('ticker', 'title', 'date', 'published_at', 'text', 'summary', 'source',
                  'publisher', 'source_type', 'source_role', 'issuer_evidence_basis', 'link',
                  'source_document_url', 'source_request_parameters', 'content_coverage',
                  'content_truncated', 'content_sha256')


def validate_json_context(data, ticker):
    if (not isinstance(data, dict) or ticker not in TICKERS or data.get('ticker') != ticker
            or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):
        raise ValueError('mops_context_or_instrument_invalid')
    identity = data.get('company_identity')
    if identity is None:
        identity = {}
    if (not isinstance(identity, dict) or identity.get('ticker') not in (None,'',ticker)
            or identity.get('instrument_type') not in (None,'','EQUITY')):
        raise ValueError('mops_identity_invalid')


def _text(value):
    return ' '.join(value.split())


def _stamp(day, clock, tz):
    if (not isinstance(day, str) or not re.fullmatch(r'\d{3}/\d{2}/\d{2}', day)
            or not isinstance(clock, str) or not re.fullmatch(r'\d{2}:\d{2}:\d{2}', clock)):
        raise ValueError('mops_publication_invalid')
    year, month, date = map(int, day.split('/'))
    return datetime.fromisoformat(f'{year+1911:04d}-{month:02d}-{date:02d}T{clock}').replace(tzinfo=tz)


def _result(raw, code):
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError('mops_envelope_invalid')
    if payload.get('code') == 406 and payload.get('message') == '查無相符資料' and payload.get('result') is None:
        return None
    result = payload.get('result')
    if (payload.get('code') != 200 or payload.get('message') != '查詢成功'
            or not isinstance(result, dict) or result.get('marketName') != '上市公司'
            or result.get('companyId') != code or not isinstance(result.get('companyAbbreviation'), str)
            or not 1 <= len(result['companyAbbreviation'].strip()) <= 100):
        raise ValueError('mops_envelope_or_issuer_invalid')
    return result


def _candidate(row, query, company, tz):
    if (not isinstance(query, dict) or set(query) != {'companyId','year','month','firstDay','lastDay'}
            or query.get('companyId') not in ORDINARY_DETAIL_CODES
            or any(not isinstance(query.get(k), str) or not query[k].isdigit()
                   for k in ('year','month','firstDay','lastDay'))
            or not isinstance(row, list) or len(row) != 6 or row[:2] != [query['companyId'], company]
            or not isinstance(row[4], str) or not 1 <= len(_text(row[4])) <= 300):
        raise ValueError('mops_index_row_invalid')
    published = _stamp(row[2], row[3], tz)
    if (published.year-1911 != int(query['year']) or published.month != int(query['month'])
            or not 1 <= int(query['firstDay']) <= published.day <= int(query['lastDay'])
                   <= calendar.monthrange(published.year, published.month)[1]):
        raise ValueError('mops_index_query_mismatch')
    action = row[5]
    params = action.get('parameters') if isinstance(action, dict) and action.get('apiName') == 't05st01_detail' else None
    if (not isinstance(params, dict) or set(params) != {'companyId','marketKind','enterDate','serialNumber'}
            or params.get('companyId') != query['companyId'] or params.get('marketKind') != 'sii'
            or not isinstance(params.get('serialNumber'), str) or not re.fullmatch(r'[1-9]\d{0,5}', params['serialNumber'])
            or not isinstance(params.get('enterDate'), str) or not re.fullmatch(r'\d{7}', params['enterDate'])):
        raise ValueError('mops_published_action_invalid')
    entry = params['enterDate']
    entry_date = datetime(int(entry[:3])+1911, int(entry[3:5]), int(entry[5:])).date()
    # An updated announcement can publish later than its original entry date.
    # Keep the exact published action; the original must independently match
    # the index's publication timestamp, title, issuer and serial number.
    if entry_date > published.date():
        raise ValueError('mops_action_future_entry')
    return published, dict(params)


def _record(result, row, published, params, ticker):
    if (result is None or result['companyAbbreviation'] != row[1]
            or [x.get('main') for x in result.get('titles', []) if isinstance(x, dict)] != DETAIL_TITLES
            or not isinstance(result.get('data'), list) or len(result['data']) != 1
            or not isinstance(result['data'][0], list) or len(result['data'][0]) != 10
            or any(not isinstance(x, str) for x in result['data'][0])):
        raise ValueError('mops_original_shape_invalid')
    fields = dict(zip(DETAIL_TITLES, result['data'][0]))
    if (fields['序號'] != params['serialNumber']
            or _stamp(fields['發言日期'], fields['發言時間'], published.tzinfo) != published
            or _text(fields['主旨']) != _text(row[4]) or len(fields['說明'].strip()) < 20):
        raise ValueError('mops_original_publication_or_content_invalid')
    text = f"{row[1]}（{ticker.split('.')[0]}） {_text(row[4])}\n{fields['說明'].strip()}"
    if len(text) > 12000:
        raise ValueError('mops_original_content_over_limit')
    return {'ticker': ticker, 'title': _text(row[4]), 'date': published.isoformat(),
            'published_at': published.isoformat(), 'text': text, 'summary': text[:1500],
            'source': PROVIDER, 'publisher': '臺灣證券交易所／公開資訊觀測站',
            'source_type': 'mops_issuer_announcement', 'source_role': 'issuer_statement',
            'issuer_evidence_basis': 'verified_mops_json_original', 'link': PAGE_URL,
            'source_document_url': ORDINARY_DETAIL_URL, 'source_request_parameters': params,
            'catalyst_assessment': 'not_assessed', 'content_coverage': 'text_available',
            'content_truncated': False, 'content_sha256': sha256(text.encode()).hexdigest()}


def _original(response, url, deadline):
    response.raise_for_status()
    if response.status_code != 200 or time.monotonic() >= deadline or not 0 < len(response.content) <= 256000:
        raise ValueError('mops_original_transfer_invalid')
    stamp = time.time()
    receipt = archive_response(response.content, source_url=url, retrieved_at=stamp, http_status=200)
    if receipt.get('status') != 'archived' or read_response(receipt) != response.content:
        raise ValueError('mops_original_archive_unavailable')
    if time.monotonic() >= deadline:
        raise TimeoutError('mops_shared_deadline')
    return response.content, receipt


def fetch_json_announcements(ticker, *, now, post, deadline):
    audit = {'status': 'unavailable', 'record_count': 0, 'parser_version': POLICY,
             'coverage_status': 'partial', 'requests': [], 'rejected_reason_counts': {}, 'detail_limit': 64}
    if ticker not in TICKERS:
        return [], {**audit, 'status': 'not_applicable'}
    code, lower = ticker.split('.')[0], now-timedelta(days=30)
    cursor, candidates, records, seen = lower.replace(day=1), [], [], set()
    rejected = Counter()
    try:
        company = None
        while cursor.date() <= now.date() and len(audit['requests']) < 3:
            last = cursor.replace(day=calendar.monthrange(cursor.year, cursor.month)[1])
            query = {'companyId': code, 'year': str(cursor.year-1911), 'month': str(cursor.month),
                     'firstDay': str(max(cursor.date(),lower.date()).day), 'lastDay': str(min(last.date(),now.date()).day)}
            if time.monotonic() >= deadline:
                raise TimeoutError('mops_shared_deadline')
            raw, receipt = _original(post(JSON_URL,json=query,timeout=(2,4),provider=PROVIDER),JSON_URL,deadline)
            audit['requests'].append({'query': query, 'receipt': receipt})
            result = _result(raw,code)
            if result is not None:
                if ([x.get('main') for x in result.get('titles',[]) if isinstance(x,dict)] != INDEX_TITLES
                        or not isinstance(result.get('data'),list) or len(result['data']) > 64
                        or company is not None and company != result['companyAbbreviation']):
                    raise ValueError('mops_index_shape_or_company_changed')
                company = result['companyAbbreviation']
                for row in result['data']:
                    try:
                        published,params = _candidate(row,query,company,now.tzinfo)
                        key = json.dumps(params,sort_keys=True)
                        if key in seen:
                            raise ValueError('mops_duplicate_action')
                        seen.add(key)
                        if lower <= published <= now:
                            candidates.append((published,row,params,query,receipt))
                    except (ValueError,TypeError,KeyError):
                        rejected['index_row_unverified'] += 1
            cursor = last+timedelta(days=1)
        if cursor.date() <= now.date() or len(candidates) > 64:
            raise ValueError('mops_window_over_limit')
        for published,row,params,query,index_receipt in sorted(candidates,key=lambda x:x[0],reverse=True):
            if time.monotonic() >= deadline:
                raise TimeoutError('mops_shared_deadline')
            try:
                raw,detail_receipt = _original(post(ORDINARY_DETAIL_URL,json=params,timeout=(2,4),provider=PROVIDER),ORDINARY_DETAIL_URL,deadline)
                record = _record(_result(raw,code),row,published,params,ticker)
                record['mops_json_receipt'] = {'policy':POLICY,'ticker':ticker,'index_query':query,'index_row':row,
                                               'index_receipt':index_receipt,'detail_receipt':detail_receipt}
                if time.monotonic() >= deadline:
                    raise TimeoutError('mops_shared_deadline')
                records.append(record)
            except (ValueError,TypeError,KeyError):
                rejected['original_unverified'] += 1
        complete = not rejected and len(records)==len(candidates) and time.monotonic()<deadline
        audit.update(status='success' if complete and records else 'degraded_enrichment' if records or rejected else 'unavailable',
                     coverage_status='window_complete' if complete else 'partial')
    except Exception as exc:
        audit.update(status='error',error_kind=getattr(exc,'error_kind',type(exc).__name__),
                     http_status=getattr(getattr(exc,'response',None),'status_code',getattr(exc,'status_code',None)))
    audit.update(record_count=len(records),rejected_reason_counts=dict(rejected),
                 message='已核對新版MOPS公告原文；發言日期與原published action分開保存。' if records else '新版MOPS未取得可核對的近期公告原文。')
    return records,audit


def _saved(receipt, url):
    stamp = receipt.get('retrieved_at')
    if (receipt.get('status') != 'archived' or receipt.get('source_url') != url or receipt.get('http_status') != 200
            or type(stamp) not in (int,float) or not math.isfinite(stamp) or not 0 < stamp <= time.time()+300):
        raise ValueError('mops_saved_receipt_invalid')
    raw = read_response(receipt)
    if not 0 < len(raw) <= 256000 or receipt.get('raw_response_bytes') != len(raw):
        raise ValueError('mops_saved_original_size_invalid')
    return raw


def verified_json_record(record, data):
    try:
        ticker = data['ticker']
        validate_json_context(data, ticker)
        receipt = record['mops_json_receipt']
        if (ticker not in TICKERS or receipt.get('ticker') != ticker or receipt.get('policy') != POLICY
                or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):
            return None
        code = ticker.split('.')[0]
        result = _result(_saved(receipt['index_receipt'],JSON_URL),code)
        if result is None or result['data'].count(receipt['index_row']) != 1:
            return None
        company = result['companyAbbreviation']
        identity = data.get('company_identity')
        if identity is None:
            identity = {}
        if (not isinstance(identity,dict) or identity.get('ticker') not in (None,'',ticker)
                or identity.get('official_name') not in (None,'',company)):
            return None
        forbidden = identity.get('forbidden_aliases',[])
        if (not isinstance(forbidden,(list,tuple))
                or any(not isinstance(x,str) or clean_text(x).strip().strip('*').strip().casefold()==company.casefold()
                       for x in forbidden)):
            return None
        from zoneinfo import ZoneInfo
        published,params = _candidate(receipt['index_row'],receipt['index_query'],company,ZoneInfo('Asia/Taipei'))
        rebuilt = _record(_result(_saved(receipt['detail_receipt'],ORDINARY_DETAIL_URL),code),receipt['index_row'],published,params,ticker)
        if any(record.get(k)!=rebuilt[k] for k in CONTENT_FIELDS if k not in ('date','published_at')):
            return None
        if any(parse_news_datetime(record.get(k))!=published for k in ('date','published_at')):
            return None
        return company
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,OSError,EOFError):
        return None


def guard_json_result(result, data):
    """Do not publish a successful acquisition audit for damaged originals."""
    from ..types import ProviderResult
    if result.status not in {'success','degraded_enrichment','skipped_fresh_cache'}:
        return result
    rows, audit = result.value, result.audit if isinstance(result.audit,dict) else {}
    stamp = audit.get('fetched_at_epoch')
    if (isinstance(rows,list) and 1 <= len(rows) <= 64
            and type(audit.get('record_count')) is int and audit['record_count']==len(rows)
            and audit.get('status')==result.status and audit.get('provider')==PROVIDER
            and audit.get('source')=='recent_catalysts'
            and type(stamp) in (int,float) and math.isfinite(stamp) and 0 < stamp <= time.time()+300
            and all(isinstance(row,dict) and verified_json_record(row,data) for row in rows)):
        return result
    failed = {**audit,'status':'error','record_count':0,'coverage_status':'partial',
              'error_kind':'original_unverified','message':'新版公告原件或憑據未通過核對，保留原快照。'}
    return ProviderResult('recent_catalysts',PROVIDER,'error',value=[],audit=failed,duration_ms=result.duration_ms)


def announcement_link_identity(record):
    """Internal filing key; keep the real general page as the public URL."""
    try:
        receipt = record['mops_json_receipt']
        ticker = receipt['ticker']
        if not verified_json_record(record,{'ticker':ticker}):
            return None
        return 'mops-json-original:'+json.dumps(record['source_request_parameters'],sort_keys=True)
    except (KeyError,TypeError,ValueError,AttributeError):
        return None
