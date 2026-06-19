from __future__ import annotations

import logging

from external_data_client import ExternalDataClient


PTT = [{"title": "PTT 2330", "link": "https://ptt.example/a", "published_date": "", "source": "PTT Stock", "summary": ""}]
GOOGLE = [{"title": "Google", "link": "https://news.example/a", "published_date": "", "source": "Google News RSS", "summary": ""}]
DDG = [{"title": "DDG", "link": "https://news.example/b", "published_date": "", "source": "DuckDuckGo News", "summary": ""}]


def test_news_falls_back_google_to_ddg_to_ptt(caplog):
    client = ExternalDataClient(
        google_news=lambda *_args, **_kwargs: [],
        ddg_news=lambda *_args, **_kwargs: [],
        ptt_news=lambda *_args, **_kwargs: PTT,
    )

    with caplog.at_level(logging.WARNING):
        assert client.get_news("2330 台積電", ticker="2330") == PTT

    assert "Google News RSS" in caplog.text
    assert "DuckDuckGo News" in caplog.text
    assert "PTT Stock" in caplog.text


def test_news_dedupes_and_skips_ptt_for_us_ticker():
    calls = {"ptt": 0}

    def ptt(*_args, **_kwargs):
        calls["ptt"] += 1
        return PTT

    client = ExternalDataClient(
        google_news=lambda *_args, **_kwargs: [GOOGLE[0], dict(GOOGLE[0])],
        ddg_news=lambda *_args, **_kwargs: DDG,
        ptt_news=ptt,
    )

    assert client.get_news("AAPL", ticker="AAPL") == [GOOGLE[0]]
    assert calls["ptt"] == 0


def test_news_does_not_infer_ptt_ticker_from_numeric_query(caplog):
    calls = {"ptt": 0}

    def ptt(*_args, **_kwargs):
        calls["ptt"] += 1
        return PTT

    client = ExternalDataClient(
        google_news=lambda *_args, **_kwargs: [],
        ddg_news=lambda *_args, **_kwargs: [],
        ptt_news=ptt,
    )

    with caplog.at_level(logging.WARNING):
        assert client.get_news("2026 market outlook") == []
    assert calls["ptt"] == 0
    assert "PTT Stock" not in caplog.text


def test_domestic_two_suffix_can_use_ptt_and_mops_fallback():
    calls = {"ptt": 0, "mops": 0}

    def ptt(*_args, **_kwargs):
        calls["ptt"] += 1
        return PTT

    def mops(*_args, **_kwargs):
        calls["mops"] += 1
        return {"total_liabilities": 900}

    client = ExternalDataClient(
        google_news=lambda *_args, **_kwargs: [],
        ddg_news=lambda *_args, **_kwargs: [],
        ptt_news=ptt,
        financial_fetcher=lambda *_args: {"total_debt_raw": None},
        mops_fetcher=mops,
    )

    assert client.get_news("上櫃公司", ticker="1234.TWO") == PTT
    assert client.get_financial_data("1234.TWO", year=2025, season=4)["total_debt_raw"] == 900
    assert calls == {"ptt": 1, "mops": 1}


def test_invalid_yfinance_debt_uses_mops():
    mops = {
        "total_liabilities": 900,
        "unit": "thousand_twd",
        "source": "MOPS",
        "raw_line_items": {"負債總計": 900},
    }
    client = ExternalDataClient(
        financial_fetcher=lambda *_args: {"total_debt_raw": None, "source": "yfinance"},
        mops_fetcher=lambda *_args, **_kwargs: mops,
    )

    result = client.get_financial_data("2330.TW", year=2025, season=4)

    assert result["total_debt_raw"] == 900
    assert result["field_provenance"]["total_debt_raw"] == "MOPS"
    assert result["mops_balance_sheet"] == mops
    assert result["audit_events"][0]["event"] == "invalid_total_debt_mops_fallback"


def test_valid_debt_bypasses_mops_and_negative_nan_open_status():
    called = {"mops": 0}

    def mops(*_args, **_kwargs):
        called["mops"] += 1
        return {"total_liabilities": 900}

    client = ExternalDataClient(
        financial_fetcher=lambda *_args: {"total_debt_raw": 100, "source": "yfinance"},
        mops_fetcher=mops,
    )
    assert client.get_financial_data("2330.TW")["total_debt_raw"] == 100
    assert called["mops"] == 0

    client = ExternalDataClient(
        financial_fetcher=lambda *_args: {"total_debt_raw": float("nan")},
        mops_fetcher=lambda *_args, **_kwargs: None,
    )
    unresolved = client.get_financial_data("2330.TW", year=2025, season=4)
    assert unresolved["official_reconciliation_status"] == "unresolved"
    assert unresolved["circuit_breaker_signal"]["status"] == "open"
    assert unresolved["field_provenance"]["total_debt_raw"] == "unresolved"


def test_financial_data_handles_malformed_period_and_audit_events():
    client = ExternalDataClient(
        financial_fetcher=lambda *_args: {"total_debt_raw": None, "audit_events": None},
        mops_fetcher=lambda *_args, **_kwargs: {"total_liabilities": 900},
    )

    result = client.get_financial_data("2330.TW", year="bad", season=4)

    assert result["total_debt_raw"] == 900
    assert isinstance(result["audit_events"], list)


def test_mops_not_used_for_non_taiwan_ticker():
    called = {"mops": 0}

    def mops(*_args, **_kwargs):
        called["mops"] += 1
        return {"total_liabilities": 900}

    client = ExternalDataClient(
        financial_fetcher=lambda *_args: {"total_debt_raw": None},
        mops_fetcher=mops,
    )

    result = client.get_financial_data("AAPL", year=2025, season=4)

    assert called["mops"] == 0
    assert result["official_reconciliation_status"] == "not_applicable"
