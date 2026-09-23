"""Taiwan Open Data (data.gov.tw / BOT) provider for macro indicators."""

from __future__ import annotations

import csv
import math
import time
from io import StringIO
from email.utils import parsedate_to_datetime
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
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        from shared_provider_cache import shared_fetch

        value, meta = shared_fetch("exchange_rates:USD_TWD:v2", _fetch_exchange_rates,
                                  freshness_seconds=15 * 60, retention_seconds=15 * 60,
                                  use_cache=not request.options.force_refresh)
        if value:
            _screen_quote_recency(value, ticker=request.ticker, now_epoch=time.time())
            meta["stale"] = bool(meta.get("stale")) or value["stale"]
        provider = value.get("actual_provider", self.name) if value else self.name
        status = (AUDIT_STATUS_SUCCESS if value and value.get("status") == "success" else
                  AUDIT_STATUS_DEGRADED_ENRICHMENT if value else AUDIT_STATUS_UNAVAILABLE)
        return ProviderResult(
            source=self.source, provider=provider, status=status, value=value,
            audit={"source": self.source, "provider": provider, "actual_provider": provider,
                   "status": status, "record_count": sum(bool(v) for v in value["rates"].values()) if value else 0,
                   "coverage_status": value.get("status") if value else "unavailable",
                   "coverage": value.get("coverage", {}) if value else {},
                   "component_statuses": value.get("component_statuses", {}) if value else {}, **meta,
                   "message": ("匯率依實際上游及報價種類提供；缺少幣別不代表完整。" if value else "匯率來源暫無可用資料。")},
        )


def _screen_quote_recency(value: dict, *, ticker: str, now_epoch: float) -> None:
    from source_observation_freshness import observation_recency

    components = {}
    for currency, quote in value.get("rates", {}).items():
        if not isinstance(quote, dict):
            continue
        # FX observations are checked against Taiwan's calendar day.
        recency = observation_recency(quote.get("as_of"), ticker=ticker, now_epoch=now_epoch, max_age_days=7)
        recent = recency["observation_status"] == "recent"
        quote.update(recency, stale=not recent)
        components[currency] = {"status": "success" if recent else recency["observation_status"],
                                "as_of": recency["observed_at"], "provider": value.get("actual_provider"),
                                "reason_code": "observation_" + recency["observation_status"]}
    value["component_statuses"] = components
    value["stale"] = any(item["status"] != "success" for item in components.values())
    if value["stale"]:
        value["status"] = "partial"
        value.setdefault("coverage_notes", []).append("匯率觀測日期過舊、未知或位於未來時，不可當作最新報價。")


def _fetch_exchange_rates() -> dict:
    attempts = []
    try:
        rates = _fetch_bot_exchange_rates()
        selected = {}
        for currency in ("USD", "EUR", "JPY"):
            quote = rates.get(currency)
            if isinstance(quote, dict) and any(_valid_rate(quote.get(k)) for k in ("buy", "sell")):
                selected[currency] = {**quote, **{k: quote[k] if _valid_rate(quote.get(k)) else None for k in ("buy", "sell")},
                                      "rate_kind": "bank_quote", "quote_currency": "TWD"}
            else:
                selected[currency] = None
        if not any(selected.values()):
            raise ValueError("BOT CSV did not include USD/EUR/JPY rates")
        coverage = {currency: "available" if quote and all(_valid_rate(quote.get(k)) for k in ("buy", "sell"))
                    else "partial" if quote else "unavailable" for currency, quote in selected.items()}
        return {"dataset": "Bank of Taiwan Exchange Rates (牌告匯率)",
                "source": "Open Data (rate.bot.com.tw)", "actual_provider": "Bank of Taiwan",
                "source_url": BOT_EXCHANGE_RATE_URL, "rates": selected, "coverage": coverage,
                "status": "success" if all(v == "available" for v in coverage.values()) else "partial"}
    except Exception as exc:
        attempts.append({"provider": "Bank of Taiwan", "error_kind": type(exc).__name__})
    for provider, fetcher, dataset, source, url in (
        ("open.er-api.com", _fetch_er_api_usd_twd_rate, "ExchangeRate-API free USD latest", "open.er-api.com fallback", ER_API_USD_URL),
        ("FRED DEXTAUS", _fetch_fred_usd_twd_rate, "Taiwan Dollars to U.S. Dollar Spot Exchange Rate (DEXTAUS)", "FRED DEXTAUS fallback", FRED_TWD_USD_URL),
    ):
        try:
            quote = fetcher()
            if not _valid_rate(quote.get("rate")):
                raise ValueError("Invalid USD/TWD spot")
            value = _usd_twd_fallback_value(dataset, source, quote, "臺銀牌告未取得；僅有第三方 USD/TWD spot，無 EUR/JPY 與銀行買賣報價。")
            value.update(actual_provider=provider, source_url=url, fallback_attempts=attempts,
                         fallback_reason="primary_unavailable", status="partial",
                         coverage={"USD": "available", "EUR": "unsupported", "JPY": "unsupported"})
            return value
        except Exception as exc:
            attempts.append({"provider": provider, "error_kind": type(exc).__name__})
    raise ValueError("All exchange rate sources unavailable")


def _valid_rate(value) -> bool:
    try:
        return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _fetch_bot_exchange_rates() -> dict:
    r = sync_get(BOT_EXCHANGE_RATE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=5, provider="Bank of Taiwan")
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
    r = sync_get(ER_API_USD_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, provider="open.er-api.com")
    payload = r.json()
    if not isinstance(payload, dict) or payload.get("result") != "success":
        raise ValueError("open.er-api.com did not return a success payload.")
    rates = payload.get("rates") if isinstance(payload.get("rates"), dict) else {}
    rate = rates.get("TWD")
    if rate is None:
        raise ValueError("open.er-api.com payload did not include TWD.")
    raw_date = str(payload.get("time_last_update_utc") or "").strip()
    try:
        observed_date = parsedate_to_datetime(raw_date).isoformat()
    except (ValueError, TypeError, OverflowError):
        observed_date = None
    return {"date": observed_date, "reported_timestamp": raw_date, "rate": f"{float(rate):.4f}"}


def _fetch_fred_usd_twd_rate() -> dict:
    r = sync_get(FRED_TWD_USD_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=FRED_TIMEOUT_SECONDS, provider="FRED DEXTAUS")
    rows = csv.DictReader(StringIO(r.content.decode("utf-8-sig", errors="replace")))
    latest = {}
    for row in rows:
        rate = str(row.get("DEXTAUS") or "").strip()
        if _valid_rate(rate):
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
                "buy": None,
                "sell": None,
                "rate_kind": "spot",
                "quote_currency": "TWD",
                "spot": usd_twd["rate"],
                "as_of": usd_twd["date"],
            },
            "EUR": None,
            "JPY": None,
        },
        "coverage_notes": [note],
    }
