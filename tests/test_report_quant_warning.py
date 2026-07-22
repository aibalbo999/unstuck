import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


from reporting.quant_warning import build_quant_warning_html, build_quant_warning_markdown  # noqa: E402


def test_quant_warning_helper_builds_consistent_html_and_markdown_warning():
    data = {
        "quant_metrics": {
            "fallback_fields": [b"bad-field", "wacc\nfield", "terminal_growth"],
            "data_quality_warning": "DCF 欄位\n使用預設假設。",
        }
    }

    html = build_quant_warning_html(data)
    markdown = build_quant_warning_markdown(data)
    rendered = html + markdown

    assert "量化模型警示" in rendered
    assert "DCF 欄位 使用預設假設。" in markdown
    assert "DCF 欄位\n使用預設假設。" not in markdown
    assert "bad-field" not in rendered
    assert "wacc field" not in rendered


def test_quant_warning_helper_returns_empty_sections_without_fallback_fields():
    data = {"quant_metrics": {"data_quality_warning": "不應單獨出現"}}

    assert build_quant_warning_html(data) == ""
    assert build_quant_warning_markdown(data) == ""


def test_quant_warning_helper_drops_non_finite_warning_fields_and_message():
    data = {
        "quant_metrics": {
            "fallback_fields": [float("nan"), Decimal("Infinity"), "wacc"],
            "data_quality_warning": Decimal("NaN"),
        }
    }

    html = build_quant_warning_html(data)
    markdown = build_quant_warning_markdown(data)
    rendered = html + markdown

    assert "量化模型警示" in rendered
    assert "wacc" in rendered
    assert "以下欄位使用預設假設" in rendered
    assert "nan" not in rendered.lower()
    assert "infinity" not in rendered.lower()


def test_quant_warning_helper_drops_non_finite_string_token_fields_and_message():
    data = {
        "quant_metrics": {
            "fallback_fields": ["Infinity", "wacc", "NaN", "N/A", "-Infinity"],
            "data_quality_warning": "NaN",
        }
    }

    html = build_quant_warning_html(data)
    markdown = build_quant_warning_markdown(data)
    rendered = html + markdown

    assert "量化模型警示" in rendered
    assert "wacc" in rendered
    assert "以下欄位使用預設假設" in rendered
    assert "nan" not in rendered.lower()
    assert "infinity" not in rendered.lower()
