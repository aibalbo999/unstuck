"""Complete public parent originals, never a bank or insurance attribution shortcut."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import gzip
import importlib.util
import json
import time
import pytest
from test_shared_provider_cache import memory_cache

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'docs/evidence/source-acquisition/20261014/remaining-four-next'
D = ROOT / 'docs/evidence/source-acquisition/20261014/unitech-and-parent-news'
NOW = datetime(2026, 10, 14, 0, tzinfo=timezone.utc)
MASTER = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX = 'https://www.tcfhc.com.tw/news/message/news/2026'
PARENT = INDEX + '/021-1151007'
SPORTS = INDEX + '/076-1151001'
BANK = INDEX + '/078-1151007'
DATA = {'ticker': '5880.TW', 'company_name': '合庫金', 'quote_type': 'EQUITY', 'company_identity': {
    'ticker': '5880.TW', 'stock_id': '5880', 'official_name': '合庫金', 'legal_name': '合作金庫金融控股股份有限公司',
    'official_ubn': '53021433', 'instrument_type': 'EQUITY', 'allowed_aliases': ['合庫金', '合庫金控'], 'forbidden_aliases': []}}


class Http:
    def __init__(self, cached=False):
        self.contents = {MASTER: gzip.decompress((ROOT/'tests/fixtures/source_acquisition/tcfhc5880_master_20261013.gz').read_bytes()),
                         INDEX: (R/'tcfhc-news-2026-index.body').read_bytes(),
                         PARENT: (R/'tcfhc-news-20261007-sustainability.body').read_bytes(),
                         SPORTS: (D/'news-research-sports.body').read_bytes(),
                         BANK: (D/'news-research-bank-negative.body').read_bytes()}
        self.calls = []; self.components = []; self.http_request_count = 0; self.cached = cached
        self.epoch = NOW.timestamp() - 20
    def get_receipt(self, url):
        from official_response_evidence import archive_response
        self.calls.append(url); self.http_request_count += int(not self.cached)
        body = self.contents[url]
        proof = archive_response(body, source_url=url, retrieved_at=self.epoch, http_status=200)
        proof.update(http_status_observed=True, request_method='GET', response_complete=True, cache_hit=self.cached)
        self.components.append({'url': url, 'http_request_sent': not self.cached, 'http_status': 200,
                                'fetched_at_epoch': self.epoch, 'cache_hit': self.cached, 'original_receipt': proof})
        return body, proof
    def get(self, url):
        return self.get_receipt(url)[0]


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(time, 'time', lambda: NOW.timestamp())


@pytest.fixture
def native_news(monkeypatch):
    """Default NewsHttp, real complete originals, isolated cache; zero native I/O.

    Return (base_module, mutable_url_bytes, native_calls, original_collect).
    Each native_calls item is (argv, deadline, kwargs).
    """
    from data_fetch.market_sources import issuer_news_transport as base
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for name in base.PROXY_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(base, 'proxy_url_for_request', lambda *args: None)
    monkeypatch.setattr(base, 'observe_http_response', lambda *args: None)
    calls, contents = [], Http().contents
    def collect(argv, deadline, **kwargs):
        url = argv[-1]; calls.append((argv, deadline, kwargs)); raw = contents[url]
        mime = 'text/csv' if url == MASTER else 'text/html'
        return {'body': raw, 'headers': f'HTTP/2 200\r\nContent-Type: {mime}\r\nContent-Length: {len(raw)}\r\n\r\n'.encode(),
                'metadata': json.dumps({'http_code': 200, 'url_effective': url, 'num_redirects': 0,
                                        'size_download': len(raw), 'method': 'GET'}).encode(),
                'process_started': True, 'body_bytes_read': len(raw)}, 0, None
    monkeypatch.setattr(base, 'collect_capped_process', collect)
    return base, contents, calls, collect


def source():
    from data_fetch.market_sources import tcfhc_issuer_news
    return tcfhc_issuer_news


def get(http=None):
    return source().fetch_recent_news(now=NOW, http=http or Http())


def test_first_page_admits_one_explicit_parent_original_and_excludes_bank_sports():
    h = Http()
    if importlib.util.find_spec('data_fetch.market_sources.tcfhc_issuer_news'):
        records, audit = get(h)
    else:
        import types
        legacy = types.ModuleType('data_fetch.market_sources.legacy_tcfhc_review')
        legacy.__package__ = 'data_fetch.market_sources'
        before = D / 'before/backend/data_fetch/market_sources/issuer_news.py'
        exec(compile(before.read_text(), str(before), 'exec'), legacy.__dict__)
        records, audit = legacy.fetch_recent_issuer_news('5880.TW', now=NOW, http=h)
    assert len(records) == 1, audit
    record = records[0]
    assert record['source_document_url'] == PARENT
    assert record['publisher'] == 'TCFHC' and record['date'] == '2026-10-07'
    assert record['source_role'] == 'issuer_statement' and record['event_assessment'] == 'not_assessed'
    assert record['content_truncated'] is False and len(record['text']) >= 529
    assert h.calls == [MASTER, INDEX, PARENT, SPORTS]
    assert audit['raw_count'] == 10 and audit['record_count'] == audit['usable_count'] == 1
    assert audit['window_complete'] is False and audit['coverage_status'] == 'partial'
    assert audit['http_request_count'] == 4 and audit['status'] == 'success'
    assert source().verified_record(record, DATA, today=NOW.date()) == 'TCFHC'


@pytest.mark.parametrize('change', ['root_ticker', 'identity_ticker', 'stock_id', 'short', 'legal', 'ubn',
                                  'instrument', 'root_company', 'root_company_with_good_identity',
                                  'alias_string', 'alias_boolean', 'english_dict', 'forbidden_parent', 'allowed_child'])
def test_context_cannot_alias_a_bank_or_conflicting_issuer_before_any_request(change):
    d = deepcopy(DATA)
    mapping = {'identity_ticker': ('ticker', '5880.TWO'), 'stock_id': ('stock_id', '2801'),
               'short': ('official_name', '合庫銀行'), 'legal': ('legal_name', '合作金庫商業銀行股份有限公司'),
               'ubn': ('official_ubn', '12345678'), 'alias_string': ('allowed_aliases', '合庫金'),
               'alias_boolean': ('allowed_aliases', [True]), 'english_dict': ('english_names', {}),
               'forbidden_parent': ('forbidden_aliases', ['合庫金控']), 'allowed_child': ('allowed_aliases', ['合庫銀行'])}
    if change in mapping:
        key, value = mapping[change]; d['company_identity'][key] = value
    if change == 'root_ticker': d['ticker'] = '2801.TW'
    if change == 'instrument': d['quote_type'] = 'ETF'
    if change == 'root_company': d['company_name'] = '合庫人壽'
    if change == 'root_company_with_good_identity': d['company_name'] = '其他公司 / Taiwan Cooperative Financial Holding Co., Ltd.'
    assert source().validate_context(d) is False
    h = Http()
    if source().validate_context(d): get(h)
    assert not h.calls


def test_saved_full_parent_record_cannot_bypass_changed_context():
    records, _ = get(); d = deepcopy(DATA); d['company_name'] = '合庫銀行'
    assert source().verified_record(records[0], d, today=NOW.date()) is None


@pytest.mark.parametrize('change', ['title', 'date', 'link', 'body', 'publisher', 'role', 'coverage', 'truncated',
                                  'receipt_policy', 'receipt_scope', 'fake_identity', 'extra_archive', 'missing_archive',
                                  'original_hash', 'original_bytes', 'original_epoch', 'original_future',
                                  'original_bool_epoch', 'original_infinite_epoch', 'original_huge_epoch',
                                  'original_http', 'original_method', 'original_complete', 'original_cache',
                                  'original_finality', 'original_historical', 'original_extra', 'original_source'])
def test_saved_record_replays_complete_originals_and_all_bound_fields(change):
    records, _ = get(); r = deepcopy(records[0]); receipt = r['issuer_news_receipt']; proofs = receipt['source_record_archive']
    changes = {'title': ('title', '合庫金控不同標題'), 'date': ('date', '2026-10-08'),
               'link': ('link', SPORTS), 'body': ('text', '不同正文'*100), 'publisher': ('publisher', 'TC BANK'),
               'role': ('source_role', 'independent_editorial'), 'coverage': ('content_coverage', 'snippet'),
               'truncated': ('content_truncated', True)}
    if change in changes:
        k, v = changes[change]; r[k] = v
    if change == 'receipt_policy': receipt['policy'] = 'generic-news'
    if change == 'receipt_scope': receipt['window_complete'] = True
    if change == 'fake_identity': receipt['official_ubn'] = '12345678'
    if change == 'extra_archive': proofs['other'] = deepcopy(proofs['article'])
    if change == 'missing_archive': del proofs['master']
    p = proofs['article']
    mutation = {'original_hash': ('raw_response_sha256', '0'*64), 'original_bytes': ('raw_response_bytes', p['raw_response_bytes']+1),
                'original_epoch': ('retrieved_at', p['retrieved_at']-1), 'original_future': ('retrieved_at', NOW.timestamp()+1),
                'original_bool_epoch': ('retrieved_at', True), 'original_infinite_epoch': ('retrieved_at', float('inf')),
                'original_huge_epoch': ('retrieved_at', 10**500), 'original_http': ('http_status', 201),
                'original_method': ('request_method', 'POST'), 'original_complete': ('response_complete', False),
                'original_cache': ('cache_hit', True), 'original_finality': ('finality_guaranteed', True),
                'original_historical': ('historical_point_in_time_verified', True), 'original_extra': ('stale', True),
                'original_source': ('source_url', SPORTS)}
    if change in mutation:
        k, v = mutation[change]; p[k] = v
    assert source().verified_record(r, DATA, today=NOW.date()) is None


@pytest.mark.parametrize('change', ['date', 'url', 'host', 'duplicate', 'blank_title', 'anchor_title',
                                  'owner', 'language', 'second_page', 'truncated'])
def test_index_binding_and_first_page_scope_fail_closed(change):
    from bs4 import BeautifulSoup
    h = Http(); soup = BeautifulSoup(h.contents[INDEX], 'html.parser')
    anchor = soup.find('a', href=PARENT.removeprefix('https://www.tcfhc.com.tw'))
    card = anchor.find_parent('li')
    if change == 'date': card.select_one('.c-list__date').string = '2026-10-06'
    if change == 'url': anchor['href'] += '?download=1'
    if change == 'host': anchor['href'] = 'https://www.tcfhc.com.tw.evil.invalid' + anchor['href']
    if change == 'duplicate': card.insert_after(deepcopy(card))
    if change == 'blank_title': card.select_one('.c-list__title').string = ''
    if change == 'anchor_title': anchor['title'] = '前往不同新聞'
    if change == 'owner': soup.select_one('.c-terms__copyright').string = '©合作金庫商業銀行'
    if change == 'language': soup.html['lang'] = 'en-US'
    if change == 'second_page': soup.select_one('.c-pager__num.is-active')['data-pagination-number'] = '2'
    raw = str(soup).encode()
    if change == 'truncated': raw = raw[:-50]
    h.contents[INDEX] = raw
    records, audit = get(h)
    assert not records and audit['status'] == 'error', audit
    assert h.calls == [MASTER, INDEX]


@pytest.mark.parametrize('change', ['title', 'date', 'og_url', 'og_title', 'body_child', 'script',
                                  'breadcrumb', 'missing_body', 'truncated'])
def test_full_article_must_match_index_and_explicit_parent_body(change):
    from bs4 import BeautifulSoup
    h = Http(); soup = BeautifulSoup(h.contents[PARENT], 'html.parser')
    body = soup.select_one('section[data-tc-announcement] .l-textBlock__text')
    if change == 'title': soup.select_one('h2.o-pageTitle').string = '不同標題'
    if change == 'date': soup.select_one('.l-postInfo__head span').string = '2026-10-08'
    if change == 'og_url': soup.select_one('meta[property="og:url"]')['content'] = SPORTS
    if change == 'og_title': soup.select_one('meta[property="og:title"]')['content'] = '不同標題'
    if change == 'body_child': body.string = '合庫銀行推廣銀行業務與客戶服務。'*40
    if change == 'script': body.append(BeautifulSoup('<script>different body</script>', 'html.parser'))
    if change == 'breadcrumb': soup.select_one('.c-breadcrumbs a[href="/news/message/news/2026"]')['href'] = '/news/message/news/2025'
    if change == 'missing_body': body.decompose()
    raw = str(soup).encode()
    if change == 'truncated': raw = raw[:raw.rindex(b'</html>')]
    h.contents[PARENT] = raw
    records, audit = get(h)
    assert not records
    if change == 'body_child':
        assert audit['status'] == 'unavailable' and audit['excluded_reason_counts']['not_explicit_parent_body_lead'] == 2
    else: assert audit['status'] == 'error' and h.calls == [MASTER, INDEX, PARENT]


def test_current_bank_and_sports_originals_do_not_become_parent_from_footer_or_dual_role():
    t = source(); h = Http(); rows = {x['url']: x for x in t.parse_index(h.contents[INDEX])}
    assert t.parse_article(h.contents[PARENT], rows[PARENT])[2] is True
    assert t.parse_article(h.contents[BANK], rows[BANK])[2] is False
    title, body, parent = t.parse_article(h.contents[SPORTS], rows[SPORTS])
    assert '合庫金控暨合庫銀行董事長' in body and parent is False


@pytest.mark.parametrize('day,slug', [('2026-10-15', '021-1151015'), ('2026-09-01', '021-1150901')])
def test_out_of_window_published_card_is_not_fetched(day, slug):
    from bs4 import BeautifulSoup
    h = Http(); soup = BeautifulSoup(h.contents[INDEX], 'html.parser')
    anchor = soup.find('a', href=PARENT.removeprefix('https://www.tcfhc.com.tw')); card = anchor.find_parent('li')
    anchor['href'] = '/news/message/news/2026/' + slug; card.select_one('.c-list__date').string = day
    h.contents[INDEX] = str(soup).encode(); records, audit = get(h)
    assert not records and PARENT not in h.calls and h.calls == [MASTER, INDEX, SPORTS]


def test_warm_originals_are_zero_http_and_do_not_renew_epoch():
    h = Http(cached=True); records, audit = get(h)
    assert len(records) == 1 and audit['status'] == 'skipped_fresh_cache'
    assert audit['http_request_count'] == 0 and audit['http_request_sent'] is False
    assert audit['fetched_at_epoch'] == h.epoch and audit['cache_hit'] is True
    proofs = records[0]['issuer_news_receipt']['source_record_archive']
    assert all(p['retrieved_at'] == h.epoch and p['cache_hit'] is True for p in proofs.values())


def test_all_acquired_originals_checked_at_common_final_delivery_time(monkeypatch):
    h = Http(cached=True); h.epoch = NOW.timestamp() - 1799.5
    original = source().parse_article
    def late(raw, row):
        result = original(raw, row)
        if row['url'] == SPORTS: monkeypatch.setattr(time, 'time', lambda: NOW.timestamp() + .6)
        return result
    monkeypatch.setattr(source(), 'parse_article', late)
    records, audit = get(h)
    assert not records and audit['status'] == 'error' and audit['error_kind'] == 'original_expired'
    assert audit['record_count'] == 0 and audit['http_request_count'] == 0


def test_total_deadline_includes_projection_after_last_article(monkeypatch):
    h = Http(); clock = [0.]; monkeypatch.setattr(time, 'monotonic', lambda: clock[0])
    original = source().parse_article
    def late(raw, row):
        result = original(raw, row)
        if row['url'] == SPORTS: clock[0] = 20.01
        return result
    monkeypatch.setattr(source(), 'parse_article', late)
    records, audit = get(h)
    assert not records and audit['status'] == 'error' and audit['error_kind'] == 'timeout'


def test_one_official_publisher_cannot_satisfy_eight_three_quality_gate():
    from external_search_quality import search_quality_satisfied
    from external_search_types import SearchResult
    records, _ = get()
    rows = [SearchResult(r['title'], r['text'], r['link'], r['publisher'], r['date']) for r in records]
    assert not search_quality_satisfied(rows, max_results=8, query='合庫金')


def test_shared_freshness_normalization_keeps_original_dates_and_replay():
    from news_freshness_policy import apply_news_only_freshness
    records, _ = get(); d = deepcopy(DATA)
    apply_news_only_freshness(d, cutoff=NOW, records=records)
    assert len(d['recent_catalysts']) == 1, d.get('news_selection')
    record = d['recent_catalysts'][0]
    assert record['date'] == record['published_date'] == '2026-10-07T00:00:00+00:00'
    assert record['publication_date_original'] == records[0]['publication_date_original']
    assert source().verified_record(record, DATA, today=NOW.date()) == 'TCFHC'


def test_warm_parent_is_not_new_success_from_metadata_or_excluded_bank_requests():
    class Mixed(Http):
        def get_receipt(self, url):
            self.cached = url == PARENT
            self.epoch = NOW.timestamp() - (100 if self.cached else 5)
            return super().get_receipt(url)
    records, audit = get(Mixed())
    assert len(records) == 1 and audit['cache_hit'] is True
    assert audit['status'] == 'skipped_fresh_cache'
    assert audit['http_request_count'] == 3 and audit['http_request_sent'] is True
    assert audit['fetched_at_epoch'] == NOW.timestamp() - 100
    from provider_acquisition import observation_kind
    assert observation_kind({'provider': 'Verified issuer news', 'status': audit['status'],
        'record_count': 1, 'message': '', 'details': audit}) == 'fresh_cache_count'


def test_default_transport_cold_and_warm_keep_native_receipts_and_epoch(native_news):
    cold, first = source().fetch_recent_news(now=NOW)
    warm, second = source().fetch_recent_news(now=NOW)
    assert len(cold) == len(warm) == 1
    assert first['http_request_count'] == 4 and first['status'] == 'success'
    assert second['http_request_count'] == 0 and second['status'] == 'skipped_fresh_cache'
    assert first['fetched_at_epoch'] == second['fetched_at_epoch'] == NOW.timestamp()
    assert [c[0][-1] for c in native_news[2]] == [MASTER, INDEX, PARENT, SPORTS]
    for record in [cold[0], warm[0]]:
        assert source().verified_record(record, DATA, today=NOW.date()) == 'TCFHC'
    for argv, deadline, kwargs in native_news[2]:
        if argv[-1] == MASTER:
            assert float(argv[argv.index('--max-time') + 1]) == 8
            assert float(argv[argv.index('--connect-timeout') + 1]) == 3
        else:
            assert float(argv[argv.index('--max-time') + 1]) <= 5
            assert float(argv[argv.index('--connect-timeout') + 1]) <= 2
        assert argv[argv.index('--retry') + 1] == argv[argv.index('--max-redirs') + 1] == '0'
        assert not any(x in argv for x in ('--insecure', '--location', '--cookie', '--proxy'))


@pytest.mark.parametrize('url', [INDEX+'?page=2', PARENT+'#article', PARENT+'?x=1',
                               PARENT.replace('https:', 'http:'), PARENT.replace('.com.tw/', '.com.tw.evil.invalid/'),
                               INDEX+'/021-1151032', INDEX+'/20251007', INDEX+'/../2026/021-1151007'])
def test_default_transport_rejects_unpublished_route_shapes_before_http(native_news, url):
    from search_provider_runtime import SourceResponseError
    h = source().NewsHttp(time.monotonic()+20)
    with pytest.raises(SourceResponseError): h.get_receipt(url)
    assert not native_news[2] and h.http_request_count == 0


@pytest.mark.parametrize('status,kind', [(403, 'access_denied'), (429, 'rate_limited'), (503, 'server_error')])
def test_native_failure_preserves_status_and_blocks_normal_and_forced_retry(native_news, monkeypatch, status, kind):
    from search_provider_runtime import SourceResponseError
    base, contents, calls, original = native_news
    def fail(argv, deadline, **kw):
        parts, rc, error = original(argv, deadline, **kw)
        parts['headers'] = f'HTTP/2 {status}\r\nContent-Type: text/html\r\n\r\n'.encode()
        parts['metadata'] = json.dumps({'http_code': status, 'url_effective': argv[-1], 'num_redirects': 0}).encode()
        return parts, 0, None
    monkeypatch.setattr(base, 'collect_capped_process', fail)
    first = source().NewsHttp(time.monotonic()+20)
    with pytest.raises(SourceResponseError) as error: first.get_receipt(PARENT)
    assert error.value.error_kind == kind
    assert first.components[0]['http_status'] == status
    assert first.http_request_count == 1
    for flags in ({}, {'force_refresh': True}, {'use_cache': False}):
        h = source().NewsHttp(time.monotonic()+20, **flags)
        with pytest.raises(SourceResponseError): h.get_receipt(PARENT)
        assert h.http_request_count == 0
    assert len(calls) == 1


@pytest.mark.parametrize('change', ['incomplete', 'refusal', 'timeout', 'redirect', 'mime'])
def test_native_invalid_original_is_not_success_or_retried(native_news, monkeypatch, change):
    base, contents, calls, original = native_news
    if change == 'incomplete': contents[PARENT] = contents[PARENT][:-50]
    if change == 'refusal': contents[PARENT] = b'<html lang="zh-Hant-TW"><title>Access denied</title></html>'
    def altered(argv, deadline, **kw):
        parts, rc, error = original(argv, deadline, **kw)
        if argv[-1] == PARENT:
            if change == 'timeout': return parts, 28, 'timeout'
            if change == 'redirect':
                meta = json.loads(parts['metadata']); meta['num_redirects'] = 1; parts['metadata'] = json.dumps(meta).encode()
            if change == 'mime': parts['headers'] = parts['headers'].replace(b'text/html', b'application/json')
        return parts, rc, error
    monkeypatch.setattr(base, 'collect_capped_process', altered)
    records, audit = source().fetch_recent_news(now=NOW)
    assert not records and audit['status'] == 'error' and audit['record_count'] == 0
    assert audit['http_request_count'] == 3 and len(calls) == 3
    again, second = source().fetch_recent_news(now=NOW)
    assert not again and second['status'] == 'error' and second['http_request_count'] == 0
    assert len(calls) == 3


@pytest.mark.parametrize('value', ['2026-10-07T00:00:00+08:00', '2026-10-07T01:00:00Z', '2026-10-08', True])
def test_normalized_date_cannot_contradict_original_day_or_timezone(value):
    records, _ = get(); record = records[0]; record['date'] = record['published_date'] = value
    assert source().verified_record(record, DATA, today=NOW.date()) is None


def test_guard_storage_failure_blocks_http_even_when_forced(native_news, monkeypatch):
    from search_provider_runtime import SourceResponseError
    import cache_store
    def broken(*args, **kwargs): raise OSError('isolated storage failure')
    monkeypatch.setattr(cache_store, 'set_cache_json', broken)
    for flags in ({}, {'force_refresh': True}, {'use_cache': False}):
        h = source().NewsHttp(time.monotonic()+20, **flags)
        with pytest.raises(SourceResponseError): h.get_receipt(PARENT)
        assert h.http_request_count == 0
    assert not native_news[2]
