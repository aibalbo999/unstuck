"""Regional open data must not turn subsidiaries or expired rows into issuer jobs."""
from datetime import date, datetime
from types import SimpleNamespace
import time
from zoneinfo import ZoneInfo

from data_fetch.market_sources.taiwanjobs_company_jobs import (
    fetch_taiwanjobs_regional_jobs, verified_taiwanjobs_job_count,
)


class RegionalClient:
    def __init__(self, *, feed_company="統一超商股份有限公司", profile_ubn="22555003",
                 detail_expiry="2026/12/31"):
        self.feed_company = feed_company
        self.profile_ubn = profile_ubn
        self.detail_expiry = detail_expiry
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if "Webservice.ashx" in url:
            body = (
                'OCCU_DESC（職務名稱）,WK_TYPE（職務性質）,CJOB1_COUNT（職務大類別代碼）,CJOB_NAME1（職務大類別名稱）,CJOB2_COUNT（職務小類別代碼）,CJOB_NAME2（職務小類別名稱）,JOB_PERSON（雇用人數）,STOP_DATE（應徵截止日期）,JOB_DETAIL（工作內容）,CITYNAME（工作地點）,EXPERIENCE（工作經驗）,WKTIME（工作時間）,SALARYCD（核薪方式）,NT_L（薪資範圍下限）,NT_U（薪資範圍上限）,EDGRDESC（最低學歷要求）,URL_QUERY（職缺資料URL）,COMPNAME（公司名稱）,TRANDATE（職缺更新日期）\n'
                f'門市服務人員,全職,16,門市,1601,店員,1,20261231,服務,新北市,,,,,,,"https://job.taiwanjobs.gov.tw/Internet/jobwanted/JobDetail.aspx?EMPLOYER_ID=66025&HIRE_ID=14712117",{self.feed_company},20261002\n'
            )
        elif "company_desc2.aspx" in url:
            body = (f'<h2 id="CPH1_h1_COMPNAME">{self.feed_company}</h2>'
                    f'<dl><dt>統一編號</dt><dd>{self.profile_ubn}</dd></dl>')
        else:
            body = ('<h2>門市服務人員【徵才活動】</h2>'
                    f'<a href="https://job.taiwanjobs.gov.tw/internet/jobwanted/company_desc2.aspx?EMPLOYER_ID=66025&amp;BRANCH_ID=">{self.feed_company}</a>'
                    '<dl><dt>工作代碼</dt><dd>14712117</dd></dl>'
                    f'<dl><dt>應徵截止日期</dt><dd>{self.detail_expiry}</dd></dl>')
        return SimpleNamespace(status_code=200, content=body.encode(), text=body, url=url,
                               raise_for_status=lambda: None)


def test_regional_feed_requires_exact_issuer_profile_and_open_detail():
    client = RegionalClient()
    result = fetch_taiwanjobs_regional_jobs(
        "2912.TW", "統一超商股份有限公司", "22555003", client=client,
        cities=("31",), today=date(2026, 10, 9), now=1000,
    )
    assert result["status"] == "success"
    assert result["current_open_job_count"] == 1
    assert result["job_postings"][0]["job_no"] == "14712117"
    assert verified_taiwanjobs_job_count(result, "2912.TW", "統一超商股份有限公司", "22555003", now=1001) == 1
    assert len(client.calls) == 3


def test_regional_feed_rejects_subsidiary_wrong_ubn_and_expired_detail():
    cases = [
        RegionalClient(feed_company="聯華食品工業股份有限公司"),
        RegionalClient(profile_ubn="11996904"),
        RegionalClient(detail_expiry="2026/10/08"),
    ]
    for client in cases:
        result = fetch_taiwanjobs_regional_jobs(
            "2912.TW", "統一超商股份有限公司", "22555003", client=client,
            cities=("31",), today=date(2026, 10, 9), now=1000,
        )
        assert result["status"] == "unavailable"
        assert result["current_open_job_count"] is None


def test_regional_feed_rejects_non_taiwan_jobs_or_ambiguous_link():
    for original, replacement in (
        (b"job.taiwanjobs.gov.tw", b"jobs.example.com"),
        (b"HIRE_ID=14712117", b"HIRE_ID=14712117&HIRE_ID=14712118"),
    ):
        client = RegionalClient()
        original_get = client.get

        def wrong_link(url, **kwargs):
            response = original_get(url, **kwargs)
            if "Webservice.ashx" in url:
                response.content = response.content.replace(original, replacement)
                response.text = response.content.decode()
            return response

        client.get = wrong_link
        result = fetch_taiwanjobs_regional_jobs(
            "2912.TW", "統一超商股份有限公司", "22555003", client=client,
            cities=("31",), today=date(2026, 10, 9), now=1000,
        )
        assert result["status"] == "unavailable"
        assert len(client.calls) == 1


def test_optional_job_provider_uses_verified_regional_fallback(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name as identity_source
    from data_fetch.market_sources import taiwanjobs_company_jobs as government_jobs
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count

    now = time.time()
    receipt = {"ticker": "2912.TW", "legal_name": "統一超商股份有限公司",
               "official_short_name": "統一超", "official_ubn": "22555003",
               "as_of": datetime.fromtimestamp(now, ZoneInfo("Asia/Taipei")).date().isoformat(),
               "source_url": identity_source.URLS[".TW"], "response_sha256": "a" * 64,
               "fetched_at_epoch": now, "stale": False}
    monkeypatch.setattr(identity_source, "get_official_legal_name", lambda *a: receipt)
    unavailable = {"status": "unavailable", "job_count": None, "source": "104 Job Search"}
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs", lambda *a, **k: unavailable)
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs_by_ubn", lambda *a, **k: unavailable)
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_job_openings_count", lambda *a, **k: unavailable)
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count", lambda *a, **k: unavailable)
    monkeypatch.setattr(government_jobs, "fetch_taiwanjobs_company_jobs", lambda *a: unavailable)
    regional = fetch_taiwanjobs_regional_jobs(
        "2912.TW", "統一超商股份有限公司", "22555003", client=RegionalClient(),
        cities=("31",), today=date(2026, 10, 9), now=now,
    )
    monkeypatch.setattr(government_jobs, "fetch_taiwanjobs_regional_jobs", lambda *a: regional)
    data = {"ticker": "2912.TW", "company_name": "統一超", "quote_type": "EQUITY",
            "company_identity": {"ticker": "2912.TW", "official_name": "統一超",
                                 "instrument_type": "EQUITY"}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker("2912.TW"), {"data": data})
    assert result.status == "success"
    assert result.value["job_openings_taiwanjobs"]["source"] == "TaiwanJobs public regional open data"
    assert result.audit["component_statuses"]["taiwanjobs"]["provider"] == "TaiwanJobs public regional open data"
    assert source_record_count("alternative_data", {**data, "alternative_data": result.value}) == 1

    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_job_openings_count",
                        lambda *a, **k: {"status": "success", "evidence_kind": "company_job_postings",
                                         "job_postings": [{"title": "已核對職缺"}], "job_count": None})

    def regional_must_not_run(*_args):
        raise AssertionError("regional backup must wait for other verified jobs")

    monkeypatch.setattr(government_jobs, "fetch_taiwanjobs_regional_jobs", regional_must_not_run)
    other = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker("2912.TW"), {"data": data})
    assert other.status == "success"
