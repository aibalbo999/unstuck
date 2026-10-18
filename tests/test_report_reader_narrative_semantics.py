"""Self-contained, offline DOM checks for the reversible report reading layer."""

import hashlib
import json
import sqlite3
from copy import deepcopy
from html import escape

import pytest

from report_reader_assets import inject_reader, remove_reader


WAIT = "觀望（暫不建立新交易）"
NO_PRICE = "不適用（觀望中，暫不設定交易價位）"
MARKET = "市場情緒中性，技術指標中性；支撐位 NT$100.00，壓力位 NT$110.00。"
NARRATIVE = (
    "本次 1-2 週交易方向為「Neutral」，進場區間 N/A，目標價 N/A，嚴格停損 N/A。"
    + MARKET
)
LAYOUTS = {"v1": "research", "v2": "trading", "v3": "contrarian", "v4": "event-swing"}


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api", reason="Offline reader DOM tests require Playwright")
    with sync_api.sync_playwright() as playwright:
        instance = playwright.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    requests, errors = [], []

    def reject(route):
        requests.append(route.request.url)
        route.abort()

    context.route("**/*", reject)
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    context.close()
    assert not errors
    # Renderer assets are denied locally, never sent to a live service.
    assert all(not url.startswith("http://127.0.0.1") for url in requests)


def _load(page, html):
    page.set_content(html, wait_until="load")
    assert page.locator("body").get_attribute("data-reader-version") == "1"


def _fixture(body, *, mode="v4", direction="Neutral"):
    focus = (
        f"<dl><div><dt>交易方向</dt><dd>{escape(direction)}</dd></div>"
        "<div><dt>進場區間</dt><dd>N/A</dd></div>"
        "<div><dt>1-2 週目標</dt><dd>N/A</dd></div>"
        "<div><dt>嚴格停損</dt><dd>N/A</dd></div></dl>"
    ) if mode == "v4" else "<dl><div><dt>最終建議</dt><dd>持有</dd></div></dl>"
    return (
        '<!doctype html><html><body><main class="main" '
        f'data-report-layout="{LAYOUTS[mode]}"><div class="hero">'
        '<div class="hero-subtitle">2026-10-18</div>'
        '<div class="verdict-banner"><div class="verdict-label">研究評級</div>'
        '<div class="verdict-main">持有</div><div class="verdict-sub"></div></div>'
        f'<section class="mode-focus">{focus}</section></div>'
        f'<div class="executive-thesis"><p>{body}</p></div>'
        f'<div class="analysis-card"><p>{body}</p></div>'
        '<p class="report-reading-notice-note">品質 gate 未通過：原分析不可直接採用。</p>'
        '<script id="report-chart-data" type="application/json">'
        '{"prices":[100.00,null,0,-2.84]}</script></main></body></html>'
    )


def _context(mode):
    setup = {
        "trade_direction": "Neutral", "entry_zone": "N/A", "target_price": "N/A",
        "stop_loss": "N/A", "support_level": "NT$100.00",
        "resistance_level": "NT$110.00", "core_catalyst": "等待下一份財報",
        "risk_level": "High",
    }
    return {
        "ticker": "2330.TW", "company_name": "合成測試公司", "pipeline_id": mode,
        "data": {
            "ticker": "2330.TW", "company_name": "合成測試公司",
            "fetch_date": "2026-10-18", "current_price": 100.0,
            "current_price_fmt": "NT$100.00", "source_audit": [],
        },
        "parsed": {
            "recommendation": {"建議": "持有", "信心": "5/10"},
            "trade_setup": setup if mode == "v4" else {},
            "position_plan": {"action": "等待", "position_size": "0%"},
            "short_setup": {"entry_trigger": "不建立空方部位"},
        },
        "analyses": {24: "## 極短線交易計畫\n" + NARRATIVE} if mode == "v4" else {7: MARKET},
        "executive_thesis": NARRATIVE if mode == "v4" else MARKET,
        "final_audit": {"status": "blocked", "critical": ["合成品質警示，不得取消"], "warnings": []},
    }


def test_neutral_narrative_matches_decision_fields_before_any_source_changes(page):
    original = _fixture(NARRATIVE)
    html = inject_reader(original)
    assert remove_reader(html) == original
    _load(page, html)
    assert page.locator(".verdict-main").first.inner_text() == WAIT
    assert page.locator(".reader-facts").inner_text().count(NO_PRICE) == 3
    for selector in (".executive-thesis", ".reader-analysis"):
        observed = page.locator(selector).first.inner_text()
        assert f"交易方向為「{WAIT}」" in observed
        assert observed.count(NO_PRICE) == 3
        assert MARKET in observed
        assert "尚未提供" not in observed
    assert NARRATIVE in page.locator("#reader-audit").text_content()
    assert NARRATIVE in page.locator(".analysis-card > .reader-original").text_content()
    assert page.locator("#report-chart-data").text_content() == '{"prices":[100.00,null,0,-2.84]}'
    assert "原分析不可直接採用" in page.locator("body").inner_text()


@pytest.mark.parametrize("mode", LAYOUTS)
def test_generated_four_mode_reports_keep_mode_semantics_and_originals(page, mode):
    from reporting.html_renderer import generate_html_report

    context = _context(mode)
    before = deepcopy(context)
    html = generate_html_report(context)
    assert context == before
    _load(page, html)
    observed = page.locator(".executive-thesis").first.inner_text()
    assert MARKET in observed
    assert "合成品質警示，不得取消" in page.locator("body").text_content()
    if mode == "v4":
        assert WAIT in observed
        assert observed.count(NO_PRICE) == 3
        assert "Neutral" in remove_reader(html)
    else:
        assert WAIT not in observed
        assert NO_PRICE not in observed


@pytest.mark.parametrize("mode", LAYOUTS)
def test_existing_html_migration_is_reversible_and_preserves_data_and_quality(page, tmp_path, mode):
    from report_paths import report_storage_key_for_filename
    from report_reader_migration import migrate_report
    from storage.report_storage import LocalFileStorage

    storage = LocalFileStorage(tmp_path / "output")
    filename = f"2330_TW_{mode}_report_20261018_000000.html"
    key = report_storage_key_for_filename(filename)
    body = NARRATIVE if mode == "v4" else MARKET
    original = _fixture(body, mode=mode).encode()
    storage.save_report(key, original, content_type="text/html")
    snapshot = json.dumps({"data": {"ticker": "2330.TW", "target_price": None},
                           "analyses": {"24": body}, "content_credibility": {"status": "blocked"}}).encode()
    protected = {key.replace(".html", ".data.json"): snapshot,
                 key.replace(".html", ".md"): body.encode()}
    for name, content in protected.items():
        storage.save_report(name, content, content_type="application/json" if name.endswith(".json") else "text/markdown")
    db = tmp_path / "index.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE reports (output_dir TEXT, filename TEXT, html_hash TEXT, pipeline_id TEXT, data_trust_json TEXT, analysis_text_stale INTEGER)")
        conn.execute("INSERT INTO reports VALUES (?,?,?,?,?,?)", (
            str(storage._root), filename, hashlib.sha256(original).hexdigest(), mode,
            '{"status":"blocked"}', 1))
    mtime = (storage._root / key).stat().st_mtime_ns
    assert migrate_report(db, storage, filename, apply=True)["status"] == "updated"
    updated = storage.get_report(key).content.decode()
    assert remove_reader(updated).encode() == original
    assert (storage._root / key).stat().st_mtime_ns == mtime
    for name, content in protected.items():
        assert storage.get_report(name).content == content
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT data_trust_json,analysis_text_stale FROM reports").fetchone() == ('{"status":"blocked"}', 1)
    _load(page, updated)
    visible = page.locator(".executive-thesis").first.inner_text()
    assert MARKET in visible
    if mode == "v4":
        assert WAIT in visible and visible.count(NO_PRICE) == 3
    else:
        assert WAIT not in visible and NO_PRICE not in visible
    assert migrate_report(db, storage, filename, apply=True)["status"] == "unchanged"


@pytest.mark.parametrize("body", [
    "交易方向為 Neutral；進場區間 N/A，1-2 週目標 N/A，嚴格停損 N/A。",
    "交易方向是中性，進場價：N/A，目標價：資料不足，停損價：未提供。",
    "交易方向：「中性 Neutral」；進場區間為「N/A」，目標價是 N/A，停損點 N/A。",
    "交易方向：Neutral；進場區間：尚未提供（原報告未填此項，未記錄缺漏原因），目標價 N/A，嚴格停損 N/A。",
    "<strong>交易方向：</strong><span>Neutral</span>；<strong>進場區間：</strong><span>N/A</span>，<strong>目標價：</strong><span>N/A</span>，<strong>停損價：</strong><span>N/A</span>。",
])
def test_named_narrative_fields_support_legacy_punctuation_and_inline_markup(page, body):
    _load(page, inject_reader(_fixture(body)))
    visible = page.locator(".executive-thesis").first.inner_text()
    assert WAIT in visible
    assert visible.count(NO_PRICE) == 3
    assert "尚未提供" not in visible


@pytest.mark.parametrize("direction", ["Long", "Short", "N/A"])
def test_missing_direction_is_not_inferred_and_other_directions_remain(page, direction):
    body = f"交易方向為「{direction}」，進場區間 N/A。{MARKET}"
    _load(page, inject_reader(_fixture(body, direction=direction)))
    visible = page.locator(".executive-thesis").first.inner_text()
    assert WAIT not in visible
    assert NO_PRICE not in visible
    assert MARKET in visible


@pytest.mark.parametrize("mode", LAYOUTS)
def test_explicit_missing_causes_and_real_values_are_not_reclassified_by_observation(page, mode):
    body = (
        "交易方向為「Neutral」，進場區間：來源異常（HTTP 429，原件取得失敗），"
        "目標價：尚未確認（期間互有衝突，須核對），"
        "嚴格停損：尚未提供（原分析未記錄停損原因）。"
        "支撐位：不適用（原分析未使用支撐策略）。"
        "進場價 NT$100.00，目標價 110.50，停損價 0，部位大小 0%，現金流 -2.84。"
    )
    _load(page, inject_reader(_fixture(body, mode=mode)))
    visible = page.locator(".executive-thesis").first.inner_text()
    for phrase in (
        "來源異常（HTTP 429，原件取得失敗）", "尚未確認（期間互有衝突，須核對）",
        "尚未提供（原分析未記錄停損原因）", "不適用（原分析未使用支撐策略）",
        "進場價 NT$100.00，目標價 110.50，停損價 0，部位大小 0%，現金流 -2.84",
    ):
        assert phrase in visible
    assert NO_PRICE not in visible


def test_reader_second_run_does_not_duplicate_semantics(page):
    html = inject_reader(_fixture(NARRATIVE))
    _load(page, html)
    original = page.locator(".executive-thesis").first.inner_text()
    script = page.locator("#report-reader-script").text_content()
    page.evaluate(script)
    assert page.locator(".executive-thesis").first.inner_text() == original
    assert page.locator("#reader-brief").count() == 1


def test_five_year_financial_reference_is_not_described_as_individual_history(page):
    from test_annual_filing_reference import reference
    snapshot = {'data': {'ticker': '2892.TW', 'financial_currency': 'TWD'},
                '_reader_annual_cash_flow_review': {
                    'schema': 'official-annual-cash-flow-reference:v1', 'ticker': '2892.TW',
                    'year': 2025, 'annual_filing_reference': reference()}}
    _load(page, inject_reader(_fixture(MARKET, mode='v1'), snapshot=snapshot))
    limits = page.locator('.reader-limits').inner_text()
    assert '另存五年金融業原件可重播' in limits
    assert '另存個別原件可重播五年' not in limits
    assert '不證明可用一般企業方法估值' in limits
    assert '依各年申報範圍核對' in limits
    assert 'raw_response_path' not in limits


def test_saved_mode_d_executive_plan_and_conditional_return_use_plain_direction(page):
    body = (
        "合成公司（2330.TW）的 1-2 週交易計畫為「Neutral」，進場區間為 N/A，"
        "目標為 N/A，停損為 N/A。若催化失效或技術籌碼分歧，結論需回到 Neutral。"
        "風控邊界：若技術與籌碼互相衝突，需取消交易或回到 Neutral。"
    )
    _load(page, inject_reader(_fixture(body)))
    visible = page.locator(".executive-thesis").first.inner_text()
    assert f"交易計畫為「{WAIT}」" in visible
    assert visible.count(NO_PRICE) == 3
    assert f"結論需回到 {WAIT}" in visible
    assert f"取消交易或回到 {WAIT}" in visible
    assert "尚未提供" not in visible


@pytest.mark.parametrize("space", ["", " "])
def test_saved_mode_d_assumptions_do_not_wait_near_a_missing_price(page, space):
    body = (
        '<strong>交易方向仍由技術、籌碼與事件共同支持</strong>：'
        '目前方向為 中性 Neutral；若三者分歧，回到 Neutral（每日收盤後）</p><p>'
        '<strong>進場區間仍有效</strong>：'
        f'只在 N/A{space}附近等待觸發，不追價（盤中/收盤）</p><p>'
        '<strong>停損優先於目標價</strong>：停損條件：N/A（即時）'
    )
    _load(page, inject_reader(_fixture(body)))
    visible = page.locator(".executive-thesis").first.inner_text()
    assert f"目前方向為 {WAIT}" in visible
    assert f"回到 {WAIT}（每日收盤後）" in visible
    assert "只在" not in visible and "附近等待" not in visible
    assert "進場區間仍有效" not in visible
    assert visible.count(NO_PRICE) == 2
    assert "不追價（盤中/收盤）" in visible
    assert "（即時）" in visible
    assert "尚未提供" not in visible


def test_generic_neutral_and_nontrading_missing_goals_do_not_acquire_a_trade_direction(page):
    body = (
        "市場情緒中性；技術狀態為 Neutral；預期市場情緒回到 Neutral。"
        "年度營運目標為 N/A；產能目標 N/A。"
    )
    _load(page, inject_reader(_fixture(body)))
    visible = page.locator(".executive-thesis").first.inner_text()
    assert WAIT not in visible and NO_PRICE not in visible
    assert "市場情緒中性" in visible
    assert "技術狀態為 中性" in visible
    assert "市場情緒回到 中性" in visible


@pytest.mark.parametrize("prefix, expected", [
    ("資料不足", "尚未確認"),
    ("未確認", "尚未確認"),
    ("未提供", "尚未提供"),
])
@pytest.mark.parametrize("embedded", [False, True])
def test_recorded_missing_reason_is_not_erased_by_a_sentence_field(page, prefix, expected, embedded):
    body = ("交易方向為「Neutral」，" if embedded else "") + f"目標價：{prefix}，須取得同期間原件才能核對。"
    _load(page, inject_reader(_fixture(body)))
    visible = page.locator(".executive-thesis").first.inner_text()
    assert f"目標價：{expected}，須取得同期間原件才能核對" in visible
    assert NO_PRICE not in visible


@pytest.mark.parametrize("mode", LAYOUTS)
@pytest.mark.parametrize("saved, expected", [
    ("N/A（未評估；缺少同期間可驗證目標）", "尚未確認（缺少同期間可驗證目標）"),
    ("N/A（本次未重新估計）", "尚未確認（本次未重新估計）"),
    ("N/A（來源異常：HTTP429）", "來源異常（HTTP429）"),
])
def test_compound_na_preserves_its_recorded_cause_in_fields_and_narrative(page, mode, saved, expected):
    body = (
        f'目標價：{saved}，每股來回成本：{saved}。</p><p>'
        f'<strong>同期間目標：</strong><span>{saved}</span></p>'
        f'<table><tr><td>目標價</td><td>{saved}</td></tr></table><p>'
    )
    original = _fixture(body, mode=mode)
    html = inject_reader(original)
    assert remove_reader(html) == original
    _load(page, html)
    for selector in (".executive-thesis", ".reader-analysis"):
        visible = page.locator(selector).first.inner_text()
        assert visible.count(expected) == 4
        assert "N/A" not in visible
        assert "原報告未填此項，未記錄缺漏原因" not in visible
        assert NO_PRICE not in visible
    assert saved in page.locator("#reader-audit").text_content()
