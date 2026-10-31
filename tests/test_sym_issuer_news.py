"""Saved full official SYM articles; isolated archive and transport seams only."""
import importlib
from datetime import datetime, timezone
from pathlib import Path
import pytest
import base64
from copy import deepcopy
from hashlib import sha256
import json
import time

ROOT = Path(__file__).parents[1]
R = ROOT / 'docs/evidence/source-acquisition/20261014/free-entry-followup/news-research'
NOW = 1791988800.0


def valid_data():
    return {'ticker': '2206.TW', 'company_name': '三陽工業 / Sanyang Motor Co., Ltd.', 'instrument_type': 'EQUITY',
            'company_identity': {'ticker': '2206.TW', 'stock_id': '2206', 'official_name': '三陽工業',
                                 'legal_name': None, 'english_names': ['Sanyang Motor Co., Ltd.', 'SANYANG MOTOR CO LTD'],
                                 'allowed_aliases': ['三陽工業', 'SANYANG MOTOR CO LTD', '2206', '2206.TW'], 'forbidden_aliases': []}}


@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import sym_issuer_news_transport as t
    from data_fetch.market_sources import official_issuer_master as master
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    names = {t.CORPORATE: 'sanyang-root', t.BRAND: 'sanyang-sym-brand', t.TAIWAN: 'sym-taiwan-index',
             t.INDEX: 'sym-global-index', t.ARTICLES[0]: 'sym-jepardo', t.ARTICLES[1]: 'sym-new-website'}
    bodies = {u: (R / (n + '.body')).read_bytes() for u, n in names.items()}
    bodies[t.MASTER] = (ROOT / 'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body').read_bytes()
    calls = []

    def download(self, url, diagnostic):
        raw = bodies[url]
        calls.append(url)
        self.http_request_count += 1
        ctype = 'text/csv' if url == t.MASTER else 'text/html'
        metadata = {'http_status': 200, 'effective_url': url, 'num_redirects': 0, 'size_download': len(raw),
                    'content_type': ctype, 'content_length': len(raw), 'method': 'GET', 'proxy_used': 0,
                    'cache_control': 'private' if url == t.MASTER else 'no-cache, private'}
        if url == t.MASTER:
            metadata = master.master_metadata(metadata, raw, {})
        else:
            metadata.update(pragma='', expires='access plus 1 month', age=None, cf_cache_status='')
        diagnostic.update(http_request_sent=True, http_status=200, response_metadata=metadata)
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                'request_method': 'GET', 'request_body': None, 'response_metadata': metadata}
    monkeypatch.setattr(t.SymNewsHttp, 'download_original', download)
    monkeypatch.setattr(t.IssuerMasterHttp, 'download_original', download)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def fetch():
    from data_fetch.market_sources.sym_issuer_news import fetch_recent_news
    return fetch_recent_news(now=datetime.fromtimestamp(time.time(), timezone.utc))


def test_public_saved_brand_originals_supply_two_distinct_articles(request):
    try:
        source = importlib.import_module('data_fetch.market_sources.sym_issuer_news')
    except ModuleNotFoundError as exc:
        if exc.name != 'data_fetch.market_sources.sym_issuer_news':
            raise
        records = []
    else:
        request.getfixturevalue('harness')
        records, audit = source.fetch_recent_news(now=datetime.fromtimestamp(NOW, timezone.utc))
        assert audit['status'] == 'success' and audit['window_complete'] is False, audit
        assert audit['coverage_status'] == 'partial' and audit['http_request_count'] == 7
        assert all(source.verified_record(r, valid_data(), today=datetime.fromtimestamp(NOW, timezone.utc).date()) for r in records)
    assert len(records) == 2, 'Published SYM global originals have no qualified issuer-news adapter'
    assert [r['date'] for r in records] == ['2026-10-01', '2026-09-30']
    assert all(r['source_role'] == 'issuer_statement' and not r['content_truncated'] for r in records)
    assert 'Europe' in records[0]['text'] and 'Digital' in records[1]['title']
    assert all('Home NEWSROOM' not in r['text'] and 'Share' not in r['text'] for r in records)


def test_actual_current_snapshot_identity_is_accepted():
    from data_fetch.market_sources.sym_issuer_news import validate_context
    snapshot = json.loads((ROOT / 'docs/evidence/source-acquisition/20261014/sym-news-recovery/author/current-snapshot.json').read_text())
    assert validate_context({**snapshot['selected_data'], 'ticker': '2206.TW'})


@pytest.mark.parametrize('field,value', [('ticker', '2206.TWO'), ('instrument_type', 'ETF'), ('quote_type', False), ('quoteType', 'ETF'), ('company_identity', False), ('company_name', '其他公司')])
def test_contradictory_root_context_is_rejected(field, value):
    from data_fetch.market_sources.sym_issuer_news import validate_context
    data = valid_data(); data[field] = value
    assert not validate_context(data)


@pytest.mark.parametrize('field,value', [('ticker', '2206.TWO'), ('stock_id', '2207'), ('official_name', '其他公司'), ('legal_name', '同名公司'), ('official_ubn', '99999999'), ('instrument_type', False), ('forbidden_aliases', ['SYM'])])
def test_nested_context_is_not_overridden_by_good_root(field, value):
    from data_fetch.market_sources.sym_issuer_news import validate_context
    data = valid_data(); data['company_identity'][field] = value
    assert not validate_context(data)


@pytest.mark.parametrize('field,value', [('公司名稱', '其他公司'), ('營利事業統一編號', '99999999'), ('網址', 'www.sanyang.com.tw.evil.test'), ('英文簡稱', 'Other'), ('出表日期', '1150814')])
def test_wrong_master_stops_before_chain(harness, field, value):
    import csv, io
    from data_fetch.market_sources import sym_issuer_news_transport as t
    rows = list(csv.DictReader(io.StringIO(harness[0][t.MASTER].decode('utf-8-sig'))))
    next(r for r in rows if r['公司代號'] == '2206')[field] = value
    buf = io.StringIO(); writer = csv.DictWriter(buf, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    harness[0][t.MASTER] = buf.getvalue().encode()
    records, audit = fetch()
    assert not records and audit['status'] == 'error' and harness[1] == [t.MASTER]


@pytest.mark.parametrize('name,old,new', [
    ('CORPORATE', b'sym-page67', b'sym-page68'), ('BRAND', b'https://tw.sym-global.com/', b'https://evil.test/'),
    ('TAIWAN', b'https://www.sym-global.com/', b'https://evil.test/'),
    ('INDEX', b'TAIWAN SANYANG MOTOR Co., Ltd.', b'OTHER MOTOR Co., Ltd.')])
def test_broken_brand_chain_cannot_borrow_other_brand_body(harness, name, old, new):
    from data_fetch.market_sources import sym_issuer_news_transport as t
    url = getattr(t, name); raw = harness[0][url]; changed = raw.replace(old, new); assert changed != raw
    harness[0][url] = changed
    records, audit = fetch()
    assert not records and audit['status'] == 'error' and not any(u in t.ARTICLES for u in harness[1])


@pytest.mark.parametrize('change', ['title', 'date', 'duplicate', 'canonical', 'ogurl', 'publisher', 'script', 'empty'])
def test_index_or_article_contradiction_cannot_supply_first_record(harness, change):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources import sym_issuer_news_transport as t
    url = t.INDEX if change in ('title', 'date', 'duplicate') else t.ARTICLES[0]
    soup = BeautifulSoup(harness[0][url], 'html.parser')
    if change in ('title', 'date', 'duplicate'):
        card = next(c for c in soup.select('a.c-news-card__content-wrap') if c['href'] == t.ARTICLES[0])
        if change == 'title': card.select_one('h2').string = 'Invented news'
        elif change == 'date': card.select_one('.c-news-card__date').string = 'Oct. 14 2026'
        else:
            copied = deepcopy(card); copied.select_one('.c-news-card__date').string = 'Oct. 13 2026'; card.insert_after(copied)
    elif change == 'canonical': soup.select_one('link[rel=canonical]')['href'] = t.ARTICLES[1]
    elif change == 'ogurl': soup.select_one('meta[property="og:url"]')['content'] = t.INDEX
    elif change == 'publisher': soup.select_one('footer').clear()
    elif change == 'script': soup.select_one('.post_content').append(BeautifulSoup('<script>fake()</script>', 'html.parser'))
    else: soup.select_one('.post_content').clear()
    harness[0][url] = str(soup).encode()
    records, audit = fetch()
    assert not records and audit['status'] == 'error'


def test_global_web_title_alias_is_not_invented_visible_title(harness):
    from data_fetch.market_sources import sym_issuer_news as source
    records, _ = fetch()
    assert records[1]['title'] == 'SYM Upgrades Global Website for a New Digital Era'
    assert records[1]['publication_date_original']['article_date'] is None
    assert records[1]['publication_date_precision'] == 'day' and not records[1]['first_publication_time_verified']
    assert not records[1]['commercial_reuse_permission_verified'] and not records[1]['image_content_verified']
    assert {source.verified_record(r, valid_data(), today=datetime.fromtimestamp(NOW).date()) for r in records} == {source.PUBLISHER}


def test_second_article_failure_preserves_first_with_explicit_degraded_audit(harness, monkeypatch):
    from data_fetch.market_sources import sym_issuer_news_transport as t
    from search_provider_runtime import SourceResponseError
    original = t.SymNewsHttp.download_original
    def fail(self, url, diagnostic):
        if url == t.ARTICLES[1]: raise SourceResponseError('timeout')
        return original(self, url, diagnostic)
    monkeypatch.setattr(t.SymNewsHttp, 'download_original', fail)
    records, audit = fetch()
    assert len(records) == 1 and audit['status'] == 'degraded_enrichment' and audit['error_kind'] == 'timeout'
    assert audit['http_request_count'] == 6 and audit['window_complete'] is False


def test_shared_warm_master_does_not_reuse_html_or_refresh_original_epoch(harness, monkeypatch):
    from data_fetch.market_sources import sym_issuer_news_transport as t
    first, _ = fetch(); monkeypatch.setattr(time, 'time', lambda: NOW + 10)
    second, audit = fetch()
    assert audit['http_request_count'] == 6 and audit['cache_hit'] is False
    proof = second[0]['issuer_news_receipt']['source_record_archive']
    assert proof['master']['cache_hit'] is True and proof['master']['retrieved_at'] == NOW
    assert proof['article']['cache_hit'] is False and proof['article']['retrieved_at'] == NOW + 10
    assert harness[1] == [t.MASTER, *t.HTML_URLS, *t.HTML_URLS]
    assert first[0]['issuer_news_receipt']['source_record_archive']['article']['retrieved_at'] == NOW


@pytest.mark.parametrize('change', ['text', 'title', 'publisher', 'date', 'invented_time', 'policy', 'role', 'precision', 'coverage_bool', 'cache_bool', 'http_bool', 'epoch', 'expiry', 'hash', 'manifest', 'strip'])
def test_saved_record_tamper_fails_full_original_replay(harness, change):
    from data_fetch.market_sources import sym_issuer_news as s
    records, _ = fetch(); r = deepcopy(records[0]); proof = r['issuer_news_receipt']['source_record_archive']['article']
    if change in ('text', 'title', 'publisher'): r[change] += ' altered'
    elif change == 'date': r['date'] = '2026-10-02'
    elif change == 'invented_time': r['date'] = '2026-10-01T13:00:00+00:00'
    elif change == 'policy': r['issuer_news_receipt']['policy'] = 'first-party-issuer-news-v1'
    elif change == 'role': r['source_role'] = 'independent_editorial'
    elif change == 'precision': r['publication_date_precision'] = 'second'
    elif change == 'coverage_bool': r['content_truncated'] = 0
    elif change == 'cache_bool': proof['cache_hit'] = 0
    elif change == 'http_bool': proof['http_status'] = True
    elif change == 'epoch': proof['retrieved_at'] += 1
    elif change == 'expiry': proof['fresh_until_epoch'] += 1
    elif change == 'hash': proof['raw_response_sha256'] = '0' * 64
    elif change == 'manifest': proof.pop('acquisition_manifest')
    else: r.pop('issuer_news_receipt')
    assert s.is_marked(r) and s.verified_record(r, valid_data(), today=datetime.fromtimestamp(NOW).date()) is None


def test_dynamic_date_window_skips_currently_old_material_without_articles(harness, monkeypatch):
    from data_fetch.market_sources import sym_issuer_news as s, sym_issuer_news_transport as t
    monkeypatch.setattr(s, 'parse_master', lambda *a: {})  # identity is not this date-boundary test
    records, audit = s.fetch_recent_news(now=datetime(2026, 11, 2, tzinfo=timezone.utc))
    assert not records and audit['status'] == 'unavailable' and not any(u in t.ARTICLES for u in harness[1])
    assert audit['excluded_reason_counts']['historical'] == 9


def test_caller_deadline_is_not_extended(harness):
    from data_fetch.market_sources import sym_issuer_news as s
    records, audit = s.fetch_recent_news(now=datetime.fromtimestamp(NOW, timezone.utc), deadline=time.monotonic() - 1)
    assert not records and audit['error_kind'] == 'timeout' and harness[1] == []


def future_article(harness, number=375, *, indexed=True):
    """Synthetic future schema case, not a qualified real-world event."""
    from bs4 import BeautifulSoup
    from data_fetch.market_sources import sym_issuer_news_transport as t
    url = t.GLOBAL + f'newsroom-page{number}'
    title = f'SYM announces a new distribution centre {number}'
    if indexed:
        index = BeautifulSoup(harness[0][t.INDEX], 'html.parser')
        card = deepcopy(index.select_one('a.c-news-card__content-wrap'))
        card['href'] = url; card['title'] = title
        card.select_one('h2').string = title
        card.select_one('.c-news-card__date').string = 'Oct. 13 2026'
        index.select_one('a.c-news-card__content-wrap').insert_before(card)
        harness[0][t.INDEX] = str(index).encode()
    article = BeautifulSoup(harness[0][t.ARTICLES[0]], 'html.parser')
    article.select_one('h1.page-title').string = title
    article.select_one('link[rel=canonical]')['href'] = url
    article.select_one('meta[property="og:url"]')['content'] = url
    article.select_one('.post_content').string = ('SYM announced a distribution centre for supporting dealers and after-sales service. '
                                                  'This synthetic publication exercises a new exact index entry and never represents live qualification.')
    harness[0][url] = str(article).encode()
    return url


def test_new_published_index_article_is_not_limited_to_initial_two_ids(harness):
    from data_fetch.market_sources import sym_issuer_news as s
    url = future_article(harness)
    records, audit = fetch()
    assert len(records) == 3 and records[0]['link'] == url and audit['http_request_count'] == 8
    assert s.verified_record(records[0], valid_data(), today=datetime.fromtimestamp(NOW).date()) == s.PUBLISHER


def test_unlisted_body_url_cannot_enter_saved_record_even_with_valid_archive(harness):
    from data_fetch.market_sources import sym_issuer_news as s, sym_issuer_news_transport as t
    records, _ = fetch(); url = future_article(harness, indexed=False)
    _, receipt = t.SymNewsHttp(time.monotonic() + 25).get_receipt(url)
    r = deepcopy(records[0]); r.update(link=url, source_document_url=url)
    r['issuer_news_receipt']['source_record_archive']['article'] = receipt
    assert s.verified_record(r, valid_data(), today=datetime.fromtimestamp(NOW).date()) is None


def test_at_most_five_published_articles_and_no_event_pages(harness):
    from data_fetch.market_sources import sym_issuer_news_transport as t
    for number in range(375, 381): future_article(harness, number)
    records, audit = fetch()
    assert len(records) == 5 and audit['excluded_reason_counts']['article_limit'] == 3
    assert sum(bool(t.ARTICLE.fullmatch(u)) for u in harness[1]) == 5
    assert all('news-events' not in u for u in harness[1])


def test_final_shared_expiry_is_rechecked_even_if_second_article_failed(harness, monkeypatch):
    from data_fetch.market_sources import sym_issuer_news_transport as t
    from search_provider_runtime import SourceResponseError
    original = t.SymNewsHttp.download_original
    def fail_late(self, url, diagnostic):
        if url == t.ARTICLES[1]:
            monkeypatch.setattr(time, 'time', lambda: NOW + 1801)
            raise SourceResponseError('timeout')
        return original(self, url, diagnostic)
    monkeypatch.setattr(t.SymNewsHttp, 'download_original', fail_late)
    records, audit = fetch()
    assert not records and audit['error_kind'] == 'original_expired'


def test_snapshot_sanitizer_preserves_complete_receipts(harness):
    from data_trust_snapshot_sanitizer import sanitize_for_snapshot
    from data_fetch.market_sources import sym_issuer_news as s
    records, _ = fetch()
    saved = sanitize_for_snapshot(records)
    assert all(s.verified_record(r, valid_data(), today=datetime.fromtimestamp(NOW).date()) for r in saved)


def test_corporate_and_global_articles_are_one_reported_publisher(harness):
    from news_freshness_policy import publisher_identity, apply_news_freshness
    from data_fetch.market_sources import sym_issuer_news as s
    from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news, verified_issuer_news
    from test_issuer_news import Http
    records, _ = fetch()
    legacy = {'source': '三陽工業官網', 'publisher': '三陽工業官網',
              'link': 'https://www.sanyang.com.tw/busnessnews-page123',
              'issuer_news_receipt': {'policy': 'first-party-issuer-news-v1'}}
    assert publisher_identity(records[0])[1] == publisher_identity(legacy)[1]
    assert not s.is_marked(legacy), 'new adapter must not intercept old corporate receipts'
    old, _ = fetch_recent_issuer_news('2206.TW', now=datetime.fromtimestamp(NOW, timezone.utc), http=Http('2206.TW'))
    data = {}  # Test normalization independently of root's still-unfrozen dispatch.
    apply_news_freshness(data, records=[*old, *records], cutoff=datetime.fromtimestamp(NOW, timezone.utc))
    first = deepcopy(data['recent_catalysts'])
    apply_news_freshness(data, cutoff=datetime.fromtimestamp(NOW, timezone.utc))
    assert data['recent_catalysts'] == first and len(first) == 3 and data['news_selection']['publisher_count'] == 1
    for row in first:
        if s.is_marked(row): assert s.verified_record(row, valid_data(), today=datetime.fromtimestamp(NOW).date())
        else: assert verified_issuer_news(row, valid_data(), today=datetime.fromtimestamp(NOW).date())


def test_caller_limit_saves_unneeded_article_http(harness):
    from data_fetch.market_sources import sym_issuer_news as s, sym_issuer_news_transport as t
    records, audit = s.fetch_recent_news(now=datetime.fromtimestamp(NOW, timezone.utc), limit=1)
    assert len(records) == 1 and audit['http_request_count'] == 6
    assert t.ARTICLES[1] not in harness[1] and audit['excluded_reason_counts']['article_limit'] == 1


@pytest.mark.parametrize('limit', [True, False, 0, 6, -1, 1.0, '1', None])
def test_invalid_caller_limit_cannot_start_http(harness, limit):
    from data_fetch.market_sources import sym_issuer_news as s
    with pytest.raises(ValueError): s.fetch_recent_news(now=datetime.fromtimestamp(NOW, timezone.utc), limit=limit)
    assert harness[1] == []


def test_preexisting_shared_master_consumer_preserves_epoch_and_avoids_identity_http(harness, monkeypatch):
    from data_fetch.market_sources import sym_issuer_news_transport as t
    t.IssuerMasterHttp(time.monotonic() + 25).get_receipt(t.MASTER)
    monkeypatch.setattr(time, 'time', lambda: NOW + 15)
    records, audit = fetch()
    assert len(records) == 2 and audit['http_request_count'] == 6
    master = records[0]['issuer_news_receipt']['source_record_archive']['master']
    assert master['cache_hit'] is True and master['retrieved_at'] == NOW
    assert harness[1].count(t.MASTER) == 1
