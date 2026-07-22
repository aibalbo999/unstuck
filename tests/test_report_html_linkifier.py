import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


from reporting.html_linkifier import linkify_sanitized_html  # noqa: E402


def test_html_linkifier_links_urls_and_tw_tickers_with_trailing_punctuation_outside_anchor():
    html = linkify_sanitized_html("觀察 2330.TW 與 https://example.com/report)。")

    assert 'href="https://tw.stock.yahoo.com/quote/2330.TW"' in html
    assert '>2330.TW</a>' in html
    assert 'href="https://example.com/report"' in html
    assert ">https://example.com/report</a>)。" in html


def test_html_linkifier_normalizes_existing_anchor_and_skips_code_blocks():
    html = linkify_sanitized_html(
        '<a href="http://2308.TW">台達電</a> <code>2330.TW https://example.com</code>'
    )

    assert 'href="https://tw.stock.yahoo.com/quote/2308.TW"' in html
    assert 'rel="nofollow noopener noreferrer"' in html
    assert 'target="_blank"' in html
    assert '<code>2330.TW https://example.com</code>' in html
    assert html.count('href="https://tw.stock.yahoo.com/quote/2330.TW"') == 0


def test_html_linkifier_drops_missing_token_existing_anchor_text_and_attrs():
    html = linkify_sanitized_html(
        '<a href="https://example.com" title="Infinity">NaN</a> '
        '<a href="Infinity">有效連結</a>'
    )

    assert "NaN" not in html
    assert "Infinity" not in html
    assert ">有效連結</a>" in html
    assert 'href="Infinity"' not in html
