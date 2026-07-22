import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_report_html_chart_context_builds_json_safe_chart_payload():
    from reporting.html_chart_context import build_html_chart_context

    context = build_html_chart_context(
        {
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "years": [b"bad-year", "2026"],
            "revenue_history": [10, memoryview(b"bad-revenue")],
            "net_income_history": [float("nan"), 4],
            "fcf_history": [2, bytearray(b"bad-fcf")],
            "gross_margin_history": [45, b"bad-margin"],
            "op_margin_history": [30, float("inf")],
            "net_margin_history": [20, bytearray(b"bad-net-margin")],
            "roe_history": [18, memoryview(b"bad-roe")],
            "price_history": {"dates": ["2026-01-02"], "prices": [memoryview(b"bad-price")]},
            "pe_river_chart": {
                "source": "default multiples",
                "years": [b"bad-river-year", "2026"],
                "bands": {"15x": [memoryview(b"bad-band"), 120]},
                "eps": [bytearray(b"bad-eps"), 8],
            },
        },
        {
            "price_targets": {"牛市情境": "150", b"bad-target-label": memoryview(b"bad-target")},
            "moat_scores": {"品牌影響力": 7, "整體護城河": 8, "草稿筆記": 10},
        },
    )

    chart_data = context["chart_data"]

    assert chart_data["years"] == ["", "2026"]
    assert chart_data["revenue"] == [100, None]
    assert chart_data["netIncome"] == [None, 40]
    assert chart_data["grossMargin"] == [45, None]
    assert chart_data["opMargin"] == [30, None]
    assert chart_data["priceHistory"] == {"dates": ["2026-01-02"], "prices": [None]}
    assert chart_data["moatLabels"] == ["品牌影響力", "整體護城河"]
    assert chart_data["moatValues"] == [7, 8]
    assert chart_data["priceTargets"] == {"牛市情境": 150.0, "情境": None}
    assert chart_data["currentPrice"] == 100
    assert chart_data["peRiver"]["years"] == ["", "2026"]
    assert chart_data["peRiver"]["bands"] == {"15x": [None, 120]}
    assert chart_data["peRiver"]["eps"] == [None, 8]
    assert context["overall_moat"] == 8
    assert context["current_price_numeric"] == 100
    assert context["pe_river_title"] == "P/E 河流圖（EPS × 預設本益比通道）"
    assert "metric-card" in context["metrics_html"]
    assert "price-target-card" in context["price_targets_html"]


def test_report_html_chart_context_uses_unique_fallback_pe_river_band_labels():
    from reporting.html_chart_context import build_html_chart_context

    context = build_html_chart_context(
        {
            "current_price": 100,
            "pe_river_chart": {
                "source": "historical_pe",
                "years": ["2025", "2026"],
                "bands": {
                    b"bad-band-one": [80, 90],
                    b"bad-band-two": [100, 110],
                    "15x": [120, 130],
                },
                "eps": [6, 8],
            },
        },
        {"price_targets": {}, "moat_scores": {}},
    )

    assert context["chart_data"]["peRiver"]["bands"] == {
        "估值通道": [80, 90],
        "估值通道 2": [100, 110],
        "15x": [120, 130],
    }
    assert "" not in context["chart_data"]["peRiver"]["bands"]


def test_report_html_chart_context_uses_unique_fallback_price_target_labels():
    from reporting.html_chart_context import build_html_chart_context

    context = build_html_chart_context(
        {"current_price": 100},
        {
            "price_targets": {
                b"bad-target-one": "120",
                b"bad-target-two": "130",
                "牛市情境": "150",
            },
            "moat_scores": {},
        },
    )

    expected = {
        "情境": 120.0,
        "情境 2": 130.0,
        "牛市情境": 150.0,
    }
    assert context["price_targets"] == expected
    assert context["chart_data"]["priceTargets"] == expected
    assert "" not in context["price_targets"]


def test_report_html_chart_context_rejects_non_finite_scientific_price_targets():
    from reporting.html_chart_context import build_html_chart_context

    context = build_html_chart_context(
        {"current_price": 100},
        {
            "price_targets": {
                "壞科學記號": "NT$1e309",
                "合法科學記號": "NT$1e3",
            },
            "moat_scores": {},
        },
    )

    assert context["price_targets"] == {
        "壞科學記號": None,
        "合法科學記號": 1000.0,
    }
    assert context["chart_data"]["priceTargets"] == context["price_targets"]


def test_chart_payload_rejects_non_finite_scientific_text_with_units():
    from reporting.chart_payload import chart_number

    assert chart_number("NT$1e309") is None
    assert chart_number("NT$1e3") == 1000.0
    assert chart_number("NT$1e3", scale=10) == 10000.0


def test_report_html_chart_context_drops_string_empty_tokens_from_chart_labels():
    from reporting.html_chart_context import build_html_chart_context

    context = build_html_chart_context(
        {
            "current_price": 100,
            "years": ["NaN", "2026"],
            "price_history": {
                "dates": ["Infinity", "2026-01-02"],
                "prices": [999, 100],
            },
            "pe_river_chart": {
                "source": "Infinity",
                "years": ["-Infinity", "2026"],
                "bands": {
                    "NaN": [80, 90],
                    "Infinity": [100, 110],
                    "15x": [120, 130],
                },
                "eps": [6, 8],
            },
        },
        {
            "price_targets": {
                "NaN": "120",
                "Infinity": "130",
                "牛市情境": "150",
            },
            "moat_scores": {},
        },
    )

    chart_data = context["chart_data"]

    assert chart_data["years"] == ["", "2026"]
    assert chart_data["priceHistory"] == {"dates": ["2026-01-02"], "prices": [100.0]}
    assert chart_data["peRiver"].get("source") is None
    assert chart_data["peRiver"]["years"] == ["", "2026"]
    assert chart_data["peRiver"]["bands"] == {
        "估值通道": [80, 90],
        "估值通道 2": [100, 110],
        "15x": [120, 130],
    }
    assert context["price_targets"] == {
        "情境": 120.0,
        "情境 2": 130.0,
        "牛市情境": 150.0,
    }
    rendered_labels = repr(chart_data) + repr(context["price_targets"])
    assert "NaN" not in rendered_labels
    assert "Infinity" not in rendered_labels
