from __future__ import annotations

import hashlib
import json

import pytest

from oos_research.dataset import validate_dataset
from oos_research.official_market_data import build_official_market_dataset, official_url


def _capture(payload, *, url, captured_at="2026-09-10T07:05:00Z"):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "payload": payload,
        "source_url": url,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_file": f"raw/{hashlib.sha256(raw).hexdigest()}.json",
        "captured_at": captured_at,
    }


def _session_calendar(sessions):
    return {
        "schema_version": "oos.exchange-sessions.v1",
        "market": "tw",
        "timezone": "Asia/Taipei",
        "session_open_local_time": "09:00:00",
        "range": {"start": sessions[0], "end": sessions[-1]},
        "calendar_definition_sha256": "c" * 64,
        "sessions": sessions,
    }


def test_build_official_market_dataset_uses_twse_and_tpex_and_stops_at_cutoff():
    inventory = {
        "coverage_status": "closed",
        "candidates": [
            {"candidate_id": "tw-v1", "ticker": "1623.TW", "pipeline_id": "v1"},
            {"candidate_id": "two-v1", "ticker": "3324.TWO", "pipeline_id": "v1"},
        ],
    }
    sessions = ["2026-09-09", "2026-09-10", "2026-09-11"]
    twse = {
        "stat": "OK",
        "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"],
        "data": [
            ["115/09/09", "1", "1", "204.50", "220.00", "204.50", "218.50"],
            ["115/09/10", "1", "1", "216.00", "220.00", "216.00", "218.50"],
            ["115/09/11", "1", "1", "219.00", "221.00", "217.00", "220.00"],
        ],
    }
    tpex = {
        "tables": [{
            "fields": ["日 期", "成交張數", "成交仟元", "開盤", "最高", "最低", "收盤"],
            "data": [
                ["115/09/09", "1", "1", "1,375.00", "1,400.00", "1,320.00", "1,385.00"],
                ["115/09/10", "1", "1", "1,355.00", "1,440.00", "1,355.00", "1,440.00"],
                ["115/09/11", "1", "1", "1,450.00", "1,460.00", "1,430.00", "1,455.00"],
            ],
        }],
    }
    calls = []

    def fetch_month(ticker, month):
        calls.append((ticker, month))
        if ticker.endswith(".TWO"):
            return _capture(tpex, url=official_url(ticker, month))
        return _capture(twse, url=official_url(ticker, month))

    dataset = build_official_market_dataset(
        inventory=inventory,
        session_calendar=_session_calendar(sessions),
        cutoff_session="2026-09-10",
        as_of="2026-09-10T15:05:00+08:00",
        fetch_month=fetch_month,
    )

    assert calls == [("1623.TW", "2026-09"), ("3324.TWO", "2026-09")]
    assert dataset["calendar"] == ["2026-09-09", "2026-09-10"]
    assert [row["date"] for row in dataset["bars"]["1623.TW"]] == dataset["calendar"]
    assert [row["date"] for row in dataset["bars"]["3324.TWO"]] == dataset["calendar"]
    assert dataset["bars"]["3324.TWO"][0]["open"] == 1375.0
    assert len(dataset["source_captures"]) == 2
    assert validate_dataset(dataset) == dataset["dataset_sha256"]


def test_build_official_market_dataset_fails_closed_when_cutoff_is_not_published():
    inventory = {
        "coverage_status": "closed",
        "candidates": [{"candidate_id": "tw-v1", "ticker": "1623.TW", "pipeline_id": "v1"}],
    }

    def fetch_month(ticker, month):
        return _capture({
            "stat": "OK",
            "data": [["115/09/09", "1", "1", "204.50", "220.00", "204.50", "218.50"]],
        }, url=official_url(ticker, month))

    with pytest.raises(ValueError, match="cutoff session is not published"):
        build_official_market_dataset(
            inventory=inventory,
            session_calendar=_session_calendar(["2026-09-09", "2026-09-10"]),
            cutoff_session="2026-09-10",
            as_of="2026-09-10T15:05:00+08:00",
            fetch_month=fetch_month,
        )


def test_build_official_market_dataset_binds_capture_url_to_ticker_and_month():
    inventory = {
        "coverage_status": "closed",
        "candidates": [{"candidate_id": "tw-v1", "ticker": "1623.TW", "pipeline_id": "v1"}],
    }
    payload = {
        "stat": "OK",
        "data": [["115/09/10", "1", "1", "204.50", "220.00", "204.50", "218.50"]],
    }

    with pytest.raises(ValueError, match="ticker or month"):
        build_official_market_dataset(
            inventory=inventory,
            session_calendar=_session_calendar(["2026-09-10"]),
            cutoff_session="2026-09-10",
            as_of="2026-09-10T15:05:00+08:00",
            fetch_month=lambda ticker, month: _capture(
                payload,
                url=(
                    "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
                    "?response=json&date=20260901&stockNo=2330"
                ),
            ),
        )


def test_build_official_market_dataset_requires_non_backfillable_capture_time():
    inventory = {
        "coverage_status": "closed",
        "candidates": [{"candidate_id": "tw-v1", "ticker": "1623.TW", "pipeline_id": "v1"}],
    }
    payload = {
        "stat": "OK",
        "data": [["115/09/10", "1", "1", "204.50", "220.00", "204.50", "218.50"]],
    }

    with pytest.raises(ValueError, match="capture time is required"):
        build_official_market_dataset(
            inventory=inventory,
            session_calendar=_session_calendar(["2026-09-10"]),
            cutoff_session="2026-09-10",
            as_of="2026-09-10T15:05:00+08:00",
            fetch_month=lambda ticker, month: {
                key: value
                for key, value in _capture(payload, url=official_url(ticker, month)).items()
                if key != "captured_at"
            },
        )


def test_build_official_market_dataset_as_of_equals_latest_capture_time():
    inventory = {
        "coverage_status": "closed",
        "candidates": [{"candidate_id": "tw-v1", "ticker": "1623.TW", "pipeline_id": "v1"}],
    }
    payload = {
        "stat": "OK",
        "data": [["115/09/10", "1", "1", "204.50", "220.00", "204.50", "218.50"]],
    }

    with pytest.raises(ValueError, match="latest capture time"):
        build_official_market_dataset(
            inventory=inventory,
            session_calendar=_session_calendar(["2026-09-10"]),
            cutoff_session="2026-09-10",
            as_of="2026-09-10T07:06:00Z",
            fetch_month=lambda ticker, month: _capture(
                payload,
                url=official_url(ticker, month),
                captured_at="2026-09-10T07:05:00Z",
            ),
        )


def test_build_official_market_dataset_rejects_same_day_capture_before_data_ready_boundary():
    inventory = {
        "coverage_status": "closed",
        "candidates": [{"candidate_id": "tw-v1", "ticker": "1623.TW", "pipeline_id": "v1"}],
    }
    payload = {
        "stat": "OK",
        "data": [["115/09/10", "1", "1", "204.50", "220.00", "204.50", "218.50"]],
    }

    with pytest.raises(ValueError, match="data-ready boundary"):
        build_official_market_dataset(
            inventory=inventory,
            session_calendar=_session_calendar(["2026-09-10"]),
            cutoff_session="2026-09-10",
            fetch_month=lambda ticker, month: _capture(
                payload,
                url=official_url(ticker, month),
                captured_at="2026-09-10T06:59:59Z",
            ),
        )


def test_build_official_market_dataset_rejects_inventory_hash_mismatch_before_fetch():
    inventory = {
        "coverage_status": "closed",
        "inventory_sha256": "a" * 64,
        "candidates": [{"candidate_id": "tw-v1", "ticker": "1623.TW", "pipeline_id": "v1"}],
    }
    calls = []

    with pytest.raises(ValueError, match="inventory hash mismatch"):
        build_official_market_dataset(
            inventory=inventory,
            session_calendar=_session_calendar(["2026-09-09", "2026-09-10"]),
            cutoff_session="2026-09-10",
            as_of="2026-09-10T15:05:00+08:00",
            fetch_month=lambda ticker, month: calls.append((ticker, month)),
        )

    assert calls == []


def test_dataset_rejects_future_sessions_and_post_as_of_capture():
    base = {
        "schema_version": "oos.dataset.v1",
        "provider": "fixture",
        "timezone": "Asia/Taipei",
        "as_of": "2026-09-10T15:05:00+08:00",
        "price_policy": "raw",
        "corporate_action_policy": "explicit_unprocessed_allowed",
        "calendar": ["2026-09-10"],
        "bars": {"1623.TW": [{
            "date": "2026-09-10",
            "open": 216.0,
            "high": 220.0,
            "low": 216.0,
            "close": 218.5,
            "complete": True,
            "completed_at": "2026-09-10T15:00:00+08:00",
        }]},
    }
    assert validate_dataset(base)

    future_calendar = {**base, "calendar": ["2026-09-10", "2026-09-11"]}
    with pytest.raises(ValueError, match="calendar exceeds dataset as_of"):
        validate_dataset(future_calendar)

    post_as_of = json.loads(json.dumps(base))
    post_as_of["bars"]["1623.TW"][0]["completed_at"] = "2026-09-10T15:06:00+08:00"
    with pytest.raises(ValueError, match="completed_at exceeds dataset as_of"):
        validate_dataset(post_as_of)
