import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.html_renderer import generate_html_report  # noqa: E402


def _context_for_pipeline(pipeline_id: str, agents: tuple[int, ...]) -> dict:
    return {
        "ticker": "6282.TW",
        "company_name": "康舒",
        "pipeline_id": pipeline_id,
        "data": {
            "ticker": "6282.TW",
            "company_name": "康舒",
            "fetch_date": "2026年06月08日",
            "sector": "Technology",
            "industry": "Electronic Components",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {agent: f"## Agent {agent}\n內容。" for agent in agents},
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "3個月": "NT$50",
                "6個月": "NT$55",
                "12個月": "NT$60",
                "信心": "6/10",
            },
            "price_targets": {"熊市情境": 40, "基本情境": 55, "牛市情境": 70},
            "moat_scores": {
                "品牌影響力": 5,
                "網路效應": 4,
                "轉換成本": 5,
                "成本優勢": 6,
                "專利技術": 5,
                "整體護城河": 5,
            },
        },
        "total_time": 1,
    }


def test_report_sidebar_uses_pipeline_agent_section_ids():
    mode_a_html = generate_html_report(_context_for_pipeline("v1", (1, 2, 3, 4, 5, 6, 7)))
    mode_b_html = generate_html_report(_context_for_pipeline("v2", (11, 12, 13, 14, 15, 16)))

    for agent in range(1, 8):
        assert f'href="#section-{agent}"' in mode_a_html
    for agent in range(11, 17):
        assert f'href="#section-{agent}"' in mode_b_html

    assert 'href="#section-1"' not in mode_b_html
    assert 'href="#section-7"' not in mode_b_html
    assert '<span class="nav-label">實戰交易決策</span>' in mode_b_html
