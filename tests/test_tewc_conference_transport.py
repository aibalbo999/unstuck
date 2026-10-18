"""Anonymous TEWC published Drive chain, original bytes and bounded cache behavior."""
from copy import deepcopy
import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import time

import pytest
from test_shared_provider_cache import memory_cache

MASTER = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX = 'https://tewc.com.tw/investor/shareholder/'
DRIVE_ID = '1Bwvj4q4IFxlah18p5F7HTPTQvPmMPEwq'
VIEWER = f'https://drive.google.com/file/d/{DRIVE_ID}/view?usp=sharing'
REDIRECT = f'https://drive.usercontent.google.com/uc?id={DRIVE_ID}&export=download'
PDF = f'https://drive.usercontent.google.com/download?id={DRIVE_ID}&export=download'
F = Path(__file__).parent / 'fixtures/source_acquisition'


@pytest.fixture
def native(monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as base
    if importlib.util.find_spec('data_fetch.market_sources.tewc_conference_transport'):
        from data_fetch.market_sources import tewc_conference_transport as transport
    else:
        # Exercise the existing public receipt behavior before the new route exists.
        from data_fetch.market_sources import tcfhc_conference_transport as transport
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in base.PROXY_ENV: monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(base, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(base, 'cooldown_state', lambda *a: None)
    monkeypatch.setattr(base, 'observe_http_response', lambda *a: None)
    monkeypatch.setattr(base, 'remember_failure', lambda *a: {})
    bodies = {url: gzip.decompress((F / ('tewc1623_viewer_metadata_fixture_20261018.gz' if kind == 'viewer' else f'tewc1623_{kind}_20261014.gz')).read_bytes())
              for url, kind in [(MASTER, 'master'), (INDEX, 'index'), (VIEWER, 'viewer'),
                                (REDIRECT, 'redirect'), (PDF, 'pdf')]}
    calls = []
    def response(argv, deadline, **kwargs):
        url = argv[-1]
        calls.append((argv, deadline, kwargs))
        status = 303 if url == REDIRECT else 200
        mime = 'text/csv' if url == MASTER else 'application/pdf' if url == PDF else 'text/html'
        raw = bodies[url]
        body = b'' if url == REDIRECT else raw
        return {'body': body, 'body_bytes_read': len(body), 'headers': raw if url == REDIRECT else
                f'HTTP/2 200\r\nContent-Type: {mime}\r\nContent-Length: {len(raw)}\r\n\r\n'.encode(),
                'metadata': json.dumps({'http_code': status, 'url_effective': url, 'num_redirects': 0, 'size_download':len(body), 'content_type':mime, 'method':'GET', 'proxy_used':0}).encode(),
                'process_started': True}, 0, None
    monkeypatch.setattr(base, 'collect_capped_process', response)
    from data_fetch.market_sources import gce_conference_transport as master_native
    monkeypatch.setattr(master_native, 'collect_capped_process', response)
    return transport, base, bodies, calls, response


def test_complete_native_large_pdf_retains_full_archive_and_twelve_second_cap(native):
    t, _, bodies, calls, _ = native
    http = t.ConferenceHttp(time.monotonic() + 20)
    raw, receipt = http.get_receipt(PDF)
    assert raw == bodies[PDF] and len(raw) == 16_076_336
    assert t.original_bytes(receipt, PDF) == raw
    assert receipt['http_status'] == 200 and receipt['evidence_kind'] == 'raw_http_response_bytes'
    argv, deadline, limits = calls[0]
    assert float(argv[argv.index('--max-time') + 1]) == 12
    assert float(argv[argv.index('--connect-timeout') + 1]) == 2
    assert limits['body_limit'] == 16 * 1024 * 1024
    assert http.http_request_count == 1


def test_complete_redirect_is_separate_native_303_header_receipt(native):
    t, _, bodies, calls, _ = native
    from official_response_evidence import read_response
    http = t.ConferenceHttp(time.monotonic() + 20)
    receipt = http.get_redirect_receipt(REDIRECT, PDF)
    assert receipt['http_status'] == 303 and receipt['evidence_kind'] == 'raw_http_response_headers'
    assert receipt['response_body_bytes'] == 0
    assert read_response(receipt) == bodies[REDIRECT]
    assert t.verify_redirect_receipt(receipt, REDIRECT, PDF)
    assert len(calls) == http.http_request_count == 1
    assert calls[0][0][-1] == REDIRECT
    with pytest.raises(ValueError): t.original_bytes(receipt, REDIRECT)


def test_complete_explicit_chain_warm_reuses_all_original_epochs(native):
    t, _, _, calls, _ = native
    def fetch(http):
        receipts = [http.get_receipt(url)[1] for url in (MASTER, INDEX, VIEWER)]
        receipts.append(http.get_redirect_receipt(REDIRECT, PDF))
        receipts.append(http.get_receipt(PDF)[1])
        return receipts
    cold = t.ConferenceHttp(time.monotonic() + 20); first = fetch(cold)
    warm = t.ConferenceHttp(time.monotonic() + 20); second = fetch(warm)
    assert cold.http_request_count == 5 and warm.http_request_count == 0
    assert [a['retrieved_at'] for a in first] == [a['retrieved_at'] for a in second]
    assert all(not a['cache_hit'] for a in first) and all(a['cache_hit'] for a in second)
    assert [a[0][-1] for a in calls] == [MASTER, INDEX, VIEWER, REDIRECT, PDF]
    for argv, _, _ in calls:
        assert argv[argv.index('--retry') + 1] == argv[argv.index('--max-redirs') + 1] == '0'
        assert not any(x in argv for x in ['--location', '-L', '--insecure', '-k', '--proxy', '--cookie', '--user'])


@pytest.mark.parametrize('url', [PDF + '#fragment', PDF + '&confirm=t', PDF + '&id=' + DRIVE_ID,
    PDF.replace('drive.usercontent.google.com', 'drive.usercontent.google.com.evil.example'),
    PDF.replace('https:', 'http:'), PDF.replace(DRIVE_ID, 'short'),
    VIEWER.replace('usp=sharing', 'usp=drive_link'), INDEX + '?x=1', MASTER + '#fragment',
    PDF.replace('/download?', ':443/download?'), PDF.replace('id=', '%69d=')])
def test_unknown_route_does_not_start_http(native, url):
    t, _, _, calls, _ = native
    assert t.route_kind(url) is None
    with pytest.raises(t.SourceResponseError): t.ConferenceHttp(time.monotonic() + 20).get_receipt(url)
    assert not calls


@pytest.mark.parametrize('change', ['foreign_location', 'other_id', 'duplicate_location', 'nonzero_length',
    'duplicate_length', 'truncated', 'two_blocks', 'folded_location', 'encoded', 'nonempty_body',
    'wrong_effective_url', 'redirect_followed', 'bool_redirect_count', 'rc_failure', 'timeout', 'status_200'])
def test_redirect_requires_complete_exact_single_native_response(native, monkeypatch, change):
    t, base, _, calls, respond = native
    def bad(argv, *args, **kwargs):
        parts, rc, error = respond(argv, *args, **kwargs)
        h = parts['headers']
        if change == 'foreign_location': h = h.replace(PDF.encode(), b'https://foreign.test/file.pdf')
        elif change == 'other_id': h = h.replace(DRIVE_ID.encode(), b'A' * 33)
        elif change == 'duplicate_location': h = h[:-2] + b'location: ' + PDF.encode() + b'\r\n\r\n'
        elif change == 'nonzero_length': h = h.replace(b'content-length: 0', b'content-length: 1')
        elif change == 'duplicate_length': h = h[:-2] + b'content-length: 0\r\n\r\n'
        elif change == 'truncated': h = h[:-2]
        elif change == 'two_blocks': h += h
        elif change == 'folded_location': h = h.replace(b'location:', b' location:')
        elif change == 'encoded': h = h[:-2] + b'content-encoding: gzip\r\n\r\n'
        elif change == 'nonempty_body': parts.update(body=b'x', body_bytes_read=1)
        elif change == 'wrong_effective_url':
            parts['metadata'] = json.dumps({'http_code': 303, 'url_effective': PDF, 'num_redirects': 0, 'size_download':len(body), 'content_type':mime, 'method':'GET', 'proxy_used':0}).encode()
        elif change in {'redirect_followed', 'bool_redirect_count'}:
            parts['metadata'] = json.dumps({'http_code': 303, 'url_effective': REDIRECT,
                'num_redirects': 1 if change == 'redirect_followed' else False}).encode()
        elif change == 'rc_failure': rc = 18
        elif change == 'timeout': rc, error = 28, 'timeout'
        elif change == 'status_200': h = h.replace(b'HTTP/2 303', b'HTTP/2 200')
        parts['headers'] = h
        return parts, rc, error
    monkeypatch.setattr(base, 'collect_capped_process', bad)
    with pytest.raises(t.SourceResponseError): t.ConferenceHttp(time.monotonic() + 20).get_redirect_receipt(REDIRECT, PDF)
    assert len(calls) == 1 and calls[0][0][-1] == REDIRECT


def test_mismatched_expected_download_rejected_before_redirect_request(native):
    t, _, _, calls, _ = native
    with pytest.raises(t.SourceResponseError):
        t.ConferenceHttp(time.monotonic() + 20).get_redirect_receipt(REDIRECT, PDF.replace(DRIVE_ID, 'A' * 33))
    assert not calls


@pytest.mark.parametrize('url', [REDIRECT, PDF])
def test_storage_failure_prevents_native_http(native, monkeypatch, url):
    t, _, _, calls, _ = native
    import cache_store
    def broken(*a, **k): raise OSError('storage unavailable')
    monkeypatch.setattr(cache_store, 'set_cache_json', broken)
    http = t.ConferenceHttp(time.monotonic() + 20)
    with pytest.raises(t.SourceResponseError) as exc:
        http.get_redirect_receipt(REDIRECT, PDF) if url == REDIRECT else http.get_receipt(url)
    assert exc.value.error_kind == 'guard_storage_unavailable'
    assert not calls and http.http_request_count == 0


def test_redirect_failure_cooldown_is_not_bypassed_or_extended_by_force(native, monkeypatch):
    t, base, _, calls, respond = native
    import cache_store
    def timeout(argv, *a, **k):
        parts, _, _ = respond(argv, *a, **k)
        return parts, 28, 'timeout'
    monkeypatch.setattr(base, 'collect_capped_process', timeout)
    with pytest.raises(t.SourceResponseError) as first:
        t.ConferenceHttp(time.monotonic() + 20).get_redirect_receipt(REDIRECT, PDF)
    assert first.value.error_kind == 'timeout'
    key = 'shared_provider:v1:' + sha256(('tewc-conference-raw:v1:' + REDIRECT).encode()).hexdigest()
    before = deepcopy(cache_store.get_cache_json(key))
    for options in [{}, {'force_refresh': True}, {'use_cache': False}]:
        with pytest.raises(t.SourceResponseError) as repeat:
            t.ConferenceHttp(time.monotonic() + 20, **options).get_redirect_receipt(REDIRECT, PDF)
        assert repeat.value.error_kind == 'cooldown'
        assert cache_store.get_cache_json(key) == before
    assert len(calls) == 1


@pytest.mark.parametrize('field,value', [('http_status', 200), ('http_status_observed', False),
    ('response_body_bytes', False), ('response_body_bytes', 1), ('response_body_sha256', '0' * 64),
    ('redirect_location', 'https://foreign.test/file'), ('evidence_kind', 'raw_http_response_bytes'),
    ('raw_response_bytes', True), ('raw_response_sha256', '0' * 64), ('cache_source', 'shared')])
def test_saved_redirect_receipt_cannot_be_promoted_or_rebound(native, field, value):
    t, _, _, _, _ = native
    receipt = t.ConferenceHttp(time.monotonic() + 20).get_redirect_receipt(REDIRECT, PDF)
    receipt[field] = value
    with pytest.raises((ValueError, OSError)): t.verify_redirect_receipt(receipt, REDIRECT, PDF)


@pytest.mark.parametrize('url', [REDIRECT, PDF])
def test_archive_failure_never_returns_success(native, monkeypatch, url):
    t, _, _, _, _ = native
    monkeypatch.setattr(t, 'archive_response', lambda *a, **k: {'status': 'unavailable'})
    http = t.ConferenceHttp(time.monotonic() + 20)
    with pytest.raises(t.SourceResponseError) as exc:
        http.get_redirect_receipt(REDIRECT, PDF) if url == REDIRECT else http.get_receipt(url)
    assert exc.value.error_kind == 'original_unverified' and http.http_request_count == 1


@pytest.mark.parametrize('url', [REDIRECT, PDF])
def test_deadline_expiring_during_original_readback_is_terminal(native, monkeypatch, url):
    t, _, _, _, _ = native
    now = [1000.]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])
    original = t.read_response
    def slow_read(*a, **k):
        raw = original(*a, **k); now[0] = 1020.; return raw
    monkeypatch.setattr(t, 'read_response', slow_read)
    http = t.ConferenceHttp(1020.)
    with pytest.raises(t.SourceResponseError) as exc:
        http.get_redirect_receipt(REDIRECT, PDF) if url == REDIRECT else http.get_receipt(url)
    assert exc.value.error_kind == 'timeout'


@pytest.mark.parametrize('url', [REDIRECT, VIEWER])
def test_warm_expiry_during_readback_is_not_freshened(native, monkeypatch, url):
    t, _, _, calls, _ = native
    now = [time.time()]
    monkeypatch.setattr(time, 'time', lambda: now[0])
    http = t.ConferenceHttp(time.monotonic() + 20)
    receipt = http.get_redirect_receipt(REDIRECT, PDF) if url == REDIRECT else http.get_receipt(url)[1]
    now[0] += 1799
    original = t.read_response
    def expiring(*a, **k):
        raw = original(*a, **k); now[0] += 2; return raw
    monkeypatch.setattr(t, 'read_response', expiring)
    warm = t.ConferenceHttp(time.monotonic() + 20)
    with pytest.raises(t.SourceResponseError):
        warm.get_redirect_receipt(REDIRECT, PDF) if url == REDIRECT else warm.get_receipt(url)
    assert len(calls) == 1 and warm.http_request_count == 0
    assert receipt['retrieved_at'] == now[0] - 1801


def test_handoff_rechecks_original_epoch_after_read_hook(native, monkeypatch):
    t, _, _, _, _ = native
    now = [time.time()]
    monkeypatch.setattr(time, 'time', lambda: now[0])
    reader = t.ConferenceHttp.read_original
    def expiring(self, *a, **k):
        raw = reader(self, *a, **k); now[0] += 1800; return raw
    monkeypatch.setattr(t.ConferenceHttp, 'read_original', expiring)
    with pytest.raises(t.SourceResponseError) as exc:
        t.ConferenceHttp(time.monotonic() + 20).get_receipt(VIEWER)
    assert exc.value.error_kind == 'original_expired'


def test_pdf_uses_remaining_workflow_budget_instead_of_new_twelve_seconds(native, monkeypatch):
    t, _, _, calls, _ = native
    monkeypatch.setattr(time, 'monotonic', lambda: 1000.)
    t.ConferenceHttp(1003.).get_receipt(PDF)
    argv, deadline, _ = calls[0]
    assert float(argv[argv.index('--max-time') + 1]) == 3. and deadline == 1003.
