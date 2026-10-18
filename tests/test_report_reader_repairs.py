"""Offline browser verification of the repaired report reading layer."""

from test_report_reader_narrative_semantics import browser, page, _fixture, _load
from test_report_financial_errata import snapshot
from report_reader_assets import inject_reader, remove_reader


def test_bound_amount_is_corrected_and_original_quality_and_chart_data_survive(page):
    line = "2025年營收為6.61億元。"
    original = _fixture(line, mode="v1")
    html = inject_reader(original, snapshot=snapshot(line))
    assert remove_reader(html) == original
    _load(page, html)
    assert "66.1億元" in page.locator(".reader-analysis").inner_text()
    assert "66.1億元" in page.locator(".executive-thesis").first.inner_text()
    assert "原文 6.61億元" in page.locator(".reader-financial-errata").inner_text()
    assert line in page.locator("#reader-audit").text_content()
    assert line in page.locator(".analysis-card > .reader-original").text_content()
    assert "原分析不可直接採用" in page.locator("body").inner_text()
    assert page.locator("#report-chart-data").text_content() == '{"prices":[100.00,null,0,-2.84]}'


def test_same_number_in_another_context_is_not_replaced(page):
    line = "2025年營收為6.61億元。"
    original = _fixture("預估2026年營收6.61億元，股價6.61元。", mode="v1")
    _load(page, inject_reader(original, snapshot=snapshot(line)))
    assert "預估2026年營收6.61億元，股價6.61元。" in page.locator(".reader-analysis").inner_text()


def test_bound_repeated_amounts_support_inline_markup_without_losing_links(page):
    text = '2025年自由現金流1.28億元（基於2025年淨利0.15億元與自由現金流1.28億元）。'
    body = '2025年自由現金流<strong>1.28</strong>億元（基於2025年淨利0.15億元與自由現金流1.28億元）。<a href="https://example.test/source">原件</a>'
    # The source-bound line includes the citation label too.
    saved = snapshot(text + '[原件](https://example.test/source)')
    original = _fixture(body, mode='v1')
    _load(page, inject_reader(original, snapshot=saved))
    observed = page.locator('.reader-analysis').inner_text()
    assert observed.count('12.8億元') == 2
    assert '淨利1.5億元' in observed
    assert page.locator('.reader-analysis a[href="https://example.test/source"]').count() == 1


def test_unassessed_management_old_html_has_reason_without_false_score(page):
    saved = {"rerun_context": {"structured_outputs": {"20": {
        "guidance_tone": "資料不足", "confidence": 0.0, "highlights": [],
        "analysis_markdown": "法說會逐字稿缺漏，無法可靠判斷。"}}}}
    original = _fixture("保留分析", mode="v1").replace('</main>',
        '<section id="management-sentiment"><p class="section-lead">Guidance 語氣：資料不足，信心 0%</p></section></main>')
    _load(page, inject_reader(original, snapshot=saved))
    lead = page.locator("#management-sentiment .section-lead")
    assert "逐字稿" in lead.inner_text()
    assert "0%" not in lead.inner_text()
    assert "信心 0%" in page.locator("#reader-audit").text_content()


def test_secondary_limits_collapse_but_stale_warning_and_print_details_remain(page):
    saved = {"data": {"source_audit": []}, "refreshed_without_analysis_rerun": True}
    rows = ''.join(f'<tr><td>來源{i}</td><td>P</td><td><span class="audit-status audit-status-error">error</span></td><td>2026-10-18</td><td></td><td></td><td></td><td></td><td>逾時{i}</td></tr>' for i in range(20))
    original = _fixture("原分析", mode="v1").replace('</main>',
        f'<table class="source-audit-table"><tbody>{rows}</tbody></table></main>')
    _load(page, inject_reader(original, snapshot=saved))
    assert "原分析尚未重跑" in page.locator("#reader-limits > ul").inner_text()
    details = page.locator(".reader-limit-details")
    assert details.get_attribute("open") is None
    assert len(page.locator("#reader-limits > ul > li").all()) <= 4
    assert page.locator("#reader-limits li").count() >= 21
    assert sum(f"逾時{i}" in item for i in range(20) for item in page.locator("#reader-limits li").all_text_contents()) >= 20
    details.locator("summary").click()
    assert "逾時19" in details.inner_text()
    details.locator("summary").click()
    page.emulate_media(media="print")
    assert details.locator("ul").is_visible()


def test_unknown_chart_runtime_shows_honest_fallback_not_blank_or_zero(page):
    original = _fixture("保留分析").replace('</main>', '<div class="chart-card"><canvas id="unknownChart"></canvas></div></main>')
    _load(page, inject_reader(original))
    assert page.locator("#unknownChart").is_hidden()
    assert "未通過安全相容檢查" in page.locator(".reader-chart-unavailable").inner_text()


def test_blocking_contract_and_quantitative_warning_never_collapse(page):
    rows = ''.join(f'<tr><td>來源{i}</td><td>P</td><td><span class="audit-status audit-status-error">error</span></td><td></td><td></td><td></td><td></td><td></td><td>逾時</td></tr>' for i in range(4))
    original = _fixture('保留分析').replace('</main>',
        f'<table class="source-audit-table"><tbody>{rows}</tbody></table>'
        '<section class="report-reading-notice"><ul class="report-reading-notice-checks"><li><span>輸出契約</span><strong>阻斷</strong></li></ul></section>'
        '<div class="data-trust-card"><div class="data-trust-quant-warning">DCF 不可用</div></div></main>')
    _load(page, inject_reader(original))
    assert '阻斷' in page.locator('#reader-limits > ul').inner_text()
    assert page.locator('#reader-limits > .data-trust-quant-warning').is_visible()


def test_waiting_position_does_not_keep_the_original_buy_arrow(page):
    original = _fixture('原研究評級買入', mode='v2').replace('<div class="verdict-main">', '<span class="verdict-icon">↑</span><div class="verdict-main">').replace('<dt>最終建議</dt><dd>持有</dd>', '<dt>部位動作</dt><dd>等待</dd>')
    _load(page, inject_reader(original))
    assert page.locator('.verdict-banner').first.get_attribute('data-reader-decision') == 'observe'
    assert page.locator('.verdict-icon').first.inner_text() == '→'
    assert page.locator('.verdict-main').first.inner_text() == '等待'


def test_original_markdown_race_prevents_migrating_a_mixed_financial_receipt(tmp_path, monkeypatch):
    import pytest
    import report_reader_migration as migration
    from test_report_reader_migration import fixture_bundle
    storage, db, name, key, original = fixture_bundle(tmp_path)
    load = migration._reader_snapshot

    def change_after_read(*args):
        result = load(*args)
        storage.save_report(key.replace('.html', '.md'), b'changed source prose', content_type='text/markdown')
        return result

    monkeypatch.setattr(migration, '_reader_snapshot', change_after_read)
    with pytest.raises(ValueError, match='Markdown changed'):
        migration.migrate_report(db, storage, name, apply=True)
    assert storage.get_report(key).content == original
