(function () {
    function create(options) {
        let eventSource = null;
        let currentJobId = null;
        let lastEventId = 0;
        let reconnectTimer = null;
        let reconnectAttempts = 0;
        let streamClosedByClient = false;

        function patchState(patch) {
            if (typeof options.setState === 'function') options.setState(patch);
        }

        function state() {
            return typeof options.getState === 'function' ? options.getState() : {};
        }

        function updateLastEventId(eventId) {
            lastEventId = Math.max(lastEventId, Number(eventId) || 0);
        }

        function close() {
            streamClosedByClient = true;
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        }

        function connect(ticker, pipelineId) {
            clearTimeout(reconnectTimer);
            streamClosedByClient = false;
            if (eventSource) eventSource.close();

            const params = new URLSearchParams();
            params.set('pipeline', pipelineId || 'v1');
            if (currentJobId) params.set('job_id', currentJobId);
            if (lastEventId) params.set('last_event_id', String(lastEventId));
            const query = params.toString();
            const url = `/api/analyze/${encodeURIComponent(ticker)}${query ? `?${query}` : ''}`;
            eventSource = new EventSource(url);

            eventSource.onmessage = (event) => {
                reconnectAttempts = 0;
                if (event.lastEventId) {
                    const parsedId = Number(event.lastEventId);
                    if (Number.isFinite(parsedId)) updateLastEventId(parsedId);
                }

                try {
                    eventHandlers.handle(JSON.parse(event.data), ticker);
                } catch (err) {
                    console.error('Parse error:', err);
                }
            };

            eventSource.onerror = () => {
                if (streamClosedByClient) return;
                if (eventSource) eventSource.close();
                const delay = Math.min(30000, 1000 * (2 ** reconnectAttempts));
                reconnectAttempts += 1;
                options.loadingMsg.textContent = `連線中斷，${Math.ceil(delay / 1000)} 秒後自動接續...`;
                reconnectTimer = setTimeout(() => connect(ticker, pipelineId), delay);
            };
        }

        const eventHandlers = window.StockAgentAnalysisStreamEvents.create({
            ...options,
            state,
            patchState,
            close,
            setCurrentJobId: jobId => { currentJobId = jobId || currentJobId; },
            updateLastEventId
        });

        function resetAndConnect(ticker, pipelineId) {
            currentJobId = null;
            lastEventId = 0;
            reconnectAttempts = 0;
            close();
            connect(ticker, pipelineId);
        }

        return { close, resetAndConnect };
    }

    window.StockAgentAnalysisStream = { create };
})();
