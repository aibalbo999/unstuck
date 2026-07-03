"""Taiwan Open Data (data.gov.tw / BOT) provider for macro indicators."""

from __future__ import annotations

import csv
from io import StringIO
from external_http_client import sync_get
from .provider_base import DataProvider
from .types import FetchRequest, ProviderResult

# 台灣銀行牌告匯率 Open Data CSV
BOT_EXCHANGE_RATE_URL = "https://rate.bot.com.tw/xrt/flcsv/0/day"
ER_API_USD_URL = "https://open.er-api.com/v6/latest/USD"
FRED_TWD_USD_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXTAUS"
FRED_TIMEOUT_SECONDS = 8


class TaiwanOpenDataProvider(DataProvider):
    name = "Taiwan Open Data (Exchange Rates)"
    source = "taiwan_open_data"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"taiwan_open_data", "macro_context"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE

        errors = []
        try:
            rates = _fetch_bot_exchange_rates()
            value = {
                "dataset": "Bank of Taiwan Exchange Rates (牌告匯率)",
                "source": "Open Data (rate.bot.com.tw)",
                "rates": {
                    "USD": rates.get("USD"),
                    "EUR": rates.get("EUR"),
                    "JPY": rates.get("JPY"),
                }
            }
            record_count = sum(1 for rate in value["rates"].values() if rate)
            if record_count <= 0:
                raise ValueError("BOT CSV did not include USD/EUR/JPY rates.")
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_SUCCESS,
                value=value,
                audit={"source": self.source, "provider": self.name, "message": "Successfully fetched exchange rates from Taiwan open data.", "status": AUDIT_STATUS_SUCCESS, "record_count": record_count}
            )
        except Exception as e:
            errors.append(f"BOT: {e}")

        try:
            usd_twd = _fetch_er_api_usd_twd_rate()
            value = _usd_twd_fallback_value(
                "ExchangeRate-API free USD latest",
                "open.er-api.com fallback",
                usd_twd,
                "臺銀 open data 暫不可用，改用 open.er-api.com USD/TWD fallback。",
            )
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_SUCCESS,
                value=value,
                audit={"source": self.source, "provider": self.name, "message": "Taiwan open data unavailable; open.er-api.com USD/TWD fallback returned data.", "status": AUDIT_STATUS_SUCCESS, "record_count": 1}
            )
        except Exception as e:
            errors.append(f"ER API: {e}")

        try:
            usd_twd = _fetch_fred_usd_twd_rate()
            value = _usd_twd_fallback_value(
                "Taiwan Dollars to U.S. Dollar Spot Exchange Rate (DEXTAUS)",
                "FRED DEXTAUS fallback",
                usd_twd,
                "臺銀 open data 暫不可用，改用 FRED USD/TWD daily spot fallback。",
            )
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_SUCCESS,
                value=value,
                audit={"source": self.source, "provider": self.name, "message": "Taiwan open data unavailable; FRED USD/TWD fallback returned data.", "status": AUDIT_STATUS_SUCCESS, "record_count": 1}
            )
        except Exception as e:
            errors.append(f"FRED: {e}")

        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=AUDIT_STATUS_UNAVAILABLE,
            value=None,
            audit={"source": self.source, "provider": self.name, "message": f"Failed to fetch exchange rates: {'; '.join(errors)}.", "status": AUDIT_STATUS_UNAVAILABLE, "record_count": 0}
        )


def _fetch_bot_exchange_rates() -> dict:
    r = sync_get(BOT_EXCHANGE_RATE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=5, provider="Taiwan Open Data")
    content = r.content.decode("utf-8-sig", errors="replace")
    if "<html" in content.lower() or "Challenge Validation" in content:
        raise ValueError("BOT endpoint returned HTML challenge instead of CSV.")
    rows = list(csv.reader(StringIO(content)))
    if len(rows) < 2:
        raise ValueError("CSV data is empty or malformed.")

    rates = {}
    for row in rows[1:]:
        if len(row) < 13:
            continue
        currency = str(row[0] or "").strip()
        if not currency:
            continue
        rates[currency] = {"buy": str(row[2] or "").strip(), "sell": str(row[12] or "").strip()}
    if not rates:
        raise ValueError("CSV data did not include exchange-rate rows.")
    return rates


def _fetch_er_api_usd_twd_rate() -> dict:
    r = sync_get(ER_API_USD_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, provider="Taiwan Open Data")
    payload = r.json()
    if not isinstance(payload, dict) or payload.get("result") != "success":
        raise ValueError("open.er-api.com did not return a success payload.")
    rates = payload.get("rates") if isinstance(payload.get("rates"), dict) else {}
    rate = rates.get("TWD")
    if rate is None:
        raise ValueError("open.er-api.com payload did not include TWD.")
    return {"date": str(payload.get("time_last_update_utc") or "").strip(), "rate": f"{float(rate):.4f}"}


def _fetch_fred_usd_twd_rate() -> dict:
    r = sync_get(FRED_TWD_USD_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=FRED_TIMEOUT_SECONDS, provider="Taiwan Open Data")
    rows = csv.DictReader(StringIO(r.content.decode("utf-8-sig", errors="replace")))
    latest = {}
    for row in rows:
        rate = str(row.get("DEXTAUS") or "").strip()
        if rate and rate != ".":
            latest = {"date": str(row.get("observation_date") or "").strip(), "rate": rate}
    if not latest:
        raise ValueError("FRED DEXTAUS did not include a latest observation.")
    return latest


def _usd_twd_fallback_value(dataset: str, source: str, usd_twd: dict, note: str) -> dict:
    return {
        "dataset": dataset,
        "source": source,
        "rates": {
            "USD": {
                "buy": usd_twd["rate"],
                "sell": usd_twd["rate"],
                "spot": usd_twd["rate"],
                "as_of": usd_twd["date"],
            },
            "EUR": None,
            "JPY": None,
        },
        "coverage_notes": [note],
    }
