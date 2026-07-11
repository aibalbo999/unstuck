import {
  OPERATOR_POLICY,
  normalizeOperatorPolicy,
  readOperatorPolicy,
  writeOperatorPolicy,
} from './operator_policy.js?v=20260711-operator6';

const FIELDS = [
  {
    key: 'capital',
    label: '操作資金',
    suffix: '元',
    min: 100000,
    max: Number.MAX_SAFE_INTEGER,
    step: 100000,
  },
  { key: 'cashReservePct', label: '現金保留', suffix: '%', min: 0, max: 95, step: 1 },
  { key: 'maxPositionPct', label: '單一持股上限', suffix: '%', min: 1, max: 100, step: 1 },
  { key: 'maxTradeRiskPct', label: '單筆最大風險', suffix: '%', min: 0.1, max: 100, step: 0.1 },
];

function browserStorage() {
  try {
    return window.localStorage;
  } catch (_error) {
    return null;
  }
}

function fieldControl(field, value) {
  const label = document.createElement('label');
  label.className = 'commercial-field';
  const name = document.createElement('span');
  name.textContent = field.label;
  const wrap = document.createElement('span');
  wrap.className = 'commercial-input-with-suffix';
  const input = document.createElement('input');
  input.name = field.key;
  input.type = 'number';
  input.required = true;
  input.min = String(field.min);
  input.max = String(field.max);
  input.step = String(field.step);
  input.value = String(value);
  input.inputMode = 'decimal';
  const suffix = document.createElement('span');
  suffix.textContent = field.suffix;
  wrap.append(input, suffix);
  label.append(name, wrap);
  return label;
}

function formPolicy(form) {
  const values = Object.fromEntries(
    FIELDS.map(field => [field.key, Number(form.elements[field.key].value)]),
  );
  return normalizeOperatorPolicy(values);
}

export function mountOperatorPolicyEditor(root, { onChange = () => {}, storage = browserStorage() } = {}) {
  let current = readOperatorPolicy(storage);
  const details = document.createElement('details');
  details.className = 'commercial-policy-editor';
  const summary = document.createElement('summary');
  summary.textContent = '調整操作資金與風險設定';
  const form = document.createElement('form');
  form.className = 'commercial-policy-editor-form';
  form.noValidate = false;
  const fields = document.createElement('div');
  fields.className = 'commercial-policy-editor-grid';
  const actions = document.createElement('div');
  actions.className = 'commercial-policy-editor-actions';
  const apply = document.createElement('button');
  apply.type = 'submit';
  apply.className = 'commercial-secondary-action';
  apply.textContent = '套用設定';
  const reset = document.createElement('button');
  reset.type = 'button';
  reset.className = 'commercial-text-action';
  reset.textContent = '恢復預設';
  const status = document.createElement('p');
  status.className = 'commercial-policy-editor-status';
  status.setAttribute('aria-live', 'polite');

  const renderFields = policy => {
    fields.replaceChildren(...FIELDS.map(field => fieldControl(field, policy[field.key])));
  };
  const applyPolicy = policy => {
    current = normalizeOperatorPolicy(policy);
    const saved = writeOperatorPolicy(storage, current);
    status.textContent = saved ? '設定已保存並套用。' : '設定已套用；此瀏覽器無法保存。';
    onChange(current);
  };

  form.addEventListener('submit', event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    applyPolicy(formPolicy(form));
  });
  reset.addEventListener('click', () => {
    renderFields(OPERATOR_POLICY);
    applyPolicy(OPERATOR_POLICY);
  });

  renderFields(current);
  actions.append(apply, reset);
  form.append(fields, actions, status);
  details.append(summary, form);
  root.replaceChildren(details);
  onChange(current);

  return { get policy() { return current; } };
}
