"""Offline market applicability, observation lineage, and missing-value boundaries."""
import pytest

from chip_data_fetcher import fetch_twse_margin_short_sales


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class Session:
    def __init__(self, margin_date=None, borrowed_date="20260921"):
        self.calls = []
        self.margin_date = margin_date
        self.borrowed_date = borrowed_date

    def get(self, url, **kwargs):
        self.calls.append(url)
        if "MI_MARGN" in url:
            return Response([{"股票代號": "2330", "日期": self.margin_date,
                              "融資今日餘額": "0", "融券今日餘額": None}])
        return Response({"date": self.borrowed_date,
                         "data": [["2330"] + [None] * 8 + ["0", None, None, "1000"]]})


def test_two_endpoint_never_sends_twse_requests():
    from test_tpex_credit_source import Session as TpexSession
    session = TpexSession()
    result = fetch_twse_margin_short_sales("3324.TWO", session=session)
    assert result["status"] == "success"
    assert all("tpex.org.tw" in url for url in session.calls)


def test_margin_and_borrowed_source_dates_remain_independent():
    result = fetch_twse_margin_short_sales("2330.TW", session=Session("20260918"))
    assert result["margin_as_of_date"] == "2026-09-18"
    assert result["borrowed_short_as_of_date"] == "2026-09-21"
    assert result["as_of_date"] == "2026-09-18"
    assert result["margin_balance"] == 0
    assert result["short_balance"] is None
    assert result["borrowed_short_sale_today"] == 0
    assert result["borrowed_short_return_today"] is None


@pytest.mark.parametrize("bad_date", [None, "", "unknown", "20260999"])
def test_missing_margin_date_cannot_borrow_date_from_other_feed(bad_date):
    result = fetch_twse_margin_short_sales("2330.TW", session=Session(bad_date))
    assert result.get("as_of_date") is None
    assert result["margin_as_of_date"] is None
    assert result["borrowed_short_as_of_date"] == "2026-09-21"
    assert result["margin_date_status"] == "unknown"


@pytest.mark.parametrize("value", ["", "--", "NaN"])
def test_tdcc_missing_percentage_is_not_reported_as_zero(value):
    from chip_data_fetcher import fetch_tdcc_shareholder_distribution

    class CsvSession:
        def get(self, *args, **kwargs):
            response = Response(None)
            response.text = ("資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%\n"
                             f"20260918,2330,15,1,1,{value}\n"
                             "20260918,2330,1,1,1,0\n")
            return response

    result = fetch_tdcc_shareholder_distribution("2330.TW", session=CsvSession())
    assert result["major_holders_gt_1000_lots_pct"] is None
    assert result["retail_holders_lt_50_lots_pct"] is None  # Missing levels 2..8 cannot be treated as zero.
    assert result["availability"] == "partial"
