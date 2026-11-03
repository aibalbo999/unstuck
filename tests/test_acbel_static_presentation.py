"""AcBel's published POST and exact static GET remain different identities."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import gzip
import io
import time

import pytest

from test_mops_presentation import harness
from test_mops_semantic_role_pages import semantic, D
from test_mops_material_transport import descriptor, wire, offline, PDF


def test_acbel_exact_static_get_preserves_original_and_existing_budgets(semantic, monkeypatch):
    from data_fetch.market_sources import mops_presentation as source
    from mops_body_cache import body_ready, originals_due
    original = source.download_published_material
    observed = []
    def download(spec, *, deadline, diagnostics, **options):
        observed.append((deepcopy(spec), deadline - time.monotonic(), options))
        return original(spec, deadline=deadline, diagnostics=diagnostics, **options)
    monkeypatch.setattr(source, 'download_published_material', download)
    diagnostic = {}
    value = source.fetch_presentation_context('6282.TW', diagnostics=diagnostic)
    proof = value['mops_material_receipt']
    assert proof['policy'] == source.STATIC_POLICY
    assert proof['selected']['method'] == 'POST'
    assert proof['selected']['url'].endswith('/server-java/FileDownLoad')
    assert proof['material_request']['method'] == proof['material']['request_method'] == 'GET'
    assert proof['material']['source_url'] == 'https://mopsov.twse.com.tw/nas/STR/628220260914E001.pdf'
    assert observed[0][2] == {'wire_budget_seconds': 15.}
    assert 0 < observed[0][1] <= 25
    assert value['documents'][0]['page_count'] == 16
    assert value['documents'][0]['content_period'] == '2026Q2'
    assert source.verify_context(value, '6282.TW') and body_ready('6282.TW')
    assert not originals_due(value, '6282.TW')
    observed.clear(); diagnostic = {}
    warm = source.fetch_presentation_context('6282.TW', diagnostics=diagnostic)
    assert not observed and diagnostic['cache_hit'] is True and diagnostic['http_request_count'] == 0
    assert warm['fetched_at_epoch'] == value['fetched_at_epoch']


@pytest.fixture
def previous_acbel(semantic, monkeypatch):
    from data_fetch.market_sources import mops_presentation as source
    # An isolated 2027 scenario retains the real 2026 index/PDF and updates
    # only the simulated master publication date, as the existing prior-year suite does.
    reader = csv.DictReader(io.StringIO(semantic[0]['master'].decode('utf-8-sig')))
    rows = list(reader); stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=reader.fieldnames); writer.writeheader()
    for row in rows:
        row['出表日期'] = '1160102'
    writer.writerows(rows); semantic[0]['master'] = stream.getvalue().encode()
    monkeypatch.setattr(time, 'time', lambda: datetime(2027, 1, 2, 12, tzinfo=ZoneInfo('Asia/Taipei')).timestamp())
    empty = gzip.decompress((D.parent/'mops-smallcap-entries/2338.TW.rejected-index.gz').read_bytes())
    original = source.download_conference_index
    def index(ticker, *, year, deadline, diagnostics):
        if year == 2027:
            old = semantic[0][ticker+':index']; semantic[0][ticker+':index'] = empty
            try:
                return original(ticker, year=year, deadline=deadline, diagnostics=diagnostics)
            finally:
                semantic[0][ticker+':index'] = old
        assert year == 2026
        return original(ticker, year=year, deadline=deadline, diagnostics=diagnostics)
    monkeypatch.setattr(source, 'download_conference_index', index)
    return source.fetch_presentation_context('6282.TW')


def test_prior_year_static_keeps_absence_proof_and_role_limits(previous_acbel):
    from data_fetch.market_sources import mops_presentation as source
    from conference_presentation_prompt import presentation_prompt_context
    from mops_body_cache import originals_due
    value = previous_acbel; proof = value['mops_material_receipt']
    assert proof['policy'] == 'mops-published-presentation-previous-year-static-get-v1'
    assert proof['absence_current_request']['year'] == 2027
    assert proof['index_request']['year'] == 2026
    assert proof['material_request']['method'] == 'GET' and proof['selected']['method'] == 'POST'
    assert source.verify_context(value, '6282.TW') and not originals_due(value, '6282.TW')
    doc = presentation_prompt_context(value, 3)['documents'][0]
    assert '前一年' in doc['period_scope_caution'] and '歷史' in doc['period_scope_caution']
    assert [p['page_number'] for p in doc['pages']] == [2, 10, 11, 13]


@pytest.mark.parametrize('damage', ['missing_absence', 'expired_absence', 'wire_method', 'wire_url', 'current_disguise'])
def test_prior_static_rejects_broken_period_or_wire_proofs(previous_acbel, damage):
    from data_fetch.market_sources import mops_presentation as source
    from mops_body_cache import publish_body_hint, originals_due
    value = deepcopy(previous_acbel); proof = value['mops_material_receipt']
    if damage == 'missing_absence':
        proof.pop('absence_current_index')
    elif damage == 'expired_absence':
        proof['absence_current_index']['fresh_until_epoch'] = time.time()-1
        assert not source._originals_current_at_handoff(proof)
        assert not publish_body_hint(value)
    elif damage == 'wire_method':
        proof['material']['request_method'] = 'POST'
    elif damage == 'wire_url':
        proof['material_request']['url'] += '?other=1'
    else:
        proof['policy'] = source.STATIC_POLICY
    assert not source.verify_context(value, '6282.TW')
    if damage in {'missing_absence', 'expired_absence'}:
        assert originals_due(value, '6282.TW')


def test_transport_admits_only_index_selected_issuer_static_url(monkeypatch, offline):
    import mops_material_transport as transport
    spec = descriptor('6282', filename='628220260914E001.pdf'); spec['language'] = 'en'
    selected = deepcopy(spec)
    derived = transport.static_material_request(spec)
    assert selected == spec and selected['method'] == 'POST'
    assert derived['url'] == 'https://mopsov.twse.com.tw/nas/STR/628220260914E001.pdf'
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: wire(
        meta_changes={'method': 'GET', 'url_effective': derived['url']}))
    diagnostic = {}
    assert transport.download_published_material(derived, deadline=time.monotonic()+25,
                                                diagnostics=diagnostic, wire_budget_seconds=15.) == PDF
    assert diagnostic['response_complete'] and diagnostic['request_method'] == 'GET'


def test_legacy_acbel_post_proof_remains_replayable(semantic):
    from data_fetch.market_sources import mops_presentation as source
    from mops_material_originals import get_original
    value = source.fetch_presentation_context('6282.TW')
    proof = deepcopy(value['mops_material_receipt']); selected = proof['selected']
    deadline = time.monotonic()+25
    (native, period), receipt = get_original(selected,
        lambda d: source.download_published_material(selected, deadline=deadline, diagnostics=d),
        deadline=deadline, owns=lambda: True, diagnostic={}, force_refresh=True,
        parser=lambda raw, r: source.native_material(raw, selected, deadline))
    proof.pop('material_request'); proof.update(policy=source.POLICY, material=receipt)
    legacy = source._context(selected, native, period, proof)
    assert legacy['materials'][0]['request_method'] == 'POST'
    assert source.verify_context(legacy, '6282.TW')


@pytest.mark.parametrize('change', ['wrong_issuer', 'query', 'filename', 'language'])
def test_static_allowance_never_becomes_an_unrestricted_get(offline, change):
    import mops_material_transport as transport
    from search_provider_runtime import SourceResponseError
    import hashlib
    spec = descriptor('6282', filename='628220260914E001.pdf'); spec['language'] = 'en'
    spec = transport.static_material_request(spec)
    if change == 'wrong_issuer':
        spec.update(ticker='2441.TW', symbol='2441', filename='244120260914E001.pdf',
                    url='https://mopsov.twse.com.tw/nas/STR/244120260914E001.pdf')
    elif change == 'query':
        spec['url'] += '?issuer=6282'
    elif change == 'filename':
        spec['filename'] = '202320260914E001.pdf'
    else:
        spec['language'] = 'zh'
    spec['request_sha256'] = hashlib.sha256(('GET\n'+spec['url']+'\n').encode()).hexdigest()
    with pytest.raises(SourceResponseError):
        transport.download_published_material(spec, deadline=time.monotonic()+25, diagnostics={})
    assert offline[0] == []
