export function setAsyncState(button, statusRoot, state, message) {
  const loading = state === 'loading';
  if (button) {
    if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent.trim();
    button.disabled = loading;
    button.setAttribute('aria-busy', loading ? 'true' : 'false');
    button.textContent = loading ? '載入中…' : button.dataset.idleLabel;
  }
  if (statusRoot) {
    statusRoot.dataset.state = state;
    statusRoot.textContent = message || '';
  }
}
