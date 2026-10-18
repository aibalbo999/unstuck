from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urlsplit

import httpx

from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest
from news_freshness_policy import apply_news_freshness


NOW = datetime(2026, 10, 9, 3, 0, tzinfo=ZoneInfo("Asia/Taipei"))
INDEX = "https://wwwc.twse.com.tw/rwd/zh/IIH/company/events"
EN_INDEX = "https://wwwc.twse.com.tw/rwd/en/IIH/company/events"
DETAIL = (
    "https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1?firstin=true&stp=1&step=1"
    "&SEQ_NO=1&SPOKE_TIME=141538&SPOKE_DATE=20261006&COMPANY_ID=2855"
)


def _row(*, code="2855", day="115/10/06", link=DETAIL):
    return {"companyId": code, "companyName": "統一證", "subject": "公告本公司115年9月份損益",
            "date": day, "time": "14:15", "link": link}


def _detail(*, code="2855", body="公告本公司自行結算115年9月份合併損益情形：九月份稅後盈餘933,137仟元"):
    return ("<html><table class='noBorder'><tr class='compName'><td>本資料由 (上市公司) "
            f"{code} 統一證 公司提供</td></tr></table><table class='hasBorder'>"
            "<tr><th>序號</th><td>1</td><th>發言日期</th><td>115/10/06</td>"
            "<th>發言時間</th><td>14:15:38</td></tr>"
            "<tr><th>主旨</th><td>公告本公司115年9月份損益</td></tr>"
            f"<tr><th>說明</th><td>{body}</td></tr></table></html>")


def _get(index_rows, detail_html=None):
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        request = httpx.Request("GET", url)
        if url == INDEX:
            return httpx.Response(200, request=request, json={"info": {"status": "success", "data": {"code": "2855", "name": "統一證"}},
                                                       "news": index_rows, "fina": [], "conference": []})
        return httpx.Response(200, request=request, text=detail_html or _detail())
    return get, calls


def test_recent_official_announcement_requires_detail_body_and_matching_issuer():
    get, calls = _get([_row()], _detail())
    rows, audit = fetch_recent_company_announcements("2855.TW", now=NOW, get=get)
    assert len(rows) == 1
    assert rows[0]["link"] == DETAIL
    assert rows[0]["date"] == "2026-10-06T14:15:38+08:00"
    assert "933,137" in rows[0]["text"]
    assert rows[0]["source_type"] == "official_disclosure"
    assert rows[0]["catalyst_assessment"] == "not_assessed"
    assert audit["status"] == "success"
    assert calls == [INDEX, DETAIL]


def test_official_english_iih_fallback_fetches_and_checks_english_original():
    from data_fetch.market_sources.twse_history_transport import IIH_EN_URL

    now = datetime(2026, 10, 17, 12, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    index_url = IIH_EN_URL
    detail_url = ("https://emops.twse.com.tw/server-java/t05sr01_1_e?&isNew=Y&seq_no=1"
                  "&spoke_time=154044&spoke_date=20261012&co_id=2354")
    title = "Announcement That the Company's Losses from Derivatives Trading Have Reached the Prescribed Loss Limit"
    english_detail = (
        "<html><head><title>Today's Information</title></head><table><tr><th>Today's Information</th></tr></table><table>"
        "<tr><td>Provided by: FOXCONN TECHNOLOGY CO., LTD.</td></tr>"
        "<tr><td>SEQ_NO</td><td>1</td><td>Date of announcement</td><td>2026/10/12</td>"
        "<td>Time of announcement</td><td>15:40:44</td></tr>"
        f"<tr><td>Subject</td><td colspan='5'>{title}</td></tr>"
        "<tr><td>Statement</td><td colspan='5'>The company hereby announces the loss limit event with supporting transaction details and dates.</td></tr>"
        "</table></html>"
    )
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs.get("params")))
        request = httpx.Request("GET", url)
        if url == INDEX:
            raise httpx.ConnectError("Chinese endpoint unavailable", request=request)
        if url == index_url:
            assert kwargs.get("params") == {"code": "2354"}
            return httpx.Response(200, request=request, json={
                "info": {"status": "success", "data": {
                    "code": "2354", "name": "FOXCONN TECHNOLOGY CO., LTD.", "shortName": "",
                }},
                "news": [{"companyId": "2354", "companyName": "FTC", "subject": title,
                          "date": "2026/10/12", "time": "15:40", "link": detail_url}],
                "fina": [], "conference": [],
            })
        if url == detail_url:
            return httpx.Response(200, request=request, text=english_detail)
        raise AssertionError(f"unexpected request: {url}")

    def post(*_args, **_kwargs):
        raise AssertionError("a complete one-row English index must not trigger a second index")

    rows, audit = fetch_recent_company_announcements("2354.TW", now=now, get=get, post=post)

    assert len(rows) == 1, (audit.get("english_index_status"), audit.get("english_index_error_kind"),
                            audit.get("rejected_reason_counts"), audit.get("detail_observations"))
    assert rows[0]["ticker"] == "2354.TW"
    assert rows[0]["title"] == title
    assert rows[0]["link"] == detail_url
    assert "supporting transaction details" in rows[0]["text"]
    assert rows[0]["source_type"] == "official_disclosure"
    assert rows[0]["official_event"]["policy"] == "ordinary-mops-event-en-v1"
    assert audit["status"] == "success"
    assert calls == [(INDEX, {"code": "2354"}), (index_url, {"code": "2354"}), (detail_url, None)]


def test_wrong_issuer_detail_is_rejected_without_substitution():
    get, _ = _get([_row()], _detail(code="2851"))
    rows, audit = fetch_recent_company_announcements("2855.TW", now=NOW, get=get)
    assert rows == []
    assert audit["status"] == "degraded_enrichment"
    assert audit["rejected_reason_counts"] == {"detail_mismatch": 1}


def test_stale_and_nonofficial_links_do_not_trigger_detail_fetch():
    get, calls = _get([_row(day="115/08/01"), _row(link="https://example.com/fake?COMPANY_ID=2855")])
    rows, audit = fetch_recent_company_announcements("2855.TW", now=NOW, get=get)
    assert rows == []
    assert audit["rejected_reason_counts"] == {"outside_window": 1, "invalid_detail_url": 1}
    assert calls == [INDEX]


def test_verified_announcement_is_admitted_as_issuer_matched_recent_event():
    get, _ = _get([_row()])
    rows, _ = fetch_recent_company_announcements("2855.TW", now=NOW, get=get)
    data = {"ticker": "2855.TW", "company_name": "統一證",
            "company_identity": {"official_name": "統一證"}}
    apply_news_freshness(data, cutoff=NOW, records=rows)
    assert [item["link"] for item in data["recent_catalysts"]] == [DETAIL]
    assert data["identity_rejected_catalysts"] == []
    assert "TWSE company announcement history" in ProviderRegistry().provider_names(
        FetchRequest.from_ticker("2855.TW"), source="recent_catalysts")
    assert "TWSE company announcement history" not in ProviderRegistry().provider_names(
        FetchRequest.from_ticker("2855.TWO"), source="recent_catalysts")


def test_ezsearch_fallback_recovers_announcements_beyond_ten_item_index():
    from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements

    links = [DETAIL.replace("SEQ_NO=1", f"SEQ_NO={index}").replace("SPOKE_DATE=20261006", "SPOKE_DATE=20261008")
             .replace("SPOKE_TIME=141538", f"SPOKE_TIME={100000 + index:06d}")
             for index in range(1, 12)]
    index_rows = [_row(day="115/10/08", link=link) for link in links[:10]]
    for index, row in enumerate(index_rows, 1):
        clock = f"{100000 + index:06d}"
        row["time"] = f"{clock[:2]}:{clock[2:4]}"
    calls = []

    def get(url, **_kwargs):
        calls.append(url)
        request = httpx.Request("GET", url)
        if url == INDEX:
            return httpx.Response(200, request=request, json={
                "info": {"status": "success", "data": {"code": "2855", "name": "統一證"}},
                "news": index_rows, "fina": [], "conference": [],
            })
        params = parse_qs(urlsplit(url).query)
        clock = params["SPOKE_TIME"][0]
        detail = _detail().replace("115/10/06", "115/10/08").replace("14:15:38", f"{clock[:2]}:{clock[2:4]}:{clock[4:]}")
        return httpx.Response(200, request=request, text=detail)

    def post(url, **_kwargs):
        assert url == "https://mopsov.twse.com.tw/mops/web/ezsearch_query"
        payload = {"status": "success", "data": [
            {"COMPANY_ID": "2855", "COMPANY_NAME": "統一證", "TYPEK": "上市", "CDATE": "115/10/08",
             "CTIME": f"{100000 + index:06d}"[:2] + ":" + f"{100000 + index:06d}"[2:4] + ":" + f"{100000 + index:06d}"[4:],
             "AN_CODE": "M99", "SUBJECT": "公告本公司115年9月份損益", "HYPERLINK": link}
            for index, link in enumerate(links, 1)]}
        return httpx.Response(200, request=httpx.Request("POST", url), content=("\ufeff" + __import__("json").dumps(payload)).encode())

    rows, audit = fetch_recent_company_announcements("2855.TW", now=NOW, get=get, post=post)

    assert len(rows) == 11, (audit["rejected_reason_counts"], calls[1])
    assert {row["link"] for row in rows} == set(links)
    assert audit["coverage_status"] == "window_complete"
    assert audit["status"] == "success"
    assert audit["ezsearch_added_count"] == 1
    assert calls.count(INDEX) == 1
    assert set(calls[1:]) == set(links)


def test_ezsearch_fallback_rejects_wrong_issuer_without_claiming_complete_window():
    from data_fetch.market_sources.twse_ezsearch_history import fetch_ezsearch_candidates

    def post(url, **_kwargs):
        payload = {"status": "success", "data": [
            {"COMPANY_ID": "2851", "COMPANY_NAME": "中再保", "TYPEK": "上市", "CDATE": "115/10/06",
             "CTIME": "14:15:38", "AN_CODE": "M99", "SUBJECT": "其他公司公告", "HYPERLINK": DETAIL},
            {"COMPANY_ID": "2855", "COMPANY_NAME": "統一證", "TYPEK": "上市", "CDATE": "115/10/06",
             "CTIME": "14:15:38", "AN_CODE": "M99", "SUBJECT": "公告本公司115年9月份損益",
             "HYPERLINK": "https://example.com/forged"},
        ]}
        return httpx.Response(200, request=httpx.Request("POST", url), json=payload)

    candidates, audit = fetch_ezsearch_candidates("2855", now=NOW, post=post)

    assert candidates == []
    assert audit["coverage_status"] == "partial"
    assert audit["rejected_reason_counts"] == {"issuer_mismatch": 1, "invalid_detail_url": 1}


def test_ezsearch_accepts_mops_time_with_omitted_leading_zero():
    from data_fetch.market_sources.twse_ezsearch_history import fetch_ezsearch_candidates

    link = ("https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1?firstin=true&stp=1&step=1"
            "&SEQ_NO=5&SPOKE_TIME=64117&SPOKE_DATE=20260915&COMPANY_ID=2308")

    def post(url, **_kwargs):
        payload = {"status": "success", "data": [{
            "COMPANY_ID": "2308", "COMPANY_NAME": "台達電", "TYPEK": "上市", "CDATE": "115/09/15",
            "CTIME": "06:41:17", "AN_CODE": "M11", "SUBJECT": "公告海外可交換公司債",
            "HYPERLINK": link,
        }]}
        return httpx.Response(200, request=httpx.Request("POST", url), json=payload)

    candidates, audit = fetch_ezsearch_candidates("2308", now=NOW, post=post)

    assert [item[3] for item in candidates] == [link]
    assert audit["coverage_status"] == "window_complete"


def test_ezsearch_does_not_attribute_otc_record_to_listed_ticker():
    from data_fetch.market_sources.twse_ezsearch_history import fetch_ezsearch_candidates

    def post(url, **_kwargs):
        payload = {"status": "success", "data": [{
            "COMPANY_ID": "2308", "COMPANY_NAME": "台達電", "TYPEK": "上櫃",
            "CDATE": "115/10/06", "CTIME": "14:15:38", "AN_CODE": "M99",
            "SUBJECT": "不能冒用上市市場", "HYPERLINK": DETAIL.replace("COMPANY_ID=2855", "COMPANY_ID=2308"),
        }]}
        return httpx.Response(200, request=httpx.Request("POST", url), json=payload)

    candidates, audit = fetch_ezsearch_candidates("2308", now=NOW, post=post)

    assert candidates == []
    assert audit["coverage_status"] == "partial"
    assert audit["rejected_reason_counts"] == {"market_mismatch": 1}


def test_ezsearch_recovers_when_primary_company_index_is_unavailable():
    calls = []

    def get(url, **_kwargs):
        calls.append(url)
        if url in {INDEX, EN_INDEX}:
            raise httpx.ConnectError("index unavailable")
        return httpx.Response(200, request=httpx.Request("GET", url), text=_detail())

    def post(url, **_kwargs):
        assert url == "https://mopsov.twse.com.tw/mops/web/ezsearch_query"
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "status": "success", "data": [{
                "COMPANY_ID": "2855", "COMPANY_NAME": "統一證", "TYPEK": "上市",
                "CDATE": "115/10/06", "CTIME": "14:15:38", "AN_CODE": "M99",
                "SUBJECT": "公告本公司115年9月份損益", "HYPERLINK": DETAIL,
            }],
        })

    rows, audit = fetch_recent_company_announcements("2855.TW", now=NOW, get=get, post=post)

    assert [row["link"] for row in rows] == [DETAIL]
    assert calls == [INDEX, EN_INDEX, DETAIL]
    assert audit["status"] == "success"
    assert audit["coverage_status"] == "window_complete"
    assert audit["primary_index_error_kind"] == "ConnectError"
    assert audit["ezsearch"]["coverage_status"] == "window_complete"


def test_failed_primary_and_partial_ezsearch_preserve_partial_coverage():
    def get(url, **_kwargs):
        if url == INDEX:
            raise httpx.ConnectError("index unavailable")
        return httpx.Response(200, request=httpx.Request("GET", url), text=_detail())

    def post(url, **_kwargs):
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "status": "success", "data": [
                {"COMPANY_ID": "2855", "COMPANY_NAME": "統一證", "TYPEK": "上市",
                 "CDATE": "115/10/06", "CTIME": "14:15:38", "AN_CODE": "M99",
                 "SUBJECT": "公告本公司115年9月份損益", "HYPERLINK": DETAIL},
                {"COMPANY_ID": "2851", "COMPANY_NAME": "中再保", "TYPEK": "上市",
                 "CDATE": "115/10/06", "CTIME": "14:15:38", "AN_CODE": "M99",
                 "SUBJECT": "其他公司公告", "HYPERLINK": DETAIL},
            ],
        })

    rows, audit = fetch_recent_company_announcements("2855.TW", now=NOW, get=get, post=post)

    assert [row["link"] for row in rows] == [DETAIL]
    assert audit["status"] == "degraded_enrichment"
    assert audit["coverage_status"] == "partial"
    assert audit["ezsearch"]["rejected_reason_counts"] == {"issuer_mismatch": 1}


def test_both_official_indexes_failing_remains_an_error():
    def get(url, **_kwargs):
        raise httpx.ConnectError("primary unavailable")

    def post(url, **_kwargs):
        raise httpx.ConnectError("fallback unavailable")

    rows, audit = fetch_recent_company_announcements("2855.TW", now=NOW, get=get, post=post)

    assert rows == []
    assert audit["status"] == "error"
    assert audit["coverage_status"] == "partial"
    assert audit["primary_index_error_kind"] == "ConnectError"
    assert audit["ezsearch"]["error_kind"] == "ConnectError"
