"""Public bank quotes retain side, currency and observation-time evidence."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from data_fetch.types import FetchRequest

FIXTURES = Path(__file__).parent / "fixtures" / "source_acquisition"
NOW = datetime(2026, 9, 27, 14, tzinfo=ZoneInfo("Asia/Taipei")).timestamp()


def captured():
    return (json.loads((FIXTURES / "megabank_rates_20260927.json").read_text()),
            json.loads((FIXTURES / "megabank_currencies_20260927.json").read_text()))


def test_captured_public_bank_quotes_preserve_both_sides_and_dates():
    from megabank_fx import parse_megabank_rates
    rates = parse_megabank_rates(*captured())
    assert set(rates) == {"USD", "EUR", "JPY"}
    assert (rates["USD"]["buy"], rates["USD"]["sell"]) == ("31.7300", "31.8300")
    assert (rates["EUR"]["buy"], rates["EUR"]["sell"]) == ("36.0300", "36.4300")
    assert (rates["JPY"]["buy"], rates["JPY"]["sell"]) == ("0.2003", "0.2044")
    for currency, quote in rates.items():
        assert quote["as_of"] == "2026-09-27T13:56:26+08:00"
        assert quote["rate_kind"] == "bank_quote"
        assert quote["bank_quote_type"] == "spot"
        assert quote["unit"] == f"TWD per {currency}"
        assert quote["raw_observation_time"] == "20260927135626"


@pytest.mark.parametrize("changes", [
    {"spot": {"bid": "NaN", "ask": "32"}},
    {"spot": {"bid": "-1", "ask": "32"}},
    {"spot": {"bid": True, "ask": "32"}},
    {"spot": {"bid": "33", "ask": "32"}},
    {"spot": {"bid": "31"}}, {"update": ""}, {"update": "20260230135626"},
])
def test_invalid_or_undated_bank_row_cannot_be_complete(changes):
    from megabank_fx import parse_megabank_rates
    rates, currencies = captured()
    rates["rates"][0].update(changes)
    with pytest.raises(ValueError):
        parse_megabank_rates(rates, currencies)


def test_unknown_currency_mapping_or_duplicate_quote_is_rejected():
    from megabank_fx import parse_megabank_rates
    rates, currencies = captured()
    with pytest.raises(ValueError):
        parse_megabank_rates(rates, [c for c in currencies if c["codeName"] != "USD"])
    rates["rates"].append(deepcopy(rates["rates"][0]))
    with pytest.raises(ValueError):
        parse_megabank_rates(rates, currencies)


def test_bot_failure_recovers_complete_fresh_bank_quotes_before_spot(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    from megabank_fx import parse_megabank_rates
    monkeypatch.setattr(fx.time, "time", lambda: NOW)
    monkeypatch.setattr(fx, "_fetch_bot_exchange_rates", lambda: (_ for _ in ()).throw(ValueError("HTML challenge")))
    monkeypatch.setattr(fx, "fetch_megabank_exchange_rates", lambda: parse_megabank_rates(*captured()))
    monkeypatch.setattr(fx, "_fetch_er_api_usd_twd_rate", lambda: pytest.fail("Complete bank data must not request spot"))
    request = FetchRequest.from_ticker("2330.TW", force_refresh=True)
    result = fx.TaiwanOpenDataProvider().fetch(request)
    assert result.status == "success"
    assert result.provider == "Mega International Commercial Bank"
    assert result.audit["record_count"] == 3
    assert result.value["fallback_attempts"][0]["provider"] == "Bank of Taiwan"
    assert result.value["coverage"] == {"USD": "available", "EUR": "available", "JPY": "available"}


@pytest.mark.parametrize("stamp", ["2026-08-01T13:56:26+08:00", "2026-09-28T13:56:26+08:00", None])
def test_stale_future_or_unknown_bank_date_does_not_become_success(monkeypatch, stamp):
    import data_fetch.taiwan_open_data_provider as fx
    from megabank_fx import parse_megabank_rates
    rates = parse_megabank_rates(*captured())
    rates["USD"]["as_of"] = stamp
    monkeypatch.setattr(fx.time, "time", lambda: NOW)
    monkeypatch.setattr(fx, "_fetch_bot_exchange_rates", lambda: (_ for _ in ()).throw(ValueError("HTML")))
    monkeypatch.setattr(fx, "fetch_megabank_exchange_rates", lambda: rates)
    result = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW", force_refresh=True))
    assert result.status == "degraded_enrichment"
    assert result.value["stale"] is True


def test_two_bank_failures_keep_spot_partial_with_unknown_buy_sell(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    monkeypatch.setattr(fx.time, "time", lambda: NOW)
    def failed(): raise ValueError("unavailable")
    monkeypatch.setattr(fx, "_fetch_bot_exchange_rates", failed)
    monkeypatch.setattr(fx, "fetch_megabank_exchange_rates", failed)
    monkeypatch.setattr(fx, "_fetch_er_api_usd_twd_rate", lambda: {"rate": "31.9", "date": "2026-09-27"})
    result = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW", force_refresh=True))
    assert result.status == "degraded_enrichment"
    assert result.value["rates"]["USD"]["buy"] is None
    assert result.value["rates"]["USD"]["sell"] is None
    assert result.value["rates"]["USD"]["rate_kind"] == "spot"
    assert len(result.value["fallback_attempts"]) == 2


def test_public_adapter_uses_two_documented_gets_and_cooldown_stops_denied_host(monkeypatch):
    import megabank_fx as mega
    from search_provider_runtime import SourceResponseError
    rates, currencies = captured()
    guard, calls = {}, []
    monkeypatch.setattr(mega, "cooldown_state", lambda key: guard)
    monkeypatch.setattr(mega, "remember_failure", lambda key, exc: guard.update(error_kind="access_denied", http_status=403) or dict(guard))
    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json=rates if url == mega.RATES_URL else currencies,
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(mega, "sync_get", get)
    assert len(mega.fetch_megabank_exchange_rates()) == 3
    assert calls == [mega.RATES_URL, mega.CURRENCIES_URL]
    calls.clear()
    def denied(url, **kwargs):
        calls.append(url)
        raise httpx.HTTPStatusError("denied", request=httpx.Request("GET", url),
                                    response=httpx.Response(403))
    monkeypatch.setattr(mega, "sync_get", denied)
    with pytest.raises(SourceResponseError): mega.fetch_megabank_exchange_rates()
    with pytest.raises(SourceResponseError): mega.fetch_megabank_exchange_rates()
    assert calls == [mega.RATES_URL]


@pytest.mark.parametrize('primary_kind', ['missing_side', 'missing_date', 'stale'])
def test_incomplete_primary_bank_tries_complete_backup(monkeypatch, primary_kind):
    import data_fetch.taiwan_open_data_provider as fx
    from megabank_fx import parse_megabank_rates
    good = parse_megabank_rates(*captured())
    first = deepcopy(good)
    if primary_kind == 'missing_side': first['USD']['sell'] = None
    elif primary_kind == 'missing_date': first['USD']['as_of'] = None
    else: first['USD']['as_of'] = '2026-08-01'
    monkeypatch.setattr(fx.time, 'time', lambda: NOW)
    monkeypatch.setattr(fx, '_fetch_bot_exchange_rates', lambda: first)
    monkeypatch.setattr(fx, 'fetch_megabank_exchange_rates', lambda: good)
    monkeypatch.setattr(fx, '_fetch_er_api_usd_twd_rate', lambda: pytest.fail('Bank quotes available'))
    result = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker('2330.TW', force_refresh=True))
    assert result.status == 'success'
    assert result.provider == fx.MEGABANK_PROVIDER
    assert result.value['fallback_attempts'][0]['error_kind'] == 'incomplete_bank_quotes'


def test_partial_primary_bank_survives_backup_failure(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    from megabank_fx import parse_megabank_rates
    first = parse_megabank_rates(*captured())
    first['USD']['sell'] = None
    monkeypatch.setattr(fx.time, 'time', lambda: NOW)
    monkeypatch.setattr(fx, '_fetch_bot_exchange_rates', lambda: first)
    monkeypatch.setattr(fx, 'fetch_megabank_exchange_rates', lambda: (_ for _ in ()).throw(ValueError('unavailable')))
    result = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker('2330.TW', force_refresh=True))
    assert result.status == 'degraded_enrichment'
    assert result.provider == 'Bank of Taiwan'
    assert result.value['rates']['USD']['buy'] == first['USD']['buy']
    assert result.value['rates']['USD']['sell'] is None
    assert result.value['fallback_attempts'][-1]['provider'] == fx.MEGABANK_PROVIDER


@pytest.mark.parametrize('lose_lease', [True, False])
def test_expired_deadline_or_lost_lease_after_response_cannot_publish(monkeypatch, lose_lease):
    from contextlib import contextmanager
    import megabank_fx as mega
    from search_provider_runtime import SourceResponseError
    rates, currencies = captured()
    state = {'time': 0, 'owns': True}
    @contextmanager
    def admission(*args, **kwargs): yield lambda: state['owns']
    monkeypatch.setattr(mega, 'endpoint_admission', admission)
    monkeypatch.setattr(mega, 'cooldown_state', lambda key: {})
    monkeypatch.setattr(mega.time, 'monotonic', lambda: state['time'])
    monkeypatch.setattr(mega, 'remember_failure', lambda key, exc: {'error_kind': getattr(exc, 'error_kind', 'timeout')})
    def get(url, **kwargs):
        if url == mega.CURRENCIES_URL:
            state['owns'] = not lose_lease
            state['time'] = 0 if lose_lease else 17
        return httpx.Response(200, json=rates if url == mega.RATES_URL else currencies, request=httpx.Request('GET', url))
    monkeypatch.setattr(mega, 'sync_get', get)
    with pytest.raises(SourceResponseError) as error:
        mega.fetch_megabank_exchange_rates()
    assert error.value.error_kind == ('lease_lost' if lose_lease else 'timeout')


def test_same_day_future_quote_is_rejected_using_full_row_time(monkeypatch):
    import megabank_fx as mega
    from search_provider_runtime import SourceResponseError
    rates, currencies = captured()
    monkeypatch.setattr(mega.time, 'time', lambda: NOW - 300)
    monkeypatch.setattr(mega, 'cooldown_state', lambda key: {})
    monkeypatch.setattr(mega, 'remember_failure', lambda key, exc: {'error_kind': exc.error_kind})
    monkeypatch.setattr(mega, 'sync_get', lambda url, **kw: httpx.Response(
        200, json=rates if url == mega.RATES_URL else currencies, request=httpx.Request('GET', url)))
    with pytest.raises(SourceResponseError) as error:
        mega.fetch_megabank_exchange_rates()
    assert error.value.error_kind == 'future_observation'


def test_shared_bank_screen_uses_taipei_day_when_new_york_is_previous_day(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    from megabank_fx import parse_megabank_rates
    now = datetime(2026, 9, 27, 1, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    rates = parse_megabank_rates(*captured())
    for row in rates.values(): row['as_of'] = '2026-09-27T00:30:00+08:00'
    monkeypatch.setattr(fx.time, 'time', lambda: now)
    monkeypatch.setattr(fx, '_fetch_bot_exchange_rates', lambda: rates)
    monkeypatch.setattr(fx, 'fetch_megabank_exchange_rates', lambda: pytest.fail('Fresh complete primary needs no backup'))
    result = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker('2330.TW', force_refresh=True))
    assert result.status == 'success'
    assert result.provider == 'Bank of Taiwan'
    assert all(row['observation_status'] == 'recent' for row in result.value['rates'].values())


def test_rate_limit_retains_retry_after_and_raw_response_digest(monkeypatch):
    import hashlib
    import megabank_fx as mega
    import search_provider_runtime as runtime
    from search_provider_runtime import SourceResponseError
    state, calls = {}, []
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    def limited(url, **kwargs):
        calls.append(url)
        response = httpx.Response(429, text='Too many requests', headers={'Retry-After': '600'}, request=httpx.Request('GET', url))
        response.raise_for_status()
    monkeypatch.setattr(mega, 'sync_get', limited)
    with pytest.raises(SourceResponseError) as error:
        mega.fetch_megabank_exchange_rates()
    assert error.value.error_kind == 'rate_limited'
    assert state[mega.GUARD_KEY]['retry_at'] >= mega.time.time() + 599
    receipt = error.value.diagnostic['source_evidence'][0]
    assert receipt['http_status'] == 429
    assert receipt['response_sha256'] == hashlib.sha256(b'Too many requests').hexdigest()
    with pytest.raises(SourceResponseError): mega.fetch_megabank_exchange_rates()
    assert calls == [mega.RATES_URL]
