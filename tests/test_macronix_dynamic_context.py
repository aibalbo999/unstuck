"""Different real quarters must flow through the normal collector and receipt chain."""
from pathlib import Path
import base64
import csv
from hashlib import sha256
import importlib
import io
import time
import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/evidence/source-acquisition'
Q1_URL = 'https://www.macronix.com/Lists/QuarterlyResults/Attachments/652/2026q1%20webcast_ppt_en.pdf'
YEARS_URL = 'https://www.macronix.com/_layouts/15/zMacronixPortal2016/getColumnListByLanguageJson.aspx?listName=QuarterlyResults&selectColumn=Year&lan=EN'
MAY = 1777680000.  # 2026-05-02, after the real April 27 Q1 event.


@pytest.fixture
def dynamic_http(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch.market_sources import official_issuer_master
    s = importlib.import_module('data_fetch.market_sources.macronix_conference')
    t = importlib.import_module('data_fetch.market_sources.macronix_conference_transport')
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: MAY)
    master = (EVIDENCE / '20261013/delta-transcript-integration/master.body').read_bytes()
    rows = list(csv.DictReader(io.StringIO(master.decode('utf-8-sig'))))
    # Only the identity service is a dated fixture; both quarterly PDFs and
    # the published complete quarterly index are the saved real originals.
    for row in rows:
        row['出表日期'] = '1150501'
    out = io.StringIO(); writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    bodies = {
        t.MASTER_URL: out.getvalue().encode('utf-8-sig'),
        t.INDEX_URL: (EVIDENCE / '20261015/macronix-dynamic-originals/results.body').read_bytes(),
        t.PDF_URL: (EVIDENCE / '20261015/macronix-dynamic-originals/presentation.body').read_bytes(),
        Q1_URL: (EVIDENCE / '20261016/macronix-quarter-fixture/q1.body').read_bytes(),
        YEARS_URL: (EVIDENCE / '20261015/macronix-dynamic-originals/years.body').read_bytes(),
    }
    calls = []
    def download(self, url, diagnostic):
        raw = bodies[url]; calls.append(url); self.http_request_count += 1
        kind = 'text/csv' if url == t.MASTER_URL else 'application/pdf' if url.endswith('.pdf') else 'text/html'
        meta = dict(http_status=200, effective_url=url, num_redirects=0, size_download=len(raw),
                    content_type=kind, content_length=len(raw), method='GET', proxy_used=0,
                    cache_control='private, no-store, no-cache')
        if url == t.MASTER_URL:
            meta = official_issuer_master.master_metadata(meta, raw, {})
        else:
            meta.update(pragma='', expires='', age=None, cf_cache_status='')
        diagnostic.update(http_request_sent=True, http_status=200, response_metadata=meta)
        return dict(url=url, body_b64=base64.b64encode(raw).decode(), sha256=sha256(raw).hexdigest(),
                    **t.request_spec(url), response_metadata=meta)
    monkeypatch.setattr(t.ConferenceHttp, 'download_original', download)
    yield s, t, bodies, calls
    cache_store.reset_cache_store_for_tests()


def test_real_first_quarter_is_selected_parsed_and_projected(dynamic_http):
    from conference_presentation_prompt import presentation_prompt_context
    s, t, bodies, calls = dynamic_http
    diagnostics = {}
    value = s.fetch_macronix_context(s.TICKER, diagnostics=diagnostics)
    assert value['period'] == '2026Q1' and value['date'] == '2026-04-27'
    assert value['documents'][0]['page_count'] == 21
    assert value['documents'][0]['content_sha256'] == sha256(bodies[Q1_URL]).hexdigest()
    assert Q1_URL in calls and t.PDF_URL not in calls and YEARS_URL in calls
    assert s.verify_context(value, s.TICKER, max_age=1800)
    for role in (3, 5, 12):
        shown = presentation_prompt_context(value, role)['documents'][0]
        assert shown['content_period'] == '2026Q1'
        assert len(shown['pages']) >= 3
        assert any('Quarterly Financial Results' in p['text'] for p in shown['pages'])
        assert shown['financial_statement_complete'] is False


def test_agent_roles_use_private_chain_then_remove_receipts(dynamic_http):
    from agent_runtime.prompting import data_for_agent_prompt
    s, _, _, _ = dynamic_http
    value = s.fetch_macronix_context(s.TICKER)
    for role in (3, 5, 12):
        projected = data_for_agent_prompt(role, {'ticker': s.TICKER, 'earnings_call': value})
        shown = projected['conference_presentation']['documents'][0]
        assert shown['content_period'] == '2026Q1'
        assert [p['page_number'] for p in shown['pages']] == [1, 2, 6]
        assert 'macronix_conference_receipt' not in repr(projected)
    assert 'conference_presentation' not in data_for_agent_prompt(20, {'ticker': s.TICKER, 'earnings_call': value})


@pytest.mark.parametrize('change', ['number', 'receipt', 'selected', 'date', 'role', 'marker'])
def test_dynamic_context_and_prompt_refuse_original_mismatch(dynamic_http, change):
    from copy import deepcopy
    from conference_presentation_prompt import presentation_prompt_context
    s, _, _, _ = dynamic_http
    value = deepcopy(s.fetch_macronix_context(s.TICKER))
    doc = value['documents'][0]
    if change == 'number':
        doc['pages'][5]['text'] = doc['pages'][5]['text'].replace('10,469', '99,999')
    elif change == 'receipt':
        value.pop('macronix_conference_receipt')
    elif change == 'selected':
        value['macronix_conference_receipt']['selected']['selected_row']['Id'] = '999'
    elif change == 'date':
        doc['event_date'] = '2026-04-28'
    elif change == 'role':
        doc['role_page_allowlist'].append(14)
    else:
        value['source'] = 'renamed'; doc['source'] = 'renamed'
    assert not s.verify_context(value, s.TICKER, max_age=1800)
    assert not presentation_prompt_context(value, 3)


def test_dynamic_native_requests_require_actual_published_predecessor(dynamic_http):
    from search_provider_runtime import SourceResponseError
    s, t, _, calls = dynamic_http
    http = t.ConferenceHttp(time.monotonic()+25, dynamic=True)
    for url in (t.INDEX_URL, Q1_URL, t.PDF_URL):
        with pytest.raises(SourceResponseError):
            http.get_receipt(url)
    assert not calls
    _, years = http.get_receipt(YEARS_URL)
    with pytest.raises(SourceResponseError):
        http.authorize_index(2025, years)
    raw, idx = http.get_receipt(http.authorize_index(2026, years))
    from data_fetch.market_sources import macronix_presentation_index as index
    selected = index.select_presentation(raw, MAY, index_year=2026)
    assert http.authorize_presentation(selected, idx) == Q1_URL
    with pytest.raises(SourceResponseError):
        http.get_receipt(t.PDF_URL)
    assert calls == [YEARS_URL, t.INDEX_URL]


def test_latest_past_without_attachment_does_not_reuse_an_older_quarter(dynamic_http):
    import json
    from search_provider_runtime import SourceResponseError
    s, t, bodies, calls = dynamic_http
    rows = json.loads(bodies[t.INDEX_URL]); rows[0]['webcast_PPT'] = None
    bodies[t.INDEX_URL] = json.dumps(rows).encode()
    with pytest.raises(SourceResponseError):
        s.fetch_macronix_context(s.TICKER)
    assert Q1_URL not in calls and t.PDF_URL not in calls


def test_dynamic_originals_remain_historical_content_after_expiry(dynamic_http, monkeypatch):
    from conference_presentation_prompt import presentation_prompt_context
    from data_fetch.market_sources.macronix_dynamic_presentation import verify_for_projection
    s, _, _, _ = dynamic_http
    value = s.fetch_macronix_context(s.TICKER)
    monkeypatch.setattr(time, 'time', lambda: MAY+400*86400)
    assert not s.verify_context(value, s.TICKER, max_age=1800)
    assert verify_for_projection(value)
    assert presentation_prompt_context(value, 3)['documents'][0]['content_period'] == '2026Q1'


@pytest.mark.parametrize('current_published', [True, False])
def test_year_rollover_never_hides_unpublished_latest_past_event(dynamic_http, monkeypatch, current_published):
    import json
    from search_provider_runtime import SourceResponseError
    from data_fetch.market_sources import macronix_presentation_index as index
    s, t, bodies, calls = dynamic_http
    january = 1799107200.  # 2027-01-05 local.
    monkeypatch.setattr(time, 'time', lambda: january)
    bodies[t.MASTER_URL] = bodies[t.MASTER_URL].replace(b'1150501', b'1160104')
    years = json.loads(bodies[YEARS_URL])
    if current_published:
        years.append('2027'); bodies[index.index_url(2027)] = b'[]'
    bodies[YEARS_URL] = json.dumps(years).encode()
    with pytest.raises(SourceResponseError):
        s.fetch_macronix_context(s.TICKER)
    assert calls.count(t.INDEX_URL) == 1
    assert calls.count(index.index_url(2027)) == int(current_published)
    assert Q1_URL not in calls and t.PDF_URL not in calls


@pytest.mark.parametrize('mode', ['expiry', 'deadline'])
def test_final_replay_or_delivery_cannot_outlive_budget(dynamic_http, monkeypatch, mode):
    from search_provider_runtime import SourceResponseError
    from data_fetch.market_sources import macronix_dynamic_presentation as dynamic
    s, _, _, _ = dynamic_http
    real = dynamic.verify_context
    def delayed(*args, **kwargs):
        valid = real(*args, **kwargs)
        if mode == 'expiry':
            monkeypatch.setattr(time, 'time', lambda: MAY+1800)
        else:
            monkeypatch.setattr(time, 'monotonic', lambda: kwargs['deadline']+1)
        return valid
    monkeypatch.setattr(dynamic, 'verify_context', delayed)
    diag = {}
    with pytest.raises(SourceResponseError) as caught:
        s.fetch_macronix_context(s.TICKER, diagnostics=diag)
    assert caught.value.error_kind == ('timeout' if mode == 'deadline' else 'original_expired')
    assert diag['macronix_originals_verified'] is False
    assert 'fetched_at_epoch' not in diag and 'cache_hit' not in diag


def test_legacy_v1_original_and_role_pages_still_replay(dynamic_http, monkeypatch):
    from test_macronix_conference import NOW
    from conference_presentation_prompt import presentation_prompt_context
    s, t, bodies, calls = dynamic_http
    monkeypatch.setattr(time, 'time', lambda: NOW)
    bodies[t.MASTER_URL] = (EVIDENCE / '20261013/delta-transcript-integration/master.body').read_bytes()
    value = s._fetch_legacy_context(s.TICKER)
    assert value['macronix_conference_receipt']['policy'] == s.POLICY
    assert s.verify_context(value, s.TICKER, max_age=1800)
    assert len(calls) == 3
    assert [p['page_number'] for p in presentation_prompt_context(value, 3)['documents'][0]['pages']] == [1,2,7,8,12]


def test_published_new_attachment_id_does_not_lock_known_q2_to_old_url(dynamic_http, monkeypatch):
    """Synthetic new official row, real Q2 bytes: tests binding, not live publication."""
    import json
    from test_macronix_conference import NOW
    s, t, bodies, calls = dynamic_http
    monkeypatch.setattr(time, 'time', lambda: NOW)
    bodies[t.MASTER_URL] = (EVIDENCE / '20261013/delta-transcript-integration/master.body').read_bytes()
    rows = json.loads(bodies[t.INDEX_URL]); rows[1]['Id'] = '777'
    bodies[t.INDEX_URL] = json.dumps(rows).encode()
    new_url = t.PDF_URL.replace('/656/', '/777/')
    bodies[new_url] = bodies[t.PDF_URL]
    value = s.fetch_macronix_context(s.TICKER)
    assert value['documents'][0]['url'] == new_url
    assert value['documents'][0]['role_page_allowlist'] == [1,2,7,8,12]
    assert t.PDF_URL not in calls and new_url in calls
    assert s.verify_context(value, s.TICKER, max_age=1800)
