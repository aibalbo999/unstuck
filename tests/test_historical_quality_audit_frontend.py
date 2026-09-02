import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_history_quality_helper_renders_read_only_historical_audit_summary_and_targets():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    scope_path = STATIC_DIR / "report_quality_audit_scope_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
require(__HELPER_PATH__);
require(__SCOPE_PATH__);
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
  quality_metadata_missing_by_rerun_context: { present: 0, partial: 0, artifact_fallback_available: 86, missing: 57, not_evaluated: 0 },
  quality_metadata_missing_by_version_status: { current: 2, historical: 141, unknown: 0 },
  report_version_status_filter: 'all',
  quality_review_by_status: { pending: 143, approved_with_gap: 0, rejected: 0, deferred: 0 },
  artifact_quality_summary_by_status: { present: 1, not_found: 0, unavailable: 0 },
  artifact_quality_summary_by_field: { report_conformance: 1, evidence_exit_gate: 1, content_credibility: 0 },
  quality_metadata_by_pipeline: {
    v1: { quality_metadata_missing_reports: 36, quality_metadata_missing_by_rerun_context: { present: 0, partial: 0, artifact_fallback_available: 29, missing: 7, not_evaluated: 0 } },
    v2: { quality_metadata_missing_reports: 36, quality_metadata_missing_by_rerun_context: { present: 0, partial: 0, artifact_fallback_available: 29, missing: 7, not_evaluated: 0 } },
    v3: { quality_metadata_missing_reports: 35, quality_metadata_missing_by_rerun_context: { artifact_fallback_available: 14, missing: 21 } },
    v4: { quality_metadata_missing_reports: 36, quality_metadata_missing_by_rerun_context: { artifact_fallback_available: 14, missing: 22 } }
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
          detail: '資料快照曾在報告後刷新，目前未記錄品質證據；刷新歸因存在，但無法由目前 metadata 判定缺口是否由刷新造成；採用前需人工查看 artifact 與 freshness。',
      reason_codes: ['quality_metadata_missing', 'quality_metadata_after_refresh'],
      missing_quality_fields: ['report_conformance', 'evidence_exit_gate', 'content_credibility'],
      quality_metadata_provenance: 'after_refresh',
      report_version_status: 'historical',
      artifact_quality_summary: { status: 'present', source: 'markdown', fields: ['report_conformance', 'evidence_exit_gate'] }
    },
    {
      ticker: '3017.TW',
      filename: '3017_TW_v1.html',
      pipeline_id: 'v1',
      title: '刷新後品質證據缺口',
          detail: '資料快照曾在報告後刷新，目前未記錄品質證據；刷新歸因存在，但無法由目前 metadata 判定缺口是否由刷新造成；採用前需人工查看 artifact 與 freshness。',
      reason_codes: ['quality_metadata_missing', 'quality_metadata_after_refresh'],
      missing_quality_fields: ['report_conformance'],
      quality_metadata_provenance: 'after_refresh'
    }
  ]
};
const html = window.StockAgentHistoricalQualityAuditRenderer.render(audit, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__SCOPE_PATH__", json.dumps(str(scope_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "歷史版本品質稽核" in payload["html"]
    assert "143 份品質 metadata 缺口" in payload["html"]
    assert "缺口：報告一致性 143、證據關卡 143、內容可信度 143" in payload["html"]
    assert "來源：有刷新歸因 143" in payload["html"]
    assert "版本：目前版本缺口 2、歷史版本缺口 141" in payload["html"]
    assert 'data-quality-audit-version-status="current"' in payload["html"]
    assert "只看目前版本缺口（2）" in payload["html"]
    assert "審核狀態：待人工核對 143" in payload["html"]
    assert "人工審核進度：0/143" in payload["html"]
    assert "上下文：artifact 前序可查 86、無可用局部上下文 57" in payload["html"]
    assert "模式上下文：v1 artifact 前序可查 29" in payload["html"]
    assert "v2 artifact 前序可查 29" in payload["html"]
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
    assert "結構化缺口：報告一致性、證據關卡、內容可信度" in payload["html"]
    assert "來源：有刷新歸因" in payload["html"]
    assert "品質缺口：結構化缺口：報告一致性、證據關卡、內容可信度；來源：有刷新歸因" in payload["html"]
    assert "artifact 摘要可查：報告一致性、證據關卡" in payload["html"]
    assert "artifact 摘要可查 1 份" in payload["html"]
    assert "artifact 欄位可查：報告一致性 1、證據關卡 1、內容可信度 0" in payload["html"]
    assert "版本：歷史版本（非目前最新）" in payload["html"]
    assert payload["html"].count('class="history-quality-audit-summary-item"') == 8


def test_history_quality_audit_does_not_trust_items_limit_when_rendering_scope():
    scope_path = STATIC_DIR / "report_quality_queue_scope_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__SCOPE_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 2,
  quality_metadata_missing_reports: 2,
  items_total: 2,
  items_returned: 2,
  items_limit: 1,
  items_truncated: false,
  items: [{ ticker: 'AAA', filename: 'aaa.html' }, { ticker: 'BBB', filename: 'bbb.html' }]
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__SCOPE_PATH__", json.dumps(str(scope_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "目前顯示 2/2；範圍資料需確認" in payload["html"]
    assert "2 份品質 metadata 缺口（目前顯示 2 份，另有 0 份未展開）" not in payload["html"]


def test_history_quality_audit_rejects_missing_count_above_audited_scope():
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 2,
  quality_metadata_missing_reports: 3,
  items_total: 3,
  items_returned: 0,
  items_limit: 5,
  items_truncated: true,
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "範圍：2 份" in payload["html"]
    assert "品質 metadata 範圍資料需確認" in payload["html"]
    assert "3 份品質 metadata 缺口" not in payload["html"]


def test_history_quality_audit_rejects_missing_count_above_verified_scope():
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 10,
  verified_snapshot_reports: 1,
  quality_metadata_missing_reports: 2,
  items_total: 2,
  items_returned: 0,
  items_limit: 5,
  items_truncated: true,
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "範圍：10 份" in payload["html"]
    assert "品質 metadata 範圍資料需確認" in payload["html"]
    assert "2 份品質 metadata 缺口" not in payload["html"]


def test_history_quality_audit_rejects_inconsistent_complete_scope():
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 10,
  verified_snapshot_reports: 10,
  quality_metadata_complete_reports: 9,
  quality_metadata_missing_reports: 0,
  items_total: 0,
  items_returned: 0,
  items_limit: 5,
  items_truncated: false,
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "品質 metadata 範圍資料需確認" in payload["html"]
    assert "符合條件的 9 份已驗證 snapshot 沒有品質 metadata 缺口" not in payload["html"]


def test_history_quality_audit_rejects_inconsistent_snapshot_scope():
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 10,
  verified_snapshot_reports: 10,
  snapshot_invalid_reports: 1,
  snapshot_unverified_reports: 0,
  quality_metadata_complete_reports: 10,
  quality_metadata_missing_reports: 0,
  items_total: 0,
  items_returned: 0,
  items_limit: 5,
  items_truncated: false,
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "品質 metadata 範圍資料需確認" in payload["html"]
    assert "snapshot 無法驗證" not in payload["html"]


def test_history_quality_audit_rejects_returned_count_above_actual_items():
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 10,
  verified_snapshot_reports: 10,
  quality_metadata_complete_reports: 5,
  quality_metadata_missing_reports: 5,
  items_total: 5,
  items_returned: 5,
  items_limit: 5,
  items_truncated: false,
  items: [{ ticker: 'AAA', filename: 'aaa.html' }, { ticker: 'BBB', filename: 'bbb.html' }]
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "品質 metadata 範圍資料需確認" in payload["html"]
    assert "5 份品質 metadata 缺口" not in payload["html"]


def test_history_quality_audit_rejects_item_total_different_from_missing_scope():
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 10,
  verified_snapshot_reports: 10,
  quality_metadata_complete_reports: 5,
  quality_metadata_missing_reports: 5,
  items_total: 3,
  items_returned: 3,
  items_limit: 5,
  items_truncated: false,
  items: [{ ticker: 'AAA', filename: 'aaa.html' }, { ticker: 'BBB', filename: 'bbb.html' }, { ticker: 'CCC', filename: 'ccc.html' }]
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "品質 metadata 範圍資料需確認" in payload["html"]
    assert "5 份品質 metadata 缺口" not in payload["html"]


def test_history_quality_audit_rejects_offset_outside_item_scope():
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 10,
  verified_snapshot_reports: 10,
  quality_metadata_complete_reports: 5,
  quality_metadata_missing_reports: 5,
  items_offset: 99,
  items_total: 5,
  items_returned: 1,
  items_limit: 5,
  items_truncated: true,
  items: [{ ticker: 'AAA', filename: 'aaa.html' }]
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "品質 metadata 範圍資料需確認" in payload["html"]
    assert "第 100-5 份" not in payload["html"]


def test_history_quality_audit_hides_inconsistent_pipeline_missing_scope():
    scope_path = STATIC_DIR / "report_quality_audit_scope_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__SCOPE_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 5,
  quality_metadata_missing_reports: 3,
  quality_metadata_by_pipeline: {
    v1: { quality_metadata_missing_reports: 1, quality_metadata_missing_by_rerun_context: { artifact_fallback_available: 1 } },
    v2: { quality_metadata_missing_reports: 1 }
  },
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__SCOPE_PATH__", json.dumps(str(scope_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "3 份品質 metadata 缺口" in payload["html"]
    assert "模式缺口：" not in payload["html"]
    assert "模式上下文：" not in payload["html"]


def test_history_quality_audit_hides_inconsistent_pipeline_context_scope():
    scope_path = STATIC_DIR / "report_quality_audit_scope_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__SCOPE_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 5,
  quality_metadata_missing_reports: 2,
  quality_metadata_by_pipeline: {
    v1: { quality_metadata_missing_reports: 1, quality_metadata_missing_by_rerun_context: { present: 2 } },
    v2: { quality_metadata_missing_reports: 1, quality_metadata_missing_by_rerun_context: { present: 1 } }
  },
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__SCOPE_PATH__", json.dumps(str(scope_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "2 份品質 metadata 缺口" in payload["html"]
    assert "模式缺口：v1 1、v2 1" in payload["html"]
    assert "模式上下文：" not in payload["html"]


def test_history_quality_audit_hides_inconsistent_quality_distributions():
    scope_path = STATIC_DIR / "report_quality_audit_scope_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__SCOPE_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 5,
  quality_metadata_missing_reports: 2,
  quality_metadata_missing_by_provenance: { before_refresh: 1 },
  quality_metadata_missing_by_rerun_execution: { full_rerun_required: 3 },
  quality_metadata_missing_by_rerun_context: { artifact_fallback_available: 1 },
  quality_review_by_status: { pending: 1, approved_with_gap: 0, rejected: 0, deferred: 0 },
  quality_metadata_missing_by_version_status: { current: 1 },
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__SCOPE_PATH__", json.dumps(str(scope_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "2 份品質 metadata 缺口" in payload["html"]
    assert "來源：" not in payload["html"]
    assert "重跑策略：" not in payload["html"]
    assert "上下文：" not in payload["html"]
    assert "審核狀態：" not in payload["html"]
    assert "目前版本缺口" not in payload["html"]


def test_history_quality_audit_does_not_floor_fractional_or_malformed_counts():
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 10.5,
  quality_metadata_missing_reports: 2.5,
  verified_snapshot_reports: 9.5,
  quality_metadata_complete_reports: 7.5,
  snapshot_invalid_reports: 1.5,
  snapshot_unverified_reports: 0.5,
  missing_quality_field_counts: { report_conformance: 1.5, evidence_exit_gate: Infinity, content_credibility: 0.5 },
  quality_metadata_missing_by_provenance: { before_refresh: 1.5 },
  quality_metadata_missing_by_rerun_execution: { full_rerun_required: 1.5 },
  quality_metadata_missing_by_rerun_context: { missing: 1.5 },
  quality_review_by_status: { pending: 1.5 },
  quality_metadata_missing_by_version_status: { current: 1.5 },
  artifact_quality_summary_by_status: { present: 1.5 },
  artifact_quality_summary_by_field: { report_conformance: 1.5 },
  quality_metadata_by_pipeline: { v1: { quality_metadata_missing_reports: 1.5 } },
  items_total: 2.5,
  items_returned: 1.5,
  items_limit: 1.5,
  items_truncated: true,
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "範圍：10 份" not in payload["html"]
    assert "範圍：資料需確認" in payload["html"]
    assert "品質 metadata 範圍資料需確認" in payload["html"]
    assert "snapshot 無法驗證" not in payload["html"]
    assert "2 份品質 metadata 缺口" not in payload["html"]
    assert "報告一致性 1" not in payload["html"]
    assert "模式缺口：v1 1" not in payload["html"]
    assert "版本：目前版本缺口 1" not in payload["html"]
    assert "審核狀態：待人工核對 1" not in payload["html"]
    assert "來源：刷新前已有缺口 1" not in payload["html"]
    assert "重跑策略：完整重跑 1" not in payload["html"]
    assert "上下文：無可用局部上下文 1" not in payload["html"]
    assert "artifact 摘要可查 1 份" not in payload["html"]
    assert "1.5" not in payload["html"]
    assert "2.5" not in payload["html"]


def test_history_current_quality_rejects_malformed_evidence_distribution():
    helper_path = STATIC_DIR / "history_current_quality_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const summary = {
  schema_version: 'report_current_quality_summary.v1',
  scope: 'historical_filter_current_latest',
  selection_basis: 'latest_per_ticker_pipeline',
  audited_reports: 1,
  non_passed_reports: 0,
  items_total: 0,
  items_returned: 0,
  report_conformance_by_status: { passed: 1, warning: 0, blocked: 0, unknown: 0 },
  content_credibility_by_status: { passed: 1, warning: 0, blocked: 0, unknown: 0 },
  evidence_exit_gate_by_verdict: { approved: 1.5, caution: -0.5, rejected: 0, unknown: 0 },
  items: []
};
process.stdout.write(JSON.stringify({
  validated: window.StockAgentHistoricalCurrentQualityHelpers.validated(summary),
  html: window.StockAgentHistoricalCurrentQualityHelpers.render(summary, value => String(value ?? ''))
}));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["validated"] is None
    assert payload["html"] == ""


def test_history_quality_review_does_not_floor_fractional_event_or_filter_counts():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const reviewHtml = window.StockAgentHistoryPanelQualityHelpers.renderQualityReview({
  filename: 'bad.html',
  ticker: 'BAD',
  pipeline_id: 'v1',
  report_quality_revision: 'revision-1234567890',
  quality_review: { status: 'approved_with_gap', decision_label: '已核准保留缺口', event_count: 2.5 },
  quality_review_history: [{ event_id: 3.5, reviewed_at: '2026-09-02', reviewer_label: '操作員', decision_label: '已核准保留缺口', note: 'note' }]
}, 'BAD v1', value => String(value ?? ''));
const filterHtml = [
  window.StockAgentHistoryPanelQualityHelpers.renderQualityReviewStatusFilters({ quality_review_by_status: { pending: 1.5, approved_with_gap: Infinity, rejected: 0, deferred: 0 } }, value => String(value ?? '')),
  window.StockAgentHistoryPanelQualityHelpers.renderQualityMissingFieldFilters({ missing_quality_field_counts: { report_conformance: 1.5, evidence_exit_gate: Infinity, content_credibility: 0 } }, value => String(value ?? '')),
  window.StockAgentHistoryPanelQualityHelpers.renderQualityVersionStatusFilters({ quality_metadata_missing_by_version_status: { current: 1.5, historical: Infinity, unknown: 0 } }, value => String(value ?? ''))
].join('');
process.stdout.write(JSON.stringify({ reviewHtml, filterHtml }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "第 2 次" not in payload["reviewHtml"]
    assert "#3" not in payload["reviewHtml"]
    assert "1.5" not in payload["filterHtml"]
    assert "Infinity" not in payload["filterHtml"]
    assert "（1）" not in payload["filterHtml"]


def test_history_quality_audit_prioritizes_scope_warning_over_page_range():
    scope_path = STATIC_DIR / "report_quality_queue_scope_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__SCOPE_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 4,
  quality_metadata_missing_reports: 4,
  items_total: 4,
  items_returned: 2,
  items_limit: 1,
  items_offset: 2,
  items_truncated: true,
  items: [{ ticker: 'AAA', filename: 'aaa.html' }, { ticker: 'BBB', filename: 'bbb.html' }]
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__SCOPE_PATH__", json.dumps(str(scope_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "目前顯示 2/4；範圍資料需確認" in payload["html"]
    assert "目前顯示第 3-4 份，共 4 份" not in payload["html"]


def test_history_current_quality_rejects_items_above_total():
    helper_path = STATIC_DIR / "history_current_quality_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const result = window.StockAgentHistoricalCurrentQualityHelpers.validated({
  schema_version: 'report_current_quality_summary.v1',
  scope: 'historical_filter_current_latest',
  selection_basis: 'latest_per_ticker_pipeline',
  audited_reports: 1,
  non_passed_reports: 0,
  items_total: 0,
  items_returned: 1,
  report_conformance_by_status: { passed: 1, warning: 0, blocked: 0, unknown: 0 },
  content_credibility_by_status: { passed: 1, warning: 0, blocked: 0, unknown: 0 },
  evidence_exit_gate_by_verdict: { approved: 1, caution: 0, rejected: 0, unknown: 0 },
  items: [{ ticker: 'BAD', pipeline_id: 'v1', filename: 'bad.html' }]
});
process.stdout.write(JSON.stringify({ valid: Boolean(result) }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["valid"] is False


def test_history_current_quality_rejects_fractional_counts():
    helper_path = STATIC_DIR / "history_current_quality_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const result = window.StockAgentHistoricalCurrentQualityHelpers.validated({
  schema_version: 'report_current_quality_summary.v1',
  scope: 'historical_filter_current_latest',
  selection_basis: 'latest_per_ticker_pipeline',
  audited_reports: 1.5,
  non_passed_reports: 1.5,
  items_total: 1.5,
  items_returned: 0,
  report_conformance_by_status: { passed: 0.5, warning: 1, blocked: 0, unknown: 0 },
  content_credibility_by_status: { passed: 0.5, warning: 1, blocked: 0, unknown: 0 },
  evidence_exit_gate_by_verdict: { approved: 0.5, caution: 1, rejected: 0, unknown: 0 },
  items: []
});
process.stdout.write(JSON.stringify({ valid: Boolean(result) }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["valid"] is False


def test_history_current_quality_does_not_floor_fractional_evidence_failed_count():
    helper_path = STATIC_DIR / "history_current_quality_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const html = window.StockAgentHistoricalCurrentQualityHelpers.render({
  schema_version: 'report_current_quality_summary.v1',
  scope: 'historical_filter_current_latest',
  selection_basis: 'latest_per_ticker_pipeline',
  audited_reports: 1,
  non_passed_reports: 1,
  items_total: 1,
  items_returned: 0,
  report_conformance_by_status: { passed: 0, warning: 1, blocked: 0, unknown: 0 },
  content_credibility_by_status: { passed: 1, warning: 0, blocked: 0, unknown: 0 },
  evidence_exit_gate_by_verdict: { approved: 0, caution: 1, rejected: 0, unknown: 0 },
  evidence_failed_count: 1.5,
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "一致性 符合 0、警示 1" in payload["html"]
    assert "證據數值不一致" not in payload["html"]


def test_history_quality_audit_renders_missing_field_scope_and_filters():
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
  missing_quality_field_counts: { report_conformance: 143, evidence_exit_gate: 143, content_credibility: 143 },
  missing_quality_field_filter: 'content_credibility',
  quality_review_by_status: { pending: 143, approved_with_gap: 0, rejected: 0, deferred: 0 },
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "缺口範圍：內容可信度" in payload["html"]
    assert 'data-quality-audit-missing-field="content_credibility"' in payload["html"]
    assert "只看內容可信度缺口" in payload["html"]
    assert 'data-quality-audit-missing-field="all"' in payload["html"]


def test_history_quality_audit_renders_pre_refresh_provenance():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 1,
  quality_metadata_missing_reports: 1,
  quality_metadata_missing_by_provenance: { before_refresh: 1, after_refresh: 0, no_refresh_provenance: 0 },
  missing_quality_field_counts: { report_conformance: 1, evidence_exit_gate: 0, content_credibility: 0 },
  quality_review_by_status: { pending: 1, approved_with_gap: 0, rejected: 0, deferred: 0 },
  items: [{
    ticker: '1623.TW',
    filename: '1623_v1.html',
    pipeline_id: 'v1',
    title: '刷新前已有品質證據缺口',
    detail: '刷新前快照已確認缺少報告一致性品質證據。',
    missing_quality_fields: ['report_conformance'],
    reason_codes: ['quality_metadata_missing', 'quality_metadata_before_refresh'],
    quality_metadata_provenance: 'before_refresh'
  }]
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "來源：刷新前已有缺口 1" in payload["html"]
    assert "來源：刷新前已有缺口" in payload["html"]


def test_history_quality_audit_renders_rerun_execution_summary():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 3,
  quality_metadata_missing_reports: 3,
  quality_metadata_missing_by_rerun_execution: {
    full_rerun_required: 2,
    partial_rerun_available: 1,
    partial_rerun_review_required: 0,
    partial_rerun_unavailable: 0
  },
  missing_quality_field_counts: { report_conformance: 3, evidence_exit_gate: 3, content_credibility: 3 },
  quality_review_by_status: { pending: 3, approved_with_gap: 0, rejected: 0, deferred: 0 },
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "重跑策略：完整重跑 2、局部重跑可用 1" in payload["html"]


def test_history_quality_audit_filtered_missing_field_empty_state_keeps_scope_semantics():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 0,
  quality_metadata_missing_reports: 0,
  quality_metadata_coverage_pct: 100,
  quality_metadata_coverage_basis: 'verified_snapshot_reports',
  missing_quality_field_counts: { report_conformance: 0, evidence_exit_gate: 0, content_credibility: 0 },
  missing_quality_field_filter: 'content_credibility',
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "目前沒有符合「內容可信度」的品質 metadata 缺口" in payload["html"]
    assert "符合條件的 0 份已驗證 snapshot 沒有品質 metadata 缺口" not in payload["html"]


def test_history_quality_audit_renders_both_review_and_missing_field_scopes():
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
  missing_quality_field_counts: { report_conformance: 143, evidence_exit_gate: 143, content_credibility: 143 },
  missing_quality_field_filter: 'content_credibility',
  review_status_filter: 'pending',
  quality_review_by_status: { pending: 143, approved_with_gap: 0, rejected: 0, deferred: 0 },
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "審核範圍：待人工核對" in payload["html"]
    assert "缺口範圍：內容可信度" in payload["html"]
    assert payload["html"].index('class="history-quality-audit-summary-scope"') < payload["html"].index('class="history-quality-audit-summary-item"')
    assert payload["html"].count('class="history-quality-audit-summary-item"') == 3


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


def test_history_quality_audit_keeps_zero_count_current_status_filter_recoverable():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const html = window.StockAgentHistoryPanelQualityHelpers.renderQualityReviewStatusFilters({
  review_status_filter: 'pending',
  quality_review_by_status: { pending: 0, approved_with_gap: 0, rejected: 0, deferred: 0 }
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert 'data-quality-audit-review-status="pending"' in payload["html"]
    assert "待人工核對（0）" in payload["html"]
    assert 'data-quality-audit-review-status="all"' in payload["html"]


def test_history_quality_audit_filtered_empty_state_does_not_claim_zero_complete_reports():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 0,
  verified_snapshot_reports: 0,
  quality_metadata_complete_reports: 0,
  quality_metadata_missing_reports: 0,
  quality_metadata_coverage_pct: 0,
  quality_metadata_coverage_basis: 'verified_snapshot_reports',
  review_status_filter: 'pending',
  quality_review_by_status: { pending: 0, approved_with_gap: 0, rejected: 0, deferred: 0 },
  items: []
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "目前沒有符合「待人工核對」的品質 metadata 缺口" in payload["html"]
    assert "符合條件的 0 份已驗證 snapshot 沒有品質 metadata 缺口" not in payload["html"]


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


def test_history_quality_audit_missing_field_shortcut_reloads_field_filter():
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
        return { audited_reports: 1, quality_metadata_missing_reports: 1, missing_quality_field_counts: { pending: 1 }, items: [] };
      }
    },
    ui: { escapeHtml: value => String(value ?? '') },
    element
  });
  audit.bindEvents();
  await audit.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  await clickHandler({ target: { closest: selector => selector === '[data-quality-audit-missing-field]' ? { dataset: { qualityAuditMissingField: 'content_credibility' } } : null } });
  process.stdout.write(JSON.stringify({ captured }));
})();
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["captured"] == [
        {"itemLimit": 5, "itemOffset": 0, "query": "", "pipeline": "all"},
        {"itemLimit": 5, "itemOffset": 0, "query": "", "pipeline": "all", "missingField": "content_credibility"},
    ]


def test_history_quality_audit_version_shortcut_reloads_version_filter():
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
    apiClient: { fetchHistoricalReportQualityAudit: async params => { captured.push(params); return { audited_reports: 1, quality_metadata_missing_reports: 1, items: [] }; } },
    ui: { escapeHtml: value => String(value ?? '') },
    element
  });
  audit.bindEvents();
  await audit.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  await clickHandler({ target: { closest: selector => selector === '[data-quality-audit-version-status]' ? { dataset: { qualityAuditVersionStatus: 'historical' } } : null } });
  process.stdout.write(JSON.stringify({ captured }));
})();
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["captured"] == [
        {"itemLimit": 5, "itemOffset": 0, "query": "", "pipeline": "all"},
        {"itemLimit": 5, "itemOffset": 0, "query": "", "pipeline": "all", "versionStatus": "historical"},
    ]


def test_history_quality_audit_restores_persisted_version_filter():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = {};
  window.sessionStorage = {
    getItem: () => JSON.stringify({ versionStatus: 'historical' }),
    setItem: () => {},
    removeItem: () => {}
  };
  require(__HELPER_PATH__);
  require(__RENDERER_PATH__);
  require(__MODULE_PATH__);
  const captured = [];
  const element = { hidden: true, innerHTML: '', setAttribute: () => {}, removeAttribute: () => {}, addEventListener: () => {} };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: { fetchHistoricalReportQualityAudit: async params => { captured.push(params); return { audited_reports: 1, quality_metadata_missing_reports: 1, items: [] }; } },
    ui: { escapeHtml: value => String(value ?? '') },
    element
  });
  await audit.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  process.stdout.write(JSON.stringify({ captured }));
})();
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["captured"] == [{
        "itemLimit": 5,
        "itemOffset": 0,
        "query": "",
        "pipeline": "all",
        "versionStatus": "historical",
    }]


def test_history_quality_audit_persists_filters_across_reload_and_reset_clears_them():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = {};
  const storage = {};
  window.sessionStorage = {
    getItem: key => Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null,
    setItem: (key, value) => { storage[key] = String(value); },
    removeItem: key => { delete storage[key]; }
  };
  require(__HELPER_PATH__);
  require(__RENDERER_PATH__);
  require(__MODULE_PATH__);
  const captured = [];
  const makeElement = () => ({
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: (type, handler) => { if (type === 'click') elementHandler = handler; }
  });
  let elementHandler;
  const apiClient = {
    fetchHistoricalReportQualityAudit: async params => {
      captured.push(params);
      return {
        audited_reports: 1,
        quality_metadata_missing_reports: 1,
        missing_quality_field_counts: { report_conformance: 1, evidence_exit_gate: 1, content_credibility: 1 },
        quality_review_by_status: { pending: 1, approved_with_gap: 0, rejected: 0, deferred: 0 },
        review_status_filter: params.reviewStatus || 'all',
        missing_quality_field_filter: params.missingField || 'all',
        items: []
      };
    }
  };
  const first = window.StockAgentHistoricalQualityAudit.create({ apiClient, ui: { escapeHtml: value => String(value ?? '') }, element: makeElement() });
  first.bindEvents();
  await first.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  await elementHandler({ target: { closest: selector => selector === '[data-quality-audit-missing-field]' ? { dataset: { qualityAuditMissingField: 'content_credibility' } } : null } });
  await elementHandler({ target: { closest: selector => selector === '[data-quality-audit-review-status]' ? { dataset: { qualityAuditReviewStatus: 'pending' } } : null } });

  const second = window.StockAgentHistoricalQualityAudit.create({ apiClient, ui: { escapeHtml: value => String(value ?? '') }, element: makeElement() });
  await second.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  first.resetReviewStatus();
  const third = window.StockAgentHistoricalQualityAudit.create({ apiClient, ui: { escapeHtml: value => String(value ?? '') }, element: makeElement() });
  await third.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  process.stdout.write(JSON.stringify({ captured }));
})();
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["captured"][3] == {
        "itemLimit": 5,
        "itemOffset": 0,
        "query": "",
        "pipeline": "all",
        "reviewStatus": "pending",
        "missingField": "content_credibility",
    }
    assert payload["captured"][4] == {
        "itemLimit": 5,
        "itemOffset": 0,
        "query": "",
        "pipeline": "all",
    }


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
    assert "/static/api_client_extensions.js?v=20260821-current-quality-summary" in index_html
    assert "/static/watchlist_panel_actions.js?v=20260821-current-quality-background" in index_html
    assert "/static/history_panel_quality_helpers.js?v=20260902-integer-review-counts" in index_html
    assert "/static/history_quality_audit_render.js?v=20260902-distribution-scope" in index_html
    assert "/static/history_quality_audit.js?v=20260820-quality-version-filter" in index_html
    assert index_html.index("/static/history_quality_audit_render.js") < index_html.index("/static/history_quality_audit.js")
    assert len((STATIC_DIR / "history_panel_quality_helpers.js").read_text(encoding="utf-8").splitlines()) < 120
    assert len((STATIC_DIR / "history_quality_audit_render.js").read_text(encoding="utf-8").splitlines()) < 100
    assert "fetchHistoricalReportQualityAudit" in api_client
    assert "sessionStorage" in (STATIC_DIR / "history_quality_audit.js").read_text(encoding="utf-8")
    assert "historyQualityAudit" in app_elements
    assert "historyQualityAudit" in app_panels
    assert "qualityAudit.load(values)" in workspace
    assert "onSelectPipeline" in workspace
    assert "historyPipelineFilter.value = pipeline" in workspace
    assert "data-quality-audit-report" in workspace or "qualityAudit.bindEvents()" in workspace
