import sys
import ssl
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class FakeResponse:
    def __init__(self, text="", payload=None, status_code=200):
        self.text = text
        self._payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json" if payload is not None else "text/csv"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_default_chip_data_session_keeps_certificate_checks_without_x509_strict():
    from chip_data_fetcher import _build_http_session

    session = _build_http_session()
    context = session.get_adapter("https://").poolmanager.connection_pool_kw["ssl_context"]

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        assert not context.verify_flags & ssl.VERIFY_X509_STRICT


def test_fetch_tdcc_shareholder_distribution_calculates_major_and_retail_ratios():
    from chip_data_fetcher import fetch_tdcc_shareholder_distribution

    csv_text = """資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%
20260618,2308,1,120,8000,0.08
20260618,2308,2,220,7000,0.07
20260618,2308,3,320,9000,0.09
20260618,2308,4,420,11000,0.11
20260618,2308,5,520,12000,0.12
20260618,2308,6,620,13000,0.13
20260618,2308,7,720,14000,0.14
20260618,2308,8,820,15000,0.15
20260618,2308,9,920,16000,0.16
20260618,2308,10,1020,17000,0.17
20260618,2308,11,1120,18000,0.18
20260618,2308,12,1220,19000,0.19
20260618,2308,13,1320,20000,0.20
20260618,2308,14,1420,21000,0.21
20260618,2308,15,1520,22000,0.22
20260618,2317,15,1,999,9.99
"""
    session = FakeSession(FakeResponse(text=csv_text))

    result = fetch_tdcc_shareholder_distribution("2308.TW", "2026-06-18", session=session)

    assert result["ticker"] == "2308"
    assert result["as_of_date"] == "20260618"
    assert result["major_holders_gt_1000_lots_pct"] == pytest.approx(0.22)
    assert result["retail_holders_lt_50_lots_pct"] == pytest.approx(0.89)
    assert result["source"] == "TDCC OpenData"
    assert result["row_count"] == 15


def test_fetch_tdcc_shareholder_distribution_uses_latest_date_when_date_missing():
    from chip_data_fetcher import fetch_tdcc_shareholder_distribution

    csv_text = """資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%
20260612,2308,15,1,1,40.00
20260618,2308,1,1,1,0.10
20260618,2308,2,1,1,0.20
20260618,2308,15,1,1,45.00
"""
    result = fetch_tdcc_shareholder_distribution("2308", None, session=FakeSession(FakeResponse(text=csv_text)))

    assert result["as_of_date"] == "20260618"
    assert result["major_holders_gt_1000_lots_pct"] == pytest.approx(45.0)
    assert result["retail_holders_lt_50_lots_pct"] == pytest.approx(0.30)


def test_fetch_tdcc_shareholder_distribution_returns_error_payload_on_missing_rows():
    from chip_data_fetcher import fetch_tdcc_shareholder_distribution

    csv_text = "資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%\n20260618,2317,15,1,1,1.00\n"
    result = fetch_tdcc_shareholder_distribution("2308", "20260618", session=FakeSession(FakeResponse(text=csv_text)))

    assert result["status"] == "unavailable"
    assert "2308" in result["message"]


def test_fetch_twse_margin_short_sales_merges_margin_and_borrowed_short_balances():
    from chip_data_fetcher import fetch_twse_margin_short_sales

    session = FakeSession(
        FakeResponse(
            payload=[
                {
                    "股票代號": "2308",
                    "股票名稱": "台達電",
                    "融資買進": "1,200",
                    "融資賣出": "300",
                    "融資今日餘額": "12,345",
                    "融券今日餘額": "456",
                }
            ]
        )
    )

    result = fetch_twse_margin_short_sales("2308.TW", session=session)

    assert result["ticker"] == "2308"
    assert result["company_name"] == "台達電"
    assert result["margin_purchase"] == 1200
    assert result["margin_sale"] == 300
    assert result["margin_balance"] == 12345
    assert result["short_balance"] == 456
    assert result["source"] == "TWSE OpenAPI MI_MARGN"


def test_fetch_twse_margin_short_sales_uses_legacy_borrowed_short_endpoint():
    from chip_data_fetcher import fetch_twse_margin_short_sales

    class RoutedSession:
        def get(self, url, **kwargs):
            if "MI_MARGN" in url:
                return FakeResponse(payload=[{"股票代號": "2308", "股票名稱": "台達電", "融資今日餘額": "12,345", "融券今日餘額": "456"}])
            if "TWT93U" in url:
                return FakeResponse(
                    payload={
                        "date": "20260618",
                        "fields": ["代號", "名稱", "前日餘額", "賣出", "買進", "現券", "今日餘額", "次一營業日限額", "前日餘額", "當日賣出", "當日還券", "當日調整", "當日餘額", "次一營業日可限額", "備註"],
                        "data": [["2308", "台達電", "0", "0", "0", "0", "456,000", "0", "10,000", "20,000", "1,000", "0", "29,000", "0", " "]],
                    }
                )
            raise AssertionError(url)

    result = fetch_twse_margin_short_sales("2308", session=RoutedSession())

    assert result["as_of_date"] == "20260618"
    assert result["borrowed_short_sale_today"] == 20000
    assert result["borrowed_short_sale_balance"] == 29000
