let clientConfigPromise;

export class ApiError extends Error {
  constructor(status, message, payload = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

async function clientConfig() {
  if (!clientConfigPromise) {
    clientConfigPromise = fetch('/api/client-config', { credentials: 'same-origin' })
      .then(response => response.ok ? response.json() : {});
  }
  return clientConfigPromise;
}

async function requestOptions(options = {}) {
  const next = { credentials: 'same-origin', ...options };
  const method = String(next.method || 'GET').toUpperCase();
  if (['GET', 'HEAD', 'OPTIONS'].includes(method)) return next;
  const config = await clientConfig();
  const headers = new Headers(next.headers || {});
  const token = String(config.mutation_token || '');
  if (token) headers.set(config.mutation_header || 'X-Mutation-Token', token);
  next.headers = headers;
  return next;
}

export async function requestJson(url, options = {}) {
  const response = await fetch(url, await requestOptions(options));
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && typeof payload.detail === 'string'
      ? payload.detail
      : `${response.status} ${response.statusText}`;
    throw new ApiError(response.status, detail, payload);
  }
  return payload;
}
