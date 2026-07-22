import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_collect_next_catalysts_skips_decimal_non_finite_trigger_rows():
    from reporting.html_context import collect_next_catalysts

    catalysts = collect_next_catalysts({
        "next_catalysts": [
            {
                "event_name": "壞資料",
                "expected_timeframe": "本季",
                "impact_direction": "bullish",
                "trigger_condition": Decimal("NaN"),
            },
            {
                "event_name": "法說會更新",
                "expected_timeframe": "下一季",
                "impact_direction": "bullish",
                "trigger_condition": "管理層調升毛利率指引",
            },
        ]
    })

    assert catalysts == [
        {
            "event_name": "法說會更新",
            "expected_timeframe": "下一季",
            "impact_direction": "bullish",
            "trigger_condition": "管理層調升毛利率指引",
        }
    ]
    assert "nan" not in str(catalysts).lower()
