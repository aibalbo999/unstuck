import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


from reporting.summary_cards import build_metric_cards_html, build_price_target_cards_html  # noqa: E402


def test_metric_cards_escape_and_sanitize_plain_text_values():
    html = build_metric_cards_html({
        "current_price_fmt": "<script>alert(1)</script>NT$100",
        "market_cap_fmt": "NT$100億",
        "pe_ratio": "20.0x",
        "pb_ratio": "<img src=x onerror=1>",
    })

    assert 'class="metric-card"' in html
    assert "股價" in html
    assert "NT$100" in html
    assert "20.0x" in html
    assert "<script" not in html.lower()
    assert "alert(1)" not in html
    assert "onerror" not in html.lower()


def test_metric_cards_render_non_finite_numeric_values_as_na():
    html = build_metric_cards_html({
        "current_price_fmt": "NT$100",
        "market_cap_fmt": float("nan"),
        "pe_ratio": float("inf"),
        "pb_ratio": float("-inf"),
    })

    assert html.count('<div class="metric-value">N/A</div>') >= 3
    assert ">nan<" not in html.lower()
    assert ">inf<" not in html.lower()
    assert ">-inf<" not in html.lower()


def test_metric_cards_render_decimal_non_finite_numeric_values_as_na():
    html = build_metric_cards_html({
        "current_price_fmt": "NT$100",
        "market_cap_fmt": Decimal("NaN"),
        "pe_ratio": Decimal("Infinity"),
        "pb_ratio": Decimal("-Infinity"),
    })

    assert html.count('<div class="metric-value">N/A</div>') >= 3
    assert ">nan<" not in html.lower()
    assert ">infinity<" not in html.lower()
    assert ">-infinity<" not in html.lower()


def test_metric_cards_render_non_finite_string_tokens_as_na():
    html = build_metric_cards_html({
        "current_price_fmt": "NT$100",
        "market_cap_fmt": "NaN",
        "pe_ratio": "Infinity",
        "pb_ratio": "-Infinity",
        "gross_margin": "N/A",
    })

    assert html.count('<div class="metric-value">N/A</div>') >= 4
    assert ">nan<" not in html.lower()
    assert ">infinity<" not in html.lower()
    assert ">-infinity<" not in html.lower()


def test_price_target_cards_render_scenario_colors_and_current_price_delta():
    html = build_price_target_cards_html(
        {
            "熊市情境<script>alert(1)</script>": 80,
            "基本情境": "NT$100",
            "牛市情境": 125,
            "未知情境": None,
        },
        current_price=100,
    )

    assert 'class="price-target-card"' in html
    assert "熊市情境" in html
    assert "border-color: #ef4444" in html
    assert "↓ NT$80" in html
    assert "(-20.0%)" in html
    assert "→ NT$100" in html
    assert "↑ NT$125" in html
    assert "(+25.0%)" in html
    assert "未知情境" in html
    assert "N/A" in html
    assert "alert(1)" not in html


def test_price_target_cards_use_unique_fallback_scenario_labels():
    html = build_price_target_cards_html(
        {
            b"bad-scenario-one": 120,
            b"bad-scenario-two": 130,
            "牛市情境": 150,
        },
        current_price=100,
    )

    assert '<div class="pt-scenario">情境</div>' in html
    assert '<div class="pt-scenario">情境 2</div>' in html
    assert '<div class="pt-scenario">牛市情境</div>' in html
    assert "bad-scenario" not in html


def test_price_target_cards_drop_string_empty_tokens_from_scenario_labels():
    html = build_price_target_cards_html(
        {
            "NaN": 120,
            "Infinity": 130,
            "-Infinity": 90,
            "牛市情境": 150,
        },
        current_price=100,
    )

    assert '<div class="pt-scenario">情境</div>' in html
    assert '<div class="pt-scenario">情境 2</div>' in html
    assert '<div class="pt-scenario">情境 3</div>' in html
    assert '<div class="pt-scenario">牛市情境</div>' in html
    assert ">NaN<" not in html
    assert ">Infinity<" not in html
    assert ">-Infinity<" not in html
