"""Public TWSE comparison rows are only usable when every annual fact is explicit."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from data_fetch.market_sources.official_mopsfin_financial import (
    MopsFinError, parse_statement, fetch_official_comparison_year,
)


LABELS = {
    "IncomeStatement": {
        "營業收入合計": "1,000", "母公司業主（淨利∕損）": "100",
        "營業毛利（毛損）淨額": "300", "營業利益（損失）": "200",
    },
    "BalanceSheet": {"資產總額": "2,000", "歸屬於母公司業主之權益合計": "1,500"},
    "CashflowStatement": {
        "營業活動之淨現金流入（流出）": "400",
        "取得不動產、廠房及設備": "-50", "取得無形資產": "-10",
    },
}


def statement(kind, issuer="6409", *, missing=(), scope="合併", unit="新台幣仟元"):
    labels = [(key, value) for key, value in LABELS[kind].items() if key not in missing]
    left = "".join(f"<tr><td>{key}</td></tr>" for key, _ in labels)
    right = "".join(f"<tr><td>{value}</td></tr>" for _, value in labels)
    return (f'<span>金額單位：{unit}</span><table><thead><tr><th>報表類別</th></tr>'
            f'<tr><th>會計科目</th></tr></thead><tbody>{left}</tbody></table>'
            f'<table><thead><tr><th>{scope}</th></tr><tr><th>{issuer} 測試</th></tr>'
            f'</thead><tbody>{right}</tbody></table>').encode()


def test_cashflow_requires_issuer_scope_twd_and_explicit_acquisitions():
    row = parse_statement(statement("CashflowStatement"), "6409", "CashflowStatement")
    assert row["CashFlowsFromUsedInOperatingActivities"] == 400000
    assert row["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"] == -50000
    assert row["PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"] == -10000
    for raw in (
        statement("CashflowStatement", issuer="6282"),
        statement("CashflowStatement", scope="個別"),
        statement("CashflowStatement", unit="美元仟元"),
        statement("CashflowStatement", missing=("取得無形資產",)),
    ):
        with pytest.raises(MopsFinError):
            parse_statement(raw, "6409", "CashflowStatement")


def test_one_year_fetch_keeps_three_document_receipts_and_never_infers_zero(monkeypatch):
    import data_fetch.market_sources.official_mopsfin_financial as source

    calls = []

    def request(_client, kind, issuer, year):
        calls.append((kind, issuer, year))
        return statement(kind)

    monkeypatch.setattr(source, "_request_statement", request)
    result = fetch_official_comparison_year("6409", 2022, client=object())
    assert result["facts"]["Revenue"] == 1000000
    assert len(result["documents"]) == len(calls) == 3
    assert all(doc["year"] == 2022 and doc["period_end"] == "2022-12-31"
               for doc in result["documents"])

    def missing_intangible(_client, kind, _issuer, _year):
        return statement(kind, missing=("取得無形資產",) if kind == "CashflowStatement" else ())

    monkeypatch.setattr(source, "_request_statement", missing_intangible)
    with pytest.raises(MopsFinError, match="取得無形資產"):
        fetch_official_comparison_year("6409", 2022, client=object())


def test_optional_request_observer_records_official_comparison_http_attempt():
    import data_fetch.market_sources.official_mopsfin_financial as source

    class Response:
        status_code=200
        content=b"captured official comparison"

    class Client:
        def post(self,*_args,**_kwargs):return Response()

    observations=[]
    raw=source._request_statement(Client(),"IncomeStatement","6409",2022,request_observer=observations.append)
    assert raw==Response.content
    assert len(observations)==1
    assert observations[0]["provider"]==source.PROVIDER
    assert observations[0]["http_request_sent"]is True and observations[0]["http_status"]==200
    assert observations[0]["response_bytes"]==len(raw)
