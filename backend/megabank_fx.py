"""Dated bank bid/ask quotes from Mega Bank's public exchange-rate page."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import re
import time
from zoneinfo import ZoneInfo

from external_http_client import sync_get
from search_admission import endpoint_admission
from search_provider_runtime import (SourceResponseError, cooldown_state, remember_failure,
                                     scope_key, observe_http_response)

PROVIDER = "Mega International Commercial Bank"
SOURCE_URL = "https://www.megabank.com.tw/personal/savings/foreign-service/forex"
RATES_URL = "https://www.megabank.com.tw/api/client/ExchangeRate/GetRateData?sc_lang=zh-TW&sc_site=bank-zh-tw&dic_lang=zh-TW"
CURRENCIES_URL = "https://www.megabank.com.tw/api/client/ExchangeRate/GetCurrenciesData?sc_lang=zh-TW&sc_site=bank-zh-tw&dic_lang=zh-TW"
PARSER_VERSION = "megabank-fx-v1"
GUARD_KEY = scope_key(PROVIDER, endpoint="fx_quotes")
WANTED = {"USD", "EUR", "JPY"}


def _positive(value) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Boolean exchange rate")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Unknown exchange rate") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("Invalid exchange rate")
    return number


def parse_megabank_rates(payload, currency_payload) -> dict:
    """Use per-currency quote updates, never acquisition time or HTTP Date."""
    if not isinstance(payload, dict) or not isinstance(payload.get("rates"), list) or not isinstance(currency_payload, list):
        raise ValueError("Unknown Mega Bank response shape")
    mapping = {}
    for row in currency_payload:
        if not isinstance(row, dict):
            raise ValueError("Unknown currency metadata")
        code, identifier = row.get("codeName"), row.get("id")
        if not isinstance(code, str) or not isinstance(identifier, str) or not code.strip() or not identifier:
            raise ValueError("Missing currency identity")
        key = f"{code.strip()}|{identifier}"
        if key in mapping:
            raise ValueError("Duplicate currency identity")
        mapping[key] = code.strip()
    rates = {}
    for row in payload["rates"]:
        if not isinstance(row, dict):
            raise ValueError("Unknown quote row")
        currency = mapping.get(row.get("currKey"))
        if currency not in WANTED:
            continue
        if currency in rates:
            raise ValueError("Duplicate currency quote")
        spot = row.get("spot")
        if not isinstance(spot, dict):
            raise ValueError("Missing bank spot quote")
        bid, ask = spot.get("bid"), spot.get("ask")
        if _positive(bid) > _positive(ask):
            raise ValueError("Crossed bank quote")
        raw_date = row.get("update")
        if not isinstance(raw_date, str) or not re.fullmatch(r"\d{14}", raw_date):
            raise ValueError("Missing per-currency observation time")
        observed = datetime.strptime(raw_date, "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("Asia/Taipei"))
        rates[currency] = {
            "buy": str(bid), "sell": str(ask), "rate_kind": "bank_quote", "bank_quote_type": "spot",
            "base_currency": currency, "quote_currency": "TWD", "unit": f"TWD per {currency}",
            "as_of": observed.isoformat(), "raw_observation_time": raw_date,
            "observation_time_field": "update", "source_currency_key": row["currKey"],
        }
    if set(rates) != WANTED:
        raise ValueError("Missing USD/EUR/JPY bank quotes")
    return rates


def fetch_megabank_exchange_rates() -> dict:
    """Two documented public GETs, one admission lease, no HTTP retry."""
    with endpoint_admission(GUARD_KEY, timeout_seconds=16) as owns:
        if owns is None or not owns():
            raise SourceResponseError("single_flight_busy", parser_version=PARSER_VERSION)
        blocked = cooldown_state(GUARD_KEY)
        if blocked:
            raise SourceResponseError(blocked.get("error_kind", "cooldown"),
                                      status_code=blocked.get("http_status"), parser_version=PARSER_VERSION)
        deadline = time.monotonic() + 16
        responses, evidence = [], []
        try:
            for url in (RATES_URL, CURRENCIES_URL):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Bank quote acquisition deadline")
                if not owns():
                    raise SourceResponseError("lease_lost", parser_version=PARSER_VERSION)
                observe_http_response(None)
                response = sync_get(url, timeout=min(8, remaining), provider=PROVIDER)
                observe_http_response(response)
                evidence.append({'source_url': url, 'http_status': response.status_code,
                                 'response_sha256': hashlib.sha256(response.content).hexdigest(),
                                 'response_bytes': len(response.content)})
                response.raise_for_status()
                try:
                    responses.append(response.json())
                except ValueError as exc:
                    raise SourceResponseError("parse_error", status_code=response.status_code,
                                              response_text=response.text, parser_version=PARSER_VERSION) from exc
            try:
                rates = parse_megabank_rates(*responses)
            except ValueError as exc:
                raise SourceResponseError("parse_error", status_code=200, parser_version=PARSER_VERSION) from exc
            if not owns():
                raise SourceResponseError("lease_lost", parser_version=PARSER_VERSION)
            if time.monotonic() >= deadline:
                raise TimeoutError("Bank quote acquisition deadline")
            if any(datetime.fromisoformat(row['as_of']).timestamp() > time.time() for row in rates.values()):
                raise SourceResponseError("future_observation", status_code=200, parser_version=PARSER_VERSION)
            for row in rates.values():
                row['source_evidence'] = evidence
            return rates
        except Exception as exc:
            failed_response = getattr(exc, 'response', None)
            if failed_response is not None:
                evidence.append({'source_url': str(exc.request.url),
                                 'http_status': failed_response.status_code,
                                 'response_sha256': hashlib.sha256(failed_response.content).hexdigest(),
                                 'response_bytes': len(failed_response.content)})
            details = remember_failure(GUARD_KEY, exc) if owns() else {"error_kind": "lease_lost"}
            error = SourceResponseError(details.get("error_kind", "provider_error"),
                                        status_code=details.get("http_status"), parser_version=PARSER_VERSION)
            error.diagnostic.update(details, source_evidence=evidence)
            raise error from exc
