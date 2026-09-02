import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def _node(script: str) -> str:
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    return result.stdout


def test_report_reading_boundary_covers_missing_partial_blocked_and_passed_reports():
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
const reports = [
  { name: 'pending', data_trust: { status: 'fresh' } },
  { name: 'warning', data_trust: { status: 'stale' }, report_conformance: { status: 'warning' } },
  { name: 'blocked', data_trust: { status: 'fresh' }, content_credibility: { status: 'blocked' } },
  { name: 'passed', data_trust: { status: 'fresh' }, evidence_exit_gate: { verdict: 'approved' }, content_credibility: { status: 'passed' }, report_conformance: { status: 'passed' } }
];
process.stdout.write(JSON.stringify(reports.map(report => ({ name: report.name, boundary: window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report) }))));
""".replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    payload = json.loads(_node(script))
    states = {item["name"]: item["boundary"]["state"] for item in payload}

    assert states == {
        "pending": "pending",
        "warning": "warning",
        "blocked": "blocked",
        "passed": "passed",
    }
    assert payload[0]["boundary"]["label"] == "品質 gate 尚未記錄"
    assert "勿直接採用" in payload[2]["boundary"]["detail"]
    assert "不代表投資語意一定正確" in payload[3]["boundary"]["detail"]


def test_report_quality_policy_treats_empty_gate_objects_as_missing_metadata():
    gate_path = STATIC_DIR / "report_quality_gate_policy.js"
    policy_path = STATIC_DIR / "report_quality_policy.js"
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__GATE_PATH__);
require(__POLICY_PATH__);
require(__BOUNDARY_PATH__);
const report = {
  filename: '1623_v1.html',
  data_trust: { status: 'partial' },
  snapshot_integrity: { status: 'verified' },
  report_conformance: {},
  evidence_exit_gate: {},
  content_credibility: {}
};
const action = window.StockAgentReportQualityPolicy.reportRecommendedAction(report);
const gate = window.StockAgentReportQualityGatePolicy.reportQualityGateAction(report);
const boundary = window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report);
process.stdout.write(JSON.stringify({ action, gate, boundary }));
""".replace("__GATE_PATH__", json.dumps(str(gate_path))).replace("__POLICY_PATH__", json.dumps(str(policy_path))).replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    payload = json.loads(_node(script))

    assert payload["action"] == {"type": "manual_review", "filename": "1623_v1.html"}
    assert payload["gate"]["label"] == "品質證據未記錄"
    assert payload["gate"]["tone"] == "critical"
    assert payload["boundary"]["state"] == "pending"
    assert payload["boundary"]["label"] == "品質 gate 尚未記錄"


def test_report_quality_policies_treat_unrecognized_gate_states_as_unrecorded():
    gate_path = STATIC_DIR / "report_quality_gate_policy.js"
    policy_path = STATIC_DIR / "report_quality_policy.js"
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__GATE_PATH__);
require(__POLICY_PATH__);
require(__BOUNDARY_PATH__);
const base = { filename: 'future-status.html', data_trust: { status: 'fresh' }, snapshot_integrity: { status: 'verified' } };
const reports = [
  {
    name: 'all-unknown',
    ...base,
    report_conformance: { status: 'future' },
    evidence_exit_gate: { verdict: 'experimental' },
    content_credibility: { status: 'legacy' }
  },
  {
    name: 'partial-unknown',
    ...base,
    report_conformance: { status: 'future' },
    evidence_exit_gate: { verdict: 'approved' },
    content_credibility: { status: 'passed' }
  },
  {
    name: 'uppercase-known',
    ...base,
    report_conformance: { status: 'PASSED' },
    evidence_exit_gate: { verdict: 'APPROVED' },
    content_credibility: { status: 'PASSED' }
  },
  {
    name: 'uppercase-verified-missing',
    ...base,
    snapshot_integrity: { status: 'VERIFIED' },
    report_conformance: { status: 'PASSED' },
    evidence_exit_gate: { verdict: 'APPROVED' },
    content_credibility: {}
  }
];
process.stdout.write(JSON.stringify(reports.map(report => ({
  name: report.name,
  gate: window.StockAgentReportQualityGatePolicy.reportQualityGateAction(report),
  boundary: window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report)
}))));
""".replace("__GATE_PATH__", json.dumps(str(gate_path))).replace("__POLICY_PATH__", json.dumps(str(policy_path))).replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    payload = json.loads(_node(script))

    all_unknown = payload[0]
    partial_unknown = payload[1]
    assert all_unknown["gate"]["label"] == "品質證據未記錄"
    assert all_unknown["boundary"]["state"] == "pending"
    assert partial_unknown["gate"]["label"] == "品質證據未記錄"
    assert partial_unknown["boundary"]["state"] == "warning"
    assert payload[2]["gate"] is None
    assert payload[2]["boundary"]["state"] == "passed"
    assert payload[3]["gate"]["label"] == "品質證據未記錄"
    assert payload[3]["boundary"]["state"] == "warning"


def test_report_reading_boundary_blocks_case_insensitive_invalid_snapshot_status():
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
const report = {
  data_trust: { status: 'fresh' },
  evidence_exit_gate: { verdict: 'approved' },
  content_credibility: { status: 'passed' },
  report_conformance: { status: 'passed' },
  snapshot_integrity: { status: ' INVALID ' }
};
process.stdout.write(JSON.stringify(window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report)));
""".replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    boundary = json.loads(_node(script))

    assert boundary["state"] == "blocked"
    assert "品質 gate 未通過" in boundary["label"]


def test_report_quality_gate_normalizes_injected_quality_helpers():
    gate_path = STATIC_DIR / "report_quality_gate_policy.js"
    script = """
global.window = {};
require(__GATE_PATH__);
const report = {
  snapshot_integrity: { status: 'verified' },
  report_conformance: { status: 'warning' },
  evidence_exit_gate: { verdict: 'caution' },
  content_credibility: { status: 'passed' }
};
const action = window.StockAgentReportQualityGatePolicy.reportQualityGateAction(report, {
  reportConformanceStatus: () => ' WARNING ',
  evidenceExitGateVerdict: () => ' CAUTION '
});
process.stdout.write(JSON.stringify(action));
""".replace("__GATE_PATH__", json.dumps(str(gate_path)))

    action = json.loads(_node(script))

    assert action["label"] == "報告符合性需確認"


def test_report_facing_data_trust_and_freshness_states_normalize_whitespace_and_case():
    policy_path = STATIC_DIR / "report_quality_policy.js"
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    ui_data_trust_path = STATIC_DIR / "ui_data_trust.js"
    script = """
global.window = {};
require(__POLICY_PATH__);
require(__BOUNDARY_PATH__);
require(__UI_DATA_TRUST_PATH__);
const errorReport = { filename: 'error.html', data_trust: { status: ' ERROR ' } };
const freshReport = {
  filename: 'fresh.html',
  data_trust: { status: ' FRESH ' },
  decision_freshness: { status: ' CURRENT ' },
  snapshot_integrity: { status: ' VERIFIED ' },
  report_conformance: { status: ' PASSED ' },
  evidence_exit_gate: { verdict: ' APPROVED ' },
  content_credibility: { status: ' PASSED ' }
};
process.stdout.write(JSON.stringify({
  errorStatus: window.StockAgentReportQualityPolicy.dataTrustStatus(errorReport),
  errorAction: window.StockAgentReportQualityPolicy.reportRecommendedAction(errorReport),
  errorNeedsAction: window.StockAgentReportQualityPolicy.requiresDataTrustAction(errorReport),
  freshStatus: window.StockAgentReportQualityPolicy.dataTrustStatus(freshReport),
  freshData: window.StockAgentReportQualityPolicy.reportHasFreshData(freshReport),
  freshnessLabel: window.StockAgentReportQualityPolicy.decisionFreshnessStatusLabel(freshReport.decision_freshness),
  boundary: window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(freshReport),
  errorLabel: window.StockAgentUiDataTrust.dataTrustLabel(errorReport.data_trust),
  freshClass: window.StockAgentUiDataTrust.dataTrustClass(freshReport.data_trust)
}));
""".replace("__POLICY_PATH__", json.dumps(str(policy_path))).replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path))).replace("__UI_DATA_TRUST_PATH__", json.dumps(str(ui_data_trust_path)))

    payload = json.loads(_node(script))

    assert payload["errorStatus"] == "error"
    assert payload["errorAction"] == {"type": "manual_review", "filename": "error.html"}
    assert payload["errorNeedsAction"] is True
    assert payload["freshStatus"] == "fresh"
    assert payload["freshData"] is True
    assert payload["freshnessLabel"] == "有效"
    assert payload["boundary"]["state"] == "passed"
    assert payload["errorLabel"] == "本報告來源異常"
    assert payload["freshClass"] == "fresh"


def test_report_quality_actions_surface_invalid_snapshot_integrity_for_manual_review():
    gate_path = STATIC_DIR / "report_quality_gate_policy.js"
    policy_path = STATIC_DIR / "report_quality_policy.js"
    script = """
global.window = {};
require(__GATE_PATH__);
require(__POLICY_PATH__);
const report = {
  filename: 'invalid-snapshot.html',
  data_trust: { status: 'fresh' },
  snapshot_integrity: { status: ' INVALID ', errors: ['snapshot_hash mismatch'] },
  report_conformance: { status: 'passed' },
  evidence_exit_gate: { verdict: 'approved' },
  content_credibility: { status: 'passed' }
};
const contradictory = { ...report, snapshot_integrity: { status: 'verified', valid: false } };
const hashOnly = { ...report, snapshot_integrity: { status: 'invalid', hash: 'actual', expected_hash: 'expected' } };
process.stdout.write(JSON.stringify({
  gate: window.StockAgentReportQualityGatePolicy.reportQualityGateAction(report),
  contradictoryGate: window.StockAgentReportQualityGatePolicy.reportQualityGateAction(contradictory),
  hashOnlyGate: window.StockAgentReportQualityGatePolicy.reportQualityGateAction(hashOnly),
  action: window.StockAgentReportQualityPolicy.reportRecommendedAction(report),
  requiresAction: window.StockAgentReportQualityPolicy.requiresDataTrustAction(report)
}));
""".replace("__GATE_PATH__", json.dumps(str(gate_path))).replace("__POLICY_PATH__", json.dumps(str(policy_path)))

    payload = json.loads(_node(script))

    assert payload["gate"] == {
        "label": "資料快照完整性未通過",
        "tone": "critical",
        "detail": "snapshot_hash mismatch",
    }
    assert payload["contradictoryGate"]["tone"] == "critical"
    assert payload["hashOnlyGate"]["detail"] == "snapshot_hash mismatch"
    assert payload["action"] == {"type": "manual_review", "filename": "invalid-snapshot.html"}
    assert payload["requiresAction"] is True


def test_report_quality_gate_exposes_structured_gap_and_artifact_evidence_boundary():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    gate_path = STATIC_DIR / "report_quality_gate_policy.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
require(__GATE_PATH__);
const report = {
  snapshot_integrity: { status: 'verified' },
  missing_quality_fields: ['report_conformance', 'evidence_exit_gate', 'content_credibility'],
  quality_metadata_provenance: 'after_refresh',
  artifact_quality_summary: {
    status: 'present',
    source: 'markdown',
    fields: ['report_conformance', 'evidence_exit_gate']
  }
};
process.stdout.write(JSON.stringify(window.StockAgentReportQualityGatePolicy.reportQualityGateAction(report)));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__GATE_PATH__", json.dumps(str(gate_path)))

    payload = json.loads(_node(script))

    assert payload["label"] == "結構化品質缺口"
    assert "結構化品質 metadata：報告一致性、證據關卡、內容可信度" in payload["detail"]
    assert "artifact 摘要可查：報告一致性、證據關卡" in payload["detail"]
    assert "不代表 gate 已通過" in payload["detail"]


def test_report_reading_boundary_downgrades_unverified_and_blocks_invalid_snapshots():
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
const base = {
  data_trust: { status: 'fresh' },
  evidence_exit_gate: { verdict: 'approved' },
  content_credibility: { status: 'passed' },
  report_conformance: { status: 'passed' }
};
const reports = [
  { name: 'invalid', ...base, snapshot_integrity: { status: 'invalid', errors: ['snapshot_hash mismatch'] } },
  { name: 'unverified', ...base, snapshot_integrity: { status: 'unverified' } },
  { name: 'verified', ...base, snapshot_integrity: { status: 'verified' } }
];
process.stdout.write(JSON.stringify(reports.map(report => ({ name: report.name, boundary: window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report) }))));
""".replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    payload = json.loads(_node(script))
    states = {item["name"]: item["boundary"]["state"] for item in payload}

    assert states == {
        "invalid": "blocked",
        "unverified": "warning",
        "verified": "passed",
    }
    assert "品質 gate 未通過" in payload[0]["boundary"]["label"]
    assert "先核對" in payload[1]["boundary"]["detail"]


def test_report_reading_boundary_blocks_false_valid_snapshot_integrity():
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
const report = {
  data_trust: { status: 'fresh' },
  evidence_exit_gate: { verdict: 'approved' },
  content_credibility: { status: 'passed' },
  report_conformance: { status: 'passed' },
  snapshot_integrity: { status: 'verified', valid: false, errors: 'snapshot_hash mismatch' }
};
process.stdout.write(JSON.stringify(window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report)));
""".replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    boundary = json.loads(_node(script))

    assert boundary["state"] == "blocked"
    assert "品質 gate 未通過" in boundary["label"]
    assert "snapshot_hash mismatch" in boundary["detail"]


def test_report_reading_boundary_includes_snapshot_integrity_error_detail():
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
const report = {
  data_trust: { status: 'fresh' },
  evidence_exit_gate: { verdict: 'approved' },
  content_credibility: { status: 'passed' },
  report_conformance: { status: 'passed' },
  snapshot_integrity: { status: 'invalid', errors: 'snapshot_hash mismatch' }
};
process.stdout.write(JSON.stringify(window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report)));
""".replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    boundary = json.loads(_node(script))

    assert boundary["state"] == "blocked"
    assert "snapshot_hash mismatch" in boundary["detail"]


def test_report_reading_boundary_derives_snapshot_hash_mismatch_detail_from_hashes():
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
const report = {
  data_trust: { status: 'fresh' },
  evidence_exit_gate: { verdict: 'approved' },
  content_credibility: { status: 'passed' },
  report_conformance: { status: 'passed' },
  snapshot_integrity: {
    status: 'invalid',
    hash: 'actual-hash',
    expected_hash: 'expected-hash'
  }
};
process.stdout.write(JSON.stringify(window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report)));
""".replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    boundary = json.loads(_node(script))

    assert boundary["state"] == "blocked"
    assert "snapshot_hash mismatch" in boundary["detail"]


def test_report_reading_boundary_prefers_hash_mismatch_over_generic_snapshot_integrity_error():
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
const genericError = '資料快照完整性未通過，不能直接引用報告結論。';
const report = {
  data_trust: { status: 'fresh' },
  evidence_exit_gate: { verdict: 'approved' },
  content_credibility: { status: 'passed' },
  report_conformance: { status: 'passed' },
  snapshot_integrity: {
    status: 'invalid',
    hash: 'actual-hash',
    expected_hash: 'expected-hash',
    errors: [genericError]
  }
};
process.stdout.write(JSON.stringify(window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report)));
""".replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    boundary = json.loads(_node(script))

    assert boundary["state"] == "blocked"
    assert "snapshot_hash mismatch" in boundary["detail"]
    assert "資料快照完整性未通過，不能直接引用報告結論。" not in boundary["detail"]


def test_report_reading_boundary_removes_generic_snapshot_integrity_error_when_specific_detail_exists():
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
const genericError = '資料快照完整性未通過，不能直接引用報告結論。';
const specificError = 'provider audit source digest mismatch';
const report = {
  data_trust: { status: 'fresh' },
  evidence_exit_gate: { verdict: 'approved' },
  content_credibility: { status: 'passed' },
  report_conformance: { status: 'passed' },
  snapshot_integrity: { status: 'invalid', errors: [genericError, specificError] }
};
process.stdout.write(JSON.stringify(window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report)));
""".replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    boundary = json.loads(_node(script))

    assert boundary["state"] == "blocked"
    assert "provider audit source digest mismatch" in boundary["detail"]
    assert "資料快照完整性未通過，不能直接引用報告結論。" not in boundary["detail"]


def test_report_reading_boundary_deduplicates_snapshot_integrity_error_details():
    boundary_path = STATIC_DIR / "report_reading_boundary_policy.js"
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
const detail = 'provider audit source digest mismatch';
const report = {
  data_trust: { status: 'fresh' },
  evidence_exit_gate: { verdict: 'approved' },
  content_credibility: { status: 'passed' },
  report_conformance: { status: 'passed' },
  snapshot_integrity: { status: 'invalid', errors: [detail, detail] }
};
process.stdout.write(JSON.stringify(window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report)));
""".replace("__BOUNDARY_PATH__", json.dumps(str(boundary_path)))

    boundary = json.loads(_node(script))

    assert boundary["state"] == "blocked"
    assert boundary["detail"].count("provider audit source digest mismatch") == 1


def test_report_preview_panel_renders_reading_boundary_before_decision_metrics():
    paths = {
        "boundary": STATIC_DIR / "report_reading_boundary_policy.js",
        "gate": STATIC_DIR / "report_quality_gate_policy.js",
        "policy": STATIC_DIR / "report_quality_policy.js",
        "helpers": STATIC_DIR / "report_preview_helpers.js",
        "tracking": STATIC_DIR / "report_preview_tracking_helpers.js",
        "rerun": STATIC_DIR / "report_preview_rerun_helpers.js",
        "panel": STATIC_DIR / "report_preview_panel.js",
    }
    script = """
global.window = {};
require(__BOUNDARY_PATH__);
require(__GATE_PATH__);
require(__POLICY_PATH__);
require(__HELPERS_PATH__);
require(__TRACKING_PATH__);
require(__RERUN_PATH__);
require(__PANEL_PATH__);
const el = () => ({ hidden: true, textContent: '', innerHTML: '', className: '', classList: { toggle() {} }, querySelector: () => null });
const elements = {
  workspace: el(), root: el(), mode: el(), title: el(), readingNotice: el(),
  decisionRow: el(), targets: el(), summary: el(), staleNotice: el()
};
const panel = window.StockAgentReportPreviewPanel.create({
  elements,
  escapeHtml: value => String(value ?? '').replace(/[&<>]/g, ''),
  renderPipelineModeBadge: () => '',
  renderDataTrustBadge: () => '',
  pipelineMeta: () => ({ shortLabel: '價值投資派' }),
  normalizeRecommendation: value => String(value ?? ''),
  recommendationTone: () => 'is-hold'
});
panel.show({
  ticker: '2330.TW',
  pipeline_id: 'v1',
  recommendation: { recommendation: '持有' },
  data_trust: { status: 'unknown' }
});
process.stdout.write(JSON.stringify({
  hidden: elements.readingNotice.hidden,
  className: elements.readingNotice.className,
  html: elements.readingNotice.innerHTML,
  decision: elements.decisionRow.innerHTML
}));
"""
    for key, path in paths.items():
        script = script.replace(f"__{key.upper()}_PATH__", json.dumps(str(path)))

    payload = json.loads(_node(script))

    assert payload["hidden"] is False
    assert "is-pending" in payload["className"]
    assert "報告使用範圍與判讀限制" in payload["html"]
    assert "品質 gate 尚未記錄" in payload["html"]
    assert "勿直接採用報告結論" in payload["html"]
