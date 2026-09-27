from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import news_fetchers
import pytest

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=news_fetchers.TAIPEI_TZ)
RECENT = int(datetime(2026, 9, 15, 11, 44, tzinfo=news_fetchers.TAIPEI_TZ).timestamp())


def article_path(stamp=RECENT):
    return f'/bbs/Stock/M.{stamp}.A.ABC.html'


def search_html(rows):
    return '<div class="r-list-container">' + ''.join(
        f'<div class="r-ent"><div class="title"><a href="{path}">{title}</a></div><div class="date">9/15</div></div>'
        for path, title in rows) + '</div>'


def article_html(title='[標的] 5314 世紀', stamp='Tue Sep 15 11:44:41 2026'):
    return '<div id="main-content">' + ''.join(
        f'<div class="article-metaline"><span class="article-meta-tag">{key}</span><span class="article-meta-value">{value}</span></div>'
        for key, value in [('標題', title), ('時間', stamp)]) + '可驗證的公開文章</div>'


@pytest.fixture
def runtime(monkeypatch):
    calls, events, failures = [], [], []
    monkeypatch.setattr(news_fetchers, '_current_taipei_datetime', lambda: NOW)
    monkeypatch.setattr(news_fetchers, 'cooldown_state', lambda _: {})
    monkeypatch.setattr(news_fetchers, 'record_observation', lambda *a, **kw: events.append(kw))
    monkeypatch.setattr(news_fetchers, 'remember_failure', lambda key, exc: failures.append(exc) or {'error_kind': getattr(exc, 'error_kind', 'transport_error')})
    def install(responses):
        def get(url, **kwargs):
            calls.append((url, kwargs))
            value = responses[len(calls) - 1]
            if isinstance(value, BaseException):
                raise value
            return SimpleNamespace(text=value, content=value.encode(), status_code=200)
        monkeypatch.setattr(news_fetchers, 'sync_get', get)
    return install, calls, events, failures


def test_search_finds_recent_article_outside_latest_index(runtime):
    install, calls, events, failures = runtime
    install([search_html([(article_path(), '[標的] 5314 世紀')]), article_html()])
    rows = news_fetchers.fetch_ptt_stock_sentiment('5314.TWO', limit=5)
    assert len(rows) == 1
    assert calls[0][0] == 'https://www.ptt.cc/bbs/Stock/search?q=5314'
    assert rows[0]['published_date'] == '2026-09-15T11:44:41+08:00'
    assert calls[1][0] == 'https://www.ptt.cc' + article_path()
    assert events[-1]['outcome'] == 'results'
    assert events[-1]['details']['component_statuses']['article_1']['response_sha256']
    assert not failures


def test_old_search_hits_never_gain_current_year_from_mmdd(runtime):
    install, calls, events, failures = runtime
    old = int((NOW - timedelta(days=730)).timestamp())
    install([search_html([(article_path(old), '[標的] 5314 世紀')])])
    assert news_fetchers.fetch_ptt_stock_sentiment('5314') == []
    assert len(calls) == 1
    assert events[-1]['outcome'] == 'valid_empty'
    assert events[-1]['details']['rejected_reason_counts']['historical_candidate'] == 1


@pytest.mark.parametrize('stamp', ['', 'Tue Sep 15 11:44:41 2025', 'Mon Sep 28 11:44:41 2026'])
def test_article_meta_missing_stale_or_future_not_promoted(runtime, stamp):
    install, calls, events, failures = runtime
    install([search_html([(article_path(), '[標的] 5314 世紀')]), article_html(stamp=stamp)])
    assert news_fetchers.fetch_ptt_stock_sentiment('5314') == []
    assert events[-1]['outcome'] == 'valid_empty'


def test_at_most_five_same_host_articles_and_exact_stock_boundary(runtime):
    install, calls, events, failures = runtime
    listed = [('https://evil.example/bbs/Stock/M.1789443883.A.ABC.html', '5314 世紀'),
              (article_path(), '15314 unrelated')]
    listed += [(article_path(RECENT + i), '5314 世紀') for i in range(8)]
    install([search_html(listed)] + [article_html()] * 5)
    assert len(news_fetchers.fetch_ptt_stock_sentiment('5314', limit=50)) == 5
    assert len(calls) == 6
    assert all(url.startswith('https://www.ptt.cc/bbs/Stock/') for url, _ in calls)


def test_rejection_stops_requests_and_does_not_return_partial_success(runtime):
    install, calls, events, failures = runtime
    response = httpx.Response(403, request=httpx.Request('GET', 'https://www.ptt.cc'))
    error = httpx.HTTPStatusError('forbidden', request=response.request, response=response)
    install([search_html([(article_path(RECENT + i), '5314 世紀') for i in range(3)]), article_html(), error])
    assert news_fetchers.fetch_ptt_stock_sentiment('5314') == []
    assert len(calls) == 3
    assert events[-1]['outcome'] == 'failure'
    assert events[-1]['details']['component_statuses']['article_1']['response_sha256']
    assert events[-1]['details']['component_statuses']['article_2']['http_status'] == 403
    assert failures


def test_shared_deadline_stops_before_next_request(runtime, monkeypatch):
    install, calls, events, failures = runtime
    ticks = iter([0, 0, 0, 9, 9, 9, 9])
    monkeypatch.setattr(news_fetchers.time, 'monotonic', lambda: next(ticks, 9))
    install([search_html([(article_path(), '5314 世紀')]), article_html()])
    assert news_fetchers.fetch_ptt_stock_sentiment('5314') == []
    assert len(calls) == 1
    assert events[-1]['outcome'] == 'failure'


def test_prior_cooldown_blocks_search_without_renewing(runtime, monkeypatch):
    install, calls, events, failures = runtime
    install([])
    keys = []
    monkeypatch.setattr(news_fetchers, 'cooldown_state', lambda key: keys.append(key) or {'retry_at': 99})
    assert news_fetchers.fetch_ptt_stock_sentiment('5314') == []
    assert not calls and not failures
    assert ':stock_index:' in keys[0]
    assert events[-1]['outcome'] == 'cooldown'


def test_unknown_article_path_has_no_invented_current_year(runtime):
    install, calls, events, failures = runtime
    install([search_html([('/bbs/Stock/M.unknown.A.ABC.html', '5314 世紀')])])
    assert news_fetchers.fetch_ptt_stock_sentiment('5314') == []
    assert len(calls) == 1
    assert events[-1]['details']['rejected_reason_counts'] == {'invalid_article_url': 1}


def test_changed_article_identity_not_accepted_from_search_title(runtime):
    install, calls, events, failures = runtime
    install([search_html([(article_path(), '5314 世紀')]), article_html(title='[標的] 15314 unrelated')])
    assert news_fetchers.fetch_ptt_stock_sentiment('5314') == []
    assert events[-1]['details']['rejected_reason_counts'] == {'ticker_mismatch': 1}


def test_unrecognized_search_page_is_failure_not_empty(runtime):
    install, calls, events, failures = runtime
    install(['<html>Challenge verification</html>'])
    assert news_fetchers.fetch_ptt_stock_sentiment('5314') == []
    assert len(calls) == 1 and failures
    assert events[-1]['outcome'] == 'failure'
    assert events[-1]['details']['component_statuses']['search']['response_sha256']


def test_final_response_after_deadline_is_not_success(runtime, monkeypatch):
    install, calls, events, failures = runtime
    ticks = iter([0, 0, 0, 1, 9, 9])
    monkeypatch.setattr(news_fetchers.time, 'monotonic', lambda: next(ticks, 9))
    install([search_html([(article_path(), '5314 世紀')]), article_html()])
    assert news_fetchers.fetch_ptt_stock_sentiment('5314') == []
    assert len(calls) == 2 and failures
    assert events[-1]['outcome'] == 'failure'
