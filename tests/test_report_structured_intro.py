import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_structured_intro_formats_decimal_price_targets_like_numeric_values():
    from reporting.structured_intro import build_structured_intro_block

    block = build_structured_intro_block(
        4,
        {
            "pipeline_id": "v1",
            "parsed": {
                "price_targets": {
                    "熊市情境": Decimal("80"),
                    "基本情境": Decimal("100"),
                    "牛市情境": Decimal("120"),
                }
            },
        },
    )

    assert "熊市情境: NT$80" in block
    assert "基本情境: NT$100" in block
    assert "牛市情境: NT$120" in block
    assert "熊市情境: 80" not in block
    assert "基本情境: 100" not in block
    assert "牛市情境: 120" not in block


def test_structured_intro_formats_string_price_targets_like_numeric_values():
    from reporting.structured_intro import build_structured_intro_block

    block = build_structured_intro_block(
        4,
        {
            "pipeline_id": "v1",
            "parsed": {
                "price_targets": {
                    "熊市情境": "100",
                    "基本情境": "NT$320",
                    "牛市情境": "1e3",
                }
            },
        },
    )

    assert "熊市情境: NT$100" in block
    assert "基本情境: NT$320" in block
    assert "牛市情境: NT$1,000" in block
    assert "熊市情境: 100" not in block
    assert "牛市情境: 1e3" not in block


def test_structured_intro_rejects_string_non_finite_price_targets():
    from reporting.structured_intro import build_structured_intro_block

    block = build_structured_intro_block(
        4,
        {
            "pipeline_id": "v1",
            "parsed": {
                "price_targets": {
                    "熊市情境": "NaN",
                    "基本情境": "Infinity",
                    "牛市情境": "-Infinity",
                }
            },
        },
    )

    assert "熊市情境: N/A" in block
    assert "基本情境: N/A" in block
    assert "牛市情境: N/A" in block
    assert "nan" not in block.lower()
    assert "infinity" not in block.lower()


def test_structured_intro_recommendation_rejects_non_finite_string_tokens():
    from reporting.structured_intro import build_structured_intro_block

    block = build_structured_intro_block(
        7,
        {
            "pipeline_id": "v1",
            "parsed": {
                "recommendation": {
                    "建議": "NaN",
                    "3個月": "Infinity",
                    "6個月": "-Infinity",
                    "12個月": "N/A",
                    "5年": "NaN",
                    "信心": "Infinity",
                }
            },
        },
    )

    assert "建議：N/A" in block
    assert "短期目標（3個月）：N/A" in block
    assert "中期目標（6個月）：N/A" in block
    assert "長期目標（12個月）：N/A" in block
    assert "長期潛力（5年）：N/A" in block
    assert "信心指數：N/A" in block
    assert "nan" not in block.lower()
    assert "infinity" not in block.lower()
