"""An official UBN binds a known source spelling; job identities still agree."""
from copy import deepcopy
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from data_fetch.market_sources.taiwanjobs_company_jobs import (
    fetch_taiwanjobs_company_jobs, verified_taiwanjobs_job_count,
)

CANONICAL = "台灣化學纖維股份有限公司"
SOURCE = "臺灣化學纖維股份有限公司"
UBN = "58650902"
NOW = datetime(2026, 10, 10, tzinfo=ZoneInfo("Asia/Taipei")).timestamp()


class GovernmentClient:
    def __init__(self, name=SOURCE, ubn=UBN, expires="2026/10/31", detail_name=None,
                 job_query="R2=11&amp;EMPLOYER_ID=84773&amp;HIRE_ID=14713667"):
        self.name, self.ubn, self.expires = name, ubn, expires
        self.detail_name = name if detail_name is None else detail_name
        self.job_query = job_query
        self.queries = []

    def get(self, url, **kwargs):
        if url.endswith("job_search_list.aspx"):
            body = ('<form id="form1"><input name="__VIEWSTATE" type="hidden" value="state">'
                    '<input name="ctl00$CPH1$SearchBar$txtKeywordComp" type="text"></form>')
        elif "company_desc2.aspx" in url:
            body = (f'<h2 id="CPH1_h1_COMPNAME">{self.name}</h2><dl><dt>統一編號</dt><dd>{self.ubn}</dd></dl>'
                    f'<a id="CPH1_lv_company_job_lnk_jobDetail_0" href="/Internet/index/JobDetail.aspx?{self.job_query}">輔機操作員 (其它機械操作員)</a>')
        else:
            body = (f'<h2>輔機操作員</h2><a href="/Internet/jobwanted/company_desc2.aspx?EMPLOYER_ID=84773&amp;BRANCH_ID=">{self.detail_name}</a>'
                    f'<dl><dt>工作代碼</dt><dd>14713667</dd></dl><dl><dt>應徵截止日期</dt><dd>{self.expires}</dd></dl>')
        return self.response(url, body)

    def post(self, url, data, **kwargs):
        self.queries.append(data["ctl00$CPH1$SearchBar$txtKeywordComp"])
        body = (f'<a href="/Internet/jobwanted/company_desc2.aspx?EMPLOYER_ID=84773&amp;BRANCH_ID=">{self.name}</a>'
                if self.queries[-1] == self.name.removesuffix("股份有限公司") else "<p>查無資料</p>")
        return self.response("https://job.taiwanjobs.gov.tw/internet/index/jobQuery_result_comp2.aspx", body)

    @staticmethod
    def response(url, body):
        return SimpleNamespace(content=body.encode(), text=body, url=url,
                               raise_for_status=lambda: None)


def fetch(client, ticker="1326.TW", company=CANONICAL, ubn=UBN):
    return fetch_taiwanjobs_company_jobs(ticker, company, ubn, client=client,
                                         today=date(2026, 10, 10), now=NOW)


def test_known_issuer_source_spelling_restores_verified_jobs_without_renaming_issuer():
    client = GovernmentClient()
    value = fetch(client)
    assert value["status"] == "success"
    assert client.queries == [SOURCE.removesuffix("股份有限公司")]
    assert value["company_name"] == CANONICAL
    assert value["source_company_name"] == SOURCE
    assert value["job_postings"][0]["employer"] == CANONICAL
    assert value["job_postings"][0]["source_employer"] == SOURCE
    assert value["job_count"] is None
    assert verified_taiwanjobs_job_count(value, "1326.TW", CANONICAL, UBN, now=NOW + 1) == 1


def test_real_source_path_case_is_canonical_after_identity_validation():
    company, ubn = "信邦電子股份有限公司", "23542766"
    value = fetch(GovernmentClient(name=company, ubn=ubn), "3023.TW", company, ubn)
    assert value["status"] == "success"
    assert value["job_postings"][0]["url"] == "https://job.taiwanjobs.gov.tw/internet/index/JobDetail.aspx?R2=11&EMPLOYER_ID=84773&HIRE_ID=14713667"
    assert verified_taiwanjobs_job_count(value, "3023.TW", company, ubn, now=NOW + 1) == 1


@pytest.mark.parametrize("client,ticker,company,ubn", [
    (GovernmentClient(ubn="99999999"), "1326.TW", CANONICAL, UBN),
    (GovernmentClient(), "1326.TW", CANONICAL, "99999999"),
    (GovernmentClient(), "1326.TWO", CANONICAL, UBN),
    (GovernmentClient(), "6505.TW", CANONICAL, UBN),
    (GovernmentClient(name="臺灣化學纖維子公司股份有限公司"), "1326.TW", CANONICAL, UBN),
    (GovernmentClient(detail_name="臺灣化學纖維子公司股份有限公司"), "1326.TW", CANONICAL, UBN),
    (GovernmentClient(expires="2026/10/09"), "1326.TW", CANONICAL, UBN),
    (GovernmentClient(expires=""), "1326.TW", CANONICAL, UBN),
])
def test_reconciliation_preserves_issuer_and_open_job_boundaries(client, ticker, company, ubn):
    value = fetch(client, ticker, company, ubn)
    assert value["status"] == "unavailable"
    assert value["current_open_job_count"] is None


@pytest.mark.parametrize("field", ["policy", "requested_legal_name", "source_legal_name", "official_ubn"])
def test_saved_reconciliation_must_remain_bound_to_the_same_issuer(field):
    value = fetch(GovernmentClient())
    assert value["status"] == "success"
    changed = deepcopy(value)
    changed["employer_name_reconciliation"][field] = "wrong"
    assert verified_taiwanjobs_job_count(changed, "1326.TW", CANONICAL, UBN, now=NOW + 1) == 0


def test_saved_source_name_and_marker_cannot_be_deleted_or_changed():
    value = fetch(GovernmentClient())
    assert value["status"] == "success"
    for field in ("employer_name_reconciliation", "source_company_name"):
        changed = deepcopy(value)
        changed.pop(field)
        assert verified_taiwanjobs_job_count(changed, "1326.TW", CANONICAL, UBN, now=NOW + 1) == 0
    changed = deepcopy(value)
    changed["job_postings"][0]["source_employer"] = "子公司"
    assert verified_taiwanjobs_job_count(changed, "1326.TW", CANONICAL, UBN, now=NOW + 1) == 0


@pytest.mark.parametrize("extra", ["&amp;HIRE_ID=99999999", "&amp;EMPLOYER_ID=99999"])
def test_canonicalization_does_not_hide_ambiguous_source_identity(extra):
    value = fetch(GovernmentClient(job_query="R2=11&amp;EMPLOYER_ID=84773&amp;HIRE_ID=14713667" + extra))
    assert value["status"] == "unavailable"
