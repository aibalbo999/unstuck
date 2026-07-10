import { requestJson } from '../shared/api.js';
import { setAsyncState } from '../shared/async_state.js';
import {
  bindTabs,
  focusPageHeading,
  isValidTicker,
  normalizeTicker,
  tickerFromLocation,
} from '../shared/shell.js';
import { renderSourceStatus } from '../shared/source_status.js';

const form = document.getElementById('stock-form');
const input = document.getElementById('stock-ticker');
const button = document.getElementById('stock-load');
const company = document.getElementById('stock-company');
const answer = document.getElementById('stock-answer-title');
const detail = document.getElementById('stock-answer-detail');
const metrics = document.getElementById('stock-metrics');
const evidence = document.getElementById('stock-evidence');
const statusRoot = document.getElementById('stock-source-status');
let snapshot = null;
let activeTab = 'answer';

function label(value, fallback = '資料不足') {
  return value === null || value === undefined || value === '' ? fallback : String(value);
}

function signedPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return `${number > 0 ? '+' : ''}${number.toFixed(1)}%`;
}

function metric(name, value) {
  const root = document.createElement('div');
  root.className = 'commercial-metric';
  const key = document.createElement('span');
  key.textContent = name;
  const strong = document.createElement('strong');
  strong.textContent = label(value);
  root.append(key, strong);
  return root;
}

function renderSummary(data) {
  const recommendation = data.analyst_outlook?.consensus?.recommendation_label || '資料不足';
  const upside = data.valuation?.analyst_target?.upside_pct;
  const nextEvent = data.event_calendar?.next_event || {};
  const eventLabel = [nextEvent.label, nextEvent.date].filter(Boolean).join(' · ');
  const score = Number(data.data_quality?.score);
  company.textContent = [data.ticker, data.identity?.company_name].filter(Boolean).join(' · ');
  answer.textContent = [recommendation, data.analyst_outlook?.label].filter(Boolean).join('｜');
  detail.textContent = (data.analyst_outlook?.signals || []).join(' · ')
    || '目前證據不足，請查看來源狀態。';
  metrics.replaceChildren(
    metric('現價', data.quote?.price_label),
    metric('資料信心', Number.isFinite(score) ? `${score}/100` : null),
    metric('目標空間', signedPercent(upside)),
    metric('下一事件', eventLabel),
  );
}

function linesFor(tab, data) {
  if (tab === 'fundamentals') {
    return [
      data.profitability_quality?.label,
      ...(data.profitability_quality?.signals || []),
      data.financial_health?.label,
    ];
  }
  if (tab === 'events') {
    return (data.event_calendar?.events || [])
      .map(item => [item.label, item.date].filter(Boolean).join(' · '));
  }
  if (tab === 'technical') {
    return [data.technical_summary?.label, ...(data.technical_summary?.signals || [])];
  }
  return [
    data.analyst_outlook?.label,
    ...(data.analyst_outlook?.signals || []),
    data.data_quality?.status && `資料狀態：${data.data_quality.status}`,
  ];
}

function renderEvidence() {
  const lines = snapshot ? linesFor(activeTab, snapshot).filter(Boolean).slice(0, 6) : [];
  const list = document.createElement('ul');
  list.className = 'commercial-recommendations';
  (lines.length ? lines : ['目前沒有可用證據。']).forEach(text => {
    const item = document.createElement('li');
    item.textContent = text;
    list.append(item);
  });
  evidence.replaceChildren(list);
}

async function loadSnapshot(ticker) {
  const normalized = normalizeTicker(ticker);
  if (!isValidTicker(normalized)) {
    input.setCustomValidity('請輸入 2330.TW、2330 或 AAPL 格式的股票代號');
    input.reportValidity();
    return;
  }
  input.setCustomValidity('');
  setAsyncState(button, statusRoot, 'loading', `正在載入 ${normalized}`);
  try {
    const next = await requestJson(`/api/stocks/${encodeURIComponent(normalized)}/snapshot`);
    snapshot = next;
    renderSummary(next);
    renderEvidence();
    const url = new URL(window.location.href);
    url.searchParams.set('ticker', normalized);
    window.history.replaceState({}, '', url);
    renderSourceStatus(statusRoot, {
      state: 'success',
      message: '股票快照已更新',
      source: next.data_quality?.status || 'Stock Snapshot API',
      updatedAt: next.quote?.as_of || '',
    });
  } catch (error) {
    renderSourceStatus(statusRoot, {
      state: 'error',
      message: error.message,
      source: 'Stock Snapshot API',
    });
  } finally {
    setAsyncState(button, null, 'idle', '');
  }
}

bindTabs(document.getElementById('stock-tabs'), tab => {
  activeTab = tab;
  renderEvidence();
});
form.addEventListener('submit', event => {
  event.preventDefault();
  loadSnapshot(input.value);
});
input.value = tickerFromLocation();
focusPageHeading('stock-title');
renderEvidence();
loadSnapshot(input.value);
