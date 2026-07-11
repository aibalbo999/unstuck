(function () {
    let clientConfigPromise = null;

    async function fetchClientConfig() {
        if (!clientConfigPromise) {
            clientConfigPromise = fetch('/api/client-config', { credentials: 'same-origin' })
                .then(res => res.ok ? res.json() : {});
        }
        return clientConfigPromise;
    }

    async function withMutationHeader(options) {
        const requestOptions = { ...(options || {}) };
        const method = String(requestOptions.method || 'GET').toUpperCase();
        const needsMutation = requestOptions.mutation === true || !['GET', 'HEAD', 'OPTIONS'].includes(method);
        delete requestOptions.mutation;
        if (!needsMutation) return requestOptions;
        const config = await fetchClientConfig();
        const token = config.mutation_token || '';
        if (!token) return requestOptions;
        const headers = new Headers(requestOptions.headers || {});
        headers.set(config.mutation_header || 'X-Mutation-Token', token);
        requestOptions.headers = headers;
        return requestOptions;
    }

    async function requestJson(url, options) {
        const res = await fetch(url, await withMutationHeader(options));
        const text = await res.text();
        let payload = {};
        if (text) {
            try {
                payload = JSON.parse(text);
            } catch (err) {
                payload = { message: text.slice(0, 180) };
            }
        }
        if (!res.ok || payload.success === false) {
            throw new Error(payload.error || payload.detail || payload.message || `HTTP ${res.status}`);
        }
        return payload;
    }

    window.StockAgentApiRequest = { requestJson };
})();
