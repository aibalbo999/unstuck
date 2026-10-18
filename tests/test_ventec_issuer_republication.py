"""Public provider behaviour for an observed issuer-hosted DigiTimes reprint."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news
from data_fetch.market_sources.issuer_news_transport import ROSTER_URL
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest
from news_freshness_policy import apply_news_freshness
from prompt_evidence import prompt_evidence_copy
from source_content_selection import select_company_records

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/ventec_issuer_republication_selected_20261010.json').read_text())
NOW = datetime(2026, 10, 10, 5, tzinfo=timezone.utc)
INDEX = 'https://www.ventec-group.com/cht/news/'
ARTICLE = INDEX + 'ventec-makes-a-decisive-investment-in-speed-capacity-and-capability/'
ORIGINAL = 'https://www.digitimes.com/news/a20260917PD235/expansion-ccl-ventec-kunshan-laminate.html'
DATA = {'ticker': '6672.TW', 'company_name': '騰輝電子-KY', 'company_identity': {'official_name': '騰輝電子-KY', 'allowed_aliases': ['騰輝電子-KY'], 'forbidden_aliases': []}}


class Http:
    def __init__(self):
        self.contents = {ROSTER_URL: json.dumps([FIXTURE['roster']], ensure_ascii=False).encode(),
                         INDEX: FIXTURE['index_html'].encode(), ARTICLE: FIXTURE['article_html'].encode()}
        self.calls, self.components, self.http_request_count = [], [], 0

    def get(self, url):
        self.calls.append(url)
        self.http_request_count += 1
        self.components.append({'url': url, 'http_request_sent': True, 'cache_hit': False, 'fetched_at_epoch': NOW.timestamp()-60})
        return self.contents[url]


def get(http=None):
    return fetch_recent_issuer_news('6672.TW', now=NOW, http=http or Http())


def test_exact_issuer_public_plan_includes_new_free_entry():
    registry = ProviderRegistry()
    assert 'Verified issuer news' in registry.provider_names(FetchRequest.from_ticker('6672.TW'), 'recent_catalysts')
    assert 'Verified issuer news' not in registry.provider_names(FetchRequest.from_ticker('6672.TWO'), 'recent_catalysts')


def test_observed_republication_has_full_text_and_keeps_two_date_meanings():
    rows, audit = get()
    assert audit['status'] == 'success' and len(rows) == 1
    row = rows[0]
    assert row['source_type'] == row['source_role'] == 'issuer_hosted_press_republication'
    assert row['date'] == row['issuer_republication_date'] == '2026-09-22'
    assert row['publication_date_basis'] == 'issuer_republication'
    assert row['original_publisher_publication_date'] is None
    assert row['publisher'] == 'DigiTimes' and row['link'] == ORIGINAL
    assert row['source_document_url'] == ARTICLE
    assert '原文發布日期未核對' in row['text'] and '官網轉載' in row['summary']
    assert len(row['text']) > 4900 and 'dual-engine' in row['text']
    assert row['content_truncated'] is False and row['event_assessment'] == 'not_assessed'
    assert audit['window_complete'] is False and audit['http_request_count'] == 3
    accepted, _ = select_company_records(rows, DATA, cutoff=NOW)
    assert len(accepted) == 1


def test_original_and_reprint_are_one_news_item_and_one_publisher():
    rows, _ = get()
    assert rows
    original = {'title': 'Other original publisher title', 'text': 'Ventec International Group '+('original statement '*20),
                'date': '2026-09-17', 'link': ORIGINAL, 'source': 'DigiTimes'}
    data = deepcopy(DATA)
    apply_news_freshness(data, records=[*rows, original], cutoff=NOW)
    assert len(data['recent_catalysts']) == 1
    assert data['news_selection']['publisher_count'] == 1
    projected = prompt_evidence_copy(data['recent_catalysts'])
    assert projected[0]['publication_date_basis'] == 'issuer_republication'
    assert projected[0]['original_publisher_publication_date'] is None
    assert '原文發布日期未核對' in projected[0]['summary']


@pytest.mark.parametrize('change', ['date', 'attribution', 'body'])
def test_unverified_original_article_is_not_admitted(change):
    http = Http()
    raw = http.contents[ARTICLE].decode()
    if change == 'date':
        raw = raw.replace('22 九月 2026', '21 九月 2026')
    elif change == 'attribution':
        raw = raw.replace('https://www.digitimes.com/news/', 'https://evil.test/news/')
    else:
        raw = raw.replace('Ventec', 'OtherIssuer')
    http.contents[ARTICLE] = raw.encode()
    rows, audit = get(http)
    assert rows == [] and audit['status'] == 'error'


def test_changed_saved_attribution_fails_typed_gate_even_with_company_alias():
    rows, _ = get()
    assert rows
    for field, value in [('publisher', 'Independent new publisher'), ('original_publisher_publication_date', '2026-09-22'),
                         ('issuer_republication_date', '2026-10-01'), ('link', 'https://evil.test/original')]:
        row = deepcopy(rows[0]); row[field] = value
        accepted, _ = select_company_records([row], DATA, cutoff=NOW)
        assert accepted == []


def test_missing_receipt_cannot_fall_through_to_general_company_alias():
    rows, _ = get()
    assert rows
    row = deepcopy(rows[0]); row.pop('issuer_news_receipt'); row['text'] += ' 騰輝電子-KY'
    accepted, _ = select_company_records([row], DATA, cutoff=NOW)
    assert accepted == []


@pytest.mark.parametrize('invalid',[False,[],0,''])
def test_invalid_saved_identity_is_not_absent_identity(invalid):
    rows,_=get();data=deepcopy(DATA);data['company_identity']=invalid
    from data_fetch.market_sources.issuer_news import verified_issuer_news
    assert verified_issuer_news(rows[0],data,today=NOW.date()) is None


@pytest.mark.parametrize('alias',[' *Ventec* ','<b>Ventec</b>*'])
def test_forbidden_official_alias_keeps_existing_normalization(alias):
    rows,_=get();data=deepcopy(DATA);data['company_identity']['forbidden_aliases']=[alias]
    accepted,_=select_company_records(rows,data,cutoff=NOW)
    assert accepted==[]


def test_direct_domain_publisher_and_reprint_do_not_inflate_publisher_count():
    rows,_=get();data=deepcopy(DATA)
    other={'title':'Different direct article','text':'騰輝電子-KY別篇消息','date':'2026-10-08',
           'link':'https://www.digitimes.com/news/a20261008PD111/other-ventec.html','source':''}
    apply_news_freshness(data,records=[*rows,other],cutoff=NOW)
    assert len(data['recent_catalysts'])==2 and data['news_selection']['publisher_count']==1


def test_fresh_issuer_only_bundle_is_not_mislabelled_as_retained_cache(monkeypatch):
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    import time
    monkeypatch.setattr(time,'time',lambda:NOW.timestamp())
    rows,audit=get();audit.update(source='recent_catalysts',provider='Verified issuer news',fetch_id='test-fresh-issuer')
    data=deepcopy(DATA);data['source_audit']=[audit]
    after=_merge_optional_http_bundle(data,{'issuer_news':rows},refreshed_sources=('recent_catalysts',))
    merged=after['source_audit'][-1]
    assert len(after['recent_catalysts'])==1
    assert merged['cache_hit'] is False and merged['stale'] is False
    assert datetime.fromisoformat(merged['fetched_at']).timestamp()==NOW.timestamp()-60
    assert merged['status']=='degraded_enrichment'  # partial window stays partial


@pytest.mark.parametrize('invalid',['strict_window_boundary','missing_receipt','empty'])
def test_rejected_incoming_issuer_rows_do_not_renew_old_news(invalid,monkeypatch):
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    import time
    monkeypatch.setattr(time,'time',lambda:NOW.timestamp())
    http=Http()
    if invalid=='strict_window_boundary':
        http.contents[INDEX]=http.contents[INDEX].replace(b'22.09.2026',b'10.09.2026')
        http.contents[ARTICLE]=http.contents[ARTICLE].replace('22 九月 2026'.encode(),'10 九月 2026'.encode())
    rows,audit=get(http)
    if invalid=='missing_receipt':rows[0].pop('issuer_news_receipt')
    if invalid=='empty':rows=[]
    old=NOW.timestamp()-86400;data=deepcopy(DATA)
    data['recent_catalysts']=[{'title':'騰輝電子-KY既有新聞','text':'騰輝電子-KY既有事實','date':'2026-10-08',
                             'link':'https://example.com/old','source':'old publisher'}]
    data['source_freshness']={'recent_catalysts':{'fetched_at_epoch':old,'fetched_at':datetime.fromtimestamp(old,timezone.utc).isoformat()}}
    audit.update(source='recent_catalysts',provider='Verified issuer news',fetch_id='rejected-incoming')
    data['source_audit']=[audit]
    after=_merge_optional_http_bundle(data,{'issuer_news':rows},refreshed_sources=('recent_catalysts',))
    assert len(after['recent_catalysts'])==1 and after['recent_catalysts'][0]['link']=='https://example.com/old'
    assert after['source_freshness']['recent_catalysts']['fetched_at_epoch']==old
    assert after['source_audit'][-1]['stale'] is True and after['source_audit'][-1]['cache_hit'] is True
