import { requestJson } from '../shared/api.js';
import { setAsyncState } from '../shared/async_state.js';
import {
  amountForWeight,
  capitalFromCsv,
  formatTwd,
  OPERATOR_POLICY,
  policyAmounts,
  trimToPositionLimit,
} from '../shared/operator_policy.js?v=20260711-operator4';
import { mountOperatorPolicyEditor } from '../shared/operator_policy_ui.js?v=20260711-operator4';
import { bindTabs, focusPageHeading } from '../shared/shell.js';
import { renderSourceStatus } from '../shared/source_status.js';

const form = document.getElementById('portfolio-form');
const input = document.getElementById('portfolio-csv');
const errorRoot = document.getElementById('portfolio-csv-error');
const button = document.getElementById('portfolio-run');
const policyRoot = document.getElementById('portfolio-policy');
const answer = document.getElementById('portfolio-answer-title');
const detail = document.getElementById('portfolio-answer-detail');
const capitalMetrics = document.getElementById('portfolio-capital-metrics');
const recommendations = document.getElementById('portfolio-recommendations');
const allocationPanel = document.getElementById('portfolio-allocation-panel');
const positionRows = document.getElementById('portfolio-position-rows');
const evidence = document.getElementById('portfolio-evidence');
const statusRoot = document.getElementById('portfolio-source-status');
let report = null;
let activeTab = 'allocation';
let basisCapital = OPERATOR_POLICY.capital;
let actionLines = [];
let activePolicy = OPERATOR_POLICY;

export function validatePortfolioCsv(text) {
  const lines = String(text || '').trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return '至少需要標題列與一筆持股。';
  const headers = lines[0].split(',').map(value => value.trim().toLowerCase());
  if (!headers.includes('ticker') && !headers.includes('symbol')) {
    return '標題列缺少 ticker。';
  }
  if (!headers.includes('weight')
      && !headers.includes('weight_pct')
      && !headers.includes('market_value')) {
    return '標題列需要 weight 或 market_value。';
  }
  const width = headers.length;
  const invalid = lines.slice(1).findIndex(line => line.split(',').length !== width);
  return invalid >= 0 ? `第 ${invalid + 2} 列欄位數與標題列不同。` : '';
}

function metric(name, value, note = '') {
  const root = document.createElement('div');
  root.className = 'commercial-metric';
  const key = document.createElement('span');
  key.textContent = name;
  const strong = document.createElement('strong');
  strong.textContent = String(value ?? '資料不足');
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
  const amounts = policyAmounts(activePolicy);
  policyRoot.replaceChildren(
    policyMetric('操作資金', formatTwd(amounts.capital), '目前設定'),
    policyMetric('現金保留', formatTwd(amounts.cashReserve), `${activePolicy.cashReservePct}%`),
    policyMetric('單一持股上限', formatTwd(amounts.maxPosition), `${activePolicy.maxPositionPct}%`),
    policyMetric('單筆最大風險', formatTwd(amounts.maxTradeRisk), `${activePolicy.maxTradeRiskPct}%`),
  );
}

function isCash(position) {
  return String(position.ticker || '').toUpperCase() === 'CASH'
    || String(position.sector || '').toLowerCase() === 'cash';
}

function positionPolicy() {
  return { ...activePolicy, capital: basisCapital };
}

function amountForPosition(position) {
  return amountForWeight(position.weight_pct, basisCapital);
}

function trimAmount(position) {
  return isCash(position) ? 0 : trimToPositionLimit(position.weight_pct, positionPolicy());
}

function countryLeader(payload) {
  return Object.entries(payload.concentration?.country_weights || {})
    .sort((left, right) => Number(right[1]) - Number(left[1]))[0] || [];
}

function cashPosition(payload) {
  return (payload.positions || []).find(isCash) || null;
}

function operatorViolations(payload) {
  const overweight = (payload.positions || [])
    .filter(position => !isCash(position) && Number(position.weight_pct) > activePolicy.maxPositionPct)
    .length;
  const cashWeight = Number(cashPosition(payload)?.weight_pct || 0);
  return overweight + (cashWeight < activePolicy.cashReservePct ? 1 : 0);
}

function healthScore(payload) {
  const flagPenalty = (payload.risk_flags || []).length * 10;
  const operatorPenalty = operatorViolations(payload) * 10;
  const invalidPenalty = (payload.thesis_health?.invalidated || []).length * 10;
  const missingPenalty = Math.min((payload.thesis_health?.missing || []).length * 4, 16);
  return Math.max(0, 100 - flagPenalty - operatorPenalty - invalidPenalty - missingPenalty);
}

function recommendationLines(payload) {
  const lines = [];
  const overweight = (payload.positions || [])
    .filter(position => !isCash(position) && Number(position.weight_pct) > activePolicy.maxPositionPct)
    .sort((left, right) => Number(right.weight_pct) - Number(left.weight_pct));
  overweight.forEach(position => {
    lines.push(
      `${position.ticker} 由 ${position.weight_pct}% 降至 ${activePolicy.maxPositionPct}%，減少 ${formatTwd(trimAmount(position))}`,
    );
  });

  const cashWeight = Number(cashPosition(payload)?.weight_pct || 0);
  if (cashWeight < activePolicy.cashReservePct) {
    const required = amountForWeight(activePolicy.cashReservePct - cashWeight, basisCapital);
    lines.push(`現金由 ${cashWeight}% 補至 ${activePolicy.cashReservePct}%，增加 ${formatTwd(required)}`);
  }
  if ((payload.risk_flags || []).includes('sector_over_60_pct')) {
    lines.push('降低最大產業集中度，避免單一產業超過 60%。');
  }
  if ((payload.risk_flags || []).includes('country_over_80_pct')) {
    lines.push('增加不同市場曝險，避免單一市場超過 80%。');
  }
  if ((payload.thesis_health?.invalidated || []).length) {
    lines.push(`複查失效論點：${payload.thesis_health.invalidated.join('、')}`);
  }
  if ((payload.thesis_health?.missing || []).length) {
    lines.push(`補齊投資論點：${payload.thesis_health.missing.join('、')}`);
  }
  return lines.length
    ? lines.slice(0, 5)
    : ['目前符合操作護欄；維持例行檢查。'];
}

function renderPositionTable(payload) {
  const rows = (payload.positions || []).map(position => {
    const row = document.createElement('tr');
    const ticker = document.createElement('th');
    ticker.scope = 'row';
    ticker.textContent = position.ticker || '資料不足';
    const weight = document.createElement('td');
    weight.textContent = `${position.weight_pct}%`;
    const amount = document.createElement('td');
    amount.textContent = formatTwd(amountForPosition(position));
    const trim = document.createElement('td');
    const reduction = trimAmount(position);
    trim.textContent = isCash(position)
      ? '現金保留'
      : reduction > 0 ? `減少 ${formatTwd(reduction)}` : '在上限內';
    if (reduction > 0) trim.dataset.state = 'negative';
    row.append(ticker, weight, amount, trim);
    return row;
  });
  positionRows.replaceChildren(...rows);
}

function renderCapitalMetrics(payload) {
  const cash = cashPosition(payload);
  const cashAmount = cash ? amountForPosition(cash) : 0;
  const allocated = Math.max(0, basisCapital - cashAmount);
  const top = payload.concentration?.top_position || {};
  const [country, countryWeight] = countryLeader(payload);
  const sourceNote = basisCapital === activePolicy.capital
    ? '目前操作資金基準'
    : `較操作資金 ${formatTwd(basisCapital - activePolicy.capital)}`;
  capitalMetrics.replaceChildren(
    metric('總資金', formatTwd(basisCapital), sourceNote),
    metric('已配置', formatTwd(allocated)),
    metric('現金', formatTwd(cashAmount), cash ? `${cash.weight_pct}%` : '0%'),
    metric('最大部位', formatTwd(amountForWeight(top.weight_pct, basisCapital)), top.ticker || ''),
    metric('最大國家曝險', country ? `${country} ${countryWeight}%` : null),
  );
}

function evidenceList(lines) {
  const list = document.createElement('ul');
  list.className = 'commercial-recommendations commercial-evidence-list';
  lines.forEach(text => {
    const item = document.createElement('li');
    item.textContent = text;
    list.append(item);
  });
  return list;
}

function renderEvidence() {
  const allocationActive = activeTab === 'allocation';
  allocationPanel.hidden = !allocationActive;
  evidence.hidden = allocationActive;
  if (allocationActive) return;
  if (!report) {
    evidence.textContent = '完成健檢後顯示細節。';
    return;
  }
  if (activeTab === 'exposure') {
    const sectorLines = Object.entries(report.concentration?.sector_weights || {})
      .sort((left, right) => Number(right[1]) - Number(left[1]))
      .map(([key, value]) => `產業 ${key}：${value}%`);
    const countryLines = Object.entries(report.concentration?.country_weights || {})
      .sort((left, right) => Number(right[1]) - Number(left[1]))
      .map(([key, value]) => `國家 ${key}：${value}%`);
    evidence.replaceChildren(evidenceList([...sectorLines, ...countryLines]));
  } else if (activeTab === 'thesis') {
    const invalidated = (report.thesis_health?.invalidated || []).map(ticker => `失效論點：${ticker}`);
    const missing = (report.thesis_health?.missing || []).map(ticker => `缺少論點：${ticker}`);
    evidence.replaceChildren(evidenceList(
      invalidated.length || missing.length ? [...invalidated, ...missing] : ['所有持股都有有效投資論點。'],
    ));
  } else {
    evidence.replaceChildren(evidenceList(actionLines));
  }
}

function renderReport(payload) {
  const score = healthScore(payload);
  actionLines = recommendationLines(payload);
  answer.textContent = `健康度 ${score}｜${operatorViolations(payload) ? '需要調整' : '操作護欄內'}`;
  detail.textContent = `${payload.total_positions || 0} 個部位 · ${actionLines.length} 項下一步`;
  renderCapitalMetrics(payload);
  recommendations.replaceChildren(...actionLines.slice(0, 3).map(text => {
    const item = document.createElement('li');
    item.textContent = text;
    return item;
  }));
  renderPositionTable(payload);
  renderEvidence();
}

bindTabs(document.getElementById('portfolio-tabs'), tab => {
  activeTab = tab;
  renderEvidence();
});
mountOperatorPolicyEditor(document.getElementById('portfolio-policy-editor'), {
  onChange(policy) {
    activePolicy = policy;
    basisCapital = capitalFromCsv(input.value, activePolicy.capital);
    renderPolicy();
    if (report) renderReport(report);
  },
});
focusPageHeading('portfolio-title');
form.addEventListener('submit', async event => {
  event.preventDefault();
  const validationError = validatePortfolioCsv(input.value);
  errorRoot.textContent = validationError;
  if (validationError) {
    input.focus();
    return;
  }
  setAsyncState(button, statusRoot, 'loading', '正在分析組合');
  try {
    basisCapital = capitalFromCsv(input.value, activePolicy.capital);
    report = await requestJson('/api/watchlist/portfolio/risk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ csv: input.value, thesis_health: {} }),
    });
    renderReport(report);
    renderSourceStatus(statusRoot, {
      state: 'success',
      message: '組合健檢已更新',
      source: 'Portfolio Risk API',
    });
  } catch (requestError) {
    renderSourceStatus(statusRoot, {
      state: 'error',
      message: requestError.message,
      source: 'Portfolio Risk API',
    });
  } finally {
    setAsyncState(button, null, 'idle', '');
  }
});
