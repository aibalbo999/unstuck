"""Only dated, individually attributable forum posts may fill empty social context."""
from datetime import datetime, timezone

from data_fetch.market_sources.cmoney_stock_posts import (
    fetch_cmoney_stock_posts, parse_finance_listing, parse_stock_listing, parse_stock_article,
)


NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def listing(ticker="1605", company="華新", article="185070877", stamp="2026-10-02T02:01:01+00:00"):
    return f'''<html><head><title>{ticker} {company} 的模範同學觀點與討論｜股市爆料同學會</title></head>
    <body><a class="sv-disc-row-link" href="https://www.cmoney.tw/forum/article/{article}">
    <time datetime="{stamp}">6 天前</time></a></body></html>'''.encode()


def article(*, tags=("1605華新",), published="2026-10-2T10:1:1+08:00", body="開盤小小加碼幾張。",
            heading="華新 看多", title="💰💰💰"):
    tag_html = ''.join(f'<meta property="article:tag" content="{tag}">' for tag in tags)
    return f'''<html><head><meta property="article:published_time" content="{published}">
    {tag_html}<meta property="og:title" content="{title}"></head>
    <body><h2 class="articleTags__text">{heading}</h2>
    <pre class="textRule__text">{body}</pre></body></html>'''.encode()


def finance_listing(ticker="3023", company="信邦", article_id="185184304"):
    return f'''<html><head><title>{company}({ticker}) 個股概覽 | 個股 - 股市</title></head><body>
    <li id="ForumBlock" stockId="{ticker}"">
    <span class="page-list-title__stockName">{company}</span>討論區
    <article><ul id="ArticleList"><li grp="articleBlock" articleId="{article_id}">
    <p grp="longContent">今天回補缺口不用看了</p>
    <a href="/forum/article/{article_id}" class="trade-time">1天前</a>
    </li></ul></article></li></body></html>'''.encode()


def test_finance_listing_requires_exact_issuer_and_original_article_link():
    company, candidates = parse_finance_listing(finance_listing(), "3023")
    assert company == "信邦"
    assert candidates == [("https://www.cmoney.tw/forum/article/185184304", None)]
    assert parse_finance_listing(finance_listing(ticker="2308"), "3023")[1] == []
    assert parse_finance_listing(finance_listing().replace(b'/forum/article/185184304', b'/forum/article/999999999'), "3023")[1] == []
    unrelated = finance_listing().replace(b'articleId="185184304"', b'articleId="unknown"')
    unrelated += b'<li grp="articleBlock" articleId="185184304"><a href="/forum/article/185184304"></a></li>'
    assert parse_finance_listing(unrelated, "3023")[1] == []


def test_finance_candidate_uses_original_article_date_and_exact_stock_tag():
    company, candidates = parse_finance_listing(finance_listing(), "3023")
    candidate = candidates[0]
    original = article(tags=("3023信邦",), published="2026-10-7T8:23:10+08:00",
                       body="今天回補缺口不用看了", heading="信邦 看多", title="今天回補缺口不用看了")
    record = parse_stock_article(original, "3023", company, candidate, now=NOW)
    assert record is not None and record["date"] == "2026-10-07T00:23:10+00:00"
    assert record["link"] == candidate[0]
    assert parse_stock_article(article(tags=("2308台達電",), published="2026-10-7T8:23:10+08:00"),
                               "3023", company, candidate, now=NOW) is None
    assert parse_stock_article(article(tags=("3023信邦",), published="2026-08-7T8:23:10+08:00",
                                       heading="信邦 看多"), "3023", company, candidate, now=NOW) is None


def test_finance_page_recovers_when_forum_listing_has_no_recent_posts(monkeypatch):
    from data_fetch.market_sources import cmoney_stock_posts as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    original = article(tags=("3023信邦",), published="2026-10-7T8:23:10+08:00",
                       body="今天回補缺口不用看了", heading="信邦 看多")
    pages = {
        source.STOCK_URL.format(ticker="3023"): listing(ticker="3023", company="信邦", stamp="2026-08-01T02:01:01+00:00"),
        "https://www.cmoney.tw/finance/3023/f00025": finance_listing(),
        "https://www.cmoney.tw/forum/article/185184304": original,
    }
    monkeypatch.setattr(source, "_download", lambda url, **_kwargs: pages[url])
    monkeypatch.setattr(source, "_now", lambda: NOW)
    rows = fetch_cmoney_stock_posts("3023")
    assert len(rows) == 1
    assert rows[0]["link"] == "https://www.cmoney.tw/forum/article/185184304"
    assert rows[0]["sentiment_assessment"] == "not_assessed"


def test_finance_original_is_checked_before_empty_forum_listing(monkeypatch):
    from data_fetch.market_sources import cmoney_stock_posts as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(source, "_now", lambda: NOW)
    finance_url = source.FINANCE_URL.format(ticker="2912")
    article_url = "https://www.cmoney.tw/forum/article/185201404"
    pages = {
        finance_url: finance_listing(ticker="2912", company="統一超", article_id="185201404"),
        article_url: article(tags=("2912統一超",), published="2026-10-7T12:47:08+08:00",
                             body="門市銷售比上季穩定。", heading="統一超 看多"),
        source.STOCK_URL.format(ticker="2912"): listing(ticker="2912", company="統一超",
                                                        stamp="2026-08-01T02:01:01+00:00"),
    }
    calls = []

    def download(url, **_kwargs):
        calls.append(url)
        return pages[url]

    monkeypatch.setattr(source, "_download", download)
    rows = fetch_cmoney_stock_posts("2912")
    assert [row["link"] for row in rows] == [article_url]
    assert calls == [finance_url, article_url]


def test_dated_forum_listing_remains_fallback_when_finance_has_no_article(monkeypatch):
    from data_fetch.market_sources import cmoney_stock_posts as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(source, "_now", lambda: NOW)
    finance_url = source.FINANCE_URL.format(ticker="1605")
    stock_url = source.STOCK_URL.format(ticker="1605")
    article_url = "https://www.cmoney.tw/forum/article/185070877"
    pages = {
        finance_url: '<title>華新(1605) 個股概覽 | 個股 - 股市</title>'.encode(),
        stock_url: listing(),
        article_url: article(),
    }
    calls = []
    monkeypatch.setattr(source, "_download", lambda url, **_kwargs: calls.append(url) or pages[url])
    rows = fetch_cmoney_stock_posts("1605")
    assert [row["link"] for row in rows] == [article_url]
    assert calls == [finance_url, stock_url, article_url]


def test_cmoney_download_stops_at_shared_deadline_before_network(monkeypatch):
    import pytest
    from data_fetch.market_sources import cmoney_stock_posts as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    with pytest.raises(TimeoutError):
        source._download(source.FINANCE_URL.format(ticker="3023"), deadline=source.time.monotonic() - 1)


def test_finance_listing_checks_later_original_after_three_rejected_candidates(monkeypatch):
    from data_fetch.market_sources import cmoney_stock_posts as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(source, "_now", lambda: NOW)
    ids = ("185288177", "185238679", "185205680", "185203210", "185171589")
    items = ''.join(f'<li grp="articleBlock" articleId="{item}"><a href="/forum/article/{item}">1天前</a></li>'
                    for item in ids)
    finance = (f'<title>統一證(2855) 個股概覽 | 個股 - 股市</title>'
               f'<li id="ForumBlock" stockId="2855""><span class="page-list-title__stockName">統一證</span>討論區'
               f'<article><ul id="ArticleList">{items}</ul></article></li>').encode()
    pages = {
        source.STOCK_URL.format(ticker="2855"): listing(ticker="2855", company="統一證", stamp="2026-08-01T02:01:01+00:00"),
        source.FINANCE_URL.format(ticker="2855"): finance,
        **{f'https://www.cmoney.tw/forum/article/{item}': article(tags=("2855統一證",),
             published="2026-10-7T13:15:58+08:00", heading="統一證 看多",
             body="https://example.com/轉貼") for item in ids[:3]},
        f'https://www.cmoney.tw/forum/article/{ids[3]}': article(tags=("2855統一證",),
             published="2026-10-7T13:15:58+08:00", heading="統一證 看多", body="大戶棄守了嗎？營收是不好嗎"),
        f'https://www.cmoney.tw/forum/article/{ids[4]}': article(tags=("2855統一證", "6005群益證"),
             published="2026-10-7T13:15:58+08:00", heading="統一證 看多", body="兩家券商都有變化"),
    }
    monkeypatch.setattr(source, "_download", lambda url, **_kwargs: pages[url])
    rows = fetch_cmoney_stock_posts("2855")
    assert [row["link"] for row in rows] == [f'https://www.cmoney.tw/forum/article/{ids[3]}']


def test_transient_original_download_is_retried_after_both_indexes_are_exhausted(monkeypatch):
    from data_fetch.market_sources import cmoney_stock_posts as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(source, "_now", lambda: NOW)
    finance_url = source.FINANCE_URL.format(ticker="2912")
    stock_url = source.STOCK_URL.format(ticker="2912")
    article_url = "https://www.cmoney.tw/forum/article/185201404"
    calls = []

    def download(url, **_kwargs):
        calls.append(url)
        if url == finance_url:
            return finance_listing(ticker="2912", company="統一超", article_id="185201404")
        if url == stock_url:
            return listing(ticker="2912", company="統一超", stamp="2026-08-01T02:01:01+00:00")
        if calls.count(article_url) == 1:
            raise RuntimeError("transient original download failure")
        return article(tags=("2912統一超",), published="2026-10-7T12:47:08+08:00",
                       body="門市銷售比上季穩定。", heading="統一超 看多")

    monkeypatch.setattr(source, "_download", download)
    rows = fetch_cmoney_stock_posts("2912")
    assert [row["link"] for row in rows] == [article_url]
    assert calls == [finance_url, article_url, stock_url, article_url]


def test_rejected_original_content_is_not_retried_as_a_transport_failure(monkeypatch):
    from data_fetch.market_sources import cmoney_stock_posts as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "0")
    monkeypatch.setattr(source, "_now", lambda: NOW)
    finance_url = source.FINANCE_URL.format(ticker="2912")
    stock_url = source.STOCK_URL.format(ticker="2912")
    article_url = "https://www.cmoney.tw/forum/article/185201404"
    calls = []

    def download(url, **_kwargs):
        calls.append(url)
        if url == finance_url:
            return finance_listing(ticker="2912", company="統一超", article_id="185201404")
        if url == stock_url:
            return listing(ticker="2912", company="統一超", stamp="2026-08-01T02:01:01+00:00")
        return article(tags=("2308台達電",), published="2026-10-7T12:47:08+08:00",
                       body="門市銷售比上季穩定。", heading="統一超 看多")

    monkeypatch.setattr(source, "_download", download)
    assert fetch_cmoney_stock_posts("2912") == []
    assert calls == [finance_url, article_url, stock_url]


def test_exact_single_stock_post_with_matching_list_and_article_times_is_admitted():
    company, candidates = parse_stock_listing(listing(), "1605", now=NOW)
    assert company == "華新" and len(candidates) == 1
    record = parse_stock_article(article(), "1605", company, candidates[0], now=NOW)
    assert record["date"] == "2026-10-02T02:01:01+00:00"
    assert record["link"] == "https://www.cmoney.tw/forum/article/185070877"
    assert record["text"] == "開盤小小加碼幾張。"
    assert record["source_tag"] == "1605華新"


def test_wrong_issuer_multi_stock_or_unrelated_list_timestamp_does_not_count():
    company, candidates = parse_stock_listing(listing(), "1605", now=NOW)
    candidate = candidates[0]
    assert parse_stock_article(article(tags=("1605華新", "TWA00加權指數")), "1605", company, candidate, now=NOW) is None
    assert parse_stock_article(article(tags=("2308台達電",)), "1605", company, candidate, now=NOW) is None
    assert parse_stock_article(article(published="2026-10-1T10:1:1+08:00"), "1605", company, candidate, now=NOW) is None
    assert parse_stock_article(article(body="https://example.com/full-story"), "1605", company, candidate, now=NOW) is None


def test_multitag_post_requires_explicit_target_only_original_body():
    company, candidates = parse_stock_listing(
        listing(ticker="2002", company="中鋼", article="185096463"), "2002", now=NOW
    )
    candidate = candidates[0]
    tags = ("2002中鋼", "2014中鴻", "2027大成鋼")
    original = article(tags=tags, body="中鋼這次的價格已反映我的預期。", heading="中鋼 看多")
    admitted = parse_stock_article(original, "2002", company, candidate, now=NOW)
    assert admitted is not None
    assert admitted["source_tag"] == "2002中鋼"
    assert admitted["source_tags"] == list(tags)
    assert admitted["evidence_kind"] == "explicit_target_multitag_forum_post"
    assert admitted["sentiment_assessment"] == "not_assessed"
    assert parse_stock_article(article(tags=tags, body="中鋼與中鴻都有變化。", heading="中鋼 看多"),
                               "2002", company, candidate, now=NOW) is None
    assert parse_stock_article(article(tags=tags, body="這次價格已反映我的預期。", heading="中鋼 看多"),
                               "2002", company, candidate, now=NOW) is None
    assert parse_stock_article(article(tags=("2002中鋼", "TWA00加權指數"), body="中鋼近期走強。", heading="中鋼 看多"),
                               "2002", company, candidate, now=NOW) is None


def test_stale_future_or_unidentified_stock_listing_is_not_a_recovery():
    assert parse_stock_listing(listing(stamp="2026-08-01T02:01:01+00:00"), "1605", now=NOW)[1] == []
    assert parse_stock_listing(listing(stamp="2026-10-10T02:01:01+00:00"), "1605", now=NOW)[1] == []
    assert parse_stock_listing(listing(ticker="2330"), "1605", now=NOW)[1] == []
    assert parse_stock_listing(listing(company=""), "1605", now=NOW)[1] == []
    assert parse_stock_listing(listing(stamp="2026-10-02T02:01:01"), "1605", now=NOW)[1] == []


def test_provider_counts_verified_forum_fallback_only_when_other_channels_are_empty(monkeypatch):
    import news_fetchers
    from data_fetch.agent_context_providers import SocialSentimentProvider
    from data_fetch.market_sources import cmoney_stock_posts
    from data_fetch.types import FetchRequest
    from data_trust_audit import source_record_count
    from source_content_selection import reselect_social_context

    monkeypatch.setattr(news_fetchers, "fetch_google_news_rss", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(news_fetchers, "fetch_ptt_stock_sentiment", lambda *_args, **_kwargs: [])
    calls = []
    record = parse_stock_article(article(), "1605", "華新",
                                 parse_stock_listing(listing(), "1605", now=NOW)[1][0], now=NOW)
    monkeypatch.setattr(cmoney_stock_posts, "fetch_cmoney_stock_posts", lambda ticker: calls.append(ticker) or [record])
    data = {"ticker": "1605.TW", "company_name": "華新", "company_identity": {"display_name": "華新"}}
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker("1605.TW"), {"data": data})
    assert calls == ["1605"]
    assert result.audit["record_count"] == 1
    assert source_record_count("social_sentiment", {"social_sentiment": result.value}) == 1
    assert result.value["sentiment_assessment"] == "not_assessed"
    snapshot = {**data, "social_sentiment": result.value}
    reselect_social_context(snapshot)
    assert len(snapshot["social_sentiment"]["cmoney_stock_direct"]) == 1


def test_verified_cmoney_original_avoids_empty_ptt_request(monkeypatch):
    import news_fetchers
    from data_fetch.agent_context_providers import SocialSentimentProvider
    from data_fetch.market_sources import cmoney_stock_posts
    from data_fetch.types import FetchRequest

    calls = []
    record = parse_stock_article(article(), "1605", "華新",
                                 parse_stock_listing(listing(), "1605", now=NOW)[1][0], now=NOW)
    monkeypatch.setattr(cmoney_stock_posts, "fetch_cmoney_stock_posts", lambda ticker: calls.append("cmoney") or [record])
    monkeypatch.setattr(news_fetchers, "fetch_ptt_stock_sentiment", lambda *a, **k: calls.append("ptt") or [])
    result = SocialSentimentProvider()._fetch_uncached(
        FetchRequest.from_ticker("1605.TW"),
        {"data": {"ticker": "1605.TW", "company_name": "華新"}},
    )
    assert calls == ["cmoney"]
    assert result.status == "success"
    assert result.value["sample_count"] == 1
    assert result.value["ptt_stock_direct"] == []
    assert len(result.value["cmoney_stock_direct"]) == 1
