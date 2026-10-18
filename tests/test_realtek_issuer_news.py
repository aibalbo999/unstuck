"""Selected native public sections exercise issuer admission without live requests."""
from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path
import json

from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news
from data_fetch.market_sources.issuer_news_transport import ROSTER_URL, url_contract
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest
from source_content_selection import select_company_records
import pytest

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/realtek_issuer_news_selected_20261010.json').read_text())
INDEX = FIXTURE['source_index_url']
ARTICLE = FIXTURE['source_article_url']
NOW = datetime(2026, 10, 10, 0, tzinfo=timezone.utc)
DATA = {'ticker': '2379.TW', 'company_name': '瑞昱', 'company_identity': {
    'official_name': '瑞昱', 'legal_name': '瑞昱半導體股份有限公司',
    'allowed_aliases': ['瑞昱'], 'forbidden_aliases': []}}


class Http:
    def __init__(self, *, cached=False):
        self.contents = {ROSTER_URL: json.dumps([FIXTURE['roster']], ensure_ascii=False).encode(),
                         INDEX: FIXTURE['index_html'].encode(), ARTICLE: FIXTURE['article_html'].encode()}
        self.calls, self.components = [], []
        self.http_request_count = 0
        self.cached = cached

    def get(self, url):
        self.calls.append(url)
        self.http_request_count += int(not self.cached)
        self.components.append({'url': url, 'cache_hit': self.cached, 'http_request_sent': not self.cached,
                                'fetched_at_epoch': NOW.timestamp() - 300})
        return self.contents[url]


def get(http=None):
    return fetch_recent_issuer_news('2379.TW', now=NOW, http=http or Http())


def test_realtek_enters_original_recent_catalyst_plan_only_for_listed_issuer():
    registry = ProviderRegistry()
    assert 'Verified issuer news' in registry.provider_names(FetchRequest.from_ticker('2379.TW'), 'recent_catalysts')
    assert 'Verified issuer news' not in registry.provider_names(FetchRequest.from_ticker('2379.TWO'), 'recent_catalysts')


def test_observed_public_original_reaches_company_selection_without_global_alias_change():
    http = Http()
    rows, audit = get(http)
    assert len(rows) == 1 and audit['status'] == 'success'
    accepted, _ = select_company_records(rows, DATA, cutoff=NOW)
    assert len(accepted) == 1 and accepted[0]['date'] == '2026-10-08'
    assert 'from October 12 to 16, 2026' in accepted[0]['text']
    assert 'Realtek Semiconductor Corporation' in accepted[0]['text']
    assert accepted[0]['content_truncated'] is False
    assert accepted[0]['event_assessment'] == 'not_assessed'
    assert accepted[0]['publisher'] == 'Realtek'
    assert audit['window_complete'] is False
    assert http.calls == [ROSTER_URL, INDEX, ARTICLE]
    assert DATA['company_identity']['allowed_aliases'] == ['瑞昱']


def test_realtek_public_routes_have_bounded_html_contract():
    assert url_contract(INDEX) == (400_000, {'text/html', 'application/xhtml+xml'})
    assert url_contract(ARTICLE) == (150_000, {'text/html', 'application/xhtml+xml'})
    assert url_contract('https://www.sanyang.com.tw/newslist')[0] == 150_000


def test_original_exact_thirty_day_boundary_skips_outdated_article_http():
    http = Http()
    http.contents[INDEX] = http.contents[INDEX].replace(b'2026-10-08', b'2026-09-10')
    rows, audit = fetch_recent_issuer_news('2379.TW', now=NOW.replace(hour=1), http=http)
    assert rows == [] and audit['status'] == 'unavailable'
    assert http.calls == [ROSTER_URL, INDEX]
    assert audit['excluded_reason_counts']['historical'] == 3


@pytest.mark.parametrize('field,value', [
    ('公司名稱', '另一家公司股份有限公司'), ('公司簡稱', '他家公司'), ('英文簡稱', 'Realtek'),
    ('營利事業統一編號', '99999999'), ('網址', 'https://www.realtek.com/private'),
    ('網址', 'https://www.realtek.com.evil.test/'), ('出表日期', '1150801')])
def test_incorrect_issuer_binding_stops_before_news_http(field, value):
    http = Http()
    rows = json.loads(http.contents[ROSTER_URL])
    rows[0][field] = value
    http.contents[ROSTER_URL] = json.dumps(rows, ensure_ascii=False).encode()
    records, audit = get(http)
    assert records == [] and audit['status'] == 'error'
    assert http.calls == [ROSTER_URL]


def test_wholly_cached_originals_keep_original_epoch_and_zero_http():
    rows, audit = get(Http(cached=True))
    assert len(rows) == 1 and audit['status'] == 'skipped_fresh_cache'
    assert audit['http_request_count'] == 0 and audit['http_request_sent'] is False
    assert audit['fetched_at_epoch'] == NOW.timestamp() - 300


@pytest.mark.parametrize('change', ['title', 'date', 'body', 'url', 'source_type', 'publisher',
                                  'receipt_missing', 'policy', 'index_hash', 'archive_url', 'archive_size',
                                  'archive_path', 'archive_time', 'archive_future', 'master_ubn'])
def test_saved_originals_and_semantic_fields_are_revalidated(change):
    rows, _ = get()
    row = deepcopy(rows[0])
    if change == 'title':
        row['title'] = 'Realtek fabricated title'
    elif change == 'date':
        row['date'] = '2026-10-09'
    elif change == 'body':
        row['text'] = 'Realtek fabricated body' * 20
    elif change == 'url':
        row['link'] = 'https://evil.test/news/private'
    elif change == 'source_type':
        row.pop('source_type')
    elif change == 'publisher':
        row['publisher'] = 'Independent newspaper'
    elif change == 'receipt_missing':
        row['issuer_news_receipt'].pop('source_record_archive')
    elif change == 'policy':
        row['issuer_news_receipt']['policy'] = 'first-party-issuer-news-v1'
    elif change == 'index_hash':
        row['issuer_news_receipt']['index_response_sha256'] = '0' * 64
    elif change == 'master_ubn':
        row['issuer_news_receipt']['official_ubn'] = '99999999'
    else:
        proof = row['issuer_news_receipt']['source_record_archive']['article']
        if change == 'archive_url': proof['source_url'] = INDEX
        elif change == 'archive_size': proof['raw_response_bytes'] += 1
        elif change == 'archive_path': proof['raw_response_path'] = '/tmp/not-an-original.gz'
        elif change == 'archive_time': proof['retrieved_at'] = float('nan')
        else: proof['retrieved_at'] = 9e15
    accepted, _ = select_company_records([row], DATA, cutoff=NOW)
    assert accepted == []


@pytest.mark.parametrize('context', [False, {'official_name': '另一家公司'}, {'legal_name': '另一家公司股份有限公司'},
                                   {'forbidden_aliases': ['REALTEK']}, {'forbidden_aliases': False}])
def test_typed_issuer_match_cannot_override_conflicting_or_malformed_company_context(context):
    rows, _ = get()
    accepted, _ = select_company_records(rows, {**DATA, 'company_identity': context}, cutoff=NOW)
    assert accepted == []


@pytest.mark.parametrize('url', [
    'https://www.realtek.com/Article/GetAllNewsTitle', INDEX + '&token=x', ARTICLE + '&id=4839',
    ARTICLE.replace('en-GB', 'zh-TW'), ARTICLE.replace('app_id=18', 'app_id=19'),
    ARTICLE.replace('www.realtek.com', 'www.realtek.com.evil.test'), ARTICLE.replace('https:', 'http:')])
def test_dynamic_authenticated_ambiguous_or_other_language_routes_do_not_start_http(url):
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):
        url_contract(url)


@pytest.mark.parametrize('change', ['dateline_missing', 'dateline_future', 'title', 'issuer', 'nested_date', 'script'])
def test_footer_related_or_event_dates_cannot_supply_article_publication(change):
    from bs4 import BeautifulSoup
    http = Http()
    soup = BeautifulSoup(http.contents[ARTICLE], 'html.parser')
    body = soup.select_one('div.element-itemname')
    if change == 'dateline_missing':
        http.contents[ARTICLE] = http.contents[ARTICLE].replace(b'October 08, 2026', b'publication unknown')
    elif change == 'dateline_future':
        http.contents[ARTICLE] = http.contents[ARTICLE].replace(b'October 08, 2026', b'October 12, 2026')
    elif change == 'title':
        soup.select_one('h1.pos-title').string = 'Realtek other article'
        http.contents[ARTICLE] = str(soup).encode()
    elif change == 'issuer':
        http.contents[ARTICLE] = http.contents[ARTICLE].replace(b'Realtek Semiconductor Corporation', b'Another Corporation')
    elif change == 'nested_date':
        body.find('p', recursive=False).decompose()
        body.append(BeautifulSoup('<aside><p>HSINCHU, Taiwan – October 08, 2026 – related article</p></aside>', 'html.parser'))
        http.contents[ARTICLE] = str(soup).encode()
    else:
        body.append(BeautifulSoup('<script>document.write("Realtek")</script>', 'html.parser'))
        http.contents[ARTICLE] = str(soup).encode()
    rows, audit = get(http)
    assert rows == [] and audit['status'] == 'error'
    assert http.calls == [ROSTER_URL, INDEX, ARTICLE]


def test_native_article_survives_existing_optional_workflow_and_keeps_original_quality_limits(monkeypatch):
    import asyncio
    from unittest.mock import patch
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources import issuer_news
    import data_fetch.workflow as workflow
    real = issuer_news.fetch_recent_issuer_news
    monkeypatch.setattr(issuer_news, 'fetch_recent_issuer_news', lambda ticker: real(ticker, now=NOW, http=Http()))
    monkeypatch.setattr(workflow, 'cache_financial_payload', lambda *a: None)
    monkeypatch.setattr(workflow, 'finalize_data_trust', lambda *a: None)
    monkeypatch.setattr(workflow, '_merge_optional_http_bundle', lambda data, bundle, **kwargs: _merge_optional_http_bundle(data, bundle))
    data = deepcopy(DATA)
    before = deepcopy(data['company_identity'])
    with patch('news_freshness_policy.news_cutoff', return_value=NOW):
        out = asyncio.run(workflow._run_optional_provider_plan(
            FetchRequest.from_ticker('2379.TW'), ProviderRegistry([IssuerNewsProvider()]), data, sources=('recent_catalysts',)))
    assert len(out['recent_catalysts']) == 1 and out['company_identity'] == before
    assert out['recent_catalysts'][0]['date'] == '2026-10-08T00:00:00+00:00'
    assert any(a['provider'] == 'Verified issuer news' and a['record_count'] == 1 for a in out['source_audit'])
    assert out['recent_catalysts'][0]['event_assessment'] == 'not_assessed'


def test_processing_after_whole_deadline_does_not_admit_the_late_article(monkeypatch):
    import time
    from types import SimpleNamespace
    from data_fetch.market_sources import realtek_issuer_news as parser
    clock = [0.]
    real_parse = parser.parse_article
    monkeypatch.setattr(parser, 'time', SimpleNamespace(monotonic=lambda: clock[0], time=time.time))
    def slow_parse(*args, **kwargs):
        parsed = real_parse(*args, **kwargs)
        clock[0] = 21.
        return parsed
    monkeypatch.setattr(parser, 'parse_article', slow_parse)
    rows, audit = get()
    assert rows == [] and audit['record_count'] == 0 and audit['status'] == 'error'
    assert audit['error_kind'] == 'timeout'


def test_master_issue_date_does_not_precede_its_original_acquisition():
    rows, _ = get()
    row = deepcopy(rows[0])
    row['issuer_news_receipt']['source_record_archive']['master']['retrieved_at'] = NOW.timestamp() - 7 * 86400
    accepted, _ = select_company_records([row], DATA, cutoff=NOW)
    assert accepted == []


@pytest.mark.parametrize('container', ['blockquote', 'q', 'figcaption', 'strong class="caption"'])
def test_quoted_or_caption_date_cannot_replace_article_dateline(container):
    from bs4 import BeautifulSoup
    http = Http()
    soup = BeautifulSoup(http.contents[ARTICLE], 'html.parser')
    first = soup.select_one('div.element-itemname').find('p', recursive=False)
    first.clear()
    first.append(BeautifulSoup('<' + container + '>HSINCHU, Taiwan – October 08, 2026 – quoted prior release.</'
                              + container.split()[0] + '>', 'html.parser'))
    http.contents[ARTICLE] = str(soup).encode()
    rows, audit = get(http)
    assert rows == [] and audit['status'] == 'error'


def test_internal_original_paths_do_not_enter_public_prompt_or_mutate_saved_evidence():
    from prompt_builder import format_data_for_prompt
    rows, _ = get()
    before = deepcopy(rows)
    rendered = format_data_for_prompt({**deepcopy(DATA), 'recent_catalysts': rows})
    assert 'official-response-evidence' not in rendered
    assert 'raw_response_path' not in rendered
    assert before[0]['title'] in rendered and '2026-10-08' in rendered
    assert 'Realtek Semiconductor Corporation' in rendered
    assert rows == before
