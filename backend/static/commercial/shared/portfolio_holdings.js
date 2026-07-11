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

function numberText(value) {
  return String(Number(Number(value).toFixed(2)));
}

function amountCsv(text, capital) {
  const source = String(text || '').trim();
  const parsed = source ? csvParts(source) : { headers: ['ticker', 'market_value'], rows: [] };
  const tickerIndex = columnIndex(parsed.headers, ['ticker', 'symbol']);
  const marketValueIndex = columnIndex(parsed.headers, ['market_value']);
  const weightIndex = columnIndex(parsed.headers, ['weight', 'weight_pct']);
  if (!Number.isFinite(Number(capital)) || Number(capital) < 100_000) {
    return { source, error: '操作資金至少需要 NT$100,000。' };
  }
  if (tickerIndex < 0) return { source, error: 'CSV 標題列缺少 ticker。' };
  if (marketValueIndex < 0 && weightIndex < 0) {
    return { source, error: 'CSV 標題列需要 weight 或 market_value。' };
  }

  const amountIndex = marketValueIndex >= 0 ? marketValueIndex : weightIndex;
  const headers = [...parsed.headers];
  headers[amountIndex] = 'market_value';
  const rows = [];
  for (const sourceRow of parsed.rows) {
    const row = [...sourceRow];
    while (row.length < headers.length) row.push('');
    const ticker = tickerText(row[tickerIndex]);
    const sourceValue = Number(row[amountIndex]);
    if (!ticker || !Number.isFinite(sourceValue) || sourceValue < 0) {
      return { source, error: 'CSV 含有無效的股票代號或金額。' };
    }
    const amount = marketValueIndex >= 0
      ? sourceValue
      : Number(capital) * sourceValue / 100;
    row[tickerIndex] = ticker;
    row[amountIndex] = numberText(amount);
    rows.push({ ticker, amount, row });
  }
  return { source, headers, rows, tickerIndex, amountIndex, error: '' };
}

function balanceCash(converted) {
  const nonCash = converted.rows.filter(item => item.ticker !== 'CASH');
  const invested = nonCash.reduce((sum, item) => sum + item.amount, 0);
  const capital = Number(converted.capital);
  if (invested > capital) {
    return {
      text: converted.source,
      error: `股票投入總額超過操作資金 ${numberText(invested - capital)} 元。`,
    };
  }
  const priorCash = converted.rows.find(item => item.ticker === 'CASH');
  const cashRow = priorCash
    ? [...priorCash.row]
    : Array(converted.headers.length).fill('');
  cashRow[converted.tickerIndex] = 'CASH';
  cashRow[converted.amountIndex] = numberText(capital - invested);
  return {
    text: serialize(converted.headers, [...nonCash.map(item => item.row), cashRow]),
    error: '',
  };
}

export function parseAmountHoldings(text, capital) {
  const converted = amountCsv(text, capital);
  if (converted.error) return [];
  return converted.rows.map(item => ({
    ticker: item.ticker,
    amount: item.amount,
    weight: Number((item.amount / Number(capital) * 100).toFixed(4)),
  }));
}

export function upsertAmountHolding(text, holding) {
  const source = String(text || '').trim();
  const ticker = tickerText(holding?.ticker);
  const amount = Number(holding?.amount);
  const capital = Number(holding?.capital);
  if (!ticker || ticker === 'CASH') {
    return { text: source, error: '請選擇股票；Cash 由系統自動計算。' };
  }
  if (holding?.amount === '' || !Number.isFinite(amount) || amount <= 0) {
    return { text: source, error: '投入金額必須大於 0。' };
  }
  const converted = amountCsv(source, capital);
  if (converted.error) return { text: source, error: converted.error };
  converted.capital = capital;
  const existing = converted.rows.find(item => item.ticker === ticker);
  if (existing) {
    existing.amount = amount;
    existing.row[converted.amountIndex] = numberText(amount);
  } else {
    const row = Array(converted.headers.length).fill('');
    row[converted.tickerIndex] = ticker;
    row[converted.amountIndex] = numberText(amount);
    converted.rows.push({ ticker, amount, row });
  }
  return balanceCash(converted);
}

export function removeAmountHolding(text, ticker, capital) {
  const source = String(text || '').trim();
  const target = tickerText(ticker);
  if (!target || target === 'CASH') return source;
  const converted = amountCsv(source, capital);
  if (converted.error) return source;
  converted.capital = Number(capital);
  converted.rows = converted.rows.filter(item => item.ticker !== target);
  return balanceCash(converted).text;
}

export function rebalanceAmountCash(text, capital) {
  const source = String(text || '').trim();
  const converted = amountCsv(source, capital);
  if (converted.error) return source;
  converted.capital = Number(capital);
  return balanceCash(converted).text;
}
