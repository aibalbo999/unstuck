"""Checked foreign-issuer MOPS originals for one officially anchored TDR.

The ordinary IIH/EZSearch announcement formats do not cover these originals.
Amounts, currencies and periods remain source text; they are not a financial
series or an earnings-call transcript. Bilingual filings are one event sample.
"""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import re
import time
import unicodedata
from zoneinfo import ZoneInfo

from news_record_utils import clean_text, parse_news_datetime
from official_response_evidence import archive_response, read_response
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .official_company_legal_name import (URLS, parse_roster, read_cached_listed_roster_bytes,
                                         select_legal_name)
from .twse_history_transport import JSON_URL, TDR_DETAIL_URL

PROVIDER = 'MOPS TDR issuer announcements'
POLICY = 'medtecs-mops-tdr-original-v1'
TICKER, CODE, SHORT = '9103.TW', '9103', '美德醫療-DR'
LEGAL = '美德向邦醫療國際股份有限公司'
TAIPEI = ZoneInfo('Asia/Taipei')
PAGE_URL = 'https://mops.twse.com.tw/mops/#/web/t05st01'
INDEX_TITLES = ['公司代號', '公司名稱', '發言日期', '發言時間', '主旨', '詳細資料']
DETAIL_TITLES = ['公司代號', '公告序號', '事實發生日', '公司名稱', '主旨', '符合條款',
                 '發生依外國發行人所屬國及上市地國法令規定應即申報之重大情事', '其他']
CONTENT_FIELDS = ('ticker', 'title', 'date', 'text', 'summary', 'link', 'source_document_url', 'publisher',
                  'source', 'source_type', 'source_role', 'issuer_evidence_basis', 'event_date',
                  'content_coverage', 'content_truncated', 'publication_date_precision', 'source_request_parameters')


def _compact(value):
    return re.sub(r'\s+', '', value).casefold()


def _digest(record):
    projection = {k: record.get(k) for k in CONTENT_FIELDS}
    stamp = parse_news_datetime(projection['date'])
    projection['date'] = stamp.astimezone(timezone.utc).isoformat() if stamp else None
    return sha256(json.dumps(projection,
                             ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('tdr_source_deadline')


def _master_anchor(raw, stamp, now, *, require_fresh):
    """Rebuild issuer identity from the complete master, including saved reads."""
    anchor = select_legal_name(parse_roster(raw, '.TW'), TICKER, SHORT, today=now.date())
    rows = [row for row in json.loads(raw) if str(row.get('公司代號')) == CODE]
    if (not anchor or len(rows) != 1 or anchor['legal_name'] != LEGAL
            or type(stamp) not in (int, float) or not math.isfinite(stamp)
            or not 0 < stamp <= time.time() + 300
            or require_fresh and time.time() - stamp > 86400
            or str(rows[0].get('英文簡稱') or '').strip() != 'MEDTECS'
            or str(rows[0].get('網址') or '').strip() not in {'www.medtecs.com', 'https://www.medtecs.com'}
            or not str(rows[0].get('外國企業註冊地國') or '').strip().startswith('BM ')):
        raise ValueError('tdr_master_identity_unverified')
    return {'policy': POLICY, 'ticker': TICKER, 'official_name': SHORT, 'legal_name': LEGAL,
            'master_observed_on': anchor['as_of'], 'master_source_url': URLS['.TW'],
            'master_response_sha256': sha256(raw).hexdigest(), 'master_fetched_at_epoch': stamp}


def _master(now, get, deadline):
    cached = read_cached_listed_roster_bytes()
    if not cached:
        if time.monotonic() >= deadline:
            raise TimeoutError('tdr_source_deadline')
        raw, receipt = _original(get(URLS['.TW'], timeout=(2,4), provider=PROVIDER), URLS['.TW'], 2500000, deadline)
        cached = raw, {'fetched_at_epoch': receipt['retrieved_at'], 'stale': False,
                       'source_url': URLS['.TW'], 'source_payload_sha256': receipt['raw_response_sha256']}
    raw, meta = cached
    stamp = meta.get('fetched_at_epoch')
    if (meta.get('stale') is True or meta.get('source_url') != URLS['.TW']
            or meta.get('source_payload_sha256') != sha256(raw).hexdigest()):
        raise ValueError('tdr_master_identity_unverified')
    anchor = _master_anchor(raw, stamp, now, require_fresh=True)
    # Reused bytes retain their original acquisition epoch; no cache renewal.
    proof = archive_response(raw, source_url=URLS['.TW'], retrieved_at=stamp, http_status=200)
    if proof.get('status') != 'archived' or read_response(proof) != raw:
        raise ValueError('tdr_master_archive_unavailable')
    _check_deadline(deadline)
    return anchor


def _original(response, url, limit, deadline):
    _check_deadline(deadline)
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError('tdr_original_http_status_invalid')
    raw = response.content
    if not isinstance(raw, bytes) or not 0 < len(raw) <= limit:
        raise ValueError('tdr_original_size_invalid')
    receipt = archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200)
    if receipt.get('status') != 'archived' or read_response(receipt) != raw:
        raise ValueError('tdr_original_archive_unavailable')
    _check_deadline(deadline)
    return raw, receipt


def _result(raw):
    payload = json.loads(raw)
    if (not isinstance(payload, dict) or payload.get('code') != 200
            or payload.get('message') != '查詢成功' or not isinstance(payload.get('result'), dict)):
        raise ValueError('tdr_json_envelope_invalid')
    result = payload['result']
    if (result.get('marketName') != '上市公司' or result.get('companyId') != CODE
            or result.get('companyAbbreviation') != SHORT):
        raise ValueError('tdr_json_issuer_invalid')
    return result


def _candidate(row, query):
    if (not isinstance(query,dict) or set(query)!= {'companyId','year','month','firstDay','lastDay'}
            or query.get('companyId')!=CODE
            or not isinstance(query.get('year'),str) or not re.fullmatch(r'[1-9]\d{2}',query['year'])
            or not isinstance(query.get('month'),str) or not re.fullmatch(r'(?:0?[1-9]|1[0-2])',query['month'])
            or any(not isinstance(query.get(k),str) or not re.fullmatch(r'(?:0?[1-9]|[12]\d|3[01])',query[k]) for k in ('firstDay','lastDay'))
            or int(query['firstDay'])>int(query['lastDay'])):
        raise ValueError('tdr_index_query_invalid')
    if (not isinstance(row, list) or len(row) != 6 or row[:2] != [CODE, SHORT]
            or not isinstance(row[4], str) or not 1 <= len(row[4]) <= 300
            or not isinstance(row[2], str) or not re.fullmatch(r'\d{3}/\d{2}/\d{2}', row[2])
            or not isinstance(row[3], str) or not re.fullmatch(r'\d{2}:\d{2}:\d{2}', row[3])):
        raise ValueError('tdr_index_row_invalid')
    year, month, day = map(int, row[2].split('/'))
    published = datetime.fromisoformat(f'{year + 1911:04d}-{month:02d}-{day:02d}T{row[3]}').replace(tzinfo=TAIPEI)
    if (query.get('companyId') != CODE or year != int(query['year']) or month != int(query['month'])
            or not int(query['firstDay']) <= day <= int(query['lastDay'])):
        raise ValueError('tdr_index_query_mismatch')
    action = row[5]
    params = action.get('parameters') if isinstance(action, dict) and action.get('apiName') == 't59sb01_detail' else None
    if (not isinstance(params, dict) or set(params) != {'marketKind', 'companyId', 'serialNumber', 'enterDate'}
            or params.get('marketKind') != 'sii' or params.get('companyId') != CODE
            or params.get('enterDate') != f'{year:03d}{month:02d}{day:02d}'
            or not isinstance(params.get('serialNumber'), str)
            or not re.fullmatch(r'[1-9]\d?', params['serialNumber'])):
        raise ValueError('tdr_detail_binding_invalid')
    return published, params


def _detail(row, index_row, published, params):
    if (not isinstance(row, list) or len(row) != 8 or row[0] != CODE
            or type(row[1]) is not int or row[1] != int(params['serialNumber'])
            or row[3] != LEGAL or row[4] != index_row[4] or row[5] != '第五條第28款'
            or not isinstance(row[6], str) or not 20 <= len(row[6]) <= 12000):
        raise ValueError('tdr_original_identity_invalid')
    match = re.fullmatch(r'民國(\d{3})年(\d{1,2})月(\d{1,2})日', str(row[2]))
    if not match:
        raise ValueError('tdr_fact_date_invalid')
    y, m, day = map(int, match.groups()); fact = date(y + 1911, m, day)
    if fact > published.date():
        raise ValueError('tdr_future_fact_date')
    filename = f"{CODE}_{published:%Y%m%d}{int(params['serialNumber']):02d}_FIM"
    attachment = row[7]
    if attachment == '':
        if re.search(r'附加檔|附檔|詳附件', row[6]):
            raise ValueError('tdr_referenced_attachment_missing')
        return fact, None
    expected = {'fileName': filename,
                'url': f'https://mopsov.twse.com.tw/nas/t59/t59sa01/{filename}.pdf'}
    if attachment != expected:
        raise ValueError('tdr_attachment_binding_invalid')
    return fact, expected['url']


def _pdf_text(raw, title, fact, deadline):
    _check_deadline(deadline)
    if not raw.startswith(b'%PDF-'):
        raise ValueError('tdr_attachment_not_pdf')
    result = extract_pdf_pages(raw, timeout_seconds=min(5., max(.001, deadline - time.monotonic())))
    body = clean_text('\n'.join(page['text'] for page in result['pages']))
    base = re.sub(r'-[中英]文版$', '', title)
    signed = re.findall(r'謹代表董事會[\s\S]{0,300}?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', body)
    if (result['coverage_status'] != 'complete' or not 1 <= result['page_count'] <= 8
            or not 100 <= len(body) <= 12000 or LEGAL not in body
            or _compact(base) not in _compact(body)
            or signed != [(str(fact.year), str(fact.month), str(fact.day))]):
        raise ValueError('tdr_pdf_content_unverified')
    _check_deadline(deadline)
    return body, result


def _index_result(raw):
    result = _result(raw)
    if ([x.get('main') for x in result.get('titles', []) if isinstance(x, dict)] != INDEX_TITLES
            or not isinstance(result.get('data'), list) or len(result['data']) > 64):
        raise ValueError('tdr_index_shape_invalid')
    return result


def _detail_result(raw):
    result = _result(raw)
    if (result.get('header', {}).get('mainTitle') != ['外國發行人重大訊息']
            or [x.get('main') for x in result.get('titles', []) if isinstance(x, dict)] != DETAIL_TITLES
            or not isinstance(result.get('data'), list) or len(result['data']) != 1):
        raise ValueError('tdr_original_shape_invalid')
    return result


def _record(index_row, stamp, params, fact, url, body):
    text = f'{SHORT}（{CODE}） {index_row[4]}\n{body}'
    if len(text) > 12000:
        raise ValueError('tdr_content_over_limit')
    return {'ticker': TICKER, 'title': index_row[4], 'date': stamp.isoformat(),
            'text': text, 'summary': text[:1500], 'source': PROVIDER, 'publisher': LEGAL,
            'source_type': 'tdr_foreign_issuer_announcement', 'source_role': 'issuer_statement',
            'issuer_evidence_basis': 'verified_mops_tdr_original',
            'link': url or PAGE_URL, 'source_document_url': url or TDR_DETAIL_URL,
            'source_request_parameters': params, 'publication_date_precision': 'second',
            'event_date': fact.isoformat(), 'catalyst_assessment': 'not_assessed',
            'content_coverage': 'text_available', 'content_truncated': False}


def announcement_link_identity(record):
    """Internal dedupe key for POST-only originals; never invent a public URL."""
    try:
        receipt = record['tdr_mops_receipt']
        _stamp, params = _candidate(receipt['index_row'], receipt['index_query'])
        if (receipt.get('policy') != POLICY or record.get('source') != PROVIDER
                or record.get('source_type') != 'tdr_foreign_issuer_announcement'
                or record.get('source_document_url') != TDR_DETAIL_URL
                or record.get('link') != PAGE_URL or record.get('source_request_parameters') != params):
            return None
        return 'mops-tdr-original:' + json.dumps(params, sort_keys=True)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def fetch_tdr_announcements(ticker, *, now, get, post, deadline):
    """Read at most three exact monthly ranges and ten original event samples."""
    audit = {'status': 'unavailable', 'record_count': 0, 'actual_provider': PROVIDER,
             'selection_policy': POLICY, 'coverage_status': 'partial', 'window_complete': False,
             'bilingual_variant_count': 0, 'rejected_reason_counts': {}, 'requests': []}
    if ticker != TICKER:
        return [], {**audit, 'status': 'not_applicable'}
    rejected, candidates, records = Counter(), [], []
    try:
        master = _master(now, get, deadline)
        lower = now - timedelta(days=30); cursor = lower.replace(day=1)
        month_count = 0
        while cursor.date() <= now.date() and month_count < 3:
            last = cursor.replace(day=calendar.monthrange(cursor.year, cursor.month)[1])
            first_day, last_day = max(cursor.date(), lower.date()), min(last.date(), now.date())
            query = {'companyId': CODE, 'year': str(cursor.year-1911), 'month': str(cursor.month),
                     'firstDay': f'{first_day.day:02d}', 'lastDay': f'{last_day.day:02d}'}
            if time.monotonic() >= deadline:
                raise TimeoutError('tdr_source_deadline')
            response = post(JSON_URL, json=query, timeout=(2,4), provider=PROVIDER)
            raw, receipt = _original(response, JSON_URL, 256000, deadline); result = _index_result(raw)
            audit['requests'].append({'query': query, 'receipt': receipt})
            for row in result['data']:
                try:
                    stamp, params = _candidate(row, query)
                    if lower <= stamp <= now:
                        candidates.append((stamp, row, params, query, receipt))
                except (ValueError, TypeError, KeyError):
                    rejected['index_row_unverified'] += 1
            cursor = last + timedelta(days=1); month_count += 1
            _check_deadline(deadline)
        groups = {}
        for item in sorted(candidates, reverse=True, key=lambda x: x[0]):
            stamp, row = item[:2]; language = re.search(r'-([中英])文版$', row[4])
            key = (stamp.date(), re.sub(r'-[中英]文版$', '', row[4]))
            if language and key in groups and groups[key][1][4].endswith('-' + ('英' if language[1]=='中' else '中')+'文版'):
                audit['bilingual_variant_count'] += 1
                if language[1] == '中': groups[key] = item
            elif key not in groups:
                groups[key] = item
            else:
                rejected['ambiguous_repeated_title'] += 1
        if len(groups) > 10:
            rejected['sample_limit'] += len(groups)-10
        for stamp, index_row, params, query, index_receipt in sorted(groups.values(), reverse=True, key=lambda x:x[0])[:10]:
            if time.monotonic() >= deadline:
                rejected['deadline_exhausted'] += 1; break
            try:
                response = post(TDR_DETAIL_URL, json=params, timeout=(2,4), provider=PROVIDER)
                raw, detail_receipt = _original(response, TDR_DETAIL_URL, 256000, deadline); detail = _detail_result(raw)
                detail_row = detail['data'][0]; fact, url = _detail(detail_row,index_row,stamp,params)
                body, pdf_receipt = detail_row[6], None
                if url:
                    _check_deadline(deadline)
                    binary, pdf_receipt = _original(get(url,timeout=(2,4),provider=PROVIDER),url,1000000,deadline)
                    body, extraction = _pdf_text(binary,index_row[4],fact,deadline)
                record = _record(index_row,stamp,params,fact,url,body)
                record['tdr_mops_receipt']={**master,'index_row':index_row,'index_query':query,
                    'detail_row':detail_row,'index_response_sha256':index_receipt['raw_response_sha256'],
                    'detail_response_sha256':detail_receipt['raw_response_sha256'],
                    'pdf_response_sha256':pdf_receipt['raw_response_sha256'] if pdf_receipt else None,
                    'content_response_sha256':(pdf_receipt or detail_receipt)['raw_response_sha256'],
                    'parsed_content_sha256':_digest(record)}
                _check_deadline(deadline)
                records.append(record)
            except Exception as exc:
                rejected['original_unverified'] += 1
                if isinstance(exc,TimeoutError) or time.monotonic() >= deadline:
                    audit['detail_stop_reason']='tdr_source_deadline';break
                status=getattr(getattr(exc,'response',None),'status_code',getattr(exc,'status_code',None))
                if status in {401,403,429} or status and status>=500 or getattr(exc,'error_kind','')=='cooldown':
                    audit['detail_stop_reason']=getattr(exc,'error_kind',None) or f'http_{status}';break
        audit.update(status='success' if records and not rejected else 'degraded_enrichment' if records else 'unavailable',
                     record_count=len(records),raw_count=len(candidates),rejected_reason_counts=dict(rejected),
                     message='已核對外國發行人公告原文；中英文版本合併為同一事件，保留原文幣別及期間。')
    except Exception as exc:
        audit.update(status='error',error_kind=getattr(exc,'error_kind',type(exc).__name__),
                     http_status=getattr(getattr(exc,'response',None),'status_code',getattr(exc,'status_code',None)),
                     rejected_reason_counts=dict(rejected),message='未取得完整可驗證的TDR公告原件。')
    return records,audit


def _archived_original(digest, limit):
    """Only canonical content-addressed storage supplies saved original bytes."""
    from runtime_paths import current_runtime_paths
    if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest):
        raise ValueError('tdr_archive_identity_invalid')
    path=current_runtime_paths().cache_dir/'official-response-evidence'/(digest+'.gz')
    raw=read_response({'raw_response_sha256':digest,'raw_response_path':str(path)})
    if not 0<len(raw)<=limit:
        raise ValueError('tdr_archive_size_invalid')
    return raw


def verified_tdr_record(record,data):
    try:
        receipt=record['tdr_mops_receipt'];identity=data.get('company_identity')
        if identity is None:identity={}
        if (not isinstance(receipt,dict) or data.get('ticker')!=TICKER or not isinstance(identity,dict)
                or identity.get('official_name') not in (None,'',SHORT)
                or identity.get('legal_name') not in (None,'',LEGAL)):
            return None
        forbidden=identity.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple)) or any(unicodedata.normalize('NFKC',clean_text(x)).strip().strip('*').strip().casefold() in {SHORT.casefold(),LEGAL.casefold()}for x in forbidden):
            return None
        expected={'policy':POLICY,'ticker':TICKER,'official_name':SHORT,'legal_name':LEGAL,'master_source_url':URLS['.TW']}
        if any(receipt.get(k)!=v for k,v in expected.items()):return None
        master_raw=_archived_original(receipt['master_response_sha256'],2500000)
        master=_master_anchor(master_raw,receipt['master_fetched_at_epoch'],datetime.now(TAIPEI),require_fresh=False)
        if any(receipt.get(k)!=v for k,v in master.items()):return None
        index=_index_result(_archived_original(receipt['index_response_sha256'],256000))
        if index['data'].count(receipt['index_row'])!=1:return None
        published,params=_candidate(receipt['index_row'],receipt['index_query'])
        detail=_detail_result(_archived_original(receipt['detail_response_sha256'],256000))
        detail_row=detail['data'][0]
        if receipt['detail_row']!=detail_row:return None
        fact,url=_detail(detail_row,receipt['index_row'],published,params)
        body=detail_row[6]
        if url:
            if not re.fullmatch(r'[0-9a-f]{64}',str(receipt.get('pdf_response_sha256')or'')) or receipt['content_response_sha256']!=receipt['pdf_response_sha256']:return None
            binary=_archived_original(receipt['pdf_response_sha256'],1000000)
            body,_=_pdf_text(binary,receipt['index_row'][4],fact,time.monotonic()+5.)
        elif receipt.get('pdf_response_sha256')is not None or receipt['content_response_sha256']!=receipt['detail_response_sha256']:return None
        rebuilt=_record(receipt['index_row'],published,params,fact,url,body)
        if record.get('content_truncated') is not False:return None
        if parse_news_datetime(record.get('date'))!=parse_news_datetime(rebuilt['date']):return None
        if any(record.get(k)!=rebuilt[k] for k in CONTENT_FIELDS if k!='date'):return None
        if receipt.get('parsed_content_sha256')!=_digest(rebuilt):return None
        return SHORT
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,OSError,EOFError,TimeoutError,SourcePdfError):
        return None
