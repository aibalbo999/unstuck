"""Complete monthly MOPS indexes must recover a real 41-announcement window."""
from datetime import datetime
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import httpx
import pytest

from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements

NOW = datetime(2026, 10, 9, 13, tzinfo=ZoneInfo("Asia/Taipei"))
INDEX = "https://wwwc.twse.com.tw/rwd/zh/IIH/company/events"
JSON_INDEX = "https://mops.twse.com.tw/mops/api/t05st01"
FIXTURES = Path(__file__).parent / "fixtures/source_acquisition"


def monthly_indexes():
    return [json.loads((FIXTURES / f"mops_2891_20261009_month_{month}.json").read_text())
            for month in ("09", "10")]


def responses(*, corrupt_month=None, detail_error=None):
    months = monthly_indexes()
    candidates = []
    for month in months:
        for code, company, day, clock, title, action in month["result"]["data"]:
            params = action["parameters"]
            date = str(int(day[:3]) + 1911) + day[4:6] + day[7:9]
            link = ("https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1?firstin=true&stp=1&step=1"
                    f"&SEQ_NO={params['serialNumber']}&SPOKE_TIME={clock.replace(':', '')}"
                    f"&SPOKE_DATE={date}&COMPANY_ID={code}")
            candidates.append((link, code, company, day, clock, title))
    by_link = {r[0]: r for r in candidates}
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        req = httpx.Request("GET", url)
        if url == INDEX:
            news = [{"companyId": code, "companyName": company, "date": day,
                     "time": clock[:5], "subject": title, "link": link}
                    for link, code, company, day, clock, title in sorted(candidates, reverse=True)[:10]]
            return httpx.Response(200, request=req, json={
                "info": {"status": "success", "data": {"code": "2891"}}, "news": news})
        if detail_error:
            raise detail_error
        _, code, company, day, clock, title = by_link[url]
        from html import escape
        body = "公開原文的說明內容足夠長，仍需核對發行人、日期、時間與公告主旨。"
        html = (f"<table class='noBorder'><tr class='compName'><td>(上市公司) {code} {company}</td></tr></table>"
                "<table class='hasBorder'>"
                f"<tr><th>發言日期</th><td>{day}</td><th>發言時間</th><td>{clock}</td></tr>"
                f"<tr><th>主旨</th><td>{escape(title)}</td></tr>"
                f"<tr><th>說明</th><td>{body}</td></tr></table>")
        return httpx.Response(200, request=req, text=html)

    def post(url, **kwargs):
        calls.append(url)
        if url == JSON_INDEX:
            month = months[int(kwargs["json"]["month"]) - 9]
            if corrupt_month:
                month = corrupt_month(json.loads(json.dumps(month)))
            return httpx.Response(200, request=httpx.Request("POST", url), json=month)
        rows = [{"COMPANY_ID": code, "COMPANY_NAME": company, "TYPEK": "上市", "CDATE": day,
                 "CTIME": clock, "AN_CODE": "M99", "SUBJECT": title, "HYPERLINK": link}
                for link, code, company, day, clock, title in candidates]
        return httpx.Response(200, request=httpx.Request("POST", url), json={"status": "success", "data": rows})
    return get, post, calls, by_link


def test_real_monthly_41_record_window_is_not_truncated_at_30_or_ten():
    get, post, calls, by_link = responses()
    rows, audit = fetch_recent_company_announcements("2891.TW", now=NOW, get=get, post=post)
    assert len(rows) == 41, audit
    assert {r["link"] for r in rows} == set(by_link)
    assert audit["coverage_status"] == "window_complete"
    assert audit["status"] == "success"
    assert calls.count(JSON_INDEX) == 2
    assert len([u for u in calls if "ajax_t05sr01_1" in u]) == 41


@pytest.mark.parametrize("corruption", ["issuer", "market", "action", "duplicate", "subject"])
def test_invalid_monthly_index_never_closes_the_window(corruption):
    def corrupt(p):
        r = p["result"]
        if corruption == "issuer":
            r["companyId"] = "2881"
        elif corruption == "market":
            r["marketName"] = "上櫃公司"
        elif corruption == "action":
            r["data"][0][5]["parameters"]["companyId"] = "2881"
        elif corruption == "duplicate":
            r["data"].append(r["data"][0])
        else:
            r["data"][0][4] = ""
        return p
    get, post, calls, _ = responses(corrupt_month=corrupt)
    rows, audit = fetch_recent_company_announcements("2891.TW", now=NOW, get=get, post=post)
    assert audit["coverage_status"] == "partial"
    assert audit["status"] != "success"
    assert len(rows) <= 10


def test_a_refused_detail_stops_further_requests_and_keeps_partial_coverage():
    req = httpx.Request("GET", "https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1")
    response = httpx.Response(429, request=req, headers={"Retry-After": "3600"})
    get, post, calls, _ = responses(detail_error=httpx.HTTPStatusError("rate limited", request=req, response=response))
    rows, audit = fetch_recent_company_announcements("2891.TW", now=NOW, get=get, post=post)
    assert rows == []
    assert audit["coverage_status"] == "partial"
    assert len([u for u in calls if "ajax_t05sr01_1" in u]) == 1


def test_expired_shared_deadline_stops_the_detail_loop(monkeypatch):
    from data_fetch.market_sources import twse_company_history as source
    clock = [0.]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    get, post, calls, _ = responses()
    def slow_get(url, **kwargs):
        result = get(url, **kwargs)
        if "ajax_t05sr01_1" in url:
            clock[0] += 6
        return result
    rows, audit = fetch_recent_company_announcements("2891.TW", now=NOW, get=slow_get, post=post)
    assert 0 < len(rows) < 41
    assert audit["coverage_status"] == "partial"
    assert len([u for u in calls if "ajax_t05sr01_1" in u]) <= 4


@pytest.mark.parametrize("refused_index", ["monthly", "ezsearch"])
def test_index_refusal_prevents_any_followup_original_requests(refused_index):
    from search_provider_runtime import SourceResponseError
    get, post, calls, _ = responses()
    def refusing_post(url, **kwargs):
        refused = url == JSON_INDEX if refused_index == "monthly" else url.endswith("ezsearch_query")
        if refused:
            response = httpx.Response(429, request=httpx.Request("POST", url), headers={"Retry-After": "3600"})
            error = SourceResponseError("rate_limited", status_code=429)
            error.response = response
            raise error
        return post(url, **kwargs)
    rows, audit = fetch_recent_company_announcements("2891.TW", now=NOW, get=get, post=refusing_post)
    assert rows == [] and audit["coverage_status"] == "partial"
    assert not any("ajax_t05sr01_1" in url for url in calls)
    assert audit["detail_stop_reason"] == "rate_limited"


def test_final_original_parsed_after_deadline_cannot_close_the_window(monkeypatch):
    from data_fetch.market_sources import twse_company_history as source
    clock, parsed = [0.], [0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    original = source._detail_fields
    def delayed_parse(html):
        result = original(html)
        parsed[0] += 1
        if parsed[0] == 41:
            clock[0] = 21
        return result
    monkeypatch.setattr(source, "_detail_fields", delayed_parse)
    get, post, calls, _ = responses()
    rows, audit = fetch_recent_company_announcements("2891.TW", now=NOW, get=get, post=post)
    assert len(rows) < 41
    assert audit["coverage_status"] == "partial" and audit["status"] != "success"
