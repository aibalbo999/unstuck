import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_watchlist_board_surfaces_full_quality_audit_without_creating_daily_action():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  repair_queue: { summary: { sampled_reports: 20 } },
  report_quality_audit: {
    scope: 'all_indexed_reports',
    audited_reports: 160,
    quality_metadata_missing_reports: 3,
    repair_sample_overlap: {
      status: 'complete',
      audit_gap_reports: 3,
      audit_gap_items_returned: 3,
      repair_sampled_reports: 20,
      audit_gap_reports_in_repair_sample: 0,
      audit_gap_reports_outside_repair_sample: 3
    },
    quality_metadata_coverage_pct: 98.75,
    quality_metadata_coverage_basis: 'verified_snapshot_reports',
    quality_review_by_status: { pending: 2, approved_with_gap: 1, rejected: 0, deferred: 0 },
    artifact_quality_summary_by_status: { present: 2, not_found: 0, unavailable: 0 },
    artifact_quality_summary_by_field: { report_conformance: 2, evidence_exit_gate: 2, content_credibility: 0 },
    quality_metadata_missing_by_rerun_context: { present: 1, partial: 0, artifact_fallback_available: 1, missing: 1, not_evaluated: 0 },
    quality_metadata_by_pipeline: {
      v1: { quality_metadata_missing_reports: 1, quality_metadata_missing_by_rerun_context: { present: 0, partial: 0, artifact_fallback_available: 1, missing: 0, not_evaluated: 0 } },
      v2: { quality_metadata_missing_reports: 1, quality_metadata_missing_by_rerun_context: { present: 0, partial: 0, artifact_fallback_available: 1, missing: 0, not_evaluated: 0 } }
    }
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "全量報告品質" in payload["board"]
    assert "3 份品質 metadata 缺口" in payload["board"]
    assert "待人工核對 2" in payload["board"]
    assert "已驗證快照覆蓋 98.75%" in payload["board"]
    assert "artifact 摘要可查 2 份" in payload["board"]
    assert "artifact 欄位可查：報告一致性 2、證據關卡 2、內容可信度 0" in payload["board"]
    assert "審核狀態：待人工核對 2、已核准保留缺口 1" in payload["board"]
    assert "人工審核進度：1/3" in payload["board"]
    assert "上下文：原始上下文完整 1、artifact 前序可查 1、無可用局部上下文 1" in payload["board"]
    assert "模式上下文：v1 artifact 前序可查 1、v2 artifact 前序可查 1" in payload["board"]
    assert "修復 queue 範圍：取樣 20 份報告" in payload["board"]
    assert "品質缺口與 repair sample：0/3 在 sample；3 份不在 sample" in payload["board"]
    assert 'class="watchlist-daily-quality-summary"' in payload["board"]
    assert 'class="watchlist-daily-quality-scope">全量報告品質</strong>' in payload["board"]
    assert payload["board"].index('class="watchlist-daily-quality-scope"') < payload["board"].index('class="watchlist-daily-quality-item"')
    assert payload["board"].count('class="watchlist-daily-quality-item"') == 11


def test_watchlist_board_does_not_infer_unreturned_quality_gap_sample_overlap():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  repair_queue: { summary: { sampled_reports: 20 } },
  report_quality_audit: {
    scope: 'all_indexed_reports',
    quality_metadata_missing_reports: 115,
    items_returned: 5,
    items_truncated: true,
    repair_sample_overlap: {
      status: 'partial',
      audit_gap_reports: 115,
      audit_gap_items_returned: 5,
      repair_sampled_reports: 20,
      audit_gap_reports_in_repair_sample: 1
    },
    quality_metadata_coverage_pct: 90.59,
    quality_metadata_coverage_basis: 'verified_snapshot_reports'
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "品質缺口與 repair sample：只載入 5/115 份缺口，未展開部分無法判定" in payload["board"]
    assert "1/115 在 sample" not in payload["board"]


def test_watchlist_board_surfaces_full_freshness_summary_separately_from_quality_gap():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    freshness_helper_path = STATIC_DIR / "watchlist_freshness_helpers.js"
    script = """
global.window = {};
require(__FRESHNESS_HELPER_PATH__);
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  repair_queue: { summary: { sampled_reports: 20 } },
  report_quality_audit: {
    scope: 'all_indexed_reports',
    selection_basis: 'latest_per_ticker_pipeline',
    audited_reports: 165,
    quality_metadata_missing_reports: 2,
    decision_freshness_summary: {
      scope: 'all_indexed_reports',
      selection_basis: 'latest_per_ticker_pipeline',
      audited_reports: 165,
      current_reports: 143,
      needs_rerun_reports: 22,
      unknown_reports: 0
    },
    items: []
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__FRESHNESS_HELPER_PATH__", json.dumps(str(freshness_helper_path))).replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "分析新鮮度：目前一致 143、需完整重跑 22" in payload["board"]


def test_watchlist_board_surfaces_bounded_freshness_targets_with_history_navigation():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    freshness_helper_path = STATIC_DIR / "watchlist_freshness_helpers.js"
    script = """
global.window = {};
require(__FRESHNESS_HELPER_PATH__);
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  repair_queue: { summary: { sampled_reports: 20 } },
  report_quality_audit: {
    scope: 'all_indexed_reports',
    selection_basis: 'latest_per_ticker_pipeline',
    decision_freshness_summary: {
      schema_version: 'report_freshness_summary.v1',
      scope: 'all_indexed_reports',
      selection_basis: 'latest_per_ticker_pipeline',
      audited_reports: 165,
      current_reports: 143,
      needs_rerun_reports: 22,
      unknown_reports: 0
    },
    decision_freshness_items: {
      schema_version: 'report_freshness_items.v1',
      scope: 'all_indexed_reports',
      selection_basis: 'latest_per_ticker_pipeline',
      audited_reports: 165,
      needs_rerun_reports: 22,
      items_limit: 5,
      items_total: 22,
      items_returned: 1,
      items_truncated: true,
      items: [{ ticker: '3653.TW', pipeline_id: 'v3', filename: '3653_v3.html', reason: '資料快照已刷新，但分析本文未重跑。' }]
    }
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__FRESHNESS_HELPER_PATH__", json.dumps(str(freshness_helper_path))).replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "待重跑報告（顯示 1/22）" in payload["board"]
    assert 'data-quality-history-audit-target' in payload["board"]
    assert 'data-quality-history-query="3653_v3.html"' in payload["board"]
    assert "資料快照已刷新，但分析本文未重跑。" in payload["board"]


def test_watchlist_board_surfaces_current_quality_projection_separately_with_history_navigation():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    freshness_helper_path = STATIC_DIR / "watchlist_freshness_helpers.js"
    current_quality_helper_path = STATIC_DIR / "watchlist_current_quality_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
require(__FRESHNESS_HELPER_PATH__);
require(__CURRENT_QUALITY_HELPER_PATH__);
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  repair_queue: { summary: { sampled_reports: 20 } },
  report_quality_audit: {
    scope: 'all_indexed_reports',
    selection_basis: 'latest_per_ticker_pipeline',
    current_quality_summary: {
      schema_version: 'report_current_quality_summary.v1',
      scope: 'all_indexed_reports',
      selection_basis: 'latest_per_ticker_pipeline',
      audited_reports: 165,
      report_conformance_by_status: { passed: 29, warning: 127, blocked: 9, unknown: 0 },
      content_credibility_by_status: { passed: 31, warning: 126, blocked: 8, unknown: 0 },
      evidence_exit_gate_by_verdict: { approved: 39, caution: 125, rejected: 1, unknown: 0 },
      evidence_failed_count: 138,
      evidence_unverifiable_reason_counts: { research_source_not_canonical: 2 },
      report_conformance_blocker_counts: { final_audit: 9 },
      content_credibility_blocker_counts: { final_audit_critical: 8 },
      content_credibility_blocker_reports_by_freshness: { needs_rerun: 8, current: 5, unknown: 0 },
      quality_gate_action_counts: { manual_review: 1 },
      evidence_mismatch_claims_by_freshness: { needs_rerun: 138, current: 0, unknown: 0 },
      evidence_mismatch_reports_by_freshness: { needs_rerun: 1, current: 0, unknown: 0 },
      non_passed_reports: 136,
      items_limit: 5,
      items_total: 136,
      items_returned: 1,
      items_truncated: true,
      items: [{ ticker: '2454.TW', pipeline_id: 'v2', filename: '2454_v2.html', report_conformance_status: 'blocked', content_credibility_status: 'blocked', content_credibility_blocker_ids: ['final_audit_critical'], content_credibility_blocker_messages: ['Agent 7 輸出失敗。'], content_credibility_freshness_status: 'needs_rerun', evidence_exit_gate_verdict: 'rejected', evidence_failed_count: 138, evidence_mismatch_freshness_status: 'needs_rerun', quality_action: { recommended_action: 'manual_review', action_label: '人工審核', title: '內容可信度未通過', detail: 'Agent 7 輸出失敗。', reason_codes: ['content_credibility_blocked'], blocks_auto_rerun: true }, reason: '證據矛盾' }]
    }
  }
};
const board = window.StockAgentPanelHelpers?.watchlistDailyBoard || window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard;
process.stdout.write(JSON.stringify({ board: window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? '')) }));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__FRESHNESS_HELPER_PATH__", json.dumps(str(freshness_helper_path))).replace("__CURRENT_QUALITY_HELPER_PATH__", json.dumps(str(current_quality_helper_path))).replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "目前品質：符合 29、警示 127、阻斷 9、無法判定 0" in payload["board"]
    assert "品質阻斷來源：報告一致性：最終稽核 9；內容可信度：最終稽核重大問題 8" in payload["board"]
    assert "內容阻斷版本：資料已更新、本文需完整重跑 8 份、本文目前版本 5 份" in payload["board"]
    assert "證據數值不一致 138；數值不一致分布：資料已更新、本文需完整重跑 138 筆／1 份；證據未驗證原因：研究來源非 canonical 2" in payload["board"]
    assert "數值不一致分布：資料已更新、本文需完整重跑 138 筆／1 份" in payload["board"]
    assert "目前品質待查看（顯示 1/136）" in payload["board"]
    assert 'data-quality-history-query="2454_v2.html"' in payload["board"]
    assert "內容阻斷：最終稽核重大問題；內容阻斷版本：資料已更新、本文需完整重跑" in payload["board"]
    assert "內容阻斷原因：Agent 7 輸出失敗。" in payload["board"]
    assert "品質處理建議：人工審核 1" in payload["board"]
    assert "建議處理：人工審核（暫停自動重跑）" in payload["board"]
    assert "一致性：阻斷；內容：阻斷；證據：拒絕；證據矛盾；證據數值不一致 138；數值不一致來源：資料已更新、本文需完整重跑 138 筆" in payload["board"]


def test_historical_quality_audit_renders_revision_scoped_review_controls():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    renderer_path = STATIC_DIR / "history_quality_audit_render.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
require(__RENDERER_PATH__);
const html = window.StockAgentHistoricalQualityAuditRenderer.render({
  audited_reports: 1,
  quality_metadata_missing_reports: 1,
  quality_review_by_status: { pending: 1, approved_with_gap: 0, rejected: 0, deferred: 0 },
  items: [{
    ticker: '1623.TW',
    filename: '1623_v1.html',
    pipeline_id: 'v1',
    report_quality_revision: '1234567890abcdef1234567890abcdef',
    missing_quality_fields: ['content_credibility'],
    quality_review: { status: 'pending', decision_label: '待人工核對', event_count: 0 }
  }]
}, value => String(value ?? ''));
process.stdout.write(html);
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__RENDERER_PATH__", json.dumps(str(renderer_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert 'data-quality-review-decision="approved_with_gap"' in result.stdout
    assert 'data-quality-review-decision="rejected"' in result.stdout
    assert 'data-quality-review-decision="deferred"' in result.stdout
    assert 'data-quality-review-revision="1234567890abcdef1234567890abcdef"' in result.stdout
    assert '目前版本識別碼：1234567890ab...' in result.stdout
    assert 'aria-label="目前報告版本識別碼：1234567890abcdef1234567890abcdef"' in result.stdout
    assert '審核狀態：待人工核對 1' in result.stdout
    assert 'data-quality-audit-review-status="pending"' in result.stdout


def test_historical_quality_audit_renders_revision_review_timeline():
    helper_path = STATIC_DIR / "history_panel_quality_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const html = window.StockAgentHistoryPanelQualityHelpers.renderQualityReview({
  filename: '1623_TW_v1_report.html',
  pipeline_id: 'v1',
  report_quality_revision: 'rev-2',
  quality_review: { status: 'approved_with_gap', decision_label: '已核准保留缺口', event_count: 2 },
  quality_review_history: [
    { event_id: 2, reviewer_label: 'operator-b', reviewed_at: '2026-08-16T04:00:00+00:00', decision_label: '已核准保留缺口', note: '保留缺口。' },
    { event_id: 1, reviewer_label: 'operator-a', reviewed_at: '2026-08-16T03:00:00+00:00', decision_label: '已暫緩', note: '等待證據。' }
  ]
}, '1623.TW v1', value => String(value ?? ''));
process.stdout.write(html);
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    assert "審核紀錄" in result.stdout
    assert "operator-a" in result.stdout
    assert "等待證據。" in result.stdout


def test_historical_quality_audit_saves_review_with_visible_revision():
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = { prompt: () => '已核對 artifact，保留缺口。', StockAgentHistoricalQualityAuditRenderer: { render: () => '' } };
  require(__MODULE_PATH__);
  let clickHandler;
  let saved;
  let fetchCount = 0;
  const element = {
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; }
  };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: {
      fetchHistoricalReportQualityAudit: async () => { fetchCount += 1; return { audited_reports: 1, quality_metadata_missing_reports: 1, items: [] }; },
      saveHistoricalReportQualityReview: async value => { saved = value; return { success: true }; }
    },
    ui: { escapeHtml: value => String(value ?? '') },
    element
  });
  audit.bindEvents();
  await audit.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  clickHandler({ target: { closest: selector => selector === '[data-quality-review-decision]' ? { dataset: {
    qualityReviewDecision: 'approved_with_gap', qualityReviewFilename: '1623_v1.html', qualityReviewTicker: '1623.TW',
    qualityReviewPipeline: 'v1', qualityReviewRevision: 'rev-current'
  } } : null } });
  await new Promise(resolve => setTimeout(resolve, 0));
  process.stdout.write(JSON.stringify({ saved, fetchCount }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["saved"] == {
        "filename": "1623_v1.html",
        "ticker": "1623.TW",
        "pipeline_id": "v1",
        "report_quality_revision": "rev-current",
        "decision": "approved_with_gap",
        "note": "已核對 artifact，保留缺口。"
    }
    assert payload["fetchCount"] == 2


def test_historical_quality_audit_prevents_duplicate_review_submission_and_confirms_success():
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = { prompt: () => '已核對 artifact，保留缺口。', StockAgentHistoricalQualityAuditRenderer: { render: () => '' } };
  require(__MODULE_PATH__);
  let clickHandler;
  let savedCount = 0;
  const notifications = [];
  const attrs = {};
  const reviewButton = {
    disabled: false,
    dataset: {
      qualityReviewDecision: 'approved_with_gap', qualityReviewFilename: '1623_v1.html', qualityReviewTicker: '1623.TW',
      qualityReviewPipeline: 'v1', qualityReviewRevision: 'rev-current'
    },
    setAttribute: (name, value) => { attrs[name] = value; },
    removeAttribute: name => { delete attrs[name]; }
  };
  const element = {
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; }
  };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: {
      fetchHistoricalReportQualityAudit: async () => ({ audited_reports: 1, quality_metadata_missing_reports: 1, items: [] }),
      saveHistoricalReportQualityReview: async () => { savedCount += 1; return { success: true }; }
    },
    ui: { escapeHtml: value => String(value ?? '') },
    notify: { success: message => notifications.push(message), error: message => notifications.push(`error:${message}`) },
    element
  });
  audit.bindEvents();
  await audit.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  const event = { target: { closest: selector => selector === '[data-quality-review-decision]' ? reviewButton : null } };
  clickHandler(event);
  clickHandler(event);
  await new Promise(resolve => setTimeout(resolve, 0));
  process.stdout.write(JSON.stringify({ savedCount, notifications, disabled: reviewButton.disabled, attrs }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["savedCount"] == 1
    assert payload["notifications"] == ["人工審核已儲存"]
    assert payload["disabled"] is False
    assert "aria-busy" not in payload["attrs"]


def test_historical_quality_audit_does_not_save_when_review_confirmation_is_cancelled():
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = {
    prompt: () => '取消前不應寫入。',
    confirm: () => false,
    StockAgentHistoricalQualityAuditRenderer: { render: () => '' }
  };
  require(__MODULE_PATH__);
  let clickHandler;
  let savedCount = 0;
  const reviewButton = {
    disabled: false,
    dataset: {
      qualityReviewDecision: 'approved_with_gap', qualityReviewFilename: '1623_v1.html', qualityReviewTicker: '1623.TW',
      qualityReviewPipeline: 'v1', qualityReviewRevision: 'rev-current'
    },
    setAttribute: () => {},
    removeAttribute: () => {}
  };
  const element = {
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; }
  };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: {
      fetchHistoricalReportQualityAudit: async () => ({ audited_reports: 1, quality_metadata_missing_reports: 1, items: [] }),
      saveHistoricalReportQualityReview: async () => { savedCount += 1; return { success: true }; }
    },
    ui: { escapeHtml: value => String(value ?? '') },
    element
  });
  audit.bindEvents();
  await audit.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  clickHandler({ target: { closest: selector => selector === '[data-quality-review-decision]' ? reviewButton : null } });
  await new Promise(resolve => setTimeout(resolve, 0));
  process.stdout.write(JSON.stringify({ savedCount }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["savedCount"] == 0


def test_historical_quality_audit_reenables_review_after_save_failure():
    module_path = STATIC_DIR / "history_quality_audit.js"
    script = """
(async () => {
  global.window = { prompt: () => '核對失敗後保留現況。', StockAgentHistoricalQualityAuditRenderer: { render: () => '' } };
  require(__MODULE_PATH__);
  let clickHandler;
  const notifications = [];
  const attrs = {};
  const reviewButton = {
    disabled: false,
    dataset: {
      qualityReviewDecision: 'deferred', qualityReviewFilename: '1623_v1.html', qualityReviewTicker: '1623.TW',
      qualityReviewPipeline: 'v1', qualityReviewRevision: 'rev-current'
    },
    setAttribute: (name, value) => { attrs[name] = value; },
    removeAttribute: name => { delete attrs[name]; }
  };
  const element = {
    hidden: true,
    innerHTML: '',
    setAttribute: () => {},
    removeAttribute: () => {},
    addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; }
  };
  const audit = window.StockAgentHistoricalQualityAudit.create({
    apiClient: {
      fetchHistoricalReportQualityAudit: async () => ({ audited_reports: 1, quality_metadata_missing_reports: 1, items: [] }),
      saveHistoricalReportQualityReview: async () => { throw new Error('review backend unavailable'); }
    },
    ui: { escapeHtml: value => String(value ?? '') },
    notify: { success: message => notifications.push(message), error: message => notifications.push(`error:${message}`) },
    element
  });
  audit.bindEvents();
  await audit.load({ includeVersions: true, query: '', pipelineFilter: 'all' });
  clickHandler({ target: { closest: selector => selector === '[data-quality-review-decision]' ? reviewButton : null } });
  await new Promise(resolve => setTimeout(resolve, 0));
  process.stdout.write(JSON.stringify({ notifications, disabled: reviewButton.disabled, attrs }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["notifications"] == ["error:review backend unavailable"]
    assert payload["disabled"] is False
    assert "aria-busy" not in payload["attrs"]


def test_watchlist_board_discloses_truncated_quality_audit_items():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    quality_metadata_missing_reports: 8,
    items_returned: 2,
    items_truncated: true,
    items: [{ ticker: '1623.TW', filename: '1623_v1.html', pipeline_id: 'v1' }, { ticker: '2330.TW', filename: '2330_v1.html', pipeline_id: 'v1' }]
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "8 份品質 metadata 缺口（目前顯示 2 份，另有 6 份未展開）" in payload["board"]


def test_watchlist_board_labels_latest_per_ticker_pipeline_quality_scope():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    selection_basis: 'latest_per_ticker_pipeline',
    quality_metadata_missing_reports: 1,
    items: []
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert 'class="watchlist-daily-quality-scope">全量報告品質（每 ticker/pipeline 最新一筆）</strong>' in payload["board"]
    assert "1 份品質 metadata 缺口" in payload["board"]


def test_watchlist_board_surfaces_missing_quality_field_counts():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    selection_basis: 'latest_per_ticker_pipeline',
    quality_metadata_missing_reports: 2,
      missing_quality_field_counts: {
        report_conformance: 2,
        evidence_exit_gate: 1,
        content_credibility: 2
      },
      quality_metadata_by_pipeline: {
        v1: { quality_metadata_missing_reports: 1 },
        v2: { quality_metadata_missing_reports: 1 }
      }
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "缺口：報告一致性 2、證據關卡 1、內容可信度 2" in payload["board"]
    assert "模式缺口：v1 1、v2 1" in payload["board"]


def test_watchlist_board_surfaces_quality_metadata_provenance_counts():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    quality_metadata_missing_reports: 3,
    quality_metadata_missing_by_provenance: {
      after_refresh: 2,
      no_refresh_provenance: 1
    }
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "來源：有刷新歸因 2、未標記刷新來源 1" in payload["board"]


def test_watchlist_board_surfaces_pre_refresh_quality_provenance_counts():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    quality_metadata_missing_reports: 2,
    quality_metadata_missing_by_provenance: {
      before_refresh: 1,
      after_refresh: 1,
      no_refresh_provenance: 0
    }
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "來源：刷新前已有缺口 1、有刷新歸因 1" in payload["board"]


def test_watchlist_board_surfaces_quality_rerun_execution_counts():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    quality_metadata_missing_reports: 4,
    quality_metadata_missing_by_rerun_execution: {
      full_rerun_required: 2,
      partial_rerun_available: 1,
      partial_rerun_review_required: 0,
      partial_rerun_unavailable: 0,
      not_evaluated: 1
    }
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "重跑策略：完整重跑 2、局部重跑可用 1、重跑策略未判定 1" in payload["board"]


def test_watchlist_board_does_not_treat_unavailable_quality_audit_as_zero_gaps():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: { status: 'unavailable', error_code: 'quality_audit_unavailable' }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "全量報告品質：暫時無法讀取" in payload["board"]
    assert "0 份品質 metadata 缺口" not in payload["board"]


def test_watchlist_board_surfaces_snapshots_excluded_from_quality_coverage():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    snapshot_invalid_reports: 1,
    snapshot_unverified_reports: 1,
    quality_metadata_coverage_pct: 100
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "2 份 snapshot 無法驗證" in payload["board"]


def test_watchlist_board_provides_read_only_report_targets_for_missing_quality_items():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    panel_path = STATIC_DIR / "watchlist_panel.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    quality_metadata_missing_reports: 2,
    quality_metadata_coverage_pct: 98.75,
    items: [
      { ticker: '1623.TW', filename: '1623_v2.html', pipeline_id: 'v2' },
      { ticker: '1623.TW', filename: '1623_v1.html', pipeline_id: 'v1' }
    ]
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    panel = panel_path.read_text(encoding="utf-8")

    assert 'data-quality-report="1623_v2.html"' in payload["board"]
    assert "查看 1623.TW v2" in payload["board"]
    assert "data-quality-report" in panel
    assert "onOpenReport" in panel


def test_watchlist_quality_report_targets_expose_human_reason_and_reason_codes():
    evidence_path = STATIC_DIR / "report_quality_evidence_helpers.js"
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__EVIDENCE_PATH__);
require(__HELPER_PATH__);
const payload = {
  decision_queue: { summary: { total_actionable: 0 }, items: [{ type: 'monitor' }] },
  report_quality_audit: {
    quality_metadata_missing_reports: 1,
    items: [{
      ticker: '1623.TW',
      filename: '1623_v2.html',
      pipeline_id: 'v2',
      title: '刷新後品質證據缺口',
      detail: '資料快照曾在報告後刷新，目前未記錄品質證據；刷新歸因存在，但無法由目前 metadata 判定缺口是否由刷新造成；採用前需人工查看 artifact 與 freshness。',
      missing_quality_fields: ['report_conformance', 'evidence_exit_gate', 'content_credibility'],
      reason_codes: ['quality_metadata_missing', 'quality_metadata_after_refresh'],
      quality_review: { status: 'approved_with_gap', decision_label: '已核准保留缺口', event_count: 1 },
      artifact_quality_summary: { status: 'present', source: 'markdown', fields: ['report_conformance', 'evidence_exit_gate'] }
    }]
  }
};
const board = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], payload, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ board }));
""".replace("__EVIDENCE_PATH__", json.dumps(str(evidence_path))).replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert 'title="資料快照曾在報告後刷新，目前未記錄品質證據；刷新歸因存在，但無法由目前 metadata 判定缺口是否由刷新造成；採用前需人工查看 artifact 與 freshness。；審核狀態：已核准保留缺口；結構化缺口：報告一致性、證據關卡、內容可信度；來源：有刷新歸因；artifact 摘要可查：報告一致性、證據關卡"' in payload["board"]
    assert 'aria-label="人工核對 1623.TW v2：刷新後品質證據缺口；審核狀態：已核准保留缺口；結構化缺口：報告一致性、證據關卡、內容可信度；來源：有刷新歸因；artifact 摘要可查：報告一致性、證據關卡；artifact 摘要僅供人工核對，不代表 gate 已通過"' in payload["board"]
    assert 'data-quality-reason-codes="quality_metadata_missing,quality_metadata_after_refresh"' in payload["board"]
    assert 'data-quality-missing-fields="report_conformance,evidence_exit_gate,content_credibility"' in payload["board"]
    assert 'data-quality-artifact-fields="report_conformance,evidence_exit_gate"' in payload["board"]
    assert 'data-quality-evidence-detail=' in payload["board"]
    assert '<small class="watchlist-quality-review-status">審核狀態：已核准保留缺口</small>' in payload["board"]
    assert '<small class="watchlist-quality-evidence-context">結構化缺口：報告一致性、證據關卡、內容可信度；來源：有刷新歸因；artifact 摘要可查：報告一致性、證據關卡</small>' in payload["board"]
    assert '<small class="quality-evidence-warning">artifact 摘要僅供人工核對，不代表 gate 已通過</small>' in payload["board"]
    assert 'data-quality-artifact-fields="report_conformance,evidence_exit_gate"' in payload["board"]
    assert "審核狀態：已核准保留缺口" in payload["board"]
    assert "artifact 摘要可查：報告一致性、證據關卡" in payload["board"]


def test_quality_report_button_opens_the_audited_report_through_existing_callback():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    panel_path = STATIC_DIR / "watchlist_panel.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
let clickHandler;
let opened;
window.StockAgentWatchlistPanelActions = { create: () => ({}) };
require(__PANEL_PATH__);
const listEl = { addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; } };
const panel = window.StockAgentWatchlistPanel.create({
  elements: { listEl },
  onOpenReport: (...args) => { opened = args; }
});
panel.bindEvents();
const qualityButton = {
  dataset: {
    qualityReport: '1623_TW_v2_report_20260815_154718.html',
    qualityReportTicker: '1623.TW',
    qualityReportPipeline: 'v2'
  }
};
clickHandler({ target: { closest: selector => selector === '[data-quality-report]' ? qualityButton : null } });
process.stdout.write(JSON.stringify({ opened }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path))).replace("__PANEL_PATH__", json.dumps(str(panel_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["opened"] == [
        "1623_TW_v2_report_20260815_154718.html",
        "1623.TW",
        "v2",
    ]
