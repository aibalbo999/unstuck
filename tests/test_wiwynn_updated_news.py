"""New exact issuer originals: update date must never become publication date."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
import json
import pytest
from bs4 import BeautifulSoup
from test_wiwynn_issuer_news import Http, DATA, MASTER, INDEX
from data_fetch.market_sources import wiwynn_issuer_news as source

D = Path(__file__).parents[1] / 'docs/evidence/source-acquisition/20261015/auras-wiwynn-current-gaps/research'
ROWS = json.loads((D / 'index-parser.json').read_text())['rows']
NOW = datetime(2026, 10, 15, 2, tzinfo=timezone.utc)


def original(label):
    receipt = json.loads((D / f'native-{label}.json').read_text())
    raw = (D / f'{label}.body').read_bytes()
    assert receipt['curl_returncode'] == 0 and receipt['curl_metrics']['http_code'] == 200
    assert len(raw) == receipt['response_bytes'] and sha256(raw).hexdigest() == receipt['response_sha256']
    return raw, receipt['response_finished_epoch']


class CurrentHttp(Http):
    def __init__(self):
        super().__init__()
        for label, url in [('index', INDEX), ('article0', ROWS[0]['url']), ('article1', ROWS[1]['url'])]:
            self.contents[url], self.epochs[url] = original(label)


@pytest.mark.parametrize('i,date', [(0, '2026-10-13T16:30:01+00:00'), (1, '2026-10-12T19:00:00+00:00')])
def test_real_updated_multiple_tag_article_keeps_original_publication(i, date):
    title, body, dates = source.parse_article(original('article' + str(i))[0], ROWS[i])
    assert title == ROWS[i]['title'] and len(body) > 1000
    assert dates['date'] == date
    assert dates['visible_date_kind'] == 'modified'
    assert dates['issuer_article_date'] == 'Updated on October 13, 2026'
    assert dates['jsonld_dateModified'].startswith('2026-10-13T')


def test_public_issuer_flow_replays_full_new_originals(monkeypatch):
    monkeypatch.setattr(source.time, 'time', lambda: NOW.timestamp())
    records, audit = source.fetch_recent_news(now=NOW, http=CurrentHttp())
    assert len(records) == 2 and audit['status'] == 'success', audit
    assert {r['date'] for r in records} == {'2026-10-13T16:30:01+00:00', '2026-10-12T19:00:00+00:00'}
    assert all(source.verified_record(r, DATA, today=NOW.date()) == 'Wiwynn' for r in records)
    assert all(r['source_role'] == 'issuer_statement' and not r['content_truncated'] for r in records)


@pytest.mark.parametrize('change', ['no_published', 'naive_published', 'index_day', 'no_modified', 'naive_modified',
    'modified_before_published', 'wrong_visible_update', 'missing_corporate', 'unknown_tag', 'duplicate_tag', 'foreign_tag', 'foreign_author'])
def test_update_metadata_and_classification_cannot_replace_publication_proof(change):
    soup = BeautifulSoup(original('article1')[0], 'html.parser')
    node = soup.select_one('script[type="application/ld+json"]'); ld = json.loads(node.get_text())
    listed = deepcopy(ROWS[1])
    if change == 'no_published': ld.pop('datePublished')
    elif change == 'naive_published': ld['datePublished'] = '2026-10-12T19:00:00'
    elif change == 'index_day': listed['date_original'] = 'Oct 13, 2026'
    elif change == 'no_modified': ld.pop('dateModified')
    elif change == 'naive_modified': ld['dateModified'] = '2026-10-13T00:17:49'
    elif change == 'modified_before_published': ld['dateModified'] = '2026-10-11T00:17:49.944Z'
    elif change == 'wrong_visible_update': soup.select_one('.blog-post__timestamp').string = 'Updated on October 14, 2026'
    elif change == 'missing_corporate': soup.select_one('.blog-post__tag-link').decompose()
    elif change == 'unknown_tag': soup.select_one('.blog-post__tag-link').string = 'Guest Opinion'
    elif change == 'duplicate_tag': soup.select_one('.blog-post__tags').append(deepcopy(soup.select_one('.blog-post__tag-link')))
    elif change == 'foreign_tag': soup.select_one('.blog-post__tag-link')['href'] = 'https://evil.example/news/tag/corporate'
    else: soup.select_one('.meta-author > a')['href'] = 'https://www.wiwynn.com/news/author/guest'
    node.string = json.dumps(ld)
    with pytest.raises(ValueError): source.parse_article(str(soup).encode(), listed)


def test_future_revision_cannot_be_bound_to_earlier_original(monkeypatch):
    monkeypatch.setattr(source.time, 'time', lambda: NOW.timestamp())
    h = CurrentHttp(); url = ROWS[0]['url']; h.epochs[url] = datetime(2026, 10, 13, 18, tzinfo=timezone.utc).timestamp()
    records, audit = source.fetch_recent_news(now=NOW, http=h)
    assert not records and audit['status'] == 'error'


def test_updated_old_news_does_not_enter_recent_window(monkeypatch):
    monkeypatch.setattr(source.time, 'time', lambda: NOW.timestamp())
    h = CurrentHttp()
    soup = BeautifulSoup(h.contents[INDEX], 'html.parser')
    for node in soup.select('#hs_cos_wrapper_widget_1687154120281 .hhs-post-meta > p'):
        node.string = 'Aug 13, 2026'
    h.contents[INDEX] = str(soup).encode()
    records, audit = source.fetch_recent_news(now=NOW, http=h)
    assert not records and audit['status'] == 'unavailable'
    assert h.calls == [MASTER, INDEX]
