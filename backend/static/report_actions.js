(function () {
    function downloadReport(filename, format) { if (filename) window.location.href = `/api/report/${encodeURIComponent(filename)}/download/${format}`; }
    function bindDownloads(options) {
        [[options.htmlBtn, 'html'], [options.mdBtn, 'md'], [options.dataBtn, 'data']]
            .forEach(([button, format]) => button?.addEventListener('click', () => downloadReport(options.getFilename(), format)));
    }
    function setReportTitle(options) { if (options.titleEl) options.titleEl.textContent = `${options.ticker} ${options.pipelineMeta(options.pipelineId).reportSuffix}`; }
    function triggerPayload(button) {
        return {
            ticker: button.dataset.ticker || '',
            pipeline: button.dataset.pipeline || 'v1',
            enabled: true,
            schedule_slots: ['post_market'],
            triggers: [{ type: 'report_catalyst', trigger_condition: button.dataset.triggerDesc || '', impact_direction: button.dataset.impactDirection || 'volatile' }]
        };
    }
    function bindWatchlistRadarButtons(doc, options = {}) {
        const root = doc || document;
        const apiClient = options.apiClient || window.StockAgentApiClient;
        const notify = options.notify || { success: () => {}, error: () => {} };
        if (!root || !apiClient?.saveWatchlistItem) return;
        root.querySelectorAll('.add-to-watchlist-btn').forEach(button => {
            if (button.dataset.watchlistBound === '1') return;
            button.dataset.watchlistBound = '1';
            button.addEventListener('click', async () => {
                const originalText = button.textContent;
                button.disabled = true; button.textContent = 'Adding...';
                try {
                    const payload = triggerPayload(button);
                    await apiClient.saveWatchlistItem(payload);
                    button.textContent = 'Added'; notify.success(`${payload.ticker} catalyst 已加入 Watchlist Radar`);
                } catch (err) {
                    button.disabled = false; button.textContent = originalText;
                    notify.error(`加入 Watchlist Radar 失敗：${err.message || err}`);
                }
            });
        });
    }
    window.StockAgentReportActions = { bindWatchlistRadarButtons, bindDownloads, downloadReport, setReportTitle };
})();
