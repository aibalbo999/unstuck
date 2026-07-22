import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


from reporting.source_audit import build_source_audit_html, build_source_audit_markdown  # noqa: E402


def test_source_audit_helper_renders_safe_html_and_markdown_rows():
    data = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "yf|finance\nTW",
                "status": "success",
                "fetched_at": "2026-06-07T00:00:00+00:00|local\nbatch",
                "duration_ms": 12,
                "record_count": 1,
                "cache_hit": True,
                "stale": False,
                "message": "<script>alert(1)</script>ok|done\nline",
            }
        ]
    }

    html = build_source_audit_html(data)
    markdown = build_source_audit_markdown(data)
    rendered = html + markdown

    assert "來源審計" in rendered
    assert 'class="source-audit-table"' in html
    assert "市場資料" in rendered
    assert "yf/finance TW" in markdown
    assert "ok/done line" in markdown
    assert "<script" not in rendered.lower()
    assert "alert(1)" not in rendered


def test_source_audit_helper_renders_empty_state_without_entries():
    html = build_source_audit_html({})
    markdown = build_source_audit_markdown({})

    assert "source-audit-empty" in html
    assert "本報告未記錄 source_audit" in html
    assert "| 未記錄 | N/A | 未記錄 | N/A | N/A | 0 | N/A | N/A | 舊報告未保存 source_audit。 |" in markdown


def test_source_audit_helper_drops_non_finite_text_fields():
    data = {
        "source_audit": [
            {
                "source": float("nan"),
                "provider": Decimal("Infinity"),
                "status": Decimal("-Infinity"),
                "fetched_at": float("inf"),
                "duration_ms": 12,
                "record_count": 1,
                "cache_hit": False,
                "stale": False,
                "message": Decimal("NaN"),
            }
        ]
    }

    html = build_source_audit_html(data)
    markdown = build_source_audit_markdown(data)
    rendered = html + markdown

    assert "unknown" in rendered
    assert "N/A" in rendered
    assert "nan" not in rendered.lower()
    assert "infinity" not in rendered.lower()


def test_source_audit_helper_drops_non_finite_string_text_fields():
    data = {
        "source_audit": [
            {
                "source": "NaN",
                "provider": "Infinity",
                "status": "-Infinity",
                "fetched_at": "NaN",
                "duration_ms": 12,
                "record_count": 1,
                "cache_hit": False,
                "stale": False,
                "message": "N/A",
                "error_kind": "Infinity",
            }
        ]
    }

    html = build_source_audit_html(data)
    markdown = build_source_audit_markdown(data)
    rendered = html + markdown

    assert "來源審計" in rendered
    assert "N/A" in rendered
    assert "nan" not in rendered.lower()
    assert "infinity" not in rendered.lower()
