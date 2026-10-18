"""A public company search is useful only when issuer and open jobs agree."""
from datetime import date, datetime
from types import SimpleNamespace
import time
from zoneinfo import ZoneInfo

from data_fetch.market_sources.taiwanjobs_company_jobs import (
    fetch_taiwanjobs_company_jobs, verified_taiwanjobs_job_count,
)


class FakeClient:
    def __init__(self, company_name="信邦電子股份有限公司", ubn="23542766", expires="2026/12/31"):
        self.company_name, self.ubn, self.expires = company_name, ubn, expires
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        if url.endswith("job_search_list.aspx"):
            body = '<form id="form1"><input name="__VIEWSTATE" type="hidden" value="state"><input name="__VIEWSTATEGENERATOR" type="hidden" value="gen"><input name="ctl00$CPH1$SearchBar$txtKeywordComp" type="text"></form>'
        elif "company_desc2.aspx" in url:
            body = (f'<h2 id="CPH1_h1_COMPNAME">{self.company_name}</h2><dl><dt>統一編號</dt><dd>{self.ubn}</dd></dl>'
                    '<a id="CPH1_lv_company_job_lnk_jobDetail_0" href="../index/JobDetail.aspx?R2=11&amp;EMPLOYER_ID=83696&amp;HIRE_ID=14637309">現場技術人員 (電子設備組裝作業員)</a>')
        else:
            body = (f'<h2>現場技術人員</h2><a href="https://job.taiwanjobs.gov.tw/Internet/jobwanted/company_desc2.aspx?EMPLOYER_ID=83696&amp;BRANCH_ID=">{self.company_name}</a>'
                    f'<dl><dt>工作代碼</dt><dd>14637309</dd></dl><dl><dt>應徵截止日期</dt><dd>{self.expires}</dd></dl>')
        return SimpleNamespace(status_code=200, content=body.encode(), text=body, url=url, raise_for_status=lambda: None)

    def post(self, url, data, **kwargs):
        self.calls.append(("POST", url, data))
        body = (f'<a href="../jobwanted/company_desc2.aspx?EMPLOYER_ID=83696&amp;BRANCH_ID=">{self.company_name}</a>')
        return SimpleNamespace(status_code=200, content=body.encode(), text=body,
                               url="https://job.taiwanjobs.gov.tw/internet/index/jobQuery_result_comp2.aspx",
                               raise_for_status=lambda: None)


def test_exact_public_employer_and_open_detail_are_counted():
    client = FakeClient()
    result = fetch_taiwanjobs_company_jobs("3023.TW", "信邦電子股份有限公司", "23542766",
                                            client=client, today=date(2026, 10, 9), now=1000)
    assert result["status"] == "success"
    assert result["current_open_job_count"] == 1
    assert result["job_postings"][0]["job_no"] == "14637309"
    assert verified_taiwanjobs_job_count(result, "3023.TW", "信邦電子股份有限公司", "23542766", now=1001) == 1
    assert client.calls[1][2]["ctl00$CPH1$SearchBar$rblqryType1"] == "comp"


def test_issuer_or_expired_detail_cannot_be_promoted():
    for client in (FakeClient(ubn="99999999"), FakeClient(expires="2026/10/08"),
                   FakeClient(company_name="信邦電子子公司股份有限公司")):
        result = fetch_taiwanjobs_company_jobs("3023.TW", "信邦電子股份有限公司", "23542766",
                                                client=client, today=date(2026, 10, 9), now=1000)
        assert result["status"] == "unavailable"
        assert result["current_open_job_count"] is None


def test_saved_claim_rejects_wrong_identity_or_expired_receipt():
    value = fetch_taiwanjobs_company_jobs("3023.TW", "信邦電子股份有限公司", "23542766",
                                           client=FakeClient(), today=date(2026, 10, 9), now=1000)
    assert verified_taiwanjobs_job_count(value, "3023.TW", "信邦電子股份有限公司", "99999999", now=1001) == 0
    assert verified_taiwanjobs_job_count(value, "3023.TW", "信邦電子股份有限公司", "23542766", now=1000+86401) == 0


def test_provider_keeps_taiwanjobs_separate_from_104_and_trust_counts_only_verified(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name as identity_source
    from data_fetch.market_sources import taiwanjobs_company_jobs as government_jobs
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count

    now = time.time()
    receipt = {"ticker": "3023.TW", "legal_name": "信邦電子股份有限公司",
               "official_short_name": "信邦", "official_ubn": "23542766",
               "as_of": datetime.fromtimestamp(now, ZoneInfo("Asia/Taipei")).date().isoformat(),
               "source_url": identity_source.URLS[".TW"], "response_sha256": "a" * 64,
               "fetched_at_epoch": now, "stale": False}
    monkeypatch.setattr(identity_source, "get_official_legal_name", lambda *a: receipt)
    unavailable = {"status": "unavailable", "job_count": None, "source": "104 Job Search"}
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs", lambda *a, **k: unavailable)
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs_by_ubn", lambda *a, **k: unavailable)
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_job_openings_count", lambda *a, **k: unavailable)
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count", lambda *a, **k: unavailable)
    sample = fetch_taiwanjobs_company_jobs("3023.TW", "信邦電子股份有限公司", "23542766",
                                           client=FakeClient(), today=date(2026, 10, 9), now=now)
    monkeypatch.setattr(government_jobs, "fetch_taiwanjobs_company_jobs", lambda *a: sample)
    data = {"ticker": "3023.TW", "company_name": "信邦", "quote_type": "EQUITY",
            "company_identity": {"ticker": "3023.TW", "official_name": "信邦",
                                 "instrument_type": "EQUITY"}}
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker("3023.TW"), {"data": data})
    assert result.status == "success"
    assert result.value["job_openings_104"]["status"] == "unavailable"
    assert result.value["job_openings_taiwanjobs"]["current_open_job_count"] == 1
    assert result.audit["record_count"] == 1
    assert source_record_count("alternative_data", {**data, "alternative_data": result.value}) == 1
    wrong = {**data, "alternative_data": {**result.value,
             "company_legal_name_evidence": {**receipt, "official_ubn": "99999999"}}}
    assert source_record_count("alternative_data", wrong) == 0
