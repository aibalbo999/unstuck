"""Complete current-ad originals with one independent, unextended batch owner.

Enabled advertisements are a bounded source observation, never new vacancies,
headcount, actual hiring intent or first publication. Public flags are not proof.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import math
import re
import time

from cache_store import get_cache_json
from official_response_evidence import archive_response, read_response
from .current_104_postings import POLICY, MAX_LIST_BYTES, MAX_DETAIL_BYTES, MAX_SAMPLES, TZ, parse_snapshot, _json

TTL = 1800
PREFIX = '104-current-enabled-batch:v1:'
SCHEMA = '104-current-enabled-originals:v1'
PROVIDER = '104 & 1111 job openings'


def _dump(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode()


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def list_url(issuer):
    from alternative_data_fetcher import _base36
    return 'https://www.104.com.tw/api/companies/' + _base36(int(issuer['official_ubn']) * 1000) + '/jobs'


def detail_url(job):
    if not isinstance(job, str) or not re.fullmatch(r'[a-z0-9]{3,12}', job):
        raise ValueError('104 noncanonical job ID')
    return 'https://www.104.com.tw/api/jobs/' + job


def cache_key(issuer):
    return 'shared_provider:v1:' + sha256((PREFIX + list_url(issuer)).encode()).hexdigest()


def valid_context(data, issuer):
    if not isinstance(data, dict) or not isinstance(issuer, dict):
        return False
    ticker = issuer.get('ticker'); i = data.get('company_identity')
    if (not isinstance(ticker, str) or not re.fullmatch(r'[1-9][0-9]{3,5}\.(TW|TWO)', ticker)
            or ticker.startswith('91') or data.get('ticker') != ticker or data.get('quote_type') != 'EQUITY'
            or not isinstance(i, dict) or i.get('ticker') != ticker or i.get('instrument_type') != 'EQUITY'
            or i.get('official_name') != issuer.get('official_short_name')
            or i.get('legal_name') not in (None, '', issuer.get('legal_name'))
            or i.get('official_ubn') not in (None, '', issuer.get('official_ubn'))
            or data.get('official_ubn') not in (None, '', issuer.get('official_ubn'))
            or any(v not in (None, '', ticker.split('.')[0]) for v in (data.get('stock_id'), i.get('stock_id')))
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quoteType'))):
        return False
    english = i.get('english_names', [])
    return (isinstance(english, list) and all(isinstance(v, str) for v in english)
            and isinstance(data.get('company_name'), str) and bool(data['company_name'].strip())
            and all(p.strip() and p.strip() in {issuer.get('legal_name'), issuer.get('official_short_name'), *english}
                    for p in data['company_name'].split(' / ')))


def verified_issuer(issuer, *, now=None):
    """Replay the complete current TWSE/TPEx master and its unchanged cache owner."""
    from runtime_paths import current_runtime_paths
    from .official_company_legal_name import (parse_roster, select_legal_name, URLS, MAX_BYTES,
        verified_legal_name_from_evidence, verified_official_ubn_from_evidence)
    now = time.time() if now is None else now
    try:
        ticker = issuer['ticker']; suffix = '.TWO' if ticker.endswith('.TWO') else '.TW'
        stamp = issuer['fetched_at_epoch']; short = issuer['official_short_name']
        if (not _finite(now) or not _finite(stamp) or not 0 <= now-stamp < 86400
                or verified_legal_name_from_evidence(issuer, ticker, short) != issuer['legal_name']
                or verified_official_ubn_from_evidence(issuer, ticker, short) != issuer['official_ubn']):
            return False
        digest = issuer['response_sha256']
        raw = read_response({'raw_response_sha256': digest, 'raw_response_path': str(
            current_runtime_paths().cache_dir/'official-response-evidence'/(digest+'.gz'))}, max_bytes=MAX_BYTES)
        roster = parse_roster(raw, suffix)
        if len(roster['entries']) < (800 if suffix == '.TW' else 600):
            return False
        selected = select_legal_name(roster, ticker, short, today=datetime.fromtimestamp(now, TZ).date())
        if not selected or any(issuer.get(k) != selected.get(k) for k in selected):
            return False
        saved = get_cache_json('shared_provider:v1:' + sha256(('official-company-roster:v2:'+suffix).encode()).hexdigest())
        end = saved.get('fresh_until_epoch') if isinstance(saved, dict) else None
        return (isinstance(saved, dict) and not saved.get('error_kind') and saved.get('value') == roster
            and saved.get('fetched_at_epoch') == stamp and _finite(end) and stamp <= now < end
            and 0 < end-stamp <= 86401 and issuer['source_url'] == URLS[suffix])
    except (ValueError, TypeError, KeyError, OSError, OverflowError, AttributeError, UnicodeError, RecursionError):
        return False


def _pathless(proof):
    return {k: v for k, v in proof.items() if k != 'raw_response_path'}


def _read(proof, url, stamp, kind, status, maximum):
    from runtime_paths import current_runtime_paths
    fields = {'status','source_url','retrieved_at','http_status','raw_response_sha256','raw_response_bytes',
              'evidence_kind','historical_point_in_time_verified','finality_guaranteed'}
    if (not isinstance(proof, dict) or set(proof) != fields or proof.get('status') != 'archived'
            or proof.get('source_url') != url or proof.get('retrieved_at') != stamp
            or proof.get('http_status') != status or type(proof.get('http_status')) is not type(status)
            or proof.get('evidence_kind') != kind or proof.get('historical_point_in_time_verified') is not False
            or proof.get('finality_guaranteed') is not False):
        raise ValueError('104 original metadata invalid')
    digest = proof.get('raw_response_sha256')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('104 original hash invalid')
    raw = read_response({**proof, 'raw_response_path':str(current_runtime_paths().cache_dir/'official-response-evidence'/(digest+'.gz'))}, max_bytes=maximum)
    if type(proof.get('raw_response_bytes')) is not int or not 0 < len(raw) == proof['raw_response_bytes'] <= maximum:
        raise ValueError('104 complete original missing')
    return raw


def archive_original(raw, url, stamp, correlation):
    """Called only after the owned native response checks; no public value is proof."""
    if (not isinstance(correlation, dict) or not all(isinstance(correlation.get(k), str) and correlation[k]
            for k in ('ticker','fetch_id','operation_id')) or not _finite(stamp)):
        raise ValueError('104 original acquisition identity missing')
    maximum = MAX_LIST_BYTES if re.fullmatch(r'https://www\.104\.com\.tw/api/companies/[a-z0-9]+/jobs', url) else MAX_DETAIL_BYTES
    if not (re.fullmatch(r'https://www\.104\.com\.tw/api/companies/[a-z0-9]+/jobs', url)
            or re.fullmatch(r'https://www\.104\.com\.tw/api/jobs/[a-z0-9]{3,12}', url)):
        raise ValueError('104 original URL invalid')
    proof = archive_response(raw, source_url=url, retrieved_at=stamp, http_status=200, max_bytes=maximum)
    return {'url':url, 'method':'GET', 'observed_at_epoch':stamp,
            'correlation':{k:correlation[k] for k in ('ticker','fetch_id','operation_id')},
            'raw_receipt':_pathless(proof)}


def selected_ids(raw):
    d = _json(raw, MAX_LIST_BYTES); cards = d.get('list')
    if not isinstance(cards, dict) or not isinstance(cards.get('topJobs'), list) or not isinstance(cards.get('normalJobs'), list):
        raise ValueError('104 listing absent')
    rows = cards['topJobs']+cards['normalJobs']
    if not 1 <= len(rows) <= 100:
        raise ValueError('104 listing size invalid')
    ids = []
    for row in rows:
        job = row.get('jobNo') if isinstance(row, dict) else None
        detail_url(job)
        if job not in ids: ids.append(job)
    return ids[:MAX_SAMPLES]


def _parse(receipts, issuer, now):
    if not isinstance(receipts, list) or not 2 <= len(receipts) <= 1+MAX_SAMPLES:
        raise ValueError('104 complete batch missing')
    bodies = []; stamps = []; identity = None
    for n, r in enumerate(receipts):
        if not isinstance(r, dict) or set(r) != {'url','method','observed_at_epoch','correlation','raw_receipt'}:
            raise ValueError('104 original shape invalid')
        stamp = r['observed_at_epoch']; c = r['correlation']
        if (not _finite(stamp) or not 0 <= now-stamp < TTL or r['method'] != 'GET'
                or not isinstance(c, dict) or set(c) != {'ticker','fetch_id','operation_id'}
                or c['ticker'] != issuer['ticker'] or not all(isinstance(v,str) and 0 < len(v) <= 160 for v in c.values())
                or identity is not None and identity != c):
            raise ValueError('104 batch time or acquisition identity invalid')
        identity = c
        expected_url = list_url(issuer) if n == 0 else detail_url(selected[n-1])
        if r['url'] != expected_url:
            raise ValueError('104 selected URL mismatch')
        raw = _read(r['raw_receipt'], expected_url, stamp, 'raw_http_response_bytes', 200,
                    MAX_LIST_BYTES if n == 0 else MAX_DETAIL_BYTES)
        if n == 0:
            selected = selected_ids(raw)
            if len(receipts) != len(selected)+1:
                raise ValueError('104 selected batch incomplete')
        bodies.append(raw); stamps.append(stamp)
    if stamps != sorted(stamps) or max(stamps)-min(stamps) > 25:
        raise ValueError('104 batch time span invalid')
    parsed = parse_snapshot(bodies[0], dict(zip(selected,bodies[1:])), issuer=issuer, observed_at=max(stamps), now=now)
    today = datetime.fromtimestamp(now,TZ).date().isoformat()
    if any(p.deadline is not None and p.deadline <= today for p in parsed.postings):
        raise ValueError('104 deadline no longer current')
    return parsed


def make_batch(receipts, issuer, *, now=None):
    now = time.time() if now is None else now
    if not verified_issuer(issuer,now=now):
        raise ValueError('104 official issuer unavailable')
    _parse(receipts,issuer,now)
    stamp = receipts[0]['observed_at_epoch']; url = list_url(issuer)
    content = {'schema':SCHEMA, 'issuer':{k:issuer[k] for k in ('ticker','legal_name','official_short_name','official_ubn')},
               'receipts':deepcopy(receipts)}
    proof = archive_response(_dump(content), source_url=url, retrieved_at=stamp, http_status=None,
                             evidence_kind='private_acquisition_manifest', max_bytes=32768)
    if proof.get('status') != 'archived':
        raise ValueError('104 batch manifest unavailable')
    return {'schema':SCHEMA,'manifest':_pathless(proof)}


def replay_batch(batch, issuer, *, now=None):
    now = time.time() if now is None else now
    if not isinstance(batch, dict) or set(batch) != {'schema','manifest'} or batch['schema'] != SCHEMA:
        raise ValueError('104 original manifest missing')
    stamp = batch['manifest']['retrieved_at']
    if not _finite(stamp) or not 0 <= now-stamp < TTL:
        raise ValueError('104 batch expired')
    raw = _read(batch['manifest'], list_url(issuer), stamp, 'private_acquisition_manifest', None, 32768)
    content = json.loads(raw)
    if (not isinstance(content,dict) or set(content) != {'schema','issuer','receipts'} or content['schema'] != SCHEMA
            or content['issuer'] != {k:issuer[k] for k in ('ticker','legal_name','official_short_name','official_ubn')}
            or content['receipts'][0]['observed_at_epoch'] != stamp):
        raise ValueError('104 batch issuer invalid')
    parsed = _parse(content['receipts'],issuer,now)
    p = parsed.public_value()
    p.update(status='partial',native_originals_verified=True,fetched_at_epoch=stamp,
             source_record_archive=deepcopy(batch))
    return p


def verified_count(value, data, issuer, *, now=None):
    live_clock = now is None; now = time.time() if now is None else now
    try:
        if not valid_context(data,issuer) or not verified_issuer(issuer,now=now): return 0
        batch = value['source_record_archive']; saved = get_cache_json(cache_key(issuer))
        if not isinstance(saved,dict) or saved.get('error_kind') or saved.get('value') != batch: return 0
        stamp = batch['manifest']['retrieved_at']; start = saved.get('fetched_at_epoch'); end = saved.get('fresh_until_epoch')
        if (not _finite(start) or not _finite(end) or not stamp <= start <= stamp+25
                or not start <= now < end or not 0 < end-start <= TTL+1): return 0
        expected = replay_batch(batch,issuer,now=now)
        if _dump(value) != _dump(expected): return 0
        finished = time.time() if live_clock else now
        if (not verified_issuer(issuer,now=finished) or replay_batch(batch,issuer,now=finished) != expected
                or get_cache_json(cache_key(issuer)) != saved): return 0
        return expected['observed_sample_posting_count']
    except (ValueError,TypeError,KeyError,OSError,OverflowError,AttributeError,UnicodeError,RecursionError,IndexError):
        return 0
