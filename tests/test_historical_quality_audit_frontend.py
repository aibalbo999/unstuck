import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_history_quality_helper_renders_read_only_historical_audit_summary_and_targets():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
require(__RENDERER_PATH__);
const audit = {
  scope: 'all_historical_indexed_reports',
  audited_reports: 1330,
  quality_metadata_coverage_pct: 89.25,
  quality_metadata_coverage_basis: 'verified_snapshot_reports',
  snapshot_invalid_reports: 0,
  snapshot_unverified_reports: 0,
  quality_metadata_missing_reports: 143,
  missing_quality_field_counts: {
    report_conformance: 143,
    evidence_exit_gate: 143,
    content_credibility: 143
  },
  quality_metadata_missing_by_provenance: { after_refresh: 143, no_refresh_provenance: 0 },
  quality_review_by_status: { pending: 143, approved_with_gap: 0, rejected: 0, deferred: 0 },
  artifact_quality_summary_by_status: { present: 1, not_found: 0, unavailable: 0 },
  artifact_quality_summary_by_field: { report_conformance: 1, evidence_exit_gate: 1, content_credibility: 0 },
  quality_metadata_by_pipeline: {
    v1: { quality_metadata_missing_reports: 36 },
    v2: { quality_metadata_missing_reports: 36 }
  },
  items_returned: 2,
  items_offset: 0,
  items_limit: 5,
  items_total: 143,
  items_has_prev: false,
  items_has_next: true,
  items_truncated: true,
  items: [
    {
      ticker: '1623.TW',
      filename: '1623_TW_v2.html',
      pipeline_id: 'v2',
      report_date: '2026-08-15 15:47',
      title: '刷新後品質證據缺口',
      detail: '資料快照曾在報告後刷新，採用前需人工查看。',
      reason_codes: ['quality_metadata_missing', 'quality_metadata_after_refresh'],
      missing_quality_fields: ['report_conformance', 'evidence_exit_gate', 'content_credibility'],
      quality_metadata_provenance: 'after_refresh',
      artifact_quality_summary: { status: 'present', source: 'markdown', fields: ['report_conformance', 'evidence_exit_gate'] }
    },
    {
      ticker: '3017.TW',
      filename: '3017_TW_v1.html',
      pipeline_id: 'v1',
      title: '刷新後品質證據缺口',
      detail: '資料快照曾在報告後刷新，採用前需人工查看。',
      reason_codes: ['quality_metadata_missing', 'quality_metadata_after_refresh'],
      missing_quality_fields: ['report_conformance'],
      quality_metadata_provenance: 'after_refresh'
    }
  ]
};
const html = window.StockAgentHistoricalQualityAuditRenderer.render(audit, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "歷史版本品質稽核" in payload["html"]
    assert "143 份品質 metadata 缺口" in payload["html"]
    assert "缺口：報告一致性 143、證據關卡 143、內容可信度 143" in payload["html"]
    assert "來源：刷新後缺口 143" in payload["html"]
    assert "審核狀態：待人工核對 143" in payload["html"]
    assert "模式缺口：v1 36、v2 36" in payload["html"]
    assert "另有 141 份未展開" in payload["html"]
    assert "品質 metadata 完整度：89.25%（分母：已驗證快照）" in payload["html"]
    assert 'data-quality-audit-page="next"' in payload["html"]
    assert "下一批" in payload["html"]
    assert 'data-quality-audit-pipeline="v1"' in payload["html"]
    assert "只看 v1 缺口" in payload["html"]
    assert 'data-quality-audit-report="1623_TW_v2.html"' in payload["html"]
    assert 'data-quality-reason-codes="quality_metadata_missing,quality_metadata_after_refresh"' in payload["html"]
    assert "查看 1623.TW v2 · 2026-08-15 15:47" in payload["html"]
    assert "缺少報告一致性、證據關卡、內容可信度" in payload["html"]
    assert "來源：刷新後" in payload["html"]
    assert "品質缺口：缺少報告一致性、證據關卡、內容可信度；來源：刷新後" in payload["html"]
    assert "artifact 摘要可查：報告一致性、證據關卡" in payload["html"]
    assert "artifact 摘要可查 1 份" in payload["html"]
    assert "artifact 欄位可查：報告一致性 1、證據關卡 1、內容可信度 0" in payload["html"]


def test_history_quality_audit_module_filters_requests_and_reuses_open_report_callback():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = {};
  require(__HELPER_PATH__);
  require(__RENDERER_PATH__);
  require(__MODULE_PATH__);
  let clickHandler;
  let captured;
  let opened;
  const element = {
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; }
  };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: {
      fetchHistoricalReportQualityAudit: async params => {
        captured = params;
        return { audited_reports: 1, quality_metadata_missing_reports: 0, items: [] };
      }
    },
    ui: { escapeHtml: value => String(value ?? '') },
    element,
    openReport: (...args) => { opened = args; }
  });
  audit.bindEvents();
  await audit.load({ includeVersions: true, query: '1623.TW', pipelineFilter: 'v2' });
  clickHandler({ target: { closest: () => ({ dataset: { qualityAuditReport: '1623_v2.html', qualityAuditTicker: '1623.TW', qualityAuditPipeline: 'v2' } }) } });
  await audit.load({ includeVersions: false, query: '1623.TW', pipelineFilter: 'v2' });
  process.stdout.write(JSON.stringify({ captured, opened, hidden: element.hidden }));
})();
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["captured"] == {"itemLimit": 5, "itemOffset": 0, "query": "1623.TW", "pipeline": "v2"}
    assert payload["opened"] == ["1623_v2.html", "1623.TW", "v2"]
    assert payload["hidden"] is True


def test_history_quality_audit_filtered_status_shows_scope_instead_of_global_coverage():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 143,
  quality_metadata_missing_reports: 143,
  quality_metadata_coverage_pct: 0,
  quality_metadata_coverage_basis: 'verified_snapshot_reports',
  review_status_filter: 'pending',
  quality_review_by_status: { pending: 143, approved_with_gap: 0, rejected: 0, deferred: 0 },
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "審核範圍：待人工核對" in payload["html"]
    assert "品質 metadata 完整度：0%" not in payload["html"]


def test_history_quality_audit_pipeline_shortcut_delegates_filter_selection():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = {};
  require(__HELPER_PATH__);
  require(__RENDERER_PATH__);
  require(__MODULE_PATH__);
  let clickHandler;
  let selected;
  const element = {
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; }
  };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: { fetchHistoricalReportQualityAudit: async () => ({ audited_reports: 1, items: [] }) },
    ui: { escapeHtml: value => String(value ?? '') },
    element,
    onSelectPipeline: pipeline => { selected = pipeline; }
  });
  audit.bindEvents();
  clickHandler({ target: { closest: selector => selector === '[data-quality-audit-pipeline]' ? { dataset: { qualityAuditPipeline: 'v2' } } : null } });
  process.stdout.write(JSON.stringify({ selected }));
})();
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["selected"] == "v2"


def test_history_quality_audit_review_status_shortcut_reloads_status_filter():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = {};
  require(__HELPER_PATH__);
  require(__RENDERER_PATH__);
  require(__MODULE_PATH__);
  let clickHandler;
  const captured = [];
  const element = {
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; }
  };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: {
      fetchHistoricalReportQualityAudit: async params => {
        captured.push(params);
        return { audited_reports: 1, quality_metadata_missing_reports: 1, quality_review_by_status: { pending: 0, approved_with_gap: 1, rejected: 0, deferred: 0 }, review_status_filter: params.reviewStatus || 'all', items: [] };
      }
    },
    ui: { escapeHtml: value => String(value ?? '') },
    element
  });
  audit.bindEvents();
  await audit.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  await clickHandler({ target: { closest: selector => selector === '[data-quality-audit-review-status]' ? { dataset: { qualityAuditReviewStatus: 'approved_with_gap' } } : null } });
  process.stdout.write(JSON.stringify({ captured }));
})();
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["captured"] == [
        {"itemLimit": 5, "itemOffset": 0, "query": "", "pipeline": "all"},
        {"itemLimit": 5, "itemOffset": 0, "query": "", "pipeline": "all", "reviewStatus": "approved_with_gap"},
    ]


def test_history_quality_audit_pages_manual_review_targets_in_batches():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = {};
  require(__HELPER_PATH__);
  require(__RENDERER_PATH__);
  require(__MODULE_PATH__);
  let clickHandler;
  const captured = [];
  const element = {
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; }
  };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: {
      fetchHistoricalReportQualityAudit: async params => {
        captured.push(params);
        return {
          audited_reports: 10,
          quality_metadata_missing_reports: 10,
          quality_metadata_coverage_pct: 0,
          items_offset: params.itemOffset,
          items_limit: params.itemLimit,
          items_total: 10,
          items_returned: 5,
          items_has_prev: params.itemOffset > 0,
          items_has_next: params.itemOffset === 0,
          items: []
        };
      }
    },
    ui: { escapeHtml: value => String(value ?? '') },
    element
  });
  audit.bindEvents();
  await audit.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  await clickHandler({ target: { closest: selector => selector === '[data-quality-audit-page]' ? { dataset: { qualityAuditPage: 'next' } } : null } });
  process.stdout.write(JSON.stringify({ captured }));
})();
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["captured"] == [
        {"itemLimit": 5, "itemOffset": 0, "query": "", "pipeline": "all"},
        {"itemLimit": 5, "itemOffset": 5, "query": "", "pipeline": "all"},
    ]


def test_history_quality_audit_ignores_stale_filter_response():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = {};
  require(__HELPER_PATH__);
  require(__RENDERER_PATH__);
  require(__MODULE_PATH__);
  const pending = {};
  const element = {
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: () => {}
  };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: {
      fetchHistoricalReportQualityAudit: params => new Promise(resolve => { pending[params.query] = resolve; })
    },
    ui: { escapeHtml: value => String(value ?? '') },
    element
  });
  const stale = audit.load({ includeVersions: true, query: 'old', pipelineFilter: 'all' });
  const latest = audit.load({ includeVersions: true, query: 'new', pipelineFilter: 'v2' });
  pending.new({ audited_reports: 1, quality_metadata_missing_reports: 0, items: [] });
  await latest;
  pending.old({ audited_reports: 9, quality_metadata_missing_reports: 9, items: [] });
  await stale;
  process.stdout.write(JSON.stringify({ html: element.innerHTML }));
})();
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "範圍：1 份" in payload["html"]
    assert "範圍：9 份" not in payload["html"]


def test_history_quality_helper_surfaces_snapshot_verification_boundary():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 10,
  quality_metadata_coverage_pct: 100,
  quality_metadata_coverage_basis: 'verified_snapshot_reports',
  snapshot_invalid_reports: 1,
  snapshot_unverified_reports: 2,
  quality_metadata_missing_reports: 0,
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "品質 metadata 完整度：100%（分母：已驗證快照）" in payload["html"]
    assert "snapshot 無法驗證 3 份（invalid 1、未驗證 2）" in payload["html"]


def test_history_workspace_wires_historical_quality_audit_without_daily_queue_side_effects():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    api_client = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    app_elements = (STATIC_DIR / "app_elements.js").read_text(encoding="utf-8")
    app_panels = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    workspace = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")

    assert 'id="history-quality-audit"' in index_html
    assert "/static/api_client_extensions.js?v=20260816-quality-review-status-filter" in index_html
    assert "/static/history_panel_quality_helpers.js?v=20260816-quality-review-status-filter" in index_html
    assert "/static/history_quality_audit_render.js?v=20260816-quality-review-scope-copy" in index_html
    assert "/static/history_quality_audit.js?v=20260816-quality-review-submit-feedback" in index_html
    assert index_html.index("/static/history_quality_audit_render.js") < index_html.index("/static/history_quality_audit.js")
    assert len((STATIC_DIR / "history_panel_quality_helpers.js").read_text(encoding="utf-8").splitlines()) < 120
    assert len((STATIC_DIR / "history_quality_audit_render.js").read_text(encoding="utf-8").splitlines()) < 100
    assert "fetchHistoricalReportQualityAudit" in api_client
    assert "historyQualityAudit" in app_elements
    assert "historyQualityAudit" in app_panels
    assert "qualityAudit.load(values)" in workspace
    assert "onSelectPipeline" in workspace
    assert "historyPipelineFilter.value = pipeline" in workspace
    assert "data-quality-audit-report" in workspace or "qualityAudit.bindEvents()" in workspace
