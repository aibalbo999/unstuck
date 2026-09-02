from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_data_fetch_blocking_notice_does_not_treat_missing_placeholders_as_core_data():
    from analysis_job_helpers import build_data_fetch_blocking_notice

    result = SimpleNamespace(
        data={
            "error": "核心資料暫時不可用",
            "current_price": "N/A",
            "market_cap_raw": "N/A",
            "years": ["N/A"],
            "revenue_history": [],
        },
        data_trust={"status": "partial"},
    )

    notice = build_data_fetch_blocking_notice(result)

    assert notice is not None
    assert notice["data_trust"] == {"status": "partial"}
    assert "沒有可用核心資料" in notice["message"]


def test_data_fetch_blocking_notice_keeps_partial_error_non_blocking_with_core_data():
    from analysis_job_helpers import build_data_fetch_blocking_notice

    result = SimpleNamespace(
        data={
            "error": "補充來源暫時不可用",
            "current_price": 100,
            "market_cap_raw": "N/A",
            "years": [],
            "revenue_history": [],
        },
        data_trust={"status": "partial"},
    )

    assert build_data_fetch_blocking_notice(result) is None
