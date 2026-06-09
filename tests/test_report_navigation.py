import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.html_renderer import generate_html_report  # noqa: E402
from report_history_service import download_report_file  # noqa: E402
from report_view_repair import repair_report_html_for_view  # noqa: E402


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


def test_report_view_repair_rebuilds_legacy_mode_b_sidebar():
    legacy_html = """
    <nav class="sidebar">
      <div class="nav-section">
        <div class="nav-section-title">分析報告</div>
        <a class="nav-item" href="#overview"><span class="nav-num">0</span>概覽總覽</a>
        <a class="nav-item" href="#section-1"><span class="nav-num">1</span>商業模式分析</a>
        <a class="nav-item" href="#section-7"><span class="nav-num">7</span>投資決策</a>
      </div>
      <div class="sidebar-footer">生成日期</div>
    </nav>
    <div id="overview"></div>
    <div class="section" id="section-11">
      <div class="section-header">
        <div class="section-num">1</div>
        <div class="section-title">總經環境</div>
      </div>
    </div>
    <div class="section" id="section-16">
      <div class="section-header">
        <div class="section-num">6</div>
        <div class="section-title">實戰交易決策</div>
      </div>
      <p>台達電（<a href="http://2308.TW">2308.TW</a>）</p>
    </div>
    """

    repaired = repair_report_html_for_view(legacy_html)

    assert 'href="#section-1"' not in repaired
    assert 'href="#section-7"' not in repaired
    assert 'href="#section-11"' in repaired
    assert 'href="#section-16"' in repaired
    assert '<span class="nav-label">實戰交易決策</span>' in repaired
    assert 'href="https://tw.stock.yahoo.com/quote/2308.TW"' in repaired


def test_downloaded_html_uses_same_view_repairs(tmp_path):
    filename = "2308_v2_report_20260608_010000.html"
    (tmp_path / filename).write_text(
        """
        <nav class="sidebar">
          <div class="nav-section">
            <div class="nav-section-title">分析報告</div>
            <a class="nav-item" href="#overview"><span class="nav-num">0</span>概覽總覽</a>
            <a class="nav-item" href="#section-7"><span class="nav-num">7</span>投資決策</a>
          </div>
          <div class="sidebar-footer">生成日期</div>
        </nav>
        <div id="overview"></div>
        <div class="section" id="section-16">
          <div class="section-header">
            <div class="section-num">6</div>
            <div class="section-title">實戰交易決策</div>
          </div>
          <p>台達電（<a href="http://2308.TW">2308.TW</a>）</p>
        </div>
        """,
        encoding="utf-8",
    )

    response = download_report_file(filename, str(tmp_path), "html")
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"attachment; filename={filename}"
    assert 'href="#section-7"' not in body
    assert 'href="#section-16"' in body
    assert 'href="https://tw.stock.yahoo.com/quote/2308.TW"' in body
