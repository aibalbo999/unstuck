import json
import subprocess
from pathlib import Path

from provider_acquisition import project_acquisition_events

ROOT = Path(__file__).resolve().parents[1]


def render(events, *, available=True):
    payload = project_acquisition_events(events, window="last_24h", now=200_000)
    payload["available"] = available
    script = """
const fs = require('fs'), vm = require('vm');
const context = {window: {}};
for (const name of ['provider_sla_helpers.js', 'provider_sla_panel.js']) {
  vm.runInNewContext(fs.readFileSync('backend/static/' + name, 'utf8'), context);
}
const summaryEl = {}, listEl = {};
context.window.StockAgentProviderSlaPanel.render({acquisition: JSON.parse(process.argv[1])}, {
  summaryEl, listEl, windowEl: {value: 'last_24h'},
  escapeHtml: text => String(text ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')
});
console.log(JSON.stringify({summary: summaryEl.textContent, html: listEl.innerHTML}));
"""
    result = subprocess.run(["node", "-e", script, json.dumps(payload)], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def event(source, provider, status, count=0):
    return dict(source=source, provider=provider, status=status, record_count=count,
                message="", created_at=199_999)


def test_empty_result_never_renders_hundred_percent_or_green():
    result = render([event("earnings_call", "MOPS investor conference", "degraded_enrichment"),
                     event("earnings_call", "cache", "skipped_fresh_cache")])
    assert "100%" not in result["html"]
    assert "0%" in result["html"]
    assert "未取得資料" in result["html"]
    assert "空快取 1" in result["html"]
    assert "可放心分析" not in result["summary"]
    assert "可安心使用" not in result["html"]


def test_all_providers_and_sources_remain_visible_with_failures_first():
    events = [event("recent_catalysts", "PTT Stock", "unavailable")]
    events += [event("recent_catalysts", f"healthy-{i}", "success", 3) for i in range(5)]
    events += [event(f"source-{i}", f"provider-{i}", "success", 1) for i in range(9)]
    result = render(events)
    html = result["html"]
    assert "PTT Stock" in html
    assert html.index("PTT Stock") < html.index("healthy-0")
    assert "healthy-4" in html
    assert "source-8" in html
    assert "失敗／不可用 1" in html
    assert "可放心分析" not in result["summary"]


def test_cache_only_and_no_samples_do_not_render_a_success_rate():
    result = render([event("market_data", "cache", "skipped_fresh_cache", 5)])
    assert "100%" not in result["html"]
    assert "0%" not in result["html"]
    assert "無抓取樣本" in result["html"]
    assert "有效快取 1" in result["html"]
    assert "無檢查樣本" in render([])["summary"]


def test_unavailable_telemetry_is_explicit_and_escapes_source_names():
    assert "無法" in render([], available=False)["summary"]
    result = render([event("<script>bad</script>", "<img onerror=bad>", "error")])
    assert "<script>" not in result["html"]
    assert "&lt;script&gt;" in result["html"]
