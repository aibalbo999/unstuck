export const OPERATOR_POLICY = Object.freeze({
  capital: 5_000_000,
  cashReservePct: 20,
  maxPositionPct: 15,
  maxTradeRiskPct: 1,
});

function finite(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function formatTwd(value) {
  const number = finite(value);
  if (number === null) return '資料不足';
  return new Intl.NumberFormat('zh-TW', {
    style: 'currency',
    currency: 'TWD',
    maximumFractionDigits: 0,
  }).format(number);
}

export function formatPercent(value, digits = 1) {
  const number = finite(value);
  if (number === null) return '資料不足';
  return `${number > 0 ? '+' : ''}${number.toFixed(digits)}%`;
}

export function policyAmounts(policy = OPERATOR_POLICY) {
  const cashReserve = policy.capital * policy.cashReservePct / 100;
  return {
    capital: policy.capital,
    cashReserve,
    deployableCapital: policy.capital - cashReserve,
    maxPosition: policy.capital * policy.maxPositionPct / 100,
    maxTradeRisk: policy.capital * policy.maxTradeRiskPct / 100,
  };
}

export function amountForWeight(weightPct, capital = OPERATOR_POLICY.capital) {
  const weight = finite(weightPct);
  return weight === null ? null : capital * weight / 100;
}

export function capitalFromCsv(text, fallbackCapital = OPERATOR_POLICY.capital) {
  const lines = String(text || '').trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return fallbackCapital;
  const headers = lines[0].split(',').map(value => value.trim().toLowerCase());
  const marketValueIndex = headers.indexOf('market_value');
  if (marketValueIndex < 0) return fallbackCapital;
  const values = lines.slice(1).map(line => Number(line.split(',')[marketValueIndex]));
  if (!values.length || values.some(value => !Number.isFinite(value) || value < 0)) {
    return fallbackCapital;
  }
  return values.reduce((sum, value) => sum + value, 0) || fallbackCapital;
}

export function positionPlan({
  entryPrice,
  stopPrice,
  targetPrice,
  policy = OPERATOR_POLICY,
}) {
  const entry = finite(entryPrice);
  const stop = finite(stopPrice);
  const target = finite(targetPrice);
  if (entry === null || stop === null || entry <= 0 || stop < 0 || stop >= entry) {
    return null;
  }

  const amounts = policyAmounts(policy);
  const riskPerShare = entry - stop;
  const riskShares = Math.floor(amounts.maxTradeRisk / riskPerShare);
  const positionShares = Math.floor(amounts.maxPosition / entry);
  const shares = Math.max(0, Math.min(riskShares, positionShares));
  const investment = shares * entry;
  const maxLoss = shares * riskPerShare;
  const targetGain = target !== null && target > entry ? shares * (target - entry) : null;
  return {
    shares,
    investment,
    capitalPct: investment / policy.capital * 100,
    riskPerShare,
    maxLoss,
    targetGain,
    riskReward: targetGain === null || maxLoss <= 0 ? null : targetGain / maxLoss,
    binding: riskShares <= positionShares ? 'risk' : 'position',
  };
}

export function trimToPositionLimit(weightPct, policy = OPERATOR_POLICY) {
  const weight = finite(weightPct);
  if (weight === null || weight <= policy.maxPositionPct) return 0;
  return amountForWeight(weight - policy.maxPositionPct, policy.capital);
}
