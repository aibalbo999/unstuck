import { requestJson } from '../shared/api.js';
import { setAsyncState } from '../shared/async_state.js';
import { bindTabs, focusPageHeading } from '../shared/shell.js';
import { renderSourceStatus } from '../shared/source_status.js';

const form = document.getElementById('portfolio-form');
const input = document.getElementById('portfolio-csv');
const errorRoot = document.getElementById('portfolio-csv-error');
const button = document.getElementById('portfolio-run');
const answer = document.getElementById('portfolio-answer-title');
const detail = document.getElementById('portfolio-answer-detail');
const metrics = document.getElementById('portfolio-metrics');
const recommendations = document.getElementById('portfolio-recommendations');
const evidence = document.getElementById('portfolio-evidence');
const statusRoot = document.getElementById('portfolio-source-status');
let report = null;
let activeTab = 'exposure';

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

function metric(name, value) {
  const root = document.createElement('div');
  root.className = 'commercial-metric';
  const key = document.createElement('span');
  key.textContent = name;
  const strong = document.createElement('strong');
  strong.textContent = String(value ?? '資料不足');
  root.append(key, strong);
  return root;
}

function healthScore(payload) {
  const flagPenalty = (payload.risk_flags || []).length * 12;
  const invalidPenalty = (payload.thesis_health?.invalidated || []).length * 12;
  const missingPenalty = Math.min((payload.thesis_health?.missing || []).length * 5, 20);
  return Math.max(0, 100 - flagPenalty - invalidPenalty - missingPenalty);
}

function recommendationLines(payload) {
  const top = payload.concentration?.top_position || {};
  const lines = [];
  if ((payload.risk_flags || []).includes('single_position_over_40_pct')) {
    lines.push(`降低 ${top.ticker || '最大部位'} 權重；目前 ${top.weight_pct}%`);
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
    ? lines.slice(0, 3)
    : ['目前沒有超過門檻的集中風險；維持例行檢查。'];
}

function renderReport(payload) {
  const score = healthScore(payload);
  const top = payload.concentration?.top_position || {};
  const lines = recommendationLines(payload);
  answer.textContent = `健康度 ${score}｜${(payload.risk_flags || []).length ? '需要調整' : '風險在門檻內'}`;
  detail.textContent = `${payload.total_positions || 0} 個部位 · ${lines.length} 項下一步`;
  metrics.replaceChildren(
    metric('健康度', score),
    metric('最大部位', top.ticker),
    metric('最大權重', top.weight_pct === undefined ? null : `${top.weight_pct}%`),
    metric('風險旗標', (payload.risk_flags || []).length),
  );
  recommendations.replaceChildren(...lines.map(text => {
    const item = document.createElement('li');
    item.textContent = text;
    return item;
  }));
  renderEvidence();
}

function renderEvidence() {
  if (!report) {
    evidence.textContent = '完成健檢後顯示細節。';
    return;
  }
  if (activeTab === 'scenario') {
    evidence.textContent = '目前壓力來源：'
      + ((report.risk_flags || []).join('、') || '沒有超過門檻的風險旗標');
  } else if (activeTab === 'contribution') {
    evidence.textContent = '持股權重由高至低：'
      + (report.positions || []).map(item => `${item.ticker} ${item.weight_pct}%`).join('、');
  } else {
    evidence.textContent = '產業曝險：'
      + Object.entries(report.concentration?.sector_weights || {})
        .map(([key, value]) => `${key} ${value}%`).join('、');
  }
}

bindTabs(document.getElementById('portfolio-tabs'), tab => {
  activeTab = tab;
  renderEvidence();
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
