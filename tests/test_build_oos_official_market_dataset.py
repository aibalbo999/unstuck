from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import ssl

import pytest

from oos_research.canonical import content_hash
from oos_research.official_market_data import verify_official_market_dataset


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_oos_official_market_dataset.py"


def _module():
    spec = importlib.util.spec_from_file_location("build_oos_official_market_dataset_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, url, payload):
        self._url = url
        self._data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, maximum):
        return self._data[:maximum]

    def geturl(self):
        return self._url


def test_script_captures_official_raw_responses_and_writes_exclusive_dataset(tmp_path):
    module = _module()
    inventory_path = tmp_path / "inventory.json"
    sessions_path = tmp_path / "sessions.json"
    raw_dir = tmp_path / "raw-20260910T150500+0800"
    output = tmp_path / "dataset-20260910T150500+0800.json"
    inventory = {
        "coverage_status": "closed",
        "candidates": [
            {"candidate_id": "tw", "ticker": "1623.TW", "pipeline_id": "v1"},
            {"candidate_id": "two", "ticker": "3324.TWO", "pipeline_id": "v1"},
        ],
    }
    inventory["inventory_sha256"] = content_hash(inventory)
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    sessions = {
        "schema_version": "oos.exchange-sessions.v1",
        "market": "tw",
        "timezone": "Asia/Taipei",
        "session_open_local_time": "09:00:00",
        "range": {"start": "2026-09-09", "end": "2026-09-11"},
        "calendar_definition_sha256": "c" * 64,
        "sessions": ["2026-09-09", "2026-09-10", "2026-09-11"],
    }
    sessions_path.write_text(json.dumps(sessions), encoding="utf-8")
    twse = {"stat": "OK", "data": [
        ["115/09/09", "1", "1", "204.5", "220", "204.5", "218.5"],
        ["115/09/10", "1", "1", "216", "220", "216", "218.5"],
    ]}
    tpex = {"tables": [{"data": [
        ["115/09/09", "1", "1", "1375", "1400", "1320", "1385"],
        ["115/09/10", "1", "1", "1355", "1440", "1355", "1440"],
    ]}]}
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, timeout, request.headers.get("User-agent")))
        payload = tpex if "tpex.org.tw" in request.full_url else twse
        return FakeResponse(request.full_url, payload)

    argv = [
        "--inventory", str(inventory_path),
        "--expected-inventory-sha256", inventory["inventory_sha256"],
        "--sessions", str(sessions_path),
        "--expected-session-calendar-sha256", content_hash(sessions),
        "--cutoff-session", "2026-09-10",
        "--raw-dir", str(raw_dir),
        "--output", str(output),
    ]
    clock = lambda: datetime(2026, 9, 10, 7, 5, tzinfo=timezone.utc)
    assert module.main(argv, opener=opener, clock=clock) == 0

    dataset = json.loads(output.read_text(encoding="utf-8"))
    assert dataset["candidate_inventory_sha256"] == inventory["inventory_sha256"]
    assert dataset["as_of"] == "2026-09-10T07:05:00Z"
    assert dataset["builder_identity"]["schema_version"] == "oos.dataset-builder-identity.v1"
    assert dataset["builder_identity"]["source_sha256"]
    assert "scripts/build_oos_official_market_dataset.py" in dataset["builder_identity"]["files"]
    assert dataset["calendar"] == ["2026-09-09", "2026-09-10"]
    assert len(list(raw_dir.glob("*.json"))) == 2
    assert all(capture["raw_file"].startswith(f"{raw_dir.name}/") for capture in dataset["source_captures"])
    assert verify_official_market_dataset(
        dataset,
        inventory=json.loads(inventory_path.read_text(encoding="utf-8")),
        session_calendar=json.loads(sessions_path.read_text(encoding="utf-8")),
        dataset_path=str(output),
    ) == dataset["dataset_sha256"]
    assert calls == [
        (
            "https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20260901&stockNo=1623",
            30,
            "stock-agent-oos/1.0",
        ),
        (
            "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code=3324&date=2026%2F09%2F01&response=json",
            30,
            "stock-agent-oos/1.0",
        ),
    ]

    with pytest.raises(ValueError, match="new absolute"):
        module.main(argv, opener=opener, clock=clock)
    assert len(calls) == 2

    tampered = json.loads(json.dumps(dataset))
    tampered["bars"]["1623.TW"][0]["close"] = 219.0
    tampered["dataset_sha256"] = content_hash({
        key: value for key, value in tampered.items() if key != "dataset_sha256"
    })
    with pytest.raises(ValueError, match="does not match raw"):
        verify_official_market_dataset(
            tampered,
            inventory=json.loads(inventory_path.read_text(encoding="utf-8")),
            session_calendar=json.loads(sessions_path.read_text(encoding="utf-8")),
            dataset_path=str(output),
        )

    tampered_calendar = json.loads(json.dumps(dataset))
    tampered_calendar["calendar"] = ["2026-09-09"]
    for rows in tampered_calendar["bars"].values():
        rows[:] = [row for row in rows if row["date"] == "2026-09-09"]
    tampered_calendar["dataset_sha256"] = content_hash({
        key: value for key, value in tampered_calendar.items() if key != "dataset_sha256"
    })
    with pytest.raises(ValueError, match="calendar does not match"):
        verify_official_market_dataset(
            tampered_calendar,
            inventory=json.loads(inventory_path.read_text(encoding="utf-8")),
            session_calendar=json.loads(sessions_path.read_text(encoding="utf-8")),
            dataset_path=str(output),
        )


@pytest.mark.parametrize(
    ("pin_flag", "wrong_pin", "message"),
    [
        ("--expected-inventory-sha256", "f" * 64, "inventory SHA-256"),
        ("--expected-session-calendar-sha256", "e" * 64, "session calendar SHA-256"),
    ],
)
def test_builder_rejects_wrong_external_pins_before_raw_creation_or_network(
    tmp_path, pin_flag, wrong_pin, message
):
    module = _module()
    inventory_path = tmp_path / "inventory.json"
    sessions_path = tmp_path / "sessions.json"
    raw_dir = tmp_path / "raw"
    output = tmp_path / "dataset.json"
    inventory = {
        "coverage_status": "closed",
        "candidates": [{"candidate_id": "tw", "ticker": "1623.TW", "pipeline_id": "v1"}],
    }
    inventory["inventory_sha256"] = content_hash(inventory)
    sessions = {
        "schema_version": "oos.exchange-sessions.v1",
        "market": "tw",
        "timezone": "Asia/Taipei",
        "session_open_local_time": "09:00:00",
        "range": {"start": "2026-09-09", "end": "2026-09-10"},
        "calendar_definition_sha256": "c" * 64,
        "sessions": ["2026-09-09", "2026-09-10"],
    }
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    sessions_path.write_text(json.dumps(sessions), encoding="utf-8")
    calls = []

    argv = [
        "--inventory", str(inventory_path),
        "--expected-inventory-sha256", inventory["inventory_sha256"],
        "--sessions", str(sessions_path),
        "--expected-session-calendar-sha256", content_hash(sessions),
        "--cutoff-session", "2026-09-10",
        "--raw-dir", str(raw_dir),
        "--output", str(output),
    ]
    argv[argv.index(pin_flag) + 1] = wrong_pin

    with pytest.raises(ValueError, match=message):
        module.main(argv, opener=lambda *args, **kwargs: calls.append((args, kwargs)))

    assert calls == []
    assert not raw_dir.exists()
    assert not output.exists()


def test_builder_rejects_non_session_cutoff_before_raw_creation_or_network(tmp_path):
    module = _module()
    inventory_path = tmp_path / "inventory.json"
    sessions_path = tmp_path / "sessions.json"
    raw_dir = tmp_path / "raw"
    output = tmp_path / "dataset.json"
    inventory = {
        "coverage_status": "closed",
        "candidates": [{"candidate_id": "tw", "ticker": "1623.TW", "pipeline_id": "v1"}],
    }
    inventory["inventory_sha256"] = content_hash(inventory)
    sessions = {
        "schema_version": "oos.exchange-sessions.v1",
        "market": "tw",
        "timezone": "Asia/Taipei",
        "session_open_local_time": "09:00:00",
        "range": {"start": "2026-09-09", "end": "2026-09-10"},
        "calendar_definition_sha256": "c" * 64,
        "sessions": ["2026-09-09", "2026-09-10"],
    }
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    sessions_path.write_text(json.dumps(sessions), encoding="utf-8")
    calls = []
    argv = [
        "--inventory", str(inventory_path),
        "--expected-inventory-sha256", inventory["inventory_sha256"],
        "--sessions", str(sessions_path),
        "--expected-session-calendar-sha256", content_hash(sessions),
        "--cutoff-session", "2026-09-08",
        "--raw-dir", str(raw_dir),
        "--output", str(output),
    ]

    with pytest.raises(ValueError, match="cutoff session is not in the official calendar"):
        module.main(argv, opener=lambda *args, **kwargs: calls.append((args, kwargs)))

    assert calls == []
    assert not raw_dir.exists()
    assert not output.exists()


def test_builder_rejects_premature_capture_before_raw_creation_or_network(tmp_path):
    module = _module()
    inventory_path = tmp_path / "inventory.json"
    sessions_path = tmp_path / "sessions.json"
    raw_dir = tmp_path / "raw"
    output = tmp_path / "dataset.json"
    inventory = {
        "coverage_status": "closed",
        "candidates": [{"candidate_id": "tw", "ticker": "1623.TW", "pipeline_id": "v1"}],
    }
    inventory["inventory_sha256"] = content_hash(inventory)
    sessions = {
        "schema_version": "oos.exchange-sessions.v1",
        "market": "tw",
        "timezone": "Asia/Taipei",
        "session_open_local_time": "09:00:00",
        "range": {"start": "2026-09-09", "end": "2026-09-10"},
        "calendar_definition_sha256": "c" * 64,
        "sessions": ["2026-09-09", "2026-09-10"],
    }
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    sessions_path.write_text(json.dumps(sessions), encoding="utf-8")
    response = {"stat": "OK", "data": [
        ["115/09/10", "1", "1", "216", "220", "216", "218.5"],
    ]}
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse(request.full_url, response)

    argv = [
        "--inventory", str(inventory_path),
        "--expected-inventory-sha256", inventory["inventory_sha256"],
        "--sessions", str(sessions_path),
        "--expected-session-calendar-sha256", content_hash(sessions),
        "--cutoff-session", "2026-09-10",
        "--raw-dir", str(raw_dir),
        "--output", str(output),
    ]

    with pytest.raises(ValueError, match="predates the cutoff data-ready boundary"):
        module.main(
            argv,
            opener=opener,
            clock=lambda: datetime(2026, 9, 10, 6, 59, tzinfo=timezone.utc),
        )

    assert calls == []
    assert not raw_dir.exists()
    assert not output.exists()

@pytest.mark.parametrize("ticker", ["../../etc/passwd.TW", "3324.TW%2FO"])
def test_official_url_rejects_unsafe_ticker(ticker):
    with pytest.raises(ValueError, match="ticker"):
        _module().official_url(ticker, "2026-09")


def test_official_ssl_context_keeps_ca_and_hostname_verification_enabled():
    context = _module().official_ssl_context()

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        assert context.verify_flags & ssl.VERIFY_X509_STRICT == 0


def test_evidence_writer_never_publishes_a_partial_final_file(tmp_path, monkeypatch):
    module = _module()
    output = tmp_path / "evidence.json"
    monkeypatch.setattr(module.os, "write", lambda descriptor, data: 0)

    with pytest.raises(OSError, match="short official evidence write"):
        module._write_exclusive(output, b"valuable")

    assert not output.exists()
