import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import external_data_twse  # noqa: E402


class FakeFinMindLoader:
    def login_by_token(self, api_token):
        self.api_token = api_token

    def taiwan_stock_income_statement(self, stock_id, start_date):
        rows = []
        for date, revenue, gross_profit, operating_income, net_income in [
            ("2025-03-31", 1000.0, 400.0, 200.0, 100.0),
            ("2025-06-30", 1100.0, 440.0, 220.0, 110.0),
            ("2025-09-30", 1200.0, 480.0, 240.0, 120.0),
            ("2025-12-31", 1300.0, 520.0, 260.0, 130.0),
        ]:
            rows.extend([
                {"date": date, "type": "Revenue", "value": revenue},
                {"date": date, "type": "GrossProfit", "value": gross_profit},
                {"date": date, "type": "OperatingIncome", "value": operating_income},
                {"date": date, "type": "IncomeAfterTaxes", "value": net_income},
            ])
        return pd.DataFrame(rows)

    def taiwan_stock_balance_sheet(self, stock_id, start_date):
        return pd.DataFrame([
            {"date": "2025-12-31", "type": "TotalLiabilities", "value": 700.0},
        ])

    def taiwan_stock_cash_flows_statement(self, stock_id, start_date):
        rows = []
        for date, ocf, capex in [
            ("2025-03-31", 150.0, -50.0),
            ("2025-06-30", 160.0, -60.0),
            ("2025-09-30", 170.0, -70.0),
            ("2025-12-31", 180.0, -80.0),
        ]:
            rows.extend([
                {"date": date, "type": "NetCashInflowFromOperatingActivities", "value": ocf},
                {"date": date, "type": "PurchaseOfPropertyPlantAndEquipment", "value": capex},
            ])
        return pd.DataFrame(rows)


def test_fetch_twse_official_data_formats_finmind_statement_payload(monkeypatch):
    monkeypatch.setattr(external_data_twse, "DataLoader", FakeFinMindLoader, raising=False)
    monkeypatch.setattr(external_data_twse, "FINMIND_API_TOKEN", "test-token", raising=False)
    monkeypatch.setattr(external_data_twse, "_today_iso", lambda: "2026-06-19", raising=False)

    result = external_data_twse.fetch_twse_official_data("2330.TW")

    assert result == {
        "revenue_ttm_raw": 4600.0,
        "net_income_ttm_raw": 460.0,
        "free_cash_flow_raw": 400.0,
        "gross_margin_raw": 0.4,
        "operating_margin_raw": 0.2,
        "profit_margin_raw": 0.1,
        "total_debt_raw": 700.0,
        "source": "FinMind_TWSE",
        "fetch_date": "2026-06-19",
    }


def test_fetch_twse_official_data_uses_offline_twse_openapi_fixture(monkeypatch):
    fixture = ROOT / "tests" / "fixtures" / "twse_openapi_official_2330.json"
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return fixture.read_bytes()

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        return FakeResponse()

    monkeypatch.setattr(external_data_twse, "DataLoader", None, raising=False)
    monkeypatch.setattr(external_data_twse.urllib.request, "urlopen", fake_urlopen, raising=False)
    monkeypatch.setattr(external_data_twse, "_today_iso", lambda: "2026-06-19", raising=False)

    result = external_data_twse.fetch_twse_official_data("2330.TW")

    assert calls
    assert result == {
        "revenue_ttm_raw": 4600.0,
        "net_income_ttm_raw": 460.0,
        "free_cash_flow_raw": 400.0,
        "gross_margin_raw": 0.4,
        "operating_margin_raw": 0.2,
        "profit_margin_raw": 0.1,
        "total_debt_raw": 730.0,
        "source": "TWSE_OpenAPI",
        "fetch_date": "2026-06-19",
    }
