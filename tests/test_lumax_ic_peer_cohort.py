"""Official IC-distribution membership supplies leads, never valuation peers."""
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
import base64
import gzip
import json
import time

import pytest

from test_official_thermal_peer_cohort import Stock

TARGET = '6192.TW'
TODAY = date(2026, 11, 3)
BASE = Path(__file__).parent / 'fixtures/source_acquisition/lumax_ic_20261103'
URLS = {
    'https://openapi.twse.com.tw/v1/opendata/t187ap03_L': 'listed.json.gz',
    'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O': 'otc.json.gz',
    'https://ic.tpex.org.tw/company_chain.php?stk_code=6192': 'issuer.html.gz',
    'https://ic.tpex.org.tw/introduce.php?ic=D000': 'segment.html.gz',
}
FIRST = ['2308.TW', '2347.TW', '2459.TW', '3010.TW', '3026.TW']


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import peers
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: datetime(2026, 11, 3, 6, tzinfo=timezone.utc).timestamp())
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    import thermal_peer_source_refresh
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(time.time(), tz)
    monkeypatch.setattr(thermal_peer_source_refresh, 'datetime', Clock)
    yield
    cache_store.reset_cache_store_for_tests()


def bodies():
    return {url: gzip.decompress((BASE / name).read_bytes()) for url, name in URLS.items()}


def boundary(monkeypatch, raw=None):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    raw = bodies() if raw is None else raw
    calls = []
    def download(self, url, diagnostic):
        calls.append(url)
        self.http_request_count += 1
        diagnostic['http_request_sent'] = True
        value = raw[url]
        return {'url': url, 'body_b64': base64.b64encode(value).decode(), 'sha256': sha256(value).hexdigest()}
    monkeypatch.setattr(IssuerNewsHttp, '_download', download)
    return calls


def test_normal_collector_recovers_current_official_ic_leads_without_comparability_upgrade(monkeypatch):
    from data_fetch.market_sources import peers
    from prompt_peer_projection import comparable_peer_rows
    from stock_snapshot.peers_valuation import _peer_comparison
    calls = boundary(monkeypatch)
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: pytest.fail('Exact profile must not download unrelated legacy candidates'))
    monkeypatch.setattr(peers.yf, 'Ticker', Stock)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(TARGET, '巨路', 'Industrials', 'Industrial Distribution', {})
    assert [r['ticker'] for r in result['peers']] == FIRST
    assert len(calls) == 4 and result['audit']['usable_count'] == 5
    assert result['audit']['candidate_attempt_count'] <= 10
    for row in result['peers']:
        assert row['comparison_scope'] == 'semiconductor_distribution_segment'
        assert row['business_comparability_verified_current'] is False
        assert row['membership_effective_date_verified'] is False
        assert row['numeric_comparability_verified'] is False
        assert row['asset_turnover'] == .8
        assert row['metric_sources']['asset_turnover']['observed_at'] == '2025-12-31'
    assert comparable_peer_rows(result['peers']) == []
    assert _peer_comparison({'ticker': TARGET, 'dynamic_peer_metrics': result['peers']})['summary']['peer_count'] == 0


def test_source_refresh_accepts_exact_lumax_context_without_any_other_fetch():
    from peer_source_refresh import validate_peer_refresh_context
    from fastapi import HTTPException
    data = {'ticker': TARGET, 'company_name': '巨路 / Lumax International Corp., Ltd.',
            'instrument_type': 'EQUITY', 'dynamic_peer_metrics': []}
    assert validate_peer_refresh_context(data, TARGET) == 'ic_distribution'
    for field, invalid in [('ticker', '6192.TWO'), ('company_name', '其他公司'), ('instrument_type', 'ETF')]:
        with pytest.raises(HTTPException) as e:
            validate_peer_refresh_context({**data, field: invalid}, TARGET)
        assert e.value.status_code == 400
    for identity in [{'ticker': '6193.TW'}, {'stock_id': False}, {'stock_id': 0},
                     {'stock_id': []}, {'official_name': '其他公司'}]:
        with pytest.raises(HTTPException):
            validate_peer_refresh_context({**data, 'company_identity': identity}, TARGET)


def test_complete_current_member_list_and_warm_receipts_are_replayed(monkeypatch):
    from data_fetch.market_sources import official_ic_distribution_peer_cohort as source
    calls = boundary(monkeypatch)
    result = source.get_candidates(TARGET, today=TODAY)
    assert result['status'] == 'success' and len(result['candidates']) >= 25
    assert [r['ticker'] for r in result['candidates'][:5]] == FIRST
    assert len(calls) == 4 and TARGET not in {r['ticker'] for r in result['candidates']}
    assert source.verified_candidates(result['candidates'][:5], TARGET, today=TODAY)
    warm = source.get_candidates(TARGET, today=TODAY)
    assert warm['http_request_count'] == 0 and warm['cache_hit'] is True
    assert warm['candidates'] == result['candidates'] and len(calls) == 4


@pytest.mark.parametrize('change', ['issuer_code', 'issuer_label', 'segment', 'target_absent', 'target_panel_disagreement',
                                  'target_ubn', 'target_old', 'target_future', 'ambiguous_market', 'small_master',
                                  'market_section', 'announced_count', 'oversize'])
def test_incorrect_source_cannot_supply_ic_membership(monkeypatch, change):
    from data_fetch.market_sources import official_ic_distribution_peer_cohort as source
    from bs4 import BeautifulSoup
    raw = bodies()
    if change == 'issuer_code': raw[source.ISSUER_URL] = raw[source.ISSUER_URL].replace(b'6192', b'6193')
    elif change == 'issuer_label': raw[source.ISSUER_URL] = raw[source.ISSUER_URL].replace('巨路'.encode(), '其他'.encode())
    elif change == 'segment': raw[source.SEGMENT_URL] = raw[source.SEGMENT_URL].replace(b'companyList_DB00', b'companyList_DX00')
    elif change == 'target_absent': raw[source.SEGMENT_URL] = raw[source.SEGMENT_URL].replace(b'stk_code=6192', b'stk_code=6193')
    elif change == 'target_panel_disagreement':
        s = BeautifulSoup(raw[source.SEGMENT_URL].decode(), 'html.parser')
        s.select('div#companyList_DB00')[0].find('a', href='company_basic.php?stk_code=6192').string = '其他'
        raw[source.SEGMENT_URL] = str(s).encode()
    elif change == 'market_section':
        s = BeautifulSoup(raw[source.SEGMENT_URL].decode(), 'html.parser')
        label = next(b for b in s.select('div#companyList_DB00')[0].find_all('b') if b.get_text().startswith('本國上市公司'))
        label.string = label.get_text().replace('上市', '上櫃')
        raw[source.SEGMENT_URL] = str(s).encode()
    elif change == 'announced_count':
        s = BeautifulSoup(raw[source.SEGMENT_URL].decode(), 'html.parser')
        label = next(b for b in s.select('div#companyList_DB00')[0].find_all('b') if b.get_text().startswith('本國上市公司'))
        label.string = label.get_text().replace('(16家)', '(17家)')
        raw[source.SEGMENT_URL] = str(s).encode()
    elif change == 'oversize': raw[source.SEGMENT_URL] += b' ' * 500001
    else:
        rows = json.loads(raw[source.MASTERS['.TW']]); target = next(r for r in rows if r['公司代號'] == '6192')
        if change == 'target_ubn': target['營利事業統一編號'] = '00000000'
        elif change == 'target_old': target['出表日期'] = '1151001'
        elif change == 'target_future': target['出表日期'] = '1151104'
        elif change == 'small_master': rows = [target]
        elif change == 'ambiguous_market':
            otc = json.loads(raw[source.MASTERS['.TWO']]); extra = dict(otc[0]); extra['SecuritiesCompanyCode'] = '6192'; otc.append(extra)
            raw[source.MASTERS['.TWO']] = json.dumps(otc, ensure_ascii=False).encode()
        raw[source.MASTERS['.TW']] = json.dumps(rows, ensure_ascii=False).encode()
    boundary(monkeypatch, raw)
    assert source.get_candidates(TARGET, today=TODAY)['candidates'] == []


@pytest.mark.parametrize('change', ['receipt', 'expired', 'digest', 'issuer', 'duplicate', 'upgrade', 'wrong_scope'])
def test_after_acquisition_tampering_cannot_supply_metrics(monkeypatch, change):
    from data_fetch.market_sources import official_ic_distribution_peer_cohort as source
    boundary(monkeypatch)
    rows = deepcopy(source.get_candidates(TARGET, today=TODAY)['candidates'][:5])
    if change == 'receipt': rows[0].pop(source.RECEIPT_KEY)
    elif change == 'expired': rows[0][source.RECEIPT_KEY][source.ISSUER_URL]['retrieved_at'] = time.time() - 1801
    elif change == 'digest': rows[0][source.RECEIPT_KEY][source.SEGMENT_URL]['raw_response_sha256'] = '0' * 64
    elif change == 'issuer': rows[0]['issuer_master_anchor']['ticker'] = '6193.TW'
    elif change == 'duplicate': rows[1] = deepcopy(rows[0])
    elif change == 'upgrade': rows[0]['business_comparability_verified_current'] = True
    elif change == 'wrong_scope': rows[0]['comparison_scope'] = 'whole_company'
    assert not source.verified_candidates(rows, TARGET, today=TODAY)


def test_unsupported_target_never_fetches_and_emerging_members_are_not_stock_candidates(monkeypatch):
    from data_fetch.market_sources import official_ic_distribution_peer_cohort as source
    calls = boundary(monkeypatch)
    assert source.get_candidates('6192.TWO', today=TODAY)['status'] == 'not_applicable'
    assert calls == []
    result = source.get_candidates(TARGET, today=TODAY)
    assert result['candidates'] and all(r['master_anchor']['source_url'] in source.MASTERS.values() for r in result['candidates'])
    assert all(r['ticker'].endswith(('.TW', '.TWO')) for r in result['candidates'])
    assert len(result['candidates']) <= 34  # 16listed +19OTC, less the target; emerging is excluded.


def test_expiry_while_downloading_metrics_cannot_return_source_rows(monkeypatch):
    from data_fetch.market_sources import peers, official_ic_distribution_peer_cohort as source
    boundary(monkeypatch)
    result = source.get_candidates(TARGET, today=TODAY)
    monkeypatch.setattr(peers, 'get_official_ic_candidates', lambda *a, **k: result)
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: [])
    class ExpiredStock(Stock):
        @property
        def info(self):
            result['candidates'][0][source.RECEIPT_KEY][source.ISSUER_URL]['retrieved_at'] = time.time() - 1801
            return super().info
    monkeypatch.setattr(peers.yf, 'Ticker', ExpiredStock)
    actual = peers.fetch_dynamic_peer_metrics_with_diagnostics(TARGET, '巨路', 'Industrials', 'Industrial Distribution', {})
    assert actual['peers'] == [] and actual['audit']['usable_count'] == 0
    assert actual['audit']['official_ic_candidate_status'] == 'originals_expired_or_unverified_after_metrics'


def test_unavailable_official_profile_does_not_download_known_unqualified_nearby_codes(monkeypatch):
    from data_fetch.market_sources import peers
    monkeypatch.setattr(peers, 'get_official_ic_candidates', lambda *a, **k: {
        'candidates': [], 'status': 'official_ic_originals_unavailable'})
    def forbidden(*a, **k): pytest.fail('No unrelated peer or legacy master download is allowed')
    monkeypatch.setattr(peers, 'load_peer_stock_master', forbidden)
    monkeypatch.setattr(peers.yf, 'Ticker', forbidden)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(TARGET, '巨路', 'Industrials', 'Industrial Distribution', {})
    assert result['peers'] == [] and result['audit']['candidate_attempt_count'] == 0
    assert result['audit']['usable_count'] == 0


def test_source_only_forced_refresh_is_rejected_before_provider_fetch(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest
    import data_fetch.service as service_module
    async def forbidden(*a, **k): pytest.fail('Forced refresh must not fetch')
    monkeypatch.setattr(service_module, 'fetch_correlated_provider', forbidden)
    data = {'ticker': TARGET, 'company_name': '巨路', 'instrument_type': 'EQUITY', 'dynamic_peer_metrics': []}
    with pytest.raises(HTTPException) as e:
        asyncio.run(StockDataService().fetch_source_async(
            FetchRequest.from_ticker(TARGET, force_refresh=True), 'dynamic_peer_metrics', context={'data': data}))
    assert e.value.status_code == 400


def test_public_source_refresh_keeps_original_analysis_and_all_other_sources(monkeypatch, tmp_path):
    import asyncio
    from data_fetch.market_sources import peers
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_analysis_evidence import capture_analysis_evidence
    from report_persistence import report_bundle_keys_for_filename
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_thermal_peer_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db, events
    init_db()
    boundary(monkeypatch)
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: [])
    monkeypatch.setattr(peers.yf, 'Ticker', Stock)
    storage = InMemoryStorage()
    _, original_keys, old = saved_report(storage)
    old['ticker'] = old['data']['ticker'] = TARGET
    old['company_name'] = old['data']['company_name'] = '巨路 / Lumax International Corp., Ltd.'
    old['data'].update(sector='Industrials', industry='Industrial Distribution')
    old['analysis_evidence'] = capture_analysis_evidence({'data': old['data']}, generated_at=old['generated_at'])
    filename = '6192_TW_v1_report_20261103_090000.html'
    keys = report_bundle_keys_for_filename(filename)
    for new, original in [(keys.html_key, original_keys.html_key), (keys.md_key, original_keys.md_key)]:
        storage.save_report(new, storage.get_report(original).content, content_type='text/plain')
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    def forbidden(*a, **k): pytest.fail('Source-only refresh must not fetch core data or models')
    request_flags = []
    class ObservedProvider(DynamicPeerMetricsProvider):
        def fetch(self, request, context=None):
            request_flags.append(request.options.force_refresh)
            return super().fetch(request, context)
    service = StockDataService(registry=ProviderRegistry([
        ObservedProvider(), CallableProvider('market_data', 'forbidden core', forbidden)]))
    response = asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
        refresh_service=service, source='dynamic_peer_metrics', return_refreshed_data=True))
    updated = json.loads(storage.get_report(keys.data_key).content)
    assert [r['ticker'] for r in updated['data']['dynamic_peer_metrics']] == FIRST
    for key in ['current_price', 'revenue_history', 'years', 'peer_discovery_results']:
        assert updated['data'][key] == old['data'][key]
    assert updated['analysis_evidence'] == old['analysis_evidence']
    assert next(a for a in updated['source_audit'] if a['source'] == 'market_data') == old['source_audit'][0]
    for gate in ['report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance']:
        assert updated[gate] == old[gate]
    assert storage.get_report(keys.html_key).content == b'<html>unchanged conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'unchanged conclusions'
    assert response['analysis_text_stale'] is True
    assert request_flags == [False]
    assert events() and all(r['source'] == 'dynamic_peer_metrics' for r in events())
