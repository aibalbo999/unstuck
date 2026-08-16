import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def _node(script: str) -> str:
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    return result.stdout


def test_shared_quality_evidence_helper_loads_before_all_consumers():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    helper = "/static/report_quality_evidence_helpers.js"
    assert (STATIC_DIR / "report_quality_evidence_helpers.js").exists()
    assert f"{helper}?v=20260816-visible-evidence-warning" in index_html
    assert "/static/report_quality_gate_policy.js?v=20260816-shared-quality-evidence" in index_html
    assert "/static/report_preview_helpers.js?v=20260816-visible-evidence-warning" in index_html
    assert "/static/report_preview_panel.js?v=20260816-clickable-quality-evidence" in index_html
    assert "/static/history_quality_audit_render.js?v=20260816-visible-evidence-warning" in index_html
    assert "/static/watchlist_panel_helpers.js?v=20260816-visible-evidence-warning" in index_html
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    assert "/static/styles/history_list.css?v=20260816-clickable-quality-evidence" in style_css
    assert index_html.index(helper) < index_html.index("/static/report_quality_gate_policy.js")
    assert index_html.index(helper) < index_html.index("/static/watchlist_panel_helpers.js")
    assert index_html.index(helper) < index_html.index("/static/report_preview_helpers.js")
    assert len((STATIC_DIR / "report_quality_evidence_helpers.js").read_text(encoding="utf-8").splitlines()) < 45


def test_preview_and_history_share_clickable_quality_evidence_context():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    gate_path = STATIC_DIR / "report_quality_gate_policy.js"
    policy_path = STATIC_DIR / "report_quality_policy.js"
    preview_path = STATIC_DIR / "report_preview_helpers.js"
    history_helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    history_renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
require(__GATE_PATH__);
require(__POLICY_PATH__);
require(__PREVIEW_PATH__);
require(__HISTORY_HELPER_PATH__);
require(__HISTORY_RENDERER_PATH__);
const report = {
  filename: '1623_TW_v2_report_20260815_154718.html',
  ticker: '1623.TW',
  pipeline_id: 'v2',
  snapshot_integrity: { status: 'verified' },
  missing_quality_fields: ['report_conformance', 'evidence_exit_gate', 'content_credibility'],
  quality_metadata_provenance: 'after_refresh',
  artifact_quality_summary: { status: 'present', source: 'markdown', fields: ['report_conformance', 'evidence_exit_gate'] },
  report_conformance: {}, evidence_exit_gate: {}, content_credibility: {}
};
const escapeHtml = value => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const badge = window.StockAgentReportPreviewHelpers.reportQualityBadge(report, escapeHtml);
const completeEvidence = window.StockAgentReportQualityEvidence.context({ artifact_quality_summary: { status: 'present', fields: ['report_conformance'] } });
const history = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 1,
  quality_metadata_missing_reports: 1,
  quality_metadata_coverage_pct: 0,
  quality_metadata_coverage_basis: 'verified_snapshot_reports',
  missing_quality_field_counts: { report_conformance: 1, evidence_exit_gate: 1, content_credibility: 1 },
  quality_review_by_status: { pending: 1, approved_with_gap: 0, rejected: 0, deferred: 0 },
  items: [{ ...report, title: '刷新後品質證據缺口', detail: '資料快照曾在報告後刷新，採用前需人工查看。', reason_codes: ['quality_metadata_after_refresh'] }]
}, escapeHtml);
process.stdout.write(JSON.stringify({ badge, history, completeEvidence }));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__GATE_PATH__", json.dumps(str(gate_path))).replace("__POLICY_PATH__", json.dumps(str(policy_path))).replace("__PREVIEW_PATH__", json.dumps(str(preview_path))).replace("__HISTORY_HELPER_PATH__", json.dumps(str(history_helper_path))).replace("__HISTORY_RENDERER_PATH__", json.dumps(str(history_renderer_path)))

    payload = json.loads(_node(script))

    assert '<button' in payload["badge"]
    assert 'data-quality-history-audit-target' in payload["badge"]
    assert 'data-quality-history-query="1623_TW_v2_report_20260815_154718.html"' in payload["badge"]
    assert 'artifact 摘要僅供人工核對，不代表 gate 已通過' in payload["badge"]
    assert 'aria-label="前往 1623.TW v2 的歷史品質稽核：' in payload["badge"]
    assert '結構化品質 metadata：' not in payload["completeEvidence"]["detail"]
    assert '結構化品質 metadata：報告一致性、證據關卡、內容可信度' in payload["history"]
    assert 'artifact 摘要僅供人工核對，不代表 gate 已通過' in payload["history"]
    assert '<small class="quality-evidence-warning">artifact 摘要僅供人工核對，不代表 gate 已通過</small>' in payload["history"]
    assert 'data-quality-evidence-detail=' in payload["history"]


def test_clicking_preview_quality_gap_opens_scoped_historical_audit():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    gate_path = STATIC_DIR / "report_quality_gate_policy.js"
    policy_path = STATIC_DIR / "report_quality_policy.js"
    preview_helpers_path = STATIC_DIR / "report_preview_helpers.js"
    tracking_path = STATIC_DIR / "report_preview_tracking_helpers.js"
    rerun_path = STATIC_DIR / "report_preview_rerun_helpers.js"
    panel_path = STATIC_DIR / "report_preview_panel.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
require(__GATE_PATH__);
require(__POLICY_PATH__);
require(__PREVIEW_HELPERS_PATH__);
require(__TRACKING_PATH__);
require(__RERUN_PATH__);
let clickHandler, opened;
window.StockAgentOpenHistoricalQualityAudit = scope => { opened = scope; };
const el = () => ({ hidden: false, textContent: '', innerHTML: '', className: '', classList: { toggle() {} }, querySelector: () => null });
const mode = { ...el(), addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; } };
const elements = { workspace: el(), root: el(), mode, title: el(), decisionRow: el(), targets: el(), summary: el(), readingNotice: el(), staleNotice: el() };
const panel = require(__PANEL_PATH__) || window.StockAgentReportPreviewPanel;
const previewPanel = window.StockAgentReportPreviewPanel.create({
  elements,
  escapeHtml: value => String(value ?? ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  pipelineMeta: {},
  normalizeRecommendation: value => String(value ?? ''),
  recommendationTone: () => ''
});
previewPanel.show({
  filename: '1623_TW_v2_report_20260815_154718.html', ticker: '1623.TW', pipeline_id: 'v2', date: '2026-08-15',
  snapshot_integrity: { status: 'verified' },
  missing_quality_fields: ['report_conformance', 'evidence_exit_gate', 'content_credibility'],
  quality_metadata_provenance: 'after_refresh',
  artifact_quality_summary: { status: 'present', fields: ['report_conformance', 'evidence_exit_gate'] },
  report_conformance: {}, evidence_exit_gate: {}, content_credibility: {}, recommendation: {}, decision_tracking: {}
});
clickHandler({ target: { closest: selector => selector === '[data-quality-history-audit-target]' ? { dataset: { qualityHistoryQuery: '1623_TW_v2_report_20260815_154718.html', qualityHistoryPipeline: 'v2' } } : null } });
process.stdout.write(JSON.stringify({ opened }));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__GATE_PATH__", json.dumps(str(gate_path))).replace("__POLICY_PATH__", json.dumps(str(policy_path))).replace("__PREVIEW_HELPERS_PATH__", json.dumps(str(preview_helpers_path))).replace("__TRACKING_PATH__", json.dumps(str(tracking_path))).replace("__RERUN_PATH__", json.dumps(str(rerun_path))).replace("__PANEL_PATH__", json.dumps(str(panel_path)))

    payload = json.loads(_node(script))

    assert payload["opened"] == {
        "query": "1623_TW_v2_report_20260815_154718.html",
        "pipeline": "v2",
    }
