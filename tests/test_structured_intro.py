import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_structured_intro_formats_finite_decimal_price_targets_as_currency():
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


def test_structured_intro_formats_non_finite_price_targets_as_na():
    from reporting.structured_intro import build_structured_intro_block

    block = build_structured_intro_block(
        4,
        {
            "pipeline_id": "v1",
            "parsed": {
                "price_targets": {
                    "熊市情境": float("nan"),
                    "基本情境": float("inf"),
                    "牛市情境": Decimal("-Infinity"),
                }
            },
        },
    )

    assert "熊市情境: N/A" in block
    assert "基本情境: N/A" in block
    assert "牛市情境: N/A" in block
    assert "nan" not in block.lower()
    assert "inf" not in block.lower()
