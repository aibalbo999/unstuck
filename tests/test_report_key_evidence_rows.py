import sys
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_key_evidence_rows_aggregate_successful_providers_and_latest_fetch_time():
    from reporting.evidence_rows import build_key_evidence_rows

    data = {
        "current_price": 100,
        "market_cap_fmt": "NT$1T",
        "source_audit": [
            {
                "source": "market_data",
                "provider": "yfinance",
                "status": "success",
                "fetched_at": "2026-07-01T00:00:00+08:00",
                "record_count": 2,
                "stale": False,
            },
            {
                "source": "market_data",
                "provider": "twse",
                "status": "skipped_fresh_cache",
                "fetched_at": "2026-07-02T00:00:00+08:00",
                "record_count": 3,
                "stale": False,
            },
        ],
    }

    rows = build_key_evidence_rows(data)

    assert rows == [
        {
            "label": "股價與市值",
            "source_label": "市場資料",
            "provider": "yfinance + twse",
            "status": "success",
            "status_label": "成功",
            "fetched_at": "2026-07-02T00:00:00+08:00",
            "record_count": 5,
            "stale": False,
        }
    ]


def test_key_evidence_rows_fall_back_to_latest_audit_when_data_has_no_successful_records():
    from reporting.evidence_rows import build_key_evidence_rows

    data = {
        "recent_catalysts": [{"title": "AI demand catalyst"}],
        "source_audit": [
            {
                "source": "recent_catalysts",
                "provider": "search",
                "status": "success",
                "fetched_at": "2026-07-01T00:00:00+08:00",
                "record_count": 0,
                "stale": False,
            },
            {
                "source": "recent_catalysts",
                "provider": "fallback",
                "status": "unavailable",
                "fetched_at": "2026-07-02T00:00:00+08:00",
                "record_count": 0,
                "stale": True,
            },
        ],
    }

    rows = build_key_evidence_rows(data)

    assert rows[0]["label"] == "近期催化劑"
    assert rows[0]["provider"] == "fallback"
    assert rows[0]["status"] == "unavailable"
    assert rows[0]["record_count"] == 0
    assert rows[0]["stale"] is True


def test_key_evidence_rows_tolerate_mapping_proxy_and_malformed_text_values():
    from reporting.evidence_rows import build_key_evidence_rows

    class MalformedText:
        def __str__(self):
            raise RuntimeError("key evidence row text unavailable")

    data = MappingProxyType({
        "current_price": "100",
        "source_audit": [
            MappingProxyType({
                "source": "market_data",
                "provider": MalformedText(),
                "status": "success",
                "fetched_at": MalformedText(),
                "record_count": 1,
                "stale": False,
            })
        ],
    })

    rows = build_key_evidence_rows(data)

    assert rows[0]["provider"] == "未記錄"
    assert rows[0]["fetched_at"] == "N/A"
    assert rows[0]["status"] == "success"


def test_key_evidence_rows_drop_non_finite_source_audit_text_fields():
    from reporting.evidence_rows import build_key_evidence_rows

    data = {
        "current_price": 100,
        "source_audit": [
            {
                "source": "market_data",
                "provider": float("nan"),
                "status": Decimal("Infinity"),
                "fetched_at": Decimal("-Infinity"),
                "record_count": 1,
                "stale": False,
            }
        ],
    }

    rows = build_key_evidence_rows(data)
    rendered = str(rows)

    assert rows[0]["provider"] == "未記錄"
    assert rows[0]["status"] == "unknown"
    assert rows[0]["status_label"] == "unknown"
    assert rows[0]["fetched_at"] == "N/A"
    assert "nan" not in rendered.lower()
    assert "infinity" not in rendered.lower()


def test_key_evidence_rows_drop_non_finite_string_source_audit_text_fields():
    from reporting.evidence_rows import build_key_evidence_rows

    data = {
        "current_price": 100,
        "source_audit": [
            {
                "source": "market_data",
                "provider": "Infinity",
                "status": "NaN",
                "fetched_at": "-Infinity",
                "record_count": 1,
                "stale": False,
            }
        ],
    }

    rows = build_key_evidence_rows(data)
    rendered = str(rows)

    assert rows[0]["provider"] == "未記錄"
    assert rows[0]["status"] == "unknown"
    assert rows[0]["status_label"] == "unknown"
    assert rows[0]["fetched_at"] == "N/A"
    assert "nan" not in rendered.lower()
    assert "infinity" not in rendered.lower()


def test_key_evidence_rows_do_not_count_string_tokens_as_evidence_values():
    from reporting.evidence_rows import build_key_evidence_rows

    data = {
        "current_price": "NaN",
        "market_cap_raw": "Infinity",
        "market_cap_fmt": "N/A",
        "source_audit": [
            {
                "source": "market_data",
                "provider": "yfinance",
                "status": "success",
                "fetched_at": "2026-07-02T00:00:00+08:00",
                "record_count": 3,
                "stale": False,
            }
        ],
    }

    assert build_key_evidence_rows(data) == []
