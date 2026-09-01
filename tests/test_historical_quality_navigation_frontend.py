import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"


def test_operator_dashboard_text_labels_report_sample_scope():
    module_path = STATIC_DIR / "operator_dashboard_actions.js"
    script = """
global.window = {};
require(__MODULE_PATH__);
const payload = {
  summary: {
    report_scope: { scope: 'daily_report_sample', label: '近期報告取樣', sampled_reports: 20 },
    report_repairs_required: 2,
    reports_needing_rerun: 0,
    watchlist_high_priority: 0
  },
  decision_queue: { summary: { total_actionable: 0 }, items: [] }
};
const text = window.StockAgentOperatorDashboardActions.dashboardText(payload);
process.stdout.write(JSON.stringify(text));
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["detail"] == "報告：近期報告取樣 20 份；修復 2 / 重跑 0 / watchlist 0"


def test_operator_dashboard_text_separates_repair_and_freshness_reruns():
    module_path = STATIC_DIR / "operator_dashboard_actions.js"
    script = """
global.window = {};
require(__MODULE_PATH__);
const payload = {
  summary: {
    report_scope: { scope: 'daily_report_sample', label: '近期報告取樣', sampled_reports: 20 },
    report_repairs_required: 9,
    report_repair_action_counts: { manual_review: 7, rerun_analysis: 2 },
    report_repair_rerun_required: 2,
    reports_needing_rerun: 0,
    reports_needing_freshness_rerun: 0,
    watchlist_high_priority: 0
  },
  decision_queue: { summary: { total_actionable: 0 }, items: [] }
};
const text = window.StockAgentOperatorDashboardActions.dashboardText(payload);
process.stdout.write(JSON.stringify(text));
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["detail"] == "報告：近期報告取樣 20 份；報告修復：人工審核 7、完整重跑 2；freshness需完整重跑 0 / watchlist 0"


def test_operator_dashboard_text_includes_repair_scope_with_actionable_queue():
    module_path = STATIC_DIR / "operator_dashboard_actions.js"
    script = """
global.window = {};
require(__MODULE_PATH__);
const payload = {
  summary: {
    report_scope: { scope: 'daily_report_sample', label: '近期報告取樣', sampled_reports: 20 },
    report_repairs_required: 9,
    report_repair_action_counts: { manual_review: 7, rerun_analysis: 2 },
    reports_needing_freshness_rerun: 0
  },
  decision_queue: { summary: { total_actionable: 3, displayed_count: 2, secondary_count: 4 }, secondary_count: 1, items: [] }
};
const text = window.StockAgentOperatorDashboardActions.dashboardText(payload);
process.stdout.write(JSON.stringify(text));
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["detail"] == "顯示 2 / 次要待辦 4 · 報告：近期報告取樣 20 份 · 報告修復：人工審核 7、完整重跑 2；freshness需完整重跑 0"


def test_operator_dashboard_text_includes_bounded_repair_queue_scope():
    module_path = STATIC_DIR / "operator_dashboard_actions.js"
    scope_path = STATIC_DIR / "report_quality_queue_scope_helpers.js"
    script = """
global.window = {};
require(__SCOPE_PATH__);
require(__MODULE_PATH__);
const payload = {
  summary: {
    report_repairs_required: 9,
    report_repair_action_counts: { manual_review: 7, rerun_analysis: 2 },
    reports_needing_freshness_rerun: 0
  },
  repair_queue: {
    summary: { action_required: 9, items_limit: 5, items_returned: 5, items_truncated: true }
  },
  decision_queue: { summary: { total_actionable: 0 }, items: [] }
};
const text = window.StockAgentOperatorDashboardActions.dashboardText(payload);
process.stdout.write(JSON.stringify(text));
""".replace("__SCOPE_PATH__", json.dumps(str(scope_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["detail"] == "報告修復：人工審核 7、完整重跑 2；freshness需完整重跑 0 · 修復 queue：顯示 5 / 共 9 / watchlist 0"


def test_operator_dashboard_text_ignores_inconsistent_repair_queue_scope():
    module_path = STATIC_DIR / "operator_dashboard_actions.js"
    scope_path = STATIC_DIR / "report_quality_queue_scope_helpers.js"
    script = """
global.window = {};
require(__SCOPE_PATH__);
require(__MODULE_PATH__);
const payload = {
  summary: {
    report_repairs_required: 9,
    report_repair_action_counts: { manual_review: 7, rerun_analysis: 2 },
    reports_needing_freshness_rerun: 0
  },
  repair_queue: {
    summary: { action_required: 9, items_limit: 5, items_returned: 2, items_truncated: false }
  },
  decision_queue: { summary: { total_actionable: 0 }, items: [] }
};
const text = window.StockAgentOperatorDashboardActions.dashboardText(payload);
process.stdout.write(JSON.stringify(text));
""".replace("__SCOPE_PATH__", json.dumps(str(scope_path))).replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["detail"] == "報告修復：人工審核 7、完整重跑 2；freshness需完整重跑 0 / watchlist 0"


def test_operator_dashboard_text_labels_full_freshness_summary():
    module_path = STATIC_DIR / "operator_dashboard_actions.js"
    script = """
global.window = {};
require(__MODULE_PATH__);
const payload = {
  summary: {
    report_scope: { scope: 'daily_report_sample', label: '近期報告取樣', sampled_reports: 20 },
    report_repairs_required: 2,
    reports_needing_rerun: 0,
    watchlist_high_priority: 0
  },
  report_quality_audit: {
    scope: 'all_indexed_reports',
    selection_basis: 'latest_per_ticker_pipeline',
    decision_freshness_summary: {
      audited_reports: 165,
      current_reports: 143,
      needs_rerun_reports: 22,
      unknown_reports: 0
    }
  },
  decision_queue: { summary: { total_actionable: 0 }, items: [] }
};
const text = window.StockAgentOperatorDashboardActions.dashboardText(payload);
process.stdout.write(JSON.stringify(text));
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "全量分析新鮮度：需完整重跑 22 / 165 份" in payload["detail"]


def test_daily_quality_board_offers_historical_audit_navigation_for_latest_scope():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const html = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], {
  report_quality_audit: {
    selection_basis: 'latest_per_ticker_pipeline',
    audited_reports: 160,
    quality_metadata_missing_reports: 2,
    quality_metadata_coverage_pct: 98.75,
    quality_metadata_coverage_basis: 'verified_snapshot_reports',
    items_returned: 2,
    items_truncated: false,
    items: []
  },
  decision_queue: { items: [], summary: { total_actionable: 0 } }
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert 'data-quality-history-audit' in payload["html"]
    assert "查看歷史版本稽核" in payload["html"]


def test_daily_quality_board_prefers_canonical_summary_secondary_count():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const html = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], {
  decision_queue: {
    summary: { total_actionable: 1, secondary_count: 4 },
    secondary_count: 1,
    items: [{ type: 'manual_review', title: '需要人工核對', priority_score: 700, source: 'report_repair' }]
  }
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert "需處理 1 件 · 次要待辦 4" in payload["html"]


def test_daily_quality_target_offers_scoped_human_review_navigation():
    helper_path = STATIC_DIR / "watchlist_panel_helpers.js"
    script = """
global.window = {};
require(__HELPER_PATH__);
const html = window.StockAgentWatchlistPanelHelpers.watchlistDailyBoard([], {
  report_quality_audit: {
    selection_basis: 'latest_per_ticker_pipeline',
    audited_reports: 1,
    quality_metadata_missing_reports: 1,
    items_returned: 1,
    items: [{
      ticker: '1623.TW',
      filename: '1623_TW_v2_report_20260815_154718.html',
      pipeline_id: 'v2',
      title: '刷新後品質證據缺口',
      detail: '請人工查看 artifact。',
      quality_review: { status: 'pending' }
    }]
  },
  decision_queue: { items: [], summary: { total_actionable: 0 } }
}, value => String(value ?? ''));
process.stdout.write(JSON.stringify({ html }));
""".replace("__HELPER_PATH__", json.dumps(str(helper_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert 'data-quality-history-audit-target' in payload["html"]
    assert 'data-quality-history-query="1623_TW_v2_report_20260815_154718.html"' in payload["html"]
    assert 'data-quality-history-pipeline="v2"' in payload["html"]
    assert "前往人工核對" in payload["html"]


def test_watchlist_panel_delegates_historical_audit_navigation():
    module_path = STATIC_DIR / "watchlist_panel.js"
    script = """
global.window = {
  StockAgentWatchlistPanelHelpers: {
    itemPayload: () => ({}),
    renderSuggestions: () => {},
    resetForm: () => {},
    slotLabel: () => '',
    priorityLabel: () => '',
    reportButton: () => ''
  },
  StockAgentWatchlistPanelActions: { create: () => ({}) },
  StockAgentWatchlistTriggerForm: { renderItem: () => '' }
};
require(__MODULE_PATH__);
let handler;
let opened = 0;
const listEl = { addEventListener: (type, callback) => { if (type === 'click') handler = callback; } };
const panel = window.StockAgentWatchlistPanel.create({ elements: { listEl } });
window.StockAgentOpenHistoricalQualityAudit = () => { opened += 1; };
panel.bindEvents();
handler({ target: { closest: selector => selector === '[data-quality-history-audit]' ? {} : null } });
process.stdout.write(JSON.stringify({ opened }));
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["opened"] == 1


def test_watchlist_panel_delegates_scoped_historical_audit_navigation():
    module_path = STATIC_DIR / "watchlist_panel.js"
    script = """
global.window = {
  StockAgentWatchlistPanelHelpers: {
    itemPayload: () => ({}),
    renderSuggestions: () => {},
    resetForm: () => {},
    slotLabel: () => '',
    priorityLabel: () => '',
    reportButton: () => ''
  },
  StockAgentWatchlistPanelActions: { create: () => ({}) },
  StockAgentWatchlistTriggerForm: { renderItem: () => '' }
};
require(__MODULE_PATH__);
let handler;
let opened;
const listEl = { addEventListener: (type, callback) => { if (type === 'click') handler = callback; } };
const panel = window.StockAgentWatchlistPanel.create({ elements: { listEl } });
window.StockAgentOpenHistoricalQualityAudit = scope => { opened = scope; };
panel.bindEvents();
handler({ target: { closest: selector => selector === '[data-quality-history-audit-target]' ? { dataset: {
  qualityHistoryQuery: '1623_TW_v2_report_20260815_154718.html', qualityHistoryPipeline: 'v2'
} } : null } });
process.stdout.write(JSON.stringify({ opened }));
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["opened"] == {
        "query": "1623_TW_v2_report_20260815_154718.html",
        "pipeline": "v2"
    }


def test_operator_dashboard_maps_quality_audit_to_scoped_human_review():
    module_path = STATIC_DIR / "operator_dashboard_actions.js"
    script = """
global.window = { StockAgentDailyQueueContext: { sourceLabel: source => source } };
require(__MODULE_PATH__);
const items = window.StockAgentOperatorDashboardActions.dashboardActionItems({ decision_queue: { items: [
  { type: 'manual_review', source: 'report_quality_audit', filename: '1623_TW_v2_report_20260815_154718.html', ticker: '1623.TW', pipeline_id: 'v2' },
  { type: 'manual_review', source: 'report_repair', filename: 'broken.html', ticker: '2330.TW', pipeline_id: 'v1' },
  { type: 'refresh_data_snapshot', source: 'report_quality_audit', filename: 'refresh.html', ticker: '2603.TW', pipeline_id: 'v4' }
] } });
process.stdout.write(JSON.stringify(items));
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    quality_item, repair_item, refresh_item = json.loads(result.stdout)

    assert quality_item["action"] == "quality-audit-review"
    assert quality_item["label"] == "前往人工核對"
    assert quality_item["filename"] == "1623_TW_v2_report_20260815_154718.html"
    assert quality_item["pipeline"] == "v2"
    assert quality_item["targetPanel"] == "history-quality-audit"
    assert quality_item["targetTab"] == "analysis"
    assert repair_item["action"] == "view-report"
    assert repair_item["label"] == "查看報告"
    assert refresh_item["action"] == "refresh-report"
    assert refresh_item["label"] == "刷新資料"


def test_operator_summary_keeps_data_trust_card_separate_from_daily_queue_summary():
    module_path = STATIC_DIR / "operator_summary_panel.js"
    script = """
global.window = {
  StockAgentOperatorDashboardActions: {
    actionableActionCount: () => 0,
    candidateActionModel: item => item,
    dashboardActionItems: () => [],
    dashboardText: () => ({ tone: 'warning', value: '1 件待處理', detail: '報告修復：人工審核 1' })
  },
  StockAgentOperatorSummaryHelpers: {
    activeJobText: () => ({ tone: 'ok', value: '無進行中任務', detail: '' }),
    quotaText: () => ({ tone: 'ok', value: 'API 正常', detail: '' }),
    trustText: () => ({ tone: 'warning', value: '資料信任需處理', detail: '資料新鮮 0 / 抽樣 1' }),
    rerunText: () => ({ tone: 'ok', value: '無立即重跑', detail: '' }),
    operatorActionItems: () => []
  }
};
const elements = {};
const makeElement = () => {
  const strong = { textContent: '' }, em = { textContent: '' };
  return { className: '', innerHTML: '', strong, em, querySelector: selector => selector === 'strong' ? strong : em, addEventListener: () => {} };
};
for (const id of ['operator-active-jobs', 'operator-data-trust', 'operator-api-quota', 'operator-rerun', 'operator-action-list']) elements[id] = makeElement();
global.document = { getElementById: id => elements[id] || null, querySelectorAll: () => [] };
require(__MODULE_PATH__);
const apiClient = {
  fetchActiveJobs: async () => ({ active_count: 0, jobs: [] }),
  fetchApiQuotas: async () => ({ services: [] }),
  fetchReports: async () => ({ reports: [{ ticker: '2330.TW' }] }),
  fetchWatchlist: async () => ({ items: [] }),
  fetchDailyDecisionDashboard: async () => ({ decision_queue: { summary: { total_actionable: 1 }, items: [] } })
};
(async () => {
  await window.StockAgentOperatorSummaryPanel.create({ apiClient, ui: { escapeHtml: value => String(value ?? '') } }).load();
  process.stdout.write(JSON.stringify({
    dataTrust: [elements['operator-data-trust'].strong.textContent, elements['operator-data-trust'].em.textContent],
    actionList: elements['operator-action-list'].innerHTML
  }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["dataTrust"] == ["資料信任需處理", "資料新鮮 0 / 抽樣 1"]
    assert "今日待處理" in payload["actionList"]


def test_operator_summary_shows_total_queue_count_when_items_are_truncated():
    module_path = STATIC_DIR / "operator_summary_panel.js"
    script = """
global.window = {
  StockAgentOperatorDashboardActions: {
    actionableActionCount: items => items.length,
    candidateActionModel: item => item,
    dashboardActionItems: () => Array.from({ length: 5 }, (_, index) => ({ action: 'open-ops', label: '查看狀態', title: `待處理 ${index + 1}`, detail: '' })),
    dashboardText: () => ({ tone: 'warning', value: '23 件待處理', detail: '顯示 5 / 次要待辦 18' })
  },
  StockAgentOperatorSummaryHelpers: {
    activeJobText: () => ({ tone: 'ok', value: '無進行中任務', detail: '' }),
    quotaText: () => ({ tone: 'ok', value: 'API 正常', detail: '' }),
    trustText: () => ({ tone: 'ok', value: '近期資料正常', detail: '' }),
    rerunText: () => ({ tone: 'ok', value: '無立即重跑', detail: '' }),
    operatorActionItems: () => []
  }
};
const elements = {};
const makeElement = () => {
  const strong = { textContent: '' }, em = { textContent: '' };
  return { className: '', innerHTML: '', strong, em, querySelector: selector => selector === 'strong' ? strong : em, addEventListener: () => {} };
};
for (const id of ['operator-active-jobs', 'operator-data-trust', 'operator-api-quota', 'operator-rerun', 'operator-action-list']) elements[id] = makeElement();
global.document = { getElementById: id => elements[id] || null, querySelectorAll: () => [] };
require(__MODULE_PATH__);
const apiClient = {
  fetchActiveJobs: async () => ({ active_count: 0, jobs: [] }),
  fetchApiQuotas: async () => ({ services: [] }),
  fetchReports: async () => ({ reports: [{ ticker: '2330.TW' }] }),
  fetchWatchlist: async () => ({ items: [] }),
  fetchDailyDecisionDashboard: async () => ({ decision_queue: { summary: { total_actionable: 23, displayed_count: 5 }, items: [] } })
};
(async () => {
  await window.StockAgentOperatorSummaryPanel.create({ apiClient, ui: { escapeHtml: value => String(value ?? '') } }).load();
  process.stdout.write(JSON.stringify(elements['operator-action-list'].innerHTML));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    action_list = json.loads(result.stdout)

    assert "顯示 5 / 共 23 件快速操作" in action_list


def test_operator_summary_uses_daily_report_sample_for_data_trust_denominator():
    module_path = STATIC_DIR / "operator_summary_panel.js"
    script = """
global.window = {
  StockAgentOperatorDashboardActions: {
    actionableActionCount: () => 0,
    candidateActionModel: item => item,
    dashboardActionItems: () => [],
    dashboardText: () => ({ tone: 'ok', value: '今日節奏正常', detail: '' })
  },
  StockAgentOperatorSummaryHelpers: {
    activeJobText: () => ({ tone: 'ok', value: '', detail: '' }),
    quotaText: () => ({ tone: 'ok', value: '', detail: '' }),
    trustText: () => ({ tone: 'ok', value: '近期資料正常', detail: '20 份近期報告' }),
    rerunText: () => ({ tone: 'ok', value: '', detail: '' }),
    operatorActionItems: () => []
  }
};
const elements = {};
const makeElement = () => {
  const strong = { textContent: '' }, em = { textContent: '' };
  return { className: '', innerHTML: '', strong, em, querySelector: selector => selector === 'strong' ? strong : em, addEventListener: () => {} };
};
for (const id of ['operator-active-jobs', 'operator-data-trust', 'operator-api-quota', 'operator-rerun', 'operator-action-list']) elements[id] = makeElement();
global.document = { getElementById: id => elements[id] || null, querySelectorAll: () => [] };
require(__MODULE_PATH__);
let reportRequest;
const apiClient = {
  fetchActiveJobs: async () => ({ active_count: 0, jobs: [] }),
  fetchApiQuotas: async () => ({ services: [] }),
  fetchReports: async params => { reportRequest = params; return { reports: [] }; },
  fetchWatchlist: async () => ({ items: [] }),
  fetchDailyDecisionDashboard: async () => ({ decision_queue: { summary: { total_actionable: 0 }, items: [] } })
};
(async () => {
  await window.StockAgentOperatorSummaryPanel.create({ apiClient, ui: { escapeHtml: value => String(value ?? '') } }).load();
  process.stdout.write(JSON.stringify(reportRequest));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    report_request = json.loads(result.stdout)

    assert report_request == {"page": 1, "limit": 20, "includeVersions": False}


def test_operator_summary_delegates_quality_audit_to_scoped_historical_review():
    module_path = STATIC_DIR / "operator_summary_panel.js"
    script = """
global.window = {
  StockAgentOperatorDashboardActions: { actionableActionCount: () => 0, candidateActionModel: item => item, dashboardActionItems: () => [], dashboardText: () => ({ tone: 'ok', value: '', detail: '' }) },
  StockAgentOperatorSummaryHelpers: {}
};
let handler;
const actionList = { addEventListener: (type, callback) => { if (type === 'click') handler = callback; } };
global.document = { getElementById: id => id === 'operator-action-list' ? actionList : null, querySelectorAll: () => [] };
require(__MODULE_PATH__);
let opened;
window.StockAgentOpenHistoricalQualityAudit = scope => { opened = scope; return Promise.resolve(); };
const button = { dataset: { operatorAction: 'quality-audit-review', filename: '1623_TW_v2_report_20260815_154718.html', ticker: '1623.TW', pipeline: 'v2' }, textContent: '前往人工核對', disabled: false };
(async () => {
  window.StockAgentOperatorSummaryPanel.create({ apiClient: {}, ui: { escapeHtml: value => String(value ?? '') } });
  await handler({ target: { closest: selector => selector === '[data-operator-action]' ? button : null } });
  process.stdout.write(JSON.stringify({ opened, disabled: button.disabled, text: button.textContent }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload == {
        "opened": {"query": "1623_TW_v2_report_20260815_154718.html", "pipeline": "v2"},
        "disabled": False,
        "text": "前往人工核對"
    }


def test_history_workspace_ignores_stale_report_list_response():
    module_path = STATIC_DIR / "history_workspace.js"
    script = """
(async () => {
  global.window = {
    StockAgentHistoricalQualityAudit: { create: () => ({ load: () => {}, bindEvents: () => {}, resetReviewStatus: () => { global.reviewReset = (global.reviewReset || 0) + 1; } }) },
    StockAgentHistoryWorkspacePanels: {
      create: () => ({
        historyFilters: {
          values: (() => { let calls = 0; return () => ({ query: ['old', 'new'][calls++], pipelineFilter: 'all', recommendationFilter: 'all', dataTrustFilter: 'all', includeVersions: false }); })(),
          bind: () => {}
        },
        historyPanel: {
          renderReports: reports => { global.renderedQuery = reports[0]?.query || ''; },
          renderPagination: () => 1,
          setTrackingCompact: () => {},
          bindEvents: () => {},
          clearSelection: () => {}
        },
        reportPreviewPanel: { hide: () => {}, show: () => false },
        reportComparePanel: { bindEvents: () => {} },
        trackingSnapshotPanel: { bindEvents: () => {}, load: async () => {} },
        decisionTrackingPanel: {
          load: () => new Promise(resolve => global.trackingResolvers.push(resolve))
        }
      })
    },
    StockAgentHistoryWorkspaceActions: { create: () => ({}) }
  };
  global.trackingResolvers = [];
  const reportResolvers = {};
  const workspace = require(__MODULE_PATH__);
  const instance = window.StockAgentHistoryWorkspace.create({
    apiClient: {
      fetchReports: params => new Promise(resolve => { reportResolvers[params.query] = resolve; })
    },
    ui: {},
    elements: { historyIncludeVersions: { checked: false } },
    openReport: () => {}
  });
  const first = instance.loadHistory();
  const second = instance.loadHistory();
  global.trackingResolvers[1]({ items: [] });
  await Promise.resolve();
  global.trackingResolvers[0]({ items: [] });
  await Promise.resolve();
  reportResolvers.new({ reports: [{ query: 'new', filename: 'new.html' }] });
  await Promise.resolve();
  reportResolvers.old({ reports: [{ query: 'old', filename: 'old.html' }] });
  await Promise.all([first, second]);
  process.stdout.write(JSON.stringify({ renderedQuery: global.renderedQuery }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["renderedQuery"] == "new"


def test_history_workspace_clears_transient_preview_and_snapshot_on_scope_change():
    module_path = STATIC_DIR / "history_workspace.js"
    script = """
(async () => {
  const classes = new Set();
  const workspaceEl = { classList: {
    add: value => classes.add(value),
    remove: value => classes.delete(value),
    toggle: (value, enabled) => enabled ? classes.add(value) : classes.delete(value),
    contains: value => classes.has(value)
  }};
  const snapshotRoot = { hidden: false };
  const historyFilters = {
    state: { query: 'old', pipelineFilter: 'all', recommendationFilter: 'all', dataTrustFilter: 'all', includeVersions: false },
    values() { return this.state; },
    bind: () => {}
  };
  global.window = {
    StockAgentHistoricalQualityAudit: { create: () => ({ load: () => {}, bindEvents: () => {}, resetReviewStatus: () => {} }) },
    StockAgentHistoryWorkspacePanels: {
      create: () => ({
        historyFilters,
        historyPanel: {
          renderReports: () => {}, renderPagination: () => 1, setTrackingCompact: () => {},
          bindEvents: () => {}, clearSelection: () => {}
        },
        reportPreviewPanel: { hide: () => {}, show: () => false },
        reportComparePanel: { bindEvents: () => {} },
        trackingSnapshotPanel: { bindEvents: () => {}, load: async () => {} },
        decisionTrackingPanel: { load: async () => ({ items: [] }) }
      })
    },
    StockAgentHistoryWorkspaceActions: { create: () => ({}) }
  };
  const workspace = require(__MODULE_PATH__);
  const instance = window.StockAgentHistoryWorkspace.create({
    apiClient: { fetchReports: async () => ({ reports: [{ filename: 'current.html' }], pagination: { page: 1, total_pages: 1, total: 1, has_prev: false, has_next: false } }) },
    ui: {},
    elements: {
      historyWorkspace: workspaceEl,
      historyIncludeVersions: { checked: false },
      decisionTrackingStockSnapshotPanel: snapshotRoot
    },
    openReport: () => {}
  });
  await instance.loadHistory();
  workspaceEl.classList.add('has-preview');
  snapshotRoot.hidden = false;
  historyFilters.state = { ...historyFilters.state, query: 'new' };
  await instance.loadHistory();
  process.stdout.write(JSON.stringify({ hidden: snapshotRoot.hidden, hasPreview: workspaceEl.classList.contains('has-preview') }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload == {"hidden": True, "hasPreview": False}


def test_history_workspace_ignores_snapshot_response_after_scope_change():
    module_path = STATIC_DIR / "history_workspace.js"
    script = """
(async () => {
  const classes = new Set();
  const workspaceEl = { classList: {
    add: value => classes.add(value),
    remove: value => classes.delete(value),
    toggle: (value, enabled) => enabled ? classes.add(value) : classes.delete(value),
    contains: value => classes.has(value)
  }};
  const snapshotRoot = { hidden: true, scrollIntoView: () => {} };
  const historyFilters = {
    state: { query: '', pipelineFilter: 'all', recommendationFilter: 'all', dataTrustFilter: 'all', includeVersions: false },
    values() { return this.state; },
    bind: () => {}
  };
  let resolveSnapshot;
  global.window = {
    StockAgentHistoricalQualityAudit: { create: () => ({ load: () => {}, bindEvents: () => {}, resetReviewStatus: () => {} }) },
    StockAgentHistoryWorkspacePanels: {
      create: () => ({
        historyFilters,
        historyPanel: {
          renderReports: () => {}, renderPagination: () => 1, setTrackingCompact: () => {},
          bindEvents: handlers => { global.openSnapshot = handlers.onOpenSnapshot; },
          clearSelection: () => {}
        },
        reportPreviewPanel: { hide: () => {}, show: () => false },
        reportComparePanel: { bindEvents: () => {} },
        trackingSnapshotPanel: {
          bindEvents: () => {},
          load: async () => { await new Promise(resolve => { resolveSnapshot = resolve; }); snapshotRoot.hidden = false; }
        },
        decisionTrackingPanel: { load: async () => ({ items: [] }) }
      })
    },
    StockAgentHistoryWorkspaceActions: { create: () => ({}) }
  };
  const workspace = require(__MODULE_PATH__);
  const instance = window.StockAgentHistoryWorkspace.create({
    apiClient: { fetchReports: async () => ({ reports: [{ filename: 'current.html' }], pagination: { page: 1, total_pages: 1, total: 1, has_prev: false, has_next: false } }) },
    ui: {},
    elements: { historyWorkspace: workspaceEl, historyIncludeVersions: { checked: false }, decisionTrackingStockSnapshotPanel: snapshotRoot },
    openReport: () => {}
  });
  instance.bindEvents();
  const pending = global.openSnapshot('2330.TW');
  await Promise.resolve();
  historyFilters.state = { ...historyFilters.state, query: 'new' };
  await instance.loadHistory();
  resolveSnapshot();
  await pending;
  process.stdout.write(JSON.stringify({ hidden: snapshotRoot.hidden, hasPreview: workspaceEl.classList.contains('has-preview') }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload == {"hidden": True, "hasPreview": False}


def test_history_workspace_keeps_report_preview_when_snapshot_response_is_stale():
    module_path = STATIC_DIR / "history_workspace.js"
    script = """
(async () => {
  const classes = new Set();
  const workspaceEl = { classList: {
    add: value => classes.add(value),
    remove: value => classes.delete(value),
    toggle: (value, enabled) => enabled ? classes.add(value) : classes.delete(value),
    contains: value => classes.has(value)
  }};
  const snapshotRoot = { hidden: true, scrollIntoView: () => {} };
  const historyFilters = {
    state: { query: '', pipelineFilter: 'all', recommendationFilter: 'all', dataTrustFilter: 'all', includeVersions: false },
    values() { return this.state; },
    bind: () => {}
  };
  let resolveSnapshot;
  global.window = {
    StockAgentHistoricalQualityAudit: { create: () => ({ load: () => {}, bindEvents: () => {}, resetReviewStatus: () => {} }) },
    StockAgentHistoryWorkspacePanels: {
      create: () => ({
        historyFilters,
        historyPanel: {
          renderReports: () => {}, renderPagination: () => 1, setTrackingCompact: () => {},
          bindEvents: handlers => { global.openSnapshot = handlers.onOpenSnapshot; global.selectReport = handlers.onSelect; },
          clearSelection: () => {}, select: () => {}
        },
        reportPreviewPanel: { hide: () => {}, show: () => { workspaceEl.classList.add('has-preview'); return true; } },
        reportComparePanel: { bindEvents: () => {} },
        trackingSnapshotPanel: {
          bindEvents: () => {},
          load: async () => { await new Promise(resolve => { resolveSnapshot = resolve; }); snapshotRoot.hidden = false; }
        },
        decisionTrackingPanel: { load: async () => ({ items: [] }) }
      })
    },
    StockAgentHistoryWorkspaceActions: { create: () => ({}) }
  };
  const workspace = require(__MODULE_PATH__);
  const instance = window.StockAgentHistoryWorkspace.create({
    apiClient: { fetchReports: async () => ({ reports: [{ filename: 'current.html', ticker: '2330.TW' }], pagination: { page: 1, total_pages: 1, total: 1, has_prev: false, has_next: false } }) },
    ui: {},
    elements: { historyWorkspace: workspaceEl, historyIncludeVersions: { checked: false }, decisionTrackingStockSnapshotPanel: snapshotRoot },
    openReport: () => {}
  });
  await instance.loadHistory();
  instance.bindEvents();
  const pending = global.openSnapshot('2330.TW');
  await Promise.resolve();
  global.selectReport('current.html');
  resolveSnapshot();
  await pending;
  process.stdout.write(JSON.stringify({ hidden: snapshotRoot.hidden, hasPreview: workspaceEl.classList.contains('has-preview'), preview: Boolean(instance.getPreviewReport()) }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload == {"hidden": True, "hasPreview": True, "preview": True}


def test_history_filters_persist_and_restore_entire_scope_with_navigation_override():
    module_path = STATIC_DIR / "history_filters.js"
    script = """
global.window = {};
const storage = {};
window.sessionStorage = {
  getItem: key => Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null,
  setItem: (key, value) => { storage[key] = String(value); },
  removeItem: key => { delete storage[key]; }
};
require(__MODULE_PATH__);
function makeElement(value = '', checked = false) {
  return { value, checked, addEventListener: () => {} };
}
function makeFilters() {
  const elements = {
    searchEl: makeElement(),
    pipelineEl: makeElement('all'),
    recommendationEl: makeElement('all'),
    dataTrustEl: makeElement('all'),
    includeVersionsEl: makeElement('', false)
  };
  return { elements, filters: window.StockAgentHistoryFilters.create(elements) };
}
const first = makeFilters();
first.filters.setValues({ query: '1623.TW', pipelineFilter: 'v2', recommendationFilter: '買入', dataTrustFilter: 'fresh', includeVersions: true });
const restored = makeFilters();
const restoredValues = restored.filters.values();
restored.filters.setValues({ query: '2330.TW', pipelineFilter: 'v3', recommendationFilter: 'all', dataTrustFilter: 'all', includeVersions: true });
const overridden = makeFilters().filters.values();
process.stdout.write(JSON.stringify({ restoredValues, overridden }));
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["restoredValues"] == {
        "query": "1623.TW",
        "pipelineFilter": "v2",
        "recommendationFilter": "買入",
        "dataTrustFilter": "fresh",
        "includeVersions": True,
    }
    assert payload["overridden"] == {
        "query": "2330.TW",
        "pipelineFilter": "v3",
        "recommendationFilter": "all",
        "dataTrustFilter": "all",
        "includeVersions": True,
    }


def test_history_workspace_applies_scoped_quality_review_navigation():
    module_path = STATIC_DIR / "history_workspace.js"
    script = """
(async () => {
  global.window = {
    StockAgentHistoricalQualityAudit: { create: () => ({ load: () => {}, bindEvents: () => {}, resetReviewStatus: () => { global.reviewReset = (global.reviewReset || 0) + 1; } }) },
    StockAgentHistoryWorkspacePanels: {
      create: () => ({
        historyFilters: {
          state: { query: '', pipelineFilter: 'all', recommendationFilter: 'all', dataTrustFilter: 'all', includeVersions: false },
          values() { return this.state; },
          setValues(next) { this.state = { ...this.state, ...next }; global.scope = next; },
          bind: () => {}
        },
        historyPanel: {
          renderReports: () => {}, renderPagination: () => 1, setTrackingCompact: () => {},
          bindEvents: () => {}, clearSelection: () => {}
        },
        reportPreviewPanel: { hide: () => {}, show: () => false },
        reportComparePanel: { bindEvents: () => {} },
        trackingSnapshotPanel: { bindEvents: () => {}, load: async () => {} },
        decisionTrackingPanel: { load: async () => ({ items: [] }) }
      })
    },
    StockAgentHistoryWorkspaceActions: { create: () => ({}) }
  };
  let captured;
  const workspace = require(__MODULE_PATH__);
  const instance = window.StockAgentHistoryWorkspace.create({
    apiClient: { fetchReports: async params => { captured = params; return { reports: [], pagination: { page: 1, total_pages: 1, total: 0, has_prev: false, has_next: false } }; } },
    ui: {},
    elements: { historyIncludeVersions: { checked: false } },
    openReport: () => {}
  });
  await instance.openHistoricalQualityAudit({ query: '1623_TW_v2_report_20260815_154718.html', pipeline: 'v2' });
  process.stdout.write(JSON.stringify({ scope: global.scope, captured, reviewReset: global.reviewReset || 0 }));
})();
""".replace("__MODULE_PATH__", json.dumps(str(module_path)))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["scope"] == {
        "query": "1623_TW_v2_report_20260815_154718.html",
        "pipelineFilter": "v2",
        "recommendationFilter": "all",
        "dataTrustFilter": "all",
        "includeVersions": True
    }
    assert payload["captured"]["query"] == "1623_TW_v2_report_20260815_154718.html"
    assert payload["captured"]["pipeline"] == "v2"
    assert payload["captured"]["includeVersions"] is True
    assert payload["reviewReset"] == 1


def test_historical_audit_navigation_wiring_uses_cache_busters_and_existing_scope():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    style_css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    history_workspace = (STATIC_DIR / "history_workspace.js").read_text(encoding="utf-8")
    watchlist_helpers = (STATIC_DIR / "watchlist_panel_helpers.js").read_text(encoding="utf-8")
    watchlist_panel = (STATIC_DIR / "watchlist_panel.js").read_text(encoding="utf-8")

    assert "data-quality-history-audit" in watchlist_helpers
    assert "StockAgentOpenHistoricalQualityAudit" in watchlist_panel
    assert "openHistoricalQualityAudit" in history_workspace
    assert "StockAgentOpenHistoricalQualityAudit" in app_js
    assert "/static/watchlist_freshness_helpers.js?v=20260902-integer-quality-counts" in index_html
    assert "/static/watchlist_current_quality_helpers.js?v=20260902-integer-summary-counts" in index_html
    assert "/static/report_quality_evidence_freshness_helpers.js?v=20260902-integer-summary-counts" in index_html
    assert "/static/watchlist_panel_helpers.js?v=20260902-pipeline-context-scope" in index_html
    assert "/static/watchlist_panel.js?v=20260816-scoped-quality-review-navigation" in index_html
    assert "/static/history_filters.js?v=20260816-history-scope-persistence" in index_html
    assert "/static/history_workspace.js?v=20260816-scope-transient-state-guard" in index_html
    assert "/static/operator_dashboard_actions.js?v=20260902-repair-queue-scope" in index_html
    assert "/static/operator_summary_panel.js?v=20260902-report-sample-scope" in index_html
    assert "/static/app.js?v=20260821-quality-audit-action" in index_html
    assert "/static/styles/watchlist.css?v=20260816-daily-quality-target-context" in style_css
