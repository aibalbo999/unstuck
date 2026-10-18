"""Read immutable conference originals at their recorded observation time.

This is not a provider, HTTP cache or current-acquisition verifier. Current
collectors keep their existing TTLs. A historical replay never updates an epoch.
"""
from copy import deepcopy
from hashlib import sha256
import importlib
import json
import math
import re
import time

PROFILES = {
    '1623.TW': ('tewc', 'tewc_conference_receipt', ('identity', 'index', 'viewer', 'redirect', 'pdf')),
    '2308.TW': ('delta', 'delta_transcript_receipt', ('identity', 'index', 'transcript')),
    '2367.TW': ('unitech', 'unitech_conference_receipt', ('identity', 'index', 'pdf')),
    '3324.TWO': ('auras', 'auras_conference_receipt', ('identity', 'index', 'pdf')),
    '4958.TW': ('zdt', 'zdt_conference_receipt', ('identity', 'index', 'pdf')),
    '3005.TW': ('getac', 'getac_conference_receipt', ('identity', 'bridge', 'index', 'pdf')),
    '1303.TW': ('npc', 'npc_conference_receipt', ('identity', 'index', 'pdf')),
    '3023.TW': ('sinbon', 'sinbon_conference_receipt', ('identity', 'index', 'pdf')),
    '2881.TW': ('fubon', 'fubon_conference_receipt', ('identity', 'index', 'pdf')),
    '6409.TW': ('voltronic', 'voltronic_conference_receipt', ('identity', 'index', 'pdf')),
    '2337.TW': ('macronix', 'macronix_conference_receipt', ('identity', 'index', 'pdf')),
    '2321.TW': ('tecom', 'tecom_conference_receipt', ('identity', 'index', 'pdf')),
    '6924.TW': ('eikei', 'eikei_conference_receipt', ('identity', 'index', 'pdf')),
    '8046.TW': ('nanyapcb', 'nanyapcb_conference_receipt', ('identity', 'index', 'pdf')),
    '3010.TW': ('wahlee', 'wahlee_conference_receipt', ('identity', 'index', 'pdf')),
    '2360.TW': ('chroma', 'chroma_conference_receipt', ('identity', 'index', 'pdf')),
    '2801.TW': ('chb', 'chb_qa_receipt', ('identity', 'index', 'pdf')),
    '6861.TW': ('innocare', 'innocare_conference_receipt', ('identity', 'index', 'pdf')),
    '1605.TW': ('walsin', 'walsin_conference_receipt', ('identity', 'index', 'pdf')),
}

# These collectors require an immutable acquisition manifest and have no
# legacy receipt policy. They replay at the recorded observation explicitly.
MANIFEST_PROFILES = frozenset({'2881.TW', '6409.TW', '2337.TW', '3023.TW', '2321.TW', '6924.TW', '8046.TW', '1303.TW', '2801.TW', '6861.TW', '1605.TW', '2360.TW', '4958.TW', '3010.TW', '3005.TW'})


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def profile(ticker):
    name, marker, receipt_keys = PROFILES[ticker]
    module = importlib.import_module('data_fetch.market_sources.' + name + '_conference')
    return module, marker, receipt_keys


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _check(deadline):
    if time.monotonic() >= deadline:
        raise ValueError('historical original replay exceeded deadline')


def _incomplete_pdf_transfer(part, proof, seen, index_url, master_urls):
    """A partial download is not a new original and cannot renew old evidence.

    Only the same requested PDF, after a verified matching master/index, may
    leave the saved historical body available. An incomplete index could hide
    a different publication and must still fail closed.
    """
    old = proof.get('pdf')
    if not isinstance(old, dict) or index_url not in seen or not (master_urls & seen.keys()):
        return False
    read = part.get('response_bytes_read')
    size = old.get('raw_response_bytes')
    url, method, body = old.get('source_url'), old.get('request_method'), old.get('request_body')
    if (part.get('url') != url or part.get('response_complete') is not False
            or type(part.get('http_status')) is not int or part['http_status'] != 200
            or part.get('http_status_observed') is not True
            or part.get('original_http_status_observed') is True
            or part.get('http_request_sent') is not True or part.get('cache_hit') is not False
            or part.get('error_kind') not in {'timeout', 'transport_error'}
            or type(read) is not int or type(size) is not int or not 0 <= read < size
            or type(part.get('response_bytes')) is not int or part['response_bytes'] != read
            or not re.fullmatch(r'[0-9a-f]{64}', str(part.get('response_sha256') or ''))
            or method not in {'GET', 'POST'} or part.get('request_method') != method
            or part.get('request_body') != body):
        return False
    if method == 'POST':
        if not isinstance(body, str) or not body:
            return False
        expected = sha256(('POST\n' + url + '\n' + body).encode('utf-8')).hexdigest()
        return part.get('request_sha256') == expected
    return body is None


def compatible_incoming_originals(value, ticker, audits, *, deadline):
    """New successful index/master reads may disprove the saved publication.

    A timeout before receiving an index says nothing new about the old event.
    Once an index was received, its actual bytes must select the same material;
    a missing or unparseable archive must not hide a newer publication.
    """
    from report_source_refresh import _timestamp
    if ticker == '2337.TW':
        from data_fetch.market_sources.macronix_dynamic_presentation import compatible_incoming
        return compatible_incoming(value, audits, deadline=deadline)
    module, marker, _ = profile(ticker)
    proof = value[marker]
    index_url = module.INDEX if ticker == '3324.TWO' else module.INDEX_URL
    master_urls = ({module.MASTER} if ticker == '3324.TWO' else
                   {module.MASTER_URL, module.JSON_URL} if ticker in MANIFEST_PROFILES else
                   {module.MASTER_URL, module.master_identity.JSON_URL})
    original_urls = {r['source_url'] for r in proof.values() if isinstance(r, dict) and 'source_url' in r}
    seen = {}
    for audit in audits:
        end = _timestamp(audit)
        if end is None:
            raise ValueError('incoming failure time invalid')
        for part in audit.get('component_statuses', []):
            _check(deadline)
            url = part.get('url')
            if url not in original_urls | master_urls:
                raise ValueError('incoming material or endpoint differs from saved publication')
            receipt = part.get('original_receipt')
            if receipt is None:
                if _incomplete_pdf_transfer(part, proof, seen, index_url, master_urls):
                    continue
                # Successful or ambiguous observed responses require evidence.
                # Keep explicit transient HTTP errors eligible for historical
                # replay, but do not let a missing status bypass partial proof.
                status = part.get('http_status')
                ambiguous_status = (part.get('http_status_observed') is True
                                    and (type(status) is not int or not 100 <= status <= 599))
                if (status == 200 or ambiguous_status
                        or part.get('original_http_status_observed') is True):
                    raise ValueError('incoming observed component has no original')
                continue
            at = receipt.get('retrieved_at') if isinstance(receipt, dict) else None
            expiry = receipt.get('fresh_until_epoch', at + 1800 if number(at) else None) if isinstance(receipt, dict) else None
            # A shared master cache hit has no HTTP status for this attempt.
            # Its recorded original is still required and verified below.
            cached_master = (url in master_urls and part.get('cache_hit') is True
                             and part.get('http_request_sent') is False
                             and part.get('http_status') is None
                             and part.get('original_http_status_observed') is True)
            native_response = (part.get('cache_hit') is False
                               and part.get('http_request_sent') is True
                               and type(part.get('http_status')) is int
                               and part['http_status'] == (302 if ticker == '3005.TW' and url == module.ROOT_URL else 200))
            if (not number(at) or not number(expiry) or not 0 < at <= end < expiry <= at + 1800
                    or part.get('fetched_at_epoch') != at or type(part.get('cache_hit')) is not bool
                    or part['cache_hit'] != receipt.get('cache_hit')
                    or type(part.get('http_request_sent')) is not bool
                    or not (cached_master or native_response) or part.get('error_kind') not in (None, '')
                    or receipt.get('source_url') != url):
                raise ValueError('incoming receipt not bound to its original component')
            if url in seen and seen[url] != canonical(receipt):
                raise ValueError('incoming original versions conflict')
            seen[url] = canonical(receipt)
            age = max(1801., time.time() - at + 3600.)
            raw = module.original_bytes(receipt, url, max_age=age)
            if url in master_urls:
                if ticker == '3324.TWO':
                    module.parse_master(raw, at, as_of_epoch=at)
                else:
                    module.parse_master(raw, at, url, as_of_epoch=at)
            elif url == index_url:
                selected = (module.select_transcript(raw, as_of_epoch=at) if ticker == '2308.TW' else
                            module.select_presentation(raw, at, as_of_epoch=at))
                if canonical(selected) != canonical(proof['selected']):
                    raise ValueError('incoming index selects a different publication')
            elif ticker == '3005.TW' and url == module.ROOT_URL:
                module.parse_bridge(raw)
            else:
                # A new complete document or intermediate Drive artifact is
                # new evidence requiring normal acquisition reconciliation.
                raise ValueError('incoming material original cannot be replaced by saved content')
            _check(deadline)
    return True


def replay_historical_conference(value, ticker, audit, *, deadline=None):
    """Rebuild the entire typed value from captured originals, never fetch.

    Raises for unsupported, incomplete or conflicting evidence. The caller must
    keep its incoming failure. A successful return proves historical content,
    not publication finality, occurrence, current availability or a fresh fetch.
    """
    from report_source_refresh import _timestamp
    deadline = time.monotonic() + 10. if deadline is None else deadline
    _check(deadline)
    module, marker, keys = profile(ticker)
    if (not isinstance(value, dict) or value.get('ticker') != ticker
            or value.get('source') != module.PROVIDER or not isinstance(audit, dict)
            or audit.get('source') != 'earnings_call' or audit.get('provider') != module.PROVIDER
            or audit.get('ticker') != ticker or audit.get('status') not in {'success', 'skipped_fresh_cache'}
            or type(audit.get('record_count')) is not int or audit['record_count'] != 1
            or audit.get('stale') is not False or type(audit.get('cache_hit')) is not bool
            or audit.get('error_kind') not in (None, '')):
        raise ValueError('unqualified original conference audit')
    proof = value[marker]
    dynamic_macronix = ticker == '2337.TW' and isinstance(proof, dict) and proof.get('policy') == 'macronix-original-presentation-v2'
    if dynamic_macronix:
        from data_fetch.market_sources import macronix_dynamic_presentation as dynamic
        keys = dynamic.receipt_keys(proof)
    expected_keys = dynamic.PROOF_FIELDS if dynamic_macronix else {'policy', 'selected', *keys}
    if ticker == '1623.TW':
        expected_keys.add('file_info')
    if not isinstance(proof, dict) or set(proof) != expected_keys:
        raise ValueError('historical receipt profile mismatch')
    if dynamic_macronix:
        policy_valid = proof['policy'] == dynamic.POLICY
    elif ticker == '3324.TWO' or ticker in MANIFEST_PROFILES:
        policy_valid = proof['policy'] == module.POLICY
    else:
        policy_valid = module.master_identity.valid_master_policy(
            proof['policy'], proof['identity'], module.POLICY, module.LEGACY_POLICY)
    if not policy_valid:
        raise ValueError('historical master receipt policy mismatch')
    stamp = _timestamp(audit)
    body_key = keys[-1]
    if (stamp is None or not number(value.get('fetched_at_epoch'))
            or value['fetched_at_epoch'] != stamp or proof[body_key].get('retrieved_at') != stamp):
        raise ValueError('original source observation is not bound to body')
    parts = audit.get('component_statuses')
    if not isinstance(parts, list) or any(not isinstance(part, dict) for part in parts):
        raise ValueError('captured component originals missing')
    epochs = []
    for key in keys:
        receipt = proof[key]
        at = receipt.get('retrieved_at')
        expiry = receipt.get('fresh_until_epoch', at + 1800 if number(at) else None)
        if (not number(at) or not number(expiry) or not 0 < at <= stamp < expiry <= at + 1800
                or stamp - at >= 1800):
            raise ValueError('originals were not valid together at recorded observation')
        matches = [part for part in parts if part.get('url') == receipt.get('source_url')
                   and canonical(part.get('original_receipt')) == canonical(receipt)]
        if (len(matches) != 1 or matches[0].get('fetched_at_epoch') != at
                or type(matches[0].get('cache_hit')) is not bool
                or matches[0]['cache_hit'] != receipt.get('cache_hit')
                or type(matches[0].get('http_request_sent')) is not bool):
            raise ValueError('original receipt differs from captured acquisition component')
        epochs.append(at)
    # Explicit historical age allowance; receipt readers still validate complete
    # archive bytes, URL, schema and manifest. No global or module clock changes.
    historical_age = max(1801., time.time() - min(epochs) + 3600.)
    if dynamic_macronix:
        selected = proof['selected']
        expected = dynamic.rebuild(proof, deadline=deadline, max_age=historical_age, as_of_epoch=stamp)
    else:
        master = proof['identity']
        master_url = master['source_url']
        raw_master = module.original_bytes(master, master_url, max_age=historical_age)
        if ticker == '3324.TWO':
            if master_url != module.MASTER:
                raise ValueError('historical TPEx master URL mismatch')
            module.parse_master(raw_master, master['retrieved_at'], as_of_epoch=stamp)
            selected = module.select_presentation(
                module.original_bytes(proof['index'], module.INDEX, max_age=historical_age),
                proof['index']['retrieved_at'], as_of_epoch=stamp)
            native, cover = module.native_presentation(
                module.original_bytes(proof['pdf'], selected['pdf_url'], max_age=historical_age), selected, deadline)
            expected = module._context(selected, native, cover, proof)
        else:
            module.parse_master(raw_master, master['retrieved_at'], master_url, as_of_epoch=stamp)
            if ticker == '3005.TW':
                module.parse_bridge(module.original_bytes(proof['bridge'], module.ROOT_URL, max_age=historical_age))
            raw_index = module.original_bytes(proof['index'], module.INDEX_URL, max_age=historical_age)
            if ticker == '2308.TW':
                selected = module.select_transcript(raw_index, as_of_epoch=stamp)
                if selected is None:
                    raise ValueError('recorded event has no published transcript')
                native = module.native_transcript(module.original_bytes(
                    proof['transcript'], selected['url'], max_age=historical_age), selected, deadline)
                expected = module._context(selected, native, proof)
            else:
                selected = module.select_presentation(raw_index, proof['index']['retrieved_at'], as_of_epoch=stamp)
                if ticker == '1623.TW':
                    info = module.parse_viewer(module.original_bytes(
                        proof['viewer'], selected['viewer_url'], max_age=historical_age), selected)
                    if canonical(info) != canonical(proof['file_info']):
                        raise ValueError('historical Drive file metadata mismatch')
                    if module.verify_redirect_receipt(proof['redirect'], selected['uc_url'],
                                                      selected['pdf_url'], max_age=historical_age) is not True:
                        raise ValueError('historical published redirect mismatch')
                    native = module.native_presentation(module.original_bytes(
                        proof['pdf'], selected['pdf_url'], max_age=historical_age), selected, info, deadline)
                    expected = module._context(selected, info, native, proof)
                else:
                    native = module.native_presentation(module.original_bytes(
                        proof['pdf'], module.PDF_URL, max_age=historical_age), selected, deadline)
                    expected = module._context(selected, native, proof)
    if canonical(selected) != canonical(proof['selected']) or canonical(value) != canonical(expected):
        raise ValueError('historical typed projection does not match complete originals')
    _check(deadline)
    result = {'policy': 'conference-original-time-replay.v1', 'ticker': ticker,
              'context_sha256': digest(value), 'audit_sha256': digest(audit),
              'original_observation_epoch': stamp,
              'original_receipts': {key: digest(proof[key]) for key in keys},
              'historical_point_in_time_verified': False, 'finality_guaranteed': False,
              'current_acquisition': False}
    result = deepcopy(result)
    _check(deadline)
    return result
