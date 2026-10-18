"""Published-year discovery and versioned normal PDF qualification for Macronix.

Legacy v1 receipts keep their exact replay path. New acquisitions bind every
URL to current published originals; a historical replay never becomes a GET.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import math
import time
from zoneinfo import ZoneInfo

from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError
from . import macronix_presentation_index as index
from .macronix_conference_transport import ConferenceHttp, MASTER_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

POLICY = 'macronix-original-presentation-v2'
PROJECTION_POLICY = 'macronix-presentation-role-v2'
PROOF_FIELDS = {'policy', 'identity', 'years', 'current_index', 'index', 'pdf', 'selected'}
NOTE = '公司官方季度簡報原件；完整保留原生頁面，角色只使用當份文件通過公司、期別、單位及欄列核對的頁面。整體內容仍partial，未推論圖表或未解字形；不是逐字稿、完整年度財報或獨立查證。'


def legacy():
    from . import macronix_conference
    return macronix_conference


def check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def receipt_keys(proof):
    return ('identity', 'years', 'current_index', 'index', 'pdf') if proof['current_index'] is not None else ('identity', 'years', 'index', 'pdf')


def fresh(proof, max_age):
    now = time.time()
    return all(type(proof[k]['retrieved_at']) in (int, float)
               and math.isfinite(proof[k]['retrieved_at'])
               and 0 <= now - proof[k]['retrieved_at'] < max_age
               and replay_expiry_valid(proof[k], max_age, now) for k in receipt_keys(proof))


def _native(raw, selected, deadline):
    check(deadline)
    old = legacy()
    if sha256(raw).hexdigest() == old.KNOWN_SHA:
        if any(selected[k] != old.QUALIFIED_SELECTED[k] for k in ('period_label', 'event_date', 'document_date')):
            raise ValueError('Known original cannot be assigned a different quarter')
        native = old.native_presentation(raw, old.QUALIFIED_SELECTED, deadline)
    else:
        native = old.extract_macronix_presentation_pages(raw, timeout_seconds=min(10., deadline-time.monotonic()))
    if native.get('content_sha256') != sha256(raw).hexdigest():
        raise ValueError('Normal PDF reader digest differs from original')
    check(deadline)
    return native


def document(native, selected, stamp):
    from .macronix_presentation_semantics import qualify_presentation
    qualified = qualify_presentation(native, selected)
    old = legacy()
    count = native['page_count']
    pages = qualified['role_page_allowlist']
    # Preserve the existing, exactly qualified Q2 tables. A new quarter never
    # inherits these page numbers, annual/half-year periods, or units.
    if native['content_sha256'] == old.KNOWN_SHA:
        if (count != old.PAGE_COUNT or tuple(sha256(p['text'].encode()).hexdigest() for p in native['pages']) != old.PAGE_TEXT_SHA256
                or selected['period_label'] != '2026Q2' or native['garbled_pages'] != [13,16,17,18,20]):
            raise ValueError('Legacy qualified pages changed')
        pages = list(old.ROLE_PAGES)
        qualified.update({k: deepcopy(old.DOCUMENT_METADATA[k]) for k in
                          ('content_periods','period_scope_caution','unit_scope_caution','visual_semantics_caution')})
    result = {
        'document_id': f"2337:{selected['event_date']}:{native['content_sha256'][:16]}",
        'ticker': '2337.TW', 'source': PROVIDER, 'source_type': 'issuer_official',
        'document_kind': 'presentation', 'projection_policy': PROJECTION_POLICY,
        'title': selected['title'], 'url': selected['pdf_url'], 'language': 'en',
        'event_date': selected['event_date'], 'event_date_basis': 'published_issuer_index_row_and_matching_PDF_cover',
        'event_status': 'published_past_material_not_independently_occurrence_verified',
        'event_time': None, 'event_timezone': 'Asia/Taipei', 'published_at': None,
        'material_file_date': selected['document_date'], 'presentation_cover_month': selected['cover_month'],
        'content_period': selected['period_label'], 'content_sha256': native['content_sha256'],
        'page_count': count, 'binary_complete': True,
        'text_extraction_complete': native['coverage_status'] == 'complete',
        'native_text_coverage': native['coverage_status'], 'coverage_status': 'partial',
        'full_content_coverage_verified': False, 'full_visual_content_verified': False,
        'financial_statement_complete': False, 'missing_text_pages': deepcopy(native['empty_pages']),
        'garbled_pages': deepcopy(native['garbled_pages']),
        'role_page_allowlist': pages, 'excluded_native_text_pages': [n for n in range(1,count+1) if n not in pages],
        'native_editorial_caution': NOTE,
        'index_reuse_caution': 'Selected from freshly acquired published years and complete quarterly index. Future/same-day events are excluded; missing latest past attachments remain unavailable.',
        'forward_looking_caution': 'Preserve the complete Safe Harbor Statement. Management projections are not achieved outcomes; no Q&A or transcript inferred.',
        'financial_scope_caution': 'Presentation summaries do not replace audited annual, TTM, FCF or five-year financial inputs.',
        'visual_semantics_caution': 'Only qualified whole pages are supplied to roles. Chart associations and unresolved glyphs remain excluded.',
        'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False,
        'response_reuse_policy': 'Always native public index and PDF; immutable archives are provenance, not success cache.',
        'publisher_notice': 'Copyright notices kept. Public download does not establish commercial redistribution rights.',
        'retrieved_at_epoch': stamp, 'pages': deepcopy(native['pages']), 'parser_version': native['parser_version'],
        'source_selection': deepcopy(selected),
    }
    result.update({k: deepcopy(qualified[k]) for k in ('content_periods','semantic_tables','period_scope_caution','unit_scope_caution')})
    if 'visual_semantics_caution' in qualified:
        result['visual_semantics_caution'] = qualified['visual_semantics_caution']
    return result


def context(native, selected, proof):
    return {'ticker': '2337.TW', 'date': selected['event_date'], 'period': selected['period_label'],
            'title': selected['title'], 'source': PROVIDER, 'source_url': index.index_url(selected['index_year']),
            'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'url': selected['pdf_url'], 'kind': 'presentation', 'language': 'en'}],
            'documents': [document(native, selected, proof['pdf']['retrieved_at'])],
            'coverage_status': 'partial', 'coverage_notes': [NOTE], 'selection_policy': selected['selection_policy'],
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'macronix_conference_receipt': deepcopy(proof)}


def rebuild(proof, *, deadline, max_age, as_of_epoch=None):
    check(deadline)
    if not isinstance(proof, dict) or set(proof) != PROOF_FIELDS or proof['policy'] != POLICY:
        raise ValueError('Dynamic original proof shape invalid')
    observed = time.time() if as_of_epoch is None else as_of_epoch
    year = datetime.fromtimestamp(observed, ZoneInfo('Asia/Taipei')).year
    selected = index.validate_selected_descriptor(proof['selected'])
    master_url = proof['identity']['source_url']
    legacy().parse_master(original_bytes(proof['identity'], master_url, max_age=max_age),
                          proof['identity']['retrieved_at'], master_url, as_of_epoch=observed)
    years = index.parse_years(original_bytes(proof['years'], index.YEARS_URL, max_age=max_age),
                              proof['years']['retrieved_at'], as_of_epoch=observed)
    previous = max((v for v in years if v < year), default=None)
    expected_year = year if year in years else previous
    if proof['current_index'] is not None:
        r = proof['current_index']
        if year not in years or index.select_presentation(
                original_bytes(r, index.index_url(year), max_age=max_age), r['retrieved_at'],
                index_year=year, as_of_epoch=observed) is not None:
            raise ValueError('Prior-year fallback cannot hide a current-year past event')
        expected_year = previous
    if selected['index_year'] != expected_year:
        raise ValueError('Selected year not bound to the published-year chain')
    raw_index = original_bytes(proof['index'], index.index_url(expected_year), max_age=max_age)
    index.verify_selected_in_index(selected, raw_index, proof['index']['retrieved_at'], as_of_epoch=observed)
    raw = original_bytes(proof['pdf'], selected['pdf_url'], max_age=max_age)
    stamp = proof['pdf']['retrieved_at']
    for key in receipt_keys(proof):
        r = proof[key]; at = r['retrieved_at']
        expiry = r.get('fresh_until_epoch')
        if not (type(at) in (int,float) and math.isfinite(at) and 0 < at <= stamp <= observed
                and type(expiry) in (int,float) and math.isfinite(expiry)
                and stamp < expiry <= at + RAW_TTL
                and stamp - at < RAW_TTL and replay_expiry_valid(r, max_age, stamp)):
            raise ValueError('Originals were not valid together at body acquisition')
    value = context(_native(raw, selected, deadline), selected, proof)
    # Re-read immutable receipts after parsing; expiry and delivery are still
    # inside the same deadline, including any shorter upstream max-age.
    for key in receipt_keys(proof):
        original_bytes(proof[key], proof[key]['source_url'], max_age=max_age)
    check(deadline)
    return value


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = time.monotonic()+10. if deadline is None else deadline
    try:
        if ticker != '2337.TW' or not isinstance(value, dict):
            return False
        proof = value['macronix_conference_receipt']
        rebuilt = rebuild(proof, deadline=deadline, max_age=max_age)
        matches = canonical(value) == canonical(rebuilt)
        check(deadline)
        return matches and fresh(proof, max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout':
            raise
        return False
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, OSError, EOFError, SourcePdfError):
        return False


def verify_for_projection(value):
    """Immutable historical content verification; no claim of current freshness."""
    try:
        proof = value['macronix_conference_receipt']
        stamp = proof['pdf']['retrieved_at']
        age = max(1801., time.time()-min(proof[k]['retrieved_at'] for k in receipt_keys(proof))+3600.)
        return canonical(value) == canonical(rebuild(proof, deadline=time.monotonic()+10., max_age=age, as_of_epoch=stamp))
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, OSError, EOFError, SourcePdfError, SourceResponseError):
        return False


def role_pages(value):
    try:
        native = {k: deepcopy(value[k]) for k in ('pages','parser_version','page_count','content_sha256','garbled_pages')}
        native.update(empty_pages=value['missing_text_pages'], coverage_status=value['native_text_coverage'])
        expected = document(native, value['source_selection'], value['retrieved_at_epoch'])
        if canonical(value) != canonical(expected):
            return []
        return deepcopy([p for p in value['pages'] if p['page_number'] in value['role_page_allowlist']])
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError):
        return []


def fetch_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not legacy().supports_macronix(ticker):
        return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline, force_refresh=force_refresh, use_cache=use_cache, dynamic=True)
    details = {'actual_provider': PROVIDER, 'macronix_presentation_workflow': True}
    try:
        raw, identity = http.get_receipt(MASTER_URL)
        legacy().parse_master(raw, identity['retrieved_at'], identity['source_url']); check(deadline)
        raw, years_receipt = http.get_receipt(index.YEARS_URL)
        years = index.parse_years(raw, years_receipt['retrieved_at']); check(deadline)
        year = datetime.fromtimestamp(time.time(), ZoneInfo('Asia/Taipei')).year
        target = year if year in years else max((v for v in years if v < year), default=None)
        if target is None:
            raise SourceResponseError('unavailable')
        raw, selected_index = http.get_receipt(http.authorize_index(target, years_receipt))
        selected = index.select_presentation(raw, selected_index['retrieved_at'], index_year=target)
        current_index = None
        if selected is None and target == year:
            previous = max((v for v in years if v < year), default=None)
            if previous is not None:
                current_index = selected_index
                raw, selected_index = http.get_receipt(http.authorize_index(previous, years_receipt, current_index=current_index))
                selected = index.select_presentation(raw, selected_index['retrieved_at'], index_year=previous)
        if selected is None:
            raise SourceResponseError('unavailable')
        check(deadline)
        raw, pdf = http.get_receipt(http.authorize_presentation(selected, selected_index))
        proof = dict(policy=POLICY, identity=identity, years=years_receipt, current_index=current_index,
                     index=selected_index, pdf=pdf, selected=selected)
        value = context(_native(raw, selected, deadline), selected, proof)
        if not verify_context(value, '2337.TW', deadline=deadline, max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        details.update(component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count, macronix_originals_verified=True,
                       coverage_status='qualified_partial_presentation', cache_hit=False, stale=False,
                       fetched_at_epoch=pdf['retrieved_at'], message=NOTE)
        if diagnostics is not None:
            diagnostics.update(details)
        result = deepcopy(value)
        check(deadline)
        if not fresh(proof, RAW_TTL):
            raise SourceResponseError('original_expired')
        check(deadline)
        return result
    except Exception as original:
        kind = 'timeout' if time.monotonic() >= deadline else getattr(original, 'error_kind', 'parse_error')
        exc = original if isinstance(original, SourceResponseError) and original.error_kind == kind else SourceResponseError(kind)
        for key in ('coverage_status','cache_hit','stale','fetched_at_epoch'):
            details.pop(key, None); exc.diagnostic.pop(key, None)
            if diagnostics is not None:
                diagnostics.pop(key, None)
        details.update(macronix_originals_verified=False, error_kind=kind, status='error',
                       component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:
            diagnostics.update(details)
        if exc is original:
            raise
        raise exc from original


def compatible_incoming(value, audits, *, deadline):
    """A fresh index chain may preserve only the same immutable historical body."""
    from report_source_refresh import _timestamp
    from conference_historical_evidence import number, _incomplete_pdf_transfer
    from .official_issuer_master import JSON_URL
    from .macronix_conference_transport import route_kind
    proof = value['macronix_conference_receipt']
    if proof.get('policy') not in {POLICY, legacy().POLICY}:
        raise ValueError('Unknown saved Macronix proof')
    saved = proof['selected']
    master_urls = {MASTER_URL, JSON_URL}
    # Identity fields of the actual material must agree across v1/v2. Full new
    # indices can legitimately add a future row without rewriting the old proof.
    material_fields = ('pdf_url', 'event_date', 'document_date', 'period_label')
    versions = {}
    for audit in audits:
        end = _timestamp(audit)
        if not number(end):
            raise ValueError('Incoming failure time invalid')
        this_year = datetime.fromtimestamp(end, ZoneInfo('Asia/Taipei')).year
        years = None; expected_year = None; selected_url = None; seen = {}
        for part in audit.get('component_statuses', []):
            check(deadline)
            url = part.get('url')
            kind = route_kind(url)
            if url not in master_urls and url != saved['pdf_url'] and kind not in {'years', 'index'}:
                raise ValueError('Incoming endpoint differs from qualified publication chain')
            receipt = part.get('original_receipt')
            if url == saved['pdf_url'] and selected_url is None:
                raise ValueError('Incoming PDF attempt lacks a verified matching selection')
            if receipt is None:
                if selected_url and _incomplete_pdf_transfer(part, proof, seen, selected_url, master_urls):
                    continue
                status = part.get('http_status')
                ambiguous = part.get('http_status_observed') is True and (type(status) is not int or not 100 <= status <= 599)
                if status == 200 or ambiguous or part.get('original_http_status_observed') is True:
                    raise ValueError('Incoming observed response requires its complete original')
                continue
            if not isinstance(receipt, dict):
                raise ValueError('Incoming original shape invalid')
            at = receipt.get('retrieved_at'); expiry = receipt.get('fresh_until_epoch')
            cached_master = (url in master_urls and part.get('cache_hit') is True
                and part.get('http_request_sent') is False and part.get('http_status') is None
                and part.get('original_http_status_observed') is True)
            native = (part.get('cache_hit') is False and part.get('http_request_sent') is True
                and type(part.get('http_status')) is int and part['http_status'] == 200)
            if (not number(at) or not number(expiry) or not 0 < at <= end < expiry <= at+RAW_TTL
                    or part.get('fetched_at_epoch') != at or type(part.get('cache_hit')) is not bool
                    or part['cache_hit'] != receipt.get('cache_hit') or not (cached_master or native)
                    or part.get('error_kind') not in (None, '') or receipt.get('source_url') != url):
                raise ValueError('Incoming receipt not bound to its original component')
            if url in versions and versions[url] != canonical(receipt):
                raise ValueError('Conflicting incoming original versions')
            versions[url] = seen[url] = canonical(receipt)
            raw = original_bytes(receipt, url, max_age=max(1801., time.time()-at+3600.))
            if url in master_urls:
                legacy().parse_master(raw, at, url, as_of_epoch=at)
            elif kind == 'years':
                years = index.parse_years(raw, at, as_of_epoch=at)
                expected_year = this_year if this_year in years else max((y for y in years if y < this_year), default=None)
            elif kind == 'index':
                if years is None:
                    # Exact historical v1 acquisition remains replayable; a
                    # dynamic URL cannot use this compatibility branch.
                    if proof['policy'] != legacy().POLICY or url != legacy().INDEX_URL:
                        raise ValueError('Dynamic index lacks its published-year original')
                    selected = legacy().select_presentation(raw, at, as_of_epoch=at)
                else:
                    if expected_year is None or url != index.index_url(expected_year):
                        raise ValueError('Incoming index is not the next published-year selection')
                    selected = index.select_presentation(raw, at, index_year=expected_year, as_of_epoch=at)
                    if selected is None and expected_year == this_year:
                        expected_year = max((y for y in years if y < this_year), default=None)
                        continue
                if selected is None or any(selected[k] != saved[k] for k in material_fields):
                    raise ValueError('Incoming index selects a different or unavailable material')
                selected_url = url
            else:
                raise ValueError('New complete material requires normal reconciliation')
            check(deadline)
    check(deadline)
    return True
