export function normalizeTicker(value) {
  const ticker = String(value || '').trim().toUpperCase();
  if (/^\d{4}$/.test(ticker)) return `${ticker}.TW`;
  return ticker;
}

export function isValidTicker(value) {
  return /^(?:\d{4}\.(?:TW|TWO)|[A-Z][A-Z0-9.-]{0,9})$/.test(normalizeTicker(value));
}

export function stockPageHref(ticker, from = '') {
  const query = new URLSearchParams({ ticker: normalizeTicker(ticker) });
  if (from) query.set('from', from);
  return `/static/commercial/stock-detail.html?${query.toString()}`;
}

export function tickerFromLocation(fallback = '2330.TW') {
  return normalizeTicker(new URLSearchParams(window.location.search).get('ticker') || fallback);
}

export function focusPageHeading(id) {
  window.requestAnimationFrame(() => document.getElementById(id)?.focus({ preventScroll: true }));
}

export function bindTabs(tabList, onChange) {
  if (!tabList) return;
  const tabs = Array.from(tabList.querySelectorAll('[role="tab"]'));
  const activate = tab => {
    tabs.forEach(item => {
      const active = item === tab;
      item.setAttribute('aria-selected', active ? 'true' : 'false');
      item.tabIndex = active ? 0 : -1;
    });
    onChange(tab.dataset.tab);
  };
  tabList.addEventListener('click', event => {
    const tab = event.target.closest('[role="tab"]');
    if (tab) activate(tab);
  });
  tabList.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    const current = tabs.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    const delta = event.key === 'ArrowRight' ? 1 : -1;
    const next = tabs[(current + delta + tabs.length) % tabs.length];
    next.focus();
    activate(next);
  });
}
