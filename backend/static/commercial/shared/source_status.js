export function renderSourceStatus(root, { state, message, source = '', updatedAt = '' }) {
  if (!root) return;
  root.dataset.state = state;
  root.replaceChildren();
  const strong = document.createElement('strong');
  strong.textContent = message;
  const detail = document.createElement('span');
  detail.textContent = [source, updatedAt].filter(Boolean).join(' · ');
  root.append(strong, detail);
  root.setAttribute('role', state === 'error' ? 'alert' : 'status');
  root.setAttribute('aria-live', state === 'error' ? 'assertive' : 'polite');
}
