"""Archived issuer product cells retain raw-chain, period and parser boundaries."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib

import pytest

FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'
STAMP = datetime(2026, 10, 14, 1, tzinfo=timezone.utc).timestamp()
FILE_ID = '1Bwvj4q4IFxlah18p5F7HTPTQvPmMPEwq'
URLS = {
    'identity': 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv',
    'index': 'https://tewc.com.tw/investor/shareholder/',
    'viewer': f'https://drive.google.com/file/d/{FILE_ID}/view?usp=sharing',
    'redirect': f'https://drive.usercontent.google.com/uc?id={FILE_ID}&export=download',
    'pdf': f'https://drive.usercontent.google.com/download?id={FILE_ID}&export=download',
}


@pytest.fixture
def reference():
    from official_response_evidence import archive_response
    from data_fetch.market_sources.tewc_conference import select_presentation, parse_viewer
    bodies = {key: gzip.decompress((FIXTURES / f'tewc1623_{"master" if key == "identity" else key}_20261014.gz').read_bytes()) for key in URLS}
    proof = {'policy': 'tewc-published-English-presentation-v2'}
    for key, url in URLS.items():
        receipt = archive_response(bodies[key], source_url=url, retrieved_at=STAMP,
            http_status=303 if key == 'redirect' else 200,
            evidence_kind='raw_http_response_headers' if key == 'redirect' else 'raw_http_response_bytes',
            max_bytes=16 * 1024 * 1024)
        receipt.update(http_status_observed=True, request_method='GET', response_complete=True, cache_hit=False)
        if key == 'identity':
            receipt['retrieval_policy'] = 'twse-whole-issuer-master-identity-v1'
        if key == 'redirect':
            receipt.update(response_body_bytes=0, response_body_sha256=hashlib.sha256(b'').hexdigest(), redirect_location=URLS['pdf'])
        proof[key] = receipt
    proof['selected'] = select_presentation(bodies['index'], STAMP, as_of_epoch=STAMP)
    proof['file_info'] = parse_viewer(bodies['viewer'], proof['selected'])
    return {'schema': 'tewc-segment-reference:v1', 'ticker': '1623.TW', 'conference_receipt': proof}


def test_replays_original_cells_with_explicit_archive_and_aggregate_limits(reference):
    from data_fetch.market_sources.tewc_segment_reference import replay_segment_reference
    before = deepcopy(reference)
    result = replay_segment_reference(reference, '1623.TW')
    assert result['status'] == 'issuer_presentation_cells_verified'
    assert result['facts']['2025']['net_operating_revenue_twd'] == 2703969000
    assert result['facts']['2025']['company_revenue_proportion_pct'] == 40.93
    assert result['facts']['2026Q1']['net_operating_revenue_twd'] == 1022772000
    assert result['facts']['2026Q1']['company_revenue_proportion_pct'] == 54.92
    assert result['facts']['2025']['provenance']['source_column'] == '2025'
    assert result['facts']['2026Q1']['period_end'] == '2026-03-31'
    assert result['document']['page_number'] == 14
    assert result['document']['printed_page_number'] == 11
    assert result['report_scope'] == 'issuer_presentation_product'
    assert not result['audited'] and not result['historical_pit_verified']
    assert result['freshness_status'] == 'not_revalidated'
    assert result['native_acquisition'] is False
    assert result['aggregate_discrepancy']['difference_thousand_twd'] == 4
    assert result['aggregate_discrepancy']['source_corrected'] is False
    assert reference == before


@pytest.mark.parametrize('change', ['ticker', 'missing_receipt', 'url', 'raw_hash', 'raw_path', 'filename', 'parsed_value', 'oversize', 'future_receipt'])
def test_reference_rejects_unbound_metadata_and_missing_original(reference, change):
    from data_fetch.market_sources.tewc_segment_reference import replay_segment_reference
    value = deepcopy(reference)
    proof = value['conference_receipt']
    if change == 'ticker': value['ticker'] = '1609.TW'
    elif change == 'missing_receipt': proof.pop('pdf')
    elif change == 'url': proof['pdf']['source_url'] = 'https://other.example/file.pdf'
    elif change == 'raw_hash': proof['pdf']['raw_response_sha256'] = '0' * 64
    elif change == 'raw_path': proof['pdf']['raw_response_path'] = '/tmp/caller-selected.pdf.gz'
    elif change == 'filename': proof['file_info']['filename'] = 'another-issuer.pdf'
    elif change == 'parsed_value': value['facts'] = {'2025': {'net_operating_revenue_twd': 999}}
    elif change == 'oversize': proof['pdf']['raw_response_bytes'] = 16 * 1024 * 1024 + 1
    else: proof['pdf']['retrieved_at'] = 999999999999
    assert replay_segment_reference(value, '1623.TW')['status'] == 'unverified'


@pytest.mark.parametrize('change', ['wrong_year', 'wrong_amount', 'wrong_unit', 'wrong_issuer', 'parser_warning', 'timeout'])
def test_strict_native_content_remains_required(reference, monkeypatch, change):
    from data_fetch.market_sources import tewc_segment_reference as source
    from source_pdf_reader import SourcePdfError
    if change in ('parser_warning', 'timeout'):
        def warning(*args, **kwargs): raise SourcePdfError(change)
        monkeypatch.setattr(source.conference, 'extract_pdf_pages', warning)
    else:
        original = source.conference.extract_pdf_pages
        def altered(*args, **kwargs):
            parsed = deepcopy(original(*args, **kwargs))
            if change == 'wrong_issuer': parsed['pages'][0]['text'] = parsed['pages'][0]['text'].replace('大東', '大亞')
            else:
                old, new = {'wrong_year': ('2023 2024 2025 2026Q1', '2023 2024 2024 2026Q1'),
                            'wrong_amount': ('2,703,969', '2,703,999'),
                            'wrong_unit': ('NTD Thousand', 'USD Thousand')}[change]
                parsed['pages'][13]['text'] = parsed['pages'][13]['text'].replace(old, new)
            return parsed
        monkeypatch.setattr(source.conference, 'extract_pdf_pages', altered)
    result = source.replay_segment_reference(reference, '1623.TW')
    assert result['status'] == 'unverified'
    if change == 'parser_warning': assert result['reason'] == 'pdf_parser_warning'
    if change == 'timeout': assert result['reason'] == 'bounded_source_unavailable'
