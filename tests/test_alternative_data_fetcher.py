import sys
from pathlib import Path
from unittest.mock import patch
import json

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.text)


def test_fetch_104_job_openings_count_extracts_total_from_html():
    from alternative_data_fetcher import fetch_104_job_openings_count

    session = FakeSession(
        """
        <html>
          <body>
            <script>window.__STATE__={"totalCount":128,"other":true}</script>
            <h1>台達電 散熱 職缺</h1>
          </body>
        </html>
        """
    )

    result = fetch_104_job_openings_count("台達電", "散熱", session=session)

    assert result["job_count"] == 128
    assert result["company_name"] == "台達電"
    assert result["keyword"] == "散熱"
    assert "104.com.tw" in result["source_url"]
    headers = session.calls[0][1]["headers"]
    assert "Mozilla" in headers["User-Agent"]


def test_104_company_api_keeps_only_exact_recent_employer_jobs():
    from alternative_data_fetcher import fetch_104_company_jobs

    page = {
        "data": [
            {"custName": "世紀民生科技股份有限公司", "custNo": "22099815000",
             "jobNo": "15137142", "jobName": "稽核儲備主管", "appearDate": "20261002",
             "link": {"job": "https://www.104.com.tw/job/90fw6"}},
            {"custName": "別家公司", "custNo": "123", "jobNo": "2", "jobName": "工程師",
             "appearDate": "20261002", "link": {"job": "https://www.104.com.tw/job/other"}},
            {"custName": "世紀民生科技股份有限公司", "custNo": "22099815000",
             "jobNo": "15137142", "jobName": "重複職缺", "appearDate": "20261002",
             "link": {"job": "https://www.104.com.tw/job/90fw6"}},
        ],
        "metadata": {"pagination": {"currentPage": 1, "lastPage": 1, "total": 2}},
    }
    session = FakeSession(json.dumps(page))
    result = fetch_104_company_jobs("世紀民生科技股份有限公司", session=session, today="2026-10-04")

    assert result["status"] == "success"
    assert result["recent_company_job_count"] == 1
    assert result["job_count"] is None
    assert result["query_scope"] == "exact_company_recent_postings"
    assert result["job_postings"][0]["url"] == "https://www.104.com.tw/job/90fw6"
    assert result["rejected_count"] == 2
    assert session.calls[0][1]["params"]["keyword"] == '"世紀民生科技股份有限公司"'
    assert session.calls[0][1]["params"]["kwop"] == "2"


def test_104_company_api_incomplete_pages_or_no_exact_employer_are_unknown():
    from alternative_data_fetcher import fetch_104_company_jobs

    job = {"custName": "世紀民生科技股份有限公司", "custNo": "22099815000",
           "jobNo": "15137142", "jobName": "稽核儲備主管", "appearDate": "20261002",
           "link": {"job": "https://www.104.com.tw/job/90fw6"}}
    incomplete = {"data": [job], "metadata": {"pagination": {"currentPage": 2, "lastPage": 3, "total": 999}}}
    result = fetch_104_company_jobs("世紀民生科技股份有限公司", session=FakeSession(json.dumps(incomplete)), today="2026-10-04")
    assert result["status"] == "unavailable" and result["job_count"] is None
    wrong = {"data": [{**job, "custName": "別家公司"}],
             "metadata": {"pagination": {"currentPage": 1, "lastPage": 1, "total": 1}}}
    result = fetch_104_company_jobs("世紀民生科技股份有限公司", session=FakeSession(json.dumps(wrong)), today="2026-10-04")
    assert result["status"] == "unavailable" and result["recent_company_job_count"] is None


def test_104_company_api_samples_large_search_without_claiming_total_or_skipping_pages():
    from alternative_data_fetcher import fetch_104_company_jobs

    company = "統一綜合證券股份有限公司"
    pages = {}
    for page in range(1, 4):
        pages[page] = json.dumps({
            "data": [
                {"custName": company, "custNo": "23218183000", "jobNo": str(1000 + page),
                 "jobName": f"職缺 {page}", "appearDate": "20261007",
                 "link": {"job": f"https://www.104.com.tw/job/test{page}"}},
                {"custName": "相似名稱的其他公司", "custNo": "123", "jobNo": str(2000 + page),
                 "jobName": "排除", "appearDate": "20261007",
                 "link": {"job": f"https://www.104.com.tw/job/other{page}"}},
            ],
            "metadata": {"pagination": {"currentPage": page, "lastPage": 7, "total": 186}},
        })

    class PagedSession:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            page = int(kwargs["params"]["page"])
            self.calls.append(page)
            return FakeResponse(pages[page])

    session = PagedSession()
    result = fetch_104_company_jobs(company, session=session, today="2026-10-09")

    assert result["status"] == "success"
    assert session.calls == [1, 2, 3]
    assert result["recent_company_job_count"] == 3
    assert result["job_count"] is None
    assert result["page_count"] == 7
    assert result["searched_page_count"] == 3
    assert result["pagination_truncated"] is True
    assert result["coverage_status"] == "bounded_company_recent_postings_sample"
    assert result["rejected_count"] == 3
    assert "樣本" in result["message"]


def test_104_company_api_requires_every_searched_page_for_bounded_sample():
    from alternative_data_fetcher import fetch_104_company_jobs

    company = "統一綜合證券股份有限公司"
    job = {"custName": company, "custNo": "23218183000", "jobNo": "1001",
           "jobName": "職缺", "appearDate": "20261007",
           "link": {"job": "https://www.104.com.tw/job/test1"}}

    class BrokenSecondPage:
        def get(self, url, **kwargs):
            page = int(kwargs["params"]["page"])
            current_page = 1 if page == 2 else page
            return FakeResponse(json.dumps({"data": [job], "metadata": {"pagination": {
                "currentPage": current_page, "lastPage": 7, "total": 186}}}))

    result = fetch_104_company_jobs(company, session=BrokenSecondPage(), today="2026-10-09")
    assert result["status"] == "unavailable"
    assert result["reason_code"] == "api_unverified"

    class ChangingPageCount:
        def get(self, url, **kwargs):
            page = int(kwargs["params"]["page"])
            return FakeResponse(json.dumps({"data": [job], "metadata": {"pagination": {
                "currentPage": page, "lastPage": 7 if page == 1 else 6, "total": 186}}}))

    result = fetch_104_company_jobs(company, session=ChangingPageCount(), today="2026-10-09")
    assert result["status"] == "unavailable"
    assert result["reason_code"] == "api_unverified"


def test_104_company_api_accepts_only_official_short_name_alias_with_matching_tax_id():
    from alternative_data_fetcher import fetch_104_company_jobs

    legal = "台灣積體電路製造股份有限公司"
    alias = legal + "(台積電)"
    job = {"custName": alias, "custNo": "22099131000", "jobNo": "12345678",
           "jobName": "製程工程師", "appearDate": "20261007",
           "link": {"job": "https://www.104.com.tw/job/abc123"}}

    def result_for(row, **identity):
        payload = {"data": [row], "metadata": {"pagination": {
            "currentPage": 1, "lastPage": 1, "total": 1}}}
        return fetch_104_company_jobs(legal, session=FakeSession(json.dumps(payload)),
                                      today="2026-10-09", **identity)

    assert result_for(job)["status"] == "unavailable"
    verified = result_for(job, official_short_name="台積電", official_ubn="22099131")
    assert verified["status"] == "success"
    assert verified["job_count"] is None
    assert verified["job_postings"][0]["employer"] == legal
    assert verified["job_postings"][0]["source_employer"] == alias
    assert verified["job_postings"][0]["employer_match_basis"] == "official_name_ubn_alias"
    assert result_for({**job, "custNo": "22099131001"}, official_short_name="台積電",
                      official_ubn="22099131")["status"] == "unavailable"
    assert result_for(job, official_short_name="台積電", official_ubn="22099132")["status"] == "unavailable"
    assert result_for({**job, "custName": legal + "(台積電集團)"}, official_short_name="台積電",
                      official_ubn="22099131")["status"] == "unavailable"

def test_104_company_api_accepts_verified_prefix_alias_only_with_matching_tax_id():
    from alternative_data_fetcher import fetch_104_company_jobs

    legal = "臺灣水泥股份有限公司"
    job = {"custName": "(台泥)" + legal, "custNo": "11913502000", "jobNo": "12345678",
           "jobName": "品管工程師", "appearDate": "20261008",
           "link": {"job": "https://www.104.com.tw/job/abc123"}}

    def result_for(row, **identity):
        payload = {"data": [row], "metadata": {"pagination": {
            "currentPage": 1, "lastPage": 1, "total": 1}}}
        return fetch_104_company_jobs(legal, session=FakeSession(json.dumps(payload)),
                                      today="2026-10-09", **identity)

    assert result_for(job)["status"] == "unavailable"
    verified = result_for(job, official_short_name="台泥", official_ubn="11913502")
    assert verified["status"] == "success"
    assert verified["job_postings"][0]["employer_match_basis"] == "official_name_ubn_prefix_alias"
    assert result_for({**job, "custNo": "11913502001"}, official_short_name="台泥",
                      official_ubn="11913502")["status"] == "unavailable"
    assert result_for({**job, "custName": "(台泥集團)" + legal}, official_short_name="台泥",
                      official_ubn="11913502")["status"] == "unavailable"


def test_104_company_api_accepts_exact_legal_name_with_latin_suffix_only_with_tax_id():
    from alternative_data_fetcher import fetch_104_company_jobs

    legal = "台達電子工業股份有限公司"
    job = {"custName": legal + " _DELTA ELECTRONICS INC.", "custNo": "34051920000",
           "jobNo": "12345678", "jobName": "電源工程師", "appearDate": "20261008",
           "link": {"job": "https://www.104.com.tw/job/abc123"}}

    def result_for(row, **identity):
        payload = {"data": [row], "metadata": {"pagination": {
            "currentPage": 1, "lastPage": 1, "total": 1}}}
        return fetch_104_company_jobs(legal, session=FakeSession(json.dumps(payload)),
                                      today="2026-10-09", **identity)

    assert result_for(job)["status"] == "unavailable"
    verified = result_for(job, official_short_name="台達電", official_ubn="34051920")
    assert verified["status"] == "success"
    assert verified["job_postings"][0]["employer_match_basis"] == "official_name_ubn_latin_suffix"
    assert result_for({**job, "custNo": "34051920001"}, official_short_name="台達電",
                      official_ubn="34051920")["status"] == "unavailable"
    assert result_for({**job, "custName": legal + " _台達子公司"}, official_short_name="台達電",
                      official_ubn="34051920")["status"] == "unavailable"


def test_104_company_endpoint_recovers_exact_employer_hidden_on_later_search_page():
    from alternative_data_fetcher import fetch_104_company_jobs_by_ubn

    list_payload = {"data": {"totalCount": 1, "totalPages": 1, "page": 1,
                             "pageSize": 20, "list": {"topJobs": [], "normalJobs": [{
        "jobNo": "965f7", "jobName": "研發替代役", "jobUrl": "https://www.104.com.tw/job/965f7",
        "appearDate": "9/23"}]}}, "metadata": {}}
    detail_payload = {"data": {"custNo": "dyztbmg", "header": {
        "custName": "中國鋼鐵股份有限公司", "jobName": "研發替代役",
        "custUrl": "https://www.104.com.tw/company/dyztbmg", "appearDate": "2026/09/23"}},
        "metadata": {}}

    class RoutedSession:
        def __init__(self, detail):
            self.calls = []
            self.detail = detail

        def get(self, url, **kwargs):
            self.calls.append(url)
            payload = self.detail if "/job/ajax/content/" in url else list_payload
            return FakeResponse(json.dumps(payload))

    session = RoutedSession(detail_payload)
    result = fetch_104_company_jobs_by_ubn("中國鋼鐵股份有限公司", "30414175",
                                           official_short_name="中鋼", session=session,
                                           today="2026-10-09")
    assert result["status"] == "success"
    assert result["recent_company_job_count"] == 1
    assert result["job_count"] is None
    assert result["job_postings"][0]["source_employer_id"] == "dyztbmg"
    assert result["job_postings"][0]["employer_id"] == "30414175000"
    assert result["job_postings"][0]["job_no"] == "15403507"
    assert result["job_postings"][0]["published_date"] == "2026-09-23"
    assert session.calls == ["https://www.104.com.tw/api/companies/dyztbmg/jobs",
                             "https://www.104.com.tw/job/ajax/content/965f7"]
    for change in ({"custNo": "dyztbmh"},
                   {"header": {**detail_payload["data"]["header"], "custName": "中國鋼鐵結構股份有限公司"}},
                   {"header": {**detail_payload["data"]["header"], "appearDate": "2026/08/01"}}):
        bad = {"data": {**detail_payload["data"], **change}, "metadata": {}}
        assert fetch_104_company_jobs_by_ubn("中國鋼鐵股份有限公司", "30414175",
                                             official_short_name="中鋼", session=RoutedSession(bad),
                                             today="2026-10-09")["status"] == "unavailable"


def test_fetch_104_job_openings_count_falls_back_to_text_pattern():
    from alternative_data_fetcher import fetch_104_job_openings_count

    session = FakeSession("<main>搜尋結果：共 36 筆工作機會</main>")

    result = fetch_104_job_openings_count("台達電", "液冷", session=session)

    assert result["job_count"] == 36


def test_fetch_104_job_openings_count_uses_shared_http_client(monkeypatch):
    import alternative_data_fetcher
    from alternative_data_fetcher import fetch_104_job_openings_count

    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse('<script>{"totalCount":88}</script>')

    monkeypatch.setattr(alternative_data_fetcher, "sync_get", fake_get)

    result = fetch_104_job_openings_count("台達電", "散熱")

    assert result["job_count"] == 88
    assert calls[0]["provider"] == "104 Job Search"
    assert calls[0]["params"]["keyword"] == "台達電 散熱"


def test_fetch_1111_job_openings_count_uses_shared_http_client(monkeypatch):
    import alternative_data_fetcher
    from alternative_data_fetcher import fetch_1111_job_openings_count

    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse("<main>共 42 筆</main>")

    monkeypatch.setattr(alternative_data_fetcher, "sync_get", fake_get)

    result = fetch_1111_job_openings_count("台達電", "散熱")

    assert result["job_count"] == 42
    assert calls[0]["provider"] == "1111 Job Search"
    assert calls[0]["params"]["ks"] == "台達電 散熱"


def test_fetch_104_job_openings_count_returns_unavailable_on_parse_failure():
    from alternative_data_fetcher import fetch_104_job_openings_count

    with patch("news_fetchers.fetch_google_news_rss", return_value=[]) as news_fallback:
        result = fetch_104_job_openings_count("台達電", "AI", session=FakeSession("<html></html>"))

    news_fallback.assert_called_once()
    assert result["reason_code"] == "parse_failure"
    assert result["status"] == "unavailable"
    assert result["job_count"] is None
    assert "未揭露可解析的職缺總數" in result["message"]


def test_fetch_104_job_openings_count_uses_news_fallback_on_transport_failure():
    from alternative_data_fetcher import fetch_104_job_openings_count

    class FailingSession:
        def get(self, url, **kwargs):
            raise TimeoutError("offline")

    from datetime import datetime, timezone
    fake_news = [{"title": "台達電擴編消息", "published_date": datetime.now(timezone.utc).isoformat(), "link": "https://example.test/recruitment"}]
    with patch("news_fetchers.fetch_google_news_rss", return_value=fake_news) as fetch_news:
        result = fetch_104_job_openings_count("台達電", "AI", session=FailingSession())

    fetch_news.assert_called_once_with('"台達電" (徵才 OR 擴編 OR 招募 OR hiring OR recruitment) when:30d', limit=5)
    assert result["status"] == "success"
    assert result["job_count"] is None
    assert result["recent_recruitment_news"][0]["title"] == fake_news[0]["title"]
    assert result["recent_recruitment_news"][0]["content_coverage"] == "headline_or_snippet"


def test_fetch_104_job_openings_count_does_not_mask_parser_errors_with_news_fallback():
    from alternative_data_fetcher import fetch_104_job_openings_count

    with (
        patch("alternative_data_fetcher._extract_104_job_count", side_effect=ValueError("parser bug")),
        patch("alternative_data_fetcher._google_news_fallback") as news_fallback,
    ):
        with pytest.raises(ValueError, match="parser bug"):
            fetch_104_job_openings_count("台達電", "AI", session=FakeSession("<html></html>"))

    news_fallback.assert_not_called()
