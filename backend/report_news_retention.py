"""Keep this report's replayable announcement bodies after a transient failure.

Historical evidence only: no acquisition, cache access, audit promotion or TTL
renewal. A fresh provider payload remains independent of each saved report.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
import re
import time
from urllib.parse import parse_qs, urlsplit
import zlib

from data_fetch.market_sources.twse_company_history import (
    INDEX_URL, PARSER_VERSION, PROVIDER, TAIPEI, _detail_fields, _roc_day, _text,
)
from data_fetch.market_sources.twse_announcement_progress import (
    MAX_BYTES, RECEIPT_KEYS, _detail_url, request_fingerprint,
)
from news_freshness_policy import apply_news_only_freshness
from news_record_utils import canonical_link, parse_news_datetime
from official_response_evidence import read_response

POLICY = 'report-local-native-announcement-retention.v1'
BUCKETS = ('recent_catalysts', 'additional_recent_catalysts', 'historical_catalysts',
           'unverified_catalysts', 'identity_rejected_catalysts')
TRANSIENT = frozenset({'timeout', 'transport_error', 'server_error', 'cooldown'})
MAX_RECORDS = 64
REPLAY_SECONDS = 2.


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _records(data):
    records = []
    for key in BUCKETS:
        rows = data.get(key, [])
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError('invalid news bucket')
        records.extend(rows)
    return records


def _identity(data, ticker):
    if not isinstance(data, dict) or data.get('ticker') != ticker:
        raise ValueError('different news ticker')
    identity = data.get('company_identity')
    if (not isinstance(identity, dict) or identity.get('ticker') != ticker
            or identity.get('stock_id') != ticker.split('.')[0]
            or data.get('stock_id') not in (None, '', ticker.split('.')[0])
            or identity.get('instrument_type') != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quote_type', 'quoteType'))):
        raise ValueError('different news instrument')
    company = identity.get('official_name')
    legal = identity.get('legal_name')
    forbidden = identity.get('forbidden_aliases', [])
    if (not isinstance(company, str) or not company.strip() or company != _text(company)
            or not isinstance(forbidden, list) or any(not isinstance(x, str) for x in forbidden)
            or any(_text(x).strip('*') == company.strip('*') for x in forbidden)
            or legal is not None and (not isinstance(legal, str) or not legal.strip())):
        raise ValueError('invalid news issuer')
    return company, legal


def _http_status(observation):
    status = observation.get('http_status')
    observed = observation.get('http_status_observed')
    if type(observed) is not bool or (status is None) != (observed is False):
        raise ValueError('unknown HTTP status observation')
    if status is not None and (type(status) is not int or not 200 <= status <= 599):
        raise ValueError('invalid HTTP status type')
    return status


def _request_identity(observation, ticker):
    url = observation.get('url')
    if observation.get('method') != 'GET':
        raise ValueError('unbound announcement request')
    if url == INDEX_URL:
        expected = request_fingerprint('GET', INDEX_URL, params={'code': ticker.split('.')[0]})
    elif _detail_url(url) and parse_qs(urlsplit(url).query)['COMPANY_ID'] == [ticker.split('.')[0]]:
        expected = request_fingerprint('GET', url)
    else:
        # Other indexes do not preserve enough request parameters in a failed
        # audit to bind their POST fingerprint independently to this issuer.
        raise ValueError('unbound announcement endpoint')
    if observation.get('request_fingerprint') != expected:
        raise ValueError('announcement request fingerprint mismatch')


def _transient_failure(incoming, ticker):
    audits = incoming.get('source_audit')
    if not isinstance(audits, list) or any(not isinstance(a, dict) for a in audits):
        return False
    component = [a for a in audits if a.get('source') == 'recent_catalysts' and a.get('provider') == PROVIDER]
    if len(component) != 1:
        return False
    audit = component[0]
    if (audit.get('ticker') != ticker or audit.get('parser_version') != PARSER_VERSION
            or audit.get('status') not in {'error', 'degraded_enrichment', 'unavailable'}
            or type(audit.get('record_count')) is not int or audit['record_count'] != 0
            or type(audit.get('detail_new_body_count', 0)) is not int or audit.get('detail_new_body_count', 0) != 0
            or audit.get('source_record_archive') or audit.get('body_cache_hit') is True
            or audit.get('error_kind') not in (None, '', *TRANSIENT)
            or audit.get('detail_stop_reason') not in (None, '', *TRANSIENT)
            or audit.get('http_status') is not None and (type(audit['http_status']) is not int
                                                        or audit['http_status'] not in (200, *range(500, 600)))):
        return False
    rejected = audit.get('rejected_reason_counts', {})
    if (not isinstance(rejected, dict) or set(rejected) - {'outside_window', 'detail_fetch_error', 'deadline_exhausted'}
            or any(type(n) is not int or n < 0 for n in rejected.values())):
        return False
    observations = audit.get('request_observations')
    details = audit.get('detail_observations', [])
    if (not isinstance(observations, list) or not observations or len(observations) > MAX_RECORDS + 5
            or not isinstance(details, list) or any(not isinstance(o, dict) for o in [*observations, *details])):
        return False
    if any(o.get('http_status') is not None and (type(o['http_status']) is not int
                                               or o['http_status'] not in (200, *range(500, 600)))
           or o.get('error_kind') not in (None, '', *TRANSIENT) for o in [*observations, *details]):
        return False
    if any(o.get('status') in {'success', 'cache_hit'} for o in details):
        return False
    if any(o.get('status') == 'success' and _detail_url(o.get('url')) for o in observations):
        return False
    failures = [o for o in observations if o.get('status') == 'error' and o.get('error_kind') in TRANSIENT]
    if not failures:
        return False
    for observation in failures:
        _request_identity(observation, ticker)
        kind, status = observation['error_kind'], _http_status(observation)
        if (type(observation.get('http_request_count')) is not int
                or observation['http_request_count'] not in (0, 1)
                or type(observation.get('http_request_sent')) is not bool
                or observation['http_request_sent'] != bool(observation['http_request_count'])
                or observation.get('response_complete') is not False
                or type(observation.get('response_bytes')) is not int or observation['response_bytes'] < 0
                or kind == 'server_error' and not (type(status) is int and 500 <= status <= 599)
                or status is not None and status >= 500 and kind != 'server_error'
                or kind == 'cooldown' and (status is not None or observation['http_request_sent'])):
            return False
    for observation in observations:
        _request_identity(observation, ticker)
        status = _http_status(observation)
        if observation.get('status') == 'success':
            if (status != 200 or observation.get('response_complete') is not True
                    or type(observation.get('http_request_count')) is not int or observation['http_request_count'] != 1
                    or observation.get('http_request_sent') is not True):
                return False
        elif observation not in failures:
            return False
        stamp = observation.get('response_retrieved_at_epoch')
        if stamp is not None and (not _number(stamp) or stamp > time.time()):
            return False
    for detail in details:
        matches = [o for o in failures if o.get('url') == detail.get('url')
                   and o.get('request_fingerprint') == detail.get('request_fingerprint')]
        if (len(matches) != 1 or detail.get('status') != 'error'
                or detail.get('error_kind') != matches[0]['error_kind']
                or detail.get('http_status') != matches[0].get('http_status')):
            return False
    if audit.get('detail_stop_reason') and audit['detail_stop_reason'] not in {o['error_kind'] for o in failures}:
        return False
    return True


def _qualified_origin(audit, ticker, origin_epoch):
    if (audit.get('ticker') != ticker or audit.get('source') != 'recent_catalysts' or audit.get('provider') != PROVIDER
            or audit.get('parser_version') != PARSER_VERSION or audit.get('index_url') != INDEX_URL
            or audit.get('status') != 'success' or audit.get('cache_hit') is not False
            or not isinstance(audit.get('fetch_id'), str) or not audit['fetch_id']
            or type(audit.get('record_count')) is not int or not 0 < audit['record_count'] <= MAX_RECORDS
            or not _number(audit.get('fetched_at_epoch')) or audit['fetched_at_epoch'] > origin_epoch):
        raise ValueError('unverified original acquisition')


def _origin(snapshot, ticker, filename, company, deadline):
    old = snapshot['data']
    if snapshot.get('ticker') != ticker:
        raise ValueError('different saved ticker')
    generated = parse_news_datetime(snapshot.get('snapshot_refreshed_at') or snapshot.get('generated_at'))
    if (generated is None or generated.timestamp() > time.time()
            or snapshot.get('refreshed_from_report') not in (None, '', filename)):
        raise ValueError('saved snapshot time missing')
    marker = old.get('news_retention')
    if marker is not None:
        if (not isinstance(marker, dict) or marker.get('policy') != POLICY or marker.get('ticker') != ticker
                or marker.get('report_filename') != filename or marker.get('new_acquisition') is not False
                or not _number(marker.get('original_snapshot_at_epoch'))
                or marker['original_snapshot_at_epoch'] > generated.timestamp()):
            raise ValueError('invalid retained news origin')
        audits, epochs = marker.get('original_audits'), marker.get('original_snapshot_at_epochs')
        if (not isinstance(audits, list) or not 0 < len(audits) <= MAX_RECORDS
                or any(not isinstance(a, dict) for a in audits)
                or marker.get('original_audit_sha256') != [_digest(a) for a in audits]
                or len(set(marker['original_audit_sha256'])) != len(audits)
                or not isinstance(epochs, list) or len(epochs) != len(audits)
                or any(not _number(e) or e > generated.timestamp() for e in epochs)
                or marker['original_snapshot_at_epoch'] != min(epochs)):
            raise ValueError('retained audit changed')
        origins = list(zip(audits, epochs))
        for audit, epoch in origins:
            _qualified_origin(audit, ticker, epoch)
        bindings = marker.get('records')
        if (not isinstance(bindings, list) or not 0 < len(bindings) <= MAX_RECORDS
                or any(not isinstance(b, dict) for b in bindings)
                or len({b.get('link') for b in bindings}) != len(bindings)):
            raise ValueError('retained record bindings changed')
        by_hash = {_digest(a): a for a in audits}
        # Source-only refresh can replace a record while keeping this marker.
        # Validate the prior original itself before consulting the newer audit;
        # never ignore a damaged marker merely because another audit is present.
        for binding in bindings:
            audit_hash = binding.get('original_audit_sha256')
            replayed = _replay(None, by_hash[audit_hash], ticker, company, deadline, url=binding.get('link'))
            if binding != {**replayed, 'original_audit_sha256': audit_hash}:
                raise ValueError('retained original binding mismatch')
    else:
        origins = []
    audits = []
    for parent in (snapshot, old):
        rows = parent.get('source_audit')
        if not isinstance(rows, list) or any(not isinstance(a, dict) for a in rows):
            raise ValueError('missing saved news audit')
        audits += [a for a in rows if a.get('source') == 'recent_catalysts' and a.get('provider') == PROVIDER]
    audits = list({_digest(a): a for a in audits}.values())
    if len(audits) != 1:
        raise ValueError('ambiguous current saved news audit')
    current = audits[0]
    if current.get('status') == 'success':
        _qualified_origin(current, ticker, generated.timestamp())
        if _digest(current) not in {_digest(a) for a, _ in origins}:
            origins.append((current, generated.timestamp()))
    elif current.get('source_record_archive') or current.get('record_count') != 0:
        raise ValueError('unqualified newer news acquisition')
    if not origins or len(origins) > MAX_RECORDS:
        raise ValueError('news origin limit')
    return origins


def _replay(record, audit, ticker, company, deadline, *, url=None):
    if time.monotonic() >= deadline:
        raise ValueError('news replay deadline')
    url = record.get('link') if record is not None else url
    if (not _detail_url(url) or record is not None and (record.get('source') != PROVIDER or record.get('ticker') != ticker
            or record.get('source_type') != 'official_disclosure' or record.get('content_truncated') is not False
            or record.get('content_coverage') != 'text_available')):
        raise ValueError('incomplete saved announcement')
    fingerprint = request_fingerprint('GET', url)
    archive = audit.get('source_record_archive')
    observations = audit.get('request_observations')
    if (not isinstance(archive, list) or len(archive) > MAX_RECORDS + 1
            or not isinstance(observations, list) or len(observations) > MAX_RECORDS + 5
            or any(not isinstance(o, dict) for o in [*archive, *observations])):
        raise ValueError('invalid news originals')
    entries = [entry for entry in archive if entry.get('url') == url]
    if len(entries) != 1:
        raise ValueError('announcement receipt missing')
    entry = entries[0]
    proof = entry.get('receipt')
    if (entry.get('request_fingerprint') != fingerprint or entry.get('method') != 'GET'
            or entry.get('cache_hit') is not False or not isinstance(proof, dict) or set(proof) != RECEIPT_KEYS
            or proof['status'] != 'archived' or proof['source_url'] != url
            or type(proof['http_status']) is not int or proof['http_status'] != 200
            or proof['evidence_kind'] != 'raw_http_response_bytes'
            or proof['historical_point_in_time_verified'] is not False or proof['finality_guaranteed'] is not False
            or type(proof['raw_response_bytes']) is not int or not 0 < proof['raw_response_bytes'] <= MAX_BYTES
            or not _number(proof['retrieved_at']) or proof['retrieved_at'] > audit['fetched_at_epoch']):
        raise ValueError('invalid announcement receipt')
    native = [o for o in observations if o.get('url') == url and o.get('request_fingerprint') == fingerprint]
    if len(native) != 1:
        raise ValueError('native observation missing')
    observation = native[0]
    if (observation.get('method') != 'GET' or observation.get('status') != 'success'
            or _http_status(observation) != 200
            or observation.get('response_complete') is not True or observation.get('http_request_sent') is not True
            or type(observation.get('http_request_count')) is not int or observation['http_request_count'] != 1
            or observation.get('response_sha256') != proof['raw_response_sha256']
            or type(observation.get('response_bytes')) is not int or observation['response_bytes'] != proof['raw_response_bytes']
            or not _number(observation.get('response_retrieved_at_epoch'))
            or observation['response_retrieved_at_epoch'] != proof['retrieved_at']
            or proof['retrieved_at'] > time.time()):
        raise ValueError('native observation mismatch')
    raw = read_response(proof, max_bytes=MAX_BYTES)
    if len(raw) != proof['raw_response_bytes']:
        raise ValueError('announcement bytes mismatch')
    header, fields = _detail_fields(raw.decode('utf-8'))
    published = _roc_day(fields.get('發言日期'))
    observed = datetime.fromisoformat(f"{published.date().isoformat()}T{fields.get('發言時間')}").replace(tzinfo=TAIPEI)
    params = parse_qs(urlsplit(url).query)
    title, body = _text(fields.get('主旨')), fields.get('說明', '').strip()
    text = f'{company}（{ticker.split(".")[0]}） {title}\n{body}'
    if (params['COMPANY_ID'] != [ticker.split('.')[0]] or params['SPOKE_DATE'] != [observed.strftime('%Y%m%d')]
            or params['SPOKE_TIME'][0].zfill(6) != observed.strftime('%H%M%S')
            or not re.search(rf'(?<!\d){re.escape(ticker.split(".")[0])}(?!\d)', header)
            or company not in header or '上市公司' not in header or observed.timestamp() > proof['retrieved_at']
            or not title or len(body) < 20 or len(text) > 12_000):
        raise ValueError('announcement parser replay mismatch')
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    if record is not None and (record.get('title') != title or record.get('text') != text or record.get('summary') != text[:1500]
            or record.get('content_sha256') != content_hash
            or parse_news_datetime(record.get('published_at')) != observed
            or any(parse_news_datetime(record[k]) != observed for k in ('date', 'published_date') if k in record)):
        raise ValueError('announcement parser replay mismatch')
    if time.monotonic() >= deadline:
        raise ValueError('news replay deadline')
    return {'link': url, 'content_sha256': content_hash,
            'original_fetched_at_epoch': proof['retrieved_at'], 'raw_response_sha256': proof['raw_response_sha256']}


def retain_verified_news(snapshot, incoming, ticker, *, report_filename):
    """Preserve only locally replayed original text, keeping incoming audits intact."""
    try:
        deadline = time.monotonic() + REPLAY_SECONDS
        if not isinstance(ticker, str) or not re.fullmatch(r'[1-9]\d{3,5}\.TW', ticker):
            return incoming
        old = snapshot['data']
        company, legal = _identity(old, ticker)
        current_company, current_legal = _identity(incoming, ticker)
        if company != current_company or legal and current_legal and legal != current_legal:
            return incoming
        if incoming.get('news_retention') is not None or not _transient_failure(incoming, ticker):
            return incoming
        previous, current = _records(old), _records(incoming)
        if any(r.get('source') == PROVIDER and r.get('text') for r in current):
            return incoming
        origins = _origin(snapshot, ticker, report_filename, company, deadline)
        originals = [r for r in previous if r.get('source') == PROVIDER]
        if not originals or len(originals) > MAX_RECORDS:
            return incoming
        bindings = []
        for record in originals:
            candidates = [a for a, _ in origins if any(e.get('url') == record.get('link')
                          for e in a.get('source_record_archive', []) if isinstance(e, dict))]
            if not candidates:
                return incoming
            newest = max(a['fetched_at_epoch'] for a in candidates)
            candidates = [a for a in candidates if a['fetched_at_epoch'] == newest]
            if len(candidates) != 1:
                return incoming
            # A newer audit mentioning this URL is authoritative. A mismatch
            # must fail closed, never fall back to an older version of the URL.
            audit = candidates[0]
            binding = _replay(record, audit, ticker, company, deadline)
            binding = {**binding, 'original_audit_sha256': _digest(audit)}
            marker = old.get('news_retention')
            if (marker is not None and _digest(audit) in marker['original_audit_sha256']
                    and binding not in marker['records']):
                return incoming
            bindings.append(binding)
        if len({r['link'] for r in bindings}) != len(bindings):
            return incoming
        incoming_links = {canonical_link(r.get('link') or r.get('url')) for r in current}
        pairs = [(r, b) for r, b in zip(originals, bindings) if canonical_link(r['link']) not in incoming_links]
        if not pairs:
            return incoming
        merged = deepcopy(incoming)
        apply_news_only_freshness(merged, records=[*deepcopy(current), *deepcopy([r for r, _ in pairs])], cutoff=time.time())
        # The unchanged selector may reject an issuer/date/role or deduplicate
        # a headline. A provenance marker may only describe retained content.
        kept = {r.get('link') for key in ('recent_catalysts', 'additional_recent_catalysts', 'historical_catalysts')
                for r in merged.get(key, [])}
        admitted = [b for _, b in pairs if b['link'] in kept]
        if not admitted or time.monotonic() >= deadline:
            return incoming
        used = {b['original_audit_sha256'] for b in admitted}
        origins = [(a, e) for a, e in origins if _digest(a) in used]
        merged['news_retention'] = {'policy': POLICY, 'ticker': ticker, 'report_filename': report_filename,
            'new_acquisition': False, 'original_snapshot_at_epoch': min(e for _, e in origins),
            'original_snapshot_at_epochs': [e for _, e in origins],
            'original_audits': [deepcopy(a) for a, _ in origins],
            'original_audit_sha256': [_digest(a) for a, _ in origins], 'records': admitted}
        return merged
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError,
            OSError, EOFError, RuntimeError, zlib.error, RecursionError):
        return incoming
