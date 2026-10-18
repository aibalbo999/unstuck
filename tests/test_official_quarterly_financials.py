"""Offline contracts for the explicitly partial official quarter fallback."""
from __future__ import annotations

import csv
from datetime import date
import io
import time

from official_response_evidence import archive_response

from data_fetch.market_sources import official_quarterly_financials as quarterly


def _csv(fields, row):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow(row)
    return output.getvalue().encode("utf-8")


def _fixtures(ticker="3703.TW"):
    common = {"出表日期": "1151017", "年度": "115", "季別": "2",
              "公司代號": ticker.split(".")[0], "公司名稱": "欣陸"}
    balance_url = quarterly.quarterly_url("07", "L", "ci")
    income_url = quarterly.quarterly_url("06", "L", "ci")
    balance_fields = [*quarterly.IDENTITY_FIELDS, "資產總計", "負債總計", "權益總計"]
    income_fields = [*quarterly.IDENTITY_FIELDS, "營業收入", "本期淨利（淨損）"]
    balance = _csv(balance_fields, {**common, "資產總計": "1,234,567", "負債總計": "345,678", "權益總計": "888,889"})
    income = _csv(income_fields, {**common, "營業收入": "456,789", "本期淨利（淨損）": "12,345"})
    now = time.time()
    receipts = {
        balance_url: (balance, archive_response(balance, source_url=balance_url, retrieved_at=now, http_status=200, max_bytes=quarterly.MAX_BYTES)),
        income_url: (income, archive_response(income, source_url=income_url, retrieved_at=now, http_status=200, max_bytes=quarterly.MAX_BYTES)),
    }
    return receipts


def _openapi_json(url, *, ticker="3703.TW", name="欣陸", statement="07"):
    row={"出表日期":"1151017","年度":"115","季別":"2",
         "公司代號":ticker.split(".")[0],"公司名稱":name}
    row.update({"資產總計":"1,234,567","負債總計":"345,678","權益總計":"888,889"}
               if statement=="07" else {"營業收入":"456,789","本期淨利（淨損）":"12,345"})
    return __import__("json").dumps([row],ensure_ascii=False).encode("utf-8")


def test_latest_quarter_fallback_returns_verified_point_and_ytd_tables(monkeypatch):
    receipts = _fixtures()
    monkeypatch.setattr(quarterly, "_today", lambda: date(2026, 10, 17))

    class FakeHttp:
        def __init__(self, deadline):
            self.deadline = deadline
            self.http_request_count = 2
            self.components = []

        def get(self, url):
            raw, receipt = receipts[url]
            self.components.append({"url": url, "http_request_sent": True, "cache_hit": False,
                                    "http_status": 200, "response_bytes": len(raw),
                                    "response_sha256": receipt["raw_response_sha256"],
                                    "original_receipt": receipt})
            return raw, receipt

    monkeypatch.setattr(quarterly, "QuarterlyFinancialHttp", FakeHttp)
    result = quarterly.fetch_latest_quarter_result("3703.TW", {"industry": "Construction"})

    assert result["audit"]["status"] == "success", result["audit"]
    assert result["audit"]["coverage_status"] == "latest_quarter_only"
    value = result["value"]
    assert value["period"] == {"year": 2026, "quarter": 2, "period_end": "2026-06-30"}
    assert value["income_period_basis"] == "year_to_date_cumulative"
    assert value["balance_period_basis"] == "quarter_end_instant"
    assert value["filed_unit"] == "thousands" and value["cash_flow_statement_available"] is False
    assert value["tables"]["balance_sheet"]["row"]["資產總計"] == "1,234,567"
    assert value["tables"]["income_statement_ytd"]["row"]["營業收入"] == "456,789"
    assert quarterly.project_latest_quarter(value, "3703.TW") is not None
    from prompt_builder import format_data_for_prompt
    prompt = format_data_for_prompt({"ticker":"3703.TW", "latest_quarter_financials":value}, compact=True)
    assert '"latest_quarter_financials"' in prompt and '"year_to_date_cumulative"' in prompt
    assert '"TWD_thousands"' not in prompt  # the unit remains explicit, not relabeled or converted
    assert '金額單位為新臺幣仟元' in prompt and '未提供現金流量表' in prompt


def test_latest_quarter_parser_rejects_wrong_issuer_and_old_period(monkeypatch):
    today = date(2026, 10, 17)
    url = quarterly.quarterly_url("07", "L", "ci")
    fields = [*quarterly.IDENTITY_FIELDS, "資產總計", "股本"]
    wrong = _csv(fields, {"出表日期": "1151017", "年度": "115", "季別": "2",
                          "公司代號": "2454", "公司名稱": "聯發科", "資產總計": "123", "股本": "1"})
    rows, _ = quarterly.parse_quarterly_csv(wrong, url, today)
    try:
        quarterly._select_record(rows, "3703.TW", "07", today)
    except ValueError as exc:
        assert "issuer" in str(exc)
    else:
        raise AssertionError("mismatched company code accepted")

    old = _csv(fields, {"出表日期": "1140401", "年度": "113", "季別": "4",
                        "公司代號": "3703", "公司名稱": "欣陸", "資產總計": "123", "股本": "1"})
    rows, _ = quarterly.parse_quarterly_csv(old, url, today)
    try:
        quarterly._select_record(rows, "3703.TW", "07", today)
    except ValueError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("stale quarter accepted")


def test_openapi_quarterly_route_is_secondary_free_l_market_entry():
    balance=quarterly.quarterly_source_urls("07","L","ci")
    income=quarterly.quarterly_source_urls("06","L","ci")
    otc=quarterly.quarterly_source_urls("07","O","ci")
    assert balance==[
        "https://mopsfin.twse.com.tw/opendata/t187ap07_L_ci.csv",
        "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci",
    ]
    assert income[-1].endswith("/t187ap06_L_ci")
    assert len(otc)==1 and otc[0].startswith("https://mopsfin.twse.com.tw/")


def test_official_openapi_json_fallback_recovers_both_latest_quarter_statements(monkeypatch):
    from data_fetch.market_sources.official_quarterly_financial_transport import allowed_urls
    from search_provider_runtime import SourceResponseError

    monkeypatch.setattr(quarterly,"_today",lambda:date(2026,10,17))
    urls={key:quarterly.quarterly_source_urls(statement,"L","ci")[-1]
          for key,statement in (("balance_sheet","07"),("income_statement_ytd","06"))}
    raw_by_url={url:_openapi_json(url,statement="07" if key=="balance_sheet" else "06")
                for key,url in urls.items()}
    receipts={url:archive_response(raw,source_url=url,retrieved_at=time.time(),http_status=200,
                                   max_bytes=quarterly.MAX_BYTES)
              for url,raw in raw_by_url.items()}
    class FallbackHttp:
        def __init__(self,deadline):
            self.deadline=deadline;self.http_request_count=4;self.components=[]
        def get(self,url):
            self.components.append({"url":url,"http_request_sent":True,"cache_hit":False})
            if url.startswith("https://mopsfin.twse.com.tw/"):
                raise SourceResponseError("transport_error")
            return raw_by_url[url],receipts[url]

    monkeypatch.setattr(quarterly,"QuarterlyFinancialHttp",FallbackHttp)
    result=quarterly.fetch_latest_quarter_result("3703.TW",{"industry":"Construction"})
    assert result["audit"]["status"]=="success",result["audit"]
    assert result["value"]["coverage_status"]=="latest_quarter_only"
    for key,url in urls.items():
        assert result["value"]["tables"][key]["source_url"]==url
        assert url in allowed_urls()
