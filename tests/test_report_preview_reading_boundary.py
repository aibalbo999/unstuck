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
