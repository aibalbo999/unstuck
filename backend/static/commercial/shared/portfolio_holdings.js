function csvParts(text) {
  const lines = String(text || '').trim().split(/\r?\n/).filter(Boolean);
  if (!lines.length) return { headers: [], rows: [] };
  const headers = lines[0].split(',').map(value => value.trim());
  const rows = lines.slice(1).map(line => line.split(',').map(value => value.trim()));
  return { headers, rows };
}

function columnIndex(headers, names) {
  const normalized = headers.map(value => value.toLowerCase());
  return names.map(name => normalized.indexOf(name)).find(index => index >= 0) ?? -1;
}

function tickerText(value) {
  return String(value || '').trim().toUpperCase();
}

function serialize(headers, rows) {
  return [headers, ...rows].map(row => row.join(',')).join('\n');
}

export function parseWeightHoldings(text) {
  const { headers, rows } = csvParts(text);
  const tickerIndex = columnIndex(headers, ['ticker', 'symbol']);
  const weightIndex = columnIndex(headers, ['weight', 'weight_pct']);
  if (tickerIndex < 0 || weightIndex < 0) return [];
  return rows.flatMap(row => {
    const ticker = tickerText(row[tickerIndex]);
    const weight = Number(row[weightIndex]);
    return ticker && Number.isFinite(weight) ? [{ ticker, weight }] : [];
  });
}

export function upsertWeightHolding(text, holding) {
  const ticker = tickerText(holding?.ticker);
  const weight = Number(holding?.weight);
  if (!ticker) return { text: String(text || ''), error: '請先選擇股票代號。' };
  if (!Number.isFinite(weight) || weight < 0 || weight > 100) {
    return { text: String(text || ''), error: '持股權重必須介於 0% 到 100%。' };
  }

  const source = String(text || '').trim();
  const parsed = source ? csvParts(source) : { headers: ['ticker', 'weight'], rows: [] };
  const tickerIndex = columnIndex(parsed.headers, ['ticker', 'symbol']);
  const weightIndex = columnIndex(parsed.headers, ['weight', 'weight_pct']);
  const marketValueIndex = columnIndex(parsed.headers, ['market_value']);
  if (tickerIndex < 0) return { text: source, error: 'CSV 標題列缺少 ticker。' };
  if (weightIndex < 0) {
    const message = marketValueIndex >= 0
      ? '目前 CSV 使用 market_value，請用檔案或文字直接編輯市值。'
      : 'CSV 標題列需要 weight 或 weight_pct。';
    return { text: source, error: message };
  }

  const existing = parsed.rows.find(row => tickerText(row[tickerIndex]) === ticker);
  if (existing) {
    while (existing.length < parsed.headers.length) existing.push('');
    existing[weightIndex] = String(weight);
  } else {
    const row = Array(parsed.headers.length).fill('');
    row[tickerIndex] = ticker;
    row[weightIndex] = String(weight);
    parsed.rows.push(row);
  }
  return { text: serialize(parsed.headers, parsed.rows), error: '' };
}

export function removeHolding(text, ticker) {
  const parsed = csvParts(text);
  const tickerIndex = columnIndex(parsed.headers, ['ticker', 'symbol']);
  if (tickerIndex < 0) return String(text || '');
  const target = tickerText(ticker);
  const rows = parsed.rows.filter(row => tickerText(row[tickerIndex]) !== target);
  return serialize(parsed.headers, rows);
}
