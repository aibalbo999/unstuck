import { requestJson } from '../shared/api.js';
import { setAsyncState } from '../shared/async_state.js';
import {
  formatPercent,
  formatTwd,
  policyAmounts,
  positionPlan,
} from '../shared/operator_policy.js?v=20260711-operator3';
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
const policyRoot = document.getElementById('stock-policy');
const company = document.getElementById('stock-company');
const answer = document.getElementById('stock-answer-title');
const detail = document.getElementById('stock-answer-detail');
const metrics = document.getElementById('stock-metrics');
const positionForm = document.getElementById('stock-position-form');
const entryInput = document.getElementById('stock-entry-price');
const stopInput = document.getElementById('stock-stop-price');
const positionError = document.getElementById('stock-position-error');
const positionMetrics = document.getElementById('stock-position-metrics');
const evidence = document.getElementById('stock-evidence');
const statusRoot = document.getElementById('stock-source-status');
let snapshot = null;
let activeTab = 'plan';

function label(value, fallback = '資料不足') {
  return value === null || value === undefined || value === '' ? fallback : String(value);
}

function signedPercent(value) {
  const number = Number(value);
  return Number.isFinite(number) ? formatPercent(number) : '資料不足';
}

function metric(name, value, note = '') {
  const root = document.createElement('div');
  root.className = 'commercial-metric';
  const key = document.createElement('span');
  key.textContent = name;
  const strong = document.createElement('strong');
  strong.textContent = label(value);
  root.append(key, strong);
  if (note) {
    const small = document.createElement('small');
    small.textContent = note;
    root.append(small);
  }
  return root;
}

function policyMetric(name, value, note) {
  const root = metric(name, value, note);
  root.className = 'commercial-policy-item';
  return root;
}

function renderPolicy() {
  const amounts = policyAmounts();
  policyRoot.replaceChildren(
    policyMetric('操作資金', formatTwd(amounts.capital), '固定基準'),
    policyMetric('現金保留', formatTwd(amounts.cashReserve), '20%'),
    policyMetric('單一持股上限', formatTwd(amounts.maxPosition), '15%'),
    policyMetric('單筆最大風險', formatTwd(amounts.maxTradeRisk), '1%'),
  );
}

function renderSummary(data) {
  const recommendation = data.analyst_outlook?.consensus?.recommendation_label || '資料不足';
  const target = data.valuation?.analyst_target || {};
  const nextEvent = data.event_calendar?.next_event || {};
  const eventLabel = [nextEvent.label, nextEvent.date].filter(Boolean).join(' · ');
  const score = Number(data.data_quality?.score);
  company.textContent = [data.ticker, data.identity?.company_name].filter(Boolean).join(' · ');
  answer.textContent = [recommendation, data.analyst_outlook?.label].filter(Boolean).join('｜');
  detail.textContent = (data.analyst_outlook?.signals || []).join(' · ')
    || '目前證據不足，請查看來源狀態。';
  metrics.replaceChildren(
    metric('現價', data.quote?.price_label),
    metric('分析師目標', target.label),
    metric('目標空間', signedPercent(target.upside_pct)),
    metric('資料信心', Number.isFinite(score) ? `${score}/100` : null),
    metric('下一事件', eventLabel),
  );
}

function isTaiwanTicker(ticker) {
  return /\.(?:TW|TWO)$/i.test(String(ticker || ''));
}

function currentPositionPlan() {
  if (!snapshot || !isTaiwanTicker(snapshot.ticker)) return null;
  return positionPlan({
    entryPrice: entryInput.value,
    stopPrice: stopInput.value,
    targetPrice: snapshot.valuation?.analyst_target?.price,
  });
}

function renderPositionPlan() {
  positionError.textContent = '';
  positionMetrics.replaceChildren();
  if (!snapshot) return;

  if (!isTaiwanTicker(snapshot.ticker)) {
    entryInput.disabled = true;
    stopInput.disabled = true;
    positionError.textContent = '海外股票需要匯率才能換算 500 萬台幣部位；目前只顯示研究資料。';
    if (activeTab === 'plan') renderEvidence();
    return;
  }

  entryInput.disabled = false;
  stopInput.disabled = false;
  const plan = currentPositionPlan();
  if (!plan) {
    positionError.textContent = '停損價必須大於或等於 0，且低於進場價。';
    if (activeTab === 'plan') renderEvidence();
    return;
  }

  positionMetrics.replaceChildren(
    metric('建議股數', `${plan.shares.toLocaleString('zh-TW')} 股`, plan.binding === 'risk' ? '受風險上限限制' : '受部位上限限制'),
    metric('預估投入', formatTwd(plan.investment)),
    metric('資金占比', `${plan.capitalPct.toFixed(1)}%`),
    metric('每股風險', formatTwd(plan.riskPerShare)),
    metric('最大損失', formatTwd(plan.maxLoss)),
    metric('目標潛在報酬', formatTwd(plan.targetGain)),
    metric('風險報酬比', plan.riskReward === null ? null : `${plan.riskReward.toFixed(2)}x`),
  );
  if (activeTab === 'plan') renderEvidence();
}

function setupPositionInputs(data) {
  const current = Number(data.quote?.price);
  const sixMonthAverage = Number(data.technical_summary?.moving_averages?.ma_6m?.value);
  if (!Number.isFinite(current) || current <= 0) {
    entryInput.value = '';
    stopInput.value = '';
    renderPositionPlan();
    return;
  }
  const stop = Number.isFinite(sixMonthAverage) && sixMonthAverage > 0 && sixMonthAverage < current
    ? sixMonthAverage
    : current * 0.92;
  entryInput.value = current.toFixed(2);
  stopInput.value = stop.toFixed(2);
  renderPositionPlan();
}

function line(name, value) {
  const text = label(value);
  return text === '資料不足' ? `${name}：資料不足` : `${name}：${text}`;
}

function planLines() {
  const plan = currentPositionPlan();
  if (!snapshot) return ['載入股票快照後顯示操作計畫。'];
  if (!isTaiwanTicker(snapshot.ticker)) {
    return ['海外股票尚缺匯率，不能把當地股價直接視為新台幣進行部位試算。'];
  }
  if (!plan) return ['請修正進場價與停損價後再查看操作計畫。'];
  return [
    `建議股數 ${plan.shares.toLocaleString('zh-TW')} 股；投入 ${formatTwd(plan.investment)}。`,
    `占 500 萬資金 ${plan.capitalPct.toFixed(1)}%；最大損失 ${formatTwd(plan.maxLoss)}。`,
    `目標潛在報酬 ${formatTwd(plan.targetGain)}；風險報酬比 ${plan.riskReward === null ? '資料不足' : `${plan.riskReward.toFixed(2)}x`}。`,
    `限制來源：${plan.binding === 'risk' ? '單筆最大風險 1%' : '單一持股上限 15%'}。`,
  ];
}

function valuationLines(data) {
  const valuation = data.valuation || {};
  const target = valuation.analyst_target || {};
  return [
    line('本益比', valuation.pe_ratio?.label),
    line('預估本益比', valuation.forward_pe?.label),
    line('股價淨值比', valuation.pb_ratio?.label),
    line('股價營收比', valuation.ps_ratio?.label),
    line('分析師目標', target.label),
    line('目標空間', signedPercent(target.upside_pct)),
  ];
}

function fundamentalsLines(data) {
  const health = data.financial_health || {};
  const quality = data.profitability_quality || {};
  return [
    line('營收成長', health.revenue_growth?.label),
    line('毛利率', health.gross_margin?.label),
    line('營業利益率', health.operating_margin?.label),
    line('ROE', quality.roe_pct === undefined ? null : `${quality.roe_pct}%`),
    line('自由現金流', health.free_cash_flow?.label),
    line('現金', health.balance_sheet?.cash_label),
    line('負債', health.balance_sheet?.debt_label),
  ];
}

function eventLines(data) {
  return (data.event_calendar?.events || []).map(item => {
    const timing = Number.isFinite(Number(item.days_until))
      ? Number(item.days_until) >= 0 ? `${item.days_until} 天後` : `${Math.abs(item.days_until)} 天前`
      : '';
    return [item.label, item.date, timing].filter(Boolean).join(' · ');
  });
}

function technicalLines(data) {
  const technical = data.technical_summary || {};
  const averages = technical.moving_averages || {};
  const range = technical.range_52w || {};
  const momentum = technical.momentum || {};
  return [
    line('趨勢', technical.label),
    ...['ma_3m', 'ma_6m', 'ma_12m'].map(key => {
      const average = averages[key] || {};
      const value = Number(average.value);
      return line(average.label || key, Number.isFinite(value) ? value.toLocaleString('zh-TW') : null);
    }),
    line('52 週位置', range.position_pct === undefined ? null : `${range.position_pct}%`),
    line('距 52 週高點', formatPercent(range.drawdown_from_high_pct)),
    line('1M 動能', formatPercent(momentum['1m'])),
    line('3M 動能', formatPercent(momentum['3m'])),
    line('1Y 動能', formatPercent(momentum['1y'])),
  ];
}

function linesFor(tab, data) {
  if (tab === 'valuation') return valuationLines(data);
  if (tab === 'fundamentals') return fundamentalsLines(data);
  if (tab === 'events') return eventLines(data);
  if (tab === 'technical') return technicalLines(data);
  return planLines();
}

function renderEvidence() {
  const lines = snapshot ? linesFor(activeTab, snapshot).filter(Boolean) : planLines();
  const list = document.createElement('ul');
  list.className = 'commercial-recommendations commercial-evidence-list';
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
    setupPositionInputs(next);
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
positionForm.addEventListener('submit', event => event.preventDefault());
[entryInput, stopInput].forEach(field => field.addEventListener('input', renderPositionPlan));

input.value = tickerFromLocation();
renderPolicy();
focusPageHeading('stock-title');
renderEvidence();
loadSnapshot(input.value);
