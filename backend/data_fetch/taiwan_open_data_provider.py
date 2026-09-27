"""Taiwan Open Data (data.gov.tw / BOT) provider for macro indicators."""

from __future__ import annotations

import csv
import math
import time
from io import StringIO
from email.utils import parsedate_to_datetime
from external_http_client import sync_get
from megabank_fx import (fetch_megabank_exchange_rates, PROVIDER as MEGABANK_PROVIDER,
                         SOURCE_URL as MEGABANK_SOURCE_URL)
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

        value, meta = shared_fetch("exchange_rates:TWD_quotes:v3", _fetch_exchange_rates,
                                  freshness_seconds=60 * 60, retention_seconds=60 * 60,
                                  result_ttl=lambda value: (60 * 60 if value.get("actual_provider") == "open.er-api.com" else 15 * 60),
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
                   "component_statuses": value.get("component_statuses", {}) if value else {},
                   "source_evidence": value.get("source_evidence", []) if value else [],
                   "fallback_attempts": value.get("fallback_attempts", []) if value else [], **meta,
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
        note = "匯率觀測日期過舊、未知或位於未來時，不可當作最新報價。"
        if note not in value.setdefault("coverage_notes", []):
            value["coverage_notes"].append(note)


def _fetch_exchange_rates() -> dict:
    attempts, partial = [], None
    for provider, fetcher, dataset, source, url in (
        ("Bank of Taiwan", _fetch_bot_exchange_rates, "Bank of Taiwan Exchange Rates (牌告匯率)",
         "Open Data (rate.bot.com.tw)", BOT_EXCHANGE_RATE_URL),
        (MEGABANK_PROVIDER, fetch_megabank_exchange_rates, "Mega Bank Exchange Rates (即期銀行買賣牌告)",
         "Mega Bank public exchange rates", MEGABANK_SOURCE_URL),
    ):
        try:
            rates = fetcher()
            selected = {}
            for currency in ("USD", "EUR", "JPY"):
                quote = rates.get(currency)
                if isinstance(quote, dict) and any(_valid_rate(quote.get(k)) for k in ("buy", "sell")):
                    selected[currency] = {**quote, **{k: quote[k] if _valid_rate(quote.get(k)) else None for k in ("buy", "sell")},
                                          "rate_kind": "bank_quote", "quote_currency": "TWD"}
                else:
                    selected[currency] = None
            if not any(selected.values()):
                raise ValueError("Bank source did not include USD/EUR/JPY rates")
            coverage = {currency: "available" if quote and all(_valid_rate(quote.get(k)) for k in ("buy", "sell"))
                        else "partial" if quote else "unavailable" for currency, quote in selected.items()}
            candidate = {"dataset": dataset, "source": source, "actual_provider": provider,
                    "source_url": url, "rates": selected, "coverage": coverage,
                    "fallback_attempts": attempts,
                    "status": "success" if all(v == "available" for v in coverage.values()) else "partial",
                    "source_evidence": next((q.get('source_evidence', []) for q in selected.values() if q), [])}
            _screen_quote_recency(candidate, ticker='FX.TW', now_epoch=time.time())
            if candidate['status'] == 'success':
                return candidate
            attempts.append({'provider': provider, 'error_kind': 'incomplete_bank_quotes',
                             'coverage': coverage, 'component_statuses': candidate['component_statuses']})
            # Keep the best actual bank observations if all later banks fail.
            # Rank by recent complete pairs, then complete pairs, then currencies.
            def rank(value):
                quotes = [q for q in value['rates'].values() if q]
                complete = [q for q in quotes if all(_valid_rate(q.get(k)) for k in ('buy', 'sell'))]
                return sum(not q.get('stale') for q in complete), len(complete), len(quotes)
            if partial is None or rank(candidate) > rank(partial):
                partial = candidate
        except Exception as exc:
            attempts.append({"provider": provider, "error_kind": getattr(exc, "error_kind", type(exc).__name__),
                             **getattr(exc, 'diagnostic', {})})
    if partial:
        partial['fallback_attempts'] = attempts
        return partial
    for provider, fetcher, dataset, source, url in (
        ("open.er-api.com", _fetch_er_api_usd_twd_rate, "ExchangeRate-API free USD latest", "open.er-api.com fallback", ER_API_USD_URL),
        ("FRED DEXTAUS", _fetch_fred_usd_twd_rate, "Taiwan Dollars to U.S. Dollar Spot Exchange Rate (DEXTAUS)", "FRED DEXTAUS fallback", FRED_TWD_USD_URL),
    ):
        try:
            quote = fetcher()
            if not _valid_rate(quote.get("rate")):
                raise ValueError("Invalid USD/TWD spot")
            value = _usd_twd_fallback_value(dataset, source, quote, "臺銀牌告未取得；第三方 spot 僅供換算參考，沒有銀行買賣報價。")
            # ER already returns these currencies in the same USD-base response.
            # Cross rates do not need extra requests and remain derived spot data.
            spot_quotes = quote.get("spot_quotes")
            if isinstance(spot_quotes, dict):
                value["rates"].update(spot_quotes)
            missing_status = "unavailable" if isinstance(spot_quotes, dict) else "unsupported"
            value.update(actual_provider=provider, source_url=url, fallback_attempts=attempts,
                         fallback_reason="primary_unavailable", status="partial",
                         coverage={currency: "available" if item else missing_status
                                   for currency, item in value["rates"].items()})
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
    if payload.get("base_code") != "USD":
        raise ValueError("open.er-api.com response must declare the USD base.")
    rates = payload.get("rates") if isinstance(payload.get("rates"), dict) else {}
    rate = rates.get("TWD")
    if not _valid_rate(rate):
        raise ValueError("open.er-api.com payload did not include a valid TWD rate.")
    raw_date = str(payload.get("time_last_update_utc") or "").strip()
    try:
        observed_date = parsedate_to_datetime(raw_date).isoformat()
    except (ValueError, TypeError, OverflowError):
        observed_date = None
    spot_quotes = {}
    for currency in ("USD", "EUR", "JPY"):
        denominator = 1 if currency == "USD" else rates.get(currency)
        spot = float(rate) / float(denominator) if _valid_rate(denominator) else None
        if not _valid_rate(spot):
            spot_quotes[currency] = None
            continue
        spot_quotes[currency] = {
            "buy": None, "sell": None, "rate_kind": "spot", "base_currency": currency,
            "quote_currency": "TWD", "unit": f"TWD per {currency}",
            "spot": f"{spot:.12g}", "as_of": observed_date,
            "derived": currency != "USD", "source_base_currency": "USD",
            "source_rates": {"TWD": rate, **({currency: denominator} if currency != "USD" else {})},
            "formula": f"rates.TWD / rates.{currency}" if currency != "USD" else "rates.TWD",
        }
    return {"date": observed_date, "reported_timestamp": raw_date, "rate": f"{float(rate):.12g}",
            "spot_quotes": spot_quotes}


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
                "base_currency": "USD",
                "quote_currency": "TWD",
                "unit": "TWD per USD",
                "spot": usd_twd["rate"],
                "as_of": usd_twd["date"],
            },
            "EUR": None,
            "JPY": None,
        },
        "coverage_notes": [note],
    }
