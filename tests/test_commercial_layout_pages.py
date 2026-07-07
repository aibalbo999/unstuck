import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"
COMMERCIAL_DIR = STATIC_DIR / "commercial"


def css_rule_body(css: str, selector: str) -> str | None:
    body = None
    for match in re.finditer(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", css, re.S):
        selectors = [item.strip() for item in match.group("selectors").split(",")]
        if selector in selectors:
            body = match.group("body")
    return body


def test_three_commercial_layout_pages_exist_in_order():
    expected_pages = [
        ("research-workbench.html", "research-workbench", "研究工作台", "追蹤表決策中樞"),
        ("stock-detail.html", "stock-detail", "單股研究", "單股快照研究"),
        ("portfolio-dashboard.html", "portfolio-dashboard", "組合健檢", "組合健檢中心"),
    ]

    for filename, page_id, marker, heading in expected_pages:
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert f'data-commercial-page="{page_id}"' in html
        assert marker in html
        assert heading in html
        assert f"<h1" in html and f">{marker}</h1>" in html
        assert "/static/commercial/commercial_pages.css" in html
        assert "/static/commercial/commercial_pages.js" in html
        assert 'href="/static/commercial/research-workbench.html"' in html
        assert 'href="/static/commercial/stock-detail.html"' in html
        assert 'href="/static/commercial/portfolio-dashboard.html"' in html


def test_commercial_layout_pages_keep_direct_navigation_back_to_main_dashboard():
    for filename in (
        "research-workbench.html",
        "stock-detail.html",
        "portfolio-dashboard.html",
    ):
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")

        assert '<a class="commercial-brand" href="/" aria-label="回到主頁">' in html
        assert '<a href="/">主頁</a>' in html


def test_commercial_mobile_topbar_stays_compact_like_trading_tools():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    topbar = re.search(r"\.commercial-topbar \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert topbar is not None
    assert "display: grid;" in topbar.group("body")
    assert "grid-template-columns: minmax(0, 1fr);" in topbar.group("body")
    assert "gap: 6px;" in topbar.group("body")
    assert "padding: 8px 10px 6px;" in topbar.group("body")

    brand_caption = re.search(r"\.commercial-brand span \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert brand_caption is not None
    assert "display: none;" in brand_caption.group("body")

    nav = re.search(r"\.commercial-nav \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert nav is not None
    assert "display: grid;" in nav.group("body")
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in nav.group("body")
    assert "width: 100%;" in nav.group("body")
    assert "overflow: visible;" in nav.group("body")

    nav_link = re.search(r"\.commercial-nav a \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert nav_link is not None
    assert "min-width: 0;" in nav_link.group("body")
    assert "min-height: 44px;" in nav_link.group("body")
    assert "white-space: normal;" in nav_link.group("body")
    assert "line-height: 1.15;" in nav_link.group("body")


def test_commercial_mobile_first_screen_prioritizes_snapshot_and_workspace_like_app_dashboards():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    for selector in (
        ".commercial-shell > .commercial-primary-answer-strip",
        ".commercial-shell > .commercial-primary-compare-lens",
        ".commercial-shell > .commercial-primary-customize-strip",
    ):
        compact_section = css_rule_body(mobile_css, selector)
        assert compact_section is not None
        assert "display: none;" in compact_section

    jump_deck = css_rule_body(mobile_css, ".commercial-shell > .commercial-jump-deck")
    assert jump_deck is not None
    assert "display: flex;" in jump_deck
    assert "overflow-x: auto;" in jump_deck

    snapshot = css_rule_body(mobile_css, ".commercial-shell > .commercial-primary-snapshot-dock")
    assert snapshot is not None
    assert "margin: 6px 12px 0;" in snapshot
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in snapshot
    assert "gap: 6px;" in snapshot
    assert "padding: 6px;" in snapshot

    snapshot_actions = css_rule_body(
        mobile_css,
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-actions",
    )
    assert snapshot_actions is not None
    assert "display: none;" in snapshot_actions


def test_commercial_pages_use_compact_tool_title_bars_instead_of_prototype_heroes():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    base_css = css.split("@media", 1)[0]

    hero = css_rule_body(base_css, ".commercial-hero")
    assert hero is not None
    assert "display: grid;" in hero
    assert "grid-template-columns: minmax(0, 1fr) auto;" in hero
    assert "align-items: center;" in hero
    assert "min-height: 44px;" in hero
    assert "margin-bottom: 8px;" in hero
    assert "border: 1px solid rgba(148, 163, 184, 0.16);" in hero
    assert "padding: 8px 10px;" in hero

    hero_title = css_rule_body(base_css, ".commercial-hero h1")
    assert hero_title is not None
    assert "font-size: clamp(18px, 1.6vw, 24px);" in hero_title
    assert "line-height: 1.12;" in hero_title

    hero_copy = css_rule_body(base_css, ".commercial-hero p")
    assert hero_copy is not None
    assert "display: none;" in hero_copy

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_hero = css_rule_body(mobile_css, ".commercial-hero")
    assert mobile_hero is not None
    assert "margin-bottom: 6px;" in mobile_hero
    assert "padding: 7px 8px;" in mobile_hero


def test_commercial_desktop_first_screen_uses_competitor_dense_summary_row():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (min-width: 1180px)" in css
    desktop_css = css.split("@media (min-width: 1180px)", 1)[1].split("@media (max-width: 920px)", 1)[0]

    shell = re.search(r"\.commercial-shell \{(?P<body>.*?)\n  \}", desktop_css, re.S)
    assert shell is not None
    assert "grid-template-columns: 18px repeat(4, minmax(0, 1fr)) 226px;" in shell.group("body")
    assert "grid-template-rows: auto auto auto auto minmax(0, 1fr);" in shell.group("body")
    assert "column-gap: 10px;" in shell.group("body")
    assert "row-gap: 12px;" in shell.group("body")

    expected_summary_columns = {
        ".commercial-shell > .commercial-primary-snapshot-dock": "grid-column: 2;",
        ".commercial-shell > .commercial-primary-answer-strip": "grid-column: 3;",
        ".commercial-shell > .commercial-primary-compare-lens": "grid-column: 4;",
        ".commercial-shell > .commercial-primary-customize-strip": "grid-column: 5;",
    }
    for selector, expected_column in expected_summary_columns.items():
        summary_card = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", desktop_css, re.S)
        assert summary_card is not None
        assert "grid-row: 2;" in summary_card.group("body")
        assert expected_column in summary_card.group("body")
        assert "margin: 0;" in summary_card.group("body")
        assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in summary_card.group("body")
        assert "overflow: visible;" in summary_card.group("body")

    for selector in (
        ".commercial-shell > .commercial-jump-deck",
        ".commercial-shell > .commercial-workspace-chrome",
        ".commercial-main",
    ):
        row = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", desktop_css, re.S)
        assert row is not None
        assert "grid-column: 2 / 6;" in row.group("body")


def test_commercial_desktop_first_screen_avoids_nested_summary_scroll_regions():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    desktop_css = css.split("@media (min-width: 1180px)", 1)[1].split("@media (max-width: 920px)", 1)[0]

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock",
        ".commercial-shell > .commercial-primary-answer-strip",
        ".commercial-shell > .commercial-primary-compare-lens",
        ".commercial-shell > .commercial-primary-customize-strip",
    ):
        summary_card = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", desktop_css, re.S)
        assert summary_card is not None
        assert "overflow: auto;" not in summary_card.group("body")
        assert "max-height:" not in summary_card.group("body")
        assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in summary_card.group("body")

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-metrics",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-grid",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-grid",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-grid",
    ):
        inner_grid = css_rule_body(desktop_css, selector)
        assert inner_grid is not None
        assert "grid-column: 1 / -1;" in inner_grid
        assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in inner_grid


def test_commercial_desktop_first_screen_keeps_summary_cards_decision_dense():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    desktop_css = css.split("@media (min-width: 1180px)", 1)[1].split("@media (max-width: 920px)", 1)[0]

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-actions",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-actions",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-actions",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-actions",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-monitor-rail",
    ):
        compact_action = css_rule_body(desktop_css, selector)
        assert compact_action is not None
        assert "display: none;" in compact_action

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-metric",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-item",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-metric",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-item",
    ):
        compact_item = css_rule_body(desktop_css, selector)
        assert compact_item is not None
        assert "min-height: 44px;" in compact_item
        assert "padding: 6px;" in compact_item


def test_commercial_shell_uses_zero_min_grid_track_to_prevent_mobile_overflow():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    shell = re.search(r"\.commercial-shell \{(?P<body>.*?)\n\}", css, re.S)
    assert shell is not None
    assert "grid-template-columns: minmax(0, 1fr);" in shell.group("body")
    assert "overflow-x: clip;" in shell.group("body")

    main = re.search(r"\.commercial-main \{(?P<body>.*?)\n\}", css, re.S)
    assert main is not None
    assert "max-width: 100%;" in main.group("body")
    assert "min-width: 0;" in main.group("body")


def test_commercial_layout_pages_bust_static_asset_cache_for_latest_frontend():
    for filename in ("research-workbench.html", "stock-detail.html", "portfolio-dashboard.html"):
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert "/static/commercial/commercial_pages.css?v=20260705-commercial-pro213" in html
        assert "/static/commercial/commercial_pages.js?v=20260705-commercial-pro213" in html
        assert "20260705-commercial-pro212" not in html
        assert "20260705-commercial-pro211" not in html
        assert "20260705-commercial-pro210" not in html
        assert "20260705-commercial-pro209" not in html
        assert "20260705-commercial-pro205" not in html
        assert "20260705-commercial-pro203" not in html
        assert "20260705-commercial-pro202" not in html
        assert "20260705-commercial-pro201" not in html
        assert "20260705-commercial-pro200" not in html
        assert "20260705-commercial-pro199" not in html
        assert "20260705-commercial-pro198" not in html
        assert "20260705-commercial-pro197" not in html
        assert "20260705-commercial-pro196" not in html
        assert "20260705-commercial-pro195" not in html
        assert "20260705-commercial-pro194" not in html
        assert "20260705-commercial-pro193" not in html
        assert "20260705-commercial-pro192" not in html
        assert "20260705-commercial-pro191" not in html
        assert "20260705-commercial-pro190" not in html
        assert "20260705-commercial-pro189" not in html
        assert "20260705-commercial-pro188" not in html
        assert "20260705-commercial-pro187" not in html
        assert "20260705-commercial-pro186" not in html
        assert "20260705-commercial-pro179" not in html
        assert "20260705-commercial-pro178" not in html
        assert "20260705-commercial-pro177" not in html
        assert "20260705-commercial-pro176" not in html
        assert "20260705-commercial-pro175" not in html
        assert "20260705-commercial-pro172" not in html
        assert "20260705-commercial-pro169" not in html
        assert "20260705-commercial-pro168" not in html
        assert "20260705-commercial-pro167" not in html
        assert "20260705-commercial-pro166" not in html
        assert "20260705-commercial-pro165" not in html
        assert "20260705-commercial-pro164" not in html
        assert "20260705-commercial-pro163" not in html
        assert "20260705-commercial-pro162" not in html
        assert "20260705-commercial-pro161" not in html
        assert "20260705-commercial-pro160" not in html
        assert "20260705-commercial-pro159" not in html
        assert "20260705-commercial-pro158" not in html
        assert "20260705-commercial-pro157" not in html
        assert "20260705-commercial-pro156" not in html
        assert "20260705-commercial-pro155" not in html
        assert "20260705-commercial-pro149" not in html
        assert "20260705-commercial-pro148" not in html
        assert "20260705-commercial-pro147" not in html
        assert "20260705-commercial-pro146" not in html
        assert "20260705-commercial-pro145" not in html
        assert "20260705-commercial-pro144" not in html
        assert "20260705-commercial-pro143" not in html
        assert "20260705-commercial-pro142" not in html
        assert "20260705-commercial-pro141" not in html
        assert "20260705-commercial-pro140" not in html
        assert "20260705-commercial-pro139" not in html
        assert "20260705-commercial-pro138" not in html
        assert "20260705-commercial-pro137" not in html
        assert "20260705-commercial-pro136" not in html
        assert "20260705-commercial-pro135" not in html
        assert "20260705-commercial-pro134" not in html
        assert "20260705-commercial-pro133" not in html
        assert "20260705-commercial-pro132" not in html
        assert "20260705-commercial-pro131" not in html
        assert "20260705-commercial-pro130" not in html
        assert "20260705-commercial-pro129" not in html
        assert "20260705-commercial-pro128" not in html
        assert "20260705-commercial-pro127" not in html
        assert "20260705-commercial-pro126" not in html
        assert "20260705-commercial-pro125" not in html
        assert "20260705-commercial-pro124" not in html
        assert "20260705-commercial-pro123" not in html
        assert "20260705-commercial-pro122" not in html
        assert "20260705-commercial-pro121" not in html
        assert "20260705-commercial-pro120" not in html
        assert "20260705-commercial-pro119" not in html
        assert "20260705-commercial-pro118" not in html
        assert "20260705-commercial-pro117" not in html
        assert "20260705-commercial-pro116" not in html
        assert "20260705-commercial-pro115" not in html
        assert "20260705-commercial-pro114" not in html
        assert "20260705-commercial-pro113" not in html
        assert "20260705-commercial-pro112" not in html
        assert "20260705-commercial-pro111" not in html
        assert "20260705-commercial-pro110" not in html
        assert "20260705-commercial-pro109" not in html
        assert "20260705-commercial-pro108" not in html
        assert "20260705-commercial-pro107" not in html
        assert "20260705-commercial-pro106" not in html
        assert "20260705-commercial-pro105" not in html
        assert "20260705-commercial-pro104" not in html
        assert "20260705-commercial-pro103" not in html
        assert "20260705-commercial-pro102" not in html
        assert "20260705-commercial-pro101" not in html
        assert "20260705-commercial-pro100" not in html
        assert "20260705-commercial-pro99" not in html
        assert "20260705-commercial-pro98" not in html
        assert "20260705-commercial-pro97" not in html
        assert "20260705-commercial-pro96" not in html
        assert "20260705-commercial-pro95" not in html
        assert "20260705-commercial-pro94" not in html
        assert "20260705-commercial-pro93" not in html
        assert "20260705-commercial-pro92" not in html
        assert "20260705-commercial-pro91" not in html
        assert "20260705-commercial-pro90" not in html
        assert "20260705-commercial-pro89" not in html
        assert "20260705-commercial-pro88" not in html
        assert "20260705-commercial-pro87" not in html
        assert "20260705-commercial-pro86" not in html
        assert "20260705-commercial-pro85" not in html
        assert "20260705-commercial-pro84" not in html
        assert "20260705-commercial-pro83" not in html
        assert "20260705-commercial-pro82" not in html
        assert "20260705-commercial-pro81" not in html
        assert "20260705-commercial-pro80" not in html
        assert "20260705-commercial-pro79" not in html
        assert "20260705-commercial-pro78" not in html
        assert "20260705-commercial-pro77" not in html


def test_commercial_pages_place_page_specific_core_surfaces_immediately_after_hero():
    surfaces = {
        "research-workbench.html": (
            "commercial-workbench-core-surface",
            "commercial-workbench-decision-radar",
            "追蹤表核心資料",
        ),
        "stock-detail.html": (
            "commercial-stock-core-surface",
            "commercial-stock-decision-radar",
            "單股快照核心資料",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-core-surface",
            "commercial-portfolio-decision-radar",
            "組合健康核心資料",
        ),
    }

    for filename, (surface_id, radar_id, aria_label) in surfaces.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{surface_id}"') == 1
        assert f'id="{surface_id}" class="commercial-core-surface"' in html
        assert f'aria-label="{aria_label}"' in html
        assert (
            html.index('class="commercial-hero"')
            < html.index(f'id="{surface_id}"')
            < html.index(f'id="{radar_id}"')
            < html.index('id="commercial-global-context"')
        )
        for other_id, *_ in [value for key, value in surfaces.items() if key != filename]:
            assert f'id="{other_id}"' not in html


def test_commercial_pages_place_page_specific_view_rails_between_core_and_radar():
    rails = {
        "research-workbench.html": (
            "commercial-workbench-core-surface",
            "commercial-workbench-view-rail",
            "commercial-workbench-decision-radar",
            "追蹤表視角切換",
        ),
        "stock-detail.html": (
            "commercial-stock-core-surface",
            "commercial-stock-view-rail",
            "commercial-stock-decision-radar",
            "單股研究視角切換",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-core-surface",
            "commercial-portfolio-view-rail",
            "commercial-portfolio-decision-radar",
            "組合健檢視角切換",
        ),
    }

    for filename, (core_id, rail_id, radar_id, aria_label) in rails.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{rail_id}"') == 1
        assert f'id="{rail_id}" class="commercial-view-rail"' in html
        assert f'aria-label="{aria_label}"' in html
        assert (
            html.index(f'id="{core_id}"')
            < html.index(f'id="{rail_id}"')
            < html.index(f'id="{radar_id}"')
            < html.index('id="commercial-global-context"')
        )
        for _, other_rail_id, *_ in [value for key, value in rails.items() if key != filename]:
            assert f'id="{other_rail_id}"' not in html


def test_commercial_pages_place_page_specific_signal_tapes_between_view_rail_and_radar():
    tapes = {
        "research-workbench.html": (
            "commercial-workbench-core-surface",
            "commercial-workbench-view-rail",
            "commercial-workbench-signal-tape",
            "commercial-workbench-decision-radar",
            "追蹤表即時訊號",
        ),
        "stock-detail.html": (
            "commercial-stock-core-surface",
            "commercial-stock-view-rail",
            "commercial-stock-signal-tape",
            "commercial-stock-decision-radar",
            "單股即時訊號",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-core-surface",
            "commercial-portfolio-view-rail",
            "commercial-portfolio-signal-tape",
            "commercial-portfolio-decision-radar",
            "組合即時訊號",
        ),
    }

    for filename, (core_id, rail_id, tape_id, radar_id, aria_label) in tapes.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{tape_id}"') == 1
        assert f'id="{tape_id}" class="commercial-signal-tape"' in html
        assert f'aria-label="{aria_label}"' in html
        assert (
            html.index(f'id="{core_id}"')
            < html.index(f'id="{rail_id}"')
            < html.index(f'id="{tape_id}"')
            < html.index(f'id="{radar_id}"')
            < html.index('id="commercial-global-context"')
        )
        for _, _, other_tape_id, *_ in [value for key, value in tapes.items() if key != filename]:
            assert f'id="{other_tape_id}"' not in html


def test_commercial_pages_place_page_specific_focus_docks_between_signal_tape_and_radar():
    docks = {
        "research-workbench.html": (
            "commercial-workbench-signal-tape",
            "commercial-workbench-focus-dock",
            "commercial-workbench-decision-radar",
            "追蹤表股票快照焦點",
        ),
        "stock-detail.html": (
            "commercial-stock-signal-tape",
            "commercial-stock-focus-dock",
            "commercial-stock-decision-radar",
            "單股研究焦點",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-signal-tape",
            "commercial-portfolio-focus-dock",
            "commercial-portfolio-decision-radar",
            "組合健康焦點",
        ),
    }

    for filename, (signal_id, dock_id, radar_id, aria_label) in docks.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{dock_id}"') == 1
        assert f'id="{dock_id}" class="commercial-focus-dock"' in html
        assert f'aria-label="{aria_label}"' in html
        assert (
            html.index(f'id="{signal_id}"')
            < html.index(f'id="{dock_id}"')
            < html.index(f'id="{radar_id}"')
            < html.index('id="commercial-global-context"')
        )
        for _, other_dock_id, *_ in [value for key, value in docks.items() if key != filename]:
            assert f'id="{other_dock_id}"' not in html


def test_commercial_pages_place_page_specific_market_coverage_between_focus_dock_and_radar():
    coverage_sections = {
        "research-workbench.html": (
            "commercial-workbench-focus-dock",
            "commercial-workbench-market-coverage",
            "commercial-workbench-decision-radar",
            "追蹤表競品需求覆蓋",
        ),
        "stock-detail.html": (
            "commercial-stock-focus-dock",
            "commercial-stock-market-coverage",
            "commercial-stock-decision-radar",
            "單股資訊覆蓋",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-focus-dock",
            "commercial-portfolio-market-coverage",
            "commercial-portfolio-decision-radar",
            "組合健檢覆蓋",
        ),
    }

    for filename, (dock_id, coverage_id, radar_id, aria_label) in coverage_sections.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{coverage_id}"') == 1
        assert f'id="{coverage_id}" class="commercial-market-coverage"' in html
        assert f'aria-label="{aria_label}"' in html
        assert (
            html.index(f'id="{dock_id}"')
            < html.index(f'id="{coverage_id}"')
            < html.index(f'id="{radar_id}"')
            < html.index('id="commercial-global-context"')
        )
        for _, other_coverage_id, *_ in [value for key, value in coverage_sections.items() if key != filename]:
            assert f'id="{other_coverage_id}"' not in html


def test_market_coverage_decks_render_page_specific_competitor_requirements():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-market-coverage",
        ".commercial-market-coverage-copy",
        ".commercial-market-coverage-grid",
        ".commercial-market-coverage-item",
        ".commercial-market-coverage-item.is-positive",
        ".commercial-market-coverage-item.is-warning",
        ".commercial-market-coverage-item.is-muted",
        ".commercial-market-coverage-actions",
        ".commercial-market-coverage-action",
        ".commercial-market-coverage-action.is-primary",
        ".commercial-market-coverage-status",
    ):
        assert selector in css

    for function_name in (
        "function commercialMarketCoverageItem(label, status, detail, target, tone = '')",
        "function commercialMarketCoverageAction(label, target, primary = false)",
        "function commercialMarketCoverageSummary(config)",
        "function renderCommercialMarketCoverage(root, config)",
        "function bindCommercialMarketCoverage(root)",
        "function workbenchMarketCoverageConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockMarketCoverageConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioMarketCoverageConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchMarketCoverage(root, rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function renderStockMarketCoverage(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioMarketCoverage(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "資訊覆蓋",
        "追蹤表覆蓋",
        "單股研究覆蓋",
        "投組健康覆蓋",
        "可點追蹤表",
        "進階欄位",
        "追蹤表新聞",
        "市場摘要",
        "主要統計",
        "法人/ETF 持有",
        "投組警示",
        "券商同步",
        "績效追蹤",
        "再平衡計畫",
        "未覆蓋資料",
    ):
        assert label in js

    for data_attr in (
        "data-commercial-market-coverage-target",
        "data-commercial-market-coverage-copy",
    ):
        assert data_attr in js

    assert "renderWorkbenchMarketCoverage(document.getElementById('commercial-workbench-market-coverage')" in js
    assert "renderStockMarketCoverage(document.getElementById('commercial-stock-market-coverage')" in js
    assert "renderPortfolioMarketCoverage(document.getElementById('commercial-portfolio-market-coverage')" in js
    assert "bindCommercialMarketCoverage(document.getElementById('commercial-workbench-market-coverage'))" in js
    assert "bindCommercialMarketCoverage(document.getElementById('commercial-stock-market-coverage'))" in js
    assert "bindCommercialMarketCoverage(document.getElementById('commercial-portfolio-market-coverage'))" in js


def test_market_coverage_decks_stay_compact_touch_friendly_on_mobile():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    deck = re.search(r"\.commercial-market-coverage \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert deck is not None
    assert "grid-template-columns: 1fr;" in deck.group("body")
    assert "gap: 8px;" in deck.group("body")
    assert "padding: 8px;" in deck.group("body")

    copy = re.search(r"\.commercial-market-coverage-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert copy is not None
    assert "display: grid;" in copy.group("body")
    assert "min-height: 46px;" in copy.group("body")
    assert "padding: 8px;" in copy.group("body")

    grid = re.search(r"\.commercial-market-coverage-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert grid is not None
    assert "display: grid;" in grid.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in grid.group("body")
    assert "overflow-x: visible;" in grid.group("body")
    assert "padding-bottom: 0;" in grid.group("body")

    item = re.search(r"\.commercial-market-coverage-item \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert item is not None
    assert "width: 100%;" in item.group("body")
    assert "min-width: 0;" in item.group("body")
    assert "min-height: 44px;" in item.group("body")

    action = re.search(r"\.commercial-market-coverage-action \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert action is not None
    assert "width: 100%;" in action.group("body")
    assert "min-width: 0;" in action.group("body")
    assert "min-height: 44px;" in action.group("body")
    assert "white-space: normal;" in action.group("body")


def test_market_coverage_decks_use_compact_rail_on_tablet_widths():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 920px)" in css
    tablet_css = css.split("@media (max-width: 920px)", 1)[1].split("@media (max-width: 560px)", 1)[0]

    deck = re.search(r"\.commercial-market-coverage \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert deck is not None
    assert "grid-template-columns: minmax(0, 1fr);" in deck.group("body")
    assert "overflow-x: clip;" in deck.group("body")

    copy = re.search(r"\.commercial-market-coverage-copy \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert copy is not None
    assert "display: none;" in copy.group("body")

    grid = re.search(r"\.commercial-market-coverage-grid \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert grid is not None
    assert "display: flex;" in grid.group("body")
    assert "overflow-x: auto;" in grid.group("body")

    item = re.search(r"\.commercial-market-coverage-item \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert item is not None
    assert "flex: 0 0 168px;" in item.group("body")
    assert "min-height: 44px;" in item.group("body")


def test_focus_docks_render_competitor_grade_snapshot_context_for_each_page():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-focus-dock",
        ".commercial-focus-dock-copy",
        ".commercial-focus-dock-metrics",
        ".commercial-focus-dock-metric",
        ".commercial-focus-dock-metric.is-positive",
        ".commercial-focus-dock-metric.is-warning",
        ".commercial-focus-dock-actions",
        ".commercial-focus-dock-action",
        ".commercial-focus-dock-action.is-primary",
        ".commercial-focus-dock-status",
    ):
        assert selector in css

    for function_name in (
        "function commercialFocusDockMetric(label, value, detail, tone = '')",
        "function commercialFocusDockAction(id, label, target, primary = false, href = '')",
        "function commercialFocusDockSummary(config)",
        "function renderCommercialFocusDock(root, config)",
        "function bindCommercialFocusDock(root)",
        "function workbenchFocusDockConfig(row, snapshot, rows, activeTicker, activeView, currentFilter)",
        "function stockFocusDockConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioFocusDockConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchFocusDock(root, row, snapshot, rows, activeTicker, activeView, currentFilter)",
        "function renderStockFocusDock(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioFocusDock(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "快照焦點",
        "追蹤表快照台",
        "單股研究焦點",
        "投組風險焦點",
        "選取股票",
        "報價",
        "目標上行",
        "下一事件",
        "投組健康",
        "風險旗標",
        "最大權重",
        "再平衡模型",
        "打開快照",
        "打開個股頁",
        "打開再平衡",
        "打開健檢",
        "釘選快照",
        "複製焦點",
    ):
        assert label in js

    workbench_focus = re.search(
        r"function workbenchFocusDockConfig\(row, snapshot, rows, activeTicker, activeView, currentFilter\) \{(?P<body>.*?)\n    function stockFocusDockConfig",
        js,
        re.S,
    )
    assert workbench_focus is not None
    assert "commercialFocusDockMetric('目標上行'" in workbench_focus.group("body")
    assert "commercialFocusDockMetric('下一事件'" in workbench_focus.group("body")

    stock_focus = re.search(
        r"function stockFocusDockConfig\(snapshot, currentTab, activeScenario, activeCoverage\) \{(?P<body>.*?)\n    function portfolioFocusDockConfig",
        js,
        re.S,
    )
    assert stock_focus is not None
    assert "commercialFocusDockMetric('目標上行'" in stock_focus.group("body")
    assert "commercialFocusDockMetric('下一事件'" in stock_focus.group("body")

    portfolio_focus = re.search(
        r"function portfolioFocusDockConfig\(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel\) \{(?P<body>.*?)\n    function renderWorkbenchFocusDock",
        js,
        re.S,
    )
    assert portfolio_focus is not None
    portfolio_focus_body = portfolio_focus.group("body")
    for portfolio_label in (
        "commercialFocusDockMetric('風險旗標'",
        "commercialFocusDockMetric('最大權重'",
        "commercialFocusDockMetric('再平衡模型'",
        "commercialFocusDockAction('open-health', '打開健檢'",
    ):
        assert portfolio_label in portfolio_focus_body
    assert "commercialFocusDockMetric('目標上行'" not in portfolio_focus_body
    assert "commercialFocusDockMetric('下一事件'" not in portfolio_focus_body

    visible_focus_layer = "\n".join(
        [
            workbench_focus.group("body"),
            stock_focus.group("body"),
            portfolio_focus_body,
            re.search(
                r"function renderCommercialFocusDock\(root, config\) \{(?P<body>.*?)\n    function bindCommercialFocusDock",
                js,
                re.S,
            ).group("body"),
            re.search(
                r"function bindCommercialFocusDock\(root\) \{(?P<body>.*?)\n    function workbenchFocusDockConfig",
                js,
                re.S,
            ).group("body"),
        ]
    )
    for legacy_label in (
        "Focus Dock",
        "Snapshot Dock",
        "Research Focus",
        "Portfolio Focus",
        "Selected Symbol",
        "Target Upside",
        "Next Event",
        "Open Snapshot",
        "Open Stock Page",
        "Open Rebalance",
        "Open Health",
        "Pin Snapshot",
        "Copy Focus",
        "Focus copied",
        "Snapshot pinned",
    ):
        assert legacy_label not in visible_focus_layer

    for data_attr in (
        "data-commercial-focus-target",
        "data-commercial-focus-action",
        "data-commercial-focus-copy",
        "data-commercial-focus-href",
    ):
        assert data_attr in js

    assert "renderWorkbenchFocusDock(document.getElementById('commercial-workbench-focus-dock')" in js
    assert "renderStockFocusDock(document.getElementById('commercial-stock-focus-dock')" in js
    assert "renderPortfolioFocusDock(document.getElementById('commercial-portfolio-focus-dock')" in js
    assert "bindCommercialFocusDock(document.getElementById('commercial-workbench-focus-dock'))" in js
    assert "bindCommercialFocusDock(document.getElementById('commercial-stock-focus-dock'))" in js
    assert "bindCommercialFocusDock(document.getElementById('commercial-portfolio-focus-dock'))" in js


def test_focus_docks_add_competitor_grade_visual_sparklines_above_the_fold():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-focus-dock-sparkline",
        ".commercial-focus-dock-sparkline.is-positive",
        ".commercial-focus-dock-sparkline.is-warning",
        ".commercial-focus-dock-sparkline svg",
        ".commercial-focus-dock-sparkline polyline",
        ".commercial-focus-dock-sparkline span",
        ".commercial-focus-dock-sparkline strong",
    ):
        assert selector in css

    for function_name in (
        "function commercialFocusDockSparkline(label, value, detail, points, tone = '')",
        "function commercialFocusDockSparklineDisplayLabel(label)",
        "function commercialSparklinePoints(points, width = 96, height = 30)",
        "function commercialFocusDockSparklineAria(chart)",
    ):
        assert function_name in js

    for label in (
        "趨勢脈搏",
        "追蹤表脈搏",
        "報價脈搏",
        "投組脈搏",
    ):
        assert label in js

    assert "const chart = config?.chart;" in js
    assert "displayLabel: commercialFocusDockSparklineDisplayLabel(label)" in js
    assert "commercial-focus-dock-sparkline" in js
    assert "aria-label=\"${escapeHtml(commercialFocusDockSparklineAria(chart))}\"" in js
    assert "title=\"${escapeHtml(chart.label || '')}\"" in js
    assert "${escapeHtml(chart.displayLabel || chart.label || '趨勢脈搏')}" in js
    assert "viewBox=\"0 0 96 30\"" in js
    assert "<polyline" in js
    assert "chart: commercialFocusDockSparkline('追蹤表脈搏'" in js
    assert "chart: commercialFocusDockSparkline('報價脈搏'" in js
    assert "chart: commercialFocusDockSparkline('投組脈搏'" in js

    sparkline_detail_blocks = re.findall(r"\.commercial-focus-dock-sparkline em \{(?P<body>.*?)\n\}", css, re.S)
    assert sparkline_detail_blocks
    assert any("display: none;" in block for block in sparkline_detail_blocks)

    sparkline_label_blocks = re.findall(r"\.commercial-focus-dock-sparkline span \{(?P<body>.*?)\n\}", css, re.S)
    assert sparkline_label_blocks
    assert any("white-space: nowrap;" in block and "text-overflow: ellipsis;" in block for block in sparkline_label_blocks)

    sparkline_value = re.search(r"\.commercial-focus-dock-sparkline strong \{(?P<body>.*?)\n\}", css, re.S)
    assert sparkline_value is not None
    assert "white-space: nowrap;" in sparkline_value.group("body")

    desktop_actions = re.search(r"\.commercial-focus-dock-actions \{(?P<body>.*?)\n\}", css, re.S)
    assert desktop_actions is not None
    assert "align-self: center;" in desktop_actions.group("body")

    desktop_action = re.search(r"\.commercial-focus-dock-action \{(?P<body>.*?)\n\}", css, re.S)
    assert desktop_action is not None
    assert "max-height: 52px;" in desktop_action.group("body")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-focus-dock-sparkline" in mobile_css
    sparkline = css_rule_body(mobile_css, ".commercial-focus-dock-sparkline")
    assert sparkline is not None
    assert "width: 100%;" in sparkline
    assert "min-width: 0;" in sparkline
    assert "min-height: 44px;" in mobile_css
    sparkline_value_mobile = css_rule_body(mobile_css, ".commercial-focus-dock-sparkline strong")
    assert sparkline_value_mobile is not None
    assert "white-space: normal;" in sparkline_value_mobile
    assert "overflow-wrap: anywhere;" in sparkline_value_mobile


def test_focus_docks_stay_in_flow_to_avoid_layering_while_scanning_long_watchlists():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    dock = re.search(r"\.commercial-focus-dock \{(?P<body>.*?)\n\}", css, re.S)
    assert dock is not None
    body = dock.group("body")
    assert "order: 6;" in body
    assert "minmax(420px" in body
    assert "position: relative;" in body
    assert "position: sticky;" not in body
    assert "top: 76px;" not in body
    assert "z-index: 1;" in body
    assert "backdrop-filter: blur(14px);" in body


def test_workbench_focus_dock_updates_and_ticker_clicks_jump_to_snapshot():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    select_ticker = re.search(
        r"async function selectTicker\(ticker, rows, shouldFocusSnapshot = false\) \{(?P<body>.*?)\n    \}",
        js,
        re.S,
    )
    assert select_ticker is not None
    body = select_ticker.group("body")

    assert "const focusDockRoot = document.getElementById('commercial-workbench-focus-dock');" in body
    assert "renderWorkbenchFocusDock(focusDockRoot, selectedRow, null, sourceRows, normalized, 'decision', 'loading')" in body
    assert "renderWorkbenchFocusDock(focusDockRoot, selectedRow, snapshot, sourceRows, normalized, 'decision', 'ready')" in body
    assert "renderWorkbenchFocusDock(focusDockRoot, selectedRow, fallback, sourceRows, normalized, 'decision', 'fallback')" in body
    assert "function focusWorkbenchSnapshot()" in body
    assert "if (!shouldFocusSnapshot) return;" in body
    assert "scrollCommercialTaskTarget('commercial-workbench-detail', { behavior: 'auto' })" in body
    assert "if (shouldFocusSnapshot) focusWorkbenchSnapshot();" in body
    assert "scrollWorkbenchSnapshotIntoView(inspectorRoot || detailRoot)" not in body
    assert "scrollWorkbenchSnapshotIntoView(detailRoot)" not in body

    main = re.search(r"\.commercial-main \{(?P<body>.*?)\n\}", css, re.S)
    assert main is not None
    assert "overflow-anchor: none;" in main.group("body")


def test_focus_docks_stay_compact_touch_friendly_on_mobile():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    dock = re.search(r"\.commercial-focus-dock \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert dock is not None
    assert "grid-template-columns: 1fr;" in dock.group("body")
    assert "gap: 8px;" in dock.group("body")
    assert "padding: 8px;" in dock.group("body")

    copy = re.search(r"\.commercial-focus-dock-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert copy is not None
    assert "display: none;" in copy.group("body")

    metrics = re.search(r"\.commercial-focus-dock-metrics \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert metrics is not None
    assert "display: grid;" in metrics.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in metrics.group("body")
    assert "overflow-x: visible;" in metrics.group("body")
    assert "padding-bottom: 0;" in metrics.group("body")

    metric = re.search(r"\.commercial-focus-dock-metric \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert metric is not None
    assert "width: 100%;" in metric.group("body")
    assert "min-width: 0;" in metric.group("body")
    assert "min-height: 44px;" in metric.group("body")

    actions = re.search(r"\.commercial-focus-dock-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert actions is not None
    assert "display: grid;" in actions.group("body")
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in actions.group("body")
    assert "overflow-x: visible;" in actions.group("body")

    action = re.search(r"\.commercial-focus-dock-action \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert action is not None
    assert "width: 100%;" in action.group("body")
    assert "min-width: 0;" in action.group("body")
    assert "min-height: 44px;" in action.group("body")
    assert "white-space: normal;" in action.group("body")

    status = re.search(r"\.commercial-focus-dock-status \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert status is not None
    assert "display: none;" in status.group("body")


def test_signal_tapes_render_page_specific_alert_news_and_actionable_deltas():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-signal-tape",
        ".commercial-signal-tape-copy",
        ".commercial-signal-tape-track",
        ".commercial-signal-tape-item",
        ".commercial-signal-tape-item.is-positive",
        ".commercial-signal-tape-item.is-warning",
        ".commercial-signal-tape-actions",
        ".commercial-signal-tape-action",
        ".commercial-signal-tape-action.is-primary",
        ".commercial-signal-tape-status",
    ):
        assert selector in css

    for function_name in (
        "function commercialSignalTapeItem(id, label, value, detail, target, tone = '')",
        "function commercialSignalTapeAction(id, label, target, primary = false)",
        "function commercialSignalTapeSummary(config)",
        "function renderCommercialSignalTape(root, config)",
        "function bindCommercialSignalTape(root)",
        "function workbenchSignalTapeConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockSignalTapeConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioSignalTapeConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchSignalTape(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockSignalTape(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioSignalTape(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "訊號帶",
        "追蹤表訊號",
        "單股訊號",
        "投組訊號",
        "即時警示",
        "新聞流",
        "量化評級",
        "主動報酬",
        "投組警示",
        "曝險漂移",
        "最大持股",
        "再平衡狀態",
        "目標變化",
        "打開警示",
        "打開新聞",
        "打開再平衡",
        "複製摘要",
    ):
        assert label in js

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_signal_copy = re.search(r"\.commercial-signal-tape-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_signal_copy is not None
    assert "display: grid;" in mobile_signal_copy.group("body")
    assert "min-height: 46px;" in mobile_signal_copy.group("body")

    workbench_signal = re.search(
        r"function workbenchSignalTapeConfig\(rows, activeTicker, activeView, currentFilter\) \{(?P<body>.*?)\n    function stockSignalTapeConfig",
        js,
        re.S,
    )
    assert workbench_signal is not None
    assert "commercialSignalTapeItem('target', '目標變化'" in workbench_signal.group("body")

    stock_signal = re.search(
        r"function stockSignalTapeConfig\(snapshot, currentTab, activeScenario, activeCoverage\) \{(?P<body>.*?)\n    function portfolioSignalTapeConfig",
        js,
        re.S,
    )
    assert stock_signal is not None
    assert "commercialSignalTapeItem('target', '目標變化'" in stock_signal.group("body")

    portfolio_signal = re.search(
        r"function portfolioSignalTapeConfig\(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel\) \{(?P<body>.*?)\n    function renderWorkbenchSignalTape",
        js,
        re.S,
    )
    assert portfolio_signal is not None
    portfolio_signal_body = portfolio_signal.group("body")
    for portfolio_label in (
        "commercialSignalTapeItem('warnings', '投組警示'",
        "commercialSignalTapeItem('exposure-drift', '曝險漂移'",
        "commercialSignalTapeItem('top-weight', '最大持股'",
        "commercialSignalTapeItem('rebalance-status', '再平衡狀態'",
    ):
        assert portfolio_label in portfolio_signal_body
    assert "commercialSignalTapeItem('active-return', '主動報酬'" not in portfolio_signal_body
    assert "commercialSignalTapeItem('target', '目標變化'" not in portfolio_signal_body

    for data_attr in (
        "data-commercial-signal-target",
        "data-commercial-signal-copy",
        "data-commercial-signal-action",
    ):
        assert data_attr in js

    assert "renderWorkbenchSignalTape(document.getElementById('commercial-workbench-signal-tape')" in js
    assert "renderStockSignalTape(document.getElementById('commercial-stock-signal-tape')" in js
    assert "renderPortfolioSignalTape(document.getElementById('commercial-portfolio-signal-tape')" in js
    assert "bindCommercialSignalTape(document.getElementById('commercial-workbench-signal-tape'))" in js
    assert "bindCommercialSignalTape(document.getElementById('commercial-stock-signal-tape'))" in js
    assert "bindCommercialSignalTape(document.getElementById('commercial-portfolio-signal-tape'))" in js


def test_signal_tapes_are_compact_touch_friendly_on_mobile():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    tape = re.search(r"\.commercial-signal-tape \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert tape is not None
    assert "grid-template-columns: 1fr;" in tape.group("body")
    assert "gap: 8px;" in tape.group("body")
    assert "padding: 8px;" in tape.group("body")

    track = re.search(r"\.commercial-signal-tape-track \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert track is not None
    assert "display: grid;" in track.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in track.group("body")
    assert "overflow-x: visible;" in track.group("body")
    assert "padding-bottom: 0;" in track.group("body")

    item = re.search(r"\.commercial-signal-tape-item \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert item is not None
    assert "width: 100%;" in item.group("body")
    assert "min-width: 0;" in item.group("body")
    assert "min-height: 44px;" in item.group("body")

    actions = re.search(r"\.commercial-signal-tape-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert actions is not None
    assert "display: grid;" in actions.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in actions.group("body")
    assert "overflow-x: visible;" in actions.group("body")
    assert "padding-bottom: 0;" in actions.group("body")

    action = re.search(r"\.commercial-signal-tape-action \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert action is not None
    assert "width: 100%;" in action.group("body")
    assert "min-width: 0;" in action.group("body")
    assert "min-height: 44px;" in action.group("body")
    assert "white-space: normal;" in action.group("body")

    status = re.search(r"\.commercial-signal-tape-status \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert status is not None
    assert "display: none;" in status.group("body")


def test_commercial_pages_add_page_specific_technical_pulses_for_price_risk_workflows():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-technical-pulse",
            "commercial-workbench-signal-tape",
            "commercial-workbench-focus-dock",
            "追蹤表技術面脈搏",
        ),
        "stock-detail.html": (
            "commercial-stock-technical-pulse",
            "commercial-stock-signal-tape",
            "commercial-stock-focus-dock",
            "單股技術面摘要",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-technical-pulse",
            "commercial-portfolio-signal-tape",
            "commercial-portfolio-focus-dock",
            "組合價格風險脈搏",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for filename, (pulse_id, before_id, after_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{pulse_id}"') == 1
        assert f'id="{pulse_id}" class="commercial-technical-pulse"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{before_id}"') < html.index(f'id="{pulse_id}"') < html.index(f'id="{after_id}"')
        for other_pulse_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_pulse_id}"' not in html

    for selector in (
        ".commercial-technical-pulse",
        ".commercial-technical-pulse-copy",
        ".commercial-technical-pulse-grid",
        ".commercial-technical-pulse-metric",
        ".commercial-technical-pulse-metric.is-positive",
        ".commercial-technical-pulse-metric.is-warning",
        ".commercial-technical-pulse-actions",
        ".commercial-technical-pulse-action",
        ".commercial-technical-pulse-action.is-primary",
        ".commercial-technical-pulse-status",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-technical-pulse" in mobile_css
    assert ".commercial-technical-pulse-grid" in mobile_css
    assert ".commercial-technical-pulse-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    for function_name in (
        "function commercialTechnicalPulseMetric(id, label, value, detail, target, tone = '')",
        "function commercialTechnicalPulseSummary(config)",
        "function renderCommercialTechnicalPulse(root, config)",
        "function bindCommercialTechnicalPulse(root, scope, configFactory)",
        "function workbenchTechnicalPulseConfig(rows, activeTicker, activeView, activeColumnSet)",
        "function stockTechnicalPulseConfig(snapshot, currentTab, activeScenario, activeRange)",
        "function portfolioTechnicalPulseConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchTechnicalPulse(root, rows, activeTicker, activeView, activeColumnSet)",
        "function renderStockTechnicalPulse(root, snapshot, currentTab, activeScenario, activeRange)",
        "function renderPortfolioTechnicalPulse(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "Technical Pulse",
        "Watchlist Technical Pulse",
        "Stock Technical Pulse",
        "Portfolio Price Risk",
        "Trend Score",
        "Volume Signal",
        "Beta Trend",
        "Drawdown Risk",
        "Open Technical View",
        "Copy Technical Pulse",
        "Save Technical Pulse",
    ):
        assert label in js

    for data_attr in (
        "data-commercial-technical-target",
        "data-commercial-technical-copy",
        "data-commercial-technical-save",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`technical-pulse-${scope}`" in js
    assert "copyCommercialText(commercialTechnicalPulseSummary(config)" in js
    assert "renderWorkbenchTechnicalPulse(document.getElementById('commercial-workbench-technical-pulse')" in js
    assert "renderStockTechnicalPulse(document.getElementById('commercial-stock-technical-pulse')" in js
    assert "renderPortfolioTechnicalPulse(document.getElementById('commercial-portfolio-technical-pulse')" in js
    assert "target: 'commercial-stock-risk-lab'" in js
    assert "scrollCommercialTaskTarget(event.detail?.target || 'commercial-stock-risk-lab')" in js
    assert "scrollCommercialTaskTarget(event.detail?.target || 'commercial-stock-price-chart')" not in js


def test_technical_pulses_are_compact_touch_friendly_on_mobile():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    pulse = re.search(r"\.commercial-technical-pulse \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert pulse is not None
    assert "grid-template-columns: 1fr;" in pulse.group("body")
    assert "gap: 8px;" in pulse.group("body")
    assert "padding: 8px;" in pulse.group("body")

    grid = re.search(r"\.commercial-technical-pulse-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert grid is not None
    assert "display: grid;" in grid.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in grid.group("body")
    assert "overflow-x: visible;" in grid.group("body")
    assert "padding-bottom: 0;" in grid.group("body")

    metric = re.search(r"\.commercial-technical-pulse-metric \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert metric is not None
    assert "width: 100%;" in metric.group("body")
    assert "min-width: 0;" in metric.group("body")
    assert "min-height: 44px;" in metric.group("body")

    actions = re.search(r"\.commercial-technical-pulse-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert actions is not None
    assert "display: grid;" in actions.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in actions.group("body")
    assert "overflow-x: visible;" in actions.group("body")
    assert "padding-bottom: 0;" in actions.group("body")

    action = re.search(r"\.commercial-technical-pulse-action \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert action is not None
    assert "width: 100%;" in action.group("body")
    assert "min-width: 0;" in action.group("body")
    assert "min-height: 44px;" in action.group("body")
    assert "white-space: normal;" in action.group("body")

    status = re.search(r"\.commercial-technical-pulse-status \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert status is not None
    assert "display: none;" in status.group("body")


def test_secondary_commercial_modules_do_not_force_mobile_horizontal_scrolling():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    def block_for(selector: str) -> str | None:
        for block in re.finditer(r"(?m)^  (?P<selectors>[^{}]+?) \{(?P<body>.*?)\n  \}", mobile_css, re.S):
            selectors = [part.strip() for part in block.group("selectors").split(",")]
            if selector in selectors:
                return block.group("body")
        return None

    def assert_min_touch_height(body: str, selector: str) -> None:
        match = re.search(r"min-height:\s*(\d+)px;", body)
        assert match is not None, selector
        assert int(match.group(1)) >= 44, selector

    grid_selectors = (
        ".commercial-disclosure-grid",
        ".commercial-visual-track",
        ".commercial-report-locator .commercial-report-grid",
        ".commercial-data-beacon .commercial-data-beacon-grid",
        ".commercial-alert-beacon .commercial-alert-beacon-grid",
        ".commercial-preset-beacon .commercial-preset-beacon-grid",
        ".commercial-market-coverage-grid",
        ".commercial-decision-radar-lane-grid",
        ".commercial-decision-radar-map",
        ".commercial-today-inbox-list",
        ".commercial-today-inbox-metrics",
        ".commercial-session-watch-grid",
        ".commercial-coverage-grid",
        ".commercial-context-metrics",
    )
    for selector in grid_selectors:
        body = block_for(selector)
        assert body is not None, selector
        assert "display: grid;" in body, selector
        assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in body, selector
        assert "overflow-x: visible;" in body, selector
        assert "padding-bottom: 0;" in body, selector

    item_selectors = (
        ".commercial-disclosure-item",
        ".commercial-visual-point",
        ".commercial-report-locator .commercial-report-item",
        ".commercial-data-beacon .commercial-data-beacon-item",
        ".commercial-alert-beacon .commercial-alert-beacon-item",
        ".commercial-preset-beacon .commercial-preset-beacon-item",
        ".commercial-market-coverage-item",
        ".commercial-decision-radar-lane",
        ".commercial-decision-radar-tile",
        ".commercial-today-inbox-item",
        ".commercial-today-inbox-metric",
        ".commercial-session-watch-card",
        ".commercial-coverage-card",
        ".commercial-context-metric",
    )
    for selector in item_selectors:
        body = block_for(selector)
        assert body is not None, selector
        assert "width: 100%;" in body, selector
        assert "min-width: 0;" in body, selector
        assert_min_touch_height(body, selector)

    action_selectors = (
        ".commercial-coverage-actions",
        ".commercial-disclosure-actions",
        ".commercial-visual-actions",
        ".commercial-report-locator .commercial-report-actions",
        ".commercial-data-beacon .commercial-data-beacon-actions",
        ".commercial-alert-beacon .commercial-alert-beacon-actions",
        ".commercial-preset-beacon .commercial-preset-beacon-actions",
        ".commercial-market-coverage-actions",
        ".commercial-decision-radar-actions",
        ".commercial-today-inbox-actions",
    )
    for selector in action_selectors:
        body = block_for(selector)
        assert body is not None, selector
        assert "display: grid;" in body, selector
        assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in body, selector
        assert "overflow-x: visible;" in body, selector
        assert "padding-bottom: 0;" in body, selector

    action_item_selectors = (
        ".commercial-coverage-action",
        ".commercial-disclosure-action",
        ".commercial-visual-action",
        ".commercial-report-locator .commercial-report-action",
        ".commercial-data-beacon .commercial-data-beacon-action",
        ".commercial-alert-beacon .commercial-alert-beacon-action",
        ".commercial-preset-beacon .commercial-preset-beacon-action",
        ".commercial-market-coverage-action",
        ".commercial-decision-radar-action",
        ".commercial-today-inbox-action",
    )
    for selector in action_item_selectors:
        body = block_for(selector)
        assert body is not None, selector
        assert "width: 100%;" in body, selector
        assert "min-width: 0;" in body, selector
        assert_min_touch_height(body, selector)
        assert "white-space: normal;" in body, selector


def test_commercial_pages_add_page_specific_disclosure_digests_for_news_filings_and_transcripts():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-disclosure-digest",
            "commercial-workbench-technical-pulse",
            "commercial-workbench-focus-dock",
            "追蹤表資訊揭露摘要",
        ),
        "stock-detail.html": (
            "commercial-stock-disclosure-digest",
            "commercial-stock-technical-pulse",
            "commercial-stock-focus-dock",
            "單股新聞公告與法說摘要",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-disclosure-digest",
            "commercial-portfolio-technical-pulse",
            "commercial-portfolio-focus-dock",
            "組合持股資訊揭露摘要",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for filename, (digest_id, before_id, after_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{digest_id}"') == 1
        assert f'id="{digest_id}" class="commercial-disclosure-digest"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{before_id}"') < html.index(f'id="{digest_id}"') < html.index(f'id="{after_id}"')
        for other_digest_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_digest_id}"' not in html

    for selector in (
        ".commercial-disclosure-digest",
        ".commercial-disclosure-copy",
        ".commercial-disclosure-grid",
        ".commercial-disclosure-item",
        ".commercial-disclosure-item.is-positive",
        ".commercial-disclosure-item.is-warning",
        ".commercial-disclosure-actions",
        ".commercial-disclosure-action",
        ".commercial-disclosure-action.is-primary",
        ".commercial-disclosure-status",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-disclosure-digest" in mobile_css
    assert ".commercial-disclosure-grid" in mobile_css
    assert ".commercial-disclosure-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    for function_name in (
        "function commercialDisclosureDigestItem(id, label, value, detail, target, tone = '')",
        "function commercialDisclosureDigestSummary(config)",
        "function renderCommercialDisclosureDigest(root, config)",
        "function bindCommercialDisclosureDigest(root, scope, configFactory)",
        "function workbenchDisclosureDigestConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockDisclosureDigestConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioDisclosureDigestConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchDisclosureDigest(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockDisclosureDigest(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioDisclosureDigest(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "Disclosure Digest",
        "Watchlist Disclosure Flow",
        "Company Filing Pulse",
        "Portfolio Disclosure Risk",
        "News / Filings",
        "Transcripts",
        "Portfolio Warnings",
        "Open Disclosure Flow",
        "Copy Disclosure Digest",
        "Save Disclosure Digest",
    ):
        assert label in js

    assert "renderWorkbenchDisclosureDigest(document.getElementById('commercial-workbench-disclosure-digest')" in js
    assert "renderStockDisclosureDigest(document.getElementById('commercial-stock-disclosure-digest')" in js
    assert "renderPortfolioDisclosureDigest(document.getElementById('commercial-portfolio-disclosure-digest')" in js
    assert "bindCommercialDisclosureDigest(document.getElementById('commercial-workbench-disclosure-digest')" in js
    assert "bindCommercialDisclosureDigest(document.getElementById('commercial-stock-disclosure-digest')" in js
    assert "bindCommercialDisclosureDigest(document.getElementById('commercial-portfolio-disclosure-digest')" in js
    assert "writeCommercialMemory(`disclosure-digest-${scope}`" in js
    assert "copyCommercialText(commercialDisclosureDigestSummary(config)" in js
    assert "activeColumnSet = 'event';" in js
    assert "activeQuickAction = 'news';" in js
    assert "activeCoverage = 'filings';" in js
    assert "setStockTab('news')" in js
    assert "selectPortfolioLens('risk'" in js


def test_commercial_pages_add_page_specific_visual_pulses_for_chart_first_dashboards():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-visual-pulse",
            "commercial-workbench-disclosure-digest",
            "commercial-workbench-focus-dock",
            "追蹤表視覺脈搏",
        ),
        "stock-detail.html": (
            "commercial-stock-visual-pulse",
            "commercial-stock-disclosure-digest",
            "commercial-stock-focus-dock",
            "單股價格視覺脈搏",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-visual-pulse",
            "commercial-portfolio-disclosure-digest",
            "commercial-portfolio-focus-dock",
            "組合績效視覺脈搏",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for filename, (pulse_id, before_id, after_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{pulse_id}"') == 1
        assert f'id="{pulse_id}" class="commercial-visual-pulse"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{before_id}"') < html.index(f'id="{pulse_id}"') < html.index(f'id="{after_id}"')
        for other_pulse_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_pulse_id}"' not in html

    for selector in (
        ".commercial-visual-pulse",
        ".commercial-visual-copy",
        ".commercial-visual-stage",
        ".commercial-visual-track",
        ".commercial-visual-bar",
        ".commercial-visual-point",
        ".commercial-visual-actions",
        ".commercial-visual-action",
        ".commercial-visual-action.is-primary",
        ".commercial-visual-status",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-visual-pulse" in mobile_css
    assert ".commercial-visual-stage" in mobile_css
    assert ".commercial-visual-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    for function_name in (
        "function commercialVisualPulsePoint(id, label, value, detail, target, tone = '')",
        "function commercialVisualPulseSummary(config)",
        "function renderCommercialVisualPulse(root, config)",
        "function bindCommercialVisualPulse(root, scope, configFactory)",
        "function workbenchVisualPulseConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockVisualPulseConfig(snapshot, currentTab, activeScenario, activeRange)",
        "function portfolioVisualPulseConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchVisualPulse(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockVisualPulse(root, snapshot, currentTab, activeScenario, activeRange)",
        "function renderPortfolioVisualPulse(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "Visual Pulse",
        "Watchlist Heat Trail",
        "Price Storyline",
        "Portfolio Benchmark Trail",
        "Market Heat",
        "Sparkline",
        "Benchmark Trail",
        "Open Visual Pulse",
        "Copy Visual Pulse",
        "Save Visual Pulse",
    ):
        assert label in js

    assert "renderWorkbenchVisualPulse(document.getElementById('commercial-workbench-visual-pulse')" in js
    assert "renderStockVisualPulse(document.getElementById('commercial-stock-visual-pulse')" in js
    assert "renderPortfolioVisualPulse(document.getElementById('commercial-portfolio-visual-pulse')" in js
    assert "bindCommercialVisualPulse(document.getElementById('commercial-workbench-visual-pulse')" in js
    assert "bindCommercialVisualPulse(document.getElementById('commercial-stock-visual-pulse')" in js
    assert "bindCommercialVisualPulse(document.getElementById('commercial-portfolio-visual-pulse')" in js
    assert "writeCommercialMemory(`visual-pulse-${scope}`" in js
    assert "copyCommercialText(commercialVisualPulseSummary(config)" in js
    assert "activeQuickAction = 'scatter';" in js
    assert "setStockTab('technicals')" in js
    assert "selectPortfolioLens('risk'" in js


def test_commercial_pages_add_page_specific_report_locators_to_remove_report_hunting():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-report-locator",
            "commercial-workbench-visual-pulse",
            "commercial-workbench-focus-dock",
            "追蹤表報告定位",
        ),
        "stock-detail.html": (
            "commercial-stock-report-locator",
            "commercial-stock-visual-pulse",
            "commercial-stock-focus-dock",
            "單股 AI 報告定位",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-report-locator",
            "commercial-portfolio-visual-pulse",
            "commercial-portfolio-focus-dock",
            "組合客戶報告定位",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for filename, (locator_id, before_id, after_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{locator_id}"') == 1
        assert f'id="{locator_id}" class="commercial-report-locator"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{before_id}"') < html.index(f'id="{locator_id}"') < html.index(f'id="{after_id}"')
        for other_locator_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_locator_id}"' not in html

    for selector in (
        ".commercial-report-locator",
        ".commercial-report-copy",
        ".commercial-report-grid",
        ".commercial-report-item",
        ".commercial-report-item.is-positive",
        ".commercial-report-item.is-warning",
        ".commercial-report-actions",
        ".commercial-report-action",
        ".commercial-report-action.is-primary",
        ".commercial-report-status",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-report-locator" in mobile_css
    assert ".commercial-report-grid" in mobile_css
    assert ".commercial-report-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    mobile_report_copy = re.search(r"\.commercial-report-locator \.commercial-report-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_report_copy is not None
    assert "display: grid;" in mobile_report_copy.group("body")
    assert "min-height: 46px;" in mobile_report_copy.group("body")
    assert "padding: 8px;" in mobile_report_copy.group("body")

    for function_name in (
        "function commercialReportLocatorItem(id, label, value, detail, target, tone = '')",
        "function commercialReportLocatorSummary(config)",
        "function renderCommercialReportLocator(root, config)",
        "function bindCommercialReportLocator(root, scope, configFactory)",
        "function workbenchReportLocatorConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockReportLocatorConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioReportLocatorConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchReportLocator(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockReportLocator(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioReportLocator(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "報告定位",
        "追蹤表報告隊列",
        "單股 AI 報告定位",
        "投組客戶回顧包",
        "批次報告",
        "AI 報告",
        "客戶包",
        "打開報告定位",
        "複製報告定位",
        "儲存報告定位",
    ):
        assert label in js

    assert "renderWorkbenchReportLocator(document.getElementById('commercial-workbench-report-locator')" in js
    assert "renderStockReportLocator(document.getElementById('commercial-stock-report-locator')" in js
    assert "renderPortfolioReportLocator(document.getElementById('commercial-portfolio-report-locator')" in js
    assert "bindCommercialReportLocator(document.getElementById('commercial-workbench-report-locator')" in js
    assert "bindCommercialReportLocator(document.getElementById('commercial-stock-report-locator')" in js
    assert "bindCommercialReportLocator(document.getElementById('commercial-portfolio-report-locator')" in js
    assert "writeCommercialMemory(`report-locator-${scope}`" in js
    assert "copyCommercialText(commercialReportLocatorSummary(config)" in js
    assert "activeView = 'report';" in js
    assert "currentFilter = 'rerun';" in js
    assert "activeQuickAction = 'rows';" in js
    assert "activeCoverage = 'notes';" in js
    assert "setStockTab('report')" in js
    assert "selectPortfolioLens('contribution'" in js


def test_workbench_and_stock_pages_expose_technical_views_like_competitor_research_tools():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "technical: [" in js
    assert "['trendScore', 'Trend Score']" in js
    assert "['volumeSignal', 'Volume Signal']" in js
    assert "if (key === 'trendScore')" in js
    assert "if (key === 'volumeSignal')" in js
    assert "const stockTabs = ['overview', 'report', 'financials', 'analysts', 'technicals', 'thesis', 'ownership', 'news'];" in js
    assert "technicals: [" in js
    assert "'commercial-stock-technical-pulse'" in js
    assert "setStockTab('technicals')" in js
    assert "activeColumnSet = 'technical';" in js


def test_stock_primary_view_keeps_first_screen_technical_and_disclosure_entrances_visible():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const STOCK_ALWAYS_VISIBLE_PANELS = ['commercial-stock-technical-pulse', 'commercial-stock-disclosure-digest', 'commercial-stock-visual-pulse', 'commercial-stock-report-locator', 'commercial-stock-data-beacon', 'commercial-stock-alert-beacon', 'commercial-stock-preset-beacon', 'commercial-stock-onboarding-beacon'];" in js
    assert "function syncCommercialPrimaryViewPanels(panelMap, activeKey, alwaysVisibleIds = [])" in js
    assert "...alwaysVisibleIds" in js
    assert "syncCommercialPrimaryViewPanels(STOCK_PRIMARY_TAB_PANELS, activeTab || 'overview', STOCK_ALWAYS_VISIBLE_PANELS);" in js


def test_commercial_pages_add_page_specific_data_sync_beacons_for_source_confidence():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-data-beacon",
            "commercial-workbench-report-locator",
            "commercial-workbench-focus-dock",
            "追蹤表資料同步狀態",
        ),
        "stock-detail.html": (
            "commercial-stock-data-beacon",
            "commercial-stock-report-locator",
            "commercial-stock-focus-dock",
            "單股資料來源狀態",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-data-beacon",
            "commercial-portfolio-report-locator",
            "commercial-portfolio-focus-dock",
            "組合帳戶同步狀態",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for filename, (beacon_id, before_id, after_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{beacon_id}"') == 1
        assert f'id="{beacon_id}" class="commercial-data-beacon"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{before_id}"') < html.index(f'id="{beacon_id}"') < html.index(f'id="{after_id}"')
        for other_beacon_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_beacon_id}"' not in html

    for selector in (
        ".commercial-data-beacon",
        ".commercial-data-beacon-copy",
        ".commercial-data-beacon-grid",
        ".commercial-data-beacon-item",
        ".commercial-data-beacon-item.is-positive",
        ".commercial-data-beacon-item.is-warning",
        ".commercial-data-beacon-actions",
        ".commercial-data-beacon-action",
        ".commercial-data-beacon-action.is-primary",
        ".commercial-data-beacon-status",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-data-beacon" in mobile_css
    assert ".commercial-data-beacon-grid" in mobile_css
    assert ".commercial-data-beacon-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    mobile_data_copy = re.search(r"\.commercial-data-beacon \.commercial-data-beacon-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_data_copy is not None
    assert "display: grid;" in mobile_data_copy.group("body")
    assert "min-height: 46px;" in mobile_data_copy.group("body")
    assert "padding: 8px;" in mobile_data_copy.group("body")

    for function_name in (
        "function commercialDataBeaconItem(id, label, value, detail, target, tone = '')",
        "function commercialDataBeaconSummary(config)",
        "function renderCommercialDataBeacon(root, config)",
        "function bindCommercialDataBeacon(root, scope, configFactory)",
        "function workbenchDataBeaconConfig(rows, activeTicker, activeView, currentFilter, trackingSource)",
        "function stockDataBeaconConfig(snapshot, currentTab, activeScenario, activeCoverage, snapshotSource)",
        "function portfolioDataBeaconConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel, portfolioSource)",
        "function renderWorkbenchDataBeacon(root, rows, activeTicker, activeView, currentFilter, trackingSource)",
        "function renderStockDataBeacon(root, snapshot, currentTab, activeScenario, activeCoverage, snapshotSource)",
        "function renderPortfolioDataBeacon(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel, portfolioSource)",
    ):
        assert function_name in js

    for label in (
        "資料同步",
        "追蹤表來源健康",
        "單股來源健康",
        "投組帳戶健康",
        "決策 API",
        "報價新鮮度",
        "券商連結",
        "來源品質",
        "打開資料同步",
        "複製資料同步",
        "儲存資料同步",
    ):
        assert label in js

    assert "renderWorkbenchDataBeacon(document.getElementById('commercial-workbench-data-beacon')" in js
    assert "renderStockDataBeacon(document.getElementById('commercial-stock-data-beacon')" in js
    assert "renderPortfolioDataBeacon(document.getElementById('commercial-portfolio-data-beacon')" in js
    assert "bindCommercialDataBeacon(document.getElementById('commercial-workbench-data-beacon')" in js
    assert "bindCommercialDataBeacon(document.getElementById('commercial-stock-data-beacon')" in js
    assert "bindCommercialDataBeacon(document.getElementById('commercial-portfolio-data-beacon')" in js
    assert "writeCommercialMemory(`data-beacon-${scope}`" in js
    assert "copyCommercialText(commercialDataBeaconSummary(config)" in js
    assert "activeView = 'event';" in js
    assert "activeQuickAction = 'news';" in js
    assert "activeCoverage = 'fundamentals';" in js
    assert "selectPortfolioLens('risk'" in js


def test_commercial_pages_add_page_specific_alert_beacons_for_competitor_grade_monitoring():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-alert-beacon",
            "commercial-workbench-data-beacon",
            "commercial-workbench-focus-dock",
            "追蹤表警示監控",
        ),
        "stock-detail.html": (
            "commercial-stock-alert-beacon",
            "commercial-stock-data-beacon",
            "commercial-stock-focus-dock",
            "單股即時警示",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-alert-beacon",
            "commercial-portfolio-data-beacon",
            "commercial-portfolio-focus-dock",
            "組合風險警示",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for filename, (beacon_id, before_id, after_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{beacon_id}"') == 1
        assert f'id="{beacon_id}" class="commercial-alert-beacon"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{before_id}"') < html.index(f'id="{beacon_id}"') < html.index(f'id="{after_id}"')
        for other_beacon_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_beacon_id}"' not in html

    for selector in (
        ".commercial-alert-beacon",
        ".commercial-alert-beacon-copy",
        ".commercial-alert-beacon-grid",
        ".commercial-alert-beacon-item",
        ".commercial-alert-beacon-item.is-positive",
        ".commercial-alert-beacon-item.is-warning",
        ".commercial-alert-beacon-actions",
        ".commercial-alert-beacon-action",
        ".commercial-alert-beacon-action.is-primary",
        ".commercial-alert-beacon-status",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-alert-beacon" in mobile_css
    assert ".commercial-alert-beacon-grid" in mobile_css
    assert ".commercial-alert-beacon-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    mobile_alert_copy = re.search(r"\.commercial-alert-beacon \.commercial-alert-beacon-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_alert_copy is not None
    assert "display: grid;" in mobile_alert_copy.group("body")
    assert "min-height: 46px;" in mobile_alert_copy.group("body")
    assert "padding: 8px;" in mobile_alert_copy.group("body")

    for function_name in (
        "function commercialAlertBeaconItem(id, label, value, detail, target, tone = '')",
        "function commercialAlertBeaconSummary(config)",
        "function renderCommercialAlertBeacon(root, config)",
        "function bindCommercialAlertBeacon(root, scope, configFactory)",
        "function workbenchAlertBeaconConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockAlertBeaconConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioAlertBeaconConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchAlertBeacon(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockAlertBeacon(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioAlertBeacon(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "警示中心",
        "追蹤表警示台",
        "單股警示台",
        "投組風險警示台",
        "追蹤表警示",
        "價格警示",
        "評級警示",
        "投組警示",
        "打開警示",
        "複製警示",
        "儲存警示",
    ):
        assert label in js

    assert "renderWorkbenchAlertBeacon(document.getElementById('commercial-workbench-alert-beacon')" in js
    assert "renderStockAlertBeacon(document.getElementById('commercial-stock-alert-beacon')" in js
    assert "renderPortfolioAlertBeacon(document.getElementById('commercial-portfolio-alert-beacon')" in js
    assert "bindCommercialAlertBeacon(document.getElementById('commercial-workbench-alert-beacon')" in js
    assert "bindCommercialAlertBeacon(document.getElementById('commercial-stock-alert-beacon')" in js
    assert "bindCommercialAlertBeacon(document.getElementById('commercial-portfolio-alert-beacon')" in js
    assert "writeCommercialMemory(`alert-beacon-${scope}`" in js
    assert "copyCommercialText(commercialAlertBeaconSummary(config)" in js
    assert "activeView = 'risk';" in js
    assert "currentFilter = 'alerts';" in js
    assert "activeCoverage = 'alerts';" in js
    assert "selectPortfolioLens('risk'" in js


def test_commercial_pages_add_page_specific_preset_beacons_for_custom_workspace_views():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-preset-beacon",
            "commercial-workbench-alert-beacon",
            "commercial-workbench-focus-dock",
            "追蹤表版面預設",
        ),
        "stock-detail.html": (
            "commercial-stock-preset-beacon",
            "commercial-stock-alert-beacon",
            "commercial-stock-focus-dock",
            "單股研究預設",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-preset-beacon",
            "commercial-portfolio-alert-beacon",
            "commercial-portfolio-focus-dock",
            "組合檢視預設",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for filename, (beacon_id, before_id, after_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{beacon_id}"') == 1
        assert f'id="{beacon_id}" class="commercial-preset-beacon"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{before_id}"') < html.index(f'id="{beacon_id}"') < html.index(f'id="{after_id}"')
        for other_beacon_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_beacon_id}"' not in html

    for selector in (
        ".commercial-preset-beacon",
        ".commercial-preset-beacon-copy",
        ".commercial-preset-beacon-grid",
        ".commercial-preset-beacon-item",
        ".commercial-preset-beacon-item.is-positive",
        ".commercial-preset-beacon-item.is-warning",
        ".commercial-preset-beacon-actions",
        ".commercial-preset-beacon-action",
        ".commercial-preset-beacon-action.is-primary",
        ".commercial-preset-beacon-status",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-preset-beacon" in mobile_css
    assert ".commercial-preset-beacon-grid" in mobile_css
    assert ".commercial-preset-beacon-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    for function_name in (
        "function commercialPresetBeaconItem(id, label, value, detail, target, tone = '')",
        "function commercialPresetBeaconSummary(config)",
        "function renderCommercialPresetBeacon(root, config)",
        "function bindCommercialPresetBeacon(root, scope, configFactory)",
        "function workbenchPresetBeaconConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet, activeScreenPreset)",
        "function stockPresetBeaconConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioPresetBeaconConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchPresetBeacon(root, rows, activeTicker, activeView, currentFilter, activeColumnSet, activeScreenPreset)",
        "function renderStockPresetBeacon(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioPresetBeacon(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "視圖預設",
        "追蹤表視圖預設",
        "單股研究預設",
        "投組回顧預設",
        "自訂欄位",
        "研究模式",
        "儀表板預設",
        "客戶回顧",
        "打開預設",
        "複製預設",
        "儲存預設",
    ):
        assert label in js

    mobile_preset_copy = re.search(r"\.commercial-preset-beacon \.commercial-preset-beacon-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_preset_copy is not None
    assert "display: grid;" in mobile_preset_copy.group("body")
    assert "min-height: 46px;" in mobile_preset_copy.group("body")

    assert "renderWorkbenchPresetBeacon(document.getElementById('commercial-workbench-preset-beacon')" in js
    assert "renderStockPresetBeacon(document.getElementById('commercial-stock-preset-beacon')" in js
    assert "renderPortfolioPresetBeacon(document.getElementById('commercial-portfolio-preset-beacon')" in js
    assert "bindCommercialPresetBeacon(document.getElementById('commercial-workbench-preset-beacon')" in js
    assert "bindCommercialPresetBeacon(document.getElementById('commercial-stock-preset-beacon')" in js
    assert "bindCommercialPresetBeacon(document.getElementById('commercial-portfolio-preset-beacon')" in js
    assert "writeCommercialMemory(`preset-beacon-${scope}`" in js
    assert "copyCommercialText(commercialPresetBeaconSummary(config)" in js
    assert "activeView = 'valuation';" in js
    assert "activeColumnSet = 'fundamental';" in js
    assert "activeScreenPreset = 'conviction';" in js
    assert "setStockTab('financials')" in js
    assert "activeTargetModel = 'balanced';" in js
    assert "selectPortfolioLens('contribution'" in js


def test_commercial_pages_add_page_specific_onboarding_beacons_for_first_run_setup():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-onboarding-beacon",
            "commercial-workbench-preset-beacon",
            "commercial-workbench-focus-dock",
            "追蹤表匯入啟動",
        ),
        "stock-detail.html": (
            "commercial-stock-onboarding-beacon",
            "commercial-stock-preset-beacon",
            "commercial-stock-focus-dock",
            "單股研究啟動",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-onboarding-beacon",
            "commercial-portfolio-preset-beacon",
            "commercial-portfolio-focus-dock",
            "組合帳戶匯入啟動",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for filename, (beacon_id, before_id, after_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{beacon_id}"') == 1
        assert f'id="{beacon_id}" class="commercial-onboarding-beacon"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{before_id}"') < html.index(f'id="{beacon_id}"') < html.index(f'id="{after_id}"')
        for other_beacon_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_beacon_id}"' not in html

    for selector in (
        ".commercial-onboarding-beacon",
        ".commercial-onboarding-beacon-copy",
        ".commercial-onboarding-beacon-grid",
        ".commercial-onboarding-beacon-item",
        ".commercial-onboarding-beacon-item.is-positive",
        ".commercial-onboarding-beacon-item.is-warning",
        ".commercial-onboarding-beacon-actions",
        ".commercial-onboarding-beacon-action",
        ".commercial-onboarding-beacon-action.is-primary",
        ".commercial-onboarding-beacon-status",
    ):
        assert selector in css

    onboarding_css = css.split(".commercial-onboarding-beacon {", 1)[1].split("}", 1)[0]
    assert "order: 6;" in onboarding_css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-onboarding-beacon" in mobile_css
    assert ".commercial-onboarding-beacon-grid" in mobile_css
    assert ".commercial-onboarding-beacon-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    for function_name in (
        "function commercialOnboardingBeaconItem(id, label, value, detail, target, tone = '')",
        "function commercialOnboardingBeaconSummary(config)",
        "function renderCommercialOnboardingBeacon(root, config)",
        "function bindCommercialOnboardingBeacon(root, scope, configFactory)",
        "function workbenchOnboardingBeaconConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockOnboardingBeaconConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioOnboardingBeaconConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchOnboardingBeacon(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockOnboardingBeacon(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioOnboardingBeacon(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "上手啟動",
        "追蹤表匯入啟動",
        "單股研究啟動",
        "券商匯入啟動",
        "匯入追蹤表",
        "股票搜尋",
        "連結券商",
        "CSV 匯入",
        "手動輸入",
        "設定檢查",
        "示範資料",
        "第一個警示",
        "打開設定",
        "複製設定",
        "儲存設定",
    ):
        assert label in js

    assert "renderWorkbenchOnboardingBeacon(document.getElementById('commercial-workbench-onboarding-beacon')" in js
    assert "renderStockOnboardingBeacon(document.getElementById('commercial-stock-onboarding-beacon')" in js
    assert "renderPortfolioOnboardingBeacon(document.getElementById('commercial-portfolio-onboarding-beacon')" in js
    assert "bindCommercialOnboardingBeacon(document.getElementById('commercial-workbench-onboarding-beacon')" in js
    assert "bindCommercialOnboardingBeacon(document.getElementById('commercial-stock-onboarding-beacon')" in js
    assert "bindCommercialOnboardingBeacon(document.getElementById('commercial-portfolio-onboarding-beacon')" in js
    assert "writeCommercialMemory(`onboarding-beacon-${scope}`" in js
    assert "copyCommercialText(commercialOnboardingBeaconSummary(config)" in js
    assert "activeView = 'event';" in js
    assert "activeColumnSet = 'decision';" in js
    assert "activeQuickAction = 'news';" in js
    assert "activeCoverage = 'alerts';" in js
    assert "activeTargetModel = 'balanced';" in js
    assert "selectPortfolioLens('contribution'" in js


def test_onboarding_beacons_use_mobile_grid_instead_of_clipped_carousel():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    beacon_grid = css_rule_body(
        mobile_css,
        ".commercial-onboarding-beacon .commercial-onboarding-beacon-grid",
    )
    assert beacon_grid is not None
    assert "display: grid;" in beacon_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in beacon_grid
    assert "overflow-x: visible;" in beacon_grid
    assert "padding-bottom: 0;" in beacon_grid

    beacon_item = css_rule_body(
        mobile_css,
        ".commercial-onboarding-beacon .commercial-onboarding-beacon-item",
    )
    assert beacon_item is not None
    assert "width: 100%;" in beacon_item
    assert "min-width: 0;" in beacon_item

    beacon_actions = css_rule_body(
        mobile_css,
        ".commercial-onboarding-beacon .commercial-onboarding-beacon-actions",
    )
    assert beacon_actions is not None
    assert "display: grid;" in beacon_actions
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in beacon_actions
    assert "overflow-x: visible;" in beacon_actions
    assert "padding-bottom: 0;" in beacon_actions

    beacon_action = css_rule_body(
        mobile_css,
        ".commercial-onboarding-beacon .commercial-onboarding-beacon-action",
    )
    assert beacon_action is not None
    assert "width: 100%;" in beacon_action
    assert "min-width: 0;" in beacon_action
    assert "white-space: normal;" in beacon_action


def test_visual_pulse_bars_are_scoped_from_existing_visual_board_chart_bars():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'class="commercial-visual-pulse-bar" aria-hidden="true"' in js
    assert '<i class="commercial-visual-bar" aria-hidden="true"></i>' not in js
    assert ".commercial-visual-pulse .commercial-visual-pulse-bar" in css
    assert ".commercial-visual-pulse .commercial-visual-bar" in css


def test_view_rails_render_competitor_grade_mode_switching_for_each_page():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-view-rail",
        ".commercial-view-rail-copy",
        ".commercial-view-rail-track",
        ".commercial-view-rail-item",
        ".commercial-view-rail-item.is-active",
        ".commercial-view-rail-status",
    ):
        assert selector in css

    for function_name in (
        "function commercialViewRailItem(id, label, metric, detail, target, state = {})",
        "function commercialViewRailSummary(config, activeId)",
        "function renderCommercialViewRail(root, config, activeId)",
        "function bindCommercialViewRail(root, scope, onSelect)",
        "function workbenchViewRailConfig(activeView, currentFilter, activeColumnSet)",
        "function stockViewRailConfig(currentTab, activeScenario, activeCoverage)",
        "function portfolioViewRailConfig(activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchViewRail(root, activeView, currentFilter, activeColumnSet)",
        "function renderStockViewRail(root, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioViewRail(root, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "視角切換",
        "一鍵模式",
        "進階頁籤",
        "已存視圖",
        "總覽",
        "財報",
        "股利",
        "新聞",
        "財務",
        "評級",
        "催化事件",
        "基準",
        "再平衡",
        "客戶包",
    ):
        assert label in js

    for data_attr in (
        "data-commercial-view-rail-item",
        "data-commercial-view-rail-target",
        "data-commercial-view-rail-copy",
    ):
        assert data_attr in js

    assert "renderWorkbenchViewRail(document.getElementById('commercial-workbench-view-rail')" in js
    assert "renderStockViewRail(document.getElementById('commercial-stock-view-rail')" in js
    assert "renderPortfolioViewRail(document.getElementById('commercial-portfolio-view-rail')" in js
    assert "bindCommercialViewRail(document.getElementById('commercial-workbench-view-rail'), 'workbench'" in js
    assert "bindCommercialViewRail(document.getElementById('commercial-stock-view-rail'), 'stock'" in js
    assert "bindCommercialViewRail(document.getElementById('commercial-portfolio-view-rail'), 'portfolio'" in js


def test_three_commercial_pages_surface_page_specific_session_watch():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-session-watch"' in workbench
    assert 'id="commercial-stock-session-watch"' in stock
    assert 'id="commercial-portfolio-session-watch"' in portfolio

    for selector in (
        ".commercial-session-watch",
        ".commercial-session-watch-copy",
        ".commercial-session-watch-grid",
        ".commercial-session-watch-card",
        ".commercial-session-watch-action",
    ):
        assert selector in css

    for function_name in (
        "function renderCommercialSessionWatch(root, config)",
        "function renderWorkbenchSessionWatch(root, rows, activeTicker, activeView)",
        "function renderStockSessionWatch(root, snapshot, currentTab, activeCoverage)",
        "function renderPortfolioSessionWatch(root, payload, activeLens, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "Session Watch",
        "Pre-Market Sweep",
        "After-Hours Queue",
        "Live Quote Guard",
        "Catalyst Window",
        "Exposure Drift",
        "Overnight Risk",
    ):
        assert label in js

    assert "renderWorkbenchSessionWatch(document.getElementById('commercial-workbench-session-watch')" in js
    assert "renderStockSessionWatch(document.getElementById('commercial-stock-session-watch')" in js
    assert "renderPortfolioSessionWatch(document.getElementById('commercial-portfolio-session-watch')" in js
    assert "'.commercial-session-watch'" in js


def test_view_rails_are_compact_touch_friendly_on_mobile():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    rail = re.search(r"\.commercial-view-rail \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert rail is not None
    assert "grid-template-columns: 1fr;" in rail.group("body")
    assert "gap: 8px;" in rail.group("body")
    assert "padding: 8px;" in rail.group("body")

    track = re.search(r"\.commercial-view-rail-track \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert track is not None
    assert "display: grid;" in track.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in track.group("body")
    assert "overflow-x: visible;" in track.group("body")
    assert "padding-bottom: 0;" in track.group("body")

    item = re.search(r"\.commercial-view-rail-item \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert item is not None
    assert "width: 100%;" in item.group("body")
    assert "min-width: 0;" in item.group("body")
    assert "min-height: 44px;" in item.group("body")

    status = re.search(r"\.commercial-view-rail-status \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert status is not None
    assert "display: none;" in status.group("body")


def test_core_surfaces_render_page_specific_competitor_grade_primary_data():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-core-surface",
        ".commercial-core-surface-copy",
        ".commercial-core-surface-metric-grid",
        ".commercial-core-surface-metric",
        ".commercial-core-surface-visual",
        ".commercial-core-surface-visual-track",
        ".commercial-core-surface-visual-fill",
        ".commercial-core-surface-visual-caption",
        ".commercial-core-surface-actions",
        ".commercial-core-surface-action",
        ".commercial-core-surface-status",
    ):
        assert selector in css

    for function_name in (
        "function commercialCoreSurfaceMetric(label, value, detail, tone = '', visualLevel = null)",
        "function commercialCoreSurfaceVisualCaption(label, detail, tone = '')",
        "function commercialCoreSurfaceVisual(label, value, detail, level, tone = '')",
        "function commercialCoreSurfaceLevel(value, fallback = 56)",
        "function commercialCoreSurfaceVisualAria(visual)",
        "function commercialCoreSurfaceAction(id, label, metric, target, primary = false)",
        "function commercialCoreSurfaceSummary(config)",
        "function renderCommercialCoreSurface(root, config)",
        "function bindCommercialCoreSurface(root)",
        "function workbenchCoreSurfaceConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockCoreSurfaceConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioCoreSurfaceConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchCoreSurface(root, rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function renderStockCoreSurface(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioCoreSurface(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "核心資料",
        "覆蓋率",
        "風險負載",
        "動能",
        "選取標的",
        "報價變動",
        "上行空間",
        "品質",
        "事件",
        "健康",
        "集中度",
        "分散度",
        "模型",
        "追蹤表核心資料",
        "單股快照核心",
        "組合健康核心",
        "打開表格",
        "打開快照",
        "打開財務",
        "打開健康",
        "打開曝險",
        "打開再平衡",
        "匯出 CSV",
        "客戶包",
        "量化評級",
        "健康分數",
        "摘要列數",
        "自訂欄",
    ):
        assert label in js

    assert "const visual = metric.visual;" in js
    assert "commercial-core-surface-visual" in js
    assert "role=\"img\"" in js
    assert "aria-label=\"${escapeHtml(commercialCoreSurfaceVisualAria(visual))}\"" in js
    assert "style=\"--commercial-core-level:${escapeHtml(String(visual.level))}%\"" in js
    assert "commercialCoreSurfaceMetric('平均報酬', pct(avgReturn), '決策後追蹤表現'" in js
    assert "commercialCoreSurfaceMetric('量化評級', Number.isFinite(quality) ? `${quality}/100` : 'N/A'" in js
    assert "commercialCoreSurfaceMetric('健康分數', `${healthScore}/100`" in js

    for data_attr in (
        "data-commercial-core-action",
        "data-commercial-core-target",
        "data-commercial-core-copy",
    ):
        assert data_attr in js

    assert "renderWorkbenchCoreSurface(document.getElementById('commercial-workbench-core-surface')" in js
    assert "renderStockCoreSurface(document.getElementById('commercial-stock-core-surface')" in js
    assert "renderPortfolioCoreSurface(document.getElementById('commercial-portfolio-core-surface')" in js


def test_core_surfaces_use_compact_mobile_scannable_rows():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    core = re.search(r"\.commercial-core-surface \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert core is not None
    assert "grid-template-columns: 1fr;" in core.group("body")
    assert "gap: 8px;" in core.group("body")
    assert "padding: 8px;" in core.group("body")

    metric_grid = re.search(r"\.commercial-core-surface-metric-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert metric_grid is not None
    assert "display: grid;" in metric_grid.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in metric_grid.group("body")
    assert "overflow-x: visible;" in metric_grid.group("body")
    assert "padding-bottom: 0;" in metric_grid.group("body")

    metric = re.search(r"\.commercial-core-surface-metric \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert metric is not None
    assert "width: 100%;" in metric.group("body")
    assert "min-width: 0;" in metric.group("body")
    assert "min-height: 58px;" in metric.group("body")

    visual = re.search(r"\.commercial-core-surface-visual \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert visual is not None
    assert "min-height: 18px;" in visual.group("body")

    caption = re.search(r"\.commercial-core-surface-visual-caption \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert caption is not None
    assert "display: none;" in caption.group("body")

    actions = re.search(r"\.commercial-core-surface-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert actions is not None
    assert "display: grid;" in actions.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in actions.group("body")
    assert "overflow-x: visible;" in actions.group("body")
    assert "padding-bottom: 0;" in actions.group("body")

    action = re.search(r"\.commercial-core-surface-action \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert action is not None
    assert "width: 100%;" in action.group("body")
    assert "min-width: 0;" in action.group("body")
    assert "min-height: 44px;" in action.group("body")
    assert "white-space: normal;" in action.group("body")

    status = re.search(r"\.commercial-core-surface-status \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert status is not None
    assert "display: none;" in status.group("body")


def test_home_page_exposes_commercial_layout_entries_after_restart():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="home-tab-commercial"' in html
    assert 'data-home-tab="commercial"' in html
    assert 'id="home-tab-commercial" class="home-tab-button is-active"' in html
    assert 'id="home-tab-analysis" class="home-tab-button"' in html
    assert 'id="home-panel-commercial"' in html
    assert 'id="home-panel-commercial" class="home-tab-panel is-active"' in html
    assert 'id="home-panel-analysis" class="home-tab-panel" role="tabpanel" aria-labelledby="home-tab-analysis" hidden' in html
    assert "商業版" in html
    assert 'href="/static/commercial/research-workbench.html"' in html
    assert 'href="/static/commercial/stock-detail.html"' in html
    assert 'href="/static/commercial/portfolio-dashboard.html"' in html


def test_commercial_pages_have_independent_landmarks_and_live_regions():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-page"' in workbench
    assert 'id="commercial-workbench-list"' in workbench
    assert 'id="commercial-workbench-detail"' in workbench
    assert 'id="commercial-stock-page"' in stock
    assert 'id="commercial-stock-snapshot"' in stock
    assert 'id="commercial-stock-tabs"' in stock
    assert 'id="commercial-portfolio-page"' in portfolio
    assert 'id="commercial-portfolio-risk"' in portfolio
    assert 'id="commercial-portfolio-table"' in portfolio

    for html in (workbench, stock, portfolio):
        assert 'aria-live="polite"' in html
        assert '<main ' in html
        assert 'aria-current="page"' in html

    assert ".commercial-shell" in css
    assert ".commercial-three-column" in css
    assert ".commercial-stock-layout" in css
    assert ".commercial-portfolio-layout" in css
    assert "@media (max-width: 920px)" in css


def test_commercial_pages_javascript_loads_each_page_from_existing_apis():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "loadResearchWorkbench" in js
    assert "loadStockDetail" in js
    assert "loadPortfolioDashboard" in js
    assert "/api/decision-tracking" in js
    assert "/api/stocks/" in js and "/snapshot" in js
    assert "/api/watchlist/portfolio/risk" in js
    assert "data-commercial-ticker" in js
    assert "data-stock-tab" in js
    assert "renderSnapshotSummary" in js


def test_commercial_pages_prioritize_primary_workflows_before_secondary_analysis():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")

    assert workbench.index('class="commercial-three-column"') < workbench.index('id="commercial-workbench-market-pulse"')
    assert stock.index('class="commercial-stock-layout"') < stock.index('id="commercial-stock-decision-brief"')
    assert portfolio.index('id="commercial-portfolio-what-if-controls"') < portfolio.index('id="commercial-portfolio-table"')
    assert portfolio.index('id="commercial-portfolio-what-if-controls"') < portfolio.index('id="commercial-portfolio-what-if"')
    assert portfolio.index('id="commercial-portfolio-target-model"') < portfolio.index('id="commercial-portfolio-holdings"')


def test_mobile_commercial_pages_surface_primary_actions_before_long_feeds():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert workbench.index('class="commercial-three-column"') < workbench.index("Command Center")
    assert ".commercial-portfolio-layout > aside:first-of-type" in css
    assert ".commercial-portfolio-layout > aside:last-of-type" in css
    assert ".commercial-portfolio-layout > section" in css
    assert "order: 2;" in css
    assert "order: 3;" in css
    assert ".commercial-portfolio-layout .commercial-textarea" in css
    assert "max-height: 132px;" in css


def test_research_workbench_mobile_ticker_click_surfaces_snapshot_without_hunting():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    mobile_layout = re.search(r"@media \(max-width: 1180px\) \{(?P<body>.*?)\n\}", css, re.S)
    assert mobile_layout is not None
    assert ".commercial-three-column > aside:first-child" in mobile_layout.group("body")
    assert ".commercial-three-column > aside:last-child" in mobile_layout.group("body")
    assert ".commercial-three-column > section" in mobile_layout.group("body")

    assert "async function selectTicker(ticker, rows, shouldFocusSnapshot = false)" in js
    assert "renderWorkbenchFocusDock(focusDockRoot, selectedRow, null, sourceRows, normalized, 'decision', 'loading')" in js
    assert "renderWorkbenchFocusDock(focusDockRoot, selectedRow, snapshot, sourceRows, normalized, 'decision', 'ready')" in js
    assert "scrollWorkbenchSnapshotIntoView(detailRoot)" not in js
    assert "scrollWorkbenchSnapshotIntoView(inspectorRoot || detailRoot)" not in js
    assert "await selectTicker(activeTicker, visibleRows.length ? visibleRows : rows, false)" in js
    assert "selectTicker(activeTicker, visibleRows.length ? visibleRows : rows, true)" in js


def test_stock_detail_keeps_snapshot_available_before_deep_report_content():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert ".commercial-stock-layout > aside" in css
    assert "position: sticky;" in css
    assert "top: 82px;" in css
    assert "max-height: calc(100vh - 96px);" in css
    assert "overflow: auto;" in css

    mobile_layout = re.search(r"@media \(max-width: 1180px\) \{(?P<body>.*?)\n\}", css, re.S)
    assert mobile_layout is not None
    assert ".commercial-stock-layout > aside" in mobile_layout.group("body")
    assert ".commercial-stock-layout > section" in mobile_layout.group("body")
    assert "position: static;" in mobile_layout.group("body")
    assert "max-height: none;" in mobile_layout.group("body")
    assert "overflow: visible;" in mobile_layout.group("body")


def test_commercial_primary_workspaces_are_promoted_before_deep_tool_modules():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    main = re.search(r"\.commercial-main \{(?P<body>.*?)\n\}", css, re.S)
    assert main is not None
    assert "display: flex;" in main.group("body")
    assert "flex-direction: column;" in main.group("body")

    default_sections = re.search(r"\.commercial-main > :where\(section\) \{(?P<body>.*?)\n\}", css, re.S)
    assert default_sections is not None
    assert "order: 40;" in default_sections.group("body")

    for selector, expected_order in (
        (".commercial-hero", "order: 1;"),
        (".commercial-core-surface", "order: 2;"),
        (".commercial-action-dock", "order: 3;"),
        (".commercial-view-rail", "order: 4;"),
        (".commercial-signal-tape", "order: 5;"),
        (".commercial-three-column", "order: 6;"),
        (".commercial-stock-layout", "order: 6;"),
        (".commercial-portfolio-layout", "order: 6;"),
        (".commercial-technical-pulse", "order: 7;"),
        (".commercial-disclosure-digest", "order: 7;"),
        (".commercial-visual-pulse", "order: 7;"),
        (".commercial-report-locator", "order: 7;"),
        (".commercial-data-beacon", "order: 7;"),
        (".commercial-alert-beacon", "order: 7;"),
        (".commercial-preset-beacon", "order: 7;"),
        (".commercial-today-inbox", "order: 8;"),
        (".commercial-focus-dock", "order: 6;"),
        (".commercial-market-coverage", "order: 9;"),
        (".commercial-decision-radar", "order: 10;"),
        (".commercial-context-bar", "order: 11;"),
    ):
        rule = re.search(rf"^{re.escape(selector)} \{{(?P<body>.*?)\n\}}", css, re.S | re.M)
        assert rule is not None
        assert expected_order in rule.group("body")

    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    assert "'.commercial-today-inbox'" in js


def test_primary_workspaces_have_page_specific_command_bars_like_pro_dashboards():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for html, layout_marker, command_id, first_panel_marker in (
        (
            workbench,
            'class="commercial-three-column"',
            'id="commercial-workbench-workspace-command"',
            "<strong>追蹤清單</strong>",
        ),
        (
            stock,
            'class="commercial-stock-layout"',
            'id="commercial-stock-workspace-command"',
            "<strong>研究分頁</strong>",
        ),
        (
            portfolio,
            'class="commercial-portfolio-layout"',
            'id="commercial-portfolio-workspace-command"',
            "<strong>持股資料</strong>",
        ),
    ):
        assert html.index(layout_marker) < html.index(command_id) < html.index(first_panel_marker)
        assert 'class="commercial-workspace-command-bar"' in html

    command_rule = re.search(r"\.commercial-workspace-command-bar \{(?P<body>.*?)\n\}", css, re.S)
    assert command_rule is not None
    assert "grid-column: 1 / -1;" in command_rule.group("body")
    assert "position: relative;" in command_rule.group("body")
    assert "position: sticky;" not in command_rule.group("body")
    assert "top: 82px;" not in command_rule.group("body")
    assert "z-index: 1;" in command_rule.group("body")
    assert "background-color: rgba(7, 17, 30, 0.98);" in command_rule.group("body")
    assert ".commercial-workspace-command-metrics" in css
    assert ".commercial-workspace-command-actions" in css
    assert ".commercial-workspace-command-button" in css
    assert ".commercial-workspace-command-action" in css

    mobile_layout = re.search(r"@media \(max-width: 1180px\) \{(?P<body>.*?)\n\}", css, re.S)
    assert mobile_layout is not None
    assert ".commercial-workspace-command-bar" in mobile_layout.group("body")
    assert "position: relative;" in mobile_layout.group("body")
    assert "order: 0;" in mobile_layout.group("body")

    for function_name in (
        "function commercialWorkspaceCommandMetric",
        "function commercialWorkspaceCommandAction",
        "function renderCommercialWorkspaceCommandBar",
        "function bindCommercialWorkspaceCommandBar",
        "function workbenchWorkspaceCommandBarConfig",
        "function stockWorkspaceCommandBarConfig",
        "function portfolioWorkspaceCommandBarConfig",
    ):
        assert function_name in js
    for label in (
        "追蹤表隊列",
        "可見列數",
        "打開快照",
        "匯出 CSV",
        "單股快照",
        "價格區間",
        "財務",
        "AI 報告",
        "組合透視",
        "風險旗標",
        "再平衡單",
        "客戶包",
    ):
        assert label in js
    for render_call in (
        "renderCommercialWorkspaceCommandBar(document.getElementById('commercial-workbench-workspace-command'), workbenchWorkspaceCommandBarConfig",
        "renderCommercialWorkspaceCommandBar(document.getElementById('commercial-stock-workspace-command'), stockWorkspaceCommandBarConfig",
        "renderCommercialWorkspaceCommandBar(document.getElementById('commercial-portfolio-workspace-command'), portfolioWorkspaceCommandBarConfig",
    ):
        assert render_call in js
    for bind_call in (
        "bindCommercialWorkspaceCommandBar(document.getElementById('commercial-workbench-workspace-command'), 'workbench'",
        "bindCommercialWorkspaceCommandBar(document.getElementById('commercial-stock-workspace-command'), 'stock'",
        "bindCommercialWorkspaceCommandBar(document.getElementById('commercial-portfolio-workspace-command'), 'portfolio'",
    ):
        assert bind_call in js


def test_workspace_command_bar_keeps_latest_action_handler_after_rerender_binding():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    binding = re.search(
        r"function bindCommercialWorkspaceCommandBar\(root, scope, onAction\) \{(?P<body>.*?)\n    \}",
        js,
        re.S,
    )
    assert binding is not None
    body = binding.group("body")
    assert "root.commercialWorkspaceCommandAction = onAction;" in body
    assert "root.commercialWorkspaceCommandScope = scope;" in body
    assert "if (!root || root.dataset.commercialWorkspaceCommandBound === 'true') return;" not in body
    assert "const handledAction = action && typeof root.commercialWorkspaceCommandAction === 'function';" in body
    assert "if (handledAction) root.commercialWorkspaceCommandAction(action, target, event, root.commercialWorkspaceCommandScope);" in body
    assert "if (target) scrollCommercialTaskTarget(target, { revealPrimary: !handledAction });" in body
    assert "if (root.dataset.commercialWorkspaceCommandBound === 'true') return;" in body
    assert "if (action === 'ai-report') setStockTab('report');" in js


def test_commercial_secondary_modules_collapse_but_reveal_when_targeted():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert ".commercial-secondary-module" in css
    secondary_rule = re.search(r"\.commercial-secondary-module \{(?P<body>.*?)\n\}", css, re.S)
    assert secondary_rule is not None
    assert "max-height: 92px;" in secondary_rule.group("body")
    assert "overflow: hidden;" in secondary_rule.group("body")

    expanded_rule = re.search(r"\.commercial-secondary-module\.is-expanded \{(?P<body>.*?)\n\}", css, re.S)
    assert expanded_rule is not None
    assert "max-height: none;" in expanded_rule.group("body")
    assert "overflow: visible;" in expanded_rule.group("body")

    assert "function setupCommercialSecondaryModules(pageName)" in js
    assert "'.commercial-technical-pulse'" in js
    assert "'.commercial-three-column'" in js
    assert "'.commercial-stock-layout'" in js
    assert "'.commercial-portfolio-layout'" in js
    assert "commercialSetSecondaryModuleExpanded(module, true)" in js
    assert "revealCommercialSecondaryModule(target)" in js


def test_commercial_secondary_modules_move_into_competitor_style_module_library():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    hidden_rule = re.search(r"\.commercial-secondary-module:not\(\.is-expanded\) \{(?P<body>.*?)\n\}", css, re.S)
    assert hidden_rule is not None
    assert "display: none;" in hidden_rule.group("body")

    library_rule = re.search(r"\.commercial-secondary-library \{(?P<body>.*?)\n\}", css, re.S)
    assert library_rule is not None
    assert "order: 12;" in library_rule.group("body")
    assert "max-height: 260px;" in library_rule.group("body")
    assert "overflow: auto;" in library_rule.group("body")

    assert "'.commercial-secondary-library'" in js
    assert "function setupCommercialSecondaryModuleLibrary(main, pageName, modules)" in js
    assert "data-commercial-secondary-open" in js
    assert "function commercialCollapseSecondaryModulesExcept(activeModule)" in js
    assert "commercialCollapseSecondaryModulesExcept(module);" in js
    assert "const openButton = event.target.closest('[data-commercial-secondary-open]')" in js


def test_commercial_secondary_module_library_is_searchable_like_pro_tool_drawers():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert ".commercial-secondary-library-search" in css
    assert ".commercial-secondary-library-status" in css
    assert "data-commercial-secondary-search" in js
    assert "data-commercial-secondary-search-text" in js
    assert "data-commercial-secondary-status" in js
    assert "function commercialFilterSecondaryLibrary(library, query)" in js
    assert "const searchText = `${module.id} ${label} ${summary}`.toLowerCase();" in js
    assert "button.hidden = !matched;" in js
    assert "main.addEventListener('input', event => {" in js
    assert "const search = event.target.closest('[data-commercial-secondary-search]')" in js


def test_commercial_secondary_module_library_supports_terminal_style_keyboard_entry():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'aria-keyshortcuts="/ Control+K Meta+K Escape"' in js
    assert "function commercialShouldIgnoreKeyboardShortcut(event)" in js
    assert "event.target.closest('input, textarea, select, [contenteditable=\"true\"]')" in js
    assert "function focusCommercialSecondaryLibrarySearch(main, query = '')" in js
    assert "search.focus();" in js
    assert "search.select();" in js
    assert "commercialFilterSecondaryLibrary(library, search.value);" in js
    assert "function bindCommercialSecondaryLibraryShortcuts(main)" in js
    assert "event.key === '/'" in js
    assert "event.key.toLowerCase() === 'k'" in js
    assert "event.key === 'Escape'" in js
    assert "bindCommercialSecondaryLibraryShortcuts(main);" in js


def test_commercial_secondary_module_library_accepts_koyfin_style_page_commands():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function commercialSecondaryCommandTarget(pageName, query)" in js
    assert "const COMMERCIAL_SECONDARY_COMMANDS = {" in js
    assert "workbench: [" in js
    assert "stock: [" in js
    assert "portfolio: [" in js
    assert "aliases: ['s', 'snapshot', 'quote']" in js
    assert "aliases: ['est', 'actuals', 'consensus', 'earnings']" in js
    assert "aliases: ['rebalance', 'drift', 'orders']" in js
    assert "function runCommercialSecondaryCommand(library, pageName, query)" in js
    assert "scrollCommercialTaskTarget(command.target)" in js
    assert "data-commercial-secondary-page" in js
    assert "event.key === 'Enter'" in js
    assert "runCommercialSecondaryCommand(library, library.dataset.commercialSecondaryPage, search.value)" in js
    assert "已打開命令" in js


def test_commercial_secondary_module_library_surfaces_page_specific_command_presets_and_recents():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-secondary-command-presets",
        ".commercial-secondary-command-recents",
        ".commercial-secondary-command-preset",
        ".commercial-secondary-command-preset.is-primary",
    ):
        assert selector in css

    assert "function commercialSecondaryCommandPresets(pageName)" in js
    assert "function commercialSecondaryCommandPresetButton(command, index, recent = false)" in js
    assert "function renderCommercialSecondaryCommandPresets(library, pageName)" in js
    assert "function rememberCommercialSecondaryCommand(pageName, command)" in js
    assert "secondary-command-recents-${scope}" in js
    assert "data-commercial-secondary-command" in js
    assert "data-commercial-secondary-command-target" in js
    assert "data-commercial-secondary-command-presets" in js
    assert "data-commercial-secondary-command-recents" in js
    assert "打開快照" in js
    assert "打開財報" in js
    assert "打開再平衡" in js
    assert "const commandButton = event.target.closest('[data-commercial-secondary-command]')" in js
    assert "runCommercialSecondaryCommand(library, library.dataset.commercialSecondaryPage, commandButton.dataset.commercialSecondaryCommand)" in js
    assert "renderCommercialSecondaryCommandPresets(library, library.dataset.commercialSecondaryPage)" in js


def test_commercial_secondary_command_presets_fit_mobile_touch_targets():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    assert ".commercial-secondary-command-presets" in mobile_css
    assert ".commercial-secondary-command-recents" in mobile_css
    assert ".commercial-secondary-command-preset" in mobile_css
    rule = re.search(r"\.commercial-secondary-command-preset \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert rule is not None
    assert "min-height: 44px;" in rule.group("body")
    assert "min-width: 0;" in rule.group("body")


def test_commercial_pages_bind_page_specific_keyboard_workflows_like_terminal_tools():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function commercialWorkflowKeyboardIndex(items, currentId, delta)" in js
    assert "function commercialWorkflowKeyboardScope()" in js
    assert "function bindCommercialWorkflowKeyboardShortcuts(scope, handlers)" in js
    assert "data-commercial-workflow-keyboard-scope" in js
    assert "aria-keyshortcuts" in js
    assert "Alt+ArrowDown Alt+ArrowUp Alt+ArrowRight Alt+ArrowLeft" in js
    assert "event.altKey && event.key === 'ArrowDown'" in js
    assert "event.altKey && event.key === 'ArrowRight'" in js
    assert "commercialShouldIgnoreKeyboardShortcut(event)" in js
    assert "Promise.resolve(handler(direction)).catch(() => {})" in js

    assert "bindCommercialWorkflowKeyboardShortcuts('research-workbench'" in js
    assert "nextTicker: async direction =>" in js
    assert "const tickers = visibleRows.map(row => normalizeTicker(row.ticker))" in js
    assert "commercialWorkflowKeyboardIndex(tickers, activeTicker, direction)" in js
    assert "nextButton.click();" in js

    assert "bindCommercialWorkflowKeyboardShortcuts('stock-detail'" in js
    assert "nextTab: direction =>" in js
    assert "commercialWorkflowKeyboardIndex(stockTabs, currentTab, direction)" in js
    assert "setStockTab(stockTabs[nextIndex]);" in js

    assert "bindCommercialWorkflowKeyboardShortcuts('portfolio-dashboard'" in js
    assert "nextLens: direction =>" in js
    assert "const portfolioLenses = ['sector', 'country', 'risk', 'contribution']" in js
    assert "commercialWorkflowKeyboardIndex(portfolioLenses, activeLens, direction)" in js
    assert "selectPortfolioLens(portfolioLenses[nextIndex], { target: 'commercial-portfolio-health-score' });" in js


def test_portfolio_lens_keyboard_and_clicks_share_the_same_state_path():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function selectPortfolioLens(nextLens, options = {})" in js
    assert "const portfolioLens = validCommercialChoice(nextLens, ['sector', 'country', 'risk', 'contribution'], activeLens);" in js
    assert "activeLens = portfolioLens;" in js
    assert "applyPortfolioTargetWeight(lastPayload, activeLens, activeScenario, targetWeight, activeExecutionMode, activeTargetModel, driftTolerance, portfolioSource);" in js
    assert "renderCommercialProvenance(portfolioProvenanceRoot, portfolioProvenanceItems(portfolioSource, lastPayload, activeTargetModel));" in js
    assert "syncPortfolioUrl();" in js
    assert "renderPortfolioWorkspaceChrome();" in js
    assert "renderPortfolioHistory(options.historyMessage);" in js
    assert "requestAnimationFrame(() => scrollCommercialElementTarget(options.target || 'commercial-portfolio-health-score'));" in js
    assert "selectPortfolioLens(item.lens, { target: item.target || 'commercial-portfolio-health-score' });" in js
    assert "selectPortfolioLens(portfolioLenses[nextIndex], { target: 'commercial-portfolio-health-score' });" in js
    assert "selectPortfolioLens(button.dataset.portfolioLens);" in js
    assert "button.setAttribute('aria-pressed', String(isActive));" in js
    assert "function scrollCommercialElementTarget(targetId)" in js
    assert "scrollCommercialTaskTarget(targetId, { revealPrimary: false });" in js


def test_stock_and_portfolio_primary_views_show_only_active_competitive_panels():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    hidden_rule = re.search(r"\.commercial-primary-view-panel\[hidden\] \{(?P<body>.*?)\n\}", css, re.S)
    assert hidden_rule is not None
    assert "display: none !important;" in hidden_rule.group("body")

    assert "const STOCK_PRIMARY_TAB_PANELS = {" in js
    assert "overview: [" in js
    assert "'commercial-stock-price-chart'" in js
    assert "'commercial-stock-snapshot'" in js
    assert "financials: [" in js
    assert "'commercial-stock-financial-statements'" in js
    assert "analysts: [" in js
    assert "'commercial-stock-target-distribution'" in js
    assert "function syncStockPrimaryTabPanels(activeTab)" in js
    assert "syncStockPrimaryTabPanels(currentTab);" in js

    assert "const PORTFOLIO_PRIMARY_LENS_PANELS = {" in js
    assert "sector: [" in js
    assert "'commercial-portfolio-xray'" in js
    assert "risk: [" in js
    assert "'commercial-portfolio-risk'" in js
    assert "'commercial-portfolio-rebalance-ticket'" in js
    assert "contribution: [" in js
    assert "'commercial-portfolio-risk-contribution'" in js
    assert "function syncPortfolioPrimaryLensPanels(activeLens)" in js
    assert "syncPortfolioPrimaryLensPanels(activeLens);" in js


def test_scroll_task_target_activates_hidden_stock_and_portfolio_primary_views():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function commercialPrimaryViewKeyForTarget(panelMap, targetId)" in js
    assert "Object.entries(panelMap || {}).find(([, ids]) => ids.includes(targetId))" in js
    assert "function revealCommercialPrimaryTaskTarget(targetId)" in js
    assert "const stockTab = commercialPrimaryViewKeyForTarget(STOCK_PRIMARY_TAB_PANELS, targetId);" in js
    assert 'document.querySelector(`[data-stock-tab="${stockTab}"]`)' in js
    assert "stockTabButton.click();" in js
    assert "syncStockPrimaryTabPanels(stockTab);" in js
    assert "const portfolioLens = commercialPrimaryViewKeyForTarget(PORTFOLIO_PRIMARY_LENS_PANELS, targetId);" in js
    assert 'document.querySelector(`[data-portfolio-lens="${portfolioLens}"]`)' in js
    assert "portfolioLensButton.click();" in js
    assert "syncPortfolioPrimaryLensPanels(portfolioLens);" in js

    scroll_helper = re.search(
        r"function scrollCommercialTaskTarget\(targetId, options = \{\}\) \{(?P<body>.*?)\n    \}",
        js,
        re.S,
    )
    assert scroll_helper is not None
    body = scroll_helper.group("body")
    assert body.index("if (options.revealPrimary !== false) revealCommercialPrimaryTaskTarget(targetId);") < body.index("const firstTarget = currentTarget();")
    assert "'commercial-stock-earnings-panel'" in js
    assert "'commercial-portfolio-rebalance-ticket'" in js


def test_portfolio_dashboard_keeps_rebalance_action_rail_available_on_desktop():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    action_rail = re.search(r"\.commercial-portfolio-layout > aside:last-of-type \{(?P<body>.*?)\n\}", css, re.S)
    assert action_rail is not None
    assert "position: sticky;" in action_rail.group("body")
    assert "top: 82px;" in action_rail.group("body")
    assert "max-height: calc(100vh - 96px);" in action_rail.group("body")
    assert "overflow: auto;" in action_rail.group("body")

    mobile_layout = re.search(r"@media \(max-width: 1180px\) \{(?P<body>.*?)\n\}", css, re.S)
    assert mobile_layout is not None
    assert ".commercial-portfolio-layout > aside:last-of-type" in mobile_layout.group("body")
    assert "position: static;" in mobile_layout.group("body")
    assert "max-height: none;" in mobile_layout.group("body")
    assert "overflow: visible;" in mobile_layout.group("body")


def test_commercial_pages_have_shareable_url_state_helpers():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function readCommercialParams()" in js
    assert "new URLSearchParams(window.location.search || '')" in js
    assert "function replaceCommercialQuery(state)" in js
    assert "window.history.replaceState" in js
    assert "function validCommercialChoice(value, allowed, fallback)" in js
    assert "function commercialNumberParam(params, key, fallback, min, max)" in js


def test_research_workbench_supports_shareable_workspace_state():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const params = readCommercialParams();" in js
    assert "const hasInitialTickerParam = params.has('ticker');" in js
    assert "activeTicker = normalizeTicker(hasInitialTickerParam ? params.get('ticker') : rows[0]?.ticker || '2330.TW')" in js
    assert "currentFilter = validCommercialChoice(params.get('filter'), ['all', 'alerts', 'rerun', 'positive'], initialScreenConfig.filter)" in js
    assert "activeView = validCommercialChoice(params.get('view'), ['decision', 'valuation', 'event', 'risk'], initialScreenConfig.view)" in js
    assert "activeColumnSet = validCommercialChoice(params.get('columns'), Object.keys(WORKBENCH_COLUMN_SETS), initialScreenConfig.columnSet)" in js
    assert "const contextTicker = hasInitialTickerParam ? normalizeTicker(params.get('ticker')) : ''" in js
    assert "&& !contextTicker) activeTicker = visibleRows[0]?.ticker || rows[0]?.ticker || activeTicker" in js
    assert "function syncWorkbenchUrl()" in js
    assert "replaceCommercialQuery({ ticker: activeTicker, view: activeView, filter: currentFilter, columns: activeColumnSet, flag: activeFlag, screen: activeScreenPreset, quick: activeQuickAction, q: commandQuery })" in js
    assert "syncWorkbenchUrl();" in js


def test_stock_detail_supports_shareable_ticker_tab_and_scenario_state():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const stockTabs = ['overview', 'report', 'financials', 'analysts', 'technicals', 'thesis', 'ownership', 'news'];" in js
    assert "currentTab = validCommercialChoice(params.get('tab'), stockTabs, 'overview')" in js
    assert "activeRange = validCommercialChoice(params.get('range'), ['1M', '6M', '1Y', '5Y'], '1M')" in js
    assert "activeScenario = validCommercialChoice(params.get('scenario'), ['bear', 'base', 'bull'], 'base')" in js
    assert "function syncStockUrl(ticker)" in js
    assert "replaceCommercialQuery({ ticker: normalizeTicker(ticker || input?.value), tab: currentTab, range: activeRange, scenario: activeScenario })" in js
    assert "await load(params.get('ticker') || input?.value || '2330.TW');" in js


def test_portfolio_dashboard_supports_shareable_rebalance_state():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "activeLens = validCommercialChoice(params.get('lens'), ['sector', 'country', 'risk', 'contribution'], 'sector')" in js
    assert "activeScenario = validCommercialChoice(params.get('scenario'), ['base', 'rate', 'chip', 'fx'], 'base')" in js
    assert "targetWeight = commercialNumberParam(params, 'target', 35, 20, 45)" in js
    assert "driftTolerance = commercialNumberParam(params, 'drift', 5, 2, 15)" in js
    assert "activeExecutionMode = validCommercialChoice(params.get('mode'), ['trim', 'cash', 'balanced'], 'trim')" in js
    assert "activeTargetModel = validCommercialChoice(params.get('model'), Object.keys(PORTFOLIO_TARGET_MODELS), 'balanced')" in js
    assert "function syncPortfolioUrl()" in js
    assert "replaceCommercialQuery({ ticker: portfolioContextTicker, lens: activeLens, scenario: activeScenario, target: targetWeight, drift: driftTolerance, mode: activeExecutionMode, model: activeTargetModel })" in js


def test_commercial_pages_have_delivery_action_containers():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-delivery"' in workbench
    assert 'id="commercial-stock-delivery"' in stock
    assert 'id="commercial-portfolio-delivery"' in portfolio
    for html in (workbench, stock, portfolio):
        assert 'class="commercial-delivery-bar"' in html
        assert 'aria-live="polite"' in html

    assert ".commercial-delivery-bar" in css
    assert ".commercial-delivery-actions" in css
    assert ".commercial-delivery-feedback" in css


def test_commercial_pages_can_copy_links_and_download_work_products():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function copyCommercialText(text, root, successLabel)" in js
    assert "navigator.clipboard.writeText" in js
    assert "function fallbackCopyCommercialText(text)" in js
    assert "function downloadCommercialText(filename, text)" in js
    assert "function showCommercialFeedback(root, message)" in js
    assert "data-commercial-copy-link" in js
    assert "data-commercial-feedback" in js


def test_research_workbench_exports_current_view_delivery_pack():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function workbenchDeliveryText(rows, activeTicker, activeView, currentFilter, activeColumnSet)" in js
    assert "function renderWorkbenchDelivery(root, rows, activeTicker, activeView, currentFilter, activeColumnSet)" in js
    assert "data-workbench-copy-brief" in js
    assert "data-workbench-download-csv" in js
    assert "onstock-watchlist-view.csv" in js
    assert "renderWorkbenchDelivery(document.getElementById('commercial-workbench-delivery'), visibleRows.length ? visibleRows : rows, activeTicker, activeView, currentFilter, activeColumnSet)" in js


def test_stock_detail_exports_research_delivery_pack():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function stockDeliveryText(snapshot, currentTab, activeScenario, activeRange)" in js
    assert "function renderStockDelivery(root, snapshot, currentTab, activeScenario, activeRange)" in js
    assert "data-stock-copy-brief" in js
    assert "data-stock-download-report" in js
    assert "onstock-research-" in js
    assert "renderStockDelivery(document.getElementById('commercial-stock-delivery'), snapshot, currentTab, activeScenario, activeRange)" in js


def test_portfolio_dashboard_exports_rebalance_delivery_pack():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function portfolioDeliveryText(payload, activeLens, activeScenario, targetWeight, driftTolerance, activeExecutionMode, activeTargetModel)" in js
    assert "function renderPortfolioDelivery(root, payload, activeLens, activeScenario, targetWeight, driftTolerance, activeExecutionMode, activeTargetModel)" in js
    assert "data-portfolio-copy-plan" in js
    assert "data-portfolio-download-plan" in js
    assert "onstock-portfolio-rebalance.txt" in js
    assert "renderPortfolioDelivery(document.getElementById('commercial-portfolio-delivery'), payload, activeLens, activeScenario, targetWeight, driftTolerance, activeExecutionMode, activeTargetModel)" in js


def test_commercial_pages_surface_data_status_and_retry_controls():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-data-status"' in workbench
    assert 'id="commercial-stock-data-status"' in stock
    assert 'id="commercial-portfolio-data-status"' in portfolio
    assert ".commercial-data-status" in css
    assert ".commercial-data-status.is-live" in css
    assert ".commercial-data-status.is-fallback" in css
    assert ".commercial-data-status.is-loading" in css
    assert ".commercial-data-status.is-error" in css

    assert "function renderCommercialDataStatus(root, state)" in js
    assert "data-commercial-retry" in js
    assert "Live data" in js
    assert "Fallback demo" in js


def test_commercial_pages_surface_page_specific_next_action_rails():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-action-rail"' in workbench
    assert 'id="commercial-stock-action-rail"' in stock
    assert 'id="commercial-portfolio-action-rail"' in portfolio
    assert ".commercial-next-actions" in css
    assert ".commercial-next-action" in css
    assert ".commercial-next-action.is-primary" in css
    assert "function renderCommercialNextActions(root, config)" in js


def test_commercial_pages_surface_data_provenance_and_freshness_strips():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-provenance"' in workbench
    assert 'id="commercial-stock-provenance"' in stock
    assert 'id="commercial-portfolio-provenance"' in portfolio
    assert ".commercial-provenance-strip" in css
    assert ".commercial-provenance-item" in css
    assert ".commercial-provenance-item.is-warning" in css
    assert ".commercial-provenance-item.is-live" in css
    assert "function renderCommercialProvenance(root, items)" in js
    assert "function formatCommercialTimestamp(value)" in js


def test_research_workbench_provenance_uses_decision_tracking_freshness():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "lastRefreshAt: item.last_refresh_at || item.last_refresh_date" in js
    assert "function workbenchProvenanceItems(source, rows)" in js
    assert "Decision freshness" in js
    assert "requiresRerun" in js
    assert "renderCommercialProvenance(workbenchProvenanceRoot, workbenchProvenanceItems(trackingSource, rows))" in js


def test_stock_detail_provenance_uses_quote_quality_and_market_session():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const stockProvenanceRoot = document.getElementById('commercial-stock-provenance')" in js
    assert "function stockProvenanceItems(source, snapshot)" in js
    assert "Data quality" in js
    assert "Market session" in js
    assert "snapshot.data_quality?.score" in js
    assert "snapshot.market_session?.direction" in js
    assert "renderCommercialProvenance(stockProvenanceRoot, stockProvenanceItems(snapshotSource, snapshot))" in js


def test_portfolio_dashboard_provenance_uses_benchmark_model_and_thesis_gaps():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const portfolioProvenanceRoot = document.getElementById('commercial-portfolio-provenance')" in js
    assert "function portfolioProvenanceItems(source, payload, activeTargetModel)" in js
    assert "Benchmark basis" in js
    assert "Target model" in js
    assert "Thesis gaps" in js
    assert "PORTFOLIO_TARGET_MODELS[activeTargetModel]" in js
    assert "renderCommercialProvenance(portfolioProvenanceRoot, portfolioProvenanceItems(portfolioSource, lastPayload, activeTargetModel))" in js


def test_research_workbench_next_actions_focus_decision_workflow():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function renderWorkbenchNextActions(root, rows, activeTicker, activeView)" in js
    assert "data-workbench-next-action=\"alerts\"" in js
    assert "data-workbench-next-action=\"stock-page\"" in js
    assert "data-workbench-next-action=\"copy-brief\"" in js
    assert "renderWorkbenchNextActions(document.getElementById('commercial-workbench-action-rail'), visibleRows.length ? visibleRows : rows, activeTicker, activeView)" in js
    assert "openCommercialStockDetail(activeTicker)" in js
    assert "document.getElementById('commercial-workbench-action-rail')?.addEventListener('click', async event =>" in js
    assert "if (action === 'alerts') {\n                currentFilter = 'alerts';\n                await applyWorkbenchFilter();" in js


def test_stock_detail_next_actions_promote_research_workflow():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function renderStockNextActions(root, snapshot, currentTab, activeScenario)" in js
    assert "data-stock-next-action=\"report\"" in js
    assert "data-stock-next-action=\"target-alert\"" in js
    assert "data-stock-next-action=\"peer-check\"" in js
    assert "renderStockNextActions(document.getElementById('commercial-stock-action-rail'), snapshot, currentTab, activeScenario)" in js
    assert "setStockTab('report')" in js
    assert "setStockAlertPreset('target')" in js


def test_portfolio_dashboard_next_actions_promote_xray_and_rebalance_workflow():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function renderPortfolioNextActions(root, payload, activeLens, activeScenario, activeTargetModel)" in js
    assert "data-portfolio-next-action=\"xray\"" in js
    assert "data-portfolio-next-action=\"rebalance\"" in js
    assert "data-portfolio-next-action=\"copy-plan\"" in js
    assert "renderPortfolioNextActions(document.getElementById('commercial-portfolio-action-rail'), payload, activeLens, activeScenario, activeTargetModel)" in js
    assert "activeLens = 'risk';" in js
    assert "activeScenario = 'chip';" in js


def test_commercial_number_params_use_declared_defaults_when_query_is_missing():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "if (!params.has(key)) return fallback;" in js
    assert "targetWeight = commercialNumberParam(params, 'target', 35, 20, 45)" in js
    assert "driftTolerance = commercialNumberParam(params, 'drift', 5, 2, 15)" in js


def test_research_workbench_marks_decision_tracking_source_and_retry():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const workbenchDataStatusRoot = document.getElementById('commercial-workbench-data-status')" in js
    assert "renderCommercialDataStatus(workbenchDataStatusRoot, { tone: 'loading', label: 'Loading decision tracking'" in js
    assert "const trackingPromise = jsonRequest('/api/decision-tracking').then(payload => ({ payload, source: 'live' })).catch(error => ({ payload: null, source: 'fallback', error }))" in js
    assert "renderCommercialDataStatus(workbenchDataStatusRoot, workbenchDataStatus(trackingSource, rows.length))" in js
    assert "data-commercial-retry=\"workbench\"" in js


def test_stock_detail_marks_snapshot_source_and_retry():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const stockDataStatusRoot = document.getElementById('commercial-stock-data-status')" in js
    assert "let snapshot = fallbackSnapshot, snapshotSource = 'fallback'" in js
    assert "snapshotSource = 'live';" in js
    assert "snapshotSource = 'fallback';" in js
    assert "renderCommercialDataStatus(stockDataStatusRoot, stockDataStatus(snapshotSource, normalized))" in js
    assert "data-commercial-retry=\"stock\"" in js


def test_portfolio_dashboard_marks_risk_source_and_retry():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const portfolioDataStatusRoot = document.getElementById('commercial-portfolio-data-status')" in js
    assert "let lastPayload = fallbackPortfolio, portfolioSource = 'fallback'" in js
    assert "portfolioSource = 'live';" in js
    assert "portfolioSource = 'fallback';" in js
    assert "renderCommercialDataStatus(portfolioDataStatusRoot, portfolioDataStatus(portfolioSource, lastPayload))" in js
    assert "data-commercial-retry=\"portfolio\"" in js


def test_commercial_pages_attach_mutation_token_to_portfolio_risk_post():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "/api/client-config" in js
    assert "mutation_token" in js
    assert "mutation_header" in js
    assert "X-Mutation-Token" in js
    assert "withMutationHeader" in js


def test_research_workbench_is_optimized_for_decision_operations():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-filter"' in html
    assert 'data-workbench-filter="alerts"' in html
    assert 'id="commercial-workbench-market-pulse"' in html
    assert 'id="commercial-workbench-alerts"' in html
    assert "filterWorkbenchRows" in js
    assert "renderWorkbenchAlerts" in js
    assert "data-workbench-filter" in js
    assert 'id="commercial-workbench-views"' in html
    assert 'data-workbench-view="valuation"' in html
    assert 'id="commercial-workbench-inline-alert-builder"' in html
    assert "renderWorkbenchViewSummary" in js
    assert "renderAlertBuilder" in js
    assert 'id="commercial-workbench-command"' in html
    assert 'id="commercial-workbench-news"' in html
    assert 'id="commercial-workbench-notes"' in html
    assert "renderWorkbenchNews" in js
    assert "renderTickerNotes" in js
    assert "applyWorkbenchSearch" in js


def test_research_workbench_command_search_opens_common_stock_aliases():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "WORKBENCH_SEARCH_ALIASES" in js
    assert "resolveWorkbenchCommandTicker" in js
    assert "virtualWorkbenchRow" in js
    assert "台積" in js
    assert "commandQuery = document.getElementById('commercial-workbench-command')?.value || ''" in js
    assert "filtered.length ? filtered : rows" not in js


def test_research_workbench_has_competitor_grade_watchlist_operations():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-column-set"' in html
    assert 'data-workbench-column-set="fundamental"' in html
    assert 'id="commercial-workbench-bulk-actions"' in html
    assert 'id="commercial-workbench-insight-queue"' in html
    assert "renderWorkbenchColumnSet" in js
    assert "renderWorkbenchBulkActions" in js
    assert "renderWorkbenchInsightQueue" in js
    assert "virtualWorkbenchRow(activeTicker, activeTicker)" in js
    assert "data-workbench-column-set" in js
    assert "const trackingPromise = jsonRequest('/api/decision-tracking').then(payload => ({ payload, source: 'live' })).catch(error => ({ payload: null, source: 'fallback', error }))" in js
    assert "trackingSource = trackingResult.source" in js
    assert "rows = trackingRows(trackingResult.payload)" in js
    assert ".commercial-operation-grid" in css
    assert ".commercial-command-bar" in css


def test_research_workbench_has_saved_views_formula_lab_and_alert_manager():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-saved-views"' in html
    assert 'id="commercial-workbench-formula-lab"' in html
    assert 'id="commercial-workbench-alert-manager"' in html
    assert "renderSavedWorkbenchViews" in js
    assert "renderFormulaLab" in js
    assert "renderAlertManager" in js
    assert "persistWorkbenchView" in js
    assert "stock-agent-commercial-workbench-view" in js
    assert ".commercial-formula-lab" in css
    assert ".commercial-alert-manager" in css


def test_research_workbench_has_grouped_summary_event_calendar_and_screener_rules():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-section-summary"' in html
    assert 'id="commercial-workbench-event-calendar"' in html
    assert 'id="commercial-workbench-screener-rules"' in html
    assert "renderWatchlistSectionSummary" in js
    assert "renderWatchlistEventCalendar" in js
    assert "renderScreenerRuleStack" in js
    assert "Summary Rows" in js
    assert "Earnings / News" in js
    assert ".commercial-section-summary" in css
    assert ".commercial-screener-rules" in css


def test_research_workbench_has_sortable_exportable_watchlist_table():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-table-toolbar"' in html
    assert 'id="commercial-workbench-export-preview"' in html
    assert 'data-workbench-export-csv' in html
    assert "sortWorkbenchRows" in js
    assert "renderWorkbenchTableToolbar" in js
    assert "exportWorkbenchCsv" in js
    assert "data-workbench-sort" in js
    assert "aria-sort" in js
    assert ".commercial-table-toolbar" in css
    assert ".commercial-export-preview" in css


def test_research_workbench_has_multi_select_compare_basket():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-compare-basket"' in html
    assert "data-workbench-select" in js
    assert "renderCompareBasket" in js
    assert "toggleCompareTicker" in js
    assert "selectedCompareTickers" in js
    assert "Compare Basket" in js
    assert ".commercial-compare-basket" in css
    assert ".commercial-select-cell" in css


def test_research_workbench_has_relative_compare_chart_for_selected_symbols():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-compare-chart"' in html
    assert "renderWorkbenchCompareChart" in js
    assert "Relative Performance" in js
    assert "Benchmark" in js
    assert "selectedCompareTickers" in js
    assert ".commercial-compare-chart" in css
    assert ".commercial-compare-line" in css


def test_research_workbench_has_watchlist_heatmap_scan_view():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-heatmap"' in html
    assert "renderWatchlistHeatmap" in js
    assert "Watchlist Heatmap" in js
    assert "data-heatmap-ticker" in js
    assert "heatmapToneForReturn" in js
    assert ".commercial-watchlist-heatmap" in css
    assert ".commercial-heatmap-tile" in css


def test_research_workbench_has_priority_matrix_for_action_ordering():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-priority-matrix"' in html
    assert "renderWatchlistPriorityMatrix" in js
    assert "priorityScoreForWorkbenchRow" in js
    assert "Priority Matrix" in js
    assert "Impact" in js
    assert "Urgency" in js
    assert "data-priority-ticker" in js
    assert ".commercial-priority-matrix" in css
    assert ".commercial-priority-card" in css


def test_research_workbench_has_client_ready_report_pack():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-report-pack"' in html
    assert "renderWatchlistReportPack" in js
    assert "Client-Ready Report Pack" in js
    assert "Research Reports" in js
    assert "data-report-pack-ticker" in js
    assert "priorityScoreForWorkbenchRow" in js
    assert ".commercial-report-pack" in css
    assert ".commercial-report-pack-item" in css


def test_research_workbench_has_market_briefing_tape_workflow():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-briefing-tape"' in html
    assert "renderMarketBriefingTape" in js
    assert "Market Briefing Tape" in js
    assert "Open Brief" in js
    assert "Filing / Transcript" in js
    assert "Close Review" in js
    assert "data-briefing-ticker" in js
    assert ".commercial-briefing-tape" in css
    assert ".commercial-briefing-item" in css


def test_research_workbench_has_dashboard_preset_workspace_modes():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-layout-presets"' in html
    assert "renderWorkbenchLayoutPresets" in js
    assert "applyWorkbenchDashboardPreset" in js
    assert "Dashboard Presets" in js
    assert "Research Desk" in js
    assert "News Monitor" in js
    assert "Advisor Report" in js
    assert "data-dashboard-preset" in js
    assert ".commercial-dashboard-presets" in css
    assert ".commercial-dashboard-preset" in css


def test_research_workbench_has_screen_builder_for_universe_presets():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-screen-builder"' in html
    assert "renderWorkbenchScreenBuilder" in js
    assert "applyWorkbenchScreenPreset" in js
    assert "Screen Builder" in js
    assert "High Conviction" in js
    assert "Earnings Soon" in js
    assert "Risk Reset" in js
    assert "data-screen-preset" in js
    assert ".commercial-screen-builder" in css
    assert ".commercial-screen-preset" in css
    assert ".commercial-screen-rule" in css


def test_research_workbench_has_opportunity_radar_for_new_ideas():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-opportunity-radar"' in html
    assert "renderWorkbenchOpportunityRadar" in js
    assert "Opportunity Radar" in js
    assert "Idea Match" in js
    assert "Add to Watchlist" in js
    assert "Screen Score" in js
    assert "data-opportunity-ticker" in js
    assert ".commercial-opportunity-radar" in css
    assert ".commercial-opportunity-card" in css


def test_research_workbench_has_market_regime_overlay():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-market-regime"' in html
    assert "renderWorkbenchMarketRegimeOverlay" in js
    assert "Market Regime Overlay" in js
    assert "Rates" in js
    assert "FX" in js
    assert "Sector Breadth" in js
    assert "Regime Impact" in js
    assert "data-market-regime" in js
    assert ".commercial-market-regime" in css
    assert ".commercial-regime-signal" in css


def test_research_workbench_has_advanced_watchlist_summary():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-advanced-watchlist"' in html
    assert "renderWorkbenchAdvancedWatchlist" in js
    assert "Advanced Watchlist" in js
    assert "Distribution" in js
    assert "Summary Rows" in js
    assert "Currency Toggle" in js
    assert "Median Return" in js
    assert "data-watchlist-advanced" in js
    assert ".commercial-advanced-watchlist" in css
    assert ".commercial-advanced-metric" in css


def test_research_workbench_has_heatmap_display_controls():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-heatmap-controls"' in html
    assert "renderWorkbenchHeatmapControls" in js
    assert "Heatmap Controls" in js
    assert "Size By" in js
    assert "Color By" in js
    assert "Group By" in js
    assert "Display Value" in js
    assert "Color Scheme" in js
    assert "Legend" in js
    assert "data-heatmap-control" in js
    assert ".commercial-heatmap-controls" in css
    assert ".commercial-heatmap-control" in css


def test_research_workbench_column_sets_change_visible_table_columns():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "WORKBENCH_COLUMN_SETS" in js
    assert "columnsForWorkbenchSet" in js
    assert "workbenchCellValue" in js
    assert "activeColumnSet" in js
    assert "renderDecisionTable(document.getElementById('commercial-workbench-table'), visibleRows, sortState, selectedCompareTickers, activeColumnSet)" in js
    for label in ("Target Gap", "Quality", "Next Event", "Risk Flag"):
        assert label in js
    assert ".commercial-column-chip" in css


def test_research_workbench_has_watchlist_flag_board():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-flag-board"' in html
    assert 'data-workbench-flag="priority"' in html
    assert "renderWatchlistFlagBoard" in js
    assert "flagForWorkbenchRow" in js
    assert "activeFlag" in js
    assert "data-workbench-flag" in js
    assert "Flagged Symbols" in js
    assert ".commercial-flag-board" in css
    assert ".commercial-flag-dot" in css


def test_research_workbench_has_symbol_details_dock_for_selected_ticker():
    html = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-symbol-details"' in html
    assert "renderWorkbenchSymbolDetails" in js
    assert "Mini Trend" in js
    assert "Flash News" in js
    assert "Key Stats" in js
    assert "activeTicker" in js
    assert ".commercial-symbol-details" in css
    assert ".commercial-mini-sparkline" in css


def test_research_workbench_clicking_ticker_immediately_shows_loading_snapshot():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "renderSnapshotLoading" in js
    assert "讀取快照" in js
    assert "renderSnapshotLoading(normalized" in js
    assert js.index("renderSnapshotLoading(normalized") < js.index("fetchSnapshot(normalized)")
    assert ".commercial-quality.is-loading" in css


def test_research_workbench_default_screen_keeps_tracking_rows_clickable():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const initialScreenPreset = validCommercialChoice(params.get('screen'), ['conviction', 'event', 'risk'], 'conviction')" in js
    assert "const initialScreenConfig = workbenchScreenPresetConfig(initialScreenPreset)" in js
    assert "conviction: { label: 'High Conviction', view: 'valuation', columnSet: 'fundamental', filter: 'all'" in js
    assert "renderDecisionTable(document.getElementById('commercial-workbench-table'), visibleRows" in js


def test_research_workbench_live_tracking_defaults_to_first_real_row_without_url_ticker():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const hasInitialTickerParam = params.has('ticker');" in js
    assert "let activeTicker = normalizeTicker(hasInitialTickerParam ? params.get('ticker') : rows[0]?.ticker || '2330.TW');" in js

    apply_filter = re.search(
        r"async function applyWorkbenchFilter\(\) \{(?P<body>.*?)\n            document\.querySelectorAll\('\[data-workbench-view\]'\)",
        js,
        re.S,
    )
    assert apply_filter is not None
    body = apply_filter.group("body")
    assert "const contextTicker = hasInitialTickerParam ? normalizeTicker(params.get('ticker')) : '';" in body
    assert "readCommercialParams().has('ticker')" not in body
    assert "activeTicker = visibleRows[0]?.ticker || rows[0]?.ticker || activeTicker;" in body


def test_research_workbench_mobile_table_keeps_ticker_buttons_clickable():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    for selector, expected in (
        ("#commercial-workbench-table .commercial-table", "width: 100%;"),
        ("#commercial-workbench-table .commercial-table thead", "display: none;"),
        ("#commercial-workbench-table .commercial-table tbody", "display: grid;"),
        ("#commercial-workbench-table .commercial-table tr", "grid-template-columns: 44px minmax(0, 1fr);"),
        ("#commercial-workbench-table .commercial-table td:nth-child(2)", "grid-column: 2;"),
        ("#commercial-workbench-table .commercial-table td:nth-child(n+3)", "grid-column: 1 / -1;"),
        ("#commercial-workbench-table .commercial-row-button", "position: relative;"),
    ):
        rule = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", mobile_css, re.S)
        assert rule is not None
        assert expected in rule.group("body")

    ticker_cell = re.search(r"#commercial-workbench-table \.commercial-table td:nth-child\(2\) \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert ticker_cell is not None
    assert "position: relative;" in ticker_cell.group("body")
    assert "z-index: 4;" in ticker_cell.group("body")

    metric_cell = re.search(r"#commercial-workbench-table \.commercial-table td:nth-child\(n\+3\) \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert metric_cell is not None
    assert "position: relative;" in metric_cell.group("body")
    assert "z-index: 1;" in metric_cell.group("body")

    ticker_button = re.search(r"#commercial-workbench-table \.commercial-row-button \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert ticker_button is not None
    assert "z-index: 3;" in ticker_button.group("body")
    assert "pointer-events: auto;" in ticker_button.group("body")

    ticker_text = re.search(
        r"#commercial-workbench-table \.commercial-row-button strong,\n"
        r"  #commercial-workbench-table \.commercial-row-button span,\n"
        r"  #commercial-workbench-table \.commercial-row-button em \{(?P<body>.*?)\n  \}",
        mobile_css,
        re.S,
    )
    assert ticker_text is not None
    assert "overflow: visible;" in ticker_text.group("body")
    assert "text-overflow: clip;" in ticker_text.group("body")
    assert "white-space: normal;" in ticker_text.group("body")
    assert "overflow-wrap: anywhere;" in ticker_text.group("body")


def test_research_workbench_mobile_watchlist_queue_allows_long_names_to_wrap():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    watchlist_text = re.search(
        r"\.commercial-three-column \.commercial-list \.commercial-row-button strong,\n"
        r"  \.commercial-three-column \.commercial-list \.commercial-row-button span,\n"
        r"  \.commercial-three-column \.commercial-list \.commercial-row-button em \{(?P<body>.*?)\n  \}",
        mobile_css,
        re.S,
    )
    assert watchlist_text is not None
    assert "overflow: visible;" in watchlist_text.group("body")
    assert "text-overflow: clip;" in watchlist_text.group("body")
    assert "white-space: normal;" in watchlist_text.group("body")
    assert "overflow-wrap: anywhere;" in watchlist_text.group("body")


def test_research_workbench_mobile_watchlist_scrolls_inside_table_container():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    table_container = re.search(r"#commercial-workbench-table \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert table_container is not None
    assert "max-height: min(620px, 72vh);" in table_container.group("body")
    assert "overflow: auto;" in table_container.group("body")
    assert "overscroll-behavior: contain;" in table_container.group("body")
    assert "-webkit-overflow-scrolling: touch;" in table_container.group("body")
    assert "scrollbar-gutter: stable;" in table_container.group("body")


def test_stock_detail_is_optimized_for_single_stock_research():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-stock-scorecard"' in html
    assert 'id="commercial-stock-peer-table"' in html
    assert 'data-stock-tab="analysts"' in html
    assert 'data-stock-tab="technicals"' in html
    assert 'data-stock-tab="thesis"' in html
    assert "renderStockScorecard" in js
    assert "renderPeerComparison" in js
    assert "分析師分歧" in js
    assert 'id="commercial-stock-factor-grades"' in html
    assert 'id="commercial-stock-ratings-strip"' in html
    assert "renderFactorGrades" in js
    assert "renderRatingsStrip" in js
    for factor in ("Value", "Growth", "Profitability", "Momentum", "EPS Revisions"):
        assert factor in js
    assert 'id="commercial-stock-earnings-panel"' in html
    assert 'id="commercial-stock-valuation-band"' in html
    assert 'data-stock-tab="ownership"' in html
    assert 'role="tab"' in html
    assert "renderEarningsPanel" in js
    assert "renderValuationBand" in js
    assert "renderOwnershipInsight" in js
    assert "setAttribute('aria-selected'" in js


def test_stock_detail_has_decision_brief_and_catalyst_workflow():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-decision-brief"' in html
    assert 'id="commercial-stock-catalysts"' in html
    assert 'id="commercial-stock-risk-reward"' in html
    assert "renderDecisionBrief" in js
    assert "renderCatalystCalendar" in js
    assert "renderRiskRewardPanel" in js
    assert "Risk / Reward" in js
    assert ".commercial-decision-brief" in css
    assert ".commercial-catalyst-list" in css


def test_stock_detail_has_revisions_peer_matrix_and_financial_trend():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-revision-timeline"' in html
    assert 'id="commercial-stock-peer-matrix"' in html
    assert 'id="commercial-stock-financial-trend"' in html
    assert "renderRevisionTimeline" in js
    assert "renderPeerMatrix" in js
    assert "renderFinancialTrend" in js
    assert "Revision Timeline" in js
    assert ".commercial-revision-timeline" in css
    assert ".commercial-peer-matrix" in css


def test_stock_detail_has_quant_history_valuation_factsheet_and_report_outline():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-rating-history"' in html
    assert 'id="commercial-stock-valuation-factsheet"' in html
    assert 'id="commercial-stock-report-outline"' in html
    assert "renderQuantRatingHistory" in js
    assert "renderValuationFactsheet" in js
    assert "renderReportOutline" in js
    assert "Quant Rating History" in js
    assert "Report Outline" in js
    assert ".commercial-rating-history" in css
    assert ".commercial-report-outline" in css


def test_stock_detail_has_interactive_price_range_controls():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-chart-controls"' in html
    assert 'id="commercial-stock-price-chart"' in html
    assert 'data-stock-range="1M"' in html
    assert 'data-stock-range="1Y"' in html
    assert "renderStockChartControls" in js
    assert "renderPriceRangeChart" in js
    assert "setStockRange" in js
    assert "data-stock-range" in js
    assert ".commercial-chart-toolbar" in css
    assert ".commercial-price-chart" in css


def test_stock_detail_has_bull_base_bear_scenario_controls():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-scenario-controls"' in html
    assert 'id="commercial-stock-scenario-panel"' in html
    assert 'data-stock-scenario="bear"' in html
    assert 'data-stock-scenario="bull"' in html
    assert "renderStockScenarioControls" in js
    assert "renderStockScenarioPanel" in js
    assert "setStockScenario" in js
    assert "Bull / Base / Bear" in js
    assert ".commercial-scenario-panel" in css


def test_stock_detail_has_research_readiness_checklist():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-research-readiness"' in html
    assert "renderResearchReadiness" in js
    assert "Research Readiness" in js
    for item in ("Price", "Valuation", "Peers", "Scenario", "Thesis"):
        assert item in js
    assert ".commercial-readiness-list" in css
    assert ".commercial-readiness-score" in css


def test_stock_detail_has_rating_alert_presets():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-rating-alerts"' in html
    assert 'data-stock-alert-preset="downgrade"' in html
    assert "renderStockRatingAlerts" in js
    assert "setStockAlertPreset" in js
    assert "Rating Alerts" in js
    assert "Quant downgrade" in js
    assert ".commercial-rating-alerts" in css


def test_stock_detail_has_key_stats_and_sector_percentile_ranks():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-key-stats"' in html
    assert 'id="commercial-stock-percentile-ranks"' in html
    assert "renderStockKeyStats" in js
    assert "renderStockPercentileRanks" in js
    assert "52W Range" in js
    assert "Sector Percentile" in js
    assert "sectorPercentileRank" in js
    assert ".commercial-key-stats" in css
    assert ".commercial-percentile-ranks" in css


def test_stock_detail_surfaces_market_facts_near_top_like_competitor_snapshots():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-stock-market-facts" class="commercial-market-facts"' in stock
    assert 'aria-label="單股關鍵市場資訊"' in stock
    assert stock.index('id="commercial-stock-core-surface"') < stock.index('id="commercial-stock-market-facts"') < stock.index('id="commercial-stock-view-rail"')
    assert "commercial-stock-market-facts" not in workbench
    assert "commercial-stock-market-facts" not in portfolio

    for selector in (
        ".commercial-market-facts",
        ".commercial-market-facts-copy",
        ".commercial-market-facts-grid",
        ".commercial-market-fact",
        ".commercial-market-fact.is-positive",
        ".commercial-market-fact.is-warning",
    ):
        assert selector in css

    facts = re.search(r"\.commercial-market-facts \{(?P<body>.*?)\n\}", css, re.S)
    assert facts is not None
    assert "order: 3;" in facts.group("body")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_facts = re.search(r"\.commercial-market-facts \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_facts is not None
    assert "grid-template-columns: 1fr;" in mobile_facts.group("body")
    assert "padding: 8px;" in mobile_facts.group("body")

    mobile_grid = re.search(r"\.commercial-market-facts-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_grid is not None
    assert "display: grid;" in mobile_grid.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in mobile_grid.group("body")
    assert "overflow-x: visible;" in mobile_grid.group("body")

    mobile_fact = re.search(r"\.commercial-market-fact \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_fact is not None
    assert "width: 100%;" in mobile_fact.group("body")
    assert "min-width: 0;" in mobile_fact.group("body")
    assert "min-height: 44px;" in mobile_fact.group("body")

    for required in (
        "function stockMarketFactRows(snapshot)",
        "function renderStockMarketFacts(snapshot)",
        "renderStockMarketFacts(snapshot)",
        "commercial-stock-market-facts",
        "'.commercial-market-facts'",
        "52W Range",
        "Market Cap",
        "P/E",
        "Volume",
        "Beta",
        "Dividend",
    ):
        assert required in js


def test_workbench_and_portfolio_surface_distinct_first_screen_workflows():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-decision-queue" class="commercial-decision-queue"' in workbench
    assert 'aria-label="追蹤表即點即看決策隊列"' in workbench
    assert workbench.index('id="commercial-workbench-core-surface"') < workbench.index('id="commercial-workbench-decision-queue"') < workbench.index('id="commercial-workbench-view-rail"')
    assert "commercial-workbench-decision-queue" not in stock
    assert "commercial-workbench-decision-queue" not in portfolio

    assert 'id="commercial-portfolio-health-strip" class="commercial-portfolio-health-strip"' in portfolio
    assert 'aria-label="組合持股與風險快照"' in portfolio
    assert portfolio.index('id="commercial-portfolio-core-surface"') < portfolio.index('id="commercial-portfolio-health-strip"') < portfolio.index('id="commercial-portfolio-view-rail"')
    assert "commercial-portfolio-health-strip" not in workbench
    assert "commercial-portfolio-health-strip" not in stock

    for selector in (
        ".commercial-decision-queue",
        ".commercial-decision-queue-copy",
        ".commercial-decision-queue-list",
        ".commercial-decision-queue-row",
        ".commercial-decision-queue-row.is-active",
        ".commercial-decision-queue-row.is-warning",
        ".commercial-portfolio-health-strip",
        ".commercial-portfolio-health-copy",
        ".commercial-portfolio-health-metrics",
        ".commercial-portfolio-health-holdings",
        ".commercial-portfolio-health-card",
        ".commercial-portfolio-health-action",
    ):
        assert selector in css

    queue = re.search(r"\.commercial-decision-queue \{(?P<body>.*?)\n\}", css, re.S)
    assert queue is not None
    assert "order: 3;" in queue.group("body")
    assert "grid-template-columns: minmax(180px, 0.24fr) minmax(0, 1fr) minmax(160px, 0.18fr);" in queue.group("body")

    health_blocks = re.findall(r"\.commercial-portfolio-health-strip \{(?P<body>.*?)\n\}", css, re.S)
    assert health_blocks
    assert any("order: 3;" in body for body in health_blocks)
    assert any("grid-template-columns: minmax(180px, 0.2fr) minmax(0, 1fr) minmax(280px, 0.28fr);" in body for body in health_blocks)

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-decision-queue,\n  .commercial-portfolio-health-strip {" in mobile_css
    mobile_top = re.search(r"\.commercial-decision-queue,\n  \.commercial-portfolio-health-strip \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_top is not None
    assert "grid-template-columns: 1fr;" in mobile_top.group("body")
    assert "padding: 8px;" in mobile_top.group("body")

    assert ".commercial-decision-queue-list,\n  .commercial-portfolio-health-metrics,\n  .commercial-portfolio-health-holdings {" in mobile_css
    mobile_grid = re.search(
        r"\.commercial-decision-queue-list,\n  \.commercial-portfolio-health-metrics,\n  \.commercial-portfolio-health-holdings \{(?P<body>.*?)\n  \}",
        mobile_css,
        re.S,
    )
    assert mobile_grid is not None
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in mobile_grid.group("body")
    assert "overflow-x: visible;" in mobile_grid.group("body")

    for required in (
        "function workbenchDecisionQueueRows(rows, activeTicker)",
        "function renderWorkbenchDecisionQueue(root, rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function portfolioHealthStripItems(payload, activeLens, activeScenario, activeTargetModel)",
        "function renderPortfolioHealthStrip(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "renderWorkbenchDecisionQueue(document.getElementById('commercial-workbench-decision-queue')",
        "renderPortfolioHealthStrip(document.getElementById('commercial-portfolio-health-strip')",
        "commercial-workbench-decision-queue",
        "commercial-portfolio-health-strip",
        "data-commercial-ticker",
        "data-commercial-portfolio-health-target",
        "Decision Queue",
        "Portfolio Health Strip",
        "Top Holding",
        "Risk Flags",
        "Model Drift",
    ):
        assert required in js
    assert js.count("renderWorkbenchCoreSurface(document.getElementById('commercial-workbench-core-surface'), visibleRows.length ? visibleRows : rows, activeTicker, activeView, currentFilter, activeColumnSet)") >= 2


def test_three_pages_add_first_screen_handoff_strips_for_shareable_outputs():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    pages = {
        "workbench": (workbench, "commercial-workbench-decision-queue", "commercial-workbench-handoff-strip", "commercial-workbench-view-rail", "追蹤表交付摘要"),
        "stock": (stock, "commercial-stock-market-facts", "commercial-stock-handoff-strip", "commercial-stock-view-rail", "單股研究交付摘要"),
        "portfolio": (portfolio, "commercial-portfolio-health-strip", "commercial-portfolio-handoff-strip", "commercial-portfolio-view-rail", "組合健檢交付摘要"),
    }
    for _, (html, previous_id, handoff_id, next_id, aria_label) in pages.items():
        assert f'id="{handoff_id}" class="commercial-handoff-strip"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{previous_id}"') < html.index(f'id="{handoff_id}"') < html.index(f'id="{next_id}"')
        for other_id in {item[2] for item in pages.values()} - {handoff_id}:
            assert f'id="{other_id}"' not in html

    for selector in (
        ".commercial-handoff-strip",
        ".commercial-handoff-copy",
        ".commercial-handoff-metrics",
        ".commercial-handoff-metric",
        ".commercial-handoff-metric.is-positive",
        ".commercial-handoff-metric.is-warning",
        ".commercial-handoff-actions",
        ".commercial-handoff-action",
        ".commercial-handoff-action.is-primary",
        ".commercial-handoff-status",
    ):
        assert selector in css

    handoff = re.search(r"\.commercial-handoff-strip \{(?P<body>.*?)\n\}", css, re.S)
    assert handoff is not None
    assert "order: 3;" in handoff.group("body")
    assert "grid-template-columns: minmax(180px, 0.22fr) minmax(0, 1fr) minmax(220px, 0.24fr);" in handoff.group("body")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_handoff = re.search(r"\.commercial-handoff-strip \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_handoff is not None
    assert "grid-template-columns: 1fr;" in mobile_handoff.group("body")
    assert "padding: 8px;" in mobile_handoff.group("body")

    mobile_actions = re.search(r"\.commercial-handoff-metrics,\n  \.commercial-handoff-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_actions is not None
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in mobile_actions.group("body")
    assert "overflow-x: visible;" in mobile_actions.group("body")

    for required in (
        "function commercialHandoffMetric(label, value, detail, tone = '')",
        "function commercialHandoffAction(id, label, target, primary = false)",
        "function commercialHandoffSummary(config)",
        "function renderCommercialHandoffStrip(root, config)",
        "function bindCommercialHandoffStrip(root)",
        "function workbenchHandoffStripConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockHandoffStripConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioHandoffStripConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "renderCommercialHandoffStrip(document.getElementById('commercial-workbench-handoff-strip'), workbenchHandoffStripConfig",
        "renderCommercialHandoffStrip(document.getElementById('commercial-stock-handoff-strip'), stockHandoffStripConfig",
        "renderCommercialHandoffStrip(document.getElementById('commercial-portfolio-handoff-strip'), portfolioHandoffStripConfig",
        "bindCommercialHandoffStrip(document.getElementById('commercial-workbench-handoff-strip'))",
        "bindCommercialHandoffStrip(document.getElementById('commercial-stock-handoff-strip'))",
        "bindCommercialHandoffStrip(document.getElementById('commercial-portfolio-handoff-strip'))",
        "data-commercial-handoff-target",
        "data-commercial-handoff-copy",
        "Watchlist Brief",
        "Stock Memo",
        "Portfolio Review",
    ):
        assert required in js


def test_three_pages_surface_competitor_grade_first_screen_previews():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    pages = {
        "workbench": (workbench, "commercial-workbench-handoff-strip", "commercial-workbench-competitive-strip", "commercial-workbench-view-rail", "追蹤表競品級資料格摘要"),
        "stock": (stock, "commercial-stock-handoff-strip", "commercial-stock-competitive-strip", "commercial-stock-view-rail", "單股競品級因子摘要"),
        "portfolio": (portfolio, "commercial-portfolio-handoff-strip", "commercial-portfolio-competitive-strip", "commercial-portfolio-view-rail", "組合競品級分析摘要"),
    }
    for _, (html, previous_id, preview_id, next_id, aria_label) in pages.items():
        assert f'id="{preview_id}" class="commercial-competitive-strip"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{previous_id}"') < html.index(f'id="{preview_id}"') < html.index(f'id="{next_id}"')
        for other_id in {item[2] for item in pages.values()} - {preview_id}:
            assert f'id="{other_id}"' not in html

    for selector in (
        ".commercial-competitive-strip",
        ".commercial-competitive-copy",
        ".commercial-competitive-metrics",
        ".commercial-competitive-metric",
        ".commercial-competitive-metric.is-positive",
        ".commercial-competitive-metric.is-warning",
        ".commercial-competitive-actions",
        ".commercial-competitive-action",
        ".commercial-competitive-action.is-primary",
        ".commercial-competitive-status",
    ):
        assert selector in css

    preview = re.search(r"\.commercial-competitive-strip \{(?P<body>.*?)\n\}", css, re.S)
    assert preview is not None
    assert "order: 3;" in preview.group("body")
    assert "grid-template-columns: minmax(170px, 0.2fr) minmax(0, 1fr) minmax(220px, 0.24fr);" in preview.group("body")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_preview = re.search(r"\.commercial-competitive-strip \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_preview is not None
    assert "grid-template-columns: 1fr;" in mobile_preview.group("body")
    assert "padding: 8px;" in mobile_preview.group("body")

    mobile_actions = re.search(r"\.commercial-competitive-metrics,\n  \.commercial-competitive-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_actions is not None
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in mobile_actions.group("body")
    assert "overflow-x: visible;" in mobile_actions.group("body")

    for required in (
        "function commercialCompetitiveMetric(label, value, detail, target, tone = '')",
        "function commercialCompetitiveAction(id, label, target, primary = false)",
        "function renderCommercialCompetitiveStrip(root, config)",
        "function bindCommercialCompetitiveStrip(root)",
        "function workbenchCompetitiveStripConfig(rows, activeTicker, activeColumnSet, sortState)",
        "function stockCompetitiveStripConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioCompetitiveStripConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "renderCommercialCompetitiveStrip(document.getElementById('commercial-workbench-competitive-strip'), workbenchCompetitiveStripConfig",
        "renderCommercialCompetitiveStrip(document.getElementById('commercial-stock-competitive-strip'), stockCompetitiveStripConfig",
        "renderCommercialCompetitiveStrip(document.getElementById('commercial-portfolio-competitive-strip'), portfolioCompetitiveStripConfig",
        "bindCommercialCompetitiveStrip(document.getElementById('commercial-workbench-competitive-strip'))",
        "bindCommercialCompetitiveStrip(document.getElementById('commercial-stock-competitive-strip'))",
        "bindCommercialCompetitiveStrip(document.getElementById('commercial-portfolio-competitive-strip'))",
        "data-commercial-competitive-target",
        "Advanced View",
        "Quant Factor Grades",
        "Holdings Analytics",
    ):
        assert required in js


def test_stock_detail_has_analyst_target_distribution():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-target-distribution"' in html
    assert "renderStockTargetDistribution" in js
    assert "Analyst Target Range" in js
    assert "Low Target" in js
    assert "Average Target" in js
    assert "High Target" in js
    assert "data-stock-target-marker" in js
    assert ".commercial-target-distribution" in css
    assert ".commercial-target-range" in css


def test_stock_detail_has_analyst_rating_breakdown():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-analyst-breakdown"' in html
    assert "renderStockAnalystBreakdown" in js
    assert "Analyst Rating Breakdown" in js
    assert "Strong Buy" in js
    assert "Hold" in js
    assert "data-analyst-rating" in js
    assert ".commercial-analyst-breakdown" in css
    assert ".commercial-analyst-rating-bar" in css


def test_stock_detail_has_financial_statements_explorer():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-financial-statements"' in html
    assert "renderStockFinancialStatements" in js
    assert "Financial Statements" in js
    assert "Income Statement" in js
    assert "Balance Sheet" in js
    assert "Cash Flow" in js
    assert 'data-stock-financial-statement="income"' in html
    assert "activeFinancialStatement" in js
    assert ".commercial-financial-statements" in css
    assert ".commercial-statement-table" in css


def test_stock_detail_has_dividend_safety_income_panel():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-dividend-safety"' in html
    assert "renderStockDividendSafety" in js
    assert "Dividend Safety" in js
    assert "Dividend Growth" in js
    assert "Payout Ratio" in js
    assert "data-dividend-grade" in js
    assert ".commercial-dividend-safety" in css
    assert ".commercial-dividend-grade" in css


def test_stock_detail_has_ownership_and_transcript_intelligence():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-ownership-transcripts"' in html
    assert "renderStockOwnershipTranscripts" in js
    assert "Ownership & Transcripts" in js
    assert "Institutional Ownership" in js
    assert "Insider Transactions" in js
    assert "Transcript Sentiment" in js
    assert "data-ownership-signal" in js
    assert ".commercial-ownership-transcripts" in css
    assert ".commercial-ownership-signal" in css


def test_stock_detail_has_actuals_consensus_surprise_snapshot():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-actuals-consensus"' in html
    assert "renderStockActualsConsensus" in js
    assert "Actuals & Consensus" in js
    assert "Revenue Surprise" in js
    assert "EPS Surprise" in js
    assert "Forward EPS" in js
    assert "data-consensus-metric" in js
    assert ".commercial-actuals-consensus" in css
    assert ".commercial-consensus-metric" in css


def test_stock_detail_has_estimate_revision_quality_panel():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-estimate-revisions"' in html
    assert "renderStockEstimateRevisionQuality" in js
    assert "Estimate Revision Quality" in js
    assert "EPS Revision Trend" in js
    assert "Revenue Revision Trend" in js
    assert "Analyst Drift" in js
    assert "Revision Breadth" in js
    assert "data-estimate-revision" in js
    assert ".commercial-estimate-revisions" in css
    assert ".commercial-revision-signal" in css


def test_stock_detail_has_dcf_sensitivity_matrix():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-dcf-sensitivity"' in html
    assert "renderStockDcfSensitivity" in js
    assert "DCF Sensitivity" in js
    assert "Discount Rate" in js
    assert "Terminal Growth" in js
    assert "Margin of Safety" in js
    assert "data-dcf-cell" in js
    assert ".commercial-dcf-sensitivity" in css
    assert ".commercial-dcf-cell" in css


def test_stock_detail_has_earnings_reaction_analyzer():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-earnings-reaction"' in html
    assert "renderStockEarningsReactionAnalyzer" in js
    assert "Earnings Reaction" in js
    assert "Expected Move" in js
    assert "Post-Earnings Drift" in js
    assert "Beat Reaction" in js
    assert "Miss Risk" in js
    assert "data-earnings-reaction" in js
    assert ".commercial-earnings-reaction" in css
    assert ".commercial-reaction-metric" in css


def test_stock_detail_has_rating_explainability_panel():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-rating-explainability"' in html
    assert "renderStockRatingExplainability" in js
    assert "Rating Explainability" in js
    assert "Quant Score" in js
    assert "Sector Average" in js
    assert "Factor Weight" in js
    assert "Disqualifier Check" in js
    assert "data-rating-explainability" in js
    assert ".commercial-rating-explainability" in css
    assert ".commercial-rating-factor" in css


def test_stock_detail_has_etf_exposure_snapshot():
    html = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-stock-etf-exposure"' in html
    assert "renderStockEtfExposure" in js
    assert "ETF Exposure" in js
    assert "ETF Count" in js
    assert "Fund Focus" in js
    assert "Market Value Held" in js
    assert "Weight in ETF" in js
    assert "data-etf-exposure" in js
    assert ".commercial-etf-exposure" in css
    assert ".commercial-etf-row" in css


def test_portfolio_dashboard_is_optimized_for_portfolio_health():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-lenses"' in html
    assert 'data-portfolio-lens="sector"' in html
    assert 'id="commercial-portfolio-rebalance"' in html
    assert 'id="commercial-portfolio-contribution"' in html
    assert "renderPortfolioLenses" in js
    assert "renderRebalancePlan" in js
    assert "data-portfolio-lens" in js
    assert 'id="commercial-portfolio-health-score"' in html
    assert 'id="commercial-portfolio-benchmark"' in html
    assert 'id="commercial-portfolio-holdings"' in html
    assert "renderPortfolioHealthScore" in js
    assert "renderBenchmarkComparison" in js
    assert "renderHoldingsDrilldown" in js
    assert 'id="commercial-portfolio-scenarios"' in html
    assert 'data-portfolio-scenario="rate"' in html
    assert 'id="commercial-portfolio-targets"' in html
    assert 'id="commercial-portfolio-style-map"' in html
    assert 'aria-selected="true"' in html
    assert "renderScenarioStress" in js
    assert "renderAllocationTargets" in js
    assert "renderStyleMap" in js


def test_portfolio_dashboard_has_xray_drilldown_and_rebalance_ticket():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-xray"' in html
    assert 'id="commercial-portfolio-overlap"' in html
    assert 'id="commercial-portfolio-rebalance-ticket"' in html
    assert "renderXrayBreakdown" in js
    assert "renderOverlapMap" in js
    assert "renderRebalanceTicket" in js
    assert "Asset Allocation" in js
    assert ".commercial-xray-grid" in css
    assert ".commercial-overlap-list" in css


def test_portfolio_dashboard_has_factor_correlation_and_whatif_analysis():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-factor-exposure"' in html
    assert 'id="commercial-portfolio-correlation-matrix"' in html
    assert 'id="commercial-portfolio-what-if"' in html
    assert "renderFactorExposure" in js
    assert "renderCorrelationMatrix" in js
    assert "renderPortfolioWhatIf" in js
    assert "What-if Rebalance" in js
    assert ".commercial-factor-exposure" in css
    assert ".commercial-correlation-matrix" in css


def test_portfolio_dashboard_has_risk_contribution_waterfall():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-risk-contribution"' in html
    assert "renderPortfolioRiskContribution" in js
    assert "Risk Contribution" in js
    assert "Top Holding" in js
    assert "Concentration Drag" in js
    assert "data-risk-contribution" in js
    assert ".commercial-risk-contribution" in css
    assert ".commercial-waterfall-bar" in css


def test_portfolio_dashboard_has_efficient_frontier_optimizer_view():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-efficient-frontier"' in html
    assert "renderPortfolioEfficientFrontier" in js
    assert "Efficient Frontier" in js
    assert "Current Portfolio" in js
    assert "Optimized" in js
    assert "Risk" in js
    assert "Return" in js
    assert "data-frontier-point" in js
    assert ".commercial-efficient-frontier" in css
    assert ".commercial-frontier-point" in css


def test_portfolio_dashboard_has_monte_carlo_outcome_projection():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-monte-carlo"' in html
    assert "renderPortfolioMonteCarlo" in js
    assert "Monte Carlo" in js
    assert "Survival Rate" in js
    assert "10th Percentile" in js
    assert "90th Percentile" in js
    assert "data-monte-carlo-band" in js
    assert ".commercial-monte-carlo" in css
    assert ".commercial-monte-carlo-band" in css


def test_portfolio_dashboard_has_drawdown_recovery_analysis():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-drawdown-recovery"' in html
    assert "renderPortfolioDrawdownRecovery" in js
    assert "Drawdown & Recovery" in js
    assert "Max Drawdown" in js
    assert "Recovery Months" in js
    assert "Stress Budget" in js
    assert "data-drawdown-metric" in js
    assert ".commercial-drawdown-recovery" in css
    assert ".commercial-drawdown-metric" in css


def test_portfolio_dashboard_has_risk_adjusted_performance_metrics():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-risk-adjusted"' in html
    assert "renderPortfolioRiskAdjustedPerformance" in js
    assert "Risk-Adjusted Performance" in js
    assert "Sharpe Ratio" in js
    assert "Volatility" in js
    assert "Beta" in js
    assert "IRR" in js
    assert "data-risk-adjusted-metric" in js
    assert ".commercial-risk-adjusted" in css
    assert ".commercial-risk-adjusted-metric" in css


def test_portfolio_dashboard_has_future_income_planner():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-future-income"' in html
    assert "renderPortfolioFutureIncomePlanner" in js
    assert "Future Income Planner" in js
    assert "Monthly Income" in js
    assert "Annual Income" in js
    assert "Yield Gap" in js
    assert "Cash Buffer" in js
    assert "data-future-income" in js
    assert ".commercial-future-income" in css
    assert ".commercial-income-bar" in css


def test_portfolio_dashboard_has_tax_aware_rebalance_panel():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-tax-rebalance"' in html
    assert "renderPortfolioTaxAwareRebalance" in js
    assert "Tax-Aware Rebalance" in js
    assert "Harvestable Loss" in js
    assert "Offset Gains" in js
    assert "Wash-sale Watch" in js
    assert "After-tax Drift" in js
    assert "data-tax-rebalance" in js
    assert ".commercial-tax-rebalance" in css
    assert ".commercial-tax-lot" in css


def test_portfolio_dashboard_has_goal_funding_plan():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-goal-funding"' in html
    assert "renderPortfolioGoalFundingPlan" in js
    assert "Goal Funding Plan" in js
    assert "Funding Ratio" in js
    assert "Withdrawal Runway" in js
    assert "Shortfall Risk" in js
    assert "Required Return" in js
    assert "data-goal-funding" in js
    assert ".commercial-goal-funding" in css
    assert ".commercial-goal-metric" in css


def test_portfolio_dashboard_has_stock_intersection_drilldown():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-stock-intersection"' in html
    assert "renderPortfolioStockIntersection" in js
    assert "Stock Intersection" in js
    assert "Look-through Exposure" in js
    assert "Duplicate Holding" in js
    assert "Fund Overlap" in js
    assert "Top Intersections" in js
    assert "data-stock-intersection" in js
    assert ".commercial-stock-intersection" in css
    assert ".commercial-intersection-row" in css


def test_portfolio_dashboard_has_trade_evaluator_panel():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-trade-evaluator"' in html
    assert "renderPortfolioTradeEvaluator" in js
    assert "Trade Evaluator" in js
    assert "Alpha Added" in js
    assert "Benchmark Drag" in js
    assert "Winner Contribution" in js
    assert "Decision Hit Rate" in js
    assert "data-trade-evaluator" in js
    assert ".commercial-trade-evaluator" in css
    assert ".commercial-trade-evaluator-row" in css


def test_portfolio_dashboard_has_benchmark_delta_fee_yield_and_action_checklist():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-benchmark-delta"' in html
    assert 'id="commercial-portfolio-fee-yield"' in html
    assert 'id="commercial-portfolio-action-checklist"' in html
    assert "renderBenchmarkDelta" in js
    assert "renderFeeYieldPanel" in js
    assert "renderActionChecklist" in js
    assert "Benchmark Delta" in js
    assert "Fee / Yield" in js
    assert ".commercial-benchmark-delta" in css
    assert ".commercial-action-checklist" in css


def test_portfolio_dashboard_has_adjustable_whatif_rebalance_controls():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-what-if-controls"' in html
    assert 'data-portfolio-target-weight' in html
    assert 'data-portfolio-drift-tolerance' in html
    assert "renderWhatIfControls" in js
    assert "applyPortfolioTargetWeight" in js
    assert "targetWeight" in js
    assert "driftTolerance" in js
    assert "Drift Tolerance" in js
    assert "Tolerance Breaches" in js
    assert ".commercial-whatif-controls" in css
    assert ".commercial-target-slider" in css


def test_portfolio_dashboard_has_execution_mode_and_order_queue():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-execution-mode"' in html
    assert 'id="commercial-portfolio-order-queue"' in html
    assert 'data-portfolio-execution-mode="trim"' in html
    assert "renderExecutionMode" in js
    assert "renderOrderQueue" in js
    assert "applyPortfolioExecutionMode" in js
    assert "Order Queue" in js
    assert ".commercial-order-queue" in css
    assert ".commercial-execution-mode" in css


def test_portfolio_dashboard_has_target_model_and_drift_panel():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-target-model"' in html
    assert 'id="commercial-portfolio-drift-panel"' in html
    assert 'data-portfolio-target-model="balanced"' in html
    assert "PORTFOLIO_TARGET_MODELS" in js
    assert "renderTargetModelSelector" in js
    assert "renderPortfolioDriftPanel" in js
    assert "applyPortfolioTargetModel" in js
    assert "Target Drift" in js
    assert ".commercial-target-model" in css
    assert ".commercial-drift-panel" in css


def test_portfolio_dashboard_has_trade_impact_panel():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-trade-impact"' in html
    assert "renderTradeImpactPanel" in js
    assert "Trade Impact" in js
    assert "estimatedTurnover" in js
    assert "After Cash" in js
    assert ".commercial-trade-impact" in css


def test_portfolio_dashboard_has_before_after_rebalance_allocation():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-before-after"' in html
    assert "renderPortfolioBeforeAfterAllocation" in js
    assert "Before / After Allocation" in js
    assert "Before" in js
    assert "After" in js
    assert "activeTargetModel" in js
    assert ".commercial-before-after" in css
    assert ".commercial-allocation-row" in css


def test_portfolio_dashboard_has_morningstar_style_box_visual():
    html = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert 'id="commercial-portfolio-style-box"' in html
    assert "renderPortfolioStyleBox" in js
    assert "Style Box" in js
    assert "Large Growth" in js
    assert "data-style-box-cell" in js
    assert ".commercial-style-box" in css
    assert ".commercial-style-box-cell" in css


def test_commercial_pages_surface_global_research_context_bar():
    pages = [
        (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8"),
        (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8"),
        (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8"),
    ]
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for html in pages:
        assert 'id="commercial-global-context"' in html
        assert 'class="commercial-context-bar"' in html
        assert html.index('id="commercial-global-context"') < html.index('class="commercial-delivery-bar"')

    assert ".commercial-context-bar" in css
    assert ".commercial-context-form" in css
    assert ".commercial-context-actions" in css
    assert ".commercial-context-link" in css
    assert ".commercial-context-link.is-active" in css
    assert ".commercial-context-input" in css
    assert ".commercial-context-metrics" in css
    assert ".commercial-context-metric" in css
    assert ".commercial-context-metric.is-positive" in css
    assert ".commercial-context-metric.is-warning" in css
    assert "function commercialPageUrl(pageName, ticker)" in js
    assert "function commercialContextMetricTone(value)" in js
    assert "function quoteContextMetrics(snapshot, row)" in js
    assert "function portfolioContextMetrics(payload, contextTicker, activeLens, activeScenario, activeTargetModel)" in js
    assert "function renderCommercialGlobalContext(root, state)" in js
    assert "const pendingInput = activeInput === document.activeElement ? activeInput.value : ''" in js
    assert "const inputValue = pendingInput && normalizeTicker(pendingInput) !== ticker ? pendingInput : ticker" in js
    assert "function bindCommercialGlobalContext(pageName, getTicker, onTicker)" in js
    assert "function syncCommercialContextTicker(ticker)" in js
    assert "state?.metrics" in js
    assert "commercial-context-metrics" in js
    assert "commercial-context-metric" in js
    assert "data-commercial-context-target=\"workbench\"" in js
    assert "data-commercial-context-target=\"stock\"" in js
    assert "data-commercial-context-target=\"portfolio\"" in js


def test_commercial_pages_surface_above_fold_decision_score_strips():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-score-strip"' in workbench
    assert 'id="commercial-stock-score-strip"' in stock
    assert 'id="commercial-portfolio-score-strip"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('id="commercial-global-context"') < html.index('class="commercial-score-strip"')
        assert html.index('class="commercial-score-strip"') < html.index('class="commercial-delivery-bar"')

    assert ".commercial-score-strip" in css
    assert ".commercial-score-strip-copy" in css
    assert ".commercial-score-card" in css
    assert ".commercial-score-card.is-positive" in css
    assert ".commercial-factor-pill" in css
    assert ".commercial-score-strip.is-portfolio" in css
    assert "function renderCommercialDecisionScoreStrip(root, config)" in js
    assert "function workbenchDecisionScores(rows, activeTicker, activeView)" in js
    assert "function stockDecisionScores(snapshot, currentTab, activeScenario)" in js
    assert "function portfolioDecisionScores(payload, activeLens, activeScenario, activeTargetModel)" in js


def test_commercial_pages_surface_page_specific_requirement_maps_above_fold():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-requirement-map"' in workbench
    assert 'id="commercial-stock-requirement-map"' in stock
    assert 'id="commercial-portfolio-requirement-map"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('id="commercial-global-context"') < html.index('class="commercial-requirement-map"')
        assert html.index('class="commercial-requirement-map"') < html.index('class="commercial-score-strip"')

    for selector in (
        ".commercial-requirement-map",
        ".commercial-requirement-map-copy",
        ".commercial-requirement-card",
        ".commercial-requirement-card.is-primary",
        ".commercial-requirement-card.is-warning",
        ".commercial-requirement-actions",
    ):
        assert selector in css

    assert "function renderCommercialRequirementMap(root, config)" in js
    assert "function workbenchRequirementMap(rows, activeTicker, activeView, currentFilter, activeColumnSet)" in js
    assert "function stockRequirementMap(snapshot, currentTab, activeScenario, activeRange)" in js
    assert "function portfolioRequirementMap(payload, activeLens, activeScenario, activeTargetModel)" in js
    assert "data-commercial-requirement-target" in js


def test_commercial_pages_surface_page_specific_actionable_answer_strips_above_fold():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-answer-strip"' in workbench
    assert 'id="commercial-stock-answer-strip"' in stock
    assert 'id="commercial-portfolio-answer-strip"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('class="commercial-requirement-map"') < html.index('class="commercial-answer-strip"')
        assert html.index('class="commercial-answer-strip"') < html.index('class="commercial-score-strip"')

    for selector in (
        ".commercial-answer-strip",
        ".commercial-answer-copy",
        ".commercial-answer-metrics",
        ".commercial-answer-action",
        ".commercial-answer-action.is-primary",
        ".commercial-answer-strip.is-portfolio",
    ):
        assert selector in css

    assert "function renderCommercialDecisionAnswer(root, config)" in js
    assert "function workbenchDecisionAnswer(rows, activeTicker, activeView, currentFilter)" in js
    assert "function stockDecisionAnswer(snapshot, currentTab, activeScenario, activeRange)" in js
    assert "function portfolioDecisionAnswer(payload, activeLens, activeScenario, activeTargetModel)" in js


def test_commercial_pages_surface_page_specific_plain_language_explain_strips_after_answer():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-explain-strip"' in workbench
    assert 'id="commercial-stock-explain-strip"' in stock
    assert 'id="commercial-portfolio-explain-strip"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('class="commercial-answer-strip"') < html.index('class="commercial-explain-strip"')
        assert html.index('class="commercial-explain-strip"') < html.index('class="commercial-trust-strip"')

    for selector in (
        ".commercial-explain-strip",
        ".commercial-explain-copy",
        ".commercial-explain-cards",
        ".commercial-explain-card",
        ".commercial-explain-card.is-warning",
        ".commercial-explain-card.is-live",
        ".commercial-explain-actions",
        ".commercial-explain-action",
        ".commercial-explain-action.is-primary",
        ".commercial-explain-strip.is-portfolio",
    ):
        assert selector in css

    for function_name in (
        "function renderCommercialExplainStrip(root, config)",
        "function workbenchExplainStrip(rows, activeTicker, activeView, currentFilter)",
        "function stockExplainStrip(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioExplainStrip(payload, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js


def test_research_workbench_explain_strip_translates_watchlist_reason_into_actions():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Explain the Watchlist", "Why Tracked", "What Changed", "Next Plain Step", "Open Snapshot Why", "Review Why Alerted"):
        assert label in js
    assert 'data-commercial-workbench-explain-view="valuation"' in js
    assert 'data-commercial-workbench-explain-filter="alerts"' in js
    assert 'data-commercial-workbench-explain-target="commercial-workbench-detail"' in js
    assert "const workbenchExplainTarget = button.dataset.commercialWorkbenchExplainTarget || button.dataset.commercialExplainTarget;" in js
    assert "renderCommercialExplainStrip(document.getElementById('commercial-workbench-explain-strip'), workbenchExplainStrip(visibleRows.length ? visibleRows : rows, activeTicker, activeView, currentFilter))" in js
    assert "scrollCommercialTaskTarget(workbenchExplainTarget);" in js


def test_stock_detail_explain_strip_translates_rating_financials_and_evidence():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Explain the Stock", "Rating Why", "Financial Context", "Evidence Trail", "Open Rating Why", "Open Financial Why"):
        assert label in js
    assert 'data-commercial-stock-explain-tab="analysts"' in js
    assert 'data-commercial-stock-explain-tab="financials"' in js
    assert 'data-commercial-stock-explain-coverage="fundamentals"' in js
    assert "const stockExplainCoverage = button.dataset.commercialStockExplainCoverage;" in js
    assert "activeCoverage = stockExplainCoverage;" in js
    assert "renderCommercialExplainStrip(document.getElementById('commercial-stock-explain-strip'), stockExplainStrip(snapshot, currentTab, activeScenario, activeCoverage))" in js


def test_portfolio_dashboard_explain_strip_translates_health_warnings_and_rebalance():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Explain Portfolio Health", "Health Why", "Risk Warning", "Rebalance Reason", "Open Health Why", "Open Rebalance Why"):
        assert label in js
    assert 'data-commercial-portfolio-explain-lens="risk"' in js
    assert 'data-commercial-portfolio-explain-lens="contribution"' in js
    assert 'data-commercial-portfolio-explain-target="commercial-portfolio-rebalance-ticket"' in js
    assert "const portfolioExplainLens = validCommercialChoice(button.dataset.commercialPortfolioExplainLens, ['sector', 'country', 'risk', 'contribution'], activeLens);" in js
    assert "activeLens = portfolioExplainLens;" in js
    assert "renderCommercialExplainStrip(document.getElementById('commercial-portfolio-explain-strip'), portfolioExplainStrip(payload, activeLens, activeScenario, activeTargetModel))" in js


def test_explain_strips_keep_mobile_actions_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    assert "@media (max-width: 560px)" in css
    mobile_css = css[css.index("@media (max-width: 560px)"):]

    assert ".commercial-explain-strip" in mobile_css
    assert ".commercial-explain-cards" in mobile_css
    explain_action = re.search(r"\.commercial-explain-action \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert explain_action is not None
    assert "min-height: 44px;" in explain_action.group("body")
    assert "width: 100%;" in explain_action.group("body")


def test_commercial_pages_surface_page_specific_data_trust_strips_near_answer():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-trust-strip"' in workbench
    assert 'id="commercial-stock-trust-strip"' in stock
    assert 'id="commercial-portfolio-trust-strip"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('class="commercial-answer-strip"') < html.index('class="commercial-trust-strip"')
        assert html.index('class="commercial-trust-strip"') < html.index('class="commercial-score-strip"')

    for selector in (
        ".commercial-trust-strip",
        ".commercial-trust-copy",
        ".commercial-trust-cards",
        ".commercial-trust-card",
        ".commercial-trust-action",
        ".commercial-trust-card.is-warning",
        ".commercial-trust-card.is-live",
        ".commercial-trust-strip.is-portfolio",
    ):
        assert selector in css

    assert "function renderCommercialDataTrustStrip(root, config)" in js
    assert "function workbenchTrustStrip(rows, trackingSource, activeTicker, activeView, currentFilter)" in js
    assert "function stockTrustStrip(snapshot, snapshotSource, currentTab, activeCoverage)" in js
    assert "function portfolioTrustStrip(payload, portfolioSource, activeLens, activeScenario, activeTargetModel)" in js


def test_research_workbench_trust_strip_surfaces_decision_freshness_and_source_actions():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Workbench Data Trust", "Decision Freshness", "Watchlist Coverage", "Alert Source", "Open Data Provenance"):
        assert label in js
    assert 'data-commercial-workbench-trust-action="provenance"' in js
    assert 'data-commercial-workbench-trust-action="coverage"' in js
    assert "renderCommercialDataTrustStrip(document.getElementById('commercial-workbench-trust-strip'), workbenchTrustStrip(visibleRows.length ? visibleRows : rows, trackingSource, activeTicker, activeView, currentFilter))" in js
    assert "scrollCommercialTaskTarget(button.dataset.commercialTrustTarget);" in js


def test_stock_detail_trust_strip_surfaces_quote_factor_and_analyst_coverage():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Stock Data Trust", "Quote Freshness", "Factor Coverage", "Analyst Consensus", "Open Factor Coverage"):
        assert label in js
    assert 'data-commercial-stock-trust-tab="analysts"' in js
    assert 'data-commercial-stock-trust-coverage="fundamentals"' in js
    assert "const stockTrustCoverage = button.dataset.commercialStockTrustCoverage;" in js
    assert "activeCoverage = stockTrustCoverage;" in js
    assert "renderCommercialDataTrustStrip(document.getElementById('commercial-stock-trust-strip'), stockTrustStrip(snapshot, snapshotSource, currentTab, activeCoverage))" in js


def test_portfolio_dashboard_trust_strip_surfaces_holdings_benchmark_and_thesis_gap():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Portfolio Data Trust", "Holding Source", "Benchmark Model", "Thesis Gaps", "Open Benchmark Drift"):
        assert label in js
    assert 'data-commercial-portfolio-trust-lens="risk"' in js
    assert 'data-commercial-portfolio-trust-target="commercial-portfolio-benchmark-delta"' in js
    assert "const portfolioTrustLens = validCommercialChoice(button.dataset.commercialPortfolioTrustLens, ['sector', 'country', 'risk', 'contribution'], activeLens);" in js
    assert "activeLens = portfolioTrustLens;" in js
    assert "renderCommercialDataTrustStrip(document.getElementById('commercial-portfolio-trust-strip'), portfolioTrustStrip(payload, portfolioSource, activeLens, activeScenario, activeTargetModel))" in js


def test_commercial_pages_surface_page_specific_flow_navigators_after_data_trust():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-flow-navigator"' in workbench
    assert 'id="commercial-stock-flow-navigator"' in stock
    assert 'id="commercial-portfolio-flow-navigator"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('class="commercial-trust-strip"') < html.index('class="commercial-flow-navigator"')
        assert html.index('class="commercial-flow-navigator"') < html.index('class="commercial-score-strip"')

    for selector in (
        ".commercial-flow-navigator",
        ".commercial-flow-copy",
        ".commercial-flow-step-grid",
        ".commercial-flow-step",
        ".commercial-flow-step.is-current",
        ".commercial-flow-step.is-warning",
        ".commercial-flow-metrics",
        ".commercial-flow-metric",
    ):
        assert selector in css

    assert "function renderCommercialFlowNavigator(root, config)" in js
    assert "function workbenchFlowNavigator(rows, activeTicker, activeView, currentFilter)" in js
    assert "function stockFlowNavigator(snapshot, currentTab, activeScenario, activeCoverage)" in js
    assert "function portfolioFlowNavigator(payload, activeLens, activeScenario, activeTargetModel)" in js


def test_research_workbench_flow_navigator_connects_watchlist_snapshot_report_and_alerts():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Workbench Flow", "Watchlist Scan", "Snapshot Review", "Report Handoff", "Alert Sweep"):
        assert label in js
    assert 'data-commercial-workbench-flow-view="valuation"' in js
    assert 'data-commercial-workbench-flow-filter="alerts"' in js
    assert 'data-commercial-workbench-flow-target="commercial-workbench-detail"' in js
    assert "const workbenchFlowTarget = button.dataset.commercialWorkbenchFlowTarget || button.dataset.commercialFlowTarget;" in js
    assert "renderCommercialFlowNavigator(document.getElementById('commercial-workbench-flow-navigator'), workbenchFlowNavigator(visibleRows.length ? visibleRows : rows, activeTicker, activeView, currentFilter))" in js
    assert "scrollCommercialTaskTarget(workbenchFlowTarget);" in js


def test_stock_detail_flow_navigator_keeps_snapshot_factors_financials_and_pack_one_tap_away():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Stock Research Flow", "Snapshot First", "Factor Check", "Financials", "Research Pack"):
        assert label in js
    assert 'data-commercial-stock-flow-tab="financials"' in js
    assert 'data-commercial-stock-flow-coverage="fundamentals"' in js
    assert 'data-commercial-stock-flow-target="commercial-stock-factor-grades"' in js
    assert "const stockFlowCoverage = button.dataset.commercialStockFlowCoverage;" in js
    assert "activeCoverage = stockFlowCoverage;" in js
    assert "renderCommercialFlowNavigator(document.getElementById('commercial-stock-flow-navigator'), stockFlowNavigator(snapshot, currentTab, activeScenario, activeCoverage))" in js


def test_portfolio_dashboard_flow_navigator_connects_import_health_xray_and_rebalance():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Portfolio Health Flow", "Import Holdings", "Health Score", "X-Ray Review", "Rebalance Ticket"):
        assert label in js
    assert 'data-commercial-portfolio-flow-lens="risk"' in js
    assert 'data-commercial-portfolio-flow-target="commercial-portfolio-rebalance-ticket"' in js
    assert "const portfolioFlowLens = validCommercialChoice(button.dataset.commercialPortfolioFlowLens, ['sector', 'country', 'risk', 'contribution'], activeLens);" in js
    assert "activeLens = portfolioFlowLens;" in js
    assert "renderCommercialFlowNavigator(document.getElementById('commercial-portfolio-flow-navigator'), portfolioFlowNavigator(payload, activeLens, activeScenario, activeTargetModel))" in js


def test_flow_navigators_keep_mobile_step_buttons_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    assert "@media (max-width: 560px)" in css
    mobile_css = css[css.index("@media (max-width: 560px)"):]

    assert ".commercial-flow-navigator" in mobile_css
    assert ".commercial-flow-step-grid" in mobile_css
    flow_step = re.search(r"\.commercial-flow-step \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert flow_step is not None
    assert "min-height: 44px;" in flow_step.group("body")
    assert "width: 100%;" in flow_step.group("body")


def test_commercial_pages_surface_page_specific_sync_strips_near_the_flow():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-sync-strip", "commercial-workbench-flow-navigator", "commercial-workbench-today-inbox"),
        "stock-detail.html": ("commercial-stock-sync-strip", "commercial-stock-flow-navigator", "commercial-stock-today-inbox"),
        "portfolio-dashboard.html": ("commercial-portfolio-sync-strip", "commercial-portfolio-flow-navigator", "commercial-portfolio-today-inbox"),
    }
    for filename, (strip_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{strip_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{strip_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-sync-strip",
        ".commercial-sync-copy",
        ".commercial-sync-items",
        ".commercial-sync-item",
        ".commercial-sync-item.is-live",
        ".commercial-sync-item.is-warning",
        ".commercial-sync-actions",
        ".commercial-sync-action",
    ):
        assert selector in css

    for function_name in (
        "function renderCommercialSyncStrip(root, config)",
        "function workbenchSyncStrip(rows, trackingSource, activeTicker, currentFilter)",
        "function stockSyncStrip(snapshot, snapshotSource, activeCoverage)",
        "function portfolioSyncStrip(payload, portfolioSource, activeLens, activeTargetModel)",
    ):
        assert function_name in js


def test_research_workbench_sync_strip_promotes_watchlist_screener_and_alert_sync():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Watchlist Sync", "Decision API", "Screen Import", "Alert Sync", "Open Sync Center"):
        assert label in js
    assert 'data-commercial-workbench-sync-target="commercial-workbench-data-sync"' in js
    assert 'data-commercial-workbench-sync-filter="alerts"' in js
    assert "const workbenchSyncTarget = button.dataset.commercialWorkbenchSyncTarget || button.dataset.commercialSyncTarget;" in js
    assert "renderCommercialSyncStrip(document.getElementById('commercial-workbench-sync-strip'), workbenchSyncStrip(visibleRows.length ? visibleRows : rows, trackingSource, activeTicker, currentFilter))" in js
    assert "scrollCommercialTaskTarget(workbenchSyncTarget);" in js


def test_stock_detail_sync_strip_promotes_quote_filings_and_alert_coverage():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Stock Feed Sync", "Quote Feed", "Filing Feed", "Alert Sync", "Open Filing Coverage"):
        assert label in js
    assert 'data-commercial-stock-sync-coverage="filings"' in js
    assert 'data-commercial-stock-sync-target="commercial-stock-data-sync"' in js
    assert "const stockSyncCoverage = button.dataset.commercialStockSyncCoverage;" in js
    assert "activeCoverage = stockSyncCoverage;" in js
    assert "renderCommercialSyncStrip(document.getElementById('commercial-stock-sync-strip'), stockSyncStrip(snapshot, snapshotSource, activeCoverage))" in js


def test_portfolio_dashboard_sync_strip_promotes_broker_csv_and_holdings_refresh():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Portfolio Sync", "Broker Link", "CSV Import", "Holding Refresh", "Open Broker Sync"):
        assert label in js
    assert 'data-commercial-portfolio-sync-lens="contribution"' in js
    assert 'data-commercial-portfolio-sync-target="commercial-portfolio-data-sync"' in js
    assert "const portfolioSyncLens = validCommercialChoice(button.dataset.commercialPortfolioSyncLens, ['sector', 'country', 'risk', 'contribution'], activeLens);" in js
    assert "activeLens = portfolioSyncLens;" in js
    assert "renderCommercialSyncStrip(document.getElementById('commercial-portfolio-sync-strip'), portfolioSyncStrip(payload, portfolioSource, activeLens, activeTargetModel))" in js


def test_sync_strips_keep_mobile_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    assert "@media (max-width: 560px)" in css
    mobile_css = css[css.index("@media (max-width: 560px)"):]

    assert ".commercial-sync-strip" in mobile_css
    assert ".commercial-sync-items" in mobile_css
    sync_action = re.search(r"\.commercial-sync-action \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert sync_action is not None
    assert "min-height: 44px;" in sync_action.group("body")
    assert "width: 100%;" in sync_action.group("body")


def test_research_workbench_answer_strip_turns_watchlist_state_into_next_action():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("追蹤表答案", "今日焦點", "主要行動", "打開警示隊列", "匯出決策摘要"):
        assert label in js
    assert 'data-commercial-workbench-answer-action="alerts"' in js
    assert 'data-commercial-workbench-answer-action="export"' in js
    assert "currentFilter = 'alerts';" in js
    assert "await applyWorkbenchFilter();" in js
    assert "renderCommercialDecisionAnswer(document.getElementById('commercial-workbench-answer-strip'), workbenchDecisionAnswer(visibleRows.length ? visibleRows : rows, activeTicker, activeView, currentFilter))" in js


def test_stock_detail_answer_strip_surfaces_snapshot_decision_and_research_pack():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("單股快照答案", "決策", "目標上行", "下一個催化", "打開研究包"):
        assert label in js
    assert 'data-commercial-stock-answer-tab="report"' in js
    assert 'data-commercial-stock-answer-alert="target"' in js
    assert "const stockAnswerTab = button.dataset.commercialStockAnswerTab;" in js
    assert "setStockTab(stockAnswerTab)" in js
    assert "renderCommercialDecisionAnswer(document.getElementById('commercial-stock-answer-strip'), stockDecisionAnswer(snapshot, currentTab, activeScenario, activeRange))" in js


def test_portfolio_dashboard_answer_strip_surfaces_risk_drift_and_rebalance_action():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("投組行動答案", "風險來源", "模型漂移", "立即再平衡", "打開客戶包"):
        assert label in js
    assert 'data-commercial-portfolio-answer-lens="risk"' in js
    assert 'data-commercial-portfolio-answer-scenario="chip"' in js
    assert "const portfolioAnswerScenario = validCommercialChoice(button.dataset.commercialPortfolioAnswerScenario, ['base', 'rate', 'chip', 'fx'], activeScenario);" in js
    assert "activeScenario = portfolioAnswerScenario;" in js
    assert "renderCommercialDecisionAnswer(document.getElementById('commercial-portfolio-answer-strip'), portfolioDecisionAnswer(payload, activeLens, activeScenario, activeTargetModel))" in js


def test_commercial_shell_clips_root_level_horizontal_overflow_without_disabling_table_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    body_rule = re.search(r"body\.commercial-page \{(?P<body>.*?)\n\}", css, re.S)
    shell_rule = re.search(r"\.commercial-shell \{(?P<body>.*?)\n\}", css, re.S)
    table_wrap_rule = re.search(r"\.commercial-table-wrap \{(?P<body>.*?)\n\}", css, re.S)

    assert body_rule is not None
    assert shell_rule is not None
    assert table_wrap_rule is not None
    assert "overflow-x: clip;" in body_rule.group("body")
    assert "width: 100%;" in shell_rule.group("body")
    assert "max-width: 100%;" in shell_rule.group("body")
    assert "overflow-x: clip;" in shell_rule.group("body")
    assert "overflow-x: auto;" in table_wrap_rule.group("body")


def test_research_workbench_requirement_map_extracts_watchlist_and_screener_needs():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("追蹤表需求", "每日決策隊列", "篩選器預設", "快照交接", "批次報告"):
        assert label in js
    assert "data-commercial-workbench-requirement-view" in js
    assert "data-commercial-workbench-requirement-filter" in js
    assert "activeColumnSet = requirementColumnSet;" in js
    assert "renderCommercialRequirementMap(document.getElementById('commercial-workbench-requirement-map'), workbenchRequirementMap(visibleRows.length ? visibleRows : rows, activeTicker, activeView, currentFilter, activeColumnSet))" in js


def test_stock_detail_requirement_map_extracts_snapshot_factor_and_valuation_needs():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("單股研究需求", "先看快照", "因子評等", "估值區間", "研究包"):
        assert label in js
    assert "data-commercial-stock-requirement-tab" in js
    assert "data-commercial-stock-requirement-scenario" in js
    assert "setStockTab(requirementTab)" in js
    assert "renderCommercialRequirementMap(document.getElementById('commercial-stock-requirement-map'), stockRequirementMap(snapshot, currentTab, activeScenario, activeRange))" in js


def test_portfolio_dashboard_requirement_map_extracts_xray_rebalance_and_client_needs():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("投組健檢需求", "曝險 X-Ray", "基準漂移", "再平衡處理單", "客戶包"):
        assert label in js
    assert "data-commercial-portfolio-requirement-lens" in js
    assert "data-commercial-portfolio-requirement-scenario" in js
    assert "activeLens = requirementLens;" in js
    assert "activeScenario = requirementScenario;" in js
    assert "renderCommercialRequirementMap(document.getElementById('commercial-portfolio-requirement-map'), portfolioRequirementMap(payload, activeLens, activeScenario, activeTargetModel))" in js


def test_research_workbench_scores_watchlist_against_screening_criteria():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "Screener Score" in js
    assert "Alert Load" in js
    assert "Report Queue" in js
    assert "Active View" in js
    assert "renderCommercialDecisionScoreStrip(document.getElementById('commercial-workbench-score-strip'), workbenchDecisionScores(visibleRows.length ? visibleRows : rows, activeTicker, activeView))" in js


def test_stock_detail_surfaces_seeking_alpha_style_factor_grades_above_fold():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "Quant Factor Grades" in js
    for factor in ("Value", "Growth", "Profitability", "Momentum", "EPS Revisions"):
        assert f"'{factor}'" in js
    assert "renderCommercialDecisionScoreStrip(document.getElementById('commercial-stock-score-strip'), stockDecisionScores(snapshot, currentTab, activeScenario))" in js
    assert js.count("renderCommercialDecisionScoreStrip(document.getElementById('commercial-stock-score-strip'), stockDecisionScores(snapshot, currentTab, activeScenario))") >= 3
    scenario_block = re.search(r"function setStockScenario\(scenario\) \{(?P<body>.*?)\n        \}", js, re.S)
    assert scenario_block is not None
    assert "renderCommercialDecisionScoreStrip(document.getElementById('commercial-stock-score-strip'), stockDecisionScores(snapshot, currentTab, activeScenario))" in scenario_block.group("body")


def test_portfolio_dashboard_surfaces_xray_drivers_above_fold():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "X-Ray Drivers" in js
    assert "Holdings Breakdown" in js
    assert "Top Holding" in js
    assert "Sector Overweight" in js
    assert "Model Drift" in js
    assert "renderCommercialDecisionScoreStrip(document.getElementById('commercial-portfolio-score-strip'), portfolioDecisionScores(payload, activeLens, activeScenario, activeTargetModel))" in js


def test_commercial_pages_surface_above_fold_comparison_docks():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-compare-dock"' in workbench
    assert 'id="commercial-stock-compare-dock"' in stock
    assert 'id="commercial-portfolio-compare-dock"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('class="commercial-score-strip"') < html.index('class="commercial-compare-dock"')
        assert html.index('class="commercial-compare-dock"') < html.index('class="commercial-delivery-bar"')

    for selector in (
        ".commercial-compare-dock",
        ".commercial-compare-dock-copy",
        ".commercial-compare-rows",
        ".commercial-compare-row",
        ".commercial-compare-row.is-active",
        ".commercial-compare-bar",
        ".commercial-compare-bar i",
        ".commercial-compare-dock.is-portfolio",
    ):
        assert selector in css

    assert "function renderCommercialCompareDock(root, config)" in js
    assert "function workbenchCompareDock(rows, activeTicker, activeView)" in js
    assert "function stockCompareDock(snapshot, currentTab, activeScenario)" in js
    assert "function portfolioCompareDock(payload, activeLens, activeScenario, activeTargetModel)" in js


def test_research_workbench_comparison_dock_benchmarks_active_ticker_against_watchlist():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "Watchlist Relative" in js
    assert "Watchlist Average" in js
    assert "Active Ticker" in js
    assert "Alert Peer" in js
    assert "renderCommercialCompareDock(document.getElementById('commercial-workbench-compare-dock'), workbenchCompareDock(visibleRows.length ? visibleRows : rows, activeTicker, activeView))" in js


def test_research_workbench_ticker_click_refreshes_above_fold_scores_and_comparison():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    click_block = re.search(r"document.addEventListener\('click', event => \{(?P<body>.*?)\n        \}\);", js, re.S)
    assert click_block is not None
    assert "const visibleRows = currentWorkbenchRows();" in click_block.group("body")
    assert "renderCommercialDecisionScoreStrip(document.getElementById('commercial-workbench-score-strip'), workbenchDecisionScores(visibleRows.length ? visibleRows : rows, activeTicker, activeView))" in click_block.group("body")
    assert "renderCommercialCompareDock(document.getElementById('commercial-workbench-compare-dock'), workbenchCompareDock(visibleRows.length ? visibleRows : rows, activeTicker, activeView))" in click_block.group("body")


def test_stock_detail_comparison_dock_updates_peer_benchmark_with_scenario():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "Peer Benchmark" in js
    assert "Sector Median" in js
    assert "同業" in js
    assert "Target Gap" in js
    assert "renderCommercialCompareDock(document.getElementById('commercial-stock-compare-dock'), stockCompareDock(snapshot, currentTab, activeScenario))" in js
    assert js.count("renderCommercialCompareDock(document.getElementById('commercial-stock-compare-dock'), stockCompareDock(snapshot, currentTab, activeScenario))") >= 3
    scenario_block = re.search(r"function setStockScenario\(scenario\) \{(?P<body>.*?)\n        \}", js, re.S)
    assert scenario_block is not None
    assert "renderCommercialCompareDock(document.getElementById('commercial-stock-compare-dock'), stockCompareDock(snapshot, currentTab, activeScenario))" in scenario_block.group("body")


def test_portfolio_dashboard_comparison_dock_benchmarks_current_portfolio_against_target_model():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "Benchmark Relative" in js
    assert "Target Model" in js
    assert "Current Portfolio" in js
    assert "Overweight Driver" in js
    assert "renderCommercialCompareDock(document.getElementById('commercial-portfolio-compare-dock'), portfolioCompareDock(payload, activeLens, activeScenario, activeTargetModel))" in js


def test_commercial_pages_surface_above_fold_task_navigation_rails():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-task-rail"' in workbench
    assert 'id="commercial-stock-task-rail"' in stock
    assert 'id="commercial-portfolio-task-rail"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('class="commercial-compare-dock"') < html.index('class="commercial-task-rail"')
        assert html.index('class="commercial-task-rail"') < html.index('class="commercial-delivery-bar"')

    for selector in (
        ".commercial-task-rail",
        ".commercial-task-rail-copy",
        ".commercial-task-actions",
        ".commercial-task-action",
        ".commercial-task-action.is-primary",
        ".commercial-task-action.is-active",
        ".commercial-task-action.is-warning",
    ):
        assert selector in css

    assert "function renderCommercialTaskRail(root, config)" in js
    assert "function workbenchTaskRail(rows, activeTicker, activeView, currentFilter)" in js
    assert "function stockTaskRail(snapshot, currentTab, activeScenario)" in js
    assert "function portfolioTaskRail(payload, activeLens, activeScenario, activeTargetModel)" in js
    assert "data-commercial-task-target" in js


def test_research_workbench_task_rail_routes_to_watchlist_workflow_steps():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Watchlist Workflow", "Snapshot", "Screener Scores", "Alert Queue", "Report Pack"):
        assert label in js
    assert "renderCommercialTaskRail(document.getElementById('commercial-workbench-task-rail'), workbenchTaskRail(visibleRows.length ? visibleRows : rows, activeTicker, activeView, currentFilter))" in js
    click_block = re.search(r"document.addEventListener\('click', event => \{(?P<body>.*?)\n        \}\);", js, re.S)
    assert click_block is not None
    assert "renderCommercialTaskRail(document.getElementById('commercial-workbench-task-rail'), workbenchTaskRail(visibleRows.length ? visibleRows : rows, activeTicker, activeView, currentFilter))" in click_block.group("body")


def test_stock_detail_task_rail_switches_research_tabs_and_scroll_targets():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Research Workflow", "Snapshot", "AI Report", "Financials", "Peers"):
        assert label in js
    assert "renderCommercialTaskRail(document.getElementById('commercial-stock-task-rail'), stockTaskRail(snapshot, currentTab, activeScenario))" in js
    assert js.count("renderCommercialTaskRail(document.getElementById('commercial-stock-task-rail'), stockTaskRail(snapshot, currentTab, activeScenario))") >= 3
    assert "data-commercial-task-stock-tab" in js
    assert "setStockTab(stockTaskTab)" in js


def test_portfolio_dashboard_task_rail_routes_to_xray_benchmark_and_rebalance_steps():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("X-Ray Workflow", "X-Ray Breakdown", "Benchmark", "Rebalance", "Holdings"):
        assert label in js
    assert "renderCommercialTaskRail(document.getElementById('commercial-portfolio-task-rail'), portfolioTaskRail(payload, activeLens, activeScenario, activeTargetModel))" in js
    assert "data-commercial-task-portfolio-model" in js
    assert "activeTargetModel = portfolioTaskModel;" in js


def test_commercial_pages_surface_section_navigation_without_readability_overlap():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-section-nav"' in workbench
    assert 'id="commercial-stock-section-nav"' in stock
    assert 'id="commercial-portfolio-section-nav"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('class="commercial-task-rail"') < html.index('class="commercial-section-nav"')
        assert html.index('class="commercial-section-nav"') < html.index('class="commercial-delivery-bar"')

    section_nav = re.search(r"\.commercial-section-nav \{(?P<body>.*?)\n\}", css, re.S)
    assert section_nav is not None
    section_nav_body = section_nav.group("body")
    assert "position: relative;" in section_nav_body
    assert "position: sticky;" not in section_nav_body
    assert "top: 224px;" not in section_nav_body
    assert "z-index: 1;" in section_nav_body
    for selector in (
        ".commercial-section-nav-copy",
        ".commercial-section-links",
        ".commercial-section-link",
        ".commercial-section-link.is-active",
        ".commercial-section-link.is-warning",
    ):
        assert selector in css

    assert "function renderCommercialSectionNav(root, config)" in js
    assert "function workbenchSectionNav(activeView, currentFilter)" in js
    assert "function stockSectionNav(currentTab, activeScenario)" in js
    assert "function portfolioSectionNav(activeLens, activeScenario, activeTargetModel)" in js
    assert "function bindCommercialSectionNavigation(root)" in js
    assert "data-commercial-section-target" in js


def test_section_navigation_keeps_active_state_after_reactive_rerenders():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const target = button.dataset.commercialSectionTarget;" in js
    assert "item.dataset.commercialSectionTarget === target" in js
    assert "scrollCommercialTaskTarget(target)" in js


def test_research_workbench_section_navigation_matches_professional_watchlist_views():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Watchlist Nav", "Table", "Snapshot", "Alerts", "Reports", "Views"):
        assert label in js
    assert "renderCommercialSectionNav(document.getElementById('commercial-workbench-section-nav'), workbenchSectionNav(activeView, currentFilter))" in js
    assert "bindCommercialSectionNavigation(document.getElementById('commercial-workbench-section-nav'))" in js


def test_stock_detail_section_navigation_keeps_symbol_page_research_regions_reachable():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Stock Nav", "Snapshot", "Chart", "Report", "Financials", "Peers"):
        assert label in js
    assert "renderCommercialSectionNav(document.getElementById('commercial-stock-section-nav'), stockSectionNav(currentTab, activeScenario))" in js
    assert js.count("renderCommercialSectionNav(document.getElementById('commercial-stock-section-nav'), stockSectionNav(currentTab, activeScenario))") >= 3


def test_portfolio_dashboard_section_navigation_keeps_xray_and_rebalance_reachable():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Portfolio Nav", "X-Ray", "Benchmark", "Risk", "Rebalance", "Holdings"):
        assert label in js
    assert "renderCommercialSectionNav(document.getElementById('commercial-portfolio-section-nav'), portfolioSectionNav(activeLens, activeScenario, activeTargetModel))" in js


def test_commercial_pages_surface_professional_command_hubs_after_section_navigation():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-command-hub"' in workbench
    assert 'id="commercial-stock-command-hub"' in stock
    assert 'id="commercial-portfolio-command-hub"' in portfolio
    for html in (workbench, stock, portfolio):
        assert html.index('class="commercial-section-nav"') < html.index('class="commercial-command-hub"')

    for selector in (
        ".commercial-command-hub",
        ".commercial-command-tabs",
        ".commercial-command-tab",
        ".commercial-command-tab.is-active",
        ".commercial-command-actions",
        ".commercial-command-evidence",
    ):
        assert selector in css

    assert "function renderCommercialCommandHub(root, config)" in js
    assert "function workbenchCommandHub(rows, activeView, currentFilter, activeColumnSet)" in js
    assert "function stockResearchCommandHub(snapshot, currentTab, activeScenario)" in js
    assert "function portfolioXrayCommandHub(payload, activeLens, activeScenario, activeTargetModel)" in js


def test_workbench_command_hub_supports_saved_views_and_table_actions():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Saved Views", "Decision View", "Valuation View", "Event Watch", "Risk Review", "Save as Screener", "CSV Export", "Tile View"):
        assert label in js
    assert "data-commercial-workbench-command-view" in js
    assert "data-commercial-workbench-command-filter" in js
    assert "data-commercial-workbench-command-columns" in js
    assert "activeColumnSet = workbenchCommandColumns;" in js
    assert "await applyWorkbenchFilter();" in js


def test_stock_command_hub_guides_symbol_research_modules_without_hunting():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Research Playbook", "Snapshot", "Valuation", "Earnings", "Ownership", "News", "Options", "ETF Exposure", "Seasonals", "Notes"):
        assert label in js
    assert "data-commercial-stock-command-tab" in js
    assert "data-commercial-stock-command-target" in js
    assert "setStockTab(stockCommandTab)" in js
    assert "scrollCommercialTaskTarget(stockCommandTarget)" in js


def test_portfolio_command_hub_supports_xray_lenses_templates_and_summary_rows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("X-Ray Template", "Allocation", "Geography", "Risk", "Contribution", "Benchmark", "Style Box", "Overlap", "Summary Rows"):
        assert label in js
    assert "data-commercial-portfolio-command-lens" in js
    assert "data-commercial-portfolio-command-model" in js
    assert "activeLens = portfolioCommandLens;" in js
    assert "activeTargetModel = portfolioCommandModel;" in js
    assert "renderPortfolioRisk(lastPayload, activeLens, activeScenario, targetWeight, activeExecutionMode, activeTargetModel, driftTolerance, portfolioSource)" in js


def test_commercial_pages_surface_competitive_drilldown_panels_after_command_hubs():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-quick-actions"' in workbench
    assert 'id="commercial-stock-info-coverage"' in stock
    assert 'id="commercial-portfolio-holdings-breakdown"' in portfolio
    assert workbench.index('id="commercial-workbench-command-hub"') < workbench.index('id="commercial-workbench-quick-actions"')
    assert stock.index('id="commercial-stock-command-hub"') < stock.index('id="commercial-stock-info-coverage"')
    assert portfolio.index('id="commercial-portfolio-command-hub"') < portfolio.index('id="commercial-portfolio-holdings-breakdown"')

    for selector in (
        ".commercial-intelligence-panel",
        ".commercial-intelligence-tabs",
        ".commercial-intelligence-tab",
        ".commercial-intelligence-grid",
        ".commercial-scatter-plot",
        ".commercial-benchmark-breakdown",
    ):
        assert selector in css

    assert "function renderWorkbenchQuickActions(root, rows, activeTicker, activeQuickAction = 'news')" in js
    assert "function renderStockInformationCoverage(root, snapshot, currentTab, activeScenario, activeCoverage = 'alerts')" in js
    assert "function renderPortfolioHoldingsBreakdown(root, payload, activeLens, activeTargetModel)" in js


def test_workbench_quick_actions_add_news_scatter_and_row_action_drilldowns():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Quick Actions", "Watchlist News", "Scatter Plot", "Row Actions", "Auto Refresh", "Chart View"):
        assert label in js
    assert "data-commercial-workbench-quick-action" in js
    assert "activeQuickAction = workbenchQuickAction;" in js
    assert "renderWorkbenchQuickActions(document.getElementById('commercial-workbench-quick-actions'), visibleRows.length ? visibleRows : rows, activeTicker, activeQuickAction)" in js


def test_stock_information_coverage_surfaces_missing_professional_stock_data():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Information Coverage", "Price Alerts", "Fundamental Snapshot", "Filings & Transcripts", "ETF / Fund Exposure", "Research Notes"):
        assert label in js
    assert "data-commercial-stock-coverage" in js
    assert "activeCoverage = stockCoverage;" in js
    assert "renderStockInformationCoverage(document.getElementById('commercial-stock-info-coverage'), snapshot, currentTab, activeScenario, activeCoverage)" in js


def test_portfolio_holdings_breakdown_explains_overweight_underweight_drivers():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Holdings Breakdown", "Overweight", "Underweight", "Benchmark Impact", "Rebalance Driver"):
        assert label in js
    assert "function portfolioHoldingBreakdownRows(payload, activeTargetModel)" in js
    assert "benchmarkWeight" in js
    assert "weightDelta" in js
    assert "renderPortfolioHoldingsBreakdown(document.getElementById('commercial-portfolio-holdings-breakdown'), payload, activeLens, activeTargetModel)" in js


def test_competitive_intelligence_panels_offer_direct_quick_action_targets():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-intelligence-actions",
        ".commercial-intelligence-action",
        ".commercial-intelligence-action.is-primary",
    ):
        assert selector in css
    assert "function commercialIntelligenceActionButton(action)" in js
    assert "function bindCommercialIntelligenceActions(root)" in js
    assert "data-commercial-intelligence-target" in js
    assert "scrollCommercialTaskTarget(target);" in js

    for label in (
        "Open Watchlist News",
        "Open Scatter Plot",
        "Open Row Actions",
        "Open Snapshot",
        "Open Actuals",
        "Open Filings",
        "Open ETF Exposure",
        "Open Notes",
        "Open Health Score",
        "Open Broker Sync",
        "Open Active Return",
        "Open Warnings",
        "Open Client Pack",
    ):
        assert label in js
    assert "bindCommercialIntelligenceActions(document.getElementById('commercial-workbench-quick-actions'))" in js
    assert "bindCommercialIntelligenceActions(document.getElementById('commercial-stock-info-coverage'))" in js
    assert "bindCommercialIntelligenceActions(document.getElementById('commercial-portfolio-holdings-breakdown'))" in js


def test_commercial_pages_surface_workspace_memory_after_competitive_drilldowns():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-workspace-memory"' in workbench
    assert 'id="commercial-stock-research-journal"' in stock
    assert 'id="commercial-portfolio-rebalance-history"' in portfolio
    assert workbench.index('id="commercial-workbench-quick-actions"') < workbench.index('id="commercial-workbench-workspace-memory"')
    assert stock.index('id="commercial-stock-info-coverage"') < stock.index('id="commercial-stock-research-journal"')
    assert portfolio.index('id="commercial-portfolio-holdings-breakdown"') < portfolio.index('id="commercial-portfolio-rebalance-history"')

    for selector in (
        ".commercial-memory-panel",
        ".commercial-memory-actions",
        ".commercial-memory-action",
        ".commercial-memory-timeline",
        ".commercial-memory-item",
        ".commercial-memory-note",
    ):
        assert selector in css

    assert "function writeCommercialMemory(scope, state)" in js
    assert "function renderWorkbenchWorkspaceMemory(root, state, message = '')" in js
    assert "function renderStockResearchJournal(root, snapshot, currentTab, activeCoverage, note = '')" in js
    assert "function renderPortfolioRebalanceHistory(root, payload, state, message = '')" in js


def test_workbench_workspace_memory_supports_autosave_undo_redo_and_share_screen():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Workspace Autosave", "Saved Screen", "Undo", "Redo", "Share Screen", "Autosave on"):
        assert label in js
    assert "data-commercial-workbench-memory-action" in js
    assert "workbenchMemoryHistory" in js
    assert "restoreWorkbenchMemoryState(previousState)" in js
    assert "writeCommercialMemory('workbench-screen'" in js


def test_stock_research_journal_autosaves_notes_and_coverage_checkpoints():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Research Journal", "Autosaved Notes", "Thesis checkpoint", "Coverage checkpoint", "Last reviewed"):
        assert label in js
    assert "data-commercial-stock-journal-note" in js
    assert "data-commercial-stock-journal-action" in js
    assert "writeCommercialMemory('stock-journal'" in js
    assert "renderStockResearchJournal(document.getElementById('commercial-stock-research-journal'), snapshot, currentTab, activeCoverage, stockJournalNote)" in js


def test_portfolio_rebalance_history_tracks_copy_restore_and_scenario_checkpoints():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Rebalance History", "Scenario checkpoint", "Make a Copy", "Restore Previous", "Rebalance checkpoint"):
        assert label in js
    assert "data-commercial-portfolio-history-action" in js
    assert "writeCommercialMemory('portfolio-rebalance'" in js
    assert "restorePortfolioRebalanceState(savedPortfolioState)" in js
    assert "renderPortfolioRebalanceHistory(document.getElementById('commercial-portfolio-rebalance-history'), lastPayload, { activeLens, activeScenario, targetWeight, activeExecutionMode, activeTargetModel }, portfolioHistoryMessage)" in js


def test_commercial_pages_add_competitive_delivery_centers_after_memory_layers():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert 'id="commercial-workbench-monitor-center"' in workbench
    assert 'id="commercial-stock-report-builder"' in stock
    assert 'id="commercial-portfolio-client-pack"' in portfolio
    assert workbench.index('id="commercial-workbench-workspace-memory"') < workbench.index('id="commercial-workbench-monitor-center"')
    assert stock.index('id="commercial-stock-research-journal"') < stock.index('id="commercial-stock-report-builder"')
    assert portfolio.index('id="commercial-portfolio-rebalance-history"') < portfolio.index('id="commercial-portfolio-client-pack"')

    for selector in (
        ".commercial-delivery-panel",
        ".commercial-delivery-actions",
        ".commercial-delivery-action",
        ".commercial-delivery-grid",
        ".commercial-delivery-check",
        ".commercial-delivery-schedule",
    ):
        assert selector in css

    assert "function renderWorkbenchMonitorCenter(root, rows, activeTicker, activeView, currentFilter, message = '')" in js
    assert "function renderStockReportBuilder(root, snapshot, currentTab, activeScenario, activeCoverage, message = '')" in js
    assert "function renderPortfolioClientPack(root, payload, activeLens, activeScenario, activeTargetModel, message = '')" in js


def test_workbench_monitor_center_batches_alerts_and_team_sharing():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Watchlist Monitor Center", "Batch Alerts", "Team Watchlist", "Alert Rules", "Share Watchlist", "Assign Review"):
        assert label in js
    assert "data-commercial-workbench-monitor-action" in js
    assert "writeCommercialMemory('workbench-monitor'" in js
    assert "renderWorkbenchMonitorCenter(document.getElementById('commercial-workbench-monitor-center'), visibleRows.length ? visibleRows : rows, activeTicker, activeView, currentFilter)" in js


def test_stock_report_builder_creates_client_ready_research_pack():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Research Report Builder", "Client-ready Report", "PDF Pack", "Citation Check", "Data freshness", "Generate Brief"):
        assert label in js
    assert "data-commercial-stock-report-action" in js
    assert "writeCommercialMemory('stock-report-pack'" in js
    assert "renderStockReportBuilder(document.getElementById('commercial-stock-report-builder'), snapshot, currentTab, activeScenario, activeCoverage)" in js


def test_portfolio_client_pack_schedules_model_portfolio_delivery():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Client Portfolio Pack", "Automated Performance Email", "Model Portfolio Monitor", "Schedule Review", "Advisor-ready"):
        assert label in js
    assert "data-commercial-portfolio-pack-action" in js
    assert "writeCommercialMemory('portfolio-client-pack'" in js
    assert "renderPortfolioClientPack(document.getElementById('commercial-portfolio-client-pack'), lastPayload, activeLens, activeScenario, activeTargetModel)" in js


def test_commercial_pages_add_product_grade_workspace_chrome_before_main_workflows():
    workbench = (COMMERCIAL_DIR / "research-workbench.html").read_text(encoding="utf-8")
    stock = (COMMERCIAL_DIR / "stock-detail.html").read_text(encoding="utf-8")
    portfolio = (COMMERCIAL_DIR / "portfolio-dashboard.html").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for html in (workbench, stock, portfolio):
        assert 'id="commercial-workspace-chrome"' in html
        assert html.index('class="commercial-topbar"') < html.index('id="commercial-workspace-chrome"') < html.index('<main ')

    for selector in (
        ".commercial-workspace-chrome",
        ".commercial-workspace-start-menu",
        ".commercial-workspace-link",
        ".commercial-workspace-search",
        ".commercial-workspace-status",
        ".commercial-workspace-pill",
    ):
        assert selector in css

    assert "function renderCommercialWorkspaceChrome(root, pageName, ticker, context = {})" in js
    assert "function bindCommercialWorkspaceChrome(root, pageName, getTicker, onTickerSubmit)" in js


def test_workspace_chrome_supports_universal_search_start_menu_and_deep_links():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    workspace_render = re.search(
        r"function renderCommercialWorkspaceChrome\(root, pageName, ticker, context = \{\}\) \{(?P<body>.*?)\n    function bindCommercialWorkspaceChrome",
        js,
        re.S,
    )
    assert workspace_render is not None
    workspace_render_body = workspace_render.group("body")

    for label in ("開始選單", "股票/功能搜尋", "打開追蹤表", "打開單股頁", "打開投組", "複製連結", "工作區健康度"):
        assert label in workspace_render_body
    for visible_utility_label in ("Universal Search", "Copy Deep Link"):
        assert visible_utility_label not in workspace_render_body
    assert "data-commercial-workspace-search" in js
    assert "data-commercial-workspace-target" in js
    assert "data-commercial-workspace-copy-link" in js
    assert "commercialPageUrl(target.pageName, ticker)" in js
    assert "onTickerSubmit(normalizeTicker(search.value || getTicker()))" in js


def test_each_commercial_page_binds_workspace_chrome_to_its_own_context():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "renderCommercialWorkspaceChrome(document.getElementById('commercial-workspace-chrome'), 'research-workbench'" in js
    assert "bindCommercialWorkspaceChrome(document.getElementById('commercial-workspace-chrome'), 'research-workbench'" in js
    assert "renderCommercialWorkspaceChrome(document.getElementById('commercial-workspace-chrome'), 'stock-detail'" in js
    assert "bindCommercialWorkspaceChrome(document.getElementById('commercial-workspace-chrome'), 'stock-detail'" in js
    assert "renderCommercialWorkspaceChrome(document.getElementById('commercial-workspace-chrome'), 'portfolio-dashboard'" in js
    assert "bindCommercialWorkspaceChrome(document.getElementById('commercial-workspace-chrome'), 'portfolio-dashboard'" in js


def test_workspace_chrome_adds_display_density_and_focus_controls():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("顯示密度", "舒適版", "精簡版", "專注模式", "重設版面"):
        assert label in js
    for selector in (
        ".commercial-workspace-display",
        ".commercial-density-button",
        "body[data-commercial-density=\"compact\"]",
        "body[data-commercial-focus=\"on\"]",
    ):
        assert selector in css
    assert "function commercialDisplayPreference()" in js
    assert "function applyCommercialDisplayPreference(preference)" in js
    assert "writeCommercialMemory('workspace-display'" in js
    assert "data-commercial-density-option" in js
    assert "data-commercial-focus-mode" in js
    assert "data-commercial-reset-layout" in js


def test_workspace_chrome_keeps_display_mode_controls_visible_when_collapsed():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "commercial-workspace-display-quick" in js
    assert "data-commercial-display-quick" in js
    assert "commercial-workspace-display-quick commercial-workspace-detail-block" not in js
    for label in ("舒適", "精簡", "專注"):
        assert label in js

    quick = re.search(r"\.commercial-workspace-display-quick \{(?P<body>.*?)\n\}", css, re.S)
    assert quick is not None
    quick_body = quick.group("body")
    assert "display: grid;" in quick_body
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in quick_body
    assert "min-width: 0;" in quick_body

    quick_button = re.search(r"\.commercial-workspace-display-quick \.commercial-density-button \{(?P<body>.*?)\n\}", css, re.S)
    assert quick_button is not None
    quick_button_body = quick_button.group("body")
    assert "min-height: 44px;" in quick_button_body
    assert "width: 100%;" in quick_button_body
    assert "min-width: 0;" in quick_button_body

    collapsed = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-display-quick \{(?P<body>.*?)\n\}", css, re.S)
    assert collapsed is not None
    collapsed_body = collapsed.group("body")
    assert "display: grid;" in collapsed_body
    assert "align-self: center;" in collapsed_body
    assert "height: 44px;" in collapsed_body

    collapsed_actions = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-summary-actions \{(?P<body>.*?)\n\}", css, re.S)
    assert collapsed_actions is not None
    assert "grid-template-columns: repeat(3, minmax(92px, 1fr));" in collapsed_actions.group("body")


def test_workspace_chrome_adds_competitor_style_symbol_handoff_for_snapshot_navigation():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "股票交接",
        "追蹤表快照",
        "單股快照",
        "投組影響",
        "打開快照",
        "因子評分",
        "投組影響",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-snapshot",
        ".commercial-workspace-handoff-grid",
        ".commercial-workspace-handoff-link",
    ):
        assert selector in css
    base_snapshot = re.search(r"\.commercial-workspace-snapshot \{(?P<body>.*?)\n\}", css, re.S)
    assert base_snapshot is not None
    assert "grid-template-columns: 1fr;" in base_snapshot.group("body")
    assert "function commercialWorkspaceHandoffConfig(pageName, ticker, context = {})" in js
    assert "data-commercial-workspace-handoff" in js
    assert "data-commercial-workspace-section" in js
    assert "commercialPageUrl('stock-detail', normalized) + '#commercial-stock-snapshot-hero'" in js
    assert "commercialPageUrl('research-workbench', normalized) + '#commercial-workbench-detail'" in js
    assert "commercialPageUrl('portfolio-dashboard', normalized) + '#commercial-portfolio-drift-review'" in js
    assert "commercialPageUrl('portfolio-dashboard', normalized) + '#commercial-portfolio-factor-lens'" in js


def test_workspace_symbol_handoff_keeps_mobile_links_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workspace-snapshot" in mobile_css
    handoff_grid = re.search(r"\.commercial-workspace-handoff-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert handoff_grid is not None
    assert "display: grid;" in handoff_grid.group("body")
    assert "grid-template-columns: 1fr;" in handoff_grid.group("body")
    assert "overflow-x: visible;" in handoff_grid.group("body")
    handoff_link = re.search(r"\.commercial-workspace-handoff-link \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert handoff_link is not None
    assert "min-height: 44px;" in handoff_link.group("body")
    assert "width: 100%;" in handoff_link.group("body")


def test_workspace_chrome_adds_recent_symbol_quick_switch_for_competitor_like_watchlists():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("最近股票", "快速切換", "追蹤中", "快照", "警示", "目前股票"):
        assert label in js
    for selector in (
        ".commercial-workspace-recents",
        ".commercial-workspace-symbol-strip",
        ".commercial-workspace-symbol-chip",
        ".commercial-workspace-symbol-chip.is-active",
    ):
        assert selector in css
    assert "function commercialWorkspacePrimarySection(pageName)" in js
    assert "function commercialWorkspaceRecentSymbols(pageName, ticker)" in js
    assert "data-commercial-symbol-chip" in js
    assert "commercialPageUrl(pageName, item.ticker) + `#${primarySection}`" in js
    assert "commercialWorkspaceRecentSymbols(pageName, normalized)" in js


def test_workspace_recent_symbols_keep_mobile_quick_switch_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workspace-recents" in mobile_css
    symbol_strip = re.search(r"\.commercial-workspace-symbol-strip \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert symbol_strip is not None
    assert "display: grid;" in symbol_strip.group("body")
    assert "grid-template-columns: 1fr;" in symbol_strip.group("body")
    assert "overflow-x: visible;" in symbol_strip.group("body")
    symbol_chip = re.search(r"\.commercial-workspace-symbol-chip \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert symbol_chip is not None
    assert "min-height: 44px;" in symbol_chip.group("body")
    assert "width: 100%;" in symbol_chip.group("body")


def test_workspace_chrome_adds_follow_alert_shortcuts_like_stock_apps():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "追蹤與警示",
        "追蹤表警示",
        "單股警示",
        "投組警示",
        "價格警示",
        "新聞警示",
        "評級警示",
        "量化評級",
        "投組守門",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-alerts",
        ".commercial-workspace-alert-grid",
        ".commercial-workspace-alert-button",
        ".commercial-workspace-alert-button.is-primary",
    ):
        assert selector in css
    assert "function commercialWorkspaceAlertConfig(pageName, ticker, context = {})" in js
    assert "data-commercial-workspace-alert" in js
    assert "data-commercial-workspace-alert-target" in js
    assert "writeCommercialMemory(`workspace-alert-${activeId}`" in js
    assert "commercialWorkspaceAlertConfig(pageName, normalized, context)" in js


def test_workspace_alert_shortcuts_keep_mobile_actions_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workspace-alerts" in mobile_css
    alert_grid = re.search(r"\.commercial-workspace-alert-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert alert_grid is not None
    assert "display: grid;" in alert_grid.group("body")
    assert "grid-template-columns: 1fr;" in alert_grid.group("body")
    assert "overflow-x: visible;" in alert_grid.group("body")
    alert_button = re.search(r"\.commercial-workspace-alert-button \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert alert_button is not None
    assert "min-height: 44px;" in alert_button.group("body")
    assert "width: 100%;" in alert_button.group("body")


def test_workspace_chrome_adds_page_specific_data_confidence_for_distinct_page_needs():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "資料新鮮度",
        "來源信心",
        "追蹤表資料準備度",
        "單股快照覆蓋",
        "投組風險覆蓋",
        "決策表",
        "新聞/公告",
        "報價",
        "財報共識",
        "估值區間",
        "持股",
        "基準",
        "風險規則",
        "客戶包",
        "即時來源",
        "備援示範",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-trust",
        ".commercial-workspace-trust-grid",
        ".commercial-workspace-trust-item",
        ".commercial-workspace-trust-item.is-live",
        ".commercial-workspace-trust-item.is-warning",
    ):
        assert selector in css
    assert "function commercialWorkspaceTrustConfig(pageName, ticker, context = {})" in js
    assert "commercialWorkspaceTrustConfig(pageName, normalized, context)" in js
    assert "data-commercial-workspace-trust" in js
    assert "data-commercial-workspace-trust-target" in js
    assert "writeCommercialMemory(`workspace-trust-${activeId}`" in js


def test_workspace_data_confidence_keeps_mobile_items_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workspace-trust" in mobile_css
    trust_grid = re.search(r"\.commercial-workspace-trust-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert trust_grid is not None
    assert "display: grid;" in trust_grid.group("body")
    assert "grid-template-columns: 1fr;" in trust_grid.group("body")
    assert "overflow-x: visible;" in trust_grid.group("body")
    trust_item = re.search(r"\.commercial-workspace-trust-item \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert trust_item is not None
    assert "min-height: 44px;" in trust_item.group("body")
    assert "width: 100%;" in trust_item.group("body")


def test_commercial_task_target_scroll_offsets_sticky_chrome_for_no_hunt_navigation():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function commercialStickyOffset(target = null)" in js
    assert "target.getBoundingClientRect().top + window.scrollY - commercialStickyOffset(target)" in js
    assert "const preferredBehavior = options.behavior || (prefersReducedMotion ? 'auto' : 'smooth');" in js
    assert "alignTarget(preferredBehavior);" in js
    assert "window.scrollTo({ top, behavior });" in js
    assert "target.classList.add('commercial-scroll-focus')" in js
    assert "target.classList.remove('commercial-scroll-focus')" in js
    assert ".commercial-scroll-focus" in css


def test_workspace_chrome_adds_page_specific_compare_benchmark_shortcuts():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "比較與基準",
        "追蹤表比較",
        "同業比較",
        "投組基準",
        "相對報酬",
        "欄位組",
        "同業矩陣",
        "估值差距",
        "主動報酬",
        "產業權重",
        "S&P 500 基準",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-compare",
        ".commercial-workspace-compare-grid",
        ".commercial-workspace-compare-button",
        ".commercial-workspace-compare-button.is-primary",
    ):
        assert selector in css
    assert "function commercialWorkspaceCompareConfig(pageName, ticker, context = {})" in js
    assert "commercialWorkspaceCompareConfig(pageName, normalized, context)" in js
    assert "data-commercial-workspace-compare" in js
    assert "data-commercial-workspace-compare-target" in js
    assert "writeCommercialMemory(`workspace-compare-${activeId}`" in js


def test_workspace_compare_benchmark_keeps_mobile_actions_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workspace-compare" in mobile_css
    compare_grid = re.search(r"\.commercial-workspace-compare-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert compare_grid is not None
    assert "display: grid;" in compare_grid.group("body")
    assert "grid-template-columns: 1fr;" in compare_grid.group("body")
    assert "overflow-x: visible;" in compare_grid.group("body")
    compare_button = re.search(r"\.commercial-workspace-compare-button \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert compare_button is not None
    assert "min-height: 44px;" in compare_button.group("body")
    assert "width: 100%;" in compare_button.group("body")


def test_workspace_chrome_adds_page_specific_compact_summary_for_distinct_product_needs():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "工作區摘要",
        "追蹤表決策",
        "個股研究",
        "投組健檢",
        "決策隊列",
        "個股快照",
        "再平衡",
        "展開工具",
        "收合工具",
    ):
        assert label in js
    for snippet in (
        "{ id: 'decision-queue', label: '決策', metric: '表格', target: 'commercial-workbench-detail', primary: true }",
        "{ id: 'stock-snapshot', label: '快照', metric: '報價', target: 'commercial-stock-snapshot-hero', primary: true }",
        "{ id: 'rebalance-queue', label: '再平衡', metric: '漂移', target: 'commercial-portfolio-drift-review', primary: true }",
    ):
        assert snippet in js
    for selector in (
        ".commercial-workspace-summary",
        ".commercial-workspace-summary-actions",
        ".commercial-workspace-summary-button",
        ".commercial-workspace-toggle",
        ".commercial-workspace-detail-block",
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-detail-block",
    ):
        assert selector in css
    assert "function commercialWorkspaceSummaryConfig(pageName, ticker, context = {})" in js
    assert "commercialWorkspaceSummaryConfig(pageName, normalized, context)" in js
    assert "data-commercial-workspace-summary-target" in js
    assert "data-commercial-workspace-toggle" in js
    assert "data-commercial-workspace-detail" in js
    assert "writeCommercialMemory(`workspace-chrome-${activeId}`" in js
    assert "writeCommercialMemory(`workspace-summary-${activeId}`" in js
    assert "const collapsed = chromeState.collapsed !== false;" in js
    assert 'class="commercial-workspace-start-menu commercial-workspace-detail-block"' in js
    assert "root.classList.add('is-collapsed')" in js
    assert "requestAnimationFrame(() => scrollCommercialTaskTarget(target))" in js


def test_workspace_chrome_collapses_secondary_setup_lens_and_alert_sections_by_default():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("設定教練", "研究鏡頭", "警示快速設定", "視圖預設"):
        assert label in js
    for section_class in (
        'class="commercial-workspace-view-presets commercial-workspace-detail-block"',
        'class="commercial-workspace-setup-coach commercial-workspace-detail-block"',
        'class="commercial-workspace-lens commercial-workspace-detail-block"',
        'class="commercial-workspace-alert-setup commercial-workspace-detail-block"',
    ):
        assert section_class in js
    assert 'data-commercial-workspace-detail aria-label="視圖預設"' in js
    assert 'data-commercial-workspace-detail aria-label="設定教練"' in js
    assert 'data-commercial-workspace-detail aria-label="研究鏡頭"' in js
    assert 'data-commercial-workspace-detail aria-label="警示快速設定"' in js
    collapsed_rule = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-detail-block \{(?P<body>.*?)\n\}", css, re.S)
    assert collapsed_rule is not None
    assert "display: none;" in collapsed_rule.group("body")
    assert "const collapsed = chromeState.collapsed !== false;" in js


def test_workspace_compact_summary_keeps_mobile_first_screen_short_and_tappable():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workspace-summary" in mobile_css
    summary = re.search(r"\.commercial-workspace-summary \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert summary is not None
    assert "grid-template-columns: 1fr;" in summary.group("body")
    summary_actions = re.search(r"\.commercial-workspace-summary-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert summary_actions is not None
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in summary_actions.group("body")
    summary_button = re.search(r"\.commercial-workspace-summary-button \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert summary_button is not None
    assert "min-height: 44px;" in summary_button.group("body")
    assert "width: 100%;" in summary_button.group("body")
    summary_toggle = re.search(r"\.commercial-workspace-toggle \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert summary_toggle is not None
    assert "min-height: 44px;" in summary_toggle.group("body")
    assert "width: 100%;" in summary_toggle.group("body")


def test_workspace_collapsed_mobile_summary_uses_scannable_buttons_without_inner_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    mobile_summary = css_rule_body(
        mobile_css,
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-summary",
    )
    assert mobile_summary is not None
    assert "grid-template-columns: minmax(0, 1fr) 44px;" in mobile_summary
    assert "align-items: stretch;" in mobile_summary

    mobile_summary_copy = css_rule_body(
        mobile_css,
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-summary-copy",
    )
    assert mobile_summary_copy is not None
    assert "display: none;" in mobile_summary_copy

    mobile_summary_actions = css_rule_body(
        mobile_css,
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-summary-actions",
    )
    assert mobile_summary_actions is not None
    assert "display: grid;" in mobile_summary_actions
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in mobile_summary_actions
    assert "overflow: visible;" in mobile_summary_actions
    assert "padding-bottom: 0;" in mobile_summary_actions

    mobile_summary_button = css_rule_body(
        mobile_css,
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-summary-button",
    )
    assert mobile_summary_button is not None
    assert "min-width: 0;" in mobile_summary_button
    assert "width: 100%;" in mobile_summary_button
    assert "white-space: normal;" in mobile_summary_button


def test_workspace_collapsed_top_stack_is_competitor_dense_on_tablet_and_mobile():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    tablet_css = css.split("@media (max-width: 920px)", 1)[1].split("@media (max-width: 720px)", 1)[0]
    tablet_chrome = re.search(r"\.commercial-workspace-chrome\.is-collapsed \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert tablet_chrome is not None
    assert "gap: 6px;" in tablet_chrome.group("body")
    assert "padding: 6px 18px 0;" in tablet_chrome.group("body")

    tablet_search = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-search \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert tablet_search is not None
    assert "display: grid;" in tablet_search.group("body")
    assert "grid-template-columns: minmax(0, 1fr) auto auto;" in tablet_search.group("body")
    assert "min-height: 52px;" in tablet_search.group("body")

    tablet_summary = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-summary \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert tablet_summary is not None
    assert "grid-template-columns: minmax(120px, 0.45fr) minmax(180px, 0.24fr) minmax(0, 1fr) auto;" in tablet_summary.group("body")
    assert "min-height: 52px;" in tablet_summary.group("body")

    tablet_confidence = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-confidence \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert tablet_confidence is not None
    assert "display: none;" in tablet_confidence.group("body")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_chrome = re.search(r"\.commercial-workspace-chrome\.is-collapsed \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_chrome is not None
    assert "gap: 6px;" in mobile_chrome.group("body")
    assert "padding: 6px 10px 0;" in mobile_chrome.group("body")

    mobile_search = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-search \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_search is not None
    assert "grid-template-columns: minmax(0, 1fr) auto;" in mobile_search.group("body")
    assert "min-height: 50px;" in mobile_search.group("body")

    mobile_summary = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-summary \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_summary is not None
    assert "grid-template-columns: minmax(0, 1fr) 44px;" in mobile_summary.group("body")
    assert "align-items: stretch;" in mobile_summary.group("body")
    assert "min-height: auto;" in mobile_summary.group("body")

    mobile_toggle = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-toggle \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_toggle is not None
    assert "width: 44px;" in mobile_toggle.group("body")
    assert "font-size: 0;" in mobile_toggle.group("body")

    mobile_toggle_icon = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-toggle::after \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_toggle_icon is not None
    assert 'content: "+";' in mobile_toggle_icon.group("body")

    mobile_hero = re.search(r"\.commercial-hero \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_hero is not None
    assert "min-height: 44px;" in mobile_hero.group("body")
    assert "padding: 7px 8px;" in mobile_hero.group("body")
    assert "margin-bottom: 6px;" in mobile_hero.group("body")

    mobile_hero_copy = re.search(r"\.commercial-hero p \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_hero_copy is not None
    assert "display: none;" in mobile_hero_copy.group("body")


def test_narrow_first_screen_keeps_mobile_jump_map_visible_without_overflow():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    tablet_css = css.split("@media (max-width: 920px)", 1)[1].split("@media (max-width: 560px)", 1)[0]
    topbar = re.search(r"\.commercial-topbar \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert topbar is not None
    assert "flex-direction: row;" in topbar.group("body")
    assert "align-items: center;" in topbar.group("body")
    assert "min-height: 60px;" in topbar.group("body")
    assert "padding: 8px 12px;" in topbar.group("body")

    nav = re.search(r"\.commercial-nav \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert nav is not None
    assert "flex-wrap: nowrap;" in nav.group("body")
    assert "overflow-x: auto;" in nav.group("body")

    tablet_jump = re.search(r"\.commercial-jump-deck \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert tablet_jump is not None
    assert "display: flex;" in tablet_jump.group("body")
    assert "flex-wrap: nowrap;" in tablet_jump.group("body")
    assert "overflow-x: auto;" in tablet_jump.group("body")
    assert "padding: 6px 12px;" in tablet_jump.group("body")

    tablet_jump_copy = re.search(r"\.commercial-jump-copy \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert tablet_jump_copy is not None
    assert "display: none;" in tablet_jump_copy.group("body")

    tablet_jump_groups = re.search(r"\.commercial-jump-steps,\n  \.commercial-jump-actions \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert tablet_jump_groups is not None
    assert "display: contents;" in tablet_jump_groups.group("body")

    tablet_hero_copy = re.search(r"\.commercial-hero p \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert tablet_hero_copy is not None
    assert "display: none;" in tablet_hero_copy.group("body")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_jump = css_rule_body(mobile_css, ".commercial-shell > .commercial-jump-deck")
    assert mobile_jump is not None
    assert "display: flex;" in mobile_jump
    assert "overflow-x: auto;" in mobile_jump
    assert "margin: 8px 10px 6px;" in mobile_jump

    mobile_jump_copy = re.search(r"\.commercial-jump-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_jump_copy is not None
    assert "display: grid;" in mobile_jump_copy.group("body")
    assert "flex: 0 0 168px;" in mobile_jump_copy.group("body")
    assert "min-height: 48px;" in mobile_jump_copy.group("body")

    mobile_status = re.search(r"\.commercial-status \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_status is not None
    assert "display: none;" in mobile_status.group("body")


def test_workspace_chrome_adds_competitor_grade_lens_strip_for_information_architecture():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "進階追蹤表視圖",
        "單股研究頁籤",
        "投組 X-Ray 頁籤",
        "價格",
        "財務",
        "績效",
        "風險",
        "新聞",
        "報價",
        "圖表",
        "財報共識",
        "實績",
        "共識",
        "警示",
        "持股",
        "曝險",
        "基準",
        "再平衡",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-lens",
        ".commercial-workspace-lens-copy",
        ".commercial-workspace-lens-grid",
        ".commercial-workspace-lens-button",
        ".commercial-workspace-lens-button.is-primary",
    ):
        assert selector in css
    assert "function commercialWorkspaceLensConfig(pageName, ticker, context = {})" in js
    assert "commercialWorkspaceLensConfig(pageName, normalized, context)" in js
    assert "data-commercial-workspace-lens" in js
    assert "data-commercial-workspace-lens-target" in js
    assert "writeCommercialMemory(`workspace-lens-${activeId}`" in js
    assert "研究鏡頭已打開" in js
    assert "{ id: 'actuals-consensus', label: '實績', metric: '共識', target: 'commercial-stock-actuals-consensus' }" in js


def test_workspace_lens_strip_keeps_mobile_tabs_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workspace-lens" in mobile_css
    lens = re.search(r"\.commercial-workspace-lens \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert lens is not None
    assert "display: none;" in lens.group("body")
    assert "{ id: 'chart', label: '圖表', metric: '區間', target: 'commercial-stock-price-chart' }" in (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    assert "{ id: 'open-financials', label: '打開財務', metric: '實績', target: 'commercial-stock-actuals-consensus' }" in (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")


def test_workspace_chrome_adds_page_specific_alert_quick_setup_for_distinct_requirements():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "警示快速設定",
        "追蹤表警示設定",
        "單股警示設定",
        "投組警示設定",
        "價格掃描",
        "新聞/公告",
        "評級/重跑",
        "價格觸發",
        "財報/公告",
        "評級變動",
        "漂移守門",
        "曝險風險",
        "客戶回顧",
        "警示設定已打開",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-alert-setup",
        ".commercial-workspace-alert-setup-copy",
        ".commercial-workspace-alert-setup-grid",
        ".commercial-workspace-alert-setup-button",
        ".commercial-workspace-alert-setup-button.is-primary",
    ):
        assert selector in css
    assert "function commercialWorkspaceAlertSetupConfig(pageName, ticker, context = {})" in js
    assert "commercialWorkspaceAlertSetupConfig(pageName, normalized, context)" in js
    assert "data-commercial-workspace-alert-setup" in js
    assert "data-commercial-workspace-alert-setup-target" in js
    assert "writeCommercialMemory(`workspace-alert-setup-${activeId}`" in js
    assert "{ id: 'news-filings', label: '新聞/公告', metric: '推播+收件匣', target: 'commercial-workbench-event-queue' }" in js
    assert "{ id: 'earnings-filings', label: '財報/公告', metric: '日曆+公告', target: 'commercial-stock-event-queue' }" in js
    assert "{ id: 'exposure-risk', label: '曝險風險', metric: '產業+因子', target: 'commercial-portfolio-exposure-map' }" in js


def test_workspace_alert_quick_setup_keeps_mobile_actions_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workspace-alert-setup" in mobile_css
    setup = re.search(r"\.commercial-workspace-alert-setup \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert setup is not None
    assert "display: none;" in setup.group("body")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    assert "{ id: 'alerts', label: '警示', metric: '追蹤', target: 'commercial-workbench-alert-center' }" in js
    assert "{ id: 'alerts', label: '提醒', metric: '推播', target: 'commercial-stock-alert-center' }" in js
    assert "{ id: 'alerts', label: '警示', metric: '規則', target: 'commercial-portfolio-alert-center' }" in js


def test_workspace_chrome_adds_page_specific_setup_coach_for_distinct_first_run_tasks():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "設定教練",
        "追蹤表設定教練",
        "單股設定教練",
        "投組設定教練",
        "加入股票",
        "設定警示",
        "產生報告",
        "載入快照",
        "檢查財務",
        "建立報告",
        "匯入持股",
        "設定模型",
        "客戶包",
        "設定教練已打開",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-setup-coach",
        ".commercial-workspace-setup-coach-copy",
        ".commercial-workspace-setup-coach-grid",
        ".commercial-workspace-setup-coach-step",
        ".commercial-workspace-setup-coach-step.is-primary",
    ):
        assert selector in css
    assert "function commercialWorkspaceSetupCoachConfig(pageName, ticker, context = {})" in js
    assert "commercialWorkspaceSetupCoachConfig(pageName, normalized, context)" in js
    assert "data-commercial-workspace-setup-coach" in js
    assert "data-commercial-workspace-setup-target" in js
    assert "writeCommercialMemory(`workspace-setup-coach-${activeId}`" in js
    assert "{ id: 'add-symbols', label: '加入股票', metric: '追蹤表', target: 'commercial-workbench-setup-launchpad', primary: true }" in js
    assert "{ id: 'load-snapshot', label: '載入快照', metric: '報價', target: 'commercial-stock-setup-launchpad', primary: true }" in js
    assert "{ id: 'check-financials', label: '檢查財務', metric: '實績', target: 'commercial-stock-actuals-consensus' }" in js
    assert "{ id: 'import-holdings', label: '匯入持股', metric: 'CSV/PDF', target: 'commercial-portfolio-setup-launchpad', primary: true }" in js


def test_workspace_chrome_adds_page_specific_view_presets_for_custom_dashboard_workflows():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "視圖預設",
        "追蹤表視圖預設",
        "單股視圖預設",
        "投組視圖預設",
        "核心清單",
        "事件觀察",
        "報告隊列",
        "快照視圖",
        "財報視圖",
        "研究包",
        "持股 X-Ray",
        "漂移複查",
        "客戶會議",
        "視圖預設已打開",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-view-presets",
        ".commercial-workspace-view-presets-copy",
        ".commercial-workspace-view-presets-grid",
        ".commercial-workspace-view-preset",
        ".commercial-workspace-view-preset.is-primary",
    ):
        assert selector in css
    assert "function commercialWorkspaceViewPresetConfig(pageName, ticker, context = {})" in js
    assert "commercialWorkspaceViewPresetConfig(pageName, normalized, context)" in js
    assert "data-commercial-workspace-view-preset" in js
    assert "data-commercial-workspace-view-preset-target" in js
    assert "writeCommercialMemory(`workspace-view-preset-${activeId}`" in js
    assert "{ id: 'core-list', label: '核心清單', metric: '欄位', target: 'commercial-workbench-table', primary: true }" in js
    assert "{ id: 'event-watch', label: '事件觀察', metric: '財報/新聞', target: 'commercial-workbench-event-calendar' }" in js
    assert "{ id: 'earnings-view', label: '財報視圖', metric: '實績', target: 'commercial-stock-actuals-consensus' }" in js
    assert "{ id: 'client-meeting', label: '客戶會議', metric: '報告包', target: 'commercial-portfolio-client-pack' }" in js


def test_workspace_search_adds_page_specific_command_menu_for_terminal_like_navigation():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "命令選單",
        "追蹤表命令",
        "單股命令",
        "投組命令",
        "打開核心表",
        "打開快照面板",
        "匯出追蹤表",
        "打開財務",
        "設定價格提醒",
        "建立研究包",
        "打開 X-Ray",
        "打開漂移複查",
        "準備客戶包",
        "命令已打開",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-command-menu",
        ".commercial-workspace-command-menu[hidden]",
        ".commercial-workspace-search:focus-within .commercial-workspace-command-menu[hidden]",
        ".commercial-workspace-command-grid",
        ".commercial-workspace-command-button",
        ".commercial-workspace-command-button.is-primary",
    ):
        assert selector in css
    focus_fallback = re.search(r"\.commercial-workspace-search:focus-within \.commercial-workspace-command-menu\[hidden\] \{(?P<body>.*?)\n\}", css, re.S)
    assert focus_fallback is not None
    assert "display: grid;" in focus_fallback.group("body")
    assert "function commercialWorkspaceCommandConfig(pageName, ticker, context = {})" in js
    assert "commercialWorkspaceCommandConfig(pageName, normalized, context)" in js
    assert "data-commercial-command-menu" in js
    assert "data-commercial-command-target" in js
    assert "data-commercial-command-search" in js
    assert "writeCommercialMemory(`workspace-command-${activeId}`" in js
    assert "{ id: 'open-core-list', label: '打開核心表', metric: '表格', target: 'commercial-workbench-table', primary: true }" in js
    assert "{ id: 'open-financials', label: '打開財務', metric: '實績', target: 'commercial-stock-actuals-consensus' }" in js
    assert "{ id: 'prepare-client-pack', label: '準備客戶包', metric: '分享', target: 'commercial-portfolio-client-pack' }" in js


def test_workspace_search_adds_symbol_suggestions_for_general_user_ticker_discovery():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "股票建議",
        "台積電",
        "Apple",
        "NVIDIA",
        "打開股票",
        "股票已打開",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-symbol-suggestions",
        ".commercial-workspace-symbol-suggestions[hidden]",
        ".commercial-workspace-symbol-suggestion-grid",
        ".commercial-workspace-symbol-suggestion",
    ):
        assert selector in css
    assert "function commercialWorkspaceSymbolSuggestions(pageName, ticker, context = {})" in js
    assert "const symbolSuggestions = commercialWorkspaceSymbolSuggestions(pageName, normalized, context)" in js
    assert "data-commercial-symbol-suggestions" in js
    assert "data-commercial-symbol-suggestion" in js
    assert "data-commercial-symbol-search" in js
    assert "const symbolSuggestion = event.target.closest('[data-commercial-symbol-suggestion]');" in js
    assert "onTickerSubmit(symbolTicker);" in js
    assert "writeCommercialMemory(`workspace-symbol-${activeId}`" in js


def test_command_menu_is_overlay_not_layout_height_on_mobile():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    command_menu = re.search(r"\.commercial-workspace-command-menu \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert command_menu is not None
    assert "position: fixed;" in command_menu.group("body")
    assert "left: 12px;" in command_menu.group("body")
    assert "right: 12px;" in command_menu.group("body")
    command_grid = re.search(r"\.commercial-workspace-command-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert command_grid is not None
    assert "grid-template-columns: 1fr;" in command_grid.group("body")
    command_button = re.search(r"\.commercial-workspace-command-button \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert command_button is not None
    assert "min-height: 44px;" in command_button.group("body")
    assert "width: 100%;" in command_button.group("body")
    specific_command_button = re.search(r"\.commercial-workspace-search \.commercial-workspace-command-button \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert specific_command_button is not None
    assert "min-height: 44px;" in specific_command_button.group("body")
    assert "width: 100%;" in specific_command_button.group("body")


def test_symbol_suggestions_fit_mobile_command_overlay_touch_targets():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    symbol_grid = re.search(r"\.commercial-workspace-symbol-suggestion-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert symbol_grid is not None
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in symbol_grid.group("body")
    symbol_button = re.search(r"\.commercial-workspace-symbol-suggestion \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert symbol_button is not None
    assert "min-height: 44px;" in symbol_button.group("body")
    assert "width: 100%;" in symbol_button.group("body")
    specific_symbol_button = re.search(r"\.commercial-workspace-search \.commercial-workspace-symbol-suggestion \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert specific_symbol_button is not None
    assert "min-height: 44px;" in specific_symbol_button.group("body")
    assert "width: 100%;" in specific_symbol_button.group("body")


def test_tablet_width_workspace_chrome_does_not_keep_desktop_min_content_widths():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 920px)" in css
    tablet_css = css.split("@media (max-width: 920px)", 1)[1].split("@media (max-width: 560px)", 1)[0]
    workspace_chrome = re.search(r"\.commercial-workspace-chrome \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert workspace_chrome is not None
    assert "grid-template-columns: minmax(0, 1fr);" in workspace_chrome.group("body")
    assert "max-width: 100%;" in workspace_chrome.group("body")

    grouped_layout = re.search(
        r"\.commercial-workspace-summary,\n"
        r"  \.commercial-workspace-view-presets,\n"
        r"  \.commercial-workspace-setup-coach,\n"
        r"  \.commercial-workspace-lens,\n"
        r"  \.commercial-workspace-alert-setup \{(?P<body>.*?)\n  \}",
        tablet_css,
        re.S,
    )
    assert grouped_layout is not None
    assert "grid-template-columns: minmax(0, 1fr);" in grouped_layout.group("body")
    mission_deck = re.search(r"\.commercial-mission-deck \{(?P<body>.*?)\n  \}", tablet_css, re.S)
    assert mission_deck is not None
    assert "grid-template-columns: minmax(0, 1fr);" in mission_deck.group("body")
    assert ".commercial-mission-lane-grid" in tablet_css
    assert ".commercial-mission-actions" in tablet_css


def test_command_menu_opens_on_search_tap_for_mobile_focus_reliability():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "root.addEventListener('pointerdown', event => {" in js
    assert "const searchTap = event.target.closest('[data-commercial-workspace-search]');" in js
    assert "if (searchTap) updateCommandMenu('');" in js
    assert "const searchClick = event.target.closest('[data-commercial-workspace-search]');" in js
    assert "if (searchClick) {" in js


def test_view_presets_stay_accessible_in_details_on_mobile_without_reintroducing_scroll_fatigue():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    presets = re.search(r"\.commercial-workspace-view-presets \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert presets is not None
    assert "grid-template-columns: 1fr;" in presets.group("body")
    assert "padding: 7px;" in presets.group("body")
    presets_copy = re.search(r"\.commercial-workspace-view-presets-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert presets_copy is not None
    assert "display: none;" in presets_copy.group("body")
    presets_grid = re.search(r"\.commercial-workspace-view-presets-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert presets_grid is not None
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in presets_grid.group("body")
    assert "overflow-x: visible;" in presets_grid.group("body")
    preset_button = re.search(r"\.commercial-workspace-view-preset \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert preset_button is not None
    assert "min-height: 42px;" in preset_button.group("body")
    assert "width: 100%;" in preset_button.group("body")


def test_setup_coach_is_desktop_visible_but_mobile_uses_page_task_dock_entry():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    setup = re.search(r"\.commercial-workspace-setup-coach \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert setup is not None
    assert "display: none;" in setup.group("body")
    dock = re.search(r"\.commercial-mobile-dock \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert dock is not None
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in dock.group("body")
    dock_button = re.search(r"\.commercial-mobile-dock-button \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert dock_button is not None
    assert "padding: 7px 4px;" in dock_button.group("body")
    assert ".slice(0, 5)" in js
    assert "{ id: 'snapshot-pane', label: '快照', metric: normalized, target: 'commercial-workbench-detail' }" in js
    assert "{ id: 'research-pack', label: '研究包', metric: '報告', target: 'commercial-stock-report-composer' }" in js
    assert "{ id: 'import', label: '匯入', metric: 'CSV', target: 'commercial-portfolio-csv' }" in js


def test_mobile_workspace_chrome_defers_secondary_strips_to_dock_so_first_content_stays_visible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    search = re.search(r"\.commercial-workspace-search \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert search is not None
    assert "display: grid;" in search.group("body")
    assert "grid-template-columns: minmax(0, 1fr) auto;" in search.group("body")
    assert "flex-wrap: nowrap;" in search.group("body")
    copy_link = re.search(r"\.commercial-workspace-search \[data-commercial-workspace-copy-link\] \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert copy_link is not None
    assert "display: none;" in copy_link.group("body")
    search_label = re.search(r"\.commercial-workspace-search \.commercial-workspace-label \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert search_label is not None
    assert "display: none;" in search_label.group("body")
    for selector in (".commercial-workspace-setup-coach", ".commercial-workspace-lens", ".commercial-workspace-alert-setup"):
        block = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", mobile_css, re.S)
        assert block is not None
        assert "display: none;" in block.group("body")
    assert "const stickyOffsetCap = window.innerWidth <= 560 ? 220 : 320;" in js
    assert "Math.min(topbarHeight + workspaceHeight + stickyContextHeight + cushion, stickyOffsetCap)" in js


def test_mobile_workspace_chrome_prioritizes_page_tasks_before_display_settings():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_summary_actions = css_rule_body(
        mobile_css,
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-summary-actions",
    )
    assert mobile_summary_actions is not None
    assert "grid-column: 1;" in mobile_summary_actions
    assert "grid-row: 1;" in mobile_summary_actions
    assert "padding-right: 50px;" in mobile_summary_actions

    mobile_display_quick = css_rule_body(
        mobile_css,
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-display-quick",
    )
    assert mobile_display_quick is not None
    assert "grid-column: 1 / -1;" in mobile_display_quick
    assert "grid-row: 2;" in mobile_display_quick
    assert "padding-right: 0;" in mobile_display_quick
    assert "opacity: 0.74;" in mobile_display_quick

    mobile_dock_config = re.search(
        r"function commercialMobileDockConfig\(pageName, ticker, context = \{\}\) \{(?P<body>.*?)\n    \}\n    function commercialDisplayPreference",
        js,
        re.S,
    )
    assert mobile_dock_config is not None
    mobile_dock_body = mobile_dock_config.group("body")

    for snippet in (
        "{ id: 'table', label: '決策', metric: '檔數', target: 'commercial-workbench-table', primary: true }",
        "{ id: 'snapshot-pane', label: '快照', metric: normalized, target: 'commercial-workbench-detail' }",
        "{ id: 'events', label: '事件', metric: '新聞', target: 'commercial-workbench-event-calendar' }",
        "{ id: 'reports', label: '報告', metric: '批次', target: 'commercial-workbench-monitor-center' }",
        "{ id: 'snapshot', label: '快照', metric: '報價', target: 'commercial-stock-snapshot-hero', primary: true }",
        "{ id: 'ratings', label: '評級', metric: '因子', target: 'commercial-stock-factor-lens' }",
        "{ id: 'financials', label: '財報', metric: '財報', target: 'commercial-stock-actuals-consensus' }",
        "{ id: 'alerts', label: '提醒', metric: '推播', target: 'commercial-stock-alert-center' }",
        "{ id: 'exposure', label: '曝險', metric: 'X-Ray', target: 'commercial-portfolio-exposure-map', primary: true }",
        "{ id: 'rebalance', label: '再平衡', metric: '漂移', target: 'commercial-portfolio-drift-review' }",
        "{ id: 'alerts', label: '警示', metric: '規則', target: 'commercial-portfolio-alert-center' }",
        "{ id: 'client-pack', label: '客戶包', metric: '分享', target: 'commercial-portfolio-client-pack' }",
    ):
        assert snippet in mobile_dock_body

    for generic_mobile_label in (
        "{ id: 'table', label: 'Table'",
        "{ id: 'snapshot', label: 'Snapshot'",
        "{ id: 'exposure', label: 'Exposure'",
        "{ id: 'setup', label: 'Setup'",
    ):
        assert generic_mobile_label not in mobile_dock_body


def test_sticky_scroll_offset_caps_desktop_workspace_height_for_deep_flow_targets():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    offset_helper = re.search(
        r"function commercialStickyOffset\(target = null\) \{(?P<body>.*?)\n    \}",
        js,
        re.S,
    )
    assert offset_helper is not None
    body = offset_helper.group("body")
    assert "const stickyOffsetCap = window.innerWidth <= 560 ? 220 : 320;" in body
    assert "const stickyContextHeight = commercialStickyContextHeight(target);" in body
    assert "Math.min(topbarHeight + workspaceHeight + stickyContextHeight + cushion, stickyOffsetCap)" in body
    assert "Infinity" not in body


def test_task_scroll_offset_accounts_for_sticky_context_without_readability_overlap():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "function commercialStickyContextHeight(target)" in js
    for selector in (
        ".commercial-context-bar",
        ".commercial-workspace-command-bar",
        ".commercial-focus-dock",
        ".commercial-section-nav",
    ):
        assert selector in js
    assert "sticky.compareDocumentPosition(target) & Node.DOCUMENT_POSITION_FOLLOWING" in js
    assert "commercialStickyOffset(target)" in js

    context_bar = re.search(r"\.commercial-context-bar \{(?P<body>.*?)\n\}", css, re.S)
    assert context_bar is not None
    assert "position: sticky;" in context_bar.group("body")
    assert "background-color: rgba(7, 17, 30, 0.98);" in context_bar.group("body")

    command_bar = re.search(r"\.commercial-workspace-command-bar \{(?P<body>.*?)\n\}", css, re.S)
    assert command_bar is not None
    command_body = command_bar.group("body")
    assert "position: relative;" in command_body
    assert "position: sticky;" not in command_body
    assert "background-color: rgba(7, 17, 30, 0.98);" in command_body

    focus_dock = re.search(r"\.commercial-focus-dock \{(?P<body>.*?)\n\}", css, re.S)
    assert focus_dock is not None
    focus_body = focus_dock.group("body")
    assert "position: relative;" in focus_body
    assert "position: sticky;" not in focus_body
    assert "background-color: rgba(7, 17, 30, 0.98);" in focus_body


def test_scroll_task_target_realigns_mobile_targets_after_dynamic_layout_settles():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function commercialTaskScrollSettleDelays()" in js
    assert "return window.innerWidth <= 560 ? [700, 1300, 1900, 2800, 3800] : [900, 1500, 2100, 3200, 4500];" in js
    assert "function commercialViewportBottomCushion()" in js
    assert "const mobileActionBar = document.getElementById('commercial-mobile-action-bar');" in js
    assert "const visible = getComputedStyle(mobileActionBar).display !== 'none' && rect.height > 0;" in js
    assert "return Math.ceil(rect.height + Math.max(fallback, window.innerHeight - rect.bottom));" in js
    assert "function commercialScrollableAncestor(target)" in js
    assert "node.scrollHeight > node.clientHeight + 4" in js

    scroll_helper = re.search(
        r"function scrollCommercialTaskTarget\(targetId, options = \{\}\) \{(?P<body>.*?)\n    \}",
        js,
        re.S,
    )
    assert scroll_helper is not None
    body = scroll_helper.group("body")
    assert "const currentTarget = () => document.getElementById(targetId);" in body
    assert "const firstTarget = currentTarget();" in body
    assert "if (!firstTarget) return false;" in body
    assert "revealCommercialSecondaryModule(firstTarget);" in body
    assert "const alignTarget = (behavior) => {" in body
    assert "const target = currentTarget();" in body
    assert "const scrollParent = commercialScrollableAncestor(target);" in body
    assert "scrollParent.scrollTo({ top, behavior });" in body
    assert "scrollParent.scrollTop + targetRect.top - parentRect.top - 12" in body
    assert "const revealTarget = () => {" in body
    assert "const bottomLimit = window.innerHeight - commercialViewportBottomCushion();" in body
    assert "if (rect.top < topLimit || rect.height >= bottomLimit - topLimit) {" in body
    assert "const nextTop = Math.max(0, window.scrollY + rect.bottom - bottomLimit);" in body
    assert "target.scrollIntoView({ block: 'center', behavior: 'auto' });" not in body
    assert "commercialTaskScrollSettleDelays().forEach(delay => {" in body
    assert "window.setTimeout(() => { alignTarget('auto'); revealTarget(); }, delay);" in body
    assert "target.getBoundingClientRect().top + window.scrollY - commercialStickyOffset(target)" in body


def test_workspace_chrome_adds_page_specific_mobile_action_dock_for_app_like_navigation():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "手機動作列",
        "追蹤表行動捷徑",
        "個股行動捷徑",
        "投組行動捷徑",
        "決策",
        "報告",
        "快照",
        "評級",
        "財報",
        "曝險",
        "再平衡",
        "客戶包",
        "匯入",
        "手機動作已打開",
    ):
        assert label in js
    for selector in (
        ".commercial-mobile-dock",
        ".commercial-mobile-dock-button",
        ".commercial-mobile-dock-button.is-primary",
        ".commercial-mobile-dock-button span",
        ".commercial-mobile-dock-button strong",
    ):
        assert selector in css
    assert "function commercialMobileDockConfig(pageName, ticker, context = {})" in js
    assert "commercialMobileDockConfig(pageName, normalized, context)" in js
    assert "data-commercial-mobile-dock" in js
    assert "data-commercial-mobile-dock-target" in js
    assert "writeCommercialMemory(`workspace-mobile-dock-${activeId}`" in js
    assert "{ id: 'reports', label: '報告', metric: '批次', target: 'commercial-workbench-monitor-center' }" in js
    assert "{ id: 'snapshot', label: '快照', metric: '報價', target: 'commercial-stock-snapshot-hero', primary: true }" in js
    assert "{ id: 'client-pack', label: '客戶包', metric: '分享', target: 'commercial-portfolio-client-pack' }" in js
    assert "{ id: 'import', label: '匯入', metric: 'CSV', target: 'commercial-portfolio-csv' }" in js


def test_mobile_action_dock_is_fixed_tappable_and_does_not_cover_content_on_mobile():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    page = re.search(r"\.commercial-page \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert page is not None
    assert "padding-bottom: calc(244px + env(safe-area-inset-bottom));" in page.group("body")
    dock = re.search(r"\.commercial-mobile-dock \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert dock is not None
    for declaration in (
        "position: fixed;",
        "left: 12px;",
        "right: 12px;",
        "bottom: calc(144px + env(safe-area-inset-bottom));",
        "display: grid;",
        "grid-template-columns: repeat(5, minmax(0, 1fr));",
        "overflow-x: visible;",
        "z-index: 90;",
    ):
        assert declaration in dock.group("body")
    button = re.search(r"\.commercial-mobile-dock-button \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert button is not None
    assert "min-height: 56px;" in button.group("body")
    assert "width: 100%;" in button.group("body")


def test_mobile_workspace_dock_stacks_above_primary_action_bar_without_pointer_overlap():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    page = css_rule_body(mobile_css, ".commercial-page")
    assert page is not None
    assert "padding-bottom: calc(244px + env(safe-area-inset-bottom));" in page

    workspace_dock = css_rule_body(mobile_css, ".commercial-mobile-dock")
    assert workspace_dock is not None
    assert "bottom: calc(144px + env(safe-area-inset-bottom));" in workspace_dock
    assert "z-index: 90;" in workspace_dock

    primary_bar = css_rule_body(mobile_css, ".commercial-mobile-action-bar")
    assert primary_bar is not None
    assert "bottom: max(10px, env(safe-area-inset-bottom));" in primary_bar
    assert "z-index: 80;" in primary_bar

    main = css_rule_body(mobile_css, ".commercial-main")
    assert main is not None
    assert "padding-bottom: 240px;" in main


def test_workspace_summary_adds_page_specific_data_confidence_for_commercial_trust():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in (
        "資料信心",
        "追蹤表信心",
        "單股信心",
        "投組信心",
        "決策資料",
        "報價新鮮度",
        "持股同步",
        "覆蓋列",
        "財務",
        "曝險",
        "新聞/公告",
        "公告",
        "客戶就緒",
        "資料信心已打開",
    ):
        assert label in js
    for selector in (
        ".commercial-workspace-confidence",
        ".commercial-workspace-confidence-item",
        ".commercial-workspace-confidence-item.is-live",
        ".commercial-workspace-confidence-item.is-warning",
    ):
        assert selector in css
    assert "function commercialWorkspaceConfidenceConfig(pageName, ticker, context = {})" in js
    assert "commercialWorkspaceConfidenceConfig(pageName, normalized, context)" in js
    assert "data-commercial-workspace-confidence" in js
    assert "data-commercial-workspace-confidence-target" in js
    assert "writeCommercialMemory(`workspace-confidence-${activeId}`" in js
    assert "{ id: 'decision-data', label: '決策資料', metric: sourceLabel, target: 'commercial-workbench-data-status', tone: sourceTone, primary: true }" in js
    assert "{ id: 'financials', label: '財務', metric: '實績', target: 'commercial-stock-data-coverage' }" in js
    assert "{ id: 'client-ready', label: '客戶就緒', metric: '報告包', target: 'commercial-portfolio-client-pack' }" in js


def test_workspace_confidence_route_strip_uses_short_labels_without_vertical_wrapping():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function commercialWorkspaceConfidenceLabel(label)" in js
    for mapping in (
        "'決策資料': '資料'",
        "'覆蓋列': '列數'",
        "'新聞/公告': '新聞'",
        "'報價新鮮度': '報價'",
        "'財務': '財務'",
        "'持股同步': '持股'",
        "'曝險': '風險'",
        "'客戶就緒': '報告'",
    ):
        assert mapping in js
    assert "shortLabel: commercialWorkspaceConfidenceLabel(item.label)" in js
    assert "title=\"${escapeHtml(item.label || '')}\"" in js
    assert "${escapeHtml(item.shortLabel || item.label || '')}" in js

    label_blocks = re.findall(r"\.commercial-workspace-confidence-item span \{(?P<body>.*?)\n\}", css, re.S)
    assert label_blocks
    assert any(
        "white-space: nowrap;" in block
        and "text-overflow: ellipsis;" in block
        and "overflow-wrap: normal;" in block
        for block in label_blocks
    )

    collapsed_item = re.search(
        r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-confidence-item \{(?P<body>.*?)\n\}",
        css,
        re.S,
    )
    assert collapsed_item is not None
    assert "min-height: 44px;" in collapsed_item.group("body")

    collapsed_summary = re.search(
        r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-summary \{(?P<body>.*?)\n\}",
        css,
        re.S,
    )
    assert collapsed_summary is not None
    assert "grid-template-columns: minmax(180px, 0.2fr) minmax(216px, 0.22fr) minmax(276px, 1fr) minmax(104px, auto);" in collapsed_summary.group("body")

    collapsed_summary_copy = re.search(
        r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-summary-copy \{(?P<body>.*?)\n\}",
        css,
        re.S,
    )
    assert collapsed_summary_copy is not None
    assert "grid-template-columns: minmax(0, 1fr);" in collapsed_summary_copy.group("body")

    collapsed_confidence = re.search(
        r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-confidence \{(?P<body>.*?)\n\}",
        css,
        re.S,
    )
    assert collapsed_confidence is not None
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in collapsed_confidence.group("body")


def test_workspace_data_confidence_stays_compact_and_tappable_on_mobile():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workspace-confidence" in mobile_css
    confidence = re.search(r"\.commercial-workspace-confidence \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert confidence is not None
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in confidence.group("body")
    assert "overflow-x: visible;" in confidence.group("body")
    summary_detail = re.search(r"\.commercial-workspace-summary-copy em \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert summary_detail is not None
    assert "display: none;" in summary_detail.group("body")
    lens = re.search(r"\.commercial-workspace-lens \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert lens is not None
    assert "display: none;" in lens.group("body")
    item = re.search(r"\.commercial-workspace-confidence-item \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert item is not None
    assert "min-height: 44px;" in item.group("body")
    assert "width: 100%;" in item.group("body")


def test_workbench_ticker_click_rerenders_workspace_chrome_for_snapshot_context():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    ticker_handler = re.search(
        r"document\.addEventListener\('click', event => \{\s+"
        r"const button = event\.target\.closest\('\[data-commercial-ticker\]'\);"
        r"(?P<body>.*?)syncCommercialContextTicker\(activeTicker\);",
        js,
        re.S,
    )
    assert ticker_handler is not None
    assert "selectTicker(activeTicker, visibleRows.length ? visibleRows : rows, true)" in ticker_handler.group("body")
    assert "renderCommercialWorkspaceChrome(document.getElementById('commercial-workspace-chrome'), 'research-workbench', activeTicker" in ticker_handler.group("body")


def test_commercial_pages_add_page_specific_outcome_cockpits():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-decision-cockpit",
        "stock-detail.html": "commercial-stock-research-cockpit",
        "portfolio-dashboard.html": "commercial-portfolio-rebalance-cockpit",
    }
    for filename, cockpit_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert f'id="{cockpit_id}"' in html
        for other_id in set(html_by_page.values()) - {cockpit_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-page-cockpit",
        ".commercial-cockpit-card",
        ".commercial-cockpit-queue",
        ".commercial-cockpit-actions",
    ):
        assert selector in css
    for function_name in (
        "function renderWorkbenchDecisionCockpit(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockResearchCockpit(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioRebalanceCockpit(root, payload, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Watchlist Decision Queue",
        "Snapshot Research Path",
        "Portfolio Rebalance Board",
        "Options Chain",
        "Short Interest",
        "Insider Trades",
        "Filings Queue",
    ):
        assert label in js
    assert "renderWorkbenchDecisionCockpit(document.getElementById('commercial-workbench-decision-cockpit')" in js
    assert "renderStockResearchCockpit(document.getElementById('commercial-stock-research-cockpit')" in js
    assert "renderPortfolioRebalanceCockpit(document.getElementById('commercial-portfolio-rebalance-cockpit')" in js


def test_commercial_pages_add_page_specific_module_layout_pinboards():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-module-layout",
        "stock-detail.html": "commercial-stock-module-layout",
        "portfolio-dashboard.html": "commercial-portfolio-module-layout",
    }
    for filename, module_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert f'id="{module_id}"' in html
        for other_id in set(html_by_page.values()) - {module_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-module-pinboard",
        ".commercial-module-card",
        ".commercial-module-card.is-pinned",
        ".commercial-module-actions",
    ):
        assert selector in css
    for function_name in (
        "function commercialModuleLayoutPreference(scope, fallbackPins)",
        "function renderCommercialModulePinboard(root, config, savedPins = [])",
        "function bindCommercialModulePinboard(root, scope, configFactory)",
        "function renderWorkbenchModulePinboard(root, activeView, currentFilter)",
        "function renderStockModulePinboard(root, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioModulePinboard(root, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Widget Layout",
        "Pinned Modules",
        "Pin to top",
        "Save Layout",
        "Reset Layout",
        "Snapshot Dock",
        "Alerts Queue",
        "Report Pack",
        "Price Chart",
        "Financials",
        "Filings Queue",
        "Portfolio X-Ray",
        "Rebalance Ticket",
        "Client Pack",
    ):
        assert label in js
    assert "writeCommercialMemory(`module-layout-${scope}`" in js
    assert "data-commercial-module-pin" in js
    assert "data-commercial-module-target" in js
    assert "renderWorkbenchModulePinboard(document.getElementById('commercial-workbench-module-layout')" in js
    assert "renderStockModulePinboard(document.getElementById('commercial-stock-module-layout')" in js
    assert "renderPortfolioModulePinboard(document.getElementById('commercial-portfolio-module-layout')" in js


def test_module_layout_pinboards_keep_mobile_touch_targets_comfortable():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert ".commercial-module-action {" in css
    assert "min-height: 44px;" in css
    assert "@media (max-width: 560px)" in css
    assert ".commercial-module-action" in css.split("@media (max-width: 560px)", 1)[1]


def test_commercial_pages_add_competitor_grade_visual_analytics_boards():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-visual-board",
        "stock-detail.html": "commercial-stock-chart-workbench",
        "portfolio-dashboard.html": "commercial-portfolio-visual-board",
    }
    for filename, visual_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert f'id="{visual_id}"' in html
        for other_id in set(html_by_page.values()) - {visual_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-visual-board",
        ".commercial-visual-chart",
        ".commercial-visual-layer-button",
        ".commercial-visual-legend",
        ".commercial-visual-table",
    ):
        assert selector in css
    for function_name in (
        "function commercialVisualLayerPreference(scope, fallbackLayer)",
        "function renderCommercialVisualBoard(root, config, activeLayer, interactionState)",
        "function bindCommercialVisualBoard(root, scope, configFactory)",
        "function renderWorkbenchVisualBoard(root, rows, activeTicker, activeView)",
        "function renderStockChartWorkbench(root, snapshot, activeRange, activeScenario, currentTab)",
        "function renderPortfolioVisualBoard(root, payload, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Visual Analytics",
        "Market Lens Board",
        "Chart Workbench",
        "Portfolio Risk Map",
        "Relative Performance",
        "Volume / Events",
        "Baseline Compare",
        "Drawdown Overlay",
        "Allocation Drift",
        "Risk Contribution",
    ):
        assert label in js
    assert "writeCommercialMemory(`visual-layer-${scope}`" in js
    assert "data-commercial-visual-layer" in js
    assert "data-commercial-visual-target" in js
    assert "aria-label=\"Visual Analytics chart\"" in js
    assert "renderWorkbenchVisualBoard(document.getElementById('commercial-workbench-visual-board')" in js
    assert "renderStockChartWorkbench(document.getElementById('commercial-stock-chart-workbench')" in js
    assert "renderPortfolioVisualBoard(document.getElementById('commercial-portfolio-visual-board')" in js


def test_visual_analytics_boards_keep_chart_accessible_and_responsive():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-visual-board" in mobile_css
    assert ".commercial-visual-layer-button" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "commercial-visual-table" in js
    assert "aria-label=\"Visual Analytics table\"" in js
    assert "screen-reader" not in js.lower()


def test_visual_analytics_boards_add_tradingview_like_chart_interactions():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-visual-toolbar",
        ".commercial-visual-tool-button",
        ".commercial-visual-crosshair",
        ".commercial-visual-tooltip",
        ".commercial-visual-event-marker",
        ".commercial-visual-baseline",
        ".commercial-visual-feedback",
    ):
        assert selector in css
    for function_name in (
        "function commercialVisualInteractionPreference(scope)",
        "function visualInteractionPoints(layer)",
        "function commercialVisualInteractionCsv(config, layer)",
        "function exportCommercialVisualData(root, config, layer)",
        "function renderCommercialVisualBoard(root, config, activeLayer, interactionState)",
        "function bindCommercialVisualBoard(root, scope, configFactory)",
    ):
        assert function_name in js
    for label in (
        "Chart Interaction Layer",
        "Crosshair Tooltip",
        "Event Markers",
        "Baseline Toggle",
        "Export Chart Data",
        "Chart data exported",
    ):
        assert label in js
    assert "downloadCommercialText(`onstock-${chartName}-chart-data.csv`" in js
    assert "writeCommercialMemory(`visual-interaction-${scope}`" in js
    assert "data-commercial-visual-point" in js
    assert "data-commercial-visual-tool" in js
    assert "data-commercial-visual-export" in js
    assert "data-commercial-visual-baseline" in js
    assert "aria-label=\"Chart tooltip\"" in js
    assert "role=\"status\"" in js


def test_visual_interactions_keep_mobile_touch_targets_and_keyboard_labels():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-visual-tool-button" in mobile_css
    assert ".commercial-visual-event-marker" in mobile_css
    assert ".commercial-visual-tooltip" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Set chart focus" in js
    assert "type=\"button\" data-commercial-visual-point" in js


def test_commercial_pages_add_competitor_grade_alert_monitor_builders():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-alert-builder",
        "stock-detail.html": "commercial-stock-thesis-alerts",
        "portfolio-dashboard.html": "commercial-portfolio-guardrails",
    }
    for filename, builder_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{builder_id}"') == 1
        for other_id in set(html_by_page.values()) - {builder_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-rule-builder",
        ".commercial-rule-presets",
        ".commercial-rule-button",
        ".commercial-rule-controls",
        ".commercial-rule-actions",
        ".commercial-rule-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialRulePreference(scope, fallbackRule)",
        "function renderCommercialRuleBuilder(root, config, activeRule)",
        "function bindCommercialRuleBuilder(root, scope, configFactory)",
        "function renderWorkbenchAlertBuilder(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockThesisAlerts(root, snapshot, currentTab, activeScenario, activeRange)",
        "function renderPortfolioGuardrails(root, payload, activeLens, activeScenario, activeTargetModel, driftTolerance)",
    ):
        assert function_name in js
    for label in (
        "Alert Rule Builder",
        "Watchlist Alert Recipes",
        "Thesis Alert Builder",
        "Portfolio Guardrails",
        "Price Move Alert",
        "Catalyst Watch",
        "Rebalance Trigger",
        "Bulk Alert Scan",
    ):
        assert label in js
    assert "writeCommercialMemory(`rule-builder-${scope}`" in js
    assert "data-commercial-rule-preset" in js
    assert "data-commercial-rule-save" in js
    assert "data-commercial-rule-target" in js
    assert "aria-label=\"Alert rule builder\"" in js
    assert "renderWorkbenchAlertBuilder(document.getElementById('commercial-workbench-alert-builder')" in js
    assert "renderStockThesisAlerts(document.getElementById('commercial-stock-thesis-alerts')" in js
    assert "renderPortfolioGuardrails(document.getElementById('commercial-portfolio-guardrails')" in js


def test_alert_monitor_builders_keep_mobile_actions_comfortable():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-rule-builder" in mobile_css
    assert ".commercial-rule-button" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-live=\"polite\"" in js
    assert "role=\"status\"" in js
    assert "commercial-rule-control" in js


def test_commercial_pages_add_competitor_grade_data_grid_labs():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-grid-lab",
        "stock-detail.html": "commercial-stock-peer-grid-lab",
        "portfolio-dashboard.html": "commercial-portfolio-holdings-grid-lab",
    }
    for filename, grid_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{grid_id}"') == 1
        for other_id in set(html_by_page.values()) - {grid_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-grid-lab",
        ".commercial-grid-copy",
        ".commercial-grid-views",
        ".commercial-grid-view-button",
        ".commercial-grid-table",
        ".commercial-grid-sort-button",
        ".commercial-grid-summary",
        ".commercial-grid-actions",
    ):
        assert selector in css
    for function_name in (
        "function commercialGridPreference(scope, fallbackView, fallbackSort)",
        "function renderCommercialGridLab(root, config, activeView, sortState)",
        "function bindCommercialGridLab(root, scope, configFactory)",
        "function renderWorkbenchGridLab(root, rows, activeTicker, activeColumnSet)",
        "function renderStockPeerGridLab(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioHoldingsGridLab(root, payload, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Advanced Data Grid",
        "Watchlist Table Lab",
        "Peer Factor Grid",
        "Holdings Drift Grid",
        "Screener Filters View",
        "Analyst / Valuation View",
        "Rebalance View",
        "Save Grid View",
    ):
        assert label in js
    assert "writeCommercialMemory(`grid-lab-${scope}`" in js
    assert "data-commercial-grid-view" in js
    assert "data-commercial-grid-sort" in js
    assert "data-commercial-grid-save" in js
    assert "data-commercial-grid-export" in js
    assert "aria-label=\"Advanced data grid\"" in js
    assert "aria-sort=" in js
    assert "renderWorkbenchGridLab(document.getElementById('commercial-workbench-grid-lab')" in js
    assert "renderStockPeerGridLab(document.getElementById('commercial-stock-peer-grid-lab')" in js
    assert "renderPortfolioHoldingsGridLab(document.getElementById('commercial-portfolio-holdings-grid-lab')" in js


def test_data_grid_labs_keep_mobile_sorting_and_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-grid-lab" in mobile_css
    assert ".commercial-grid-view-button" in mobile_css
    assert ".commercial-grid-sort-button" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "role=\"status\"" in js
    assert "aria-live=\"polite\"" in js
    assert "commercialGridCsv(config, view)" in js


def test_data_grid_labs_preserve_secondary_expansion_when_live_data_rerenders():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "function commercialSecondaryRenderState(root)" in js
    assert "function restoreCommercialSecondaryRenderState(root, state)" in js
    assert "secondaryModule: root?.classList?.contains('commercial-secondary-module')" in js
    assert "expanded: root?.classList?.contains('is-expanded')" in js
    assert "toggleHtml: root.querySelector('[data-commercial-secondary-toggle]')?.outerHTML || ''" in js
    assert "target?.classList?.add('is-expanded');" in js
    assert "target.dataset.commercialPendingSecondaryExpanded = 'true';" in js

    grid_renderer = re.search(
        r"function renderCommercialGridLab\(root, config, activeView, sortState\) \{(?P<body>.*?)\n    \}",
        js,
        re.S,
    )
    assert grid_renderer is not None
    body = grid_renderer.group("body")
    assert body.index("const secondaryState = commercialSecondaryRenderState(root);") < body.index("root.className = `commercial-grid-lab ${config?.tone || ''}`.trim();")
    assert "${secondaryState.toggleHtml}" in body
    assert body.index("restoreCommercialSecondaryRenderState(root, secondaryState);") > body.index("root.innerHTML = `")


def test_commercial_pages_add_competitor_grade_snapshot_inspector_docks():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-snapshot-inspector",
        "stock-detail.html": "commercial-stock-snapshot-inspector",
        "portfolio-dashboard.html": "commercial-portfolio-snapshot-inspector",
    }
    for filename, inspector_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{inspector_id}"') == 1
        for other_id in set(html_by_page.values()) - {inspector_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-snapshot-inspector",
        ".commercial-snapshot-inspector.is-collapsed",
        ".commercial-snapshot-strip",
        ".commercial-snapshot-metric",
        ".commercial-snapshot-actions",
        ".commercial-snapshot-action",
    ):
        assert selector in css
    for function_name in (
        "function commercialSnapshotInspectorPreference(scope)",
        "function renderCommercialSnapshotInspector(root, config, collapsed = false)",
        "function bindCommercialSnapshotInspector(root, scope, configFactory)",
        "function workbenchSnapshotInspectorConfig(snapshot, selectedRow, activeView)",
        "function stockSnapshotInspectorConfig(snapshot, currentTab, activeScenario, activeRange)",
        "function portfolioSnapshotInspectorConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Snapshot Inspector",
        "Watchlist Symbol Details",
        "Stock Snapshot Dock",
        "Portfolio Holding Lens",
        "Open Full Report",
        "Pin Snapshot",
        "Compact",
    ):
        assert label in js
    assert "writeCommercialMemory(`snapshot-inspector-${scope}`" in js
    assert "data-commercial-snapshot-toggle" in js
    assert "data-commercial-snapshot-target" in js
    assert "data-commercial-snapshot-open-stock" in js
    assert "data-commercial-snapshot-copy" in js
    assert "renderCommercialSnapshotInspector(document.getElementById('commercial-workbench-snapshot-inspector')" in js
    assert "renderCommercialSnapshotInspector(document.getElementById('commercial-stock-snapshot-inspector')" in js
    assert "renderCommercialSnapshotInspector(document.getElementById('commercial-portfolio-snapshot-inspector')" in js


def test_snapshot_inspector_docks_keep_mobile_accessible_actions():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    desktop_inspector = re.search(r"\.commercial-snapshot-inspector \{(?P<body>.*?)\n\}", css, re.S)
    assert desktop_inspector is not None
    desktop_body = desktop_inspector.group("body")
    assert "position: relative;" in desktop_body
    assert "position: sticky;" not in desktop_body
    assert "top: 72px;" not in desktop_body
    assert "z-index: 1;" in desktop_body
    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-snapshot-inspector" in mobile_css
    mobile_inspector = re.search(r"\.commercial-snapshot-inspector \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_inspector is not None
    assert "position: static;" in mobile_inspector.group("body")
    assert "z-index: auto;" in mobile_inspector.group("body")
    assert "max-width: 100%;" in mobile_inspector.group("body")
    assert ".commercial-snapshot-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Snapshot Inspector\"" in js
    assert "role=\"status\"" in js
    assert "scrollWorkbenchSnapshotIntoView(detailRoot)" not in js
    assert "scrollWorkbenchSnapshotIntoView(inspectorRoot || detailRoot)" not in js


def test_commercial_pages_add_competitor_grade_research_event_queues():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-event-queue",
        "stock-detail.html": "commercial-stock-event-queue",
        "portfolio-dashboard.html": "commercial-portfolio-event-queue",
    }
    for filename, queue_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{queue_id}"') == 1
        for other_id in set(html_by_page.values()) - {queue_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-event-queue",
        ".commercial-event-copy",
        ".commercial-event-filters",
        ".commercial-event-filter-button",
        ".commercial-event-list",
        ".commercial-event-item",
        ".commercial-event-actions",
        ".commercial-event-action",
        ".commercial-event-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialEventQueuePreference(scope, fallbackFilter)",
        "function renderCommercialEventQueue(root, config, activeFilter)",
        "function bindCommercialEventQueue(root, scope, configFactory)",
        "function commercialEventQueueCsv(config, filter)",
        "function workbenchEventQueueConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockEventQueueConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioEventQueueConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Research/Event Queue",
        "Watchlist News Queue",
        "Stock Insight Queue",
        "Portfolio Review Queue",
        "News / Filings / Transcripts",
        "Watchlist Alerts",
        "Earnings / Events",
        "Client Review",
        "Queue Export",
        "Mark Reviewed",
    ):
        assert label in js
    assert "writeCommercialMemory(`event-queue-${scope}`" in js
    assert "data-commercial-event-filter" in js
    assert "data-commercial-event-target" in js
    assert "data-commercial-event-export" in js
    assert "data-commercial-event-reviewed" in js
    assert "event.target.closest('.commercial-event-filter-button[data-commercial-event-filter]')" in js
    assert "renderWorkbenchEventQueue(document.getElementById('commercial-workbench-event-queue')" in js
    assert "renderStockEventQueue(document.getElementById('commercial-stock-event-queue')" in js
    assert "renderPortfolioEventQueue(document.getElementById('commercial-portfolio-event-queue')" in js


def test_event_queues_keep_mobile_filters_and_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-event-queue" in mobile_css
    assert ".commercial-event-filter-button" in mobile_css
    assert ".commercial-event-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Research/Event Queue\"" in js
    assert "role=\"status\"" in js
    assert "commercialEventQueueCsv(config, filter)" in js


def test_commercial_pages_add_competitor_grade_workspace_template_studios():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-template-studio",
        "stock-detail.html": "commercial-stock-template-studio",
        "portfolio-dashboard.html": "commercial-portfolio-template-studio",
    }
    for filename, template_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{template_id}"') == 1
        for other_id in set(html_by_page.values()) - {template_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-template-studio",
        ".commercial-template-copy",
        ".commercial-template-grid",
        ".commercial-template-card",
        ".commercial-template-card.is-active",
        ".commercial-template-metrics",
        ".commercial-template-actions",
        ".commercial-template-action",
        ".commercial-template-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialTemplatePreference(scope, fallbackTemplate)",
        "function renderCommercialTemplateStudio(root, config, activeTemplate)",
        "function bindCommercialTemplateStudio(root, scope, configFactory)",
        "function commercialTemplateStudioCsv(config, activeTemplate)",
        "function workbenchTemplateStudioConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockTemplateStudioConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioTemplateStudioConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchTemplateStudio(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockTemplateStudio(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioTemplateStudio(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Workspace Template Studio",
        "Dashboard Templates",
        "Research Desk Template",
        "Insight Panel Template",
        "Portfolio Review Template",
        "Reusable Views",
        "Apply Template",
        "Save Template",
        "Export Template",
        "Open Workflow",
    ):
        assert label in js
    assert "writeCommercialMemory(`template-studio-${scope}`" in js
    assert "data-commercial-template-choice" in js
    assert "data-commercial-template-apply" in js
    assert "data-commercial-template-save" in js
    assert "data-commercial-template-export" in js
    assert "data-commercial-template-target" in js
    assert "renderWorkbenchTemplateStudio(document.getElementById('commercial-workbench-template-studio')" in js
    assert "renderStockTemplateStudio(document.getElementById('commercial-stock-template-studio')" in js
    assert "renderPortfolioTemplateStudio(document.getElementById('commercial-portfolio-template-studio')" in js


def test_workspace_template_studios_keep_mobile_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-template-studio" in mobile_css
    assert ".commercial-template-grid" in mobile_css
    assert ".commercial-template-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Workspace Template Studio\"" in js
    assert "role=\"status\"" in js
    assert "commercialTemplateStudioCsv(config, activeTemplate)" in js


def test_workspace_template_studios_apply_real_page_state():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for snippet in (
        "function commercialTemplateStatePayload(template)",
        "data-commercial-template-state",
        "new CustomEvent('commercial-template-apply'",
        "writeCommercialMemory(`template-studio-${scope}`, { ...preference, template: activeTemplate, appliedAt: new Date().toLocaleString('zh-TW'), state: commercialTemplateStatePayload(selectedTemplate) })",
    ):
        assert snippet in js

    for state_snippet in (
        "state: { view: 'event', filter: 'alerts', columns: 'event', screen: 'earnings', quick: 'news' }",
        "state: { tab: 'report', scenario: 'base', coverage: 'notes', range: '1Y' }",
        "state: { lens: 'risk', scenario: 'chip', model: 'balanced', mode: 'trim' }",
    ):
        assert state_snippet in js

    for handler_snippet in (
        "document.getElementById('commercial-workbench-template-studio')?.addEventListener('commercial-template-apply', async event => {",
        "activeView = validCommercialChoice(state.view, ['decision', 'valuation', 'event', 'risk'], activeView);",
        "activeColumnSet = validCommercialChoice(state.columns, Object.keys(WORKBENCH_COLUMN_SETS), activeColumnSet);",
        "activeScreenPreset = validCommercialChoice(state.screen, ['conviction', 'earnings', 'reset'], activeScreenPreset);",
        "document.getElementById('commercial-stock-template-studio')?.addEventListener('commercial-template-apply', event => {",
        "if (state.tab) setStockTab(validCommercialChoice(state.tab, stockTabs, currentTab));",
        "activeCoverage = validCommercialChoice(state.coverage, ['alerts', 'fundamentals', 'filings', 'exposure', 'notes'], activeCoverage);",
        "document.getElementById('commercial-portfolio-template-studio')?.addEventListener('commercial-template-apply', event => {",
        "activeLens = validCommercialChoice(state.lens, ['sector', 'country', 'risk', 'contribution'], activeLens);",
        "activeTargetModel = validCommercialChoice(state.model, Object.keys(PORTFOLIO_TARGET_MODELS), activeTargetModel);",
    ):
        assert handler_snippet in js


def test_commercial_pages_add_position_ledgers_for_lots_and_cost_basis():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-position-ledger", "commercial-workbench-alert-center", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-position-ledger", "commercial-stock-alert-center", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-position-ledger", "commercial-portfolio-alert-center", "commercial-portfolio-journey-palette"),
    }
    for filename, (ledger_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{ledger_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{ledger_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-position-ledger",
        ".commercial-position-copy",
        ".commercial-position-mode-grid",
        ".commercial-position-mode",
        ".commercial-position-mode.is-active",
        ".commercial-position-summary",
        ".commercial-position-lot-list",
        ".commercial-position-lot",
        ".commercial-position-actions",
        ".commercial-position-action",
        ".commercial-position-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialPositionLedgerPreference(scope, fallbackMode)",
        "function commercialPositionLedgerCsv(config, activeMode)",
        "function renderCommercialPositionLedger(root, config, activeMode)",
        "function bindCommercialPositionLedger(root, scope, configFactory)",
        "function commercialPositionMetric(label, value, detail, tone = '')",
        "function commercialPositionLot(ticker, label, shares, cost, value, detail, tone = '')",
        "function workbenchPositionLedgerConfig(rows, activeTicker, activeView)",
        "function stockPositionLedgerConfig(snapshot, currentTab, activeScenario)",
        "function portfolioPositionLedgerConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchPositionLedger(root, rows, activeTicker, activeView)",
        "function renderStockPositionLedger(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioPositionLedger(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Position Ledger",
        "Watchlist Position Ledger",
        "Stock Lots & Cost Basis",
        "Portfolio Lots & Cash Ledger",
        "Day Gain",
        "Total Gain",
        "Average Cost",
        "Shares",
        "Cost Basis",
        "Unrealized P/L",
        "Realized P/L",
        "Cash Balance",
        "Dividends",
        "Transactions",
        "Share Lots",
        "Export Ledger",
        "Save Ledger",
        "Open Lots",
    ):
        assert label in js
    assert "writeCommercialMemory(`position-ledger-${scope}`" in js
    assert "data-commercial-position-mode" in js
    assert "data-commercial-position-save" in js
    assert "data-commercial-position-export" in js
    assert "data-commercial-position-target" in js
    assert "renderWorkbenchPositionLedger(document.getElementById('commercial-workbench-position-ledger')" in js
    assert "renderStockPositionLedger(document.getElementById('commercial-stock-position-ledger')" in js
    assert "renderPortfolioPositionLedger(document.getElementById('commercial-portfolio-position-ledger')" in js


def test_position_ledgers_keep_mobile_lot_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-position-ledger" in mobile_css
    assert ".commercial-position-mode-grid" in mobile_css
    assert ".commercial-position-lot-list" in mobile_css
    assert ".commercial-position-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Position Ledger\"" in js
    assert "role=\"status\"" in js
    assert "commercialPositionLedgerCsv(config, activeMode)" in js


def test_commercial_pages_add_page_specific_import_centers_for_onboarding_and_sync():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-import-center", "commercial-workbench-position-ledger", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-import-center", "commercial-stock-position-ledger", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-import-center", "commercial-portfolio-position-ledger", "commercial-portfolio-journey-palette"),
    }
    for filename, (import_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{import_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{import_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-import-center",
        ".commercial-import-copy",
        ".commercial-import-source-grid",
        ".commercial-import-source",
        ".commercial-import-source.is-active",
        ".commercial-import-mapping",
        ".commercial-import-field",
        ".commercial-import-preview",
        ".commercial-import-row",
        ".commercial-import-actions",
        ".commercial-import-action",
        ".commercial-import-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialImportPreference(scope, fallbackSource)",
        "function commercialImportSource(id, label, status, detail, target, fields)",
        "function commercialImportCsv(config, activeSource)",
        "function renderCommercialImportCenter(root, config, activeSource)",
        "function bindCommercialImportCenter(root, scope, configFactory)",
        "function workbenchImportCenterConfig(rows, activeTicker, activeView)",
        "function stockImportCenterConfig(snapshot, currentTab, activeScenario)",
        "function portfolioImportCenterConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchImportCenter(root, rows, activeTicker, activeView)",
        "function renderStockImportCenter(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioImportCenter(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "匯入與同步中心",
        "追蹤表匯入中心",
        "單股交易匯入",
        "券商同步與匯入中心",
        "券商 CSV",
        "追蹤表 CSV",
        "手動成本批次",
        "股息匯入",
        "現金台帳",
        "欄位映射",
        "預覽列",
        "同步匯入",
        "儲存映射",
        "匯出匯入設定",
    ):
        assert label in js
    for page_specific_need in (
        "把選取股票同步進每日決策追蹤表",
        "不離開股票快照就記錄這檔股票的交易",
        "投組 X-Ray 前先核對帳戶、現金、股息與成本批次",
    ):
        assert page_specific_need in js
    assert "writeCommercialMemory(`import-center-${scope}`" in js
    assert "data-commercial-import-source" in js
    assert "data-commercial-import-sync" in js
    assert "data-commercial-import-save" in js
    assert "data-commercial-import-export" in js
    assert "data-commercial-import-target" in js
    assert "renderWorkbenchImportCenter(document.getElementById('commercial-workbench-import-center')" in js
    assert "renderStockImportCenter(document.getElementById('commercial-stock-import-center')" in js
    assert "renderPortfolioImportCenter(document.getElementById('commercial-portfolio-import-center')" in js


def test_import_centers_keep_mobile_import_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-import-center" in mobile_css
    assert ".commercial-import-source-grid" in mobile_css
    assert ".commercial-import-preview" in mobile_css
    assert ".commercial-import-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    source_grid = css_rule_body(mobile_css, ".commercial-import-source-grid")
    assert source_grid is not None
    assert "display: grid;" in source_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in source_grid
    assert "overflow-x: visible;" in source_grid
    import_actions = css_rule_body(mobile_css, ".commercial-import-actions")
    assert import_actions is not None
    assert "display: grid;" in import_actions
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in import_actions
    assert "overflow-x: visible;" in import_actions
    import_action = css_rule_body(mobile_css, ".commercial-import-action")
    assert import_action is not None
    assert "width: 100%;" in import_action
    assert "min-width: 0;" in import_action
    assert "white-space: normal;" in import_action
    assert "aria-label=\"匯入與同步中心\"" in js
    assert "role=\"status\"" in js
    assert "commercialImportCsv(config, activeSource)" in js


def test_import_centers_parse_validate_and_apply_user_csv_like_competitors():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-import-input",
        ".commercial-import-textarea",
        ".commercial-import-file",
        ".commercial-import-validation",
        ".commercial-import-validation.is-ready",
        ".commercial-import-validation.is-warning",
        ".commercial-import-sample",
    ):
        assert selector in css
    for function_name in (
        "function commercialParseImportCsv(text)",
        "function commercialImportCsvText(config, activeSource)",
        "function commercialImportRowsFromText(config, activeSource, text)",
        "function commercialImportValidation(config, activeSource, text)",
        "function commercialPortfolioCsvFromRows(rows)",
        "function commercialApplyImportPayload(scope, config, activeSource, text, root)",
    ):
        assert function_name in js
    for label in (
        "貼上 CSV",
        "選擇 CSV 檔",
        "載入範例",
        "驗證 CSV",
        "套用匯入",
        "列已解析",
        "缺少欄位",
        "已套用到每日決策追蹤表",
        "已記錄這檔股票的交易",
        "投組 X-Ray CSV 已更新",
        "ticker,quantity,purchase date,cost",
        "Symbol,Quantity,Avg Price,Tag",
        "Date,Shares,Price,Fee,Dividend,Action",
        "Account,Symbol,Quantity,Cost,Purchase Date,Cash,Dividend",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-import-csv",
        "data-commercial-import-file",
        "data-commercial-import-sample",
        "data-commercial-import-validate",
        "data-commercial-import-apply",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`import-applied-${scope}`" in js
    assert "document.getElementById('commercial-portfolio-csv').value = commercialPortfolioCsvFromRows(rows);" in js


def test_import_centers_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    function_pairs = (
        ("commercialApplyImportPayload", "commercialImportCsv"),
        ("commercialImportCsv", "renderCommercialImportCenter"),
        ("renderCommercialImportCenter", "bindCommercialImportCenter"),
        ("bindCommercialImportCenter", "workbenchImportCenterConfig"),
        ("workbenchImportCenterConfig", "stockImportCenterConfig"),
        ("stockImportCenterConfig", "portfolioImportCenterConfig"),
        ("portfolioImportCenterConfig", "renderWorkbenchImportCenter"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "匯入與同步中心",
        "追蹤表匯入中心",
        "單股交易匯入",
        "券商同步與匯入中心",
        "券商 CSV",
        "追蹤表 CSV",
        "手動成本批次",
        "股息匯入",
        "現金台帳",
        "欄位映射",
        "預覽列",
        "貼上 CSV",
        "選擇 CSV 檔",
        "載入範例",
        "驗證 CSV",
        "套用匯入",
        "同步匯入",
        "儲存映射",
        "匯出匯入設定",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Import Center",
        "Watchlist Import Center",
        "Stock Transaction Capture",
        "Broker Sync & Import Center",
        "Broker CSV",
        "Watchlist CSV",
        "Manual Lot",
        "Dividend Import",
        "Cash Ledger",
        "Column Mapping",
        "Preview Rows",
        "Paste CSV",
        "Choose CSV File",
        "Load Sample",
        "Validate CSV",
        "Apply Import",
        "Sync Import",
        "Save Mapping",
        "Export Import",
        "Import applied",
        "Import synced",
        "Mapping saved",
        "Import exported",
    ):
        assert legacy_label not in product_layer


def test_import_csv_editor_keeps_mobile_form_controls_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-import-input" in mobile_css
    assert ".commercial-import-textarea" in mobile_css
    assert ".commercial-import-file" in mobile_css
    assert ".commercial-import-validation" in mobile_css
    assert "min-height: 44px;" in mobile_css


def test_commercial_pages_add_page_specific_performance_attribution():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-performance-attribution", "commercial-workbench-import-center", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-performance-attribution", "commercial-stock-import-center", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-performance-attribution", "commercial-portfolio-import-center", "commercial-portfolio-journey-palette"),
    }
    for filename, (attribution_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{attribution_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{attribution_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-performance-attribution",
        ".commercial-performance-copy",
        ".commercial-performance-view-grid",
        ".commercial-performance-view",
        ".commercial-performance-view.is-active",
        ".commercial-performance-metrics",
        ".commercial-performance-metric",
        ".commercial-performance-contributors",
        ".commercial-performance-contributor",
        ".commercial-performance-bars",
        ".commercial-performance-bar",
        ".commercial-performance-actions",
        ".commercial-performance-action",
        ".commercial-performance-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialPerformancePreference(scope, fallbackView)",
        "function commercialPerformanceMetric(label, value, detail, tone = '')",
        "function commercialPerformanceContributor(label, value, detail, weight, tone = '')",
        "function commercialPerformanceCsv(config, activeView)",
        "function renderCommercialPerformanceAttribution(root, config, activeView)",
        "function bindCommercialPerformanceAttribution(root, scope, configFactory)",
        "function workbenchPerformanceAttributionConfig(rows, activeTicker, activeView)",
        "function stockPerformanceAttributionConfig(snapshot, currentTab, activeScenario)",
        "function portfolioPerformanceAttributionConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchPerformanceAttribution(root, rows, activeTicker, activeView)",
        "function renderStockPerformanceAttribution(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioPerformanceAttribution(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Performance Attribution",
        "Decision Performance Attribution",
        "Single Stock Total Return Attribution",
        "Portfolio Contribution Analysis",
        "Day Gain",
        "Total Gain",
        "Benchmark Spread",
        "Capital Gain",
        "Dividend Return",
        "Currency Impact",
        "Contribution Analysis",
        "Time-Weighted Return",
        "Holdings Detail",
        "Benchmark View",
        "Income View",
        "Export Attribution",
        "Save Attribution",
        "Open Driver",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-performance-view",
        "data-commercial-performance-export",
        "data-commercial-performance-save",
        "data-commercial-performance-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`performance-attribution-${scope}`" in js
    assert "renderWorkbenchPerformanceAttribution(document.getElementById('commercial-workbench-performance-attribution')" in js
    assert "renderStockPerformanceAttribution(document.getElementById('commercial-stock-performance-attribution')" in js
    assert "renderPortfolioPerformanceAttribution(document.getElementById('commercial-portfolio-performance-attribution')" in js


def test_performance_attribution_keeps_mobile_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-performance-attribution" in mobile_css
    assert ".commercial-performance-view-grid" in mobile_css
    assert ".commercial-performance-contributors" in mobile_css
    assert ".commercial-performance-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Performance Attribution\"" in js
    assert "role=\"status\"" in js
    assert "commercialPerformanceCsv(config, activeView)" in js


def test_commercial_pages_add_page_specific_tax_income_centers():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-tax-income", "commercial-workbench-performance-attribution", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-tax-income", "commercial-stock-performance-attribution", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-tax-income", "commercial-portfolio-performance-attribution", "commercial-portfolio-journey-palette"),
    }
    for filename, (tax_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{tax_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{tax_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-tax-income",
        ".commercial-tax-copy",
        ".commercial-tax-view-grid",
        ".commercial-tax-view",
        ".commercial-tax-view.is-active",
        ".commercial-tax-metrics",
        ".commercial-tax-metric",
        ".commercial-tax-events",
        ".commercial-tax-event",
        ".commercial-tax-bars",
        ".commercial-tax-bar",
        ".commercial-tax-actions",
        ".commercial-tax-action",
        ".commercial-tax-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialTaxPreference(scope, fallbackView)",
        "function commercialTaxMetric(label, value, detail, tone = '')",
        "function commercialTaxEvent(label, value, detail, weight, tone = '')",
        "function commercialTaxReportCsv(config, activeView)",
        "function renderCommercialTaxIncomeCenter(root, config, activeView)",
        "function bindCommercialTaxIncomeCenter(root, scope, configFactory)",
        "function workbenchTaxIncomeConfig(rows, activeTicker, activeView)",
        "function stockTaxIncomeConfig(snapshot, currentTab, activeScenario)",
        "function portfolioTaxIncomeConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchTaxIncomeCenter(root, rows, activeTicker, activeView)",
        "function renderStockTaxIncomeCenter(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioTaxIncomeCenter(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Tax & Income Center",
        "Watchlist Dividend & Tax Queue",
        "Stock Tax Lot & Dividend Center",
        "Portfolio Taxable Income Report",
        "Dividend Income",
        "Realized Gains",
        "Unrealized Gains",
        "Withholding Tax",
        "Tax Lots",
        "DRIP",
        "Ex-Date",
        "Pay Date",
        "Taxable Income Report",
        "Capital Gains Report",
        "Future Income Projection",
        "Export Tax Pack",
        "Save Tax View",
        "Open Tax Lots",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-tax-view",
        "data-commercial-tax-export",
        "data-commercial-tax-save",
        "data-commercial-tax-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`tax-income-${scope}`" in js
    assert "renderWorkbenchTaxIncomeCenter(document.getElementById('commercial-workbench-tax-income')" in js
    assert "renderStockTaxIncomeCenter(document.getElementById('commercial-stock-tax-income')" in js
    assert "renderPortfolioTaxIncomeCenter(document.getElementById('commercial-portfolio-tax-income')" in js


def test_tax_income_centers_keep_mobile_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-tax-income" in mobile_css
    assert ".commercial-tax-view-grid" in mobile_css
    assert ".commercial-tax-events" in mobile_css
    assert ".commercial-tax-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Tax & Income Center\"" in js
    assert "role=\"status\"" in js
    assert "commercialTaxReportCsv(config, activeView)" in js


def test_commercial_pages_add_page_specific_performance_timelines():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-performance-timeline", "commercial-workbench-tax-income", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-performance-timeline", "commercial-stock-tax-income", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-performance-timeline", "commercial-portfolio-tax-income", "commercial-portfolio-journey-palette"),
    }
    for filename, (timeline_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{timeline_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{timeline_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-performance-timeline",
        ".commercial-timeline-copy",
        ".commercial-timeline-view-grid",
        ".commercial-timeline-view",
        ".commercial-timeline-view.is-active",
        ".commercial-timeline-metrics",
        ".commercial-timeline-metric",
        ".commercial-timeline-chart",
        ".commercial-timeline-track",
        ".commercial-timeline-point",
        ".commercial-timeline-benchmark",
        ".commercial-timeline-events",
        ".commercial-timeline-event",
        ".commercial-timeline-actions",
        ".commercial-timeline-action",
        ".commercial-timeline-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialTimelinePreference(scope, fallbackView)",
        "function commercialTimelinePoint(label, value, benchmark, detail, tone = '')",
        "function commercialTimelineEvent(label, value, detail, position, tone = '')",
        "function commercialTimelineCsv(config, activeView)",
        "function renderCommercialPerformanceTimeline(root, config, activeView)",
        "function bindCommercialPerformanceTimeline(root, scope, configFactory)",
        "function workbenchPerformanceTimelineConfig(rows, activeTicker, activeView)",
        "function stockPerformanceTimelineConfig(snapshot, currentTab, activeScenario)",
        "function portfolioPerformanceTimelineConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchPerformanceTimeline(root, rows, activeTicker, activeView)",
        "function renderStockPerformanceTimeline(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioPerformanceTimeline(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Performance Timeline",
        "Decision Value Timeline",
        "Single Stock Return Timeline",
        "Portfolio Value Over Time",
        "Value Over Time",
        "Cumulative Return",
        "Benchmark Delta",
        "Max Drawdown",
        "Total Return",
        "Price Return",
        "Dividend Adjusted",
        "Time-Weighted Return",
        "Cash Flow",
        "Decision Entry",
        "Report Rerun",
        "Alert Trigger",
        "Benchmark Reset",
        "Earnings Gap",
        "Dividend Pay Date",
        "Analyst Revision",
        "Risk Reset",
        "Deposit",
        "Dividend",
        "Rebalance",
        "Benchmark Drift",
        "Save Timeline",
        "Export Timeline",
        "Open Event",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-timeline-view",
        "data-commercial-timeline-export",
        "data-commercial-timeline-save",
        "data-commercial-timeline-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`performance-timeline-${scope}`" in js
    assert "renderWorkbenchPerformanceTimeline(document.getElementById('commercial-workbench-performance-timeline')" in js
    assert "renderStockPerformanceTimeline(document.getElementById('commercial-stock-performance-timeline')" in js
    assert "renderPortfolioPerformanceTimeline(document.getElementById('commercial-portfolio-performance-timeline')" in js


def test_performance_timelines_keep_mobile_chart_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-performance-timeline" in mobile_css
    assert ".commercial-timeline-view-grid" in mobile_css
    assert ".commercial-timeline-chart" in mobile_css
    assert ".commercial-timeline-event" in mobile_css
    assert ".commercial-timeline-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Performance Timeline\"" in js
    assert "role=\"status\"" in js
    assert "commercialTimelineCsv(config, activeView)" in js


def test_commercial_pages_add_page_specific_risk_stress_labs():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-risk-lab", "commercial-workbench-performance-timeline", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-risk-lab", "commercial-stock-performance-timeline", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-risk-lab", "commercial-portfolio-performance-timeline", "commercial-portfolio-journey-palette"),
    }
    for filename, (risk_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{risk_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{risk_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-risk-lab",
        ".commercial-risk-copy",
        ".commercial-risk-scenario-grid",
        ".commercial-risk-scenario",
        ".commercial-risk-scenario.is-active",
        ".commercial-risk-metrics",
        ".commercial-risk-metric",
        ".commercial-risk-stress-list",
        ".commercial-risk-stress",
        ".commercial-risk-correlation-grid",
        ".commercial-risk-correlation",
        ".commercial-risk-actions",
        ".commercial-risk-action",
        ".commercial-risk-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialRiskPreference(scope, fallbackScenario)",
        "function commercialRiskMetric(label, value, detail, tone = '')",
        "function commercialRiskScenario(label, value, detail, weight, tone = '')",
        "function commercialRiskCorrelation(label, value, detail, tone = '')",
        "function commercialRiskCsv(config, activeScenario)",
        "function renderCommercialRiskLab(root, config, activeScenario)",
        "function bindCommercialRiskLab(root, scope, configFactory)",
        "function workbenchRiskLabConfig(rows, activeTicker, activeView)",
        "function stockRiskLabConfig(snapshot, currentTab, activeScenario)",
        "function portfolioRiskLabConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchRiskLab(root, rows, activeTicker, activeView)",
        "function renderStockRiskLab(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioRiskLab(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Risk & Stress Lab",
        "Watchlist Risk Radar",
        "Single Stock Risk Lab",
        "Portfolio Risk & Correlation Lab",
        "Sharpe Ratio",
        "Sortino Ratio",
        "Beta Trend",
        "Portfolio Beta",
        "R-Squared",
        "Volatility",
        "Maximum Drawdown",
        "S&P 500 Correlation",
        "Risk-Adjusted Return",
        "Stress Test",
        "Drawdown Chart",
        "Correlation Heatmap",
        "Concentration Risk",
        "Rate Shock",
        "Earnings Shock",
        "Benchmark Selloff",
        "Sector Selloff",
        "Rebalance Guardrail",
        "Open Risk Report",
        "Save Risk View",
        "Export Risk Pack",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-risk-scenario",
        "data-commercial-risk-export",
        "data-commercial-risk-save",
        "data-commercial-risk-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`risk-lab-${scope}`" in js
    assert "renderWorkbenchRiskLab(document.getElementById('commercial-workbench-risk-lab')" in js
    assert "renderStockRiskLab(document.getElementById('commercial-stock-risk-lab')" in js
    assert "renderPortfolioRiskLab(document.getElementById('commercial-portfolio-risk-lab')" in js


def test_risk_stress_labs_keep_mobile_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-risk-lab" in mobile_css
    assert ".commercial-risk-scenario-grid" in mobile_css
    assert ".commercial-risk-stress-list" in mobile_css
    assert ".commercial-risk-correlation-grid" in mobile_css
    assert ".commercial-risk-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Risk & Stress Lab\"" in js
    assert "role=\"status\"" in js
    assert "commercialRiskCsv(config, activeScenario)" in js


def test_commercial_pages_add_page_specific_report_share_studios():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-report-studio", "commercial-workbench-risk-lab", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-report-studio", "commercial-stock-risk-lab", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-report-studio", "commercial-portfolio-risk-lab", "commercial-portfolio-journey-palette"),
    }
    for filename, (report_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{report_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{report_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-report-studio",
        ".commercial-report-copy",
        ".commercial-report-template-grid",
        ".commercial-report-template",
        ".commercial-report-template.is-active",
        ".commercial-report-metrics",
        ".commercial-report-metric",
        ".commercial-report-section-list",
        ".commercial-report-section",
        ".commercial-report-recipient-grid",
        ".commercial-report-recipient",
        ".commercial-report-actions",
        ".commercial-report-action",
        ".commercial-report-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialReportPreference(scope, fallbackTemplate)",
        "function commercialReportMetric(label, value, detail, tone = '')",
        "function commercialReportSection(label, value, detail, weight, tone = '')",
        "function commercialReportRecipient(label, detail, status, tone = '')",
        "function commercialReportCsv(config, activeTemplate)",
        "function commercialReportShareText(config, activeTemplate)",
        "function renderCommercialReportStudio(root, config, activeTemplate)",
        "function bindCommercialReportStudio(root, scope, configFactory)",
        "function workbenchReportStudioConfig(rows, activeTicker, activeView)",
        "function stockReportStudioConfig(snapshot, currentTab, activeScenario)",
        "function portfolioReportStudioConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchReportStudio(root, rows, activeTicker, activeView)",
        "function renderStockReportStudio(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioReportStudio(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "報告與分享工作台",
        "追蹤表決策摘要包",
        "單股投資論點包",
        "投組 X-Ray 客戶報告包",
        "客戶報告",
        "顧問分享連結",
        "會計師匯出",
        "PDF 報告",
        "Excel 匯出",
        "Google 試算表",
        "Email 排程",
        "合規註記",
        "決策摘要",
        "投資論點",
        "風險附錄",
        "稅務附錄",
        "持股附錄",
        "績效附錄",
        "複製分享連結",
        "儲存報告模板",
        "匯出報告包",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-report-template",
        "data-commercial-report-copy",
        "data-commercial-report-export",
        "data-commercial-report-save",
        "data-commercial-report-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`report-studio-${scope}`" in js
    assert "renderWorkbenchReportStudio(document.getElementById('commercial-workbench-report-studio')" in js
    assert "renderStockReportStudio(document.getElementById('commercial-stock-report-studio')" in js
    assert "renderPortfolioReportStudio(document.getElementById('commercial-portfolio-report-studio')" in js


def test_report_share_studios_keep_mobile_delivery_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-report-studio" in mobile_css
    assert ".commercial-report-template-grid" in mobile_css
    assert ".commercial-report-section-list" in mobile_css
    assert ".commercial-report-recipient-grid" in mobile_css
    assert ".commercial-report-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    template_grid = css_rule_body(mobile_css, ".commercial-report-template-grid")
    assert template_grid is not None
    assert "display: grid;" in template_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in template_grid
    assert "overflow-x: visible;" in template_grid
    section_list = css_rule_body(mobile_css, ".commercial-report-section-list")
    assert section_list is not None
    assert "display: grid;" in section_list
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in section_list
    assert "overflow-x: visible;" in section_list
    recipient_grid = css_rule_body(mobile_css, ".commercial-report-recipient-grid")
    assert recipient_grid is not None
    assert "display: grid;" in recipient_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in recipient_grid
    assert "overflow-x: visible;" in recipient_grid
    report_actions = css_rule_body(mobile_css, ".commercial-report-actions")
    assert report_actions is not None
    assert "display: grid;" in report_actions
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in report_actions
    assert "overflow-x: visible;" in report_actions
    assert "aria-label=\"報告與分享工作台\"" in js
    assert "role=\"status\"" in js
    assert "commercialReportCsv(config, activeTemplate)" in js
    assert "copyCommercialText(commercialReportShareText(config, activeTemplate)" in js


def test_report_share_studios_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    function_pairs = (
        ("commercialReportCsv", "commercialReportShareText"),
        ("commercialReportShareText", "renderCommercialReportStudio"),
        ("renderCommercialReportStudio", "bindCommercialReportStudio"),
        ("bindCommercialReportStudio", "workbenchReportStudioConfig"),
        ("workbenchReportStudioConfig", "stockReportStudioConfig"),
        ("stockReportStudioConfig", "portfolioReportStudioConfig"),
        ("portfolioReportStudioConfig", "renderWorkbenchReportStudio"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "報告與分享工作台",
        "追蹤表決策摘要包",
        "單股投資論點包",
        "投組 X-Ray 客戶報告包",
        "客戶報告",
        "顧問分享連結",
        "會計師匯出",
        "PDF 報告",
        "Excel 匯出",
        "Google 試算表",
        "Email 排程",
        "合規註記",
        "決策摘要",
        "投資論點",
        "風險附錄",
        "稅務附錄",
        "持股附錄",
        "績效附錄",
        "打開報告包",
        "複製分享連結",
        "儲存報告模板",
        "匯出報告包",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Report & Share Studio",
        "Decision Brief Pack",
        "Single Stock Research Pack",
        "Portfolio Client Pack",
        "Client-Ready Report",
        "Advisor Share Link",
        "Accountant Export",
        "PDF Report",
        "Excel Export",
        "Google Sheets",
        "Email Schedule",
        "Compliance Notes",
        "Executive Summary",
        "Risk Appendix",
        "Tax Appendix",
        "Holdings Appendix",
        "Performance Appendix",
        "Open Report Pack",
        "Copy Share Link",
        "Save Report Template",
        "Export Report Pack",
        "Share link copied",
        "Report template saved",
        "Report pack exported",
    ):
        assert legacy_label not in product_layer


def test_commercial_pages_add_page_specific_ai_research_copilots():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-copilot", "commercial-workbench-report-studio", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-copilot", "commercial-stock-report-studio", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-copilot", "commercial-portfolio-report-studio", "commercial-portfolio-journey-palette"),
    }
    for filename, (copilot_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{copilot_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{copilot_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-copilot-panel",
        ".commercial-copilot-copy",
        ".commercial-copilot-prompt-grid",
        ".commercial-copilot-prompt",
        ".commercial-copilot-prompt.is-active",
        ".commercial-copilot-answer",
        ".commercial-copilot-source-grid",
        ".commercial-copilot-source",
        ".commercial-copilot-actions",
        ".commercial-copilot-action",
        ".commercial-copilot-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialCopilotPreference(scope, fallbackPrompt)",
        "function commercialCopilotPrompt(id, label, detail, target, tone = '')",
        "function commercialCopilotSource(label, value, detail, target, tone = '')",
        "function commercialCopilotQuestionText(config, activePrompt)",
        "function commercialCopilotAnswer(config, activePrompt)",
        "function commercialCopilotShareText(config, activePrompt)",
        "function renderCommercialCopilotPanel(root, config, activePrompt)",
        "function bindCommercialCopilotPanel(root, scope, configFactory)",
        "function workbenchCopilotConfig(rows, activeTicker, activeView)",
        "function stockCopilotConfig(snapshot, currentTab, activeScenario)",
        "function portfolioCopilotConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchCopilot(root, rows, activeTicker, activeView)",
        "function renderStockCopilot(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioCopilot(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "AI 研究助理",
        "為什麼重要",
        "追蹤表決策助理",
        "單股公告助理",
        "投組配置助理",
        "來源稽核軌跡",
        "KPI / 分部檢查",
        "公告與法說逐字稿",
        "追蹤表決策",
        "再平衡問題",
        "稅務影響問題",
        "複製助理摘要",
        "儲存助理提問",
        "打開來源證據",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-copilot-prompt",
        "data-commercial-copilot-copy",
        "data-commercial-copilot-save",
        "data-commercial-copilot-source",
        "data-commercial-copilot-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`copilot-${scope}`" in js
    assert "renderWorkbenchCopilot(document.getElementById('commercial-workbench-copilot')" in js
    assert "renderStockCopilot(document.getElementById('commercial-stock-copilot')" in js
    assert "renderPortfolioCopilot(document.getElementById('commercial-portfolio-copilot')" in js


def test_ai_research_copilots_keep_mobile_prompts_and_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-copilot-panel" in mobile_css
    assert ".commercial-copilot-prompt-grid" in mobile_css
    assert ".commercial-copilot-source-grid" in mobile_css
    assert ".commercial-copilot-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    prompt_grid = css_rule_body(mobile_css, ".commercial-copilot-prompt-grid")
    assert prompt_grid is not None
    assert "display: grid;" in prompt_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in prompt_grid
    assert "overflow-x: visible;" in prompt_grid
    source_grid = css_rule_body(mobile_css, ".commercial-copilot-source-grid")
    assert source_grid is not None
    assert "display: grid;" in source_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in source_grid
    assert "overflow-x: visible;" in source_grid
    copilot_actions = css_rule_body(mobile_css, ".commercial-copilot-actions")
    assert copilot_actions is not None
    assert "display: grid;" in copilot_actions
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in copilot_actions
    assert "overflow-x: visible;" in copilot_actions
    assert "aria-label=\"AI 研究助理\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialCopilotShareText(config, activePrompt)" in js
    assert "commercialCopilotAnswer(config, selected.id || fallbackPrompt)" in js


def test_ai_research_copilots_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    function_pairs = (
        ("commercialCopilotQuestionText", "commercialCopilotAnswer"),
        ("commercialCopilotAnswer", "commercialCopilotShareText"),
        ("commercialCopilotShareText", "renderCommercialCopilotPanel"),
        ("renderCommercialCopilotPanel", "bindCommercialCopilotPanel"),
        ("bindCommercialCopilotPanel", "workbenchCopilotConfig"),
        ("workbenchCopilotConfig", "stockCopilotConfig"),
        ("stockCopilotConfig", "portfolioCopilotConfig"),
        ("portfolioCopilotConfig", "renderWorkbenchCopilot"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "AI 研究助理",
        "為什麼重要",
        "追蹤表決策助理",
        "單股公告助理",
        "投組配置助理",
        "來源稽核軌跡",
        "KPI / 分部檢查",
        "公告與法說逐字稿",
        "追蹤表決策",
        "再平衡問題",
        "稅務影響問題",
        "投組 X-Ray",
        "分析師共識",
        "打開來源證據",
        "複製助理摘要",
        "儲存助理提問",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "AI Research Copilot",
        "Ask Why This Matters",
        "Decision Copilot",
        "Stock Filing Copilot",
        "Portfolio Allocation Copilot",
        "Source Audit Trail",
        "KPI / Segment Check",
        "Filings & Transcripts",
        "Watchlist Decision",
        "Rebalance Question",
        "Tax Impact Question",
        "Open Source Evidence",
        "Copy Copilot Brief",
        "Save Copilot Prompt",
        "Copilot brief copied",
        "Copilot prompt saved",
        "Question:",
        "Answer:",
        "Link:",
    ):
        assert legacy_label not in product_layer


def test_commercial_pages_add_general_user_personal_strategy_centers():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-personalization", "commercial-workbench-copilot", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-personalization", "commercial-stock-copilot", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-personalization", "commercial-portfolio-copilot", "commercial-portfolio-journey-palette"),
    }
    for filename, (strategy_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{strategy_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{strategy_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-personalization-panel",
        ".commercial-personalization-copy",
        ".commercial-personalization-profile-grid",
        ".commercial-personalization-profile",
        ".commercial-personalization-profile.is-active",
        ".commercial-personalization-summary",
        ".commercial-personalization-rule-grid",
        ".commercial-personalization-rule",
        ".commercial-personalization-actions",
        ".commercial-personalization-action",
        ".commercial-personalization-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialPersonalizationPreference(scope, fallbackProfile)",
        "function commercialPersonalizationProfile(id, label, detail, target, tone = '')",
        "function commercialPersonalizationRule(label, value, detail, target, tone = '')",
        "function commercialPersonalizationAction(label, detail, target, tone = '')",
        "function commercialPersonalizationSummary(config, activeProfile)",
        "function commercialPersonalizationShareText(config, activeProfile)",
        "function renderCommercialPersonalizationPanel(root, config, activeProfile)",
        "function bindCommercialPersonalizationPanel(root, scope, configFactory)",
        "function workbenchPersonalizationConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockPersonalizationConfig(snapshot, currentTab, activeScenario)",
        "function portfolioPersonalizationConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchPersonalization(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockPersonalization(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioPersonalization(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Personal Strategy Center",
        "Quick Setup",
        "Strategy Profile",
        "Watchlist Strategy",
        "Stock Suitability",
        "Portfolio Goal Plan",
        "Long-term Core",
        "High-conviction",
        "Income Focus",
        "Risk Comfort",
        "Time Horizon",
        "Alert Cadence",
        "Tax Locale",
        "Notification Plan",
        "Save Strategy",
        "Apply Strategy",
        "Copy Setup",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-personalization-profile",
        "data-commercial-personalization-copy",
        "data-commercial-personalization-save",
        "data-commercial-personalization-apply",
        "data-commercial-personalization-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`personalization-${scope}`" in js
    assert "renderWorkbenchPersonalization(document.getElementById('commercial-workbench-personalization')" in js
    assert "renderStockPersonalization(document.getElementById('commercial-stock-personalization')" in js
    assert "renderPortfolioPersonalization(document.getElementById('commercial-portfolio-personalization')" in js


def test_personal_strategy_centers_keep_mobile_setup_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-personalization-panel" in mobile_css
    assert ".commercial-personalization-profile-grid" in mobile_css
    assert ".commercial-personalization-rule-grid" in mobile_css
    assert ".commercial-personalization-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Personal Strategy Center\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialPersonalizationShareText(config, activeProfile)" in js
    assert "commercialPersonalizationSummary(config, selected.id || fallbackProfile)" in js


def test_commercial_pages_add_page_specific_action_docks_for_no_hunting_workflows():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-action-dock", "commercial-global-context", "commercial-workbench-control-strip"),
        "stock-detail.html": ("commercial-stock-action-dock", "commercial-global-context", "commercial-stock-control-strip"),
        "portfolio-dashboard.html": ("commercial-portfolio-action-dock", "commercial-global-context", "commercial-portfolio-control-strip"),
    }
    for filename, (dock_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{dock_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{dock_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-action-dock",
        ".commercial-action-dock-copy",
        ".commercial-action-dock-command-grid",
        ".commercial-action-dock-command",
        ".commercial-action-dock-command.is-active",
        ".commercial-action-dock-badge-grid",
        ".commercial-action-dock-badge",
        ".commercial-action-dock-actions",
        ".commercial-action-dock-action",
        ".commercial-action-dock-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialActionDockPreference(scope, fallbackAction)",
        "function commercialActionDockCommand(id, label, detail, target, tone = '')",
        "function commercialActionDockBadge(label, value, detail, tone = '')",
        "function commercialActionDockPrimaryLabel(config, selected)",
        "function commercialActionDockShareText(config, activeAction)",
        "function renderCommercialActionDock(root, config, activeAction)",
        "function bindCommercialActionDock(root, scope, configFactory)",
        "function workbenchActionDockConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockActionDockConfig(snapshot, currentTab, activeScenario)",
        "function portfolioActionDockConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchActionDock(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockActionDock(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioActionDock(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Action Dock",
        "Today Decision Dock",
        "Stock Research Dock",
        "Portfolio Review Dock",
        "Open Snapshot",
        "Review Alerts",
        "Review Filings",
        "Set Price Alert",
        "Open X-Ray",
        "Review Drift",
        "Rebalance Plan",
        "Client Pack",
        "Alert Badge",
        "Report Status",
        "Source Freshness",
        "Next Step",
        "Save Dock",
        "Copy Deep Link",
        "Open Client Pack",
    ):
        assert label in js
    assert "commercialActionDockPrimaryLabel(config, selected)" in js
    assert ">${escapeHtml(commercialActionDockPrimaryLabel(config, selected))}</button>" in js
    assert "Open Primary Action" not in js
    for data_attr in (
        "data-commercial-action-dock-command",
        "data-commercial-action-dock-copy",
        "data-commercial-action-dock-save",
        "data-commercial-action-dock-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`action-dock-${scope}`" in js
    assert "renderWorkbenchActionDock(document.getElementById('commercial-workbench-action-dock')" in js
    assert "renderStockActionDock(document.getElementById('commercial-stock-action-dock')" in js
    assert "renderPortfolioActionDock(document.getElementById('commercial-portfolio-action-dock')" in js


def test_action_docks_keep_mobile_primary_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-action-dock" in mobile_css
    assert ".commercial-action-dock-command-grid" in mobile_css
    assert ".commercial-action-dock-badge-grid" in mobile_css
    assert ".commercial-action-dock-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    command_grid = css_rule_body(mobile_css, ".commercial-action-dock-command-grid")
    assert command_grid is not None
    assert "display: grid;" in command_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in command_grid
    assert "overflow-x: visible;" in command_grid
    assert "padding-bottom: 0;" in command_grid

    badge_grid = css_rule_body(mobile_css, ".commercial-action-dock-badge-grid")
    assert badge_grid is not None
    assert "display: grid;" in badge_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in badge_grid
    assert "overflow-x: visible;" in badge_grid

    command_tile = css_rule_body(mobile_css, ".commercial-action-dock-command")
    assert command_tile is not None
    assert "width: 100%;" in command_tile
    assert "min-width: 0;" in command_tile

    action_grid = css_rule_body(mobile_css, ".commercial-action-dock-actions")
    assert action_grid is not None
    assert "display: grid;" in action_grid
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in action_grid
    assert "overflow-x: visible;" in action_grid
    assert "padding-bottom: 0;" in action_grid

    action_button = css_rule_body(mobile_css, ".commercial-action-dock-action")
    assert action_button is not None
    assert "width: 100%;" in action_button
    assert "min-width: 0;" in action_button
    assert "white-space: normal;" in action_button

    assert "aria-label=\"Action Dock\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialActionDockShareText(config, activeAction)" in js
    assert "commercialActionDockPreference(config?.scope || 'workbench', fallbackAction)" in js


def test_commercial_pages_add_page_specific_today_inboxes_for_competitor_alert_workflows():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-today-inbox", "commercial-workbench-sync-strip", "commercial-workbench-market-brief"),
        "stock-detail.html": ("commercial-stock-today-inbox", "commercial-stock-sync-strip", "commercial-stock-market-brief"),
        "portfolio-dashboard.html": ("commercial-portfolio-today-inbox", "commercial-portfolio-sync-strip", "commercial-portfolio-market-brief"),
    }
    for filename, (inbox_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{inbox_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{inbox_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-today-inbox",
        ".commercial-today-inbox-copy",
        ".commercial-today-inbox-list",
        ".commercial-today-inbox-item",
        ".commercial-today-inbox-item.is-active",
        ".commercial-today-inbox-summary",
        ".commercial-today-inbox-metrics",
        ".commercial-today-inbox-metric",
        ".commercial-today-inbox-actions",
        ".commercial-today-inbox-action",
        ".commercial-today-inbox-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialTodayInboxPreference(scope, fallbackItem)",
        "function commercialTodayInboxItem(id, label, detail, target, time, tone = '')",
        "function commercialTodayInboxMetric(label, value, detail, tone = '')",
        "function commercialTodayInboxDigest(config, activeItem)",
        "function renderCommercialTodayInbox(root, config, activeItem)",
        "function bindCommercialTodayInbox(root, scope, configFactory)",
        "function workbenchTodayInboxConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockTodayInboxConfig(snapshot, currentTab, activeScenario)",
        "function portfolioTodayInboxConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchTodayInbox(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockTodayInbox(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioTodayInbox(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Today Inbox",
        "Watchlist Today Inbox",
        "Stock Signal Inbox",
        "Portfolio Review Inbox",
        "Open Alert",
        "Copy Digest",
        "Mark Reviewed",
        "Unread",
        "SLA",
        "Owner",
        "Price Alert",
        "Report Rerun",
        "Filing Check",
        "Rating Move",
        "Earnings Watch",
        "Drift Review",
        "Tax Check",
        "Client Review",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-today-inbox-item",
        "data-commercial-today-inbox-copy",
        "data-commercial-today-inbox-review",
        "data-commercial-today-inbox-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`today-inbox-${scope}`" in js
    assert "renderWorkbenchTodayInbox(document.getElementById('commercial-workbench-today-inbox')" in js
    assert "renderStockTodayInbox(document.getElementById('commercial-stock-today-inbox')" in js
    assert "renderPortfolioTodayInbox(document.getElementById('commercial-portfolio-today-inbox')" in js


def test_today_inboxes_keep_mobile_alert_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-today-inbox" in mobile_css
    assert ".commercial-today-inbox-list" in mobile_css
    assert ".commercial-today-inbox-item" in mobile_css
    assert ".commercial-today-inbox-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Today Inbox\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialTodayInboxDigest(config, activeItem)" in js
    assert "commercialTodayInboxPreference(config?.scope || 'workbench', fallbackItem)" in js


def test_today_inbox_primary_action_uses_selected_page_workflow_label():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const actionLabel = selected.kicker || config?.actionLabel || 'Open Item';" in js
    assert 'data-commercial-today-inbox-action-label="${escapeHtml(actionLabel)}"' in js
    assert 'aria-label="${escapeHtml(`${actionLabel}: ${selected.label || config?.title || \'Today Inbox\'}`)}"' in js
    assert ">${escapeHtml(actionLabel)}</button>" in js
    assert (
        "const actionLabel = event.target.closest('[data-commercial-today-inbox-target]')?.dataset.commercialTodayInboxActionLabel || 'Item';"
        in js
    )
    assert "showCommercialFeedback(root, `${actionLabel} opened`);" in js
    assert (
        'data-commercial-today-inbox-target="${escapeHtml(selected.target || config?.target || \'\')}">Open Alert</button>'
        not in js
    )
    handler = re.search(
        r"if \(target\) \{(?P<body>.*?)\n            \}",
        js[js.index("function bindCommercialTodayInbox"):],
        re.S,
    )
    assert handler is not None
    handler_body = handler.group("body")
    assert handler_body.index("scrollCommercialTaskTarget(target);") < handler_body.index(
        "showCommercialFeedback(root, `${actionLabel} opened`);"
    )
    for workflow_label in (
        "Report Queue",
        "Source Queue",
        "Event Watch",
        "Price Check",
        "Tax Queue",
        "Plan Queue",
        "Share Queue",
    ):
        assert workflow_label in js


def test_commercial_pages_add_guided_setup_launchpads_for_general_user_onboarding():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-setup-launchpad", "commercial-workbench-factor-lens", "commercial-workbench-workflow-lens"),
        "stock-detail.html": ("commercial-stock-setup-launchpad", "commercial-stock-factor-lens", "commercial-stock-workflow-lens"),
        "portfolio-dashboard.html": ("commercial-portfolio-setup-launchpad", "commercial-portfolio-factor-lens", "commercial-portfolio-workflow-lens"),
    }
    for filename, (launchpad_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{launchpad_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{launchpad_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-setup-launchpad",
        ".commercial-setup-copy",
        ".commercial-setup-step-grid",
        ".commercial-setup-step",
        ".commercial-setup-step.is-active",
        ".commercial-setup-step.is-complete",
        ".commercial-setup-progress",
        ".commercial-setup-meter",
        ".commercial-setup-metrics",
        ".commercial-setup-metric",
        ".commercial-setup-actions",
        ".commercial-setup-action",
        ".commercial-setup-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialSetupLaunchpadPreference(scope, fallbackStep)",
        "function commercialSetupStep(id, label, detail, target, completion, tone = '')",
        "function commercialSetupMetric(label, value, detail, tone = '')",
        "function commercialSetupLaunchpadSummary(config, activeStep)",
        "function renderCommercialSetupLaunchpad(root, config, activeStep)",
        "function bindCommercialSetupLaunchpad(root, scope, configFactory)",
        "function workbenchSetupLaunchpadConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockSetupLaunchpadConfig(snapshot, currentTab, activeScenario)",
        "function portfolioSetupLaunchpadConfig(payload, portfolioContextTicker, activeLens, activeTargetModel)",
        "function renderWorkbenchSetupLaunchpad(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockSetupLaunchpad(root, snapshot, currentTab, activeScenario)",
        "function renderPortfolioSetupLaunchpad(root, payload, portfolioContextTicker, activeLens, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "新手導引",
        "追蹤表啟動設定",
        "單股研究啟動設定",
        "投組啟動設定",
        "匯入或建立",
        "設定警示",
        "建立第一份報告",
        "儲存工作區",
        "搜尋股票",
        "檢查快照",
        "設定評級警示",
        "儲存投資論點",
        "匯入持股",
        "選擇模型",
        "檢查 X-Ray",
        "匯出報告",
        "準備度",
        "下一步",
        "已完成",
        "繼續設定",
        "複製設定計畫",
        "儲存設定",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-setup-step",
        "data-commercial-setup-copy",
        "data-commercial-setup-save",
        "data-commercial-setup-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`setup-launchpad-${scope}`" in js
    assert "renderWorkbenchSetupLaunchpad(document.getElementById('commercial-workbench-setup-launchpad')" in js
    assert "renderStockSetupLaunchpad(document.getElementById('commercial-stock-setup-launchpad')" in js
    assert "renderPortfolioSetupLaunchpad(document.getElementById('commercial-portfolio-setup-launchpad')" in js


def test_guided_setup_launchpads_keep_mobile_steps_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-setup-launchpad" in mobile_css
    assert ".commercial-setup-step-grid" in mobile_css
    assert ".commercial-setup-step" in mobile_css
    assert ".commercial-setup-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"新手導引\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialSetupLaunchpadSummary(config, activeStep)" in js
    assert "commercialSetupLaunchpadPreference(config?.scope || 'workbench', fallbackStep)" in js


def test_guided_setup_launchpads_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    function_pairs = (
        ("commercialSetupStep", "commercialSetupMetric"),
        ("commercialSetupLaunchpadSummary", "commercialSetupProgress"),
        ("renderCommercialSetupLaunchpad", "bindCommercialSetupLaunchpad"),
        ("bindCommercialSetupLaunchpad", "workbenchSetupLaunchpadConfig"),
        ("workbenchSetupLaunchpadConfig", "stockSetupLaunchpadConfig"),
        ("stockSetupLaunchpadConfig", "portfolioSetupLaunchpadConfig"),
        ("portfolioSetupLaunchpadConfig", "renderWorkbenchSetupLaunchpad"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "新手導引",
        "追蹤表啟動設定",
        "單股研究啟動設定",
        "投組啟動設定",
        "匯入或建立",
        "設定警示",
        "建立第一份報告",
        "儲存工作區",
        "搜尋股票",
        "檢查快照",
        "設定評級警示",
        "儲存投資論點",
        "匯入持股",
        "選擇模型",
        "檢查 X-Ray",
        "匯出報告",
        "準備度",
        "下一步",
        "已完成",
        "繼續設定",
        "複製設定計畫",
        "儲存設定",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Guided Setup",
        "Watchlist Setup",
        "Stock Research Setup",
        "Portfolio Setup",
        "Import or Create",
        "Set Alerts",
        "Build First Report",
        "Save Workspace",
        "Search Ticker",
        "Review Snapshot",
        "Set Rating Alert",
        "Save Thesis",
        "Import Holdings",
        "Choose Model",
        "Review X-Ray",
        "Export Report",
        "Readiness",
        "Next Step",
        "Completed",
        "Continue Setup",
        "Copy Setup Plan",
        "Save Setup",
        "Setup plan copied",
        "Setup saved",
        "Setup step opened",
    ):
        assert legacy_label not in product_layer


def test_guided_setup_launchpads_use_mobile_grid_instead_of_clipped_carousel():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    setup_steps = css_rule_body(mobile_css, ".commercial-setup-step-grid")
    assert setup_steps is not None
    assert "display: grid;" in setup_steps
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in setup_steps
    assert "overflow-x: visible;" in setup_steps
    assert "padding-bottom: 0;" in setup_steps

    setup_metrics = css_rule_body(mobile_css, ".commercial-setup-metrics")
    assert setup_metrics is not None
    assert "display: grid;" in setup_metrics
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in setup_metrics
    assert "overflow-x: visible;" in setup_metrics

    setup_tile = css_rule_body(mobile_css, ".commercial-setup-step")
    assert setup_tile is not None
    assert "width: 100%;" in setup_tile
    assert "min-width: 0;" in setup_tile

    setup_actions = css_rule_body(mobile_css, ".commercial-setup-actions")
    assert setup_actions is not None
    assert "display: grid;" in setup_actions
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in setup_actions
    assert "overflow-x: visible;" in setup_actions
    assert "padding-bottom: 0;" in setup_actions

    setup_action = css_rule_body(mobile_css, ".commercial-setup-action")
    assert setup_action is not None
    assert "width: 100%;" in setup_action
    assert "min-width: 0;" in setup_action
    assert "white-space: normal;" in setup_action


def test_commercial_pages_add_independent_competitor_grade_workflow_lenses():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-workflow-lens", "commercial-workbench-setup-launchpad", "commercial-workbench-data-coverage"),
        "stock-detail.html": ("commercial-stock-workflow-lens", "commercial-stock-setup-launchpad", "commercial-stock-data-coverage"),
        "portfolio-dashboard.html": ("commercial-portfolio-workflow-lens", "commercial-portfolio-setup-launchpad", "commercial-portfolio-data-coverage"),
    }
    for filename, (lens_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{lens_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{lens_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-workflow-lens",
        ".commercial-workflow-copy",
        ".commercial-workflow-item-grid",
        ".commercial-workflow-item",
        ".commercial-workflow-item.is-active",
        ".commercial-workflow-metrics",
        ".commercial-workflow-metric",
        ".commercial-workflow-actions",
        ".commercial-workflow-action",
        ".commercial-workflow-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialWorkflowLensPreference(scope, fallbackLens)",
        "function commercialWorkflowLensItem(id, label, detail, target, signal, tone = '')",
        "function commercialWorkflowLensMetric(label, value, detail, tone = '')",
        "function commercialWorkflowLensSummary(config, activeLens)",
        "function renderCommercialWorkflowLens(root, config, activeLens)",
        "function bindCommercialWorkflowLens(root, scope, configFactory)",
        "function workbenchWorkflowLensConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockWorkflowLensConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioWorkflowLensConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchWorkflowLens(root, rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function renderStockWorkflowLens(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioWorkflowLens(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Workflow Lens",
        "Watchlist View Lens",
        "Single Stock Signal Lens",
        "Portfolio Report Lens",
        "Decision View",
        "Alert View",
        "Income View",
        "Momentum View",
        "Snapshot Signals",
        "Rating & Target",
        "Peer Comparison",
        "Thesis Evidence",
        "Performance Report",
        "X-Ray Exposure",
        "Tax Income Report",
        "Rebalance Pack",
        "Open Lens",
        "Copy Lens Brief",
        "Save Lens",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-workflow-lens",
        "data-commercial-workflow-copy",
        "data-commercial-workflow-save",
        "data-commercial-workflow-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`workflow-lens-${scope}`" in js
    assert "renderWorkbenchWorkflowLens(document.getElementById('commercial-workbench-workflow-lens')" in js
    assert "renderStockWorkflowLens(document.getElementById('commercial-stock-workflow-lens')" in js
    assert "renderPortfolioWorkflowLens(document.getElementById('commercial-portfolio-workflow-lens')" in js


def test_workflow_lenses_keep_mobile_decision_cards_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-workflow-lens" in mobile_css
    assert ".commercial-workflow-item-grid" in mobile_css
    assert ".commercial-workflow-item" in mobile_css
    assert ".commercial-workflow-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Workflow Lens\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialWorkflowLensSummary(config, activeLens)" in js
    assert "commercialWorkflowLensPreference(config?.scope || 'workbench', fallbackLens)" in js


def test_commercial_pages_add_first_screen_data_coverage_maps():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-data-coverage", "commercial-workbench-workflow-lens", "commercial-workbench-share-brief"),
        "stock-detail.html": ("commercial-stock-data-coverage", "commercial-stock-workflow-lens", "commercial-stock-share-brief"),
        "portfolio-dashboard.html": ("commercial-portfolio-data-coverage", "commercial-portfolio-workflow-lens", "commercial-portfolio-share-brief"),
    }
    for filename, (coverage_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{coverage_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{coverage_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-data-coverage",
        ".commercial-data-coverage-copy",
        ".commercial-data-coverage-grid",
        ".commercial-data-coverage-item",
        ".commercial-data-coverage-item.is-active",
        ".commercial-data-coverage-meter",
        ".commercial-data-coverage-metrics",
        ".commercial-data-coverage-metric",
        ".commercial-data-coverage-actions",
        ".commercial-data-coverage-action",
        ".commercial-data-coverage-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialDataCoveragePreference(scope, fallbackCoverage)",
        "function commercialDataCoverageItem(id, label, detail, target, status, score, tone = '')",
        "function commercialDataCoverageMetric(label, value, detail, tone = '')",
        "function commercialDataCoverageSummary(config, activeCoverage)",
        "function renderCommercialDataCoverage(root, config, activeCoverage)",
        "function bindCommercialDataCoverage(root, scope, configFactory)",
        "function workbenchDataCoverageConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockDataCoverageConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioDataCoverageConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchDataCoverage(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockDataCoverage(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioDataCoverage(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Data Coverage",
        "Watchlist Coverage Map",
        "Stock Coverage Map",
        "Portfolio Coverage Map",
        "Price Feed",
        "Alert Rules",
        "Report Evidence",
        "News Events",
        "Quote Session",
        "Financials",
        "Analyst Ratings",
        "Filings & Events",
        "Holdings Data",
        "X-Ray Factors",
        "Tax Lots",
        "Performance History",
        "Open Data Gap",
        "Copy Coverage Brief",
        "Save Coverage Map",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-data-coverage",
        "data-commercial-data-coverage-copy",
        "data-commercial-data-coverage-save",
        "data-commercial-data-coverage-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`data-coverage-${scope}`" in js
    assert "renderWorkbenchDataCoverage(document.getElementById('commercial-workbench-data-coverage')" in js
    assert "renderStockDataCoverage(document.getElementById('commercial-stock-data-coverage')" in js
    assert "renderPortfolioDataCoverage(document.getElementById('commercial-portfolio-data-coverage')" in js


def test_data_coverage_maps_keep_mobile_gap_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-data-coverage" in mobile_css
    assert ".commercial-data-coverage-grid" in mobile_css
    assert ".commercial-data-coverage-item" in mobile_css
    assert ".commercial-data-coverage-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Data Coverage\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialDataCoverageSummary(config, activeCoverage)" in js
    assert "commercialDataCoveragePreference(config?.scope || 'workbench', fallbackCoverage)" in js


def test_commercial_pages_add_first_screen_share_brief_panels():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-share-brief", "commercial-workbench-data-coverage", "commercial-workbench-competitive-lens"),
        "stock-detail.html": ("commercial-stock-share-brief", "commercial-stock-data-coverage", "commercial-stock-competitive-lens"),
        "portfolio-dashboard.html": ("commercial-portfolio-share-brief", "commercial-portfolio-data-coverage", "commercial-portfolio-competitive-lens"),
    }
    for filename, (brief_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{brief_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{brief_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-share-brief",
        ".commercial-share-brief-copy",
        ".commercial-share-brief-package-grid",
        ".commercial-share-brief-package",
        ".commercial-share-brief-package.is-active",
        ".commercial-share-brief-checklist",
        ".commercial-share-brief-check",
        ".commercial-share-brief-actions",
        ".commercial-share-brief-action",
        ".commercial-share-brief-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialShareBriefPreference(scope, fallbackPackage)",
        "function commercialShareBriefPackage(id, label, detail, target, status, tone = '')",
        "function commercialShareBriefCheck(label, value, detail, tone = '')",
        "function commercialShareBriefSummary(config, activePackage)",
        "function renderCommercialShareBrief(root, config, activePackage)",
        "function bindCommercialShareBrief(root, scope, configFactory)",
        "function workbenchShareBriefConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockShareBriefConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioShareBriefConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchShareBrief(root, rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function renderStockShareBrief(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioShareBrief(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Share Brief",
        "Watchlist Share Brief",
        "Stock Research Brief",
        "Portfolio Client Brief",
        "Watchlist View",
        "Alert Packet",
        "Advisor Snapshot",
        "CSV Export",
        "Research Summary",
        "Rating Packet",
        "Thesis Memo",
        "Source Pack",
        "Client Review",
        "X-Ray Report",
        "Tax Appendix",
        "Rebalance Memo",
        "Open Share Pack",
        "Copy Share Brief",
        "Export Share Pack",
        "Save Share Brief",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-share-brief",
        "data-commercial-share-copy",
        "data-commercial-share-export",
        "data-commercial-share-save",
        "data-commercial-share-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`share-brief-${scope}`" in js
    assert "downloadCommercialText(`onstock-${scope}-share-brief.csv`" in js
    assert "renderWorkbenchShareBrief(document.getElementById('commercial-workbench-share-brief')" in js
    assert "renderStockShareBrief(document.getElementById('commercial-stock-share-brief')" in js
    assert "renderPortfolioShareBrief(document.getElementById('commercial-portfolio-share-brief')" in js


def test_share_brief_panels_keep_mobile_delivery_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-share-brief" in mobile_css
    assert ".commercial-share-brief-package-grid" in mobile_css
    assert ".commercial-share-brief-package" in mobile_css
    assert ".commercial-share-brief-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Share Brief\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialShareBriefSummary(config, activePackage)" in js
    assert "commercialShareBriefPreference(config?.scope || 'workbench', fallbackPackage)" in js


def test_commercial_pages_add_differentiated_competitive_lens_panels():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-competitive-lens", "commercial-workbench-share-brief", "commercial-workbench-decision-automation"),
        "stock-detail.html": ("commercial-stock-competitive-lens", "commercial-stock-share-brief", "commercial-stock-decision-automation"),
        "portfolio-dashboard.html": ("commercial-portfolio-competitive-lens", "commercial-portfolio-share-brief", "commercial-portfolio-decision-automation"),
    }
    for filename, (lens_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{lens_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{lens_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-competitive-lens",
        ".commercial-competitive-copy",
        ".commercial-competitive-stage-grid",
        ".commercial-competitive-stage",
        ".commercial-competitive-stage.is-active",
        ".commercial-competitive-bars",
        ".commercial-competitive-bar",
        ".commercial-competitive-bar-fill",
        ".commercial-competitive-radar",
        ".commercial-competitive-radar-point",
        ".commercial-competitive-return-stack",
        ".commercial-competitive-return-segment",
        ".commercial-competitive-actions",
        ".commercial-competitive-action",
        ".commercial-competitive-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialCompetitiveLensPreference(scope, fallbackLens)",
        "function commercialCompetitiveLensMetric(label, value, detail, score, tone = '')",
        "function commercialCompetitiveLensStage(id, label, detail, target, status, tone = '')",
        "function commercialCompetitiveLensSummary(config, activeLens)",
        "function renderCommercialCompetitiveLens(root, config, activeLens)",
        "function bindCommercialCompetitiveLens(root, scope, configFactory)",
        "function workbenchCompetitiveLensConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockCompetitiveLensConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioCompetitiveLensConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchCompetitiveLens(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockCompetitiveLens(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioCompetitiveLens(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Competitive Lens",
        "Strategy Scoreboard",
        "Fundamental Health Map",
        "Return Components",
        "Strategy Score",
        "Advanced View",
        "Fair Value",
        "Growth",
        "Financial Health",
        "Dividend",
        "Capital Gain",
        "Dividends",
        "FX Impact",
        "Fees",
        "Open Lens",
        "Copy Lens",
        "Export Lens",
        "Save Lens",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-competitive-lens",
        "data-commercial-competitive-copy",
        "data-commercial-competitive-export",
        "data-commercial-competitive-save",
        "data-commercial-competitive-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`competitive-lens-${scope}`" in js
    assert "downloadCommercialText(`onstock-${scope}-competitive-lens.csv`" in js
    assert "renderWorkbenchCompetitiveLens(document.getElementById('commercial-workbench-competitive-lens')" in js
    assert "renderStockCompetitiveLens(document.getElementById('commercial-stock-competitive-lens')" in js
    assert "renderPortfolioCompetitiveLens(document.getElementById('commercial-portfolio-competitive-lens')" in js


def test_competitive_lens_panels_keep_mobile_data_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-competitive-lens" in mobile_css
    assert ".commercial-competitive-stage-grid" in mobile_css
    assert ".commercial-competitive-stage" in mobile_css
    assert ".commercial-competitive-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Competitive Lens\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialCompetitiveLensSummary(config, activeLens)" in js
    assert "commercialCompetitiveLensPreference(config?.scope || 'workbench', fallbackLens)" in js


def test_commercial_pages_add_decision_automation_panels_for_actionable_alerts():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-decision-automation", "commercial-workbench-competitive-lens", "commercial-workbench-data-sync"),
        "stock-detail.html": ("commercial-stock-decision-automation", "commercial-stock-competitive-lens", "commercial-stock-data-sync"),
        "portfolio-dashboard.html": ("commercial-portfolio-decision-automation", "commercial-portfolio-competitive-lens", "commercial-portfolio-data-sync"),
    }
    for filename, (automation_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{automation_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{automation_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-decision-automation",
        ".commercial-decision-automation-copy",
        ".commercial-decision-automation-rule-grid",
        ".commercial-decision-automation-rule",
        ".commercial-decision-automation-rule.is-active",
        ".commercial-decision-automation-trigger-list",
        ".commercial-decision-automation-trigger",
        ".commercial-decision-automation-cadence-strip",
        ".commercial-decision-automation-cadence-pill",
        ".commercial-decision-automation-actions",
        ".commercial-decision-automation-action",
        ".commercial-decision-automation-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialDecisionAutomationPreference(scope, fallbackRule)",
        "function commercialDecisionAutomationRule(id, label, detail, target, status, tone = '')",
        "function commercialDecisionAutomationTrigger(label, value, detail, tone = '')",
        "function commercialDecisionAutomationSummary(config, activeRule)",
        "function renderCommercialDecisionAutomation(root, config, activeRule)",
        "function bindCommercialDecisionAutomation(root, scope, configFactory)",
        "function workbenchDecisionAutomationConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockDecisionAutomationConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioDecisionAutomationConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchDecisionAutomation(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockDecisionAutomation(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioDecisionAutomation(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Decision Automation",
        "Watchlist Alert Automation",
        "Stock Alert Automation",
        "Portfolio Review Automation",
        "Watchlist Alert",
        "Rerun Queue",
        "News Digest",
        "Rating Guard",
        "Price Alert",
        "Rating Alert",
        "Filing Alert",
        "Thesis Review",
        "Drift Alert",
        "Dividend Alert",
        "Tax Pack",
        "Client Review",
        "Arm Automation",
        "Copy Automation",
        "Export Automation",
        "Save Automation",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-decision-automation",
        "data-commercial-decision-automation-copy",
        "data-commercial-decision-automation-export",
        "data-commercial-decision-automation-save",
        "data-commercial-decision-automation-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`decision-automation-${scope}`" in js
    assert "downloadCommercialText(`onstock-${scope}-decision-automation.csv`" in js
    assert "renderWorkbenchDecisionAutomation(document.getElementById('commercial-workbench-decision-automation')" in js
    assert "renderStockDecisionAutomation(document.getElementById('commercial-stock-decision-automation')" in js
    assert "renderPortfolioDecisionAutomation(document.getElementById('commercial-portfolio-decision-automation')" in js


def test_decision_automation_panels_keep_mobile_rule_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-decision-automation" in mobile_css
    assert ".commercial-decision-automation-rule-grid" in mobile_css
    assert ".commercial-decision-automation-rule" in mobile_css
    assert ".commercial-decision-automation-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Decision Automation\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialDecisionAutomationSummary(config, activeRule)" in js
    assert "commercialDecisionAutomationPreference(config?.scope || 'workbench', fallbackRule)" in js


def test_commercial_pages_add_data_sync_launchpads_for_import_trust():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-data-sync", "commercial-workbench-decision-automation", "commercial-workbench-scenario-simulator"),
        "stock-detail.html": ("commercial-stock-data-sync", "commercial-stock-decision-automation", "commercial-stock-scenario-simulator"),
        "portfolio-dashboard.html": ("commercial-portfolio-data-sync", "commercial-portfolio-decision-automation", "commercial-portfolio-scenario-simulator"),
    }
    for filename, (sync_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{sync_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{sync_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-data-sync",
        ".commercial-data-sync-copy",
        ".commercial-data-sync-source-grid",
        ".commercial-data-sync-source",
        ".commercial-data-sync-source.is-active",
        ".commercial-data-sync-trust-list",
        ".commercial-data-sync-trust-item",
        ".commercial-data-sync-status-strip",
        ".commercial-data-sync-status-pill",
        ".commercial-data-sync-actions",
        ".commercial-data-sync-action",
        ".commercial-data-sync-status",
    ):
        assert selector in css
    base_css = css.split("@media", 1)[0]
    data_sync_rule = css_rule_body(base_css, ".commercial-data-sync")
    assert data_sync_rule is not None
    assert "order: 12;" in data_sync_rule

    primary_selector_block = re.search(r"function commercialPrimaryWorkflowSelectors\(\) \{\s*return \[(?P<body>.*?)\];", js, re.S)
    assert primary_selector_block is not None
    assert "'.commercial-data-sync'" in primary_selector_block.group("body")

    for function_name in (
        "function commercialDataSyncPreference(scope, fallbackSource)",
        "function commercialDataSyncSource(id, label, detail, target, status, tone = '')",
        "function commercialDataSyncTrust(label, value, detail, tone = '')",
        "function commercialDataSyncSummary(config, activeSource)",
        "function csvFromRows(rows)",
        "function renderCommercialDataSync(root, config, activeSource)",
        "function bindCommercialDataSync(root, scope, configFactory)",
        "function workbenchDataSyncConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockDataSyncConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioDataSyncConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchDataSync(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockDataSync(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioDataSync(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "資料同步啟動台",
        "追蹤表同步啟動台",
        "單股來源同步",
        "投組帳戶同步",
        "券商追蹤表",
        "手動股票",
        "來源稽核",
        "報價來源",
        "公告同步",
        "分析師預估",
        "筆記匯入",
        "券商 CSV",
        "持股成本批次",
        "股息資料流",
        "稅務匯出",
        "打開同步",
        "複製同步計畫",
        "匯出同步 CSV",
        "儲存同步計畫",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-data-sync",
        "data-commercial-data-sync-copy",
        "data-commercial-data-sync-export",
        "data-commercial-data-sync-save",
        "data-commercial-data-sync-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`data-sync-${scope}`" in js
    assert "downloadCommercialText(`onstock-${scope}-data-sync.csv`" in js
    assert "renderWorkbenchDataSync(document.getElementById('commercial-workbench-data-sync')" in js
    assert "renderStockDataSync(document.getElementById('commercial-stock-data-sync')" in js
    assert "renderPortfolioDataSync(document.getElementById('commercial-portfolio-data-sync')" in js


def test_data_sync_launchpads_keep_mobile_source_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-data-sync" in mobile_css
    assert ".commercial-data-sync-source-grid" in mobile_css
    assert ".commercial-data-sync-source" in mobile_css
    assert ".commercial-data-sync-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    source_grid = css_rule_body(mobile_css, ".commercial-data-sync-source-grid")
    assert source_grid is not None
    assert "display: grid;" in source_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in source_grid
    assert "overflow-x: visible;" in source_grid

    trust_grid = css_rule_body(mobile_css, ".commercial-data-sync-trust-list")
    assert trust_grid is not None
    assert "display: grid;" in trust_grid
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in trust_grid
    assert "overflow-x: visible;" in trust_grid

    actions = css_rule_body(mobile_css, ".commercial-data-sync-actions")
    assert actions is not None
    assert "display: grid;" in actions
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in actions
    assert "overflow-x: visible;" in actions

    action = css_rule_body(mobile_css, ".commercial-data-sync-action")
    assert action is not None
    assert "width: 100%;" in action
    assert "white-space: normal;" in action
    assert "aria-label=\"資料同步啟動台\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialDataSyncSummary(config, activeSource)" in js
    assert "commercialDataSyncPreference(config?.scope || 'workbench', fallbackSource)" in js


def test_data_sync_launchpads_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    function_pairs = (
        ("commercialDataSyncSummary", "commercialDataSyncCsv"),
        ("commercialDataSyncCsv", "renderCommercialDataSync"),
        ("renderCommercialDataSync", "bindCommercialDataSync"),
        ("bindCommercialDataSync", "workbenchDataSyncConfig"),
        ("workbenchDataSyncConfig", "stockDataSyncConfig"),
        ("stockDataSyncConfig", "portfolioDataSyncConfig"),
        ("portfolioDataSyncConfig", "renderWorkbenchDataSync"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "資料同步啟動台",
        "追蹤表同步啟動台",
        "單股來源同步",
        "投組帳戶同步",
        "券商追蹤表",
        "CSV 匯入",
        "手動股票",
        "來源稽核",
        "報價來源",
        "公告同步",
        "分析師預估",
        "筆記匯入",
        "券商 CSV",
        "持股成本批次",
        "股息資料流",
        "稅務匯出",
        "打開同步",
        "複製同步計畫",
        "匯出同步 CSV",
        "儲存同步計畫",
        "選取來源",
        "同步來源",
        "信任檢查",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Data Sync Launchpad",
        "Watchlist Sync Launchpad",
        "Stock Source Sync",
        "Portfolio Account Sync",
        "Broker Watchlist",
        "Manual Symbols",
        "Source Audit",
        "Quote Feed",
        "Filings Sync",
        "Analyst Estimates",
        "Notes Import",
        "Broker CSV",
        "Holdings Lots",
        "Dividend Feed",
        "Tax Export",
        "Open Sync",
        "Copy Sync Plan",
        "Export Sync CSV",
        "Save Sync Plan",
        "Data sync plan copied",
        "Data sync CSV exported",
        "Data sync plan saved",
        "Data sync opened",
        "Selected Source:",
        "Source Detail:",
        "Sync Sources:",
        "Trust Checks:",
        "Link:",
    ):
        assert legacy_label not in product_layer


def test_commercial_pages_add_scenario_simulators_for_what_if_decisions():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-scenario-simulator", "commercial-workbench-data-sync", "commercial-workbench-report-composer"),
        "stock-detail.html": ("commercial-stock-scenario-simulator", "commercial-stock-data-sync", "commercial-stock-report-composer"),
        "portfolio-dashboard.html": ("commercial-portfolio-scenario-simulator", "commercial-portfolio-data-sync", "commercial-portfolio-report-composer"),
    }
    for filename, (simulator_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{simulator_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{simulator_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-scenario-simulator",
        ".commercial-scenario-copy",
        ".commercial-scenario-option-grid",
        ".commercial-scenario-option",
        ".commercial-scenario-option.is-active",
        ".commercial-scenario-impact-list",
        ".commercial-scenario-impact",
        ".commercial-scenario-confidence-strip",
        ".commercial-scenario-confidence-pill",
        ".commercial-scenario-actions",
        ".commercial-scenario-action",
        ".commercial-scenario-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialScenarioPreference(scope, fallbackScenario)",
        "function commercialScenarioOption(id, label, detail, target, status, tone = '')",
        "function commercialScenarioImpact(label, value, detail, tone = '')",
        "function commercialScenarioSummary(config, activeScenario)",
        "function renderCommercialScenarioSimulator(root, config, activeScenario)",
        "function bindCommercialScenarioSimulator(root, scope, configFactory)",
        "function workbenchScenarioSimulatorConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockScenarioSimulatorConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioScenarioSimulatorConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchScenarioSimulator(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockScenarioSimulator(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioScenarioSimulator(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Scenario Simulator",
        "Watchlist What-If Lab",
        "Stock Valuation Simulator",
        "Portfolio Rebalance Simulator",
        "Market Shock",
        "Earnings Surprise",
        "Quality Filter",
        "Rotation Play",
        "Price Shock",
        "Bull Case",
        "Bear Case",
        "Earnings Event",
        "Drift Trim",
        "Income Tilt",
        "FX Shock",
        "Tax Aware",
        "Open Simulation",
        "Copy Scenario",
        "Export Scenario CSV",
        "Save Scenario",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-scenario-simulator",
        "data-commercial-scenario-copy",
        "data-commercial-scenario-export",
        "data-commercial-scenario-save",
        "data-commercial-scenario-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`scenario-simulator-${scope}`" in js
    assert "downloadCommercialText(`onstock-${scope}-scenario-simulator.csv`" in js
    assert "renderWorkbenchScenarioSimulator(document.getElementById('commercial-workbench-scenario-simulator')" in js
    assert "renderStockScenarioSimulator(document.getElementById('commercial-stock-scenario-simulator')" in js
    assert "renderPortfolioScenarioSimulator(document.getElementById('commercial-portfolio-scenario-simulator')" in js


def test_scenario_simulators_keep_mobile_what_if_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-scenario-simulator" in mobile_css
    assert ".commercial-scenario-option-grid" in mobile_css
    assert ".commercial-scenario-option" in mobile_css
    assert ".commercial-scenario-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Scenario Simulator\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialScenarioSummary(config, activeScenario)" in js
    assert "commercialScenarioPreference(config?.scope || 'workbench', fallbackScenario)" in js


def test_commercial_pages_add_market_briefs_for_first_screen_context():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-market-brief", "commercial-workbench-today-inbox", "commercial-workbench-setup-launchpad"),
        "stock-detail.html": ("commercial-stock-market-brief", "commercial-stock-today-inbox", "commercial-stock-setup-launchpad"),
        "portfolio-dashboard.html": ("commercial-portfolio-market-brief", "commercial-portfolio-today-inbox", "commercial-portfolio-setup-launchpad"),
    }
    for filename, (brief_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{brief_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{brief_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-market-brief",
        ".commercial-market-brief-copy",
        ".commercial-market-brief-lens-grid",
        ".commercial-market-brief-lens",
        ".commercial-market-brief-lens.is-active",
        ".commercial-market-brief-signal-grid",
        ".commercial-market-brief-signal",
        ".commercial-market-brief-actions",
        ".commercial-market-brief-action",
        ".commercial-market-brief-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialMarketBriefPreference(scope, fallbackLens)",
        "function commercialMarketBriefLens(id, label, detail, target, status, tone = '')",
        "function commercialMarketBriefSignal(label, value, detail, tone = '')",
        "function commercialMarketBriefSummary(config, activeLens)",
        "function renderCommercialMarketBrief(root, config, activeLens)",
        "function bindCommercialMarketBrief(root, scope, configFactory)",
        "function workbenchMarketBriefConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockMarketBriefConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioMarketBriefConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchMarketBrief(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockMarketBrief(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioMarketBrief(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Market Brief",
        "Watchlist Market Brief",
        "Stock Market Brief",
        "Portfolio Market Brief",
        "Market Movers",
        "Alert Heat",
        "News Flow",
        "Risk Tone",
        "Quote Pulse",
        "Catalyst Watch",
        "Factor Signal",
        "News Impact",
        "Portfolio Pulse",
        "Benchmark Drift",
        "Cash & Income",
        "Risk Queue",
        "Open Brief",
        "Copy Brief",
        "Export Brief CSV",
        "Save Brief",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-market-brief",
        "data-commercial-market-copy",
        "data-commercial-market-export",
        "data-commercial-market-save",
        "data-commercial-market-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`market-brief-${scope}`" in js
    assert "downloadCommercialText(`onstock-${scope}-market-brief.csv`" in js
    assert "renderWorkbenchMarketBrief(document.getElementById('commercial-workbench-market-brief')" in js
    assert "renderStockMarketBrief(document.getElementById('commercial-stock-market-brief')" in js
    assert "renderPortfolioMarketBrief(document.getElementById('commercial-portfolio-market-brief')" in js


def test_market_briefs_keep_mobile_daily_context_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-market-brief" in mobile_css
    assert ".commercial-market-brief-lens-grid" in mobile_css
    assert ".commercial-market-brief-lens" in mobile_css
    assert ".commercial-market-brief-action" in mobile_css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in mobile_css
    assert "order: 3;" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Market Brief\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialMarketBriefSummary(config, activeLens)" in js
    assert "commercialMarketBriefPreference(config?.scope || 'workbench', fallbackLens)" in js


def test_commercial_pages_add_page_specific_event_timeline_strips_after_market_brief():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-event-strip", "commercial-workbench-market-brief", "commercial-workbench-triage-board"),
        "stock-detail.html": ("commercial-stock-event-strip", "commercial-stock-market-brief", "commercial-stock-snapshot-hero"),
        "portfolio-dashboard.html": ("commercial-portfolio-event-strip", "commercial-portfolio-market-brief", "commercial-portfolio-exposure-map"),
    }
    for filename, (strip_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{strip_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{strip_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-event-strip",
        ".commercial-event-strip.is-portfolio",
        ".commercial-event-copy",
        ".commercial-event-cards",
        ".commercial-event-card",
        ".commercial-event-card.is-warning",
        ".commercial-event-card.is-live",
        ".commercial-event-actions",
        ".commercial-event-action",
        ".commercial-event-action.is-primary",
    ):
        assert selector in css
    for function_name in (
        "function renderCommercialEventStrip(root, config)",
        "function workbenchEventTimelineStrip(rows, activeTicker, activeView, currentFilter)",
        "function stockEventTimelineStrip(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioEventTimelineStrip(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js


def test_research_workbench_event_strip_routes_watchlist_calendar_and_reruns():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Watchlist Event Timeline", "Earnings Queue", "News & Filings", "Report Reruns", "Open Calendar", "Open Filings Queue", "Open Rerun Alerts"):
        assert label in js
    assert 'data-commercial-workbench-event-view="event"' in js
    assert 'data-commercial-workbench-event-filter="rerun"' in js
    assert 'data-commercial-workbench-event-target="commercial-workbench-event-calendar"' in js
    assert "const workbenchEventTarget = button.dataset.commercialWorkbenchEventTarget || button.dataset.commercialEventTarget;" in js
    assert "scrollCommercialTaskTarget(workbenchEventTarget);" in js


def test_stock_detail_event_strip_routes_catalyst_dividend_and_filings():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Stock Catalyst Timeline", "Next Earnings", "Dividend Check", "Filing/Transcript", "Open Catalyst", "Open Dividend Date", "Open Filings"):
        assert label in js
    assert 'data-commercial-stock-event-tab="news"' in js
    assert 'data-commercial-stock-event-tab="financials"' in js
    assert 'data-commercial-stock-event-coverage="filings"' in js
    assert "const stockEventCoverage = button.dataset.commercialStockEventCoverage;" in js
    assert "activeCoverage = stockEventCoverage;" in js


def test_portfolio_dashboard_event_strip_routes_holdings_income_and_rebalance_timing():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Portfolio Event Timeline", "Holdings Events", "Income Runway", "Rebalance Window", "Open Holdings Events", "Open Income Runway", "Open Rebalance Window"):
        assert label in js
    assert 'data-commercial-portfolio-event-lens="risk"' in js
    assert 'data-commercial-portfolio-event-lens="contribution"' in js
    assert 'data-commercial-portfolio-event-target="commercial-portfolio-rebalance-ticket"' in js
    assert "const portfolioEventLens = validCommercialChoice(button.dataset.commercialPortfolioEventLens, ['sector', 'country', 'risk', 'contribution'], activeLens);" in js
    assert "activeLens = portfolioEventLens;" in js


def test_event_timeline_strips_keep_mobile_actions_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-event-strip" in mobile_css
    assert ".commercial-event-cards" in mobile_css
    assert ".commercial-event-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "width: 100%;" in mobile_css
    assert "aria-label=\"Event Timeline\"" in js


def test_commercial_pages_add_page_specific_priority_mode_strips_after_event_timeline():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-priority-strip", "commercial-workbench-event-strip", "commercial-workbench-triage-board"),
        "stock-detail.html": ("commercial-stock-priority-strip", "commercial-stock-event-strip", "commercial-stock-snapshot-hero"),
        "portfolio-dashboard.html": ("commercial-portfolio-priority-strip", "commercial-portfolio-event-strip", "commercial-portfolio-exposure-map"),
    }
    for filename, (strip_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{strip_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{strip_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-priority-strip",
        ".commercial-priority-strip.is-portfolio",
        ".commercial-priority-copy",
        ".commercial-priority-modes",
        ".commercial-priority-mode",
        ".commercial-priority-mode.is-active",
        ".commercial-priority-mode.is-warning",
        ".commercial-priority-actions",
        ".commercial-priority-action",
        ".commercial-priority-action.is-primary",
    ):
        assert selector in css
    for function_name in (
        "function renderCommercialPriorityStrip(root, config)",
        "function workbenchPriorityModeStrip(rows, activeTicker, activeView, currentFilter)",
        "function stockPriorityModeStrip(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioPriorityModeStrip(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js


def test_research_workbench_priority_strip_routes_beginner_alerts_and_report_handoff():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Watchlist Priority Modes", "Beginner Review", "Alert First", "Report Handoff", "Start Beginner Review", "Open Alert First", "Open Report Handoff"):
        assert label in js
    assert 'data-commercial-workbench-priority-view="risk"' in js
    assert 'data-commercial-workbench-priority-filter="alerts"' in js
    assert 'data-commercial-workbench-priority-target="commercial-workbench-alert-center"' in js
    assert "const workbenchPriorityTarget = button.dataset.commercialWorkbenchPriorityTarget || button.dataset.commercialPriorityTarget;" in js
    assert "scrollCommercialTaskTarget(workbenchPriorityTarget);" in js


def test_stock_detail_priority_strip_routes_snapshot_earnings_and_research_pack():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Stock Priority Modes", "Snapshot First", "Earnings Prep", "Research Pack", "Open Snapshot First", "Open Earnings Prep", "Open Research Pack"):
        assert label in js
    assert 'data-commercial-stock-priority-tab="news"' in js
    assert 'data-commercial-stock-priority-tab="report"' in js
    assert 'data-commercial-stock-priority-coverage="filings"' in js
    assert "const stockPriorityCoverage = button.dataset.commercialStockPriorityCoverage;" in js
    assert "activeCoverage = stockPriorityCoverage;" in js


def test_portfolio_dashboard_priority_strip_routes_health_warnings_and_rebalance_prep():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("Portfolio Priority Modes", "Health First", "Warnings First", "Rebalance Prep", "Open Health First", "Open Warnings First", "Open Rebalance Prep"):
        assert label in js
    assert 'data-commercial-portfolio-priority-lens="risk"' in js
    assert 'data-commercial-portfolio-priority-lens="contribution"' in js
    assert 'data-commercial-portfolio-priority-target="commercial-portfolio-rebalance-ticket"' in js
    assert "const portfolioPriorityLens = validCommercialChoice(button.dataset.commercialPortfolioPriorityLens, ['sector', 'country', 'risk', 'contribution'], activeLens);" in js
    assert "activeLens = portfolioPriorityLens;" in js


def test_priority_mode_strips_keep_mobile_actions_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-priority-strip" in mobile_css
    assert ".commercial-priority-modes" in mobile_css
    assert ".commercial-priority-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "width: 100%;" in mobile_css
    assert "aria-label=\"Priority Mode\"" in js


def test_commercial_pages_add_above_the_fold_page_specific_jump_decks():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-jump-deck", 'class="commercial-topbar"', 'id="commercial-workspace-chrome"'),
        "stock-detail.html": ("commercial-stock-jump-deck", 'class="commercial-topbar"', 'id="commercial-workspace-chrome"'),
        "portfolio-dashboard.html": ("commercial-portfolio-jump-deck", 'class="commercial-topbar"', 'id="commercial-workspace-chrome"'),
    }
    for filename, (deck_id, before_marker, after_marker) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{deck_id}"') == 1
        assert html.index(before_marker) < html.index(f'id="{deck_id}"') < html.index(after_marker)
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-jump-deck",
        ".commercial-jump-deck.is-portfolio",
        ".commercial-jump-copy",
        ".commercial-jump-steps",
        ".commercial-jump-step",
        ".commercial-jump-step.is-active",
        ".commercial-jump-step.is-warning",
        ".commercial-jump-actions",
        ".commercial-jump-action",
        ".commercial-jump-action.is-primary",
    ):
        assert selector in css
    for function_name in (
        "function renderCommercialJumpDeck(root, config)",
        "function workbenchJumpDeck(rows, activeTicker, activeView, currentFilter)",
        "function stockJumpDeck(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioJumpDeck(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js


def test_jump_decks_use_compact_desktop_command_bar_before_workspace():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    deck = re.search(r"\.commercial-jump-deck \{(?P<body>.*?)\n\}", css, re.S)
    assert deck is not None
    deck_body = deck.group("body")
    assert "grid-template-columns: minmax(210px, 0.34fr) minmax(420px, 1fr) minmax(360px, 0.74fr);" in deck_body
    assert "gap: 10px;" in deck_body
    assert "align-items: center;" in deck_body
    assert "padding: 10px;" in deck_body

    for selector in (".commercial-jump-copy em", ".commercial-jump-step em", ".commercial-jump-action em"):
        compact_text = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n\}}", css, re.S)
        assert compact_text is not None
        assert "display: none;" in compact_text.group("body")

    steps = re.search(r"\.commercial-jump-step \{(?P<body>.*?)\n\}", css, re.S)
    assert steps is not None
    assert "min-height: 58px;" in steps.group("body")
    assert "align-content: center;" in steps.group("body")

    actions = re.search(r"\.commercial-jump-actions \{(?P<body>.*?)\n\}", css, re.S)
    assert actions is not None
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in actions.group("body")

    action = re.search(r"\.commercial-jump-action \{(?P<body>.*?)\n\}", css, re.S)
    assert action is not None
    assert "min-height: 58px;" in action.group("body")
    assert "align-content: center;" in action.group("body")


def test_workspace_collapsed_state_becomes_desktop_command_bar_for_page_specific_tasks():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    collapsed = re.search(r"\.commercial-workspace-chrome\.is-collapsed \{(?P<body>.*?)\n\}", css, re.S)
    assert collapsed is not None
    collapsed_body = collapsed.group("body")
    assert "grid-template-columns: minmax(300px, 0.3fr) minmax(0, 1fr);" in collapsed_body
    assert "gap: 8px;" in collapsed_body
    assert "align-items: stretch;" in collapsed_body
    assert "padding: 8px 18px 0;" in collapsed_body

    summary = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-summary \{(?P<body>.*?)\n\}", css, re.S)
    assert summary is not None
    summary_body = summary.group("body")
    assert "grid-column: auto;" in summary_body
    assert "grid-template-columns: minmax(180px, 0.2fr) minmax(216px, 0.22fr) minmax(276px, 1fr) minmax(104px, auto);" in summary_body
    assert "min-height: 62px;" in summary_body

    summary_copy = re.search(r"\.commercial-workspace-chrome\.is-collapsed \.commercial-workspace-summary-copy \{(?P<body>.*?)\n\}", css, re.S)
    assert summary_copy is not None
    assert "grid-template-columns: minmax(0, 1fr);" in summary_copy.group("body")

    for selector in (
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-search .commercial-workspace-label",
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-summary-copy .commercial-workspace-label",
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-summary-copy em",
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-confidence-item strong",
        ".commercial-workspace-chrome.is-collapsed .commercial-workspace-summary-button strong",
    ):
        rule = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n\}}", css, re.S)
        assert rule is not None
        assert "display: none;" in rule.group("body")

    assert "root.dataset.commercialWorkspaceScope = activeId;" in js


def test_research_workbench_jump_deck_routes_triage_alerts_and_report_desk_without_scrolling():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("追蹤表命令地圖", "分流台", "警示隊列", "報告台", "打開分流", "打開警示", "打開報告台"):
        assert label in js
    assert 'data-commercial-workbench-jump-view="risk"' in js
    assert 'data-commercial-workbench-jump-filter="alerts"' in js
    assert 'data-commercial-workbench-jump-target="commercial-workbench-alert-center"' in js
    assert "const workbenchJumpTarget = button.dataset.commercialWorkbenchJumpTarget || button.dataset.commercialJumpTarget;" in js
    assert "scrollCommercialTaskTarget(workbenchJumpTarget);" in js


def test_stock_detail_jump_deck_routes_snapshot_catalyst_and_report_path():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("單股研究地圖", "快照路徑", "催化事件", "報告路徑", "打開快照路徑", "打開事件路徑", "打開報告路徑"):
        assert label in js
    assert 'data-commercial-stock-jump-tab="news"' in js
    assert 'data-commercial-stock-jump-tab="report"' in js
    assert 'data-commercial-stock-jump-coverage="filings"' in js
    assert "const stockJumpCoverage = button.dataset.commercialStockJumpCoverage;" in js
    assert "activeCoverage = stockJumpCoverage;" in js


def test_portfolio_dashboard_jump_deck_routes_health_warnings_and_rebalance_path():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for label in ("組合透視地圖", "健康路徑", "警示路徑", "再平衡路徑", "打開健康", "打開警示", "打開再平衡"):
        assert label in js
    assert 'data-commercial-portfolio-jump-lens="risk"' in js
    assert 'data-commercial-portfolio-jump-lens="contribution"' in js
    assert 'data-commercial-portfolio-jump-target="commercial-portfolio-rebalance-ticket"' in js
    assert "const portfolioJumpLens = validCommercialChoice(button.dataset.commercialPortfolioJumpLens, ['sector', 'country', 'risk', 'contribution'], activeLens);" in js
    assert "activeLens = portfolioJumpLens;" in js


def test_jump_decks_keep_mobile_actions_accessible_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-jump-deck" in mobile_css
    assert ".commercial-jump-steps" in mobile_css
    assert ".commercial-jump-action" in mobile_css
    assert ".commercial-jump-copy em" in mobile_css
    assert "display: none;" in mobile_css
    assert "display: flex;" in mobile_css
    assert "flex-wrap: nowrap;" in mobile_css
    assert "overflow-x: auto;" in mobile_css
    assert "flex: 0 0 148px;" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"${escapeHtml(config?.title || '任務捷徑')}\"" in js


def test_commercial_pages_add_distinct_competitor_grade_first_screen_modules():
    html_requirements = {
        "research-workbench.html": (
            "commercial-workbench-triage-board",
            "commercial-workbench-market-brief",
            "commercial-workbench-setup-launchpad",
            ("commercial-stock-snapshot-hero", "commercial-portfolio-exposure-map"),
        ),
        "stock-detail.html": (
            "commercial-stock-snapshot-hero",
            "commercial-stock-market-brief",
            "commercial-stock-setup-launchpad",
            ("commercial-workbench-triage-board", "commercial-portfolio-exposure-map"),
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-exposure-map",
            "commercial-portfolio-market-brief",
            "commercial-portfolio-setup-launchpad",
            ("commercial-workbench-triage-board", "commercial-stock-snapshot-hero"),
        ),
    }
    for filename, (module_id, before_id, after_id, forbidden_ids) in html_requirements.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{module_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{module_id}"') < html.index(f'id="{after_id}"')
        for forbidden_id in forbidden_ids:
            assert f'id="{forbidden_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-triage-board",
        ".commercial-triage-toolbar",
        ".commercial-triage-list",
        ".commercial-triage-row",
        ".commercial-triage-row.is-active",
        ".commercial-triage-action",
        ".commercial-snapshot-hero",
        ".commercial-snapshot-hero-main",
        ".commercial-snapshot-metric-strip",
        ".commercial-snapshot-action",
        ".commercial-exposure-map",
        ".commercial-exposure-grid",
        ".commercial-exposure-bar",
        ".commercial-exposure-action",
    ):
        assert selector in css
    for function_name in (
        "function workbenchTriageBoardRows(rows, activeTicker, activeView, currentFilter)",
        "function workbenchTriageSummary(rows, activeTicker, activeView, currentFilter)",
        "function renderWorkbenchTriageBoard(root, rows, activeTicker, activeView, currentFilter)",
        "function bindWorkbenchTriageBoard(root, getRows, getActiveTicker, onTickerSelect)",
        "function stockSnapshotHeroSummary(snapshot, currentTab, activeScenario, activeRange)",
        "function renderStockSnapshotHero(root, snapshot, currentTab, activeScenario, activeRange)",
        "function bindStockSnapshotHero(root)",
        "function portfolioExposureMapConfig(payload, activeLens, activeScenario, activeTargetModel)",
        "function portfolioExposureMapSummary(config)",
        "function renderPortfolioExposureMap(root, payload, activeLens, activeScenario, activeTargetModel)",
        "function bindPortfolioExposureMap(root)",
    ):
        assert function_name in js
    for label in (
        "Watchlist Triage Board",
        "單股快照",
        "Portfolio Exposure Map",
        "Open Snapshot",
        "Copy Triage",
        "Export Triage CSV",
        "Save Triage",
        "打開財務",
        "複製快照",
        "設定價格提醒",
        "建立研究報告",
        "Open Rebalance",
        "Copy Exposure",
        "Export Exposure CSV",
        "Save Exposure",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-triage-ticker",
        "data-commercial-triage-copy",
        "data-commercial-triage-export",
        "data-commercial-triage-save",
        "data-commercial-snapshot-hero-action",
        "data-commercial-snapshot-hero-target",
        "data-commercial-exposure-action",
        "data-commercial-exposure-target",
    ):
        assert data_attr in js
    assert "onTickerSelect(ticker, true)" in js
    assert "writeCommercialMemory('workbench-triage-board'" in js
    assert "downloadCommercialText('onstock-workbench-triage.csv'" in js
    assert "writeCommercialMemory('stock-snapshot-hero'" in js
    assert "writeCommercialMemory('portfolio-exposure-map'" in js
    assert "downloadCommercialText('onstock-portfolio-exposure.csv'" in js
    assert "renderWorkbenchTriageBoard(document.getElementById('commercial-workbench-triage-board')" in js
    assert "renderStockSnapshotHero(document.getElementById('commercial-stock-snapshot-hero')" in js
    assert "renderPortfolioExposureMap(document.getElementById('commercial-portfolio-exposure-map')" in js


def test_distinct_first_screen_modules_keep_mobile_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    for selector in (
        ".commercial-triage-board",
        ".commercial-triage-toolbar",
        ".commercial-triage-row",
        ".commercial-triage-action",
        ".commercial-snapshot-hero",
        ".commercial-snapshot-metric-strip",
        ".commercial-snapshot-action",
        ".commercial-exposure-map",
        ".commercial-exposure-grid",
        ".commercial-exposure-action",
    ):
        assert selector in mobile_css
    assert "grid-template-columns: 1fr;" in mobile_css
    assert "min-height: 44px;" in mobile_css
    action_order = re.search(
        r"\.commercial-triage-actions,\s*\.commercial-snapshot-actions,\s*\.commercial-exposure-actions \{(?P<body>.*?)\n  \}",
        mobile_css,
        re.S,
    )
    assert action_order is not None
    assert "order: 2;" in action_order.group("body")

    triage_list_order = re.search(r"\.commercial-triage-list \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert triage_list_order is not None
    assert "order: 3;" in triage_list_order.group("body")

    snapshot_metric_order = re.search(r"\.commercial-snapshot-metric-strip \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert snapshot_metric_order is not None
    assert "order: 3;" in snapshot_metric_order.group("body")

    snapshot_copy = re.search(r"\.commercial-snapshot-hero-main em \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert snapshot_copy is not None
    assert "-webkit-line-clamp: 3;" in snapshot_copy.group("body")
    assert "overflow: hidden;" in snapshot_copy.group("body")

    exposure_grid_order = re.search(r"\.commercial-exposure-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert exposure_grid_order is not None
    assert "order: 3;" in exposure_grid_order.group("body")
    assert "aria-label=\"Watchlist Triage Board\"" in js
    assert "aria-label=\"單股快照\"" in js
    assert "aria-label=\"Portfolio Exposure Map\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(workbenchTriageSummary(rows, activeTicker, activeView, currentFilter)" in js
    assert "copyCommercialText(stockSnapshotHeroSummary(snapshot, currentTab, activeScenario, activeRange)" in js
    assert "copyCommercialText(portfolioExposureMapSummary(config)" in js


def test_stock_snapshot_hero_uses_customer_chinese_snapshot_workflow():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    summary = re.search(
        r"function stockSnapshotHeroSummary\(snapshot, currentTab, activeScenario, activeRange\) \{(?P<body>.*?)\n    function renderStockSnapshotHero",
        js,
        re.S,
    )
    render = re.search(
        r"function renderStockSnapshotHero\(root, snapshot, currentTab, activeScenario, activeRange\) \{(?P<body>.*?)\n    function bindStockSnapshotHero",
        js,
        re.S,
    )
    binder = re.search(
        r"function bindStockSnapshotHero\(root\) \{(?P<body>.*?)\n    function portfolioExposureMapConfig",
        js,
        re.S,
    )
    assert summary is not None
    assert render is not None
    assert binder is not None

    product_layer = "\n".join([summary.group("body"), render.group("body"), binder.group("body")])
    for required_label in (
        "單股快照",
        "價格",
        "當日漲跌",
        "目標空間",
        "資料品質",
        "下一事件",
        "打開財務",
        "複製快照",
        "設定價格提醒",
        "建立研究報告",
        "快照已複製",
        "價格提醒已建立",
        "研究報告已打開",
        "財務資料已打開",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Snapshot Hero",
        "Price:",
        "Day Move:",
        "Target Gap",
        "Data Quality",
        "Next Event",
        "State:",
        "Link:",
        "Open Financials",
        "Copy Snapshot",
        "Set Price Alert",
        "Build Report",
        "Snapshot copied",
        "Price alert staged",
        "Report opened",
        "Financials opened",
    ):
        assert legacy_label not in product_layer


def test_commercial_pages_add_page_specific_insight_digests_for_alerts_news_and_warnings():
    html_requirements = {
        "research-workbench.html": ("commercial-workbench-insight-digest", "commercial-workbench-triage-board", "commercial-workbench-setup-launchpad"),
        "stock-detail.html": ("commercial-stock-insight-digest", "commercial-stock-snapshot-hero", "commercial-stock-setup-launchpad"),
        "portfolio-dashboard.html": ("commercial-portfolio-insight-digest", "commercial-portfolio-exposure-map", "commercial-portfolio-setup-launchpad"),
    }
    for filename, (digest_id, before_id, after_id) in html_requirements.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{digest_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{digest_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_requirements.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-insight-digest",
        ".commercial-insight-copy",
        ".commercial-insight-channel-grid",
        ".commercial-insight-channel",
        ".commercial-insight-channel.is-active",
        ".commercial-insight-item-grid",
        ".commercial-insight-item",
        ".commercial-insight-actions",
        ".commercial-insight-action",
        ".commercial-insight-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialInsightDigestPreference(scope, fallbackChannel)",
        "function commercialInsightDigestChannel(id, label, detail, target, status, tone = '')",
        "function commercialInsightDigestItem(label, value, detail, target, tone = '')",
        "function commercialInsightDigestSummary(config, activeChannel)",
        "function renderCommercialInsightDigest(root, config, activeChannel)",
        "function bindCommercialInsightDigest(root, scope, configFactory)",
        "function workbenchInsightDigestConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockInsightDigestConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioInsightDigestConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchInsightDigest(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockInsightDigest(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioInsightDigest(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Insight Digest",
        "Watchlist Insight Digest",
        "Stock Move Digest",
        "Portfolio Alert Digest",
        "News & Filings",
        "Rating Changes",
        "Price Alerts",
        "Earnings Queue",
        "Move Explainer",
        "Earnings Prep",
        "Rating Watch",
        "Transcript Notes",
        "Portfolio Warnings",
        "Holdings News",
        "Income Alerts",
        "Rebalance Memo",
        "Open Digest",
        "Copy Digest",
        "Export Digest CSV",
        "Save Digest",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-insight-digest",
        "data-commercial-insight-copy",
        "data-commercial-insight-export",
        "data-commercial-insight-save",
        "data-commercial-insight-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`insight-digest-${scope}`" in js
    assert "downloadCommercialText(`onstock-${scope}-insight-digest.csv`" in js
    assert "renderWorkbenchInsightDigest(document.getElementById('commercial-workbench-insight-digest')" in js
    assert "renderStockInsightDigest(document.getElementById('commercial-stock-insight-digest')" in js
    assert "renderPortfolioInsightDigest(document.getElementById('commercial-portfolio-insight-digest')" in js


def test_insight_digests_keep_mobile_alert_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    for selector in (
        ".commercial-insight-digest",
        ".commercial-insight-channel-grid",
        ".commercial-insight-channel",
        ".commercial-insight-item-grid",
        ".commercial-insight-action",
    ):
        assert selector in mobile_css

    action_order = re.search(r"\.commercial-insight-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert action_order is not None
    assert "order: 3;" in action_order.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in action_order.group("body")

    item_order = re.search(r"\.commercial-insight-item-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert item_order is not None
    assert "order: 4;" in item_order.group("body")

    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Insight Digest\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialInsightDigestSummary(config, activeChannel)" in js
    assert "commercialInsightDigestPreference(config?.scope || 'workbench', fallbackChannel)" in js


def test_commercial_pages_add_page_specific_mission_decks_for_distinct_workflows():
    html_requirements = {
        "research-workbench.html": ("commercial-workbench-batch-monitor", "commercial-workbench-insight-digest", "commercial-workbench-setup-launchpad"),
        "stock-detail.html": ("commercial-stock-catalyst-brief", "commercial-stock-insight-digest", "commercial-stock-setup-launchpad"),
        "portfolio-dashboard.html": ("commercial-portfolio-drift-review", "commercial-portfolio-insight-digest", "commercial-portfolio-setup-launchpad"),
    }
    for filename, (mission_id, before_id, after_id) in html_requirements.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{mission_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{mission_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_requirements.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-mission-deck",
        ".commercial-mission-copy",
        ".commercial-mission-lane-grid",
        ".commercial-mission-lane",
        ".commercial-mission-lane.is-active",
        ".commercial-mission-metric-grid",
        ".commercial-mission-metric",
        ".commercial-mission-actions",
        ".commercial-mission-action",
        ".commercial-mission-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialMissionPreference(scope, fallbackLane)",
        "function commercialMissionLane(id, label, detail, target, status, tone = '')",
        "function commercialMissionMetric(label, value, detail, target, tone = '')",
        "function commercialMissionSummary(config, activeLane)",
        "function renderCommercialMissionDeck(root, config, activeLane)",
        "function bindCommercialMissionDeck(root, scope, configFactory)",
        "function workbenchMissionDeckConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockMissionDeckConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioMissionDeckConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchMissionDeck(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockMissionDeck(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioMissionDeck(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Mission Deck",
        "Watchlist Batch Monitor",
        "Stock Catalyst Brief",
        "Portfolio Drift Review",
        "Move Review",
        "Report Rerun",
        "Peer Screen",
        "Digest Push",
        "Price Move",
        "Earnings Setup",
        "Rating Delta",
        "Transcript Check",
        "Top Weight",
        "Model Drift",
        "Risk Flags",
        "Client Pack",
        "Open Workspace",
        "Copy Mission",
        "Export Mission CSV",
        "Save Mission",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-mission-deck",
        "data-commercial-mission-copy",
        "data-commercial-mission-export",
        "data-commercial-mission-save",
        "data-commercial-mission-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`mission-deck-${scope}`" in js
    assert "downloadCommercialText(`onstock-${scope}-mission-deck.csv`" in js
    assert "renderWorkbenchMissionDeck(document.getElementById('commercial-workbench-batch-monitor')" in js
    assert "renderStockMissionDeck(document.getElementById('commercial-stock-catalyst-brief')" in js
    assert "renderPortfolioMissionDeck(document.getElementById('commercial-portfolio-drift-review')" in js


def test_mission_decks_keep_mobile_decision_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    for selector in (
        ".commercial-mission-deck",
        ".commercial-mission-lane-grid",
        ".commercial-mission-lane",
        ".commercial-mission-metric-grid",
        ".commercial-mission-action",
    ):
        assert selector in mobile_css

    action_order = re.search(r"\.commercial-mission-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert action_order is not None
    assert "order: 3;" in action_order.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in action_order.group("body")

    metric_order = re.search(r"\.commercial-mission-metric-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert metric_order is not None
    assert "order: 4;" in metric_order.group("body")

    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Mission Deck\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialMissionSummary(config, activeLane)" in js
    assert "commercialMissionPreference(config?.scope || 'workbench', fallbackLane)" in js


def test_quant_factor_lenses_are_first_screen_after_mission_decks_for_competitor_grade_scanning():
    html_requirements = {
        "research-workbench.html": ("commercial-workbench-batch-monitor", "commercial-workbench-factor-lens", "commercial-workbench-setup-launchpad"),
        "stock-detail.html": ("commercial-stock-catalyst-brief", "commercial-stock-factor-lens", "commercial-stock-setup-launchpad"),
        "portfolio-dashboard.html": ("commercial-portfolio-drift-review", "commercial-portfolio-factor-lens", "commercial-portfolio-setup-launchpad"),
    }
    for filename, (mission_id, factor_id, setup_id) in html_requirements.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{factor_id}"') == 1
        assert html.index(f'id="{mission_id}"') < html.index(f'id="{factor_id}"') < html.index(f'id="{setup_id}"')

    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    for label in (
        "Quant Factor Lens",
        "Watchlist Factor Grades",
        "Stock Factor Grades",
        "Portfolio Factor Grades",
        "Value",
        "Growth",
        "Profitability",
        "Momentum",
        "EPS Revisions",
    ):
        assert label in js
    assert "renderWorkbenchFactorLens(document.getElementById('commercial-workbench-factor-lens')" in js
    assert "renderStockFactorLens(document.getElementById('commercial-stock-factor-lens')" in js
    assert "renderPortfolioFactorLens(document.getElementById('commercial-portfolio-factor-lens')" in js


def test_commercial_pages_add_report_composers_for_exportable_briefs():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-report-composer", "commercial-workbench-scenario-simulator", "commercial-workbench-alert-center"),
        "stock-detail.html": ("commercial-stock-report-composer", "commercial-stock-scenario-simulator", "commercial-stock-alert-center"),
        "portfolio-dashboard.html": ("commercial-portfolio-report-composer", "commercial-portfolio-scenario-simulator", "commercial-portfolio-alert-center"),
    }
    for filename, (composer_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{composer_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{composer_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-report-composer",
        ".commercial-report-copy",
        ".commercial-report-template-grid",
        ".commercial-report-template",
        ".commercial-report-template.is-active",
        ".commercial-report-checklist",
        ".commercial-report-check",
        ".commercial-report-delivery-strip",
        ".commercial-report-delivery-pill",
        ".commercial-report-actions",
        ".commercial-report-action",
        ".commercial-report-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialReportComposerPreference(scope, fallbackTemplate)",
        "function commercialReportComposerTemplate(id, label, detail, target, status, tone = '')",
        "function commercialReportComposerCheck(label, value, detail, tone = '')",
        "function commercialReportComposerSummary(config, activeTemplate)",
        "function renderCommercialReportComposer(root, config, activeTemplate)",
        "function bindCommercialReportComposer(root, scope, configFactory)",
        "function workbenchReportComposerConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockReportComposerConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioReportComposerConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchReportComposer(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockReportComposer(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioReportComposer(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Report Composer",
        "Watchlist Brief Composer",
        "Stock Thesis Composer",
        "Portfolio Review Composer",
        "Daily Brief",
        "Alert Digest",
        "Screen Summary",
        "Report Pack",
        "One Pager",
        "Valuation Note",
        "Catalyst Brief",
        "Risk Memo",
        "Client One Pager",
        "Rebalance Memo",
        "Income Appendix",
        "Tax Pack",
        "Open Report",
        "Copy Report",
        "Export Report CSV",
        "Save Report",
    ):
        assert label in js
    for data_attr in (
        "data-commercial-report-composer",
        "data-commercial-report-copy",
        "data-commercial-report-export",
        "data-commercial-report-save",
        "data-commercial-report-target",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`report-composer-${scope}`" in js
    assert "downloadCommercialText(`onstock-${scope}-report-composer.csv`" in js
    assert "renderWorkbenchReportComposer(document.getElementById('commercial-workbench-report-composer')" in js
    assert "renderStockReportComposer(document.getElementById('commercial-stock-report-composer')" in js
    assert "renderPortfolioReportComposer(document.getElementById('commercial-portfolio-report-composer')" in js


def test_report_composers_keep_mobile_report_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-report-composer" in mobile_css
    assert ".commercial-report-template-grid" in mobile_css
    assert ".commercial-report-template" in mobile_css
    assert ".commercial-report-action" in mobile_css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Report Composer\"" in js
    assert "role=\"status\"" in js
    assert "copyCommercialText(commercialReportComposerSummary(config, activeTemplate)" in js
    assert "commercialReportComposerPreference(config?.scope || 'workbench', fallbackTemplate)" in js


def test_mobile_action_dock_does_not_overlay_report_composers():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 920px)" in css
    tablet_css = css.split("@media (max-width: 920px)", 1)[1].split("@media (max-width: 560px)", 1)[0]
    assert ".commercial-action-dock" in tablet_css
    assert "position: static;" in tablet_css
    assert "z-index: auto;" in tablet_css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-action-dock" in mobile_css
    assert "position: static;" in mobile_css
    assert "z-index: auto;" in mobile_css


def test_commercial_pages_add_competitor_grade_journey_command_palettes():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-journey-palette",
        "stock-detail.html": "commercial-stock-journey-palette",
        "portfolio-dashboard.html": "commercial-portfolio-journey-palette",
    }
    for filename, palette_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{palette_id}"') == 1
        for other_id in set(html_by_page.values()) - {palette_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-journey-palette",
        ".commercial-journey-copy",
        ".commercial-journey-search",
        ".commercial-journey-command-input",
        ".commercial-journey-shortcuts",
        ".commercial-journey-command",
        ".commercial-journey-command.is-active",
        ".commercial-journey-progress",
        ".commercial-journey-actions",
        ".commercial-journey-action",
        ".commercial-journey-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialJourneyPreference(scope, fallbackCommand)",
        "function renderCommercialJourneyPalette(root, config, activeCommand)",
        "function bindCommercialJourneyPalette(root, scope, configFactory)",
        "function commercialJourneyRoute(page, ticker, command)",
        "function workbenchJourneyPaletteConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockJourneyPaletteConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioJourneyPaletteConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchJourneyPalette(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockJourneyPalette(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioJourneyPalette(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Journey Command Palette",
        "Command Bar",
        "Keyboard Shortcuts",
        "Research Journey",
        "Watchlist to Snapshot",
        "Snapshot to Report",
        "Portfolio Review Path",
        "Open Journey",
        "Save Shortcut",
        "Cross-page Route",
    ):
        assert label in js
    assert "writeCommercialMemory(`journey-palette-${scope}`" in js
    assert "data-commercial-journey-command" in js
    assert "data-commercial-journey-query" in js
    assert "data-commercial-journey-open" in js
    assert "data-commercial-journey-save" in js
    assert "data-commercial-journey-route" in js
    assert "renderWorkbenchJourneyPalette(document.getElementById('commercial-workbench-journey-palette')" in js
    assert "renderStockJourneyPalette(document.getElementById('commercial-stock-journey-palette')" in js
    assert "renderPortfolioJourneyPalette(document.getElementById('commercial-portfolio-journey-palette')" in js


def test_journey_command_palettes_keep_mobile_command_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-journey-palette" in mobile_css
    assert ".commercial-journey-command-input" in mobile_css
    assert ".commercial-journey-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Journey Command Palette\"" in js
    assert "role=\"status\"" in js
    assert "commercialJourneyRoute(page, ticker, command)" in js


def test_commercial_pages_add_market_grade_research_progress_coaches():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-progress-coach",
        "stock-detail.html": "commercial-stock-progress-coach",
        "portfolio-dashboard.html": "commercial-portfolio-progress-coach",
    }
    for filename, coach_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{coach_id}"') == 1
        for other_id in set(html_by_page.values()) - {coach_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-progress-coach",
        ".commercial-progress-copy",
        ".commercial-progress-meter",
        ".commercial-progress-ring",
        ".commercial-progress-steps",
        ".commercial-progress-step",
        ".commercial-progress-step.is-complete",
        ".commercial-progress-actions",
        ".commercial-progress-action",
        ".commercial-progress-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialProgressCoachPreference(scope)",
        "function commercialProgressCoachText(config)",
        "function renderCommercialProgressCoach(root, config)",
        "function bindCommercialProgressCoach(root, scope, configFactory)",
        "function workbenchProgressCoachConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockProgressCoachConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioProgressCoachConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchProgressCoach(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockProgressCoach(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioProgressCoach(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Research Progress Coach",
        "Watchlist Triage",
        "Due Diligence Path",
        "Portfolio Review Coach",
        "Evidence Coverage",
        "Next Best Action",
        "Mark Step Done",
        "Open Evidence",
        "Copy Progress",
    ):
        assert label in js
    assert "writeCommercialMemory(`progress-coach-${scope}`" in js
    assert "data-commercial-progress-step" in js
    assert "data-commercial-progress-target" in js
    assert "data-commercial-progress-done" in js
    assert "data-commercial-progress-copy" in js
    assert "renderWorkbenchProgressCoach(document.getElementById('commercial-workbench-progress-coach')" in js
    assert "renderStockProgressCoach(document.getElementById('commercial-stock-progress-coach')" in js
    assert "renderPortfolioProgressCoach(document.getElementById('commercial-portfolio-progress-coach')" in js


def test_research_progress_coaches_keep_mobile_steps_and_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-progress-coach" in mobile_css
    assert ".commercial-progress-step" in mobile_css
    assert ".commercial-progress-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Research Progress Coach\"" in js
    assert "role=\"status\"" in js
    assert "commercialProgressCoachText(config)" in js


def test_commercial_pages_add_competitor_grade_quant_factor_lenses():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-factor-lens",
        "stock-detail.html": "commercial-stock-factor-lens",
        "portfolio-dashboard.html": "commercial-portfolio-factor-lens",
    }
    for filename, lens_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{lens_id}"') == 1
        for other_id in set(html_by_page.values()) - {lens_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-factor-lens",
        ".commercial-factor-copy",
        ".commercial-factor-tabs",
        ".commercial-factor-tab",
        ".commercial-factor-tab.is-active",
        ".commercial-factor-grade-grid",
        ".commercial-factor-grade-card",
        ".commercial-factor-grade-card.is-active",
        ".commercial-factor-benchmark",
        ".commercial-factor-actions",
        ".commercial-factor-action",
        ".commercial-factor-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialFactorLensPreference(scope, fallbackFactor)",
        "function commercialFactorLensCsv(config, activeFactor)",
        "function renderCommercialFactorLens(root, config, activeFactor)",
        "function bindCommercialFactorLens(root, scope, configFactory)",
        "function workbenchFactorLensConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockFactorLensConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioFactorLensConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchFactorLens(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockFactorLens(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioFactorLens(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Quant Factor Lens",
        "Factor Grades",
        "Sector Peer Rank",
        "Watchlist Factor Grades",
        "Stock Factor Grades",
        "Portfolio Factor Grades",
        "Value",
        "Growth",
        "Profitability",
        "Momentum",
        "EPS Revisions",
        "Open Underlying Data",
        "Save Factor View",
        "Export Factor Lens",
    ):
        assert label in js
    assert "writeCommercialMemory(`factor-lens-${scope}`" in js
    assert "data-commercial-factor-choice" in js
    assert "data-commercial-factor-target" in js
    assert "data-commercial-factor-save" in js
    assert "data-commercial-factor-export" in js
    assert "renderWorkbenchFactorLens(document.getElementById('commercial-workbench-factor-lens')" in js
    assert "renderStockFactorLens(document.getElementById('commercial-stock-factor-lens')" in js
    assert "renderPortfolioFactorLens(document.getElementById('commercial-portfolio-factor-lens')" in js


def test_quant_factor_lenses_keep_mobile_factor_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-factor-lens" in mobile_css
    assert ".commercial-factor-tab" in mobile_css
    assert ".commercial-factor-action" in mobile_css
    factor_lens = re.search(r"\.commercial-factor-lens \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert factor_lens is not None
    assert "scroll-margin-top: 186px;" in factor_lens.group("body")
    factor_tabs = re.search(r"\.commercial-factor-tabs,\n  \.commercial-factor-grade-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert factor_tabs is not None
    assert "display: grid;" in factor_tabs.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in factor_tabs.group("body")
    assert "overflow-x: visible;" in factor_tabs.group("body")

    factor_actions = re.search(r"\.commercial-factor-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert factor_actions is not None
    assert "display: grid;" in factor_actions.group("body")
    assert "grid-template-columns: 1fr;" in factor_actions.group("body")
    assert "overflow-x: visible;" in factor_actions.group("body")
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Quant Factor Lens\"" in js
    assert "role=\"status\"" in js
    assert "commercialFactorLensCsv(config, activeFactor)" in js


def test_commercial_pages_add_market_grade_coverage_matrices():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-coverage-matrix",
        "stock-detail.html": "commercial-stock-coverage-matrix",
        "portfolio-dashboard.html": "commercial-portfolio-coverage-matrix",
    }
    for filename, matrix_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{matrix_id}"') == 1
        for other_id in set(html_by_page.values()) - {matrix_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-coverage-matrix",
        ".commercial-coverage-copy",
        ".commercial-coverage-score",
        ".commercial-coverage-grid",
        ".commercial-coverage-card",
        ".commercial-coverage-card.is-active",
        ".commercial-coverage-card.is-complete",
        ".commercial-coverage-card.is-warning",
        ".commercial-coverage-actions",
        ".commercial-coverage-action",
        ".commercial-coverage-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialCoveragePreference(scope, fallbackCoverage)",
        "function commercialCoverageMatrixCsv(config, activeCoverage)",
        "function renderCommercialCoverageMatrix(root, config, activeCoverage)",
        "function bindCommercialCoverageMatrix(root, scope, configFactory)",
        "function coverageItem(id, label, status, detail, target, metric, source)",
        "function workbenchCoverageMatrixConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockCoverageMatrixConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioCoverageMatrixConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchCoverageMatrix(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockCoverageMatrix(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioCoverageMatrix(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "覆蓋矩陣",
        "追蹤表覆蓋",
        "單股研究覆蓋",
        "投組 X-Ray 覆蓋",
        "價格",
        "財務",
        "績效",
        "風險",
        "技術面",
        "新聞",
        "分析師評級",
        "股利",
        "EPS 歷史",
        "同業",
        "資產配置",
        "產業曝險",
        "全球區域",
        "費用",
        "個股統計",
        "重疊度",
        "打開覆蓋",
        "儲存覆蓋",
        "匯出覆蓋",
    ):
        assert label in js
    assert "writeCommercialMemory(`coverage-matrix-${scope}`" in js
    assert "data-commercial-coverage-choice" in js
    assert "data-commercial-coverage-target" in js
    assert "data-commercial-coverage-save" in js
    assert "data-commercial-coverage-export" in js
    assert "renderWorkbenchCoverageMatrix(document.getElementById('commercial-workbench-coverage-matrix')" in js
    assert "renderStockCoverageMatrix(document.getElementById('commercial-stock-coverage-matrix')" in js
    assert "renderPortfolioCoverageMatrix(document.getElementById('commercial-portfolio-coverage-matrix')" in js


def test_coverage_matrices_keep_mobile_coverage_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-coverage-matrix" in mobile_css
    assert ".commercial-coverage-card" in mobile_css
    assert ".commercial-coverage-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"覆蓋矩陣\"" in js
    assert "role=\"status\"" in js
    assert "commercialCoverageMatrixCsv(config, activeCoverage)" in js


def test_commercial_pages_add_daily_change_radars_for_monitoring():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-change-radar",
        "stock-detail.html": "commercial-stock-change-radar",
        "portfolio-dashboard.html": "commercial-portfolio-change-radar",
    }
    for filename, radar_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{radar_id}"') == 1
        for other_id in set(html_by_page.values()) - {radar_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-change-radar",
        ".commercial-change-copy",
        ".commercial-change-metric-grid",
        ".commercial-change-metric",
        ".commercial-change-feed",
        ".commercial-change-item",
        ".commercial-change-item.is-active",
        ".commercial-change-item.is-warning",
        ".commercial-change-actions",
        ".commercial-change-action",
        ".commercial-change-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialChangeRadarPreference(scope, fallbackChange)",
        "function commercialChangeRadarCsv(config, activeChange)",
        "function renderCommercialChangeRadar(root, config, activeChange)",
        "function bindCommercialChangeRadar(root, scope, configFactory)",
        "function changeRadarItem(id, label, value, detail, target, tone, source)",
        "function workbenchChangeRadarConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockChangeRadarConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioChangeRadarConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchChangeRadar(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockChangeRadar(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioChangeRadar(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "變動雷達",
        "追蹤表變動雷達",
        "單股變動雷達",
        "投組漂移雷達",
        "價格變動",
        "警示觸發",
        "報告更新",
        "新聞脈動",
        "分析師情緒",
        "EPS 修正",
        "估值變化",
        "同業變動",
        "配置漂移",
        "集中度",
        "論點缺口",
        "情境壓力",
        "打開變動",
        "標記已讀",
        "匯出變動雷達",
    ):
        assert label in js
    assert "writeCommercialMemory(`change-radar-${scope}`" in js
    assert "data-commercial-change-choice" in js
    assert "data-commercial-change-target" in js
    assert "data-commercial-change-acknowledge" in js
    assert "data-commercial-change-export" in js
    assert "renderWorkbenchChangeRadar(document.getElementById('commercial-workbench-change-radar')" in js
    assert "renderStockChangeRadar(document.getElementById('commercial-stock-change-radar')" in js
    assert "renderPortfolioChangeRadar(document.getElementById('commercial-portfolio-change-radar')" in js


def test_change_radars_keep_mobile_monitoring_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-change-radar" in mobile_css
    assert ".commercial-change-item" in mobile_css
    assert ".commercial-change-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    change_feed = re.search(r"\.commercial-change-metric-grid,\n  \.commercial-change-feed \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert change_feed is not None
    assert "display: grid;" in change_feed.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in change_feed.group("body")
    assert "overflow-x: visible;" in change_feed.group("body")
    change_actions = re.search(r"\.commercial-change-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert change_actions is not None
    assert "display: grid;" in change_actions.group("body")
    assert "overflow-x: visible;" in change_actions.group("body")
    assert "aria-label=\"變動雷達\"" in js
    assert "role=\"status\"" in js
    assert "commercialChangeRadarCsv(config, activeChange)" in js


def test_commercial_pages_add_research_evidence_binders_for_trust():
    html_by_page = {
        "research-workbench.html": "commercial-workbench-evidence-binder",
        "stock-detail.html": "commercial-stock-evidence-binder",
        "portfolio-dashboard.html": "commercial-portfolio-evidence-binder",
    }
    for filename, binder_id in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{binder_id}"') == 1
        for other_id in set(html_by_page.values()) - {binder_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-evidence-binder",
        ".commercial-evidence-copy",
        ".commercial-evidence-summary",
        ".commercial-evidence-source-grid",
        ".commercial-evidence-source",
        ".commercial-evidence-source.is-active",
        ".commercial-evidence-source.is-warning",
        ".commercial-evidence-actions",
        ".commercial-evidence-action",
        ".commercial-evidence-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialEvidenceBinderPreference(scope, fallbackEvidence)",
        "function commercialEvidenceBinderText(config, activeEvidence)",
        "function commercialEvidenceBinderCsv(config, activeEvidence)",
        "function renderCommercialEvidenceBinder(root, config, activeEvidence)",
        "function bindCommercialEvidenceBinder(root, scope, configFactory)",
        "function evidenceBinderItem(id, label, status, detail, target, source, timestamp)",
        "function workbenchEvidenceBinderConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockEvidenceBinderConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioEvidenceBinderConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchEvidenceBinder(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockEvidenceBinder(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioEvidenceBinder(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "證據夾",
        "追蹤表證據夾",
        "單股證據夾",
        "投組證據夾",
        "資料來源",
        "資料新鮮度",
        "決策追蹤",
        "快照報價",
        "新聞/公告",
        "報告包",
        "分析師共識",
        "財務報表",
        "預估修正",
        "同業比較",
        "持股 CSV",
        "基準模型",
        "風險旗標",
        "論點健康",
        "打開證據",
        "釘選證據",
        "匯出證據夾",
    ):
        assert label in js
    assert "writeCommercialMemory(`evidence-binder-${scope}`" in js
    assert "data-commercial-evidence-choice" in js
    assert "data-commercial-evidence-target" in js
    assert "data-commercial-evidence-pin" in js
    assert "data-commercial-evidence-export" in js
    assert "renderWorkbenchEvidenceBinder(document.getElementById('commercial-workbench-evidence-binder')" in js
    assert "renderStockEvidenceBinder(document.getElementById('commercial-stock-evidence-binder')" in js
    assert "renderPortfolioEvidenceBinder(document.getElementById('commercial-portfolio-evidence-binder')" in js


def test_evidence_binders_keep_mobile_evidence_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-evidence-binder" in mobile_css
    assert ".commercial-evidence-source" in mobile_css
    assert ".commercial-evidence-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    evidence_sources = re.search(r"\.commercial-evidence-source-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert evidence_sources is not None
    assert "display: grid;" in evidence_sources.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in evidence_sources.group("body")
    assert "overflow-x: visible;" in evidence_sources.group("body")
    evidence_actions = re.search(r"\.commercial-evidence-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert evidence_actions is not None
    assert "display: grid;" in evidence_actions.group("body")
    assert "overflow-x: visible;" in evidence_actions.group("body")
    assert "aria-label=\"證據夾\"" in js
    assert "role=\"status\"" in js
    assert "commercialEvidenceBinderCsv(config, activeEvidence)" in js


def test_change_and_evidence_layers_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    function_pairs = (
        ("commercialChangeRadarCsv", "changeRadarItem"),
        ("renderCommercialChangeRadar", "bindCommercialChangeRadar"),
        ("bindCommercialChangeRadar", "workbenchChangeRadarConfig"),
        ("workbenchChangeRadarConfig", "stockChangeRadarConfig"),
        ("stockChangeRadarConfig", "portfolioChangeRadarConfig"),
        ("portfolioChangeRadarConfig", "renderWorkbenchChangeRadar"),
        ("commercialEvidenceBinderText", "commercialEvidenceBinderCsv"),
        ("commercialEvidenceBinderCsv", "evidenceTone"),
        ("renderCommercialEvidenceBinder", "bindCommercialEvidenceBinder"),
        ("bindCommercialEvidenceBinder", "workbenchEvidenceBinderConfig"),
        ("workbenchEvidenceBinderConfig", "stockEvidenceBinderConfig"),
        ("stockEvidenceBinderConfig", "portfolioEvidenceBinderConfig"),
        ("portfolioEvidenceBinderConfig", "renderWorkbenchEvidenceBinder"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "變動雷達",
        "追蹤表變動雷達",
        "單股變動雷達",
        "投組漂移雷達",
        "價格變動",
        "警示觸發",
        "報告更新",
        "分析師情緒",
        "配置漂移",
        "情境壓力",
        "打開變動",
        "證據夾",
        "追蹤表證據夾",
        "單股證據夾",
        "投組證據夾",
        "資料來源",
        "資料新鮮度",
        "決策追蹤",
        "分析師共識",
        "持股 CSV",
        "基準模型",
        "打開證據",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Market Change Radar",
        "Daily Watchlist Radar",
        "Stock Change Radar",
        "Portfolio Drift Radar",
        "Price Move",
        "Alert Trigger",
        "Report Refresh",
        "News Pulse",
        "Analyst Sentiment",
        "EPS Revision",
        "Valuation Change",
        "Peer Move",
        "Allocation Drift",
        "Concentration",
        "Thesis Gap",
        "Scenario Stress",
        "Open Change",
        "Acknowledge Change",
        "Export Change Radar",
        "Evidence Binder",
        "Watchlist Evidence Binder",
        "Stock Evidence Binder",
        "Portfolio Evidence Binder",
        "Data Source",
        "Freshness",
        "Decision Tracking",
        "Snapshot Quote",
        "News & Filings",
        "Report Pack",
        "Analyst Consensus",
        "Financial Statements",
        "Estimate Revisions",
        "Peer Comparison",
        "Benchmark Model",
        "Risk Flags",
        "Thesis Health",
        "Open Evidence",
        "Pin Evidence",
        "Export Evidence Binder",
    ):
        assert legacy_label not in product_layer


def test_research_workbench_global_context_drives_watchlist_snapshot():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const workbenchContextRoot = document.getElementById('commercial-global-context')" in js
    assert "bindCommercialGlobalContext('research-workbench'" in js
    assert "commandQuery = contextTicker;" in js
    assert "activeTicker = normalizeTicker(contextTicker);" in js
    assert "await applyWorkbenchFilter();" in js
    assert "syncCommercialContextTicker(activeTicker)" in js
    assert "renderCommercialGlobalContext(workbenchContextRoot, { pageName: 'research-workbench', ticker: activeTicker, metrics: quoteContextMetrics(snapshot, selectedRow) })" in js
    assert "renderCommercialGlobalContext(workbenchContextRoot, { pageName: 'research-workbench', ticker: activeTicker, metrics: quoteContextMetrics(fallback, selectedRow) })" in js


def test_stock_detail_global_context_loads_ticker_snapshot_in_place():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "let stockDetailRequestSerial = 0;" in js
    assert "const stockContextRoot = document.getElementById('commercial-global-context')" in js
    assert "bindCommercialGlobalContext('stock-detail'" in js
    assert "contextTicker => load(contextTicker)" in js
    assert "const requestId = ++stockDetailRequestSerial;" in js
    assert "if (requestId !== stockDetailRequestSerial) return;" in js
    assert "syncCommercialContextTicker(normalized)" in js
    assert "renderCommercialGlobalContext(stockContextRoot, { pageName: 'stock-detail', ticker: normalized, metrics: quoteContextMetrics(snapshot) })" in js


def test_portfolio_dashboard_global_context_preserves_xray_state_and_ticker():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "const portfolioContextRoot = document.getElementById('commercial-global-context')" in js
    assert "let portfolioContextTicker = normalizeTicker(params.get('ticker') || lastPayload.concentration?.top_position?.ticker || '2330.TW')" in js
    assert "bindCommercialGlobalContext('portfolio-dashboard'" in js
    assert "portfolioContextTicker = normalizeTicker(contextTicker);" in js
    assert "replaceCommercialQuery({ ticker: portfolioContextTicker, lens: activeLens, scenario: activeScenario" in js
    assert "renderCommercialGlobalContext(portfolioContextRoot, { pageName: 'portfolio-dashboard', ticker: portfolioContextTicker, metrics: portfolioContextMetrics(lastPayload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel) })" in js


def test_commercial_pages_add_workspace_control_strips_for_competitive_workflows():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-control-strip", "commercial-global-context", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-control-strip", "commercial-global-context", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-control-strip", "commercial-global-context", "commercial-portfolio-journey-palette"),
    }
    for filename, (strip_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{strip_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{strip_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-control-strip",
        ".commercial-control-copy",
        ".commercial-control-view-grid",
        ".commercial-control-view",
        ".commercial-control-view.is-active",
        ".commercial-control-summary",
        ".commercial-control-actions",
        ".commercial-control-action",
        ".commercial-control-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialControlStripPreference(scope, fallbackView)",
        "function commercialControlStripCsv(config, activeView)",
        "function renderCommercialControlStrip(root, config, activeView)",
        "function bindCommercialControlStrip(root, scope, configFactory)",
        "function commercialControlView(id, label, status, detail, target, metric)",
        "function workbenchControlStripConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockControlStripConfig(snapshot, currentTab, activeScenario, activeRange, activeCoverage)",
        "function portfolioControlStripConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchControlStrip(root, rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function renderStockControlStrip(root, snapshot, currentTab, activeScenario, activeRange, activeCoverage)",
        "function renderPortfolioControlStrip(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "Workspace Control Strip",
        "Watchlist Control Strip",
        "Stock Research Control Strip",
        "Portfolio Control Strip",
        "Custom Views",
        "Column Sets",
        "Table / Chart / Insight",
        "Decision View",
        "Valuation View",
        "Event View",
        "Risk View",
        "Snapshot View",
        "Report View",
        "Financial View",
        "Analyst View",
        "X-Ray View",
        "Risk Review",
        "Rebalance View",
        "Client Pack",
        "Open Workspace",
        "Save Workspace",
        "Export View",
    ):
        assert label in js
    assert "writeCommercialMemory(`control-strip-${scope}`" in js
    assert "data-commercial-control-view" in js
    assert "data-commercial-control-target" in js
    assert "data-commercial-control-save" in js
    assert "data-commercial-control-export" in js
    assert "renderWorkbenchControlStrip(document.getElementById('commercial-workbench-control-strip')" in js
    assert "renderStockControlStrip(document.getElementById('commercial-stock-control-strip')" in js
    assert "renderPortfolioControlStrip(document.getElementById('commercial-portfolio-control-strip')" in js


def test_workspace_control_strips_keep_mobile_controls_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-control-strip" in mobile_css
    assert ".commercial-control-view-grid" in mobile_css
    assert ".commercial-control-view" in mobile_css
    assert ".commercial-control-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    assert "aria-label=\"Workspace Control Strip\"" in js
    assert "role=\"status\"" in js
    assert "commercialControlStripCsv(config, activeView)" in js


def test_context_and_control_strips_stay_early_for_competitive_no_hunt_workflows():
    pages = {
        "research-workbench.html": (
            "commercial-workbench-decision-radar",
            "commercial-global-context",
            "commercial-workbench-action-dock",
            "commercial-workbench-control-strip",
            "commercial-workbench-requirement-map",
        ),
        "stock-detail.html": (
            "commercial-stock-decision-radar",
            "commercial-global-context",
            "commercial-stock-action-dock",
            "commercial-stock-control-strip",
            "commercial-stock-requirement-map",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-decision-radar",
            "commercial-global-context",
            "commercial-portfolio-action-dock",
            "commercial-portfolio-control-strip",
            "commercial-portfolio-requirement-map",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    for filename, ids in pages.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        radar_id, context_id, action_id, control_id, requirement_id = ids
        assert html.index('class="commercial-hero"') < html.index(f'id="{radar_id}"')
        assert html.index(f'id="{radar_id}"') < html.index(f'id="{context_id}"')
        assert html.index(f'id="{context_id}"') < html.index(f'id="{action_id}"')
        assert html.index(f'id="{action_id}"') < html.index(f'id="{control_id}"')
        assert html.index(f'id="{control_id}"') < html.index(f'id="{requirement_id}"')

    context_bar = re.search(r"\.commercial-context-bar \{(?P<body>.*?)\n\}", css, re.S)
    assert context_bar is not None
    context_body = context_bar.group("body")
    assert "position: sticky;" in context_body
    assert "top: 76px;" in context_body
    assert "z-index: 9;" in context_body
    assert "background-color: rgba(7, 17, 30, 0.98);" in context_body

    section_nav = re.search(r"\.commercial-section-nav \{(?P<body>.*?)\n\}", css, re.S)
    assert section_nav is not None
    assert "position: relative;" in section_nav.group("body")
    assert "top: 224px;" not in section_nav.group("body")

    action_dock = re.search(r"\.commercial-action-dock \{(?P<body>.*?)\n\}", css, re.S)
    assert action_dock is not None
    assert "position: static;" in action_dock.group("body")
    assert "top: 72px;" not in action_dock.group("body")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_context = re.search(r"\.commercial-context-bar \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_context is not None
    assert "position: static;" in mobile_context.group("body")


def test_mobile_global_context_is_compact_after_decision_radar_for_no_hunt_entry():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    compact_meta = re.search(r"\.commercial-context-meta \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert compact_meta is not None
    assert "display: none;" in compact_meta.group("body")

    compact_form = re.search(r"\.commercial-context-form \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert compact_form is not None
    assert "grid-template-columns: minmax(0, 1fr) auto;" in compact_form.group("body")

    compact_metrics = re.search(r"\.commercial-context-metrics \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert compact_metrics is not None
    assert "display: grid;" in compact_metrics.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in compact_metrics.group("body")
    assert "overflow-x: visible;" in compact_metrics.group("body")
    assert "padding-bottom: 0;" in compact_metrics.group("body")

    compact_metric = re.search(r"\.commercial-context-metric \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert compact_metric is not None
    assert "width: 100%;" in compact_metric.group("body")
    assert "min-width: 0;" in compact_metric.group("body")
    assert "min-height: 44px;" in compact_metric.group("body")

    compact_actions = re.search(r"\.commercial-context-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert compact_actions is not None
    assert "display: grid;" in compact_actions.group("body")
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in compact_actions.group("body")

    compact_link = re.search(r"\.commercial-context-link \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert compact_link is not None
    assert "min-height: 44px;" in compact_link.group("body")


def test_commercial_pages_add_page_specific_decision_radars_above_requirement_maps():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-decision-radar",
            "commercial-global-context",
            "commercial-workbench-action-dock",
            "追蹤表決策雷達",
        ),
        "stock-detail.html": (
            "commercial-stock-decision-radar",
            "commercial-global-context",
            "commercial-stock-action-dock",
            "單股決策雷達",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-decision-radar",
            "commercial-global-context",
            "commercial-portfolio-action-dock",
            "組合決策雷達",
        ),
    }
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for filename, (radar_id, context_id, after_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{radar_id}"') == 1
        assert f'class="commercial-decision-radar"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index('class="commercial-hero"') < html.index(f'id="{radar_id}"') < html.index(f'id="{context_id}"')
        assert html.index(f'id="{context_id}"') < html.index(f'id="{after_id}"')
        for other_radar_id, _, _, _ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_radar_id}"' not in html

    for selector in (
        ".commercial-decision-radar",
        ".commercial-decision-radar-copy",
        ".commercial-decision-radar-ring",
        ".commercial-decision-radar-lane-grid",
        ".commercial-decision-radar-lane",
        ".commercial-decision-radar-map",
        ".commercial-decision-radar-tile",
        ".commercial-decision-radar-actions",
        ".commercial-decision-radar-action",
        ".commercial-decision-radar-status",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-decision-radar" in mobile_css
    assert ".commercial-decision-radar-lane-grid" in mobile_css
    assert ".commercial-decision-radar-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    for function_name in (
        "function commercialDecisionCoverageStatus(checks)",
        "function commercialDecisionRadarLane(id, label, value, detail, target, tone = '')",
        "function commercialDecisionRadarTile(label, value, detail, size = 1, tone = '')",
        "function commercialDecisionRadarSummary(config, activeLane)",
        "function renderCommercialDecisionRadar(root, config, activeLane)",
        "function bindCommercialDecisionRadar(root, scope, configFactory)",
        "function workbenchDecisionRadarConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockDecisionRadarConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioDecisionRadarConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchDecisionRadar(root, rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function renderStockDecisionRadar(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioDecisionRadar(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "Decision Radar",
        "Advanced Watchlist Radar",
        "Stock Snapshot Radar",
        "Portfolio Health Radar",
        "Custom Columns",
        "Quant Grades",
        "Concentration",
        "Heatmap",
        "Coverage Gaps",
        "Missing Info",
        "Earnings / Dividends / News",
        "Dividend Coverage",
        "Real-Time Alerts",
        "Ratings Coverage",
        "Open Radar",
        "Copy Radar",
        "Save Radar",
    ):
        assert label in js

    for data_attr in (
        "data-commercial-decision-radar-lane",
        "data-commercial-decision-radar-target",
        "data-commercial-decision-radar-copy",
        "data-commercial-decision-radar-save",
    ):
        assert data_attr in js
    assert "writeCommercialMemory(`decision-radar-${scope}`" in js
    assert "copyCommercialText(commercialDecisionRadarSummary(config, activeLane)" in js
    assert "renderWorkbenchDecisionRadar(document.getElementById('commercial-workbench-decision-radar')" in js
    assert "renderStockDecisionRadar(document.getElementById('commercial-stock-decision-radar')" in js
    assert "renderPortfolioDecisionRadar(document.getElementById('commercial-portfolio-decision-radar')" in js


def test_decision_radars_use_compact_mobile_data_strip_instead_of_tall_cards():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    radar = re.search(r"\.commercial-decision-radar \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert radar is not None
    assert "gap: 8px;" in radar.group("body")
    assert "padding: 8px;" in radar.group("body")

    copy = re.search(r"\.commercial-decision-radar-copy \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert copy is not None
    assert "padding: 8px;" in copy.group("body")

    copy_detail = re.search(r"\.commercial-decision-radar-copy em \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert copy_detail is not None
    assert "display: none;" in copy_detail.group("body")

    ring = re.search(r"\.commercial-decision-radar-ring \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert ring is not None
    assert "width: 60px;" in ring.group("body")
    assert "height: 60px;" in ring.group("body")

    lane = re.search(r"\.commercial-decision-radar-lane \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert lane is not None
    assert "width: 100%;" in lane.group("body")
    assert "min-width: 0;" in lane.group("body")
    assert "min-height: 44px;" in lane.group("body")

    radar_map = re.search(r"\.commercial-decision-radar-map \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert radar_map is not None
    assert "display: grid;" in radar_map.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in radar_map.group("body")
    assert "overflow-x: visible;" in radar_map.group("body")
    assert "padding-bottom: 0;" in radar_map.group("body")
    assert "min-height: 0;" in radar_map.group("body")

    tile = re.search(r"\.commercial-decision-radar-tile \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert tile is not None
    assert "width: 100%;" in tile.group("body")
    assert "min-width: 0;" in tile.group("body")
    assert "min-height: 62px;" in tile.group("body")
    assert "padding: 7px;" in tile.group("body")

    readout = re.search(r"\.commercial-decision-radar-readout \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert readout is not None
    assert "padding: 7px 8px;" in readout.group("body")

    readout_detail = re.search(r"\.commercial-decision-radar-readout em \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert readout_detail is not None
    assert "display: none;" in readout_detail.group("body")

    actions = re.search(r"\.commercial-decision-radar-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert actions is not None
    assert "display: grid;" in actions.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in actions.group("body")
    assert "overflow-x: visible;" in actions.group("body")
    assert "padding-bottom: 0;" in actions.group("body")


def test_decision_radars_use_compact_desktop_terminal_strip_to_keep_core_data_above_fold():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")

    radar = re.search(r"\.commercial-decision-radar \{(?P<body>.*?)\n\}", css, re.S)
    assert radar is not None
    radar_body = radar.group("body")
    assert "grid-template-columns: minmax(210px, 0.22fr) minmax(0, 1fr) minmax(220px, 0.24fr);" in radar_body
    assert "gap: 8px;" in radar_body
    assert "padding: 8px;" in radar_body
    assert "margin: 0 0 10px;" in radar_body

    copy_detail = re.search(r"\.commercial-decision-radar-copy em \{(?P<body>.*?)\n\}", css, re.S)
    assert copy_detail is not None
    assert "display: none;" in copy_detail.group("body")

    ring = re.search(r"\.commercial-decision-radar-ring \{(?P<body>.*?)\n\}", css, re.S)
    assert ring is not None
    assert "width: 58px;" in ring.group("body")
    assert "height: 58px;" in ring.group("body")

    body = re.search(r"\.commercial-decision-radar-body \{(?P<body>.*?)\n\}", css, re.S)
    assert body is not None
    assert "grid-template-columns: minmax(0, 0.58fr) minmax(0, 0.42fr);" in body.group("body")

    lane = re.search(r"\.commercial-decision-radar-lane \{(?P<body>.*?)\n\}", css, re.S)
    assert lane is not None
    assert "min-height: 58px;" in lane.group("body")
    assert "padding: 7px;" in lane.group("body")

    radar_map = re.search(r"\.commercial-decision-radar-map \{(?P<body>.*?)\n\}", css, re.S)
    assert radar_map is not None
    assert "min-height: 72px;" in radar_map.group("body")

    readout_rules = re.findall(r"\.commercial-decision-radar-readout \{(?P<body>.*?)\n\}", css, re.S)
    readout_body = next((body for body in readout_rules if "grid-column: 1 / -1;" in body), "")
    assert readout_body
    assert "grid-column: 1 / -1;" in readout_body
    assert "grid-template-columns: minmax(150px, 0.28fr) minmax(0, 1fr);" in readout_body

    readout_detail = re.search(r"\.commercial-decision-radar-readout em \{(?P<body>.*?)\n\}", css, re.S)
    assert readout_detail is not None
    assert "display: none;" in readout_detail.group("body")

    actions = re.search(r"\.commercial-decision-radar-actions \{(?P<body>.*?)\n\}", css, re.S)
    assert actions is not None
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in actions.group("body")


def test_commercial_pages_add_smart_alert_centers_for_market_monitoring():
    html_by_page = {
        "research-workbench.html": ("commercial-workbench-alert-center", "commercial-workbench-control-strip", "commercial-workbench-journey-palette"),
        "stock-detail.html": ("commercial-stock-alert-center", "commercial-stock-control-strip", "commercial-stock-journey-palette"),
        "portfolio-dashboard.html": ("commercial-portfolio-alert-center", "commercial-portfolio-control-strip", "commercial-portfolio-journey-palette"),
    }
    for filename, (center_id, before_id, after_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{center_id}"') == 1
        assert html.index(f'id="{before_id}"') < html.index(f'id="{center_id}"') < html.index(f'id="{after_id}"')
        for other_id, *_ in [value for key, value in html_by_page.items() if key != filename]:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-smart-alert-center",
        ".commercial-smart-alert-copy",
        ".commercial-smart-alert-grid",
        ".commercial-smart-alert",
        ".commercial-smart-alert.is-active",
        ".commercial-smart-alert.is-warning",
        ".commercial-smart-alert-settings",
        ".commercial-smart-alert-actions",
        ".commercial-smart-alert-action",
        ".commercial-smart-alert-status",
    ):
        assert selector in css
    for function_name in (
        "function commercialSmartAlertPreference(scope, fallbackAlert)",
        "function commercialSmartAlertCsv(config, activeAlert)",
        "function renderCommercialSmartAlertCenter(root, config, activeAlert)",
        "function bindCommercialSmartAlertCenter(root, scope, configFactory)",
        "function commercialSmartAlert(id, label, status, detail, target, trigger, channel)",
        "function workbenchSmartAlertCenterConfig(rows, activeTicker, activeView, currentFilter)",
        "function stockSmartAlertCenterConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioSmartAlertCenterConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
        "function renderWorkbenchSmartAlertCenter(root, rows, activeTicker, activeView, currentFilter)",
        "function renderStockSmartAlertCenter(root, snapshot, currentTab, activeScenario, activeCoverage)",
        "function renderPortfolioSmartAlertCenter(root, payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js
    for label in (
        "警示中心",
        "追蹤表警示中心",
        "單股警示中心",
        "投組警示中心",
        "價格警示",
        "估值警示",
        "新聞/公告警示",
        "技術面警示",
        "財報警示",
        "風險漂移警示",
        "集中度警示",
        "再平衡警示",
        "客戶回顧警示",
        "通知通道",
        "桌面",
        "信箱",
        "手機推播",
        "啟用警示",
        "延後警示",
        "匯出警示",
    ):
        assert label in js
    assert "writeCommercialMemory(`smart-alert-center-${scope}`" in js
    assert "data-commercial-smart-alert-choice" in js
    assert "data-commercial-smart-alert-target" in js
    assert "data-commercial-smart-alert-arm" in js
    assert "data-commercial-smart-alert-snooze" in js
    assert "data-commercial-smart-alert-export" in js
    assert "renderWorkbenchSmartAlertCenter(document.getElementById('commercial-workbench-alert-center')" in js
    assert "renderStockSmartAlertCenter(document.getElementById('commercial-stock-alert-center')" in js
    assert "renderPortfolioSmartAlertCenter(document.getElementById('commercial-portfolio-alert-center')" in js


def test_smart_alert_centers_keep_mobile_alert_actions_accessible():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-smart-alert-center" in mobile_css
    assert ".commercial-smart-alert-grid" in mobile_css
    assert ".commercial-smart-alert" in mobile_css
    assert ".commercial-smart-alert-action" in mobile_css
    assert "min-height: 44px;" in mobile_css
    smart_grid = re.search(r"\.commercial-smart-alert-grid \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert smart_grid is not None
    assert "display: grid;" in smart_grid.group("body")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in smart_grid.group("body")
    assert "overflow-x: visible;" in smart_grid.group("body")
    smart_actions = re.search(r"\.commercial-smart-alert-actions \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert smart_actions is not None
    assert "display: grid;" in smart_actions.group("body")
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in smart_actions.group("body")
    assert "overflow-x: visible;" in smart_actions.group("body")
    assert "aria-label=\"警示中心\"" in js
    assert "role=\"status\"" in js
    assert "commercialSmartAlertCsv(config, activeAlert)" in js


def test_smart_alert_centers_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    function_pairs = (
        ("commercialSmartAlertCsv", "renderCommercialSmartAlertCenter"),
        ("renderCommercialSmartAlertCenter", "bindCommercialSmartAlertCenter"),
        ("bindCommercialSmartAlertCenter", "workbenchSmartAlertCenterConfig"),
        ("workbenchSmartAlertCenterConfig", "stockSmartAlertCenterConfig"),
        ("stockSmartAlertCenterConfig", "portfolioSmartAlertCenterConfig"),
        ("portfolioSmartAlertCenterConfig", "renderWorkbenchSmartAlertCenter"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "警示中心",
        "追蹤表警示中心",
        "單股警示中心",
        "投組警示中心",
        "價格警示",
        "估值警示",
        "新聞/公告警示",
        "技術面警示",
        "財報警示",
        "風險漂移警示",
        "集中度警示",
        "再平衡警示",
        "客戶回顧警示",
        "通知通道",
        "桌面",
        "信箱",
        "手機推播",
        "啟用警示",
        "延後警示",
        "匯出警示",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Smart Alert Center",
        "Watchlist Alert Center",
        "Stock Alert Center",
        "Portfolio Alert Center",
        "Price Alert",
        "Valuation Alert",
        "News & Filings Alert",
        "Technical Alert",
        "Earnings Alert",
        "Risk Drift Alert",
        "Concentration Alert",
        "Rebalance Alert",
        "Client Review Alert",
        "Channel",
        "Desktop",
        "Email",
        "Mobile Push",
        "Arm Alert",
        "Snooze Alert",
        "Export Alerts",
    ):
        assert legacy_label not in product_layer


def test_primary_workspaces_explain_page_specific_information_coverage():
    html_by_page = {
        "research-workbench.html": (
            "commercial-three-column",
            "commercial-workbench-workspace-command",
            "commercial-workbench-coverage-strip",
            "commercial-workbench-list",
            "追蹤表資訊覆蓋導覽",
        ),
        "stock-detail.html": (
            "commercial-stock-layout",
            "commercial-stock-workspace-command",
            "commercial-stock-coverage-strip",
            "commercial-stock-tabs",
            "單股資訊覆蓋導覽",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-layout",
            "commercial-portfolio-workspace-command",
            "commercial-portfolio-coverage-strip",
            "commercial-portfolio-csv",
            "組合資訊覆蓋導覽",
        ),
    }

    for filename, (layout_class, command_id, strip_id, next_anchor_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{strip_id}"') == 1
        assert f'id="{strip_id}" class="commercial-coverage-strip"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'class="{layout_class}"') < html.index(f'id="{command_id}"') < html.index(f'id="{strip_id}"') < html.index(f'id="{next_anchor_id}"')

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-coverage-strip",
        ".commercial-coverage-copy",
        ".commercial-coverage-track",
        ".commercial-coverage-item",
        ".commercial-coverage-item.is-covered",
        ".commercial-coverage-item.is-watch",
        ".commercial-coverage-actions",
        ".commercial-coverage-action",
        ".commercial-coverage-status",
    ):
        assert selector in css

    assert "@media (max-width: 1180px)" in css
    tablet_css = css.split("@media (max-width: 1180px)", 1)[1]
    assert ".commercial-three-column > .commercial-coverage-strip" in tablet_css
    assert ".commercial-stock-layout > .commercial-coverage-strip" in tablet_css
    assert ".commercial-portfolio-layout > .commercial-coverage-strip" in tablet_css
    assert "grid-template-columns: minmax(0, 1fr);" in tablet_css

    for function_name in (
        "function commercialCoverageItem(label, status, detail, target, tone = '')",
        "function renderCommercialCoverageStrip(root, config)",
        "function bindCommercialCoverageStrip(root)",
        "function workbenchCoverageStripConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockCoverageStripConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioCoverageStripConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for text in (
        "Watchlist Coverage",
        "Stock Data Coverage",
        "Portfolio Coverage",
        "Price",
        "Financials",
        "Performance",
        "Risk",
        "Technicals",
        "Earnings",
        "News",
        "Ownership",
        "ETF Exposure",
        "Transcripts",
        "Holdings",
        "Benchmark",
        "Contribution",
        "Rebalance",
        "Client Pack",
    ):
        assert text in js

    assert "data-commercial-coverage-target" in js
    assert "data-commercial-coverage-status" in js
    assert "renderCommercialCoverageStrip(document.getElementById('commercial-workbench-coverage-strip'), workbenchCoverageStripConfig" in js
    assert "renderCommercialCoverageStrip(document.getElementById('commercial-stock-coverage-strip'), stockCoverageStripConfig" in js
    assert "renderCommercialCoverageStrip(document.getElementById('commercial-portfolio-coverage-strip'), portfolioCoverageStripConfig" in js
    assert "bindCommercialCoverageStrip(document.getElementById('commercial-workbench-coverage-strip'))" in js
    assert "bindCommercialCoverageStrip(document.getElementById('commercial-stock-coverage-strip'))" in js
    assert "bindCommercialCoverageStrip(document.getElementById('commercial-portfolio-coverage-strip'))" in js


def test_workspace_coverage_click_feedback_survives_primary_panel_reveal():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    handler = re.search(
        r"function bindCommercialCoverageStrip\(root\) \{(?P<body>.*?)\n    \}",
        js,
        re.S,
    )
    assert handler is not None
    body = handler.group("body")
    assert "if (target) scrollCommercialTaskTarget(target);" in body
    assert body.index("if (target) scrollCommercialTaskTarget(target);") < body.index("const output = root.querySelector('.commercial-coverage-status');")
    assert "Opened ${status}" in body


def test_primary_workspaces_show_page_specific_delivery_readiness():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-coverage-strip",
            "commercial-workbench-readiness-strip",
            "commercial-workbench-list",
            "追蹤表交付狀態導覽",
        ),
        "stock-detail.html": (
            "commercial-stock-coverage-strip",
            "commercial-stock-readiness-strip",
            "commercial-stock-tabs",
            "單股研究狀態導覽",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-coverage-strip",
            "commercial-portfolio-readiness-strip",
            "commercial-portfolio-csv",
            "組合回顧狀態導覽",
        ),
    }

    for filename, (coverage_id, readiness_id, next_anchor_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{readiness_id}"') == 1
        assert f'id="{readiness_id}" class="commercial-workflow-readiness"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{coverage_id}"') < html.index(f'id="{readiness_id}"') < html.index(f'id="{next_anchor_id}"')

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-workflow-readiness",
        ".commercial-workflow-readiness-copy",
        ".commercial-workflow-readiness-meter",
        ".commercial-workflow-readiness-track",
        ".commercial-workflow-readiness-step",
        ".commercial-workflow-readiness-step.is-complete",
        ".commercial-workflow-readiness-step.is-active",
        ".commercial-workflow-readiness-actions",
        ".commercial-workflow-readiness-action",
        ".commercial-workflow-readiness-status",
    ):
        assert selector in css

    assert "@media (max-width: 1180px)" in css
    tablet_css = css.split("@media (max-width: 1180px)", 1)[1]
    assert ".commercial-three-column > .commercial-workflow-readiness" in tablet_css
    assert ".commercial-stock-layout > .commercial-workflow-readiness" in tablet_css
    assert ".commercial-portfolio-layout > .commercial-workflow-readiness" in tablet_css

    for function_name in (
        "function commercialWorkflowReadinessStep(id, label, status, detail, target, complete = false, tone = '')",
        "function renderCommercialWorkflowReadiness(root, config)",
        "function bindCommercialWorkflowReadiness(root)",
        "function workbenchWorkflowReadinessConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockWorkflowReadinessConfig(snapshot, currentTab, activeScenario, activeCoverage)",
        "function portfolioWorkflowReadinessConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for text in (
        "追蹤表交付準備度",
        "單股研究準備度",
        "投組回顧準備度",
        "掃描隊列",
        "打開快照",
        "報告重跑",
        "匯出報告包",
        "報價檢查",
        "估值情境",
        "財報催化",
        "持股複查",
        "研究報告包",
        "持股已載入",
        "基準差異",
        "風險漂移",
        "再平衡單",
        "客戶報告包",
    ):
        assert text in js

    assert "data-commercial-readiness-target" in js
    assert "data-commercial-readiness-copy" in js
    assert "renderCommercialWorkflowReadiness(document.getElementById('commercial-workbench-readiness-strip'), workbenchWorkflowReadinessConfig" in js
    assert "renderCommercialWorkflowReadiness(document.getElementById('commercial-stock-readiness-strip'), stockWorkflowReadinessConfig" in js
    assert "renderCommercialWorkflowReadiness(document.getElementById('commercial-portfolio-readiness-strip'), portfolioWorkflowReadinessConfig" in js
    assert "bindCommercialWorkflowReadiness(document.getElementById('commercial-workbench-readiness-strip'))" in js
    assert "bindCommercialWorkflowReadiness(document.getElementById('commercial-stock-readiness-strip'))" in js
    assert "bindCommercialWorkflowReadiness(document.getElementById('commercial-portfolio-readiness-strip'))" in js


def test_workflow_readiness_strips_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    function_pairs = (
        ("commercialWorkflowReadinessSummary", "renderCommercialWorkflowReadiness"),
        ("renderCommercialWorkflowReadiness", "bindCommercialWorkflowReadiness"),
        ("bindCommercialWorkflowReadiness", "workbenchWorkflowReadinessConfig"),
        ("workbenchWorkflowReadinessConfig", "stockWorkflowReadinessConfig"),
        ("stockWorkflowReadinessConfig", "portfolioWorkflowReadinessConfig"),
        ("portfolioWorkflowReadinessConfig", "commercialPrimarySnapshotMetric"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "工作流準備度",
        "準備度",
        "下一步",
        "追蹤表交付準備度",
        "單股研究準備度",
        "投組回顧準備度",
        "掃描隊列",
        "打開快照",
        "報告重跑",
        "匯出報告包",
        "報價檢查",
        "估值情境",
        "財報催化",
        "持股複查",
        "研究報告包",
        "持股已載入",
        "基準差異",
        "風險漂移",
        "再平衡單",
        "客戶報告包",
        "打開下一步",
        "複製檢查清單",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Workflow Readiness",
        "Watchlist Delivery Readiness",
        "Stock Research Readiness",
        "Portfolio Review Readiness",
        "Scan Queue",
        "Open Snapshot",
        "Report Rerun",
        "Export Pack",
        "Quote Check",
        "Valuation Case",
        "Earnings Catalyst",
        "Ownership Review",
        "Research Pack",
        "Holdings Loaded",
        "Benchmark Delta",
        "Risk Drift",
        "Rebalance Ticket",
        "Client Pack",
        "Open Next Step",
        "Copy Checklist",
        "Readiness checklist copied",
        "Readiness:",
        "Next Step:",
        "Context:",
        "[ready]",
        "[next]",
        "Ready for review",
        "Next:",
        "Opened ",
    ):
        assert legacy_label not in product_layer


def test_primary_workspaces_pin_page_specific_snapshot_docks_before_users_hunt():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-readiness-strip",
            "commercial-workbench-primary-snapshot",
            "commercial-workbench-list",
            "追蹤表快速快照",
        ),
        "stock-detail.html": (
            "commercial-stock-readiness-strip",
            "commercial-stock-primary-snapshot",
            "commercial-stock-tabs",
            "單股快速快照",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-readiness-strip",
            "commercial-portfolio-primary-snapshot",
            "commercial-portfolio-csv",
            "組合快速快照",
        ),
    }

    for filename, (readiness_id, dock_id, next_anchor_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{dock_id}"') == 1
        assert f'id="{dock_id}" class="commercial-primary-snapshot-dock"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{dock_id}"') < html.index(f'id="{readiness_id}"') < html.index(f'id="{next_anchor_id}"')
        for other_id in set(value[1] for value in html_by_page.values()) - {dock_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-primary-snapshot-dock",
        ".commercial-primary-snapshot-copy",
        ".commercial-primary-snapshot-quote",
        ".commercial-primary-snapshot-metrics",
        ".commercial-primary-snapshot-metric",
        ".commercial-primary-snapshot-metric.is-positive",
        ".commercial-primary-snapshot-metric.is-warning",
        ".commercial-primary-snapshot-actions",
        ".commercial-primary-snapshot-action",
        ".commercial-primary-snapshot-action.is-primary",
        ".commercial-primary-snapshot-status",
    ):
        assert selector in css

    assert ".commercial-three-column > .commercial-primary-snapshot-dock" in css
    assert ".commercial-stock-layout > .commercial-primary-snapshot-dock" in css
    assert ".commercial-portfolio-layout > .commercial-primary-snapshot-dock" in css
    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-primary-snapshot-dock" in mobile_css
    assert ".commercial-primary-snapshot-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    for function_name in (
        "function commercialPrimarySnapshotMetric(label, value, detail, target, tone = '')",
        "function commercialPrimarySnapshotAction(id, label, target, primary = false)",
        "function renderCommercialPrimarySnapshotDock(root, config)",
        "function bindCommercialPrimarySnapshotDock(root)",
        "function workbenchPrimarySnapshotConfig(row, snapshot, rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockPrimarySnapshotConfig(snapshot, currentTab, activeScenario, activeRange, activeCoverage)",
        "function portfolioPrimarySnapshotConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "今日追蹤決策",
        "個股快照決策",
        "投組健康檢查",
        "待處理股票",
        "警示/重跑",
        "選取快照",
        "報告交付",
        "即時價格",
        "價格動能",
        "估值空間",
        "資料新鮮度",
        "財報/事件",
        "健康分數",
        "最大持股",
        "模型漂移",
        "風險旗標",
        "打開快照",
        "整理報告",
        "查看警示",
        "看財務估值",
        "整理研究包",
        "看 X-Ray",
        "開再平衡單",
        "整理客戶包",
    ):
        assert label in js

    for required in (
        "data-commercial-primary-snapshot-target",
        "data-commercial-primary-snapshot-status",
        "data-commercial-primary-snapshot-action",
        "renderCommercialPrimarySnapshotDock(document.getElementById('commercial-workbench-primary-snapshot'), workbenchPrimarySnapshotConfig",
        "renderCommercialPrimarySnapshotDock(document.getElementById('commercial-stock-primary-snapshot'), stockPrimarySnapshotConfig",
        "renderCommercialPrimarySnapshotDock(document.getElementById('commercial-portfolio-primary-snapshot'), portfolioPrimarySnapshotConfig",
        "bindCommercialPrimarySnapshotDock(document.getElementById('commercial-workbench-primary-snapshot'))",
        "bindCommercialPrimarySnapshotDock(document.getElementById('commercial-stock-primary-snapshot'))",
        "bindCommercialPrimarySnapshotDock(document.getElementById('commercial-portfolio-primary-snapshot'))",
    ):
        assert required in js


def test_primary_snapshots_use_page_specific_user_workflow_language():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    workbench = re.search(
        r"function workbenchPrimarySnapshotConfig\(.*?\) \{(?P<body>.*?)\n    function stockPrimarySnapshotConfig",
        js,
        re.S,
    )
    stock = re.search(
        r"function stockPrimarySnapshotConfig\(.*?\) \{(?P<body>.*?)\n    function portfolioPrimarySnapshotConfig",
        js,
        re.S,
    )
    portfolio = re.search(
        r"function portfolioPrimarySnapshotConfig\(.*?\) \{(?P<body>.*?)\n    function commercialPrimaryCompareMetric",
        js,
        re.S,
    )
    assert workbench is not None
    assert stock is not None
    assert portfolio is not None

    workbench_body = workbench.group("body")
    assert "eyebrow: '追蹤表日流程'" in workbench_body
    assert "title: '今日追蹤決策'" in workbench_body
    assert "activeColumnSet === 'event' ? '事件欄位' : activeColumnSet === 'fundamental' ? '基本面欄位' : '決策欄位'" in workbench_body
    assert "Number.isFinite(returnValue) ? `建議後 ${pct(returnValue)}` : '報告包就緒'" in workbench_body
    assert "commercialPrimarySnapshotMetric('待處理股票'" in workbench_body
    assert "commercialPrimarySnapshotMetric('警示/重跑'" in workbench_body
    assert "commercialPrimarySnapshotMetric('選取快照'" in workbench_body
    assert "commercialPrimarySnapshotMetric('報告交付'" in workbench_body
    assert "Active Watchlist Snapshot" not in workbench_body
    assert "eyebrow: 'Watchlist Daily Flow'" not in workbench_body
    assert "ready for report pack" not in workbench_body

    stock_body = stock.group("body")
    assert "eyebrow: '單股研究流程'" in stock_body
    assert "title: '個股快照決策'" in stock_body
    assert "const qualityStatus = snapshot?.data_quality?.status === 'fresh' ? '資料新鮮' : (snapshot?.data_quality?.status || '來源準備度');" in stock_body
    assert "event.days_until !== undefined ? `${event.days_until} 天` : '查看催化事件'" in stock_body
    assert "commercialPrimarySnapshotMetric('價格動能'" in stock_body
    assert "commercialPrimarySnapshotMetric('估值空間'" in stock_body
    assert "commercialPrimarySnapshotMetric('資料新鮮度'" in stock_body
    assert "commercialPrimarySnapshotMetric('財報/事件'" in stock_body
    assert "Stock Snapshot Dock" not in stock_body
    assert "eyebrow: 'Single Stock Flow'" not in stock_body
    assert "latest market session" not in stock_body
    assert "review catalyst queue" not in stock_body

    portfolio_body = portfolio.group("body")
    assert "eyebrow: '投組風險規則'" in portfolio_body
    assert "title: '投組健康檢查'" in portfolio_body
    assert "const modelLabel = commercialPortfolioModelLabel(model.label || activeTargetModel || 'balanced');" in portfolio_body
    assert "flags.length ? `${flags.length} 項風險` : '無重大旗標'" in portfolio_body
    assert "`模型上限 ${model.maxPosition || 35}%`" in portfolio_body
    assert "commercialPrimarySnapshotMetric('健康分數'" in portfolio_body
    assert "commercialPrimarySnapshotMetric('最大持股', shortTicker(top.ticker || ticker), modelLabel" in portfolio_body
    assert "commercialPrimarySnapshotMetric('模型漂移'" in portfolio_body
    assert "commercialPrimarySnapshotMetric('風險旗標'" in portfolio_body
    assert "Portfolio Snapshot Dock" not in portfolio_body
    assert "eyebrow: 'Portfolio Guardrails'" not in portfolio_body
    assert "risk flags" not in portfolio_body


def test_mobile_and_desktop_shortcuts_use_page_specific_customer_task_language():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    workbench_mobile = re.search(
        r"function workbenchMobileActionBarConfig\(.*?\) \{(?P<body>.*?)\n    function stockMobileActionBarConfig",
        js,
        re.S,
    )
    stock_mobile = re.search(
        r"function stockMobileActionBarConfig\(.*?\) \{(?P<body>.*?)\n    function portfolioMobileActionBarConfig",
        js,
        re.S,
    )
    portfolio_mobile = re.search(
        r"function portfolioMobileActionBarConfig\(.*?\) \{(?P<body>.*?)\n    function commercialDesktopInsightAction",
        js,
        re.S,
    )
    workbench_desktop = re.search(
        r"function workbenchDesktopInsightRailConfig\(.*?\) \{(?P<body>.*?)\n    function stockDesktopInsightRailConfig",
        js,
        re.S,
    )
    stock_desktop = re.search(
        r"function stockDesktopInsightRailConfig\(.*?\) \{(?P<body>.*?)\n    function portfolioDesktopInsightRailConfig",
        js,
        re.S,
    )
    portfolio_desktop = re.search(
        r"function portfolioDesktopInsightRailConfig\(.*?\) \{(?P<body>.*?)\n    function commercialShouldIgnoreKeyboardShortcut",
        js,
        re.S,
    )
    assert workbench_mobile is not None
    assert stock_mobile is not None
    assert portfolio_mobile is not None
    assert workbench_desktop is not None
    assert stock_desktop is not None
    assert portfolio_desktop is not None

    for label in ("決策", "事件", "報告", "快照", "警示", "報告包"):
        assert label in workbench_mobile.group("body")
    for label in ("評級", "財報", "股利", "快照", "價格提醒", "研究包"):
        assert label in stock_mobile.group("body")
    for label in ("風險", "再平衡", "稅務", "客戶包"):
        assert label in portfolio_mobile.group("body")

    for label in ("決策隊列", "新聞/公告", "報告包", "打開快照", "進階表格", "警示"):
        assert label in workbench_desktop.group("body")
    for label in ("評級變動", "財報觀察", "股利/因子", "打開快照", "估值", "價格提醒", "研究報告"):
        assert label in stock_desktop.group("body")
    for label in ("風險旗標", "再平衡單", "稅務/收入", "曝險", "客戶包"):
        assert label in portfolio_desktop.group("body")


def test_above_fold_decision_strips_do_not_expose_internal_english_workflow_terms():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    function_pairs = (
        ("workbenchPrimaryCompareConfig", "stockPrimaryCompareConfig"),
        ("stockPrimaryCompareConfig", "portfolioPrimaryCompareConfig"),
        ("portfolioPrimaryCompareConfig", "commercialPrimaryAnswerItem"),
        ("workbenchPrimaryAnswerConfig", "stockPrimaryAnswerConfig"),
        ("stockPrimaryAnswerConfig", "portfolioPrimaryAnswerConfig"),
        ("portfolioPrimaryAnswerConfig", "commercialPrimaryCustomizeItem"),
        ("workbenchPrimaryCustomizeConfig", "stockPrimaryCustomizeConfig"),
        ("stockPrimaryCustomizeConfig", "portfolioPrimaryCustomizeConfig"),
        ("portfolioPrimaryCustomizeConfig", "workbenchWorkspaceCommandBarConfig"),
        ("workbenchMobileActionBarConfig", "stockMobileActionBarConfig"),
        ("stockMobileActionBarConfig", "portfolioMobileActionBarConfig"),
        ("portfolioMobileActionBarConfig", "commercialDesktopInsightAction"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    visible_decision_surface = "\n".join(bodies)

    for legacy_label in (
        "Action Answer",
        "Watchlist Decision Answer",
        "Stock Research Answer",
        "Portfolio Answer",
        "Portfolio Action Answer",
        "Compare After Snapshot",
        "Watchlist Relative Lens",
        "Peer Benchmark Lens",
        "Portfolio Benchmark Lens",
        "Relative Return",
        "Watchlist Leader",
        "Alert Peer",
        "Column View",
        "Peer Median",
        "Valuation Gap",
        "Factor Rank",
        "Estimate Trend",
        "Benchmark Delta",
        "Top Overweight",
        "Risk Drift",
        "Target Model",
        "Open Compare",
        "Open Heatmap",
        "Open Table",
        "Open Peer Matrix",
        "Open Valuation",
        "Open Financials",
        "Open Benchmark",
        "Open Risk",
        "Open Rebalance",
        "Custom Watchlist",
        "Watchlist Custom View",
        "Stock Research Workspace",
        "Portfolio Setup",
        "Portfolio Review Workspace",
        "Customize Columns",
        "Set Alerts",
        "Share Watchlist",
        "Customize Research",
        "Set Price Alert",
        "Share Report",
        "Customize Dashboard",
        "Set Guardrails",
        "Share Client Pack",
        "Watchlist Mobile Priority",
        "Stock Mobile Priority",
        "Portfolio Mobile Priority",
        "Balanced",
    ):
        assert legacy_label not in visible_decision_surface


def test_first_workspace_layer_uses_customer_language_instead_of_internal_english():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    function_pairs = (
        ("commercialCoreSurfaceVisualCaption", "commercialCoreSurfaceVisual"),
        ("renderCommercialCoreSurface", "bindCommercialCoreSurface"),
        ("workbenchCoreSurfaceConfig", "stockCoreSurfaceConfig"),
        ("stockCoreSurfaceConfig", "portfolioCoreSurfaceConfig"),
        ("portfolioCoreSurfaceConfig", "renderWorkbenchCoreSurface"),
        ("renderCommercialJumpDeck", "workbenchJumpDeck"),
        ("workbenchJumpDeck", "stockJumpDeck"),
        ("stockJumpDeck", "portfolioJumpDeck"),
        ("portfolioJumpDeck", "renderCommercialPriorityStrip"),
        ("workbenchWorkspaceCommandBarConfig", "stockWorkspaceCommandBarConfig"),
        ("stockWorkspaceCommandBarConfig", "portfolioWorkspaceCommandBarConfig"),
        ("portfolioWorkspaceCommandBarConfig", "commercialCommandAttributes"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    first_workspace_layer = "\n".join(bodies)

    for required_label in (
        "追蹤表核心資料",
        "單股快照核心",
        "組合健康核心",
        "追蹤表命令地圖",
        "單股研究地圖",
        "組合透視地圖",
        "追蹤表隊列",
        "單股快照",
        "組合透視",
    ):
        assert required_label in first_workspace_layer

    for legacy_label in (
        "Core Surface",
        "Watchlist Core",
        "Stock Snapshot Core",
        "Portfolio Health Core",
        "Summary Rows",
        "Custom Columns",
        "Open Table",
        "Open Snapshot",
        "Open Financials",
        "Open Health",
        "Open Exposure",
        "Open Rebalance",
        "Watchlist Command Map",
        "Stock Research Map",
        "Portfolio X-Ray Map",
        "Snapshot Path",
        "Catalyst Path",
        "Report Path",
        "Health Path",
        "Warnings Path",
        "Rebalance Path",
        "Watchlist Queue",
        "Visible Rows",
        "Quote Range",
        "Financials",
        "Risk Flags",
        "Rebalance Ticket",
        "Client Pack",
        "Balanced model",
    ):
        assert legacy_label not in first_workspace_layer


def test_commercial_visible_text_translation_layer_covers_page_specific_competitor_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for required in (
        "const COMMERCIAL_VISIBLE_TEXT_REPLACEMENTS = {",
        "const COMMERCIAL_VISIBLE_ONLY_REPLACEMENTS = {",
        "const COMMERCIAL_VISIBLE_TEXT_SELECTORS = [",
        "function commercialUiText(value)",
        "function commercialVisibleText(value)",
        "function translateCommercialVisibleText(root = document.body)",
        "function installCommercialVisibleTextObserver(root = document.body)",
        "return String(commercialUiText(value) ?? '').replace",
    ):
        assert required in js

    for english, chinese in (
        ("Watchlist Brief", "追蹤表摘要"),
        ("Stock Memo", "單股研究摘要"),
        ("Portfolio Review", "投組回顧摘要"),
        ("Advanced View", "進階欄位視圖"),
        ("Quant Factor Grades", "量化因子評級"),
        ("Holdings Analytics", "持股分析"),
        ("Technical Pulse", "技術面脈搏"),
        ("Disclosure Digest", "資訊揭露摘要"),
        ("Visual Pulse", "視覺脈搏"),
        ("Action Dock", "快速動作台"),
        ("Today Inbox", "今日通知匣"),
        ("Share Brief", "分享摘要"),
        ("Competitive Lens", "競品級鏡頭"),
        ("Decision Automation", "決策自動化"),
        ("Decision Radar", "決策雷達"),
        ("Open Snapshot", "打開快照"),
        ("Set Price Alert", "設定價格提醒"),
        ("Rebalance Plan", "再平衡計畫"),
        ("Tax Appendix", "稅務附錄"),
        ("CSV Export", "匯出 CSV"),
        ("Watchlist Market Brief", "追蹤表市場摘要"),
        ("Watchlist Brief Composer", "追蹤表摘要編輯器"),
        ("Watchlist Decision Queue", "追蹤表決策隊列"),
        ("Stock Market Brief", "單股市場摘要"),
        ("Stock Valuation Simulator", "單股估值模擬器"),
        ("Stock Tax Lot & Dividend Center", "單股稅務與股息中心"),
        ("Portfolio Market Brief", "投組市場摘要"),
        ("Portfolio Contribution Analysis", "投組貢獻分析"),
        ("Portfolio Taxable Income Report", "投組應稅收益報告"),
        ("Portfolio Rebalance Simulator", "投組再平衡模擬器"),
        ("Save Disclosure Digest", "儲存揭露摘要"),
        ("Build Report", "建立報告"),
        ("Workspace Autosave", "工作區自動保存"),
        ("Watchlist Monitor Center", "追蹤表監控中心"),
        ("Research Report Builder", "研究報告建立器"),
        ("Client Portfolio Pack", "客戶投組包"),
        ("Position Ledger", "部位帳本"),
        ("Performance Attribution", "績效歸因"),
        ("Tax & Income Center", "稅務與收益中心"),
        ("Market Regime Overlay", "市場環境疊圖"),
        ("Analyst Target Range", "分析師目標價區間"),
        ("Portfolio Health Score", "投組健康分數"),
    ):
        assert f'"{english}": "{chinese}"' in js

    for english, chinese in (
        ("all", "全部"),
        ("valuation", "估值"),
        ("fundamental", "基本面"),
        ("conviction", "信心"),
        ("base", "基準"),
    ):
        assert f'"{english}": "{chinese}"' in js

    for selector in (
        ".commercial-action-title",
        ".commercial-panel-header strong",
        ".commercial-control-action",
        ".commercial-intelligence-copy > span",
        ".commercial-memory-copy > span",
        ".commercial-delivery-copy > span",
    ):
        assert f'"{selector}"' in js

    for raw_heading in (
        "commercialUiText('Technical Pulse')",
        "commercialUiText('Disclosure Digest')",
        "commercialUiText('Visual Pulse')",
        "commercialUiText('Action Dock')",
        "commercialUiText('Today Inbox')",
        "commercialUiText('Share Brief')",
        "commercialUiText('Competitive Lens')",
        "commercialUiText('Decision Automation')",
        "commercialUiText('Decision Radar')",
    ):
        assert raw_heading in js

    assert "installCommercialVisibleTextObserver(scope)" in js
    assert "translateCommercialVisibleText(scope)" in js


def test_workbench_ticker_click_focuses_snapshot_without_manual_scrolling():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    assert "async function selectTicker(ticker, rows, shouldFocusSnapshot = false)" in js
    assert "function focusWorkbenchSnapshot()" in js
    assert "if (!shouldFocusSnapshot) return;" in js
    assert "scrollCommercialTaskTarget('commercial-workbench-detail', { behavior: 'auto' })" in js
    assert "if (shouldFocusSnapshot) focusWorkbenchSnapshot();" in js


def test_report_and_market_coverage_layers_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    function_pairs = (
        ("commercialReportLocatorSummary", "renderCommercialReportLocator"),
        ("renderCommercialReportLocator", "bindCommercialReportLocator"),
        ("bindCommercialReportLocator", "workbenchReportLocatorConfig"),
        ("workbenchReportLocatorConfig", "stockReportLocatorConfig"),
        ("stockReportLocatorConfig", "portfolioReportLocatorConfig"),
        ("portfolioReportLocatorConfig", "renderWorkbenchReportLocator"),
        ("commercialMarketCoverageSummary", "renderCommercialMarketCoverage"),
        ("renderCommercialMarketCoverage", "bindCommercialMarketCoverage"),
        ("bindCommercialMarketCoverage", "workbenchMarketCoverageConfig"),
        ("workbenchMarketCoverageConfig", "stockMarketCoverageConfig"),
        ("stockMarketCoverageConfig", "portfolioMarketCoverageConfig"),
        ("portfolioMarketCoverageConfig", "renderWorkbenchMarketCoverage"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "報告定位",
        "追蹤表報告隊列",
        "單股 AI 報告定位",
        "投組客戶回顧包",
        "批次報告",
        "報告包",
        "證據包",
        "交付列",
        "報告產生器",
        "催化事件筆記",
        "再平衡單",
        "資訊覆蓋",
        "追蹤表覆蓋",
        "單股研究覆蓋",
        "投組健康覆蓋",
        "可點追蹤表",
        "進階欄位",
        "追蹤表新聞",
        "即時警示",
        "未覆蓋資料",
        "法人/ETF 持有",
        "券商同步",
        "績效追蹤",
        "再平衡計畫",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Report Locator",
        "Watchlist Report Queue",
        "AI Report Locator",
        "Client Review Pack",
        "Batch Reports",
        "Report Pack",
        "Evidence Pack",
        "Delivery Bar",
        "Report Builder",
        "Catalyst Note",
        "Rebalance Ticket",
        "Market Coverage",
        "Watchlist Coverage",
        "Equity Research Coverage",
        "Portfolio Health Coverage",
        "Clickable Watchlist",
        "Advanced Columns",
        "Watchlist News",
        "Real-Time Alerts",
        "Missing Coverage",
        "Ownership & ETFs",
        "Broker Sync",
        "Performance Tracking",
        "Rebalance Plan",
        "Open Report Locator",
        "Copy Report Locator",
        "Save Report Locator",
        "Open Table",
        "Open News",
        "Open Alerts",
        "Open Snapshot",
        "Open Financials",
        "Open Ownership",
        "Open Health",
        "Open Rebalance",
        "Copy Coverage",
    ):
        assert legacy_label not in product_layer


def test_sync_alert_and_view_layers_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    function_pairs = (
        ("commercialDataBeaconSummary", "renderCommercialDataBeacon"),
        ("renderCommercialDataBeacon", "bindCommercialDataBeacon"),
        ("bindCommercialDataBeacon", "workbenchDataBeaconConfig"),
        ("workbenchDataBeaconConfig", "stockDataBeaconConfig"),
        ("stockDataBeaconConfig", "portfolioDataBeaconConfig"),
        ("portfolioDataBeaconConfig", "renderWorkbenchDataBeacon"),
        ("commercialAlertBeaconSummary", "renderCommercialAlertBeacon"),
        ("renderCommercialAlertBeacon", "bindCommercialAlertBeacon"),
        ("bindCommercialAlertBeacon", "workbenchAlertBeaconConfig"),
        ("workbenchAlertBeaconConfig", "stockAlertBeaconConfig"),
        ("stockAlertBeaconConfig", "portfolioAlertBeaconConfig"),
        ("portfolioAlertBeaconConfig", "renderWorkbenchAlertBeacon"),
        ("commercialViewRailSummary", "renderCommercialViewRail"),
        ("renderCommercialViewRail", "bindCommercialViewRail"),
        ("bindCommercialViewRail", "workbenchViewRailConfig"),
        ("workbenchViewRailConfig", "stockViewRailConfig"),
        ("stockViewRailConfig", "portfolioViewRailConfig"),
        ("portfolioViewRailConfig", "renderWorkbenchViewRail"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "資料同步",
        "追蹤表來源健康",
        "單股來源健康",
        "投組帳戶健康",
        "決策 API",
        "報價新鮮度",
        "券商連結",
        "來源品質",
        "警示中心",
        "追蹤表警示台",
        "單股警示台",
        "投組風險警示台",
        "追蹤表警示",
        "價格警示",
        "評級警示",
        "投組警示",
        "視角切換",
        "一鍵模式",
        "進階頁籤",
        "已存視圖",
        "總覽",
        "財報",
        "股利",
        "新聞",
        "財務",
        "評級",
        "催化事件",
        "基準",
        "再平衡",
        "客戶包",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Data Sync Beacon",
        "Watchlist Source Health",
        "Stock Source Health",
        "Portfolio Account Health",
        "Quote Freshness",
        "Broker Link",
        "Source Quality",
        "Open Data Sync",
        "Copy Data Sync",
        "Save Data Sync",
        "Alert Beacon",
        "Watchlist Alert Console",
        "Stock Alert Console",
        "Portfolio Warning Console",
        "Watchlist Alerts",
        "Price Alerts",
        "Rating Alerts",
        "Portfolio Alerts",
        "Open Alerts",
        "Copy Alerts",
        "Save Alerts",
        "View Rail",
        "One-Tap Mode",
        "Advanced Tabs",
        "Saved Views",
        "Overview",
        "Earnings",
        "Dividends",
        "News",
        "Financials",
        "Ratings",
        "Catalysts",
        "Benchmark",
        "Rebalance",
        "Client Pack",
    ):
        assert legacy_label not in product_layer


def test_signal_preset_and_coverage_layers_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    function_pairs = (
        ("commercialSignalTapeSummary", "renderCommercialSignalTape"),
        ("renderCommercialSignalTape", "bindCommercialSignalTape"),
        ("bindCommercialSignalTape", "workbenchSignalTapeConfig"),
        ("workbenchSignalTapeConfig", "stockSignalTapeConfig"),
        ("stockSignalTapeConfig", "portfolioSignalTapeConfig"),
        ("portfolioSignalTapeConfig", "renderWorkbenchSignalTape"),
        ("commercialPresetBeaconSummary", "renderCommercialPresetBeacon"),
        ("renderCommercialPresetBeacon", "bindCommercialPresetBeacon"),
        ("bindCommercialPresetBeacon", "workbenchPresetBeaconConfig"),
        ("workbenchPresetBeaconConfig", "stockPresetBeaconConfig"),
        ("stockPresetBeaconConfig", "portfolioPresetBeaconConfig"),
        ("portfolioPresetBeaconConfig", "renderWorkbenchPresetBeacon"),
        ("commercialCoverageMatrixCsv", "coverageTone"),
        ("renderCommercialCoverageMatrix", "bindCommercialCoverageMatrix"),
        ("bindCommercialCoverageMatrix", "workbenchCoverageMatrixConfig"),
        ("workbenchCoverageMatrixConfig", "stockCoverageMatrixConfig"),
        ("stockCoverageMatrixConfig", "portfolioCoverageMatrixConfig"),
        ("portfolioCoverageMatrixConfig", "renderWorkbenchCoverageMatrix"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "訊號帶",
        "追蹤表訊號",
        "單股訊號",
        "投組訊號",
        "即時警示",
        "新聞流",
        "量化評級",
        "目標變化",
        "視圖預設",
        "追蹤表視圖預設",
        "單股研究預設",
        "投組回顧預設",
        "自訂欄位",
        "儀表板預設",
        "客戶回顧",
        "覆蓋矩陣",
        "追蹤表覆蓋",
        "單股研究覆蓋",
        "投組 X-Ray 覆蓋",
        "分析師評級",
        "資產配置",
        "全球區域",
        "打開覆蓋",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Signal Tape",
        "Watchlist Signals",
        "Stock Signals",
        "Portfolio Signals",
        "Real-Time Alerts",
        "News Flow",
        "Quant Rating",
        "Target Change",
        "Portfolio Warnings",
        "Exposure Drift",
        "Top Weight",
        "Rebalance Status",
        "Open News",
        "Open Rebalance",
        "Copy Brief",
        "Preset Beacon",
        "Watchlist View Presets",
        "Stock Research Presets",
        "Portfolio Review Presets",
        "Custom Columns",
        "Research Mode",
        "Dashboard Presets",
        "Client Review",
        "Open Preset",
        "Copy Preset",
        "Save Preset",
        "Market Coverage Matrix",
        "Stock Research Coverage",
        "Portfolio X-Ray Coverage",
        "Analyst Ratings",
        "Asset Allocation",
        "World Regions",
        "Open Coverage",
        "Save Coverage",
        "Export Coverage",
    ):
        assert legacy_label not in product_layer


def test_primary_workspaces_add_competitor_style_compare_lenses_after_snapshot():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-primary-snapshot",
            "commercial-workbench-primary-compare",
            "commercial-workbench-list",
            "追蹤表比較焦點",
        ),
        "stock-detail.html": (
            "commercial-stock-primary-snapshot",
            "commercial-stock-primary-compare",
            "commercial-stock-tabs",
            "單股同業比較焦點",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-primary-snapshot",
            "commercial-portfolio-primary-compare",
            "commercial-portfolio-csv",
            "組合基準比較焦點",
        ),
    }

    for filename, (snapshot_id, compare_id, next_anchor_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{compare_id}"') == 1
        assert f'id="{compare_id}" class="commercial-primary-compare-lens"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{snapshot_id}"') < html.index(f'id="{compare_id}"') < html.index(f'id="{next_anchor_id}"')
        for other_id in set(value[1] for value in html_by_page.values()) - {compare_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-primary-compare-lens",
        ".commercial-primary-compare-copy",
        ".commercial-primary-compare-score",
        ".commercial-primary-compare-grid",
        ".commercial-primary-compare-metric",
        ".commercial-primary-compare-metric.is-positive",
        ".commercial-primary-compare-metric.is-warning",
        ".commercial-primary-compare-bar",
        ".commercial-primary-compare-actions",
        ".commercial-primary-compare-action",
        ".commercial-primary-compare-action.is-primary",
        ".commercial-primary-compare-status",
    ):
        assert selector in css

    assert ".commercial-three-column > .commercial-primary-compare-lens" in css
    assert ".commercial-stock-layout > .commercial-primary-compare-lens" in css
    assert ".commercial-portfolio-layout > .commercial-primary-compare-lens" in css
    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-primary-compare-lens" in mobile_css
    assert ".commercial-primary-compare-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    for function_name in (
        "function commercialPrimaryCompareMetric(label, value, detail, target, level = 50, tone = '')",
        "function commercialPrimaryCompareAction(id, label, target, primary = false)",
        "function renderCommercialPrimaryCompareLens(root, config)",
        "function bindCommercialPrimaryCompareLens(root)",
        "function workbenchPrimaryCompareConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockPrimaryCompareConfig(snapshot, currentTab, activeScenario, activeRange, activeCoverage)",
        "function portfolioPrimaryCompareConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "追蹤表相對比較",
        "同業基準鏡頭",
        "組合基準鏡頭",
        "相對報酬",
        "清單領先",
        "警示同類",
        "欄位視圖",
        "同業中位",
        "估值差距",
        "因子排名",
        "預估趨勢",
        "基準差距",
        "最大超配",
        "風險漂移",
        "目標模型",
        "打開比較",
        "打開熱區圖",
        "打開表格",
        "打開同業矩陣",
        "打開估值",
        "打開財務",
        "打開基準",
        "打開風險",
        "打開再平衡",
    ):
        assert label in js

    for required in (
        "data-commercial-primary-compare-target",
        "data-commercial-primary-compare-status",
        "data-commercial-primary-compare-action",
        "renderCommercialPrimaryCompareLens(document.getElementById('commercial-workbench-primary-compare'), workbenchPrimaryCompareConfig",
        "renderCommercialPrimaryCompareLens(document.getElementById('commercial-stock-primary-compare'), stockPrimaryCompareConfig",
        "renderCommercialPrimaryCompareLens(document.getElementById('commercial-portfolio-primary-compare'), portfolioPrimaryCompareConfig",
        "bindCommercialPrimaryCompareLens(document.getElementById('commercial-workbench-primary-compare'))",
        "bindCommercialPrimaryCompareLens(document.getElementById('commercial-stock-primary-compare'))",
        "bindCommercialPrimaryCompareLens(document.getElementById('commercial-portfolio-primary-compare'))",
    ):
        assert required in js


def test_primary_workspaces_show_plain_language_action_answers_right_after_snapshot():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-primary-snapshot",
            "commercial-workbench-primary-answer",
            "commercial-workbench-primary-compare",
            "commercial-workbench-list",
            "追蹤表決策答案",
        ),
        "stock-detail.html": (
            "commercial-stock-primary-snapshot",
            "commercial-stock-primary-answer",
            "commercial-stock-primary-compare",
            "commercial-stock-tabs",
            "單股研究決策答案",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-primary-snapshot",
            "commercial-portfolio-primary-answer",
            "commercial-portfolio-primary-compare",
            "commercial-portfolio-csv",
            "組合健檢決策答案",
        ),
    }

    for filename, (snapshot_id, answer_id, compare_id, next_anchor_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{answer_id}"') == 1
        assert f'id="{answer_id}" class="commercial-primary-answer-strip"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{snapshot_id}"') < html.index(f'id="{answer_id}"') < html.index(f'id="{compare_id}"') < html.index(f'id="{next_anchor_id}"')
        for other_id in set(value[1] for value in html_by_page.values()) - {answer_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-primary-answer-strip",
        ".commercial-primary-answer-copy",
        ".commercial-primary-answer-verdict",
        ".commercial-primary-answer-grid",
        ".commercial-primary-answer-item",
        ".commercial-primary-answer-item.is-positive",
        ".commercial-primary-answer-item.is-warning",
        ".commercial-primary-answer-actions",
        ".commercial-primary-answer-action",
        ".commercial-primary-answer-action.is-primary",
        ".commercial-primary-answer-status",
    ):
        assert selector in css

    assert ".commercial-three-column > .commercial-primary-answer-strip" in css
    assert ".commercial-stock-layout > .commercial-primary-answer-strip" in css
    assert ".commercial-portfolio-layout > .commercial-primary-answer-strip" in css
    assert "@media (max-width: 560px)" in css
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-primary-answer-strip" in mobile_css
    assert ".commercial-primary-answer-action" in mobile_css
    assert "min-height: 44px;" in mobile_css

    for function_name in (
        "function commercialPrimaryAnswerItem(label, value, detail, target, tone = '')",
        "function commercialPrimaryAnswerAction(id, label, target, primary = false)",
        "function renderCommercialPrimaryAnswerStrip(root, config)",
        "function bindCommercialPrimaryAnswerStrip(root)",
        "function workbenchPrimaryAnswerConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockPrimaryAnswerConfig(snapshot, currentTab, activeScenario, activeRange, activeCoverage)",
        "function portfolioPrimaryAnswerConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "追蹤表決策答案",
        "單股研究答案",
        "組合行動答案",
        "決策",
        "分流隊列",
        "報告包",
        "匯出欄位",
        "估值",
        "催化事件",
        "證據包",
        "行動",
        "風險",
        "漂移",
        "客戶包",
        "打開快照",
        "檢視警示",
        "建立報告包",
        "匯出 CSV",
        "打開報告",
        "打開財務",
        "打開事件",
        "打開再平衡",
        "打開風險",
        "打開客戶包",
    ):
        assert label in js

    for required in (
        "data-commercial-primary-answer-target",
        "data-commercial-primary-answer-status",
        "data-commercial-primary-answer-action",
        "renderCommercialPrimaryAnswerStrip(document.getElementById('commercial-workbench-primary-answer'), workbenchPrimaryAnswerConfig",
        "renderCommercialPrimaryAnswerStrip(document.getElementById('commercial-stock-primary-answer'), stockPrimaryAnswerConfig",
        "renderCommercialPrimaryAnswerStrip(document.getElementById('commercial-portfolio-primary-answer'), portfolioPrimaryAnswerConfig",
        "bindCommercialPrimaryAnswerStrip(document.getElementById('commercial-workbench-primary-answer'))",
        "bindCommercialPrimaryAnswerStrip(document.getElementById('commercial-stock-primary-answer'))",
        "bindCommercialPrimaryAnswerStrip(document.getElementById('commercial-portfolio-primary-answer'))",
    ):
        assert required in js


def test_primary_workspaces_add_page_specific_customization_strips_after_compare():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-primary-snapshot",
            "commercial-workbench-primary-answer",
            "commercial-workbench-primary-compare",
            "commercial-workbench-primary-customize",
            "commercial-workbench-jump-deck",
            "追蹤表自訂視圖",
        ),
        "stock-detail.html": (
            "commercial-stock-primary-snapshot",
            "commercial-stock-primary-answer",
            "commercial-stock-primary-compare",
            "commercial-stock-primary-customize",
            "commercial-stock-jump-deck",
            "單股自訂研究視圖",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-primary-snapshot",
            "commercial-portfolio-primary-answer",
            "commercial-portfolio-primary-compare",
            "commercial-portfolio-primary-customize",
            "commercial-portfolio-jump-deck",
            "組合自訂健檢視圖",
        ),
    }

    for filename, (snapshot_id, answer_id, compare_id, customize_id, jump_id, aria_label) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count(f'id="{customize_id}"') == 1
        assert f'id="{customize_id}" class="commercial-primary-customize-strip"' in html
        assert f'aria-label="{aria_label}"' in html
        assert html.index(f'id="{snapshot_id}"') < html.index(f'id="{answer_id}"') < html.index(f'id="{compare_id}"') < html.index(f'id="{customize_id}"') < html.index(f'id="{jump_id}"')
        for other_id in set(value[3] for value in html_by_page.values()) - {customize_id}:
            assert f'id="{other_id}"' not in html

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-primary-customize-strip",
        ".commercial-primary-customize-copy",
        ".commercial-primary-customize-grid",
        ".commercial-primary-customize-item",
        ".commercial-primary-customize-item.is-positive",
        ".commercial-primary-customize-item.is-warning",
        ".commercial-primary-customize-actions",
        ".commercial-primary-customize-action",
        ".commercial-primary-customize-action.is-primary",
        ".commercial-primary-customize-status",
    ):
        assert selector in css

    assert ".commercial-three-column > .commercial-primary-customize-strip" in css
    assert ".commercial-stock-layout > .commercial-primary-customize-strip" in css
    assert ".commercial-portfolio-layout > .commercial-primary-customize-strip" in css
    assert ".commercial-shell > .commercial-primary-customize-strip" in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    for selector in (
        ".commercial-primary-customize-strip",
        ".commercial-primary-customize-action",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-copy em",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-item em",
    ):
        assert selector in mobile_css
    assert "min-height: 44px;" in mobile_css

    for selector in (
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-grid",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-actions",
    ):
        match = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", mobile_css, re.S)
        assert match is not None
        assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in match.group("body")

    shell_matches = re.findall(r"\.commercial-shell > \.commercial-primary-customize-strip \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert shell_matches
    assert any("gap: 6px;" in body and "padding: 6px;" in body for body in shell_matches)

    for function_name in (
        "function commercialPrimaryCustomizeItem(label, value, detail, target, tone = '')",
        "function commercialPrimaryCustomizeAction(id, label, target, primary = false)",
        "function renderCommercialPrimaryCustomizeStrip(root, config)",
        "function bindCommercialPrimaryCustomizeStrip(root)",
        "function workbenchPrimaryCustomizeConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockPrimaryCustomizeConfig(snapshot, currentTab, activeScenario, activeRange, activeCoverage)",
        "function portfolioPrimaryCustomizeConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for label in (
        "追蹤表自訂視圖",
        "單股研究工作區",
        "組合健檢工作區",
        "欄位",
        "警示",
        "分享視圖",
        "匯入清單",
        "研究版面",
        "警示預設",
        "報告模板",
        "同業組",
        "儀表板區塊",
        "守門規則",
        "客戶包",
        "目標模型",
        "自訂欄位",
        "設定警示",
        "分享追蹤表",
        "自訂研究",
        "設定價格提醒",
        "分享報告",
        "自訂儀表板",
        "設定守門規則",
        "分享客戶包",
    ):
        assert label in js

    for required in (
        "data-commercial-primary-customize-target",
        "data-commercial-primary-customize-status",
        "data-commercial-primary-customize-action",
        "commercial-primary-customize-action",
        "renderCommercialPrimaryCustomizeStrip(document.getElementById('commercial-workbench-primary-customize'), workbenchPrimaryCustomizeConfig",
        "renderCommercialPrimaryCustomizeStrip(document.getElementById('commercial-stock-primary-customize'), stockPrimaryCustomizeConfig",
        "renderCommercialPrimaryCustomizeStrip(document.getElementById('commercial-portfolio-primary-customize'), portfolioPrimaryCustomizeConfig",
        "bindCommercialPrimaryCustomizeStrip(document.getElementById('commercial-workbench-primary-customize'))",
        "bindCommercialPrimaryCustomizeStrip(document.getElementById('commercial-stock-primary-customize'))",
        "bindCommercialPrimaryCustomizeStrip(document.getElementById('commercial-portfolio-primary-customize'))",
        "'.commercial-primary-customize-strip'",
    ):
        assert required in js


def test_primary_customization_strips_include_competitor_style_live_monitor_rails():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-primary-monitor-rail",
        ".commercial-primary-monitor-signal",
        ".commercial-primary-monitor-signal.is-positive",
        ".commercial-primary-monitor-signal.is-warning",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    assert ".commercial-primary-monitor-rail" in mobile_css
    assert ".commercial-primary-monitor-signal" in mobile_css
    monitor_signal = re.search(r"\.commercial-primary-monitor-signal \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert monitor_signal is not None
    assert "min-height: 44px;" in monitor_signal.group("body")

    for function_name in (
        "function commercialPrimaryMonitorSignal(label, value, detail, target, tone = '')",
        "monitor: [",
    ):
        assert function_name in js

    for label in (
        "警示自動同步",
        "盤前盤後",
        "摘要隊列",
        "價格提醒",
        "評級提醒",
        "新聞摘要",
        "組合警示",
        "健康摘要",
        "自動報告",
    ):
        assert label in js

    for required in (
        "data-commercial-primary-monitor-target",
        "data-commercial-primary-monitor-status",
        "event.target.closest('[data-commercial-primary-customize-target], [data-commercial-primary-monitor-target]')",
    ):
        assert required in js


def test_primary_snapshot_compare_answer_are_not_buried_below_secondary_modules():
    html_by_page = {
        "research-workbench.html": (
            "commercial-workbench-primary-snapshot",
            "commercial-workbench-primary-compare",
            "commercial-workbench-primary-answer",
            "commercial-workbench-core-surface",
            "commercial-workbench-jump-deck",
        ),
        "stock-detail.html": (
            "commercial-stock-primary-snapshot",
            "commercial-stock-primary-compare",
            "commercial-stock-primary-answer",
            "commercial-stock-core-surface",
            "commercial-stock-jump-deck",
        ),
        "portfolio-dashboard.html": (
            "commercial-portfolio-primary-snapshot",
            "commercial-portfolio-primary-compare",
            "commercial-portfolio-primary-answer",
            "commercial-portfolio-core-surface",
            "commercial-portfolio-jump-deck",
        ),
    }

    for filename, (snapshot_id, compare_id, answer_id, secondary_anchor_id, top_tool_id) in html_by_page.items():
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.index(f'id="{snapshot_id}"') < html.index(f'id="{top_tool_id}"') < html.index('id="commercial-workspace-chrome"')
        assert html.index(f'id="{snapshot_id}"') < html.index(f'id="{answer_id}"') < html.index(f'id="{compare_id}"') < html.index(f'id="{secondary_anchor_id}"')

    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    primary_selector_block = re.search(r"function commercialPrimaryWorkflowSelectors\(\) \{\s*return \[(?P<body>.*?)\];", js, re.S)
    assert primary_selector_block is not None
    for selector in (
        "'.commercial-primary-snapshot-dock'",
        "'.commercial-primary-compare-lens'",
        "'.commercial-primary-answer-strip'",
        "'.commercial-primary-customize-strip'",
    ):
        assert selector in primary_selector_block.group("body")

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    for selector, order in (
        (".commercial-primary-snapshot-dock", "order: 2;"),
        (".commercial-primary-compare-lens", "order: 3;"),
        (".commercial-primary-answer-strip", "order: 4;"),
        (".commercial-primary-customize-strip", "order: 5;"),
    ):
        match = re.search(rf"(?m)^{re.escape(selector)} \{{(?P<body>.*?)\n\}}", css, re.S)
        assert match is not None
        assert order in match.group("body")

    assert ".commercial-shell > .commercial-primary-snapshot-dock" in css
    assert ".commercial-shell > .commercial-primary-compare-lens" in css
    assert ".commercial-shell > .commercial-primary-answer-strip" in css
    assert ".commercial-shell > .commercial-primary-customize-strip" in css
    shell_primary = re.search(r"\.commercial-shell > \.commercial-primary-snapshot-dock,(?P<body>.*?)\n\}", css, re.S)
    assert shell_primary is not None
    assert "order: 0;" in shell_primary.group("body")


def test_primary_mobile_shell_uses_compact_two_column_density():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-copy em",
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-quote em",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-copy em",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-verdict em",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-item em",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-copy em",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-copy em",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-item em",
    ):
        assert selector in mobile_css

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-metrics",
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-actions",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-grid",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-actions",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-grid",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-actions",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-grid",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-actions",
    ):
        match = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", mobile_css, re.S)
        assert match is not None
        assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in match.group("body")

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock",
        ".commercial-shell > .commercial-primary-answer-strip",
        ".commercial-shell > .commercial-primary-compare-lens",
        ".commercial-shell > .commercial-primary-customize-strip",
    ):
        matches = re.findall(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", mobile_css, re.S)
        assert matches
        assert any("gap: 6px;" in body and "padding: 6px;" in body for body in matches)


def test_primary_mobile_shell_uses_two_up_headers_to_reduce_scroll_depth():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    mobile_css = css.split("@media (max-width: 560px)", 1)[1]

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock",
        ".commercial-shell > .commercial-primary-answer-strip",
        ".commercial-shell > .commercial-primary-compare-lens",
        ".commercial-shell > .commercial-primary-customize-strip",
    ):
        matches = re.findall(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", mobile_css, re.S)
        assert matches
        assert any("grid-template-columns: repeat(2, minmax(0, 1fr));" in body for body in matches)

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-copy",
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-quote",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-copy",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-verdict",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-copy",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-score",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-copy",
    ):
        match = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", mobile_css, re.S)
        assert match is not None
        assert "min-height: 44px;" in match.group("body")

    for selector in (
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-metrics",
        ".commercial-shell > .commercial-primary-snapshot-dock .commercial-primary-snapshot-actions",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-grid",
        ".commercial-shell > .commercial-primary-answer-strip .commercial-primary-answer-actions",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-grid",
        ".commercial-shell > .commercial-primary-compare-lens .commercial-primary-compare-actions",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-grid",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-customize-actions",
        ".commercial-shell > .commercial-primary-customize-strip .commercial-primary-monitor-rail",
    ):
        match = re.search(rf"{re.escape(selector)} \{{(?P<body>.*?)\n  \}}", mobile_css, re.S)
        assert match is not None
        assert "grid-column: 1 / -1;" in match.group("body")


def test_mobile_action_bars_keep_page_specific_competitor_workflows_thumb_reachable():
    pages = {
        "research-workbench.html": (
            "快照",
            "警示",
            "報告包",
            "commercial-workbench-detail",
            "commercial-workbench-alert-builder",
            "commercial-workbench-report-pack",
        ),
        "stock-detail.html": (
            "快照",
            "價格提醒",
            "研究包",
            "commercial-stock-snapshot",
            "commercial-stock-thesis-alerts",
            "commercial-stock-report-builder",
        ),
        "portfolio-dashboard.html": (
            "風險",
            "再平衡",
            "客戶包",
            "commercial-portfolio-guardrails",
            "commercial-portfolio-rebalance-ticket",
            "commercial-portfolio-client-pack",
        ),
    }

    for filename in pages:
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count('id="commercial-mobile-action-bar"') == 1
        assert 'id="commercial-mobile-action-bar" class="commercial-mobile-action-bar"' in html
        assert 'aria-label="手機快速動作"' in html
        assert (
            html.index('id="commercial-workspace-chrome"')
            < html.index('id="commercial-mobile-action-bar"')
            < html.index("<main ")
        )

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-mobile-action-bar",
        ".commercial-mobile-action",
        ".commercial-mobile-action.is-primary",
        ".commercial-mobile-action-status",
    ):
        assert selector in css

    base_bar = re.search(r"\.commercial-mobile-action-bar \{(?P<body>.*?)\n\}", css, re.S)
    assert base_bar is not None
    assert "display: none;" in base_bar.group("body")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_bar = re.search(r"\.commercial-mobile-action-bar \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_bar is not None
    for expected_rule in (
        "position: fixed;",
        "left: 10px;",
        "right: 10px;",
        "bottom: max(10px, env(safe-area-inset-bottom));",
        "z-index: 80;",
        "display: grid;",
        "grid-template-columns: repeat(3, minmax(0, 1fr));",
    ):
        assert expected_rule in mobile_bar.group("body")

    mobile_main = re.search(r"\.commercial-main \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_main is not None
    assert "padding-bottom: 240px;" in mobile_main.group("body")

    mobile_action = re.search(r"\.commercial-mobile-action \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_action is not None
    assert "min-height: 44px;" in mobile_action.group("body")
    assert "touch-action: manipulation;" in mobile_action.group("body")

    for function_name in (
        "function commercialMobileAction(id, label, detail, target, primary = false)",
        "function renderCommercialMobileActionBar(root, config)",
        "function bindCommercialMobileActionBar(root)",
        "function workbenchMobileActionBarConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockMobileActionBarConfig(snapshot, currentTab, activeScenario, activeRange, activeCoverage)",
        "function portfolioMobileActionBarConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for filename, requirements in pages.items():
        for expected in requirements:
            assert expected in js

    for snippet in (
        "data-commercial-mobile-action-target",
        "data-commercial-mobile-action-status",
        "data-commercial-mobile-action-id",
        "commercial-mobile-action-status",
        "scrollCommercialTaskTarget(target)",
        "renderCommercialMobileActionBar(document.getElementById('commercial-mobile-action-bar'), workbenchMobileActionBarConfig",
        "renderCommercialMobileActionBar(document.getElementById('commercial-mobile-action-bar'), stockMobileActionBarConfig",
        "renderCommercialMobileActionBar(document.getElementById('commercial-mobile-action-bar'), portfolioMobileActionBarConfig",
        "bindCommercialMobileActionBar(document.getElementById('commercial-mobile-action-bar'))",
    ):
        assert snippet in js


def test_mobile_action_bars_add_page_specific_priority_tray_without_horizontal_scroll():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-mobile-priority-tray",
        ".commercial-mobile-priority-action",
        ".commercial-mobile-priority-action.is-warning",
        ".commercial-mobile-priority-action.is-positive",
    ):
        assert selector in css

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_bar = re.search(r"\.commercial-mobile-action-bar \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_bar is not None
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in mobile_bar.group("body")
    assert "overflow-x: clip;" in mobile_bar.group("body")

    priority_tray = re.search(r"\.commercial-mobile-priority-tray \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert priority_tray is not None
    priority_body = priority_tray.group("body")
    assert "grid-column: 1 / -1;" in priority_body
    assert "display: grid;" in priority_body
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in priority_body

    priority_action = re.search(r"\.commercial-mobile-priority-action \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert priority_action is not None
    priority_action_body = priority_action.group("body")
    assert "min-height: 44px;" in priority_action_body
    assert "touch-action: manipulation;" in priority_action_body
    assert "min-width: 0;" in priority_action_body

    mobile_main = re.search(r"\.commercial-main \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_main is not None
    assert "padding-bottom: 240px;" in mobile_main.group("body")

    for function_name in (
        "function commercialMobilePriorityAction(id, label, detail, target, tone = '')",
        "const priority = (config?.priority || []).slice(0, 3);",
    ):
        assert function_name in js

    for snippet in (
        "data-commercial-mobile-priority",
        "決策",
        "事件",
        "報告",
        "commercial-workbench-decision-queue",
        "commercial-workbench-event-queue",
        "commercial-workbench-report-pack",
        "評級",
        "財報",
        "股利",
        "commercial-stock-rating-alerts",
        "commercial-stock-earnings-panel",
        "commercial-stock-dividend-safety",
        "風險",
        "再平衡",
        "稅務",
        "commercial-portfolio-guardrails",
        "commercial-portfolio-drift-review",
        "commercial-portfolio-rebalance-ticket",
        "commercial-portfolio-tax-income",
    ):
        assert snippet in js

    assert "const modelLabel = commercialPortfolioModelLabel(model.label || activeTargetModel || 'balanced');" in js
    assert "commercialMobilePriorityAction('portfolio-mobile-rebalance', '再平衡', modelLabel, 'commercial-portfolio-drift-review')" in js


def test_desktop_insight_rails_keep_competitor_core_panels_persistent_without_mobile_clutter():
    pages = {
        "research-workbench.html": (
            "追蹤表命令面板",
            "選取股票",
            "可見列數",
            "警示隊列",
            "優先隊列",
            "打開快照",
            "進階表格",
            "警示",
            "報告包",
            "commercial-workbench-detail",
            "commercial-workbench-grid-lab",
            "commercial-workbench-alert-builder",
            "commercial-workbench-report-pack",
        ),
        "stock-detail.html": (
            "單股洞察面板",
            "股票代號",
            "目標上行",
            "下一事件",
            "優先隊列",
            "打開快照",
            "估值",
            "價格提醒",
            "研究報告",
            "commercial-stock-snapshot",
            "commercial-stock-valuation-band",
            "commercial-stock-thesis-alerts",
            "commercial-stock-report-builder",
        ),
        "portfolio-dashboard.html": (
            "投組洞察面板",
            "健康度",
            "風險旗標",
            "目標模型",
            "優先隊列",
            "風險",
            "再平衡",
            "曝險",
            "客戶包",
            "commercial-portfolio-guardrails",
            "commercial-portfolio-rebalance-ticket",
            "commercial-portfolio-exposure-map",
            "commercial-portfolio-client-pack",
        ),
    }

    for filename in pages:
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert html.count('id="commercial-desktop-insight-rail"') == 1
        assert 'id="commercial-desktop-insight-rail" class="commercial-desktop-insight-rail"' in html
        assert 'aria-label="桌面研究洞察捷徑"' in html
        assert (
            html.index('id="commercial-workspace-chrome"')
            < html.index('id="commercial-mobile-action-bar"')
            < html.index('id="commercial-desktop-insight-rail"')
            < html.index("<main ")
        )

    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-desktop-insight-rail",
        ".commercial-desktop-insight-copy",
        ".commercial-desktop-insight-actions",
        ".commercial-desktop-insight-action",
        ".commercial-desktop-insight-action.is-primary",
        ".commercial-desktop-insight-metrics",
        ".commercial-desktop-insight-metric",
        ".commercial-desktop-insight-status",
    ):
        assert selector in css

    base_rail = re.search(r"\.commercial-desktop-insight-rail \{(?P<body>.*?)\n\}", css, re.S)
    assert base_rail is not None
    assert "display: none;" in base_rail.group("body")

    assert "@media (min-width: 1180px)" in css
    desktop_css = css.split("@media (min-width: 1180px)", 1)[1].split("@media (max-width: 560px)", 1)[0]

    desktop_rail = re.search(r"\.commercial-desktop-insight-rail \{(?P<body>.*?)\n  \}", desktop_css, re.S)
    assert desktop_rail is not None
    for expected_rule in (
        "position: fixed;",
        "right: 16px;",
        "top: 104px;",
        "width: 212px;",
        "z-index: 60;",
        "display: grid;",
    ):
        assert expected_rule in desktop_rail.group("body")

    desktop_main = re.search(r"\.commercial-main \{(?P<body>.*?)\n  \}", desktop_css, re.S)
    assert desktop_main is not None
    assert "grid-column: 2 / 6;" in desktop_main.group("body")
    assert "grid-row: 5;" in desktop_main.group("body")
    assert "padding-right: 18px;" in desktop_main.group("body")

    desktop_action = re.search(r"\.commercial-desktop-insight-action \{(?P<body>.*?)\n  \}", desktop_css, re.S)
    assert desktop_action is not None
    assert "min-height: 44px;" in desktop_action.group("body")

    mobile_css = css.split("@media (max-width: 560px)", 1)[1]
    mobile_rail = re.search(r"\.commercial-desktop-insight-rail \{(?P<body>.*?)\n  \}", mobile_css, re.S)
    assert mobile_rail is not None
    assert "display: none;" in mobile_rail.group("body")

    for function_name in (
        "function commercialDesktopInsightAction(id, label, detail, target, primary = false)",
        "function commercialDesktopInsightMetric(label, value, detail, tone = '')",
        "function renderCommercialDesktopInsightRail(root, config)",
        "function bindCommercialDesktopInsightRail(root)",
        "function workbenchDesktopInsightRailConfig(rows, activeTicker, activeView, currentFilter, activeColumnSet)",
        "function stockDesktopInsightRailConfig(snapshot, currentTab, activeScenario, activeRange, activeCoverage)",
        "function portfolioDesktopInsightRailConfig(payload, portfolioContextTicker, activeLens, activeScenario, activeTargetModel)",
    ):
        assert function_name in js

    for requirements in pages.values():
        for expected in requirements:
            assert expected in js

    desktop_insight_bind = re.search(
        r"function bindCommercialDesktopInsightRail\(root\) \{(?P<body>.*?)\n    function workbenchDesktopInsightRailConfig",
        js,
        re.S,
    )
    assert desktop_insight_bind is not None
    assert "scrollCommercialTaskTarget(target, { behavior: 'auto' });" in desktop_insight_bind.group("body")

    for snippet in (
        "data-commercial-desktop-insight-target",
        "data-commercial-desktop-insight-status",
        "data-commercial-desktop-insight-action",
        "options.behavior ||",
        "renderCommercialDesktopInsightRail(document.getElementById('commercial-desktop-insight-rail'), workbenchDesktopInsightRailConfig",
        "renderCommercialDesktopInsightRail(document.getElementById('commercial-desktop-insight-rail'), stockDesktopInsightRailConfig",
        "renderCommercialDesktopInsightRail(document.getElementById('commercial-desktop-insight-rail'), portfolioDesktopInsightRailConfig",
        "bindCommercialDesktopInsightRail(document.getElementById('commercial-desktop-insight-rail'))",
    ):
        assert snippet in js


def test_desktop_insight_rails_add_page_specific_priority_queues_for_competitor_task_flow():
    css = (COMMERCIAL_DIR / "commercial_pages.css").read_text(encoding="utf-8")
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")

    for selector in (
        ".commercial-desktop-insight-queue",
        ".commercial-desktop-insight-queue-item",
        ".commercial-desktop-insight-queue-item.is-warning",
        ".commercial-desktop-insight-queue-item.is-positive",
    ):
        assert selector in css

    desktop_css = css.split("@media (min-width: 1180px)", 1)[1].split("@media (max-width: 560px)", 1)[0]
    desktop_queue = re.search(r"\.commercial-desktop-insight-queue \{(?P<body>.*?)\n  \}", desktop_css, re.S)
    assert desktop_queue is not None
    assert "display: grid;" in desktop_queue.group("body")
    assert "gap: 6px;" in desktop_queue.group("body")

    desktop_queue_item = re.search(r"\.commercial-desktop-insight-queue-item \{(?P<body>.*?)\n  \}", desktop_css, re.S)
    assert desktop_queue_item is not None
    assert "min-height: 44px;" in desktop_queue_item.group("body")

    for function_name in (
        "function commercialWorkbenchFilterLabel(label)",
        "function commercialDesktopInsightQueueItem(id, label, detail, target, tone = '')",
        "const queue = (config?.queue || []).slice(0, 3);",
    ):
        assert function_name in js

    for state_label in (
        "全部篩選",
        "警示篩選",
        "重跑篩選",
        "正報酬篩選",
        "commercialWorkbenchFilterLabel(currentFilter || 'all')",
        "commercialWorkbenchColumnSetLabel(activeColumnSet || activeView || 'decision')",
        "commercialLensLabel(currentTab || 'overview')",
        "commercialScenarioLabel(activeScenario || 'base')",
        "event.date || commercialLensLabel(activeCoverage || 'alerts')",
        "commercialLensLabel(activeCoverage || currentTab || 'quality')",
    ):
        assert state_label in js

    for snippet in (
        "data-commercial-desktop-insight-queue",
        "data-commercial-desktop-insight-target",
        "優先隊列",
        "決策隊列",
        "新聞/公告",
        "報告包",
        "commercial-workbench-decision-queue",
        "commercial-workbench-event-queue",
        "commercial-workbench-report-pack",
        "評級變動",
        "財報觀察",
        "股利/因子",
        "commercial-stock-rating-alerts",
        "commercial-stock-earnings-panel",
        "commercial-stock-dividend-safety",
        "風險旗標",
        "再平衡單",
        "稅務/收入",
        "commercial-portfolio-guardrails",
        "commercial-portfolio-rebalance-ticket",
        "commercial-portfolio-tax-income",
    ):
        assert snippet in js


def test_mobile_and_desktop_action_surfaces_use_customer_chinese_workflows():
    js = (COMMERCIAL_DIR / "commercial_pages.js").read_text(encoding="utf-8")
    function_pairs = (
        ("commercialMobileAction", "commercialMobilePriorityAction"),
        ("commercialMobilePriorityAction", "renderCommercialMobileActionBar"),
        ("renderCommercialMobileActionBar", "bindCommercialMobileActionBar"),
        ("bindCommercialMobileActionBar", "workbenchMobileActionBarConfig"),
        ("workbenchMobileActionBarConfig", "stockMobileActionBarConfig"),
        ("stockMobileActionBarConfig", "portfolioMobileActionBarConfig"),
        ("portfolioMobileActionBarConfig", "commercialDesktopInsightAction"),
        ("commercialDesktopInsightAction", "commercialDesktopInsightQueueItem"),
        ("commercialDesktopInsightQueueItem", "commercialDesktopInsightMetric"),
        ("commercialDesktopInsightMetric", "renderCommercialDesktopInsightRail"),
        ("renderCommercialDesktopInsightRail", "bindCommercialDesktopInsightRail"),
        ("bindCommercialDesktopInsightRail", "workbenchDesktopInsightRailConfig"),
        ("workbenchDesktopInsightRailConfig", "stockDesktopInsightRailConfig"),
        ("stockDesktopInsightRailConfig", "portfolioDesktopInsightRailConfig"),
        ("portfolioDesktopInsightRailConfig", "commercialShouldIgnoreKeyboardShortcut"),
    )
    bodies = []
    for function_name, next_function_name in function_pairs:
        match = re.search(
            rf"function {function_name}\(.*?\) \{{(?P<body>.*?)\n    function {next_function_name}",
            js,
            re.S,
        )
        assert match is not None
        bodies.append(match.group("body"))
    product_layer = "\n".join(bodies)

    for required_label in (
        "手機優先動作",
        "已打開",
        "追蹤表命令面板",
        "單股洞察面板",
        "投組洞察面板",
        "研究面板",
        "洞察面板",
        "優先隊列",
        "選取股票",
        "可見列數",
        "警示隊列",
        "股票代號",
        "目標上行",
        "下一事件",
        "健康度",
        "風險旗標",
        "目標模型",
        "打開快照",
        "進階表格",
        "價格提醒",
        "研究報告",
        "客戶包",
    ):
        assert required_label in product_layer

    for legacy_label in (
        "Mobile Priority",
        "Opened mobile action",
        "Insight Panel",
        "Research Panel",
        "Priority Queue",
        "Open panel",
        "Opened insight panel action",
        "Workbench command panel",
        "Watchlist Command Panel",
        "Stock Insight Panel",
        "Portfolio Insight Panel",
        "'Selected'",
        "'Visible Rows'",
        "'Alert Queue'",
        "'Ticker'",
        "'Upside'",
        "'Next Event'",
        "'Risk Flags'",
        "target pending",
        "inside guardrails",
        "watchlist triggers",
    ):
        assert legacy_label not in product_layer


def test_commercial_pages_hide_prototype_and_competitor_reference_copy_from_user_ui():
    commercial_files = [
        STATIC_DIR / "index.html",
        COMMERCIAL_DIR / "research-workbench.html",
        COMMERCIAL_DIR / "stock-detail.html",
        COMMERCIAL_DIR / "portfolio-dashboard.html",
        COMMERCIAL_DIR / "commercial_pages.js",
    ]

    forbidden_copy = (
        "Commercial layout review",
        "商業化前端方案",
        "商業版排版方案",
        "方案 A",
        "方案 B",
        "方案 C",
        "Stock Rover",
        "TradingView",
        "Koyfin",
        "Seeking Alpha",
        "Finviz",
        "Yahoo",
        "Morningstar",
        "style panel",
        "式 ",
    )

    for path in commercial_files:
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden_copy:
            if path.name == "index.html" and phrase == "式 ":
                continue
            assert phrase not in text, f"{phrase!r} leaked into {path.name}"

    for filename in ("research-workbench.html", "stock-detail.html", "portfolio-dashboard.html"):
        html = (COMMERCIAL_DIR / filename).read_text(encoding="utf-8")
        assert "<strong>OnStock AI</strong>" in html
        assert "<span>投資決策工作區</span>" in html
        assert 'aria-label="商業版投資工作區"' in html
        assert "研究工作台" in html or "單股研究" in html or "組合健檢" in html
