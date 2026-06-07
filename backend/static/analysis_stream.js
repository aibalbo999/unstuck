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
                    if (Number.isFinite(parsedId)) lastEventId = Math.max(lastEventId, parsedId);
                }

                try {
                    handleEvent(JSON.parse(event.data), ticker);
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

        function handleEvent(data, ticker) {
            if (data.type === 'job') {
                currentJobId = data.job_id || currentJobId;
                const nextPipeline = data.pipeline_id || state().currentPipeline;
                patchState({ currentPipeline: nextPipeline });
                if (options.loadingHint) options.loadingHint.textContent = options.pipelineMeta(nextPipeline).hint;
                if (data.resume_after_id) lastEventId = Math.max(lastEventId, Number(data.resume_after_id) || 0);
                return;
            }

            if (data.type === 'status') {
                options.loadingStatus.textContent = data.message;
                if (data.detail) {
                    options.loadingMsg.textContent = data.detail;
                }
            } else if (data.type === 'pipeline_start') {
                options.loadingStatus.textContent = data.message || '開始下一段分析';
                options.loadingMsg.textContent = data.pipeline_label || '';
                if (options.loadingHint && data.pipeline_total > 1) {
                    options.loadingHint.textContent = `連續模式進度：第 ${data.pipeline_index}/${data.pipeline_total} 段`;
                }
            } else if (data.type === 'progress') {
                options.loadingStatus.textContent = `分析中：第 ${data.current}/${data.total} 位分析師`;
                options.loadingMsg.textContent = data.name;
                const percent = (data.current / data.total) * 100;
                options.progressBar.style.width = `${percent}%`;
            } else if (data.type === 'report_done') {
                const remaining = Number(data.pipeline_total || 1) - Number(data.pipeline_index || 1);
                options.loadingStatus.textContent = `${options.pipelineModeLabel(data.pipeline_id)} 報告完成`;
                options.loadingMsg.textContent = remaining > 0 ? '正在接續下一種分析模式...' : '正在整理最終報告...';
                if (remaining > 0) options.loadHistory();
            } else if (data.type === 'done') {
                close();

                const currentPipeline = state().currentPipeline;
                const reportPipeline = data.last_pipeline_id || (data.pipeline_id === 'both' ? 'v2' : data.pipeline_id) || currentPipeline;
                patchState({ currentReportFilename: data.filename, currentPipeline: reportPipeline });
                const reportCount = Array.isArray(data.filenames) ? data.filenames.length : 1;
                options.reportTickerTitle.textContent = reportCount > 1
                    ? `${ticker} 雙模式分析完成`
                    : `${ticker} ${options.pipelineMeta(reportPipeline).reportSuffix}`;
                options.setAuditNotice(data.audit || state().pendingAuditNotice);
                options.reportIframe.src = `/api/report/${encodeURIComponent(data.filename)}`;

                setTimeout(() => {
                    options.switchView('report-view');
                    options.loadHistory();
                }, 800);
            } else if (data.type === 'error') {
                options.loadingStatus.textContent = '發生錯誤';
                options.loadingMsg.textContent = data.message;
                close();

                setTimeout(() => {
                    options.switchView('home-view');
                }, 5000);
            } else if (data.type === 'audit') {
                const pendingAuditNotice = data.audit || data;
                patchState({ pendingAuditNotice });
                if (pendingAuditNotice.status === 'needs_attention') {
                    options.loadingStatus.textContent = pendingAuditNotice.message;
                }
            }
        }

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
