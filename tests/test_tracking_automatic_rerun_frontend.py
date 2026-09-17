"""Exercise the actual tracking button without contacting API/model providers."""

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "static"


def _run(reports, *, fail_filename=None):
    scripts = [
        "report_quality_evidence_helpers.js", "report_quality_gate_policy.js",
        "report_reading_boundary_policy.js", "report_automatic_rerun_policy.js", "report_quality_policy.js",
        "decision_tracking_helpers.js", "decision_tracking_panel.js",
    ]
    script = """
const fs = require('fs');
global.window = {};
for (const file of __SCRIPTS__) require(file);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const reports = input.reports;
const payload = { items: [
  { ticker: 'tracked', enabled: true, latest_reports: reports },
  { ticker: 'duplicate', enabled: true, latest_reports: reports.slice(0, 1) },
  { ticker: 'disabled', enabled: false, latest_reports: [{ ...reports[0], filename: 'disabled.html' }] }
] };
const before = JSON.stringify(payload), calls = [], notices = [];
const button = { disabled: false, addEventListener() {} };
const policy = window.StockAgentReportQualityPolicy;
const panel = window.StockAgentDecisionTrackingPanel.create({
  apiClient: {
    fetchDecisionTracking: async () => payload,
    refreshReportDataSnapshot: async filename => calls.push({ type: 'refresh', filename }),
    requestJson: async (url, options) => {
      calls.push({ type: 'rerun', url, method: options.method, disabled: button.disabled });
      if (decodeURIComponent(url).includes(input.fail_filename || '\\u0000')) throw new Error('test rejection');
      return { success: true, queued: true, job_id: 'test-only' };
    }
  },
  historyPanel: { renderTrackingGroups() {} },
  elements: { runActionsBtn: button },
  notify: { success: message => notices.push(message), error: message => notices.push(message) }
});
(async () => {
  await panel.load();
  await panel.runAllRecommendedActions();
  process.stdout.write(JSON.stringify({
    actions: window.StockAgentDecisionTrackingHelpers.uniqueRecommendedActions(payload),
    calls, notices, disabled: button.disabled, unchanged: before === JSON.stringify(payload),
    reading: reports.map(report => window.StockAgentReportReadingBoundaryPolicy.reportReadingBoundary(report)),
    generalActions: reports.map(report => policy.reportRecommendedAction(report))
  }));
})().catch(error => { console.error(error); process.exitCode = 1; });
""".replace("__SCRIPTS__", json.dumps([str(STATIC / name) for name in scripts]))
    result = subprocess.run(
        ["node", "-e", script], input=json.dumps({"reports": reports, "fail_filename": fail_filename}),
        capture_output=True, text=True, check=True, timeout=15,
    )
    return json.loads(result.stdout)


def _report(**overrides):
    return {
        "filename": "2330_TW_v4_report.html", "ticker": "2330.TW", "pipeline_id": "v4",
        "data_trust": {"status": "fresh", "reason_codes": []},
        "snapshot_integrity": {"status": "verified", "valid": True},
        "decision_freshness": {"requires_rerun": True, "status": "needs_rerun"},
        "report_conformance": {"status": "blocked"},
        "evidence_exit_gate": {"verdict": "caution"},
        "content_credibility": {"status": "blocked"},
        **overrides,
    }


def test_tracking_loads_automatic_rerun_policy_before_shared_policy_and_helpers():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    paths = [f"/static/{name}.js?v=20260917-tracking-auto-rerun" for name in (
        "report_automatic_rerun_policy", "report_quality_policy", "decision_tracking_helpers",
    )]
    assert [html.index(path) for path in paths] == sorted(html.index(path) for path in paths)
    assert len((STATIC / "report_automatic_rerun_policy.js").read_text(encoding="utf-8").splitlines()) < 40


@pytest.mark.parametrize("status,verdict", [
    ("blocked", "rejected"), ("warning", "caution"), ("warning", "approved"),
    ("passed", "rejected"), ("passed", "caution"), ("not_recorded", "not_recorded"),
])
def test_tracking_reruns_stale_reports_without_accepting_old_quality(status, verdict):
    result = _run([_report(report_conformance={"status": status}, evidence_exit_gate={"verdict": verdict})])
    assert result["actions"] == [{"type": "rerun_full_report", "filename": "2330_TW_v4_report.html"}]
    assert len(result["calls"]) == 1
    assert result["calls"][0] == {
        "type": "rerun", "url": "/api/report/2330_TW_v4_report.html/rerun?scope=full_report",
        "method": "POST", "disabled": True,
    }
    assert result["generalActions"][0]["type"] == "manual_review"
    assert result["reading"][0]["state"] == "blocked"
    assert result["unchanged"] is True
    assert result["disabled"] is False


def test_tracking_button_restores_all_32_stale_reports_across_four_modes():
    reports = [
        _report(filename=f"stock_{index}_v{index % 4 + 1}.html", pipeline_id=f"v{index % 4 + 1}",
                report_conformance={"status": "blocked" if index < 25 else "warning"})
        for index in range(32)
    ]
    result = _run(reports)
    assert len(result["calls"]) == 32
    assert len({call["url"] for call in result["calls"]}) == 32
    assert all(call["method"] == "POST" for call in result["calls"])
    assert result["notices"] == ["已送出 32 個追蹤報告警示動作"]
    assert result["unchanged"] is True


@pytest.mark.parametrize("overrides", [
    {"snapshot_integrity": {"status": " INVALID ", "valid": True}},
    {"snapshot_integrity": {"status": "verified", "valid": False}},
    {"data_trust": {"status": " ERROR "}},
    {"data_trust": {"status": "fresh", "reason_codes": [" SOURCE_ERROR:market_data "]}},
])
def test_tracking_keeps_unsafe_inputs_for_manual_review(overrides):
    result = _run([_report(**overrides)])
    assert result["actions"][0]["type"] == "manual_review"
    assert result["calls"] == []
    assert result["unchanged"] is True


@pytest.mark.parametrize("value", [False, "false", "0", 0, None, "unknown", {}])
def test_quality_warning_alone_or_false_freshness_does_not_authorize_rerun(value):
    result = _run([_report(decision_freshness={"requires_rerun": value})])
    assert result["calls"] == []
    assert result["actions"][0]["type"] == "manual_review"


@pytest.mark.parametrize("marker", ["analysis_text_stale", "requires_rerun"])
def test_tracking_supports_existing_top_level_stale_markers(marker):
    result = _run([_report(decision_freshness={}, **{marker: True})])
    assert len(result["calls"]) == 1
    assert result["calls"][0]["type"] == "rerun"


@pytest.mark.parametrize("value", [True, 1, "true", " TRUE ", "1"])
def test_tracking_supports_explicit_positive_freshness_values(value):
    result = _run([_report(decision_freshness={"requires_rerun": value})])
    assert len(result["calls"]) == 1
    assert result["calls"][0]["type"] == "rerun"


def test_tracking_does_not_submit_reports_without_filenames():
    result = _run([_report(filename=None)])
    assert result["actions"] == []
    assert result["calls"] == []


def test_tracking_mixed_batch_preserves_refresh_manual_review_and_failure_isolation():
    reports = [
        _report(filename="rejected_request.html"),
        _report(filename="next_report.html"),
        _report(filename="unsafe.html", snapshot_integrity={"status": "invalid"}),
        _report(filename="refresh.html", decision_freshness={}, data_trust={"status": "stale"},
                report_conformance={"status": "passed"}, evidence_exit_gate={"verdict": "approved"},
                content_credibility={"status": "passed"}),
    ]
    result = _run(reports, fail_filename="rejected_request.html")
    assert [call["type"] for call in result["calls"]] == ["rerun", "rerun", "refresh"]
    assert result["notices"] == ["警示動作完成 2 個，失敗 1 個"]
    assert result["unchanged"] is True
    assert result["disabled"] is False
