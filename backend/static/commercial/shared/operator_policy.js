export const OPERATOR_POLICY = Object.freeze({
  capital: 5_000_000,
  cashReservePct: 20,
  maxPositionPct: 15,
  maxTradeRiskPct: 1,
});

export const POLICY_STORAGE_KEY = 'onstock.commercial.operator-policy.v1';

const POLICY_RANGES = Object.freeze({
  capital: [100_000, Number.MAX_SAFE_INTEGER],
  cashReservePct: [0, 95],
  maxPositionPct: [1, 100],
  maxTradeRiskPct: [0.1, 100],
});

function finite(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function policyValue(source, key) {
  const value = finite(source?.[key]);
  const [minimum, maximum] = POLICY_RANGES[key];
  return value !== null && value >= minimum && value <= maximum
    ? value
    : OPERATOR_POLICY[key];
}

export function normalizeOperatorPolicy(source = {}) {
  return {
    capital: policyValue(source, 'capital'),
    cashReservePct: policyValue(source, 'cashReservePct'),
    maxPositionPct: policyValue(source, 'maxPositionPct'),
    maxTradeRiskPct: policyValue(source, 'maxTradeRiskPct'),
  };
}

export function readOperatorPolicy(storage) {
  try {
    const raw = storage?.getItem(POLICY_STORAGE_KEY);
    return normalizeOperatorPolicy(raw ? JSON.parse(raw) : OPERATOR_POLICY);
  } catch (_error) {
    return normalizeOperatorPolicy(OPERATOR_POLICY);
  }
}

export function writeOperatorPolicy(storage, policy) {
  const normalized = normalizeOperatorPolicy(policy);
  try {
    if (typeof storage?.setItem !== 'function') return false;
    storage.setItem(POLICY_STORAGE_KEY, JSON.stringify(normalized));
    return true;
  } catch (_error) {
    return false;
  }
}

export function formatTwd(value) {
  const number = finite(value);
  if (number === null) return '資料不足';
  const amount = new Intl.NumberFormat('zh-TW', {
    maximumFractionDigits: 0,
  }).format(number);
  return `NT$${amount}`;
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
