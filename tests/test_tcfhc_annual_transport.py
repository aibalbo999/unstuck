"""Native annual originals, exact publication bindings, no live provider access."""
import gzip
import importlib.util
import json
import time
from datetime import date
from pathlib import Path

import pytest
from test_shared_provider_cache import memory_cache

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/evidence/source-acquisition/20261014/remaining-four-next'
NOW = 1791936000.0  # 2026-10-14, keeps original roster replay deterministic.
MASTER = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
IR = 'https://www.tcfhc.com.tw/investors-relations/financial-info/financial-reports?sc_lang=en'


def bodies():
    raw = {MASTER: gzip.decompress((ROOT / 'tests/fixtures/source_acquisition/tcfhc5880_master_20261013.gz').read_bytes()),
           IR: (EVIDENCE / 'tcfhc-audited-financial-english-index.body').read_bytes()}
    for year in range(2021, 2026):
        receipt = json.loads((EVIDENCE / f'tcfhc-audited-{year}-english-pdf.receipt.json').read_text())
        raw[receipt['url']] = (EVIDENCE / f'tcfhc-audited-{year}-english-pdf.body').read_bytes()
    return raw


def module():
    from data_fetch.market_sources import tcfhc_annual_transport
    return tcfhc_annual_transport


@pytest.fixture
def native(monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as base
    monkeypatch.setattr(time, 'time', lambda: NOW)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for name in base.PROXY_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(base, 'proxy_url_for_request', lambda *args: None)
    monkeypatch.setattr(base, 'observe_http_response', lambda *args: None)
    calls = []
    payloads = bodies()
    def collect(argv, deadline, **kwargs):
        url = argv[-1]
        calls.append((argv, deadline, kwargs))
        raw = payloads[url]
        mime = 'text/csv' if url == MASTER else 'text/html' if url == IR else 'application/pdf'
        return {'body': raw, 'headers': f'HTTP/2 200\r\nContent-Type: {mime}\r\nContent-Length: {len(raw)}\r\n\r\n'.encode(),
                'metadata': json.dumps({'http_code': 200, 'url_effective': url, 'num_redirects': 0,
                                        'size_download': len(raw), 'method': 'GET', 'proxy_used': 0, 'content_type': mime}).encode(),
                'process_started': True, 'body_bytes_read': len(raw)}, 0, None
    monkeypatch.setattr(base, 'collect_capped_process', collect)
    from data_fetch.market_sources import gce_conference_transport as master_native
    monkeypatch.setattr(master_native, 'collect_capped_process', collect)
    monkeypatch.setattr(master_native, 'proxy_url_for_request', lambda *args: None)
    monkeypatch.setattr(master_native, 'observe_http_response', lambda *args: None)
    return base, payloads, calls, collect


def test_seven_official_originals_cold_then_warm_keep_original_epoch(native):
    # Before this source exists, exercise the real existing TCFHC adapter: its
    # exact QA route contract rejects the official annual index (behavior RED).
    if importlib.util.find_spec('data_fetch.market_sources.tcfhc_annual_transport'):
        cls = module().AnnualHttp
    else:
        from data_fetch.market_sources.tcfhc_conference_transport import ConferenceHttp as cls
    first = cls(time.monotonic() + 45)
    request = getattr(first, 'request', first.get_receipt)
    results = {url: request(url) for url in native[1]}
    assert len(first.components) == first.http_request_count == 7
    assert all(receipt['cache_hit'] is False and receipt['response_complete'] is True
               and receipt['http_status'] == 200 and receipt['request_method'] == 'GET'
               for raw, receipt in results.values())
    second = cls(time.monotonic() + 45)
    repeat = getattr(second, 'request', second.get_receipt)
    for url, (raw, receipt) in results.items():
        same, warm = repeat(url)
        assert same == raw and warm['retrieved_at'] == receipt['retrieved_at']
        assert warm['cache_hit'] is True
    assert second.http_request_count == 0 and len(native[2]) == 7
    assert all(c['http_request_sent'] is False and c['cache_hit'] is True for c in second.components)


def test_index_binds_all_five_exact_published_urls_and_master_identity():
    t = module(); raw = bodies()
    assert t.YEARS == (2021, 2022, 2023, 2024, 2025)
    parsed = t.parse_index(raw[IR])
    assert list(parsed) == list(t.YEARS)
    for year, url in parsed.items():
        receipt = json.loads((EVIDENCE / f'tcfhc-audited-{year}-english-pdf.receipt.json').read_text())
        assert url == receipt['url']
    identity = t.parse_master(raw[MASTER], today=date(2026, 10, 14))
    assert (identity['ticker'], identity['legal_name'], identity['official_ubn'], identity['english_abbreviation'],
            identity['registered_website'], identity['master_as_of']) == (
                '5880.TW', '合作金庫金融控股股份有限公司', '53021433', 'TCFHC', 'www.tcfhc.com.tw', '2026-10-13')
    from data_fetch.market_sources.tcfhc_conference_transport import RECEIPT_FIELDS
    assert t.RECEIPT_FIELDS == RECEIPT_FIELDS


@pytest.mark.parametrize('before,after', [
    ('合作金庫金融控股股份有限公司', '合作金庫商業銀行股份有限公司'), ('合庫金', '合庫銀'),
    ('53021433', '53021434'), ('TCFHC', 'TCBANK'), ('www.tcfhc.com.tw', 'www.tcfhc.com.tw.evil.invalid'),
])
def test_master_rejects_wrong_publisher(before, after):
    raw = bodies()[MASTER].decode('utf-8-sig')
    assert before in raw
    with pytest.raises(ValueError):
        module().parse_master(raw.replace(before, after).encode(), today=date(2026, 10, 14))


@pytest.mark.parametrize('change', ['small', 'duplicate_code', 'duplicate_header', 'short_row', 'extra_field',
                                   'unequal_dates', 'bad_csv', 'html_refusal'])
def test_master_rejects_incomplete_or_ambiguous_csv(change):
    import csv, io
    rows = list(csv.reader(io.StringIO(bodies()[MASTER].decode('utf-8-sig'))))
    if change == 'small': rows = [rows[0], next(r for r in rows[1:] if r[1] == '5880')]
    if change == 'duplicate_code': rows.append(rows[2])
    if change == 'duplicate_header': rows[0][0] = rows[0][1]
    if change == 'short_row': rows[-1] = rows[-1][:-1]
    if change == 'extra_field': rows[-1].append('incomplete')
    if change == 'unequal_dates': rows[-1][0] = '1151012'
    out = io.StringIO(); csv.writer(out).writerows(rows); raw = out.getvalue().encode()
    if change == 'bad_csv': raw += b'"unfinished'
    if change == 'html_refusal': raw = b'<html>Access denied</html>'
    with pytest.raises(ValueError): module().parse_master(raw, today=date(2026, 10, 14))


@pytest.mark.parametrize('today', [date(2026, 10, 12), date(2026, 10, 21), '2026-10-14', True])
def test_master_requires_valid_historical_replay_date(today):
    with pytest.raises(ValueError): module().parse_master(bodies()[MASTER], today=today)


@pytest.mark.parametrize('change', ['duplicate_block', 'duplicate_link', 'second_hash', 'individual', 'quarter',
                                   'wrong_year', 'fragment', 'wrong_host', 'wrong_lang', 'duplicate_query',
                                   'extra_query', 'missing_hash', 'publisher', 'language', 'truncated', 'contradictory_title'])
def test_index_rejects_ambiguous_or_unpublished_annual_binding(change):
    from bs4 import BeautifulSoup
    import copy
    t = module(); soup = BeautifulSoup(bodies()[IR], 'html.parser')
    block = next(b for b in soup.select('div.l-textBlock') if '2025 Financial Statements' in b.select_one('div.o-textTitle').get_text())
    row = block.select('li.c-list__item')[0]; anchor = row.select_one('a[href]')
    if change == 'duplicate_block': block.insert_after(copy.deepcopy(block))
    if change == 'duplicate_link': anchor.insert_after(copy.deepcopy(anchor))
    if change == 'second_hash':
        extra = copy.deepcopy(anchor); extra['href'] = extra['href'][:-1] + ('0' if extra['href'][-1] != '0' else '1'); block.append(extra)
    if change == 'individual': row.select_one('div.c-list__title').string = '2025 Individual Financial Statements'
    if change == 'quarter': row.select_one('div.c-list__title').string = '2025 3rd Consolidated Financial Statements'
    if change == 'wrong_year': anchor['href'] = anchor['href'].replace('/2025-', '/2024-')
    if change == 'fragment': anchor['href'] += '#fragment'
    if change == 'wrong_host': anchor['href'] = 'https://www.tcfhc.com.tw.evil.invalid' + anchor['href']
    if change == 'wrong_lang': anchor['href'] = anchor['href'].replace('sc_lang=en', 'sc_lang=zh-tw')
    if change == 'duplicate_query': anchor['href'] += '&sc_lang=en'
    if change == 'extra_query': anchor['href'] += '&download=1'
    if change == 'missing_hash': anchor['href'] = anchor['href'].split('&hash=')[0]
    if change == 'contradictory_title': anchor['title'] += ' Q3 Individual Statements'
    if change == 'publisher': soup.select_one('.c-terms__copyright').string = 'Different publisher'
    if change == 'language': soup.html['lang'] = 'zh-tw'
    raw = str(soup).encode()
    if change == 'truncated': raw = raw[:raw.rindex(b'</html>')]
    with pytest.raises((ValueError, t.SourceResponseError)): t.parse_index(raw)


@pytest.mark.parametrize('change', ['http', 'extra', 'duplicate', 'fragment', 'quarter', 'individual', 'host', 'path', 'year'])
def test_route_rejects_unknown_scope_before_http(native, change):
    t = module(); url = next(u for u in native[1] if '2025-consolidated' in u)
    if change == 'http': url = url.replace('https:', 'http:')
    if change == 'extra': url += '&extra=1'
    if change == 'duplicate': url += '&hash=' + 'A' * 32
    if change == 'fragment': url += '#fragment'
    if change == 'quarter': url = url.replace('/2025-', '/2025-4th-')
    if change == 'individual': url = url.replace('consolidated', 'individual')
    if change == 'host': url = url.replace('www.tcfhc.com.tw', 'www.tcfhc.com.tw.evil.invalid')
    if change == 'path': url = url.replace('/financial-info/', '/financial-info/../financial-info/')
    if change == 'year': url = url.replace('2025-', '2026-')
    with pytest.raises(t.SourceResponseError): t.AnnualHttp().request(url)
    assert not native[2]


def test_pdf_requires_this_http_instances_verified_index(native):
    t = module(); url = next(u for u in native[1] if '2025-consolidated' in u)
    client = t.AnnualHttp()
    with pytest.raises(t.SourceResponseError): client.request(url)
    assert not native[2]
    client.request(IR)
    different_hash = url[:-1] + ('0' if url[-1] != '0' else '1')
    with pytest.raises(t.SourceResponseError): client.request(different_hash)
    assert len(native[2]) == 1
    assert client.request(url)[0] == native[1][url]


@pytest.mark.parametrize('kind', ['html_pdf', 'incomplete_pdf', 'partial_native', 'wrong_mime', 'redirect', 'wrong_effective_url'])
def test_native_rejects_http_200_nonoriginal_and_partial_body(native, monkeypatch, kind):
    t = module(); base, payloads, calls, collect = native
    url = next(u for u in payloads if '2025-consolidated' in u)
    client = t.AnnualHttp(); client.request(IR)
    def broken(argv, *args, **kwargs):
        parts, rc, err = collect(argv, *args, **kwargs)
        if kind == 'html_pdf': parts['body'] = b'<html>Access denied</html>'
        if kind == 'incomplete_pdf': parts['body'] = parts['body'][:-200]
        if kind == 'partial_native': return parts, 18, None
        if kind == 'wrong_mime': parts['headers'] = b'HTTP/2 200\r\nContent-Type: text/html\r\n\r\n'
        if kind in {'redirect', 'wrong_effective_url'}:
            meta = json.loads(parts['metadata']); meta['num_redirects' if kind == 'redirect' else 'url_effective'] = 1 if kind == 'redirect' else 'https://evil.invalid/file.pdf'; parts['metadata'] = json.dumps(meta).encode()
        return parts, rc, err
    monkeypatch.setattr(base, 'collect_capped_process', broken)
    with pytest.raises(t.SourceResponseError): client.request(url)
    assert client.components[-1]['status'] == 'unavailable'
    assert len(calls) == 2
    with pytest.raises(t.SourceResponseError): client.request(url)
    assert len(calls) == 2


@pytest.mark.parametrize('status', [403, 429, 503])
def test_actual_status_and_cooldown_survive_force_and_no_cache(native, monkeypatch, status):
    t = module(); base, payloads, calls, collect = native
    def refused(argv, *args, **kwargs):
        parts, rc, err = collect(argv, *args, **kwargs)
        parts['headers'] = f'HTTP/2 {status}\r\nContent-Type: text/html\r\n\r\n'.encode()
        return parts, rc, err
    monkeypatch.setattr(base, 'collect_capped_process', refused)
    first = t.AnnualHttp()
    with pytest.raises(t.SourceResponseError): first.request(IR)
    assert first.components[-1]['http_status'] == status
    assert first.components[-1]['request_method'] == 'GET'
    assert first.components[-1]['response_complete'] is False
    for options in ({}, {'force_refresh': True}, {'use_cache': False}):
        with pytest.raises(t.SourceResponseError): t.AnnualHttp(**options).request(IR)
    assert len(calls) == 1


@pytest.mark.parametrize('guard', ['raw_error', 'admission', 'host', 'read_failure', 'write_failure', 'proxy'])
def test_existing_failure_guards_prevent_native_http(native, monkeypatch, guard):
    from hashlib import sha256
    import cache_store
    from search_provider_runtime import scope_key
    from data_fetch.market_sources.tcfhc_conference_transport import ConferenceHttp
    t = module(); base, _, calls, _ = native
    def unavailable(*args, **kwargs): raise OSError('guard unavailable')
    if guard == 'raw_error':
        key = 'shared_provider:v1:' + sha256((ConferenceHttp.raw_cache_prefix + IR).encode()).hexdigest()
        cache_store.set_cache_json(key, {'error_kind': 'timeout', 'retry_after_epoch': NOW + 120}, ttl_seconds=120)
    if guard == 'admission': cache_store.set_cache_json(ConferenceHttp._admission_key(IR), {'retry_at': NOW + 120}, ttl_seconds=120)
    if guard == 'host': cache_store.set_cache_json(scope_key(base.PROVIDER, endpoint='www.tcfhc.com.tw'), {'retry_at': NOW + 120}, ttl_seconds=120)
    if guard == 'read_failure': monkeypatch.setattr(cache_store, 'get_cache_json', unavailable)
    if guard == 'write_failure': monkeypatch.setattr(cache_store, 'set_cache_json', unavailable)
    if guard == 'proxy': monkeypatch.setenv('HTTPS_PROXY', 'http://127.0.0.1:9')
    with pytest.raises(t.SourceResponseError): t.AnnualHttp(force_refresh=True).request(IR)
    assert not calls


def test_fixed_native_limits_and_shared_total_deadline(native):
    t = module(); client = t.AnnualHttp(time.monotonic() + .8)
    client.request(IR)
    argv, deadline, limits = native[2][0]
    assert 0 < float(argv[argv.index('--max-time') + 1]) <= .8
    assert float(argv[argv.index('--connect-timeout') + 1]) <= .8
    assert deadline <= client.deadline
    assert argv[argv.index('--retry') + 1] == '0' and argv[argv.index('--max-redirs') + 1] == '0'
    assert not any('cookie' in v.lower() or 'authorization' in v.lower() for v in argv)
    assert limits['body_limit'] == 500_000
    with pytest.raises(t.SourceResponseError): t.AnnualHttp(time.monotonic() - 1).request(IR)
    assert len(native[2]) == 1
    assert t.contract(MASTER)[0] == 2_500_000
    assert t.contract(next(u for u in native[1] if '.pdf?' in u))[0] == 8 * 1024 * 1024


def test_deadline_after_archive_readback_rejects_delivery(native, monkeypatch):
    t = module(); client = t.AnnualHttp(); original = client.read_original
    def expired(receipt, url, **kwargs):
        raw = original(receipt, url, **kwargs)
        client.deadline = time.monotonic() - 1
        return raw
    monkeypatch.setattr(client, 'read_original', expired)
    with pytest.raises(t.SourceResponseError) as exc: client.request(IR)
    assert exc.value.error_kind == 'timeout' and len(native[2]) == 1


def test_original_ttl_is_rechecked_after_archive_readback(native, monkeypatch):
    t = module(); client = t.AnnualHttp(); original = t._original_bytes
    def expired(receipt, url, **kwargs):
        raw = original(receipt, url, **kwargs)
        monkeypatch.setattr(time, 'time', lambda: NOW + 1800)
        return raw
    monkeypatch.setattr(t, '_original_bytes', expired)
    with pytest.raises(ValueError, match='expired'): client.request(IR)
    assert len(native[2]) == 1
