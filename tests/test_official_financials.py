from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import requests
import pytest

import official_financials
import official_financials_mops_conference as conference_financials


class FakeResponse:
    def __init__(self, *, json_payload=None, text: str = "<html></html>", status_code: int = 200) -> None:
        self._json_payload = json_payload
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code

    def json(self):
        return self._json_payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class FakeSession:
    def __init__(self, *, json_payload=None, text: str = "<html></html>") -> None:
        self.json_payload = json_payload
        self.text = text
        self.last_url = ""
        self.last_data = None
        self.last_headers = None
        self.last_timeout = None

    def get(self, url, **kwargs):
        self.last_url = url
        self.last_headers = kwargs.get("headers")
        self.last_timeout = kwargs.get("timeout")
        return FakeResponse(json_payload=self.json_payload)

    def post(self, url, **kwargs):
        self.last_url = url
        self.last_data = kwargs.get("data")
        self.last_headers = kwargs.get("headers")
        self.last_timeout = kwargs.get("timeout")
        return FakeResponse(text=self.text)


class TrackingSession(FakeSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.calls += 1
        return super().post(*args, **kwargs)


def test_twse_filters_ticker_and_normalizes_net_trades():
    session = FakeSession(json_payload=[
        {"證券代號": "2317", "外陸資買賣超股數(不含外資自營商)": "1"},
        {
            "證券代號": "2330",
            "外陸資買賣超股數(不含外資自營商)": "1,200",
            "投信買賣超股數": "(50)",
            "自營商買賣超股數": "200",
            "三大法人買賣超股數": "1,350",
        },
    ])

    result = official_financials.fetch_twse_institutional_trades("2330.TW", "2026-06-18", session=session)

    assert result == {
        "ticker": "2330",
        "date": "2026-06-18",
        "foreign_net": 1200,
        "investment_trust_net": -50,
        "dealer_net": 200,
        "total_net": 1350,
        "source": "TWSE OpenAPI",
    }
    assert session.last_url.endswith("/v1/fund/TWT38U13")
    assert session.last_timeout == official_financials.REQUEST_TIMEOUT
    assert "Mozilla" in session.last_headers["User-Agent"]


def test_twse_institutional_trades_uses_shared_http_client(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse(json_payload=[{
            "證券代號": "2330",
            "ForeignInvestorsNet": "100",
            "InvestmentTrustNet": "20",
            "DealerNet": "-5",
            "TotalNet": "115",
        }])

    monkeypatch.setattr(official_financials, "sync_get", fake_get)

    result = official_financials.fetch_twse_institutional_trades("2330.TW", "2026-06-18")

    assert result["total_net"] == 115
    assert calls[0]["provider"] == "TWSE OpenAPI"
    assert calls[0]["timeout"] == official_financials.REQUEST_TIMEOUT


def test_twse_rejects_non_taiwan_ticker_and_handles_errors():
    tracking = TrackingSession()
    assert official_financials.fetch_twse_institutional_trades("AAPL", "2026-06-18", session=tracking) is None
    assert official_financials.fetch_twse_institutional_trades("2330.US", "2026-06-18", session=tracking) is None
    assert official_financials.fetch_twse_institutional_trades("1234.TWO", "2026-06-18", session=tracking) is None
    assert tracking.calls == 0

    class BrokenSession(FakeSession):
        def get(self, *_args, **_kwargs):
            raise requests.Timeout("private body")

    assert official_financials.fetch_twse_institutional_trades("2330", "2026-06-18", session=BrokenSession()) is None


def test_mops_posts_period_and_extracts_balance_sheet(monkeypatch):
    frame = pd.DataFrame({
        "會計項目": ["資產總計", "負債總計", "權益總計"],
        "2025年第4季": ["2,000", "900", "1,100"],
    })
    monkeypatch.setattr(official_financials.pd, "read_html", lambda *_args, **_kwargs: [frame])
    session = FakeSession(text="<table></table>")

    result = official_financials.fetch_mops_balance_sheet("2330", 2025, 4, session=session)

    assert session.last_data["co_id"] == "2330"
    assert session.last_data["year"] == "114"
    assert session.last_data["season"] == "04"
    assert result["ticker"] == "2330"
    assert result["year"] == 2025
    assert result["season"] == 4
    assert result["total_assets"] == 2_000
    assert result["total_liabilities"] == 900
    assert result["total_equity"] == 1_100
    assert result["statement_scope"] == "consolidated"
    assert result["unit"] == "thousand_twd"
    assert result["source"] == "MOPS"
    assert result["raw_line_items"]["負債總計"] == 900


def test_mops_balance_sheet_uses_shared_http_client(monkeypatch):
    frame = pd.DataFrame({
        "會計項目": ["資產總計"],
        "2025年第4季": ["2,000"],
    })
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse(text="<table></table>")

    monkeypatch.setattr(official_financials.pd, "read_html", lambda *_args, **_kwargs: [frame])
    monkeypatch.setattr(official_financials, "sync_post", fake_post)

    result = official_financials.fetch_mops_balance_sheet("2330", 2025, 4)

    assert result["total_assets"] == 2_000
    assert calls[0]["provider"] == "MOPS"
    assert calls[0]["data"]["co_id"] == "2330"
    assert calls[0]["timeout"] == official_financials.REQUEST_TIMEOUT


def test_mops_investor_conference_extracts_latest_materials(monkeypatch):
    frame = pd.DataFrame({
        "公司代號": ["2317", "2330"],
        "公司名稱": ["鴻海", "台積電"],
        "召開法人說明會日期": ["2026/05/01", "2026/06/20"],
        "召開法人說明會時間": ["14:00", "15:00"],
        "召開法人說明會地點": ["線上", "台北"],
        "相關資訊": ["", "第一季營運成果"],
        "簡報檔案": ["", "https://example.test/2330.pdf"],
        "影音連結": ["", "https://example.test/2330-video"],
    })
    monkeypatch.setattr(conference_financials.pd, "read_html", lambda *_args, **_kwargs: [frame])
    session = FakeSession(text="<table></table>")

    result = official_financials.fetch_mops_investor_conference_events("2330.TW", year=2026, session=session)

    assert session.last_url.endswith("/ajax_t100sb02_1")
    assert session.last_data["co_id"] == "2330"
    assert session.last_data["year"] == "115"
    assert result == [{
        "ticker": "2330",
        "company_name": "台積電",
        "date": "2026-06-20",
        "time": "15:00",
        "location": "台北",
        "title": "台積電 法人說明會",
        "summary": "第一季營運成果",
        "materials": [
            {"label": "簡報檔案", "url": "https://example.test/2330.pdf"},
            {"label": "影音連結", "url": "https://example.test/2330-video"},
        ],
        "source": "MOPS investor conference",
        "source_url": official_financials.MOPS_INVESTOR_CONFERENCE_URL,
    }]


def test_mops_investor_conference_uses_shared_http_client(monkeypatch):
    frame = pd.DataFrame({
        "公司代號": ["2330"],
        "公司名稱": ["台積電"],
        "召開法人說明會日期": ["2026/06/20"],
    })
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse(text="<table></table>")

    monkeypatch.setattr(conference_financials.pd, "read_html", lambda *_args, **_kwargs: [frame])
    monkeypatch.setattr(conference_financials, "sync_post", fake_post)

    result = official_financials.fetch_mops_investor_conference_events("2330.TW", year=2026)

    assert result[0]["ticker"] == "2330"
    assert calls[0]["provider"] == "MOPS"
    assert calls[0]["data"]["co_id"] == "2330"
    assert calls[0]["timeout"] == conference_financials.REQUEST_TIMEOUT


def test_mops_investor_conference_can_query_one_month_without_year_cache(monkeypatch):
    session = FakeSession(text="查無符合條件之資料")

    result = official_financials.fetch_mops_investor_conference_events(
        "2002.TW", year=2026, month=9, session=session,
    )

    assert result == []
    assert session.last_data["year"] == "115"
    assert session.last_data["month"] == "09"


def test_mops_investor_conference_rejects_invalid_month_before_http():
    session = FakeSession(text="查無符合條件之資料")

    with pytest.raises(ValueError, match="month"):
        official_financials.fetch_mops_investor_conference_events(
            "2002.TW", year=2026, month=13, session=session,
        )

    assert session.last_url == ""


def test_mops_investor_conference_allows_slow_complete_response_with_bounded_connect_timeout(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse(text="查無符合條件之資料")

    monkeypatch.setattr(conference_financials, "sync_post", fake_post)

    assert conference_financials.fetch_mops_investor_conference_events("2330.TW", year=2026) == []
    assert calls[0]["timeout"] == (5, 30)


def test_mops_investor_conference_preserves_anchor_material_urls(monkeypatch):
    html = """
    <table>
      <tr>
        <th>公司代號</th><th>公司名稱</th><th>召開法人說明會日期</th>
        <th>簡報檔案</th><th>影音連結</th>
      </tr>
      <tr>
        <td>2330</td><td>台積電</td><td>2026/06/20</td>
        <td><a href="/mops/web/presentation.pdf">下載</a></td>
        <td><a href="https://webpro.twse.com.tw/WebPortal/vod/101/2330">觀看</a></td>
      </tr>
    </table>
    """
    def fail_read_html(*_args, **_kwargs):
        raise ValueError("no table parser")

    monkeypatch.setattr(conference_financials.pd, "read_html", fail_read_html)
    session = FakeSession(text=html)
    warnings = []
    monkeypatch.setattr(conference_financials, "_warn", lambda _provider, operation, _exc=None: warnings.append(operation))

    result = official_financials.fetch_mops_investor_conference_events("2330.TW", year=2026, session=session)

    assert result[0]["materials"] == [
        {"label": "簡報檔案", "url": "https://mopsov.twse.com.tw/mops/web/presentation.pdf"},
        {"label": "影音連結", "url": "https://webpro.twse.com.tw/WebPortal/vod/101/2330"},
    ]
    assert warnings == []


def test_mopsov_investor_conference_detail_page_preserves_official_pdf(monkeypatch):
    html = """
    <div id="div01"><center>
      <b>公司代號：</b>2855　　<b>公司名稱：</b>統一證<br><br>
      <table class="hasBorder">
        <tr><th>1</th><td><b>召開法人說明會日期：</b></td><td>115/08/26 時間：14 點 0 分</td></tr>
        <tr><td><b>召開法人說明會地點：</b></td><td>線上法說會</td></tr>
        <tr><td><b>法人說明會擇要訊息：</b></td><td>第二季營運成果</td></tr>
        <tr><td><b>中文檔案：</b></td><td><a href="/nas/STR/285520260826M001.pdf">285520260826M001.pdf</a></td></tr>
        <tr><td><b>英文檔案：</b></td><td><a href="/nas/STR/285520260826E001.pdf">285520260826E001.pdf</a></td></tr>
      </table>
    </center></div>
    """
    session = FakeSession(text=html)
    result = official_financials.fetch_mops_investor_conference_events("2855.TW", year=2026, session=session)

    assert session.last_url.startswith("https://mopsov.twse.com.tw/mops/web/ajax_t100sb")
    assert result[0]["ticker"] == "2855"
    assert result[0]["company_name"] == "統一證"
    assert result[0]["date"] == "2026-08-26"
    assert result[0]["summary"] == "第二季營運成果"
    assert result[0]["materials"] == [
        {"label": "中文簡報檔案", "url": "https://mopsov.twse.com.tw/nas/STR/285520260826M001.pdf"},
        {"label": "英文簡報檔案", "url": "https://mopsov.twse.com.tw/nas/STR/285520260826E001.pdf"},
    ]


def test_mopsov_future_conference_is_not_presented_as_completed(monkeypatch):
    html = """
    <div id="div01"><center><b>公司代號：</b>2308 <b>公司名稱：</b>台達電<br>
    <table class="hasBorder">
      <tr><td><b>召開法人說明會日期：</b></td><td>188/11/03 時間：14 點 0 分</td></tr>
      <tr><td><b>中文檔案：</b></td><td><a href="/nas/STR/230820991103M001.pdf">下載</a></td></tr>
    </table></center></div>
    """
    session = FakeSession(text=html)
    assert official_financials.fetch_mops_investor_conference_events(
        "2308.TW", year=2026, session=session) == []


def test_mopsov_year_list_selects_completed_event_and_exact_pdf(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 9)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 9, tzinfo=tz)

    monkeypatch.setattr(conference_financials, "date", FixedDate)
    monkeypatch.setattr(conference_financials, "datetime", FixedDateTime)
    html = """
    <input type="hidden" name="filePath" value="/home/html/nas/STR/" />
    <table class="hasBorder">
      <tr><th>公司代號</th><th>公司名稱</th><th>召開法人說明會日期</th>
          <th>召開法人說明會時間</th><th>召開法人說明會地點</th>
          <th>法人說明會擇要訊息</th><th>中文檔案</th><th>英文檔案</th></tr>
      <tr><th>中文檔案</th><th>英文檔案</th></tr>
      <tr><td>2308</td><td>台達電</td><td>115/10/05 至 115/11/03</td><td>14:00</td><td>台北</td><td>尚未完成的跨日場次</td>
          <td><a href="#">230820261103M001.pdf</a></td><td></td></tr>
      <tr><td>2308</td><td>台達電</td><td>115/09/22 至 115/09/24</td><td>14:00</td><td>香港</td><td>第二季資訊沿用較早簡報</td>
          <td><a href="#">230820260730M001.pdf</a></td><td></td></tr>
      <tr><td>2308</td><td>台達電</td><td>115/07/30</td><td>14:00</td><td>台北</td><td>第二季營運成果</td>
          <td><a href="#">230820260730M001.pdf</a></td><td></td></tr>
      <tr><td>12308</td><td>錯誤公司</td><td>115/08/01</td><td>14:00</td><td>台北</td><td>錯誤資料</td>
          <td><a href="#">1230820260801M001.pdf</a></td><td></td></tr>
    </table>
    """
    session = FakeSession(text=html)
    result = official_financials.fetch_mops_investor_conference_events("2308.TW", year=2026, session=session)

    assert session.last_url == "https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1"
    assert result[0]["date"] == "2026-09-22"
    assert result[0]["summary"] == "第二季資訊沿用較早簡報"
    assert result[0]["materials"] == [
        {"label": "中文簡報檔案（2026-07-30）", "url": "https://mopsov.twse.com.tw/nas/STR/230820260730M001.pdf"},
    ]
    assert all(row["ticker"] == "2308" and row["date"] <= "2026-10-09" for row in result)


def test_mopsov_year_list_does_not_reparse_ongoing_range_as_completed(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 9)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 9, tzinfo=tz)

    monkeypatch.setattr(conference_financials, "date", FixedDate)
    monkeypatch.setattr(conference_financials, "datetime", FixedDateTime)
    monkeypatch.setattr(conference_financials.pd, "read_html", lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("generic parser must not run")))
    html = """
    <input name="filePath" value="/home/html/nas/STR/" />
    <table><tr><th>公司代號</th><th>公司名稱</th><th>召開法人說明會日期</th>
      <th>時間</th><th>地點</th><th>相關資訊</th><th>中文檔案</th><th>英文檔案</th></tr>
      <tr><td>2308</td><td>台達電</td><td>115/10/05 至 115/10/13</td>
      <td>21:00</td><td>美國</td><td>仍在進行</td>
      <td><a href="#">230820260730M001.pdf</a></td><td></td></tr>
    </table>
    """
    assert official_financials.fetch_mops_investor_conference_events(
        "2308.TW", year=2026, session=FakeSession(text=html)) == []


def test_mops_uses_otc_type_for_two_suffix(monkeypatch):
    frame = pd.DataFrame({
        "會計項目": ["負債總計"],
        "2025年第4季": ["900"],
    })
    monkeypatch.setattr(official_financials.pd, "read_html", lambda *_args, **_kwargs: [frame])
    session = FakeSession(text="<table></table>")

    result = official_financials.fetch_mops_balance_sheet("1234.TWO", 2025, 4, session=session)

    assert session.last_data["TYPEK"] == "otc"
    assert result["total_liabilities"] == 900


def test_mops_handles_multiindex_negative_values_and_no_tables(monkeypatch):
    columns = pd.MultiIndex.from_tuples([("項目", "會計項目"), ("金額", "本期")])
    frame = pd.DataFrame([["負債總計", "(1,234)"]], columns=columns)
    monkeypatch.setattr(official_financials.pd, "read_html", lambda *_args, **_kwargs: [frame])

    result = official_financials.fetch_mops_balance_sheet("2330.TW", 2025, 4, session=FakeSession())

    assert result["total_liabilities"] == -1_234

    monkeypatch.setattr(official_financials.pd, "read_html", lambda *_args, **_kwargs: [])
    assert official_financials.fetch_mops_balance_sheet("2330", 2025, 4, session=FakeSession()) is None


def test_mops_selects_requested_period_column(monkeypatch):
    frame = pd.DataFrame({
        "會計項目": ["負債總計"],
        "2024年第4季": ["111"],
        "2025年第4季": ["222"],
    })
    monkeypatch.setattr(official_financials.pd, "read_html", lambda *_args, **_kwargs: [frame])

    result = official_financials.fetch_mops_balance_sheet("2330", 2025, 4, session=FakeSession())

    assert result["total_liabilities"] == 222


def test_mops_returns_none_when_requested_period_is_absent(monkeypatch):
    frame = pd.DataFrame({
        "會計項目": ["負債總計"],
        "2024年第4季": ["111"],
        "2023年第4季": ["222"],
    })
    monkeypatch.setattr(official_financials.pd, "read_html", lambda *_args, **_kwargs: [frame])

    assert official_financials.fetch_mops_balance_sheet("2330", 2025, 4, session=FakeSession()) is None


def test_mops_rejects_invalid_inputs_and_request_errors(monkeypatch):
    tracking = TrackingSession()
    assert official_financials.fetch_mops_balance_sheet("AAPL", 2025, 4, session=tracking) is None
    assert official_financials.fetch_mops_balance_sheet("2330.US", 2025, 4, session=tracking) is None
    assert official_financials.fetch_mops_balance_sheet("2330", "bad", 4, session=tracking) is None
    assert official_financials.fetch_mops_balance_sheet("2330", 2025, 5, session=tracking) is None
    assert tracking.calls == 0

    class BrokenSession(FakeSession):
        def post(self, *_args, **_kwargs):
            raise requests.Timeout("private body")

    assert official_financials.fetch_mops_balance_sheet("2330", 2025, 4, session=BrokenSession()) is None
