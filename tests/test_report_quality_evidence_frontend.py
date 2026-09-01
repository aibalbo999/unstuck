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
    assert f"{helper}?v=20260901-quality-blockers" in index_html
    assert "/static/report_quality_gate_policy.js?v=20260816-shared-quality-evidence" in index_html
    assert "/static/report_preview_helpers.js?v=20260820-shared-evidence-detail" in index_html
    assert "/static/report_preview_panel.js?v=20260820-rerun-execution" in index_html
    assert "/static/history_quality_audit_render.js?v=20260820-per-pipeline-context-summary" in index_html
    assert "/static/history_current_quality_helpers.js?v=20260901-quality-blockers" in index_html
    assert "/static/watchlist_freshness_helpers.js?v=20260821-freshness-targets" in index_html
    assert "/static/watchlist_current_quality_helpers.js?v=20260901-quality-blockers" in index_html
    assert "/static/watchlist_panel_helpers.js?v=20260821-current-quality" in index_html
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    assert "/static/styles/history_list.css?v=20260816-clickable-quality-evidence" in style_css
    assert index_html.index(helper) < index_html.index("/static/report_quality_gate_policy.js")
    assert index_html.index(helper) < index_html.index("/static/watchlist_panel_helpers.js")
    assert index_html.index("/static/watchlist_freshness_helpers.js") < index_html.index("/static/watchlist_panel_helpers.js")
    assert index_html.index(helper) < index_html.index("/static/report_preview_helpers.js")
    assert index_html.index("/static/history_current_quality_helpers.js") < index_html.index("/static/history_quality_audit_render.js")
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
const targetContext = window.StockAgentReportQualityEvidence.renderTargetContext({
  reviewStatus: '審核狀態：待人工核對',
  evidenceContext: '結構化缺口：內容可信度；來源：刷新後',
  warning: 'artifact 摘要僅供人工核對，不代表 gate 已通過'
}, escapeHtml);
const history = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 1,
  quality_metadata_missing_reports: 1,
  quality_metadata_coverage_pct: 0,
  quality_metadata_coverage_basis: 'verified_snapshot_reports',
  missing_quality_field_counts: { report_conformance: 1, evidence_exit_gate: 1, content_credibility: 1 },
  quality_review_by_status: { pending: 1, approved_with_gap: 0, rejected: 0, deferred: 0 },
  items: [{ ...report, title: '刷新後品質證據缺口', detail: '資料快照曾在報告後刷新，採用前需人工查看。', reason_codes: ['quality_metadata_after_refresh'], quality_review: { status: 'pending' } }]
}, escapeHtml);
process.stdout.write(JSON.stringify({ badge, history, completeEvidence, targetContext }));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__GATE_PATH__", json.dumps(str(gate_path))).replace("__POLICY_PATH__", json.dumps(str(policy_path))).replace("__PREVIEW_PATH__", json.dumps(str(preview_path))).replace("__HISTORY_HELPER_PATH__", json.dumps(str(history_helper_path))).replace("__HISTORY_RENDERER_PATH__", json.dumps(str(history_renderer_path)))

    payload = json.loads(_node(script))

    assert '<button' in payload["badge"]
    assert 'data-quality-history-audit-target' in payload["badge"]
    assert 'data-quality-history-query="1623_TW_v2_report_20260815_154718.html"' in payload["badge"]
    assert 'artifact 摘要僅供人工核對，不代表 gate 已通過' in payload["badge"]
    assert 'aria-label="前往 1623.TW v2 的歷史品質稽核：' in payload["badge"]
    assert '結構化品質 metadata：' not in payload["completeEvidence"]["detail"]
    assert '結構化品質 metadata：報告一致性、證據關卡、內容可信度' in payload["history"]
    assert '<small class="quality-evidence-review-status">審核狀態：待人工核對</small>' in payload["history"]
    assert 'artifact 摘要僅供人工核對，不代表 gate 已通過' in payload["history"]
    assert '<small class="quality-evidence-warning">artifact 摘要僅供人工核對，不代表 gate 已通過</small>' in payload["history"]
    assert 'data-quality-evidence-detail=' in payload["history"]
    assert payload["targetContext"]["text"] == '審核狀態：待人工核對；結構化缺口：內容可信度；來源：刷新後；artifact 摘要僅供人工核對，不代表 gate 已通過'
    assert '<small class="quality-evidence-review-status">審核狀態：待人工核對</small>' in payload["targetContext"]["html"]
    assert '<small class="quality-evidence-context">結構化缺口：內容可信度；來源：刷新後</small>' in payload["targetContext"]["html"]
    assert '<small class="quality-evidence-warning">artifact 摘要僅供人工核對，不代表 gate 已通過</small>' in payload["targetContext"]["html"]


def test_shared_quality_evidence_labels_refresh_attribution_without_claiming_causality():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
const evidence = window.StockAgentReportQualityEvidence.context({
  missing_quality_fields: ['content_credibility'],
  quality_metadata_provenance: 'after_refresh',
  artifact_quality_summary: { status: 'present', fields: ['content_credibility'] }
});
process.stdout.write(JSON.stringify(evidence));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path)))

    evidence = json.loads(_node(script))

    assert evidence["provenanceText"] == "來源：有刷新歸因"
    assert "來源：有刷新歸因" in evidence["detail"]
    assert "來源：刷新後缺口" not in evidence["detail"]


def test_shared_quality_evidence_formats_unverifiable_reason_counts_for_operators():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
process.stdout.write(JSON.stringify({
  summary: window.StockAgentReportQualityEvidence.formatUnverifiableReasonSummary({
    snapshot_value_mismatch: 3,
    derived_metric_not_canonical: 4,
    risk_control_not_canonical: 2,
    scenario_target_not_canonical: 2,
    technical_level_not_canonical: 2,
    research_source_not_canonical: 2,
    unknown_reason: 1,
    no_matching_snapshot_path: 0
  })
}));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path)))

    payload = json.loads(_node(script))

    assert payload["summary"] == "證據未驗證原因：衍生指標沒有 canonical 欄位 4、快照數值不一致 3、研究來源非 canonical 2、風險控制沒有 canonical 欄位 2、情境目標沒有 canonical 欄位 2、技術價位沒有 canonical 欄位 2、unknown_reason 1"


def test_shared_quality_evidence_formats_mismatch_freshness_distribution():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
process.stdout.write(window.StockAgentReportQualityEvidence.formatEvidenceMismatchFreshnessSummary(
  { needs_rerun: 12, current: 1, unknown: 0 },
  { needs_rerun: 8, current: 1, unknown: 0 }
));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path)))

    assert _node(script) == "數值不一致分布：資料已更新、本文需完整重跑 12 筆／8 份、本文目前版本 1 筆／1 份"


def test_shared_quality_evidence_labels_analysis_metadata_reason():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
process.stdout.write(window.StockAgentReportQualityEvidence.formatUnverifiableReasonSummary({
  analysis_metadata_not_evidence: 3
}));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path)))

    assert _node(script) == "證據未驗證原因：分析欄位不是證據 3"


def test_shared_quality_evidence_formats_quality_blocker_sources():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
process.stdout.write(window.StockAgentReportQualityEvidence.formatQualityBlockerSummary(
  { final_audit: 14, report_lint: 0 },
  { final_audit_critical: 13, explicit_target_price_low_data_confidence: 3 }
));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path)))

    assert _node(script) == "品質阻斷來源：報告一致性：最終稽核 14；內容可信度：最終稽核重大問題 13、低資料信心仍含目標價 3"


def test_shared_quality_evidence_labels_unavailable_snapshot_field_reason():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
process.stdout.write(window.StockAgentReportQualityEvidence.formatUnverifiableReasonSummary({
  snapshot_field_unavailable: 1
}));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path)))

    assert _node(script) == "證據未驗證原因：快照欄位不可用 1"


def test_shared_quality_evidence_labels_gap_that_predates_refresh():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
const evidence = window.StockAgentReportQualityEvidence.context({
  missing_quality_fields: ['content_credibility'],
  quality_metadata_provenance: 'before_refresh',
  reason_codes: ['quality_metadata_missing', 'quality_metadata_before_refresh'],
  quality_metadata_refresh_provenance: {
    source: 'previous_snapshot_before_refresh',
    missing_fields: ['content_credibility']
  }
});
process.stdout.write(JSON.stringify(evidence));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path)))

    evidence = json.loads(_node(script))

    assert evidence["provenanceText"] == "來源：刷新前已有缺口"
    assert "來源：刷新前已有缺口" in evidence["detail"]
    assert "來源：刷新前已有缺口" in evidence["targetContext"]


def test_shared_quality_evidence_labels_historical_version_status():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
const evidence = window.StockAgentReportQualityEvidence.context({
  missing_quality_fields: ['content_credibility'],
  report_version_status: 'historical',
  artifact_quality_summary: { status: 'present', fields: ['content_credibility'] }
});
process.stdout.write(JSON.stringify(evidence));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path)))

    payload = json.loads(_node(script))

    assert payload["reportVersionText"] == "版本：歷史版本（非目前最新）"
    assert payload["reportVersionText"] in payload["targetContext"]


def test_shared_quality_evidence_surfaces_rerun_context_status_without_approving_gate():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
const evidence = window.StockAgentReportQualityEvidence.context({
  missing_quality_fields: ['report_conformance', 'evidence_exit_gate', 'content_credibility'],
  rerun_context_status: 'artifact_fallback_available',
  rerun_execution_status: 'full_rerun_required',
  snapshot_rerun_context_status: 'missing',
  artifact_rerun_context_status: 'present',
  artifact_quality_summary: { status: 'present', fields: ['report_conformance', 'evidence_exit_gate'] }
});
const target = window.StockAgentReportQualityEvidence.renderTargetContext({
  evidenceContext: evidence.targetContext,
  warning: evidence.targetWarning
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ evidence, target }));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path)))

    payload = json.loads(_node(script))

    expected_context = "局部重跑上下文：artifact 有完整前序段落（只代表上下文可查）"
    expected_execution = "重跑策略：目前資料 freshness 要求完整重跑"
    assert payload["evidence"]["rerunContextText"] == expected_context
    assert payload["evidence"]["rerunExecutionText"] == expected_execution
    assert expected_context in payload["evidence"]["targetContext"]
    assert expected_execution in payload["evidence"]["targetContext"]
    assert expected_execution in payload["target"]["text"]
    assert "可嘗試局部重跑" not in payload["target"]["text"]
    assert "gate 已通過" not in payload["evidence"]["rerunExecutionText"]
    assert "artifact 摘要僅供人工核對，不代表 gate 已通過" in payload["target"]["text"]


def test_preview_quality_badge_uses_shared_evidence_detail_over_policy_copy():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    preview_path = STATIC_DIR / "report_preview_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
window.StockAgentReportQualityPolicy = {
  reportQualityGateAction: () => ({ label: '結構化品質缺口', tone: 'critical', detail: '舊的 policy detail' })
};
require(__PREVIEW_PATH__);
const report = {
  filename: '1623_TW_v2_report_20260815_154718.html',
  ticker: '1623.TW',
  pipeline_id: 'v2',
  missing_quality_fields: ['content_credibility'],
  artifact_quality_summary: { status: 'present', fields: ['content_credibility'] }
};
const escapeHtml = value => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
process.stdout.write(window.StockAgentReportPreviewHelpers.reportQualityBadge(report, escapeHtml));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__PREVIEW_PATH__", json.dumps(str(preview_path)))

    badge = _node(script)

    assert '舊的 policy detail' not in badge
    assert '結構化品質 metadata：內容可信度' in badge
    assert 'artifact 摘要可查：內容可信度' in badge


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


def test_historical_quality_audit_surfaces_current_quality_projection_separately():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    helper_path = STATIC_DIR / "history_current_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
require(__HELPER_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 1,
  quality_metadata_missing_reports: 0,
  quality_metadata_complete_reports: 1,
  verified_snapshot_reports: 1,
  quality_metadata_coverage_pct: 100,
  quality_metadata_coverage_basis: 'verified_snapshot_reports',
  current_quality_summary: {
    schema_version: 'report_current_quality_summary.v1',
    scope: 'historical_filter_current_latest',
    selection_basis: 'latest_per_ticker_pipeline',
    filters: { q: '2330.TW', pipeline: 'v2' },
    audited_reports: 1,
    report_conformance_by_status: { passed: 0, warning: 1, blocked: 0, unknown: 0 },
    content_credibility_by_status: { passed: 1, warning: 0, blocked: 0, unknown: 0 },
    evidence_exit_gate_by_verdict: { approved: 0, caution: 1, rejected: 0, unknown: 0 },
    evidence_failed_count: 3,
    evidence_unverifiable_reason_counts: { research_source_not_canonical: 2 },
    report_conformance_blocker_counts: { final_audit: 1 },
    content_credibility_blocker_counts: { final_audit_critical: 1 },
    non_passed_reports: 1,
    items_total: 1,
    items_returned: 0,
    items: []
  },
  items: []
}, value => String(value ?? ''));
process.stdout.write(html);
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert "目前版本品質（查詢：2330.TW；模式：v2；只看最新版本）" in result.stdout
    assert "一致性 符合 0、警示 1" in result.stdout
    assert "證據關卡需注意 1" in result.stdout
    assert "證據數值不一致 3" in result.stdout
    assert "證據未驗證原因：研究來源非 canonical 2" in result.stdout
    assert "品質阻斷來源：報告一致性：最終稽核 1；內容可信度：最終稽核重大問題 1" in result.stdout
    assert "1 份品質 metadata 缺口" not in result.stdout
