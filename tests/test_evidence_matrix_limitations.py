import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _limitations_module():
    return importlib.import_module("reporting.evidence_matrix_limitations")


def test_evidence_matrix_limitations_builds_source_summary_without_row_assembly():
    limitations = _limitations_module()
    rows = [
        {
            "source_label": "股價與市值",
            "provider": "yfinance",
            "status": "success",
            "fetched_at": "2026-07-14T09:00:00+08:00",
            "stale": False,
        },
        {
            "source_label": "年度財報",
            "provider": "twse",
            "status": "warning",
            "fetched_at": "2026-07-14T10:00:00+08:00",
            "stale": True,
        },
    ]

    assert limitations.combined_evidence_status(rows, "fresh") == "degraded_enrichment"
    assert limitations.latest_evidence_fetched_at(rows) == "2026-07-14T10:00:00+08:00"

    text = limitations.evidence_data_limitations(
        {"data_source_notes": ["TTM 淨利率已依最新財報補值。", b"bad-note"]},
        {"status": "partial", "critical_failures": ["market_data"]},
        rows,
    )

    assert "TTM 淨利率已依最新財報補值。" in text
    assert "資料可信度：" in text
    assert "過期來源：年度財報。" in text
    assert "核心異常：市場資料。" in text
    assert "bad-note" not in text


def test_evidence_matrix_limitations_helpers_are_truthiness_safe():
    limitations = _limitations_module()

    class BrokenTruthiness:
        def __bool__(self):
            raise KeyError("truthiness unavailable")

        def __str__(self):
            return "success"

    class BrokenFetchedAtTruthiness:
        def __bool__(self):
            raise KeyError("fetched_at truthiness unavailable")

        def __str__(self):
            return "2026-07-14T11:00:00+08:00"

    rows = [
        {
            "source_label": "股價與市值",
            "status": BrokenTruthiness(),
            "fetched_at": BrokenFetchedAtTruthiness(),
            "stale": BrokenTruthiness(),
        },
    ]

    assert limitations.combined_evidence_status(rows, "fresh") == "success"
    assert limitations.latest_evidence_fetched_at(rows) == "2026-07-14T11:00:00+08:00"
    assert limitations.evidence_data_limitations({}, {"status": "fresh"}, rows) == "未記錄額外資料限制。"
