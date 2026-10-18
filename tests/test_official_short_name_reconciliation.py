"""A saved issuer label can be reconciled only with its exact current anchor."""

from datetime import date, datetime
import copy
import json
from zoneinfo import ZoneInfo

import pytest

TICKER = "7740.TW"
OLD = "熙特爾"
CURRENT = "熙特爾-創"
LEGAL = "熙特爾新能源股份有限公司"
UBN = "55118186"
MARKER = {"policy": "seetel-current-twse-name-v1",
          "requested_short_name": OLD, "current_short_name": CURRENT}
ROW = {"出表日期": "1151009", "公司代號": "7740", "公司名稱": LEGAL,
       "公司簡稱": CURRENT, "營利事業統一編號": UBN}


def select(row=ROW, ticker=TICKER, short=OLD, today=date(2026, 10, 10)):
    from data_fetch.market_sources.official_company_legal_name import parse_roster, select_legal_name
    return select_legal_name(parse_roster(json.dumps([row]).encode(), ".TW"),
                             ticker, short, today=today)


def test_saved_seetel_label_gets_current_exact_official_anchor():
    receipt = select()
    assert receipt is not None
    assert receipt["official_short_name"] == CURRENT
    assert receipt["legal_name"] == LEGAL and receipt["official_ubn"] == UBN
    assert receipt["as_of"] == "2026-10-09"
    assert receipt["short_name_reconciliation"] == MARKER
    assert "short_name_reconciliation" not in select(short=CURRENT)


@pytest.mark.parametrize("row,ticker,short,today", [
    ({**ROW, "公司代號": "7741"}, TICKER, OLD, date(2026, 10, 10)),
    (ROW, "7740.TWO", OLD, date(2026, 10, 10)),
    (ROW, TICKER, "熙特爾-KY", date(2026, 10, 10)),
    ({**ROW, "公司簡稱": "熙特爾-新"}, TICKER, OLD, date(2026, 10, 10)),
    ({**ROW, "公司名稱": "其他新能源股份有限公司"}, TICKER, OLD, date(2026, 10, 10)),
    ({**ROW, "營利事業統一編號": "55118187"}, TICKER, OLD, date(2026, 10, 10)),
    ({**ROW, "營利事業統一編號": "00000000"}, TICKER, OLD, date(2026, 10, 10)),
    (ROW, TICKER, OLD, date(2026, 10, 24)),
    (ROW, TICKER, OLD, date(2026, 10, 8)),
])
def test_reconciliation_does_not_strip_suffixes_or_relax_anchor(row, ticker, short, today):
    assert select(row, ticker, short, today) is None


def receipt_now():
    from data_fetch.market_sources import official_company_legal_name as names
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    row = {**ROW, "出表日期": f"{now.year-1911:03d}{now.month:02d}{now.day:02d}"}
    value = names.select_legal_name(names.parse_roster(json.dumps([row]).encode(), ".TW"),
                                    TICKER, OLD, today=now.date())
    assert value is not None
    return {**value, "fetched_at_epoch": now.timestamp(), "cache_hit": False}


def test_saved_anchor_is_reverified_with_explicit_reconciliation():
    from data_fetch.market_sources.official_company_legal_name import (
        verified_legal_name_from_evidence, verified_official_ubn_from_evidence,
    )
    receipt = receipt_now()
    assert verified_legal_name_from_evidence(receipt, TICKER, OLD) == LEGAL
    assert verified_official_ubn_from_evidence(receipt, TICKER, OLD) == UBN
    assert verified_legal_name_from_evidence(receipt, TICKER, CURRENT) == LEGAL
    for change in ({"short_name_reconciliation": None},
                   {"short_name_reconciliation": {**MARKER, "requested_short_name": "其他公司"}},
                   {"short_name_reconciliation": {**MARKER, "policy": "unverified"}},
                   {"official_ubn": "55118187"}, {"legal_name": "其他股份有限公司"},
                   {"official_short_name": OLD}, {"ticker": "7741.TW"},
                   {"source_url": "https://example.invalid"}, {"stale": True}):
        assert verified_legal_name_from_evidence({**receipt, **change}, TICKER, OLD) == ""


def test_original_saved_report_context_can_count_exact_issuer_jobs(monkeypatch):
    import alternative_data_fetcher
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.market_sources import official_company_legal_name as names
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count

    receipt = receipt_now()
    # Exercise the provider and saved-snapshot count; mock only remote job discovery.
    monkeypatch.setattr(names, "get_official_legal_name", lambda *a: receipt)
    calls = []
    def jobs(name, **kwargs):
        calls.append((name, kwargs))
        return {"status": "success", "company_name": name, "job_count": None,
                "source": "104 Company Jobs API", "evidence_kind": "company_job_postings",
                "query_scope": "exact_company_recent_postings",
                "source_url": "https://www.104.com.tw/jobs/search/api/jobs?kwop=2",
                "response_sha256": "b" * 64, "recent_company_job_count": 1,
                "job_postings": [{"title": "維運專員", "url": "https://www.104.com.tw/job/921ja",
                                  "employer": LEGAL, "source_employer": LEGAL,
                                  "employer_match_basis": "exact_legal_name",
                                  "employer_id": "130000000175315", "job_no": "15211846"}]}
    monkeypatch.setattr(alternative_data_fetcher, "fetch_104_company_jobs", jobs)
    monkeypatch.setattr(alternative_data_fetcher, "fetch_1111_job_openings_count",
                        lambda *a, **k: {"status": "unavailable", "job_count": None})
    data = {"ticker": TICKER, "company_name": OLD, "quote_type": "EQUITY",
            "company_identity": {"ticker": TICKER, "official_name": OLD,
                                 "instrument_type": "EQUITY", "legal_name": None}}
    before = copy.deepcopy(data)
    result = AlternativeJobOpeningsProvider()._fetch_uncached(FetchRequest.from_ticker(TICKER), {"data": data})
    assert calls == [(LEGAL, {"official_short_name": OLD, "official_ubn": UBN})]
    assert result.status == "success" and result.audit["record_count"] == 1
    assert source_record_count("alternative_data", {**data, "alternative_data": result.value}) == 1
    assert data == before
    damaged = copy.deepcopy(result.value)
    damaged["company_legal_name_evidence"].pop("short_name_reconciliation")
    assert source_record_count("alternative_data", {**data, "alternative_data": damaged}) == 0
