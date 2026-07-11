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
