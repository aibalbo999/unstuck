(function () {
    function create(options) {
        function state() {
            return typeof options.state === 'function' ? options.state() : {};
        }

        function patchState(patch) {
            if (typeof options.patchState === 'function') options.patchState(patch);
        }

        function reportPipelineFor(data, fallback) {
            return data.last_pipeline_id || (data.pipeline_id === 'both' ? 'v3' : data.pipeline_id) || fallback;
        }

        function handleJob(data) {
            options.setCurrentJobId(data.job_id);
            const nextPipeline = data.pipeline_id || state().currentPipeline;
            patchState({ currentPipeline: nextPipeline });
            if (options.loadingHint) options.loadingHint.textContent = options.pipelineMeta(nextPipeline).hint;
            if (data.resume_after_id) options.updateLastEventId(data.resume_after_id);
        }

        function handleReportDone(data) {
            const remaining = Number(data.pipeline_total || 1) - Number(data.pipeline_index || 1);
            options.loadingStatus.textContent = `${options.pipelineModeLabel(data.pipeline_id)} 報告完成`;
            options.loadingMsg.textContent = remaining > 0 ? '正在接續下一種分析模式...' : '正在整理最終報告...';
            if (remaining > 0) options.loadHistory();
        }

        function handleDone(data, ticker) {
            options.close();
            const reportPipeline = reportPipelineFor(data, state().currentPipeline);
            patchState({ currentReportFilename: data.filename, currentPipeline: reportPipeline });
            const reportCount = Array.isArray(data.filenames) ? data.filenames.length : 1;
            options.reportTickerTitle.textContent = reportCount > 1
                ? `${ticker} ${reportCount} 模式分析完成`
                : `${ticker} ${options.pipelineMeta(reportPipeline).reportSuffix}`;
            options.setAuditNotice(data.audit || state().pendingAuditNotice);
            options.reportIframe.src = `/api/report/${encodeURIComponent(data.filename)}`;
            setTimeout(() => {
                options.switchView('report-view');
                options.loadHistory();
            }, 800);
        }

        function handle(data, ticker) {
            if (data.type === 'job') {
                handleJob(data);
                return;
            }
            if (data.type === 'status') {
                options.loadingStatus.textContent = data.message;
                if (data.detail) options.loadingMsg.textContent = data.detail;
            } else if (data.type === 'pipeline_start') {
                options.loadingStatus.textContent = data.message || '開始下一段分析';
                options.loadingMsg.textContent = data.pipeline_label || '';
                if (options.loadingHint && data.pipeline_total > 1) {
                    options.loadingHint.textContent = `連續模式進度：第 ${data.pipeline_index}/${data.pipeline_total} 段`;
                }
            } else if (data.type === 'progress') {
                options.loadingStatus.textContent = `分析中：第 ${data.current}/${data.total} 位分析師`;
                options.loadingMsg.textContent = data.name;
                options.progressBar.style.width = `${(data.current / data.total) * 100}%`;
            } else if (data.type === 'report_done') {
                handleReportDone(data);
            } else if (data.type === 'done') {
                handleDone(data, ticker);
            } else if (data.type === 'error') {
                options.loadingStatus.textContent = '發生錯誤';
                options.loadingMsg.textContent = data.message;
                options.close();
                setTimeout(() => options.switchView('home-view'), 5000);
            } else if (data.type === 'audit') {
                const pendingAuditNotice = data.audit || data;
                patchState({ pendingAuditNotice });
                if (pendingAuditNotice.status === 'needs_attention') {
                    options.loadingStatus.textContent = pendingAuditNotice.message;
                }
            }
        }

        return { handle };
    }

    window.StockAgentAnalysisStreamEvents = { create };
})();
