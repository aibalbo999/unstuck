"""Replay selected archived issuer-product cells; never renew provider freshness."""
from decimal import Decimal
from hashlib import sha256
import math
import re
import time
import zlib

from official_response_evidence import read_response
from source_pdf_reader import SourcePdfError
from search_provider_runtime import SourceResponseError
from . import tewc_conference as conference
from . import conference_issuer_master as master
from .tewc_conference_transport import MASTER_URL, INDEX_URL, contract, _redirect_headers

SCHEMA = 'tewc-segment-reference:v1'
TICKER = '1623.TW'
PAGE_SHA256 = '4f53cb81cc14b6c7f69b109894f44e7c6ad94ab4f2e1bf6a0690e85b3f875e13'
FILENAME = '大東電業法說會20260527-EN-finalV.3.pdf'
CHAIN_FIELDS = {'policy', 'identity', 'index', 'viewer', 'redirect', 'pdf', 'selected', 'file_info'}


def _original(receipt, url, *, redirect=False):
    """Validate immutable archived bytes, not the provider's live TTL contract."""
    limit, _ = contract(url)
    stamp = receipt.get('retrieved_at') if isinstance(receipt, dict) else None
    if (not isinstance(receipt, dict) or receipt.get('status') != 'archived'
            or receipt.get('source_url') != url
            or type(stamp) not in (int, float) or not math.isfinite(stamp)
            or not 0 < stamp <= time.time()
            or receipt.get('historical_point_in_time_verified') is not False
            or receipt.get('finality_guaranteed') is not False
            or type(receipt.get('http_status')) is not int
            or receipt['http_status'] != (303 if redirect else 200)
            or receipt.get('evidence_kind') != ('raw_http_response_headers' if redirect else 'raw_http_response_bytes')
            or receipt.get('http_status_observed') is not True
            or receipt.get('request_method') != 'GET'
            or receipt.get('response_complete') is not True
            or type(receipt.get('cache_hit')) is not bool
            or type(receipt.get('raw_response_bytes')) is not int
            or not 0 < receipt['raw_response_bytes'] <= limit):
        raise ValueError('archived_receipt_invalid')
    raw = read_response(receipt, max_bytes=limit)
    if len(raw) != receipt['raw_response_bytes']:
        raise ValueError('archived_size_invalid')
    return raw


def replay_segment_reference(reference, ticker):
    """Return source cells only after replaying their exact archived issuer chain.

    This opt-in reference is deliberately separate from ``verify_context``:
    historical cells remain inspectable after the original live TTL expires,
    without extending that TTL or creating an acquisition/success observation.
    Caller-supplied parsed facts and arbitrary file paths are never accepted.
    """
    unavailable = {'status': 'unverified', 'native_acquisition': False,
                   'freshness_status': 'not_revalidated', 'historical_pit_verified': False}
    try:
        if (ticker != TICKER or not isinstance(reference, dict)
                or set(reference) != {'schema', 'ticker', 'conference_receipt'}
                or reference.get('schema') != SCHEMA or reference.get('ticker') != TICKER):
            raise ValueError('reference_identity_invalid')
        proof = reference['conference_receipt']
        if (not isinstance(proof, dict) or set(proof) != CHAIN_FIELDS
                or proof.get('policy') != conference.POLICY
                or not master.valid_master_policy(proof['policy'], proof['identity'], conference.POLICY, conference.LEGACY_POLICY)):
            raise ValueError('conference_chain_invalid')
        identity = _original(proof['identity'], MASTER_URL)
        conference.parse_master(identity, proof['identity']['retrieved_at'], MASTER_URL,
                                as_of_epoch=proof['identity']['retrieved_at'])
        index = _original(proof['index'], INDEX_URL)
        selected = conference.select_presentation(index, proof['index']['retrieved_at'],
                                                 as_of_epoch=proof['index']['retrieved_at'])
        if selected != proof['selected'] or selected['event_date'] != '2026-05-27':
            raise ValueError('published_event_invalid')
        viewer = _original(proof['viewer'], selected['viewer_url'])
        info = conference.parse_viewer(viewer, selected)
        if info != proof['file_info'] or info['filename'] != FILENAME:
            raise ValueError('published_attachment_invalid')
        headers = _original(proof['redirect'], selected['uc_url'], redirect=True)
        if (proof['redirect'].get('response_body_bytes') != 0
                or type(proof['redirect'].get('response_body_bytes')) is not int
                or proof['redirect'].get('response_body_sha256') != sha256(b'').hexdigest()
                or proof['redirect'].get('redirect_location') != selected['pdf_url']):
            raise ValueError('published_redirect_invalid')
        _redirect_headers(headers, selected['pdf_url'])
        raw = _original(proof['pdf'], selected['pdf_url'])
        if sha256(raw).hexdigest() != conference.KNOWN_SHA:
            raise ValueError('document_not_qualified')
        parsed = conference.native_presentation(raw, selected, info, time.monotonic() + 10.)
        if parsed['page_count'] != 48:
            raise ValueError('document_pages_invalid')
        page = parsed['pages'][13]
        text = page['text']
        if (page['page_number'] != 14 or sha256(text.encode()).hexdigest() != PAGE_SHA256
                or '2023 2024 2025 2026Q1' not in text
                or 'Unit: NTD Thousand' not in text
                or 'Operating Model / Major Products' not in text):
            raise ValueError('product_table_not_qualified')
        row = re.search(r'Extra-high\nVoltage Cables\n([^\n]+)\nMedium-high', text)
        cells = row[1].split() if row else []
        if cells != ['1,597,044', '37.88', '2,220,099', '40.49', '2,703,969', '40.93', '1,022,772', '54.92']:
            raise ValueError('product_row_not_qualified')
        facts = {}
        for period, start, end, offset in (('2025', '2025-01-01', '2025-12-31', 4),
                                            ('2026Q1', '2026-01-01', '2026-03-31', 6)):
            facts[period] = {
                'period_start': start, 'period_end': end, 'currency': 'TWD',
                'net_operating_revenue_twd': int(cells[offset].replace(',', '')) * 1000,
                'company_revenue_proportion_pct': float(Decimal(cells[offset + 1])),
                'provenance': {'page_number': 14, 'printed_page_number': 11,
                    'source_row': 'Extra-high Voltage Cables', 'source_column': period,
                    'source_unit': 'NTD Thousand', 'source_cells': cells[offset:offset + 2],
                    'raw_response_sha256': conference.KNOWN_SHA, 'page_text_sha256': PAGE_SHA256},
            }
        return {'schema': SCHEMA, 'status': 'issuer_presentation_cells_verified', 'ticker': TICKER,
            'issuer_name': conference.LEGAL, 'report_scope': 'issuer_presentation_product',
            'audited': False, 'historical_pit_verified': False, 'native_acquisition': False,
            'freshness_status': 'not_revalidated', 'archive_evidence_replay': True,
            'document': {'filename': info['filename'], 'source_url': selected['pdf_url'],
                'publisher_index_url': INDEX_URL, 'event_date': selected['event_date'],
                'raw_response_sha256': conference.KNOWN_SHA, 'raw_response_bytes': len(raw),
                'parser_version': parsed['parser_version'], 'page_count': 48,
                'page_number': 14, 'printed_page_number': 11,
                'original_retrieved_at': proof['pdf']['retrieved_at']},
            'source_chain_sha256': {key: proof[key]['raw_response_sha256']
                                   for key in ('identity', 'index', 'viewer', 'redirect', 'pdf')},
            'facts': facts,
            'aggregate_discrepancy': {'period': '2025', 'sum_product_rows_thousand_twd': 6607044,
                'printed_total_thousand_twd': 6607040, 'difference_thousand_twd': 4,
                'source_corrected': False},
            'warnings': ['Original2025 product rows exceed printed total by4thousandTWD; selected source cells are preserved, not reconciled or recalculated.',
                'Issuer presentation product mix is not audited reporting scope, market share, ranking or bookings.',
                'Archived evidence is not a fresh provider observation or proof of first availability; live source TTL remains unchanged.']}
    except SourcePdfError as exc:
        return {**unavailable, 'reason': 'pdf_' + exc.reason}
    except SourceResponseError:
        return {**unavailable, 'reason': 'bounded_source_unavailable'}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, EOFError, OverflowError, zlib.error):
        return {**unavailable, 'reason': 'reference_or_original_unverified'}
