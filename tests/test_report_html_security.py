import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.html_renderer import generate_html_report  # noqa: E402
from reporting.html_sanitizer import sanitize_report_html, sanitize_report_image_url  # noqa: E402
from reporting.utils import clean_markdown, format_debate_text  # noqa: E402


def test_markdown_and_debate_html_are_sanitized():
    html = clean_markdown(
        """
正常段落

<script>window.__x = 1</script>

<img src=x onerror=alert(1)>

[惡意連結](javascript:alert(1))
"""
    )
    debate_html = format_debate_text("🐂 陳博士：<img src=x onerror=1> bullish")

    combined = html + debate_html
    assert "<script" not in combined.lower()
    assert "window.__x" not in combined
    assert "onerror" not in combined.lower()
    assert "javascript:" not in combined.lower()


def test_rendered_report_escapes_external_and_model_strings():
    context = {
        "ticker": '2330"><img src=x onerror=1>',
        "company_name": "台積電<script>alert(1)</script>",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "sector": "<script>bad()</script>",
            "industry": '<img src=x onerror=1>',
            "current_price": 100,
            "current_price_fmt": '<img src=x onerror=1>',
            "source_audit": [],
        },
        "analyses": {
            1: "## 分析\n<script>alert(1)</script>\n<img src=x onerror=alert(1)>",
            6: "🐂 陳博士：<img src=x onerror=1> 看多",
        },
        "parsed": {
            "price_targets": {'基本情境<img src=x onerror=1>': 120},
            "recommendation": {
                "建議": "持有<script>alert(1)</script>",
                "3個月": '<img src=x onerror=1>',
                "信心": "7/10",
            },
        },
        "report_cover": {"image": "javascript:alert(1)"},
    }

    html = generate_html_report(context)

    assert "alert(1)" not in html
    assert "onerror" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "background-image: url('javascript" not in html.lower()
    assert "台積電" in html


def test_report_cover_image_url_allowlist():
    data_url = "data:image/png;base64,QUJDRA=="

    assert sanitize_report_image_url(data_url) == data_url
    assert sanitize_report_image_url("https://example.com/cover.jpg") == "https://example.com/cover.jpg"
    assert sanitize_report_image_url("javascript:alert(1)") == ""


def test_taiwan_ticker_autolinks_use_real_quote_pages():
    html = sanitize_report_html("主要競爭對手包括台達電（2308.TW）與 https://example.com")

    assert 'href="https://tw.stock.yahoo.com/quote/2308.TW"' in html
    assert 'href="http://2308.TW"' not in html
    assert 'href="https://example.com"' in html
