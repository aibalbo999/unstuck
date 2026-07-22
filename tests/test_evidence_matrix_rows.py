import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.evidence_matrix_rows import build_rows_from_context  # noqa: E402


def _context(*, trust=None):
    return {
        "data": {
            "data_trust": trust or {"status": "fresh", "score": 90, "critical_failures": [], "stale_sources": []},
        },
        "parsed": {
            "price_targets": {"熊市情境": 80, "基本情境": 120, "牛市情境": 140},
            "moat_scores": {"品牌": "4/5", "成本": "3/5"},
            "recommendation": {"建議": "買入", "12個月": "NT$130", "信心": "7/10"},
        },
    }


def _key_rows(*, stale=False):
    return [
        {
            "label": "股價與市值",
            "source_label": "股價與市值",
            "provider": "yfinance",
            "status": "success",
            "fetched_at": "2026-07-14T09:00:00+08:00",
            "stale": False,
        },
        {
            "label": "年度財報",
            "source_label": "年度財報",
            "provider": "twse",
            "status": "success",
            "fetched_at": "2026-07-14T10:00:00+08:00",
            "stale": stale,
        },
        {
            "label": "近期催化劑",
            "source_label": "近期催化劑",
            "provider": "news",
            "status": "success",
            "fetched_at": "2026-07-14T08:00:00+08:00",
            "stale": False,
        },
    ]


def test_evidence_matrix_rows_from_context_builds_final_recommendation_coverage():
    rows = build_rows_from_context(_context(), _key_rows())

    final = next(row for row in rows if row["claim"] == "最終投資建議")

    assert final["status"] == "success"
    assert final["fetched_at"] == "2026-07-14T10:00:00+08:00"
    assert "股價與市值" in final["source"]
    assert "年度財報" in final["source"]
    assert "yfinance" in final["provider"]
    assert "twse" in final["provider"]
    assert final["limitation"] == "未記錄額外資料限制。"


def test_evidence_matrix_rows_from_context_preserves_data_limitations():
    context = _context(trust={"status": "partial", "score": 70, "critical_failures": ["market_data"], "stale_sources": []})
    context["data"]["data_source_notes"] = ("TTM 淨利率已依最新財報補值。",)

    rows = build_rows_from_context(context, _key_rows(stale=True))

    final = next(row for row in rows if row["claim"] == "最終投資建議")
    assert "TTM 淨利率已依最新財報補值。" in final["limitation"]
    assert "資料可信度：" in final["limitation"]
    assert "過期來源：年度財報。" in final["limitation"]
    assert "核心異常：市場資料。" in final["limitation"]
