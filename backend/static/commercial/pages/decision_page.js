import { requestJson } from '../shared/api.js';
import {
  formatPercent,
  formatTwd,
  OPERATOR_POLICY,
  policyAmounts,
} from '../shared/operator_policy.js?v=20260711-operator5';
import { mountOperatorPolicyEditor } from '../shared/operator_policy_ui.js?v=20260711-operator5';
import { focusPageHeading, stockPageHref } from '../shared/shell.js';
import { renderSourceStatus } from '../shared/source_status.js';

const title = document.getElementById('decision-answer-title');
const detail = document.getElementById('decision-answer-detail');
const policyRoot = document.getElementById('decision-policy');
const summaryMetrics = document.getElementById('decision-summary-metrics');
const filters = document.getElementById('decision-filters');
const filterStatus = document.getElementById('decision-filter-status');
const list = document.getElementById('decision-task-list');
const primary = document.getElementById('decision-primary');
const allAction = document.getElementById('decision-all-action');
const emptyAction = document.getElementById('decision-empty-action');
const statusRoot = document.getElementById('decision-source-status');
let queueTasks = [];
let activeFilter = 'all';
let activePolicy = OPERATOR_POLICY;

function finite(value) {
  const number = Number(value);
  return value === null || value === undefined || value === '' || !Number.isFinite(number)
    ? null
    : number;
}

function operatorMetric(name, value, note = '') {
  const root = document.createElement('div');
  root.className = 'commercial-policy-item';
  const label = document.createElement('span');
  label.textContent = name;
  const strong = document.createElement('strong');
  strong.textContent = value;
  root.append(label, strong);
  if (note) {
    const small = document.createElement('small');
    small.textContent = note;
    root.append(small);
  }
  return root;
}

function summaryMetric(name, value) {
  const root = document.createElement('div');
  root.className = 'commercial-metric';
  const label = document.createElement('span');
  label.textContent = name;
  const strong = document.createElement('strong');
  strong.textContent = String(value);
  root.append(label, strong);
  return root;
}

function renderPolicy() {
  const amounts = policyAmounts(activePolicy);
  policyRoot.replaceChildren(
    operatorMetric('操作資金', formatTwd(amounts.capital), '目前設定'),
    operatorMetric('現金保留', formatTwd(amounts.cashReserve), `${activePolicy.cashReservePct}%`),
    operatorMetric('單一持股上限', formatTwd(amounts.maxPosition), `${activePolicy.maxPositionPct}%`),
    operatorMetric('單筆最大風險', formatTwd(amounts.maxTradeRisk), `${activePolicy.maxTradeRiskPct}%`),
  );
}

function mapItem(item) {
  const report = item.latest_report || (item.latest_reports || [])[0] || {};
  const tracking = report.decision_tracking || {};
  const freshness = report.decision_freshness || {};
  const refreshStatus = String(item.last_refresh_status || '');
  const returnPct = finite(tracking.return_pct);
  let priority = 10;
  let reason = '例行檢查';
  if (freshness.requires_rerun) {
    priority = 40;
    reason = '報告需要重跑';
  } else if (refreshStatus === 'error') {
    priority = 30;
    reason = '資料更新失敗';
  } else if (returnPct !== null && returnPct < 0) {
    priority = 20;
    reason = '報酬轉弱，檢查原論點';
  }
  return {
    ticker: String(report.ticker || item.ticker || '').toUpperCase(),
    company: report.company_name || item.company_name || '',
    priority,
    reason,
    recommendation: tracking.recommendation || '資料不足',
    latestPrice: finite(tracking.latest_price),
    returnPct,
    targetGap: finite(tracking.target_12m_gap_pct),
    confidence: tracking.confidence || '資料不足',
    requiresRerun: Boolean(freshness.requires_rerun),
    refreshError: refreshStatus === 'error',
  };
}

function fact(name, value, state = '') {
  const root = document.createElement('span');
  root.className = 'commercial-task-fact';
  if (state) root.dataset.state = state;
  const label = document.createElement('small');
  label.textContent = name;
  const strong = document.createElement('strong');
  strong.textContent = value;
  root.append(label, strong);
  return root;
}

function taskListItem(task) {
  const item = document.createElement('li');
  const link = document.createElement('a');
  link.className = 'commercial-task-link';
  link.href = stockPageHref(task.ticker, 'decision');

  const heading = document.createElement('span');
  heading.className = 'commercial-task-heading';
  const ticker = document.createElement('strong');
  ticker.textContent = [task.ticker, task.company].filter(Boolean).join(' · ');
  const reason = document.createElement('span');
  reason.className = 'commercial-status-badge';
  reason.textContent = task.reason;
  heading.append(ticker, reason);

  const facts = document.createElement('span');
  facts.className = 'commercial-task-facts';
  const price = task.latestPrice === null
    ? '資料不足'
    : task.latestPrice.toLocaleString('zh-TW', { maximumFractionDigits: 2 });
  facts.append(
    fact('建議', task.recommendation),
    fact('最新價', price),
    fact(
      '追蹤報酬',
      formatPercent(task.returnPct),
      task.returnPct === null ? '' : task.returnPct < 0 ? 'negative' : 'positive',
    ),
    fact(
      '12月目標差',
      formatPercent(task.targetGap),
      task.targetGap === null ? '' : task.targetGap < 0 ? 'negative' : 'positive',
    ),
    fact('信心', task.confidence),
  );
  link.append(heading, facts);
  item.append(link);
  return item;
}

function filteredTasks() {
  if (activeFilter === 'rerun') return queueTasks.filter(task => task.requiresRerun);
  if (activeFilter === 'weak') {
    return queueTasks.filter(task => task.returnPct !== null && task.returnPct < 0);
  }
  return queueTasks;
}

function renderFilteredTasks() {
  const tasks = filteredTasks().slice(0, 5);
  list.replaceChildren(...tasks.map(taskListItem));
  if (!tasks.length && queueTasks.length) {
    const empty = document.createElement('li');
    empty.className = 'commercial-empty-row';
    empty.textContent = '這個篩選目前沒有待處理股票。';
    list.append(empty);
  }
  filterStatus.textContent = `顯示 ${tasks.length} 筆；總計 ${queueTasks.length} 筆待檢查。`;
  filters.querySelectorAll('[data-filter]').forEach(button => {
    button.setAttribute('aria-pressed', button.dataset.filter === activeFilter ? 'true' : 'false');
  });
}

function renderSummary() {
  summaryMetrics.replaceChildren(
    summaryMetric('待處理', queueTasks.length),
    summaryMetric('需重跑', queueTasks.filter(task => task.requiresRerun).length),
    summaryMetric(
      '報酬轉弱',
      queueTasks.filter(task => task.returnPct !== null && task.returnPct < 0).length,
    ),
    summaryMetric('更新失敗', queueTasks.filter(task => task.refreshError).length),
  );
}

async function loadDecisionQueue() {
  renderSourceStatus(statusRoot, { state: 'loading', message: '正在讀取追蹤清單' });
  try {
    const payload = await requestJson('/api/decision-tracking');
    queueTasks = (payload.items || [])
      .map(mapItem)
      .filter(item => item.ticker)
      .sort((left, right) => right.priority - left.priority);
    activeFilter = 'all';
    renderSummary();
    renderFilteredTasks();

    if (!queueTasks.length) {
      title.textContent = '尚無追蹤股票';
      detail.textContent = '先建立追蹤清單，系統才會整理每日待辦。';
      primary.hidden = true;
      allAction.hidden = true;
      emptyAction.hidden = false;
    } else {
      title.textContent = `今天有 ${queueTasks.length} 件事要處理`;
      detail.textContent = '依需重跑、更新錯誤與追蹤報酬排序；先檢查最高優先項目。';
      primary.href = stockPageHref(queueTasks[0].ticker, 'decision');
      primary.textContent = `檢查最高優先股票 ${queueTasks[0].ticker}`;
      primary.hidden = false;
      allAction.hidden = false;
      emptyAction.hidden = true;
    }
    renderSourceStatus(statusRoot, {
      state: 'success',
      message: '追蹤清單已更新',
      source: 'Decision Tracking API',
    });
  } catch (error) {
    queueTasks = [];
    renderSummary();
    renderFilteredTasks();
    title.textContent = '目前無法讀取今日決策';
    detail.textContent = '請確認服務狀態後重新整理頁面。';
    primary.hidden = true;
    allAction.hidden = true;
    emptyAction.hidden = true;
    renderSourceStatus(statusRoot, {
      state: 'error',
      message: error.message,
      source: 'Decision Tracking API',
    });
  }
}

filters.addEventListener('click', event => {
  const button = event.target.closest('[data-filter]');
  if (!button) return;
  activeFilter = button.dataset.filter;
  renderFilteredTasks();
});

mountOperatorPolicyEditor(document.getElementById('decision-policy-editor'), {
  onChange(policy) {
    activePolicy = policy;
    renderPolicy();
  },
});
focusPageHeading('decision-title');
loadDecisionQueue();
