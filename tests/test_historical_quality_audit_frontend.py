import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_history_quality_helper_renders_read_only_historical_audit_summary_and_targets():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const audit = {
  scope: 'all_historical_indexed_reports',
  audited_reports: 1330,
  quality_metadata_missing_reports: 143,
  missing_quality_field_counts: {
    report_conformance: 143,
    evidence_exit_gate: 143,
    content_credibility: 143
  },
  quality_metadata_missing_by_provenance: { after_refresh: 143, no_refresh_provenance: 0 },
  quality_metadata_by_pipeline: {
    v1: { quality_metadata_missing_reports: 36 },
    v2: { quality_metadata_missing_reports: 36 }
  },
  items_returned: 2,
  items_truncated: true,
  items: [
    {
      ticker: '1623.TW',
      filename: '1623_TW_v2.html',
      pipeline_id: 'v2',
      report_date: '2026-08-15 15:47',
      title: '刷新後品質證據缺口',
      detail: '資料快照曾在報告後刷新，採用前需人工查看。',
      reason_codes: ['quality_metadata_missing', 'quality_metadata_after_refresh']
    },
    {
      ticker: '3017.TW',
      filename: '3017_TW_v1.html',
      pipeline_id: 'v1',
      title: '刷新後品質證據缺口',
      detail: '資料快照曾在報告後刷新，採用前需人工查看。',
      reason_codes: ['quality_metadata_missing', 'quality_metadata_after_refresh']
    }
  ]
};
const html = window.StockAgentHistoryPanelQualityHelpers.renderHistoricalQualityAudit(audit, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "歷史版本品質稽核" in payload["html"]
    assert "143 份待人工核對" in payload["html"]
    assert "缺口：報告一致性 143、證據關卡 143、內容可信度 143" in payload["html"]
    assert "來源：刷新後缺口 143" in payload["html"]
    assert "模式缺口：v1 36、v2 36" in payload["html"]
    assert "另有 141 份未展開" in payload["html"]
    assert 'data-quality-audit-report="1623_TW_v2.html"' in payload["html"]
    assert 'data-quality-reason-codes="quality_metadata_missing,quality_metadata_after_refresh"' in payload["html"]
    assert "查看 1623.TW v2 · 2026-08-15 15:47" in payload["html"]


def test_history_quality_audit_module_filters_requests_and_reuses_open_report_callback():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = {};
  require(__HELPER_PATH__);
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
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["captured"] == {"itemLimit": 5, "query": "1623.TW", "pipeline": "v2"}
    assert payload["opened"] == ["1623_v2.html", "1623.TW", "v2"]
    assert payload["hidden"] is True


def test_history_workspace_wires_historical_quality_audit_without_daily_queue_side_effects():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    api_client = (STATIC_DIR / "api_client_extensions.js").read_text(encoding="utf-8")
    app_elements = (STATIC_DIR / "app_elements.js").read_text(encoding="utf-8")
    app_panels = (STATIC_DIR / "app_panels.js").read_text(encoding="utf-8")
    workspace = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")

    assert 'id="history-quality-audit"' in index_html
    assert "/static/history_quality_audit.js?v=20260816-historical-quality-audit" in index_html
    assert "fetchHistoricalReportQualityAudit" in api_client
    assert "historyQualityAudit" in app_elements
    assert "historyQualityAudit" in app_panels
    assert "qualityAudit.load(values)" in workspace
    assert "data-quality-audit-report" in workspace or "qualityAudit.bindEvents()" in workspace
