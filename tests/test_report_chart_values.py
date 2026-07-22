import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_report_chart_values_filter_future_price_history_from_mapping():
    from reporting.chart_values import filter_future_price_history

    assert filter_future_price_history({
        "2000-01-03": 100,
        "2999-01-03": 999,
        "bad-date": 50,
    }) == {"2000-01-03": 100}


def test_report_chart_values_normalize_moat_scores_and_money_series_safely():
    from reporting.chart_values import billion_twd_series_to_yi_twd, normalize_moat_scores

    class BoolHostileList(list):
        def __bool__(self):
            raise KeyError("chart series truthiness unavailable")

    assert normalize_moat_scores({
        "品牌影響力": 4,
        "整體護城河": 3.5,
        "草稿筆記": 9,
        "成本優勢": True,
        "專利技術": "5",
    }) == {"品牌影響力": 4, "整體護城河": 3.5}
    assert billion_twd_series_to_yi_twd(BoolHostileList([5.53, "1.2", None, True, "bad"])) == [
        55.3,
        12.0,
        None,
        True,
        "bad",
    ]


def test_report_chart_values_drop_non_finite_money_series_values():
    from reporting.chart_values import billion_twd_series_to_yi_twd

    assert billion_twd_series_to_yi_twd([
        float("nan"),
        float("inf"),
        float("-inf"),
        "Infinity",
        "-Infinity",
        "NaN",
        "2.5",
    ]) == [None, None, None, None, None, None, 25.0]
