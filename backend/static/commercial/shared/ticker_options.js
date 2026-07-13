import { requestJson } from './api.js';
import { isValidTicker, normalizeTicker } from './shell.js';

function tickerChoice(item) {
  const report = item?.latest_report || item;
  const ticker = normalizeTicker(report?.ticker || item?.ticker || '');
  if (!isValidTicker(ticker)) return null;
  return {
    ticker,
    name: report?.company_name || report?.name || item?.company_name || item?.name || '',
  };
}

export async function loadTickerChoices(request = requestJson) {
  const sources = await Promise.allSettled([
    request('/api/watchlist/symbols?q=&limit=25'),
    request('/api/decision-tracking'),
    request('/api/reports?limit=100'),
  ]);
  const rows = [];
  sources.forEach((source, index) => {
    if (source.status !== 'fulfilled') return;
    rows.push(...(index === 2 ? source.value.reports || [] : source.value.items || []));
  });
  const unique = new Map();
  rows.map(tickerChoice).filter(Boolean).forEach(choice => {
    if (!unique.has(choice.ticker)) unique.set(choice.ticker, choice);
  });
  return [...unique.values()].sort((left, right) => left.ticker.localeCompare(right.ticker));
}
