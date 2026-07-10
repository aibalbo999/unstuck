import { requestJson } from '../shared/api.js';
import { focusPageHeading, stockPageHref } from '../shared/shell.js';
import { renderSourceStatus } from '../shared/source_status.js';

const title = document.getElementById('decision-answer-title');
const detail = document.getElementById('decision-answer-detail');
const list = document.getElementById('decision-task-list');
const primary = document.getElementById('decision-primary');
const emptyAction = document.getElementById('decision-empty-action');
const statusRoot = document.getElementById('decision-source-status');

function mapItem(item) {
  const report = item.latest_report || (item.latest_reports || [])[0] || {};
  const tracking = report.decision_tracking || {};
  const freshness = report.decision_freshness || {};
  const refreshStatus = String(item.last_refresh_status || '');
  const returnPct = Number(tracking.return_pct);
  let priority = 10;
  let reason = '例行檢查';
  if (freshness.requires_rerun) {
    priority = 40;
    reason = '報告需要重跑';
  } else if (refreshStatus === 'error') {
    priority = 30;
    reason = '資料更新失敗';
  } else if (Number.isFinite(returnPct) && returnPct < 0) {
    priority = 20;
    reason = '報酬轉弱，檢查原論點';
  }
  return {
    ticker: String(report.ticker || item.ticker || '').toUpperCase(),
    company: report.company_name || item.company_name || '',
    priority,
    reason,
  };
}

function taskListItem(task) {
  const item = document.createElement('li');
  const link = document.createElement('a');
  link.className = 'commercial-task-link';
  link.href = stockPageHref(task.ticker, 'decision');
  const ticker = document.createElement('strong');
  ticker.textContent = [task.ticker, task.company].filter(Boolean).join(' · ');
  const reason = document.createElement('span');
  reason.textContent = task.reason;
  link.append(ticker, reason);
  item.append(link);
  return item;
}

async function loadDecisionQueue() {
  renderSourceStatus(statusRoot, { state: 'loading', message: '正在讀取追蹤清單' });
  try {
    const payload = await requestJson('/api/decision-tracking');
    const allTasks = (payload.items || [])
      .map(mapItem)
      .filter(item => item.ticker)
      .sort((left, right) => right.priority - left.priority);
    const tasks = allTasks.slice(0, 3);
    list.replaceChildren(...tasks.map(taskListItem));
    if (!tasks.length) {
      title.textContent = '尚無追蹤股票';
      detail.textContent = '先建立追蹤清單，系統才會整理每日待辦。';
      primary.hidden = true;
      emptyAction.hidden = false;
    } else {
      title.textContent = `今天有 ${allTasks.length} 件事要處理`;
      detail.textContent = tasks.length < allTasks.length
        ? `先顯示優先度最高的 ${tasks.length} 項。`
        : '依需重跑、更新錯誤與報酬轉弱排序。';
      primary.href = stockPageHref(tasks[0].ticker, 'decision');
      primary.textContent = `開始檢查 ${tasks[0].ticker}`;
      primary.hidden = false;
      emptyAction.hidden = true;
    }
    renderSourceStatus(statusRoot, {
      state: 'success',
      message: '追蹤清單已更新',
      source: 'Decision Tracking API',
    });
  } catch (error) {
    title.textContent = '目前無法讀取今日決策';
    detail.textContent = '請確認服務狀態後重新整理頁面。';
    list.replaceChildren();
    primary.hidden = true;
    emptyAction.hidden = true;
    renderSourceStatus(statusRoot, {
      state: 'error',
      message: error.message,
      source: 'Decision Tracking API',
    });
  }
}

focusPageHeading('decision-title');
loadDecisionQueue();
