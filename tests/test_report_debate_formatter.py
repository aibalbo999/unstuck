import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.debate_formatter import format_debate_text  # noqa: E402


def test_debate_formatter_renders_roles_conclusion_and_narration_safely():
    html = format_debate_text(
        "\n".join(
            [
                "🐂 陳博士：<img src=x onerror=1> AI 需求支撐多頭假設。",
                "🐻 李博士：<script>alert(1)</script> 庫存修正仍是下行風險。",
                "主持人總結：等待財報確認。",
                "這是一段足夠長的背景敘述，應該保留為旁白。",
            ]
        )
    )

    assert "bull-bubble" in html
    assert "bear-bubble" in html
    assert "debate-conclusion" in html
    assert "debate-narration" in html
    assert "AI 需求支撐多頭假設。" in html
    assert "庫存修正仍是下行風險。" in html
    assert "等待財報確認。" in html
    assert "<script" not in html.lower()
    assert "<img" not in html.lower()
    assert "onerror" not in html.lower()


def test_debate_formatter_skips_short_narration_and_markdown_headings():
    html = format_debate_text(
        "\n".join(
            [
                "# 多空辯論",
                "短句",
                "一般敘述需要超過十個字才形成旁白段落。",
            ]
        )
    )

    assert "多空辯論" not in html
    assert "短句" not in html
    assert "一般敘述需要超過十個字才形成旁白段落。" in html
    assert html.count("debate-narration") == 1


def test_debate_formatter_drops_role_prefixed_string_empty_tokens():
    html = format_debate_text(
        "\n".join(
            [
                "🐂 陳博士：NaN",
                "🐻 李博士：Infinity",
                "主持人總結：-Infinity",
                "🐂 陳博士：有效多頭觀點。",
            ]
        )
    )

    assert "NaN" not in html
    assert "Infinity" not in html
    assert "-Infinity" not in html
    assert "有效多頭觀點。" in html
    assert html.count("debate-bubble") == 1
