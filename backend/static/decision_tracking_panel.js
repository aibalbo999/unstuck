(function () {
    function trackedGroups(payload) {
        return (payload?.items || [])
            .filter(item => item.enabled)
            .map(item => {
                const reports = (item.latest_reports && item.latest_reports.length ? item.latest_reports : [item.latest_report])
                    .filter(report => report && report.filename)
                    .map(report => ({ ...report, tracking_item: item }));
                return {
                    ticker: item.ticker,
                    company_name: reports[0]?.company_name || item.company_name || '',
                    tracking_item: item,
                    reports
                };
            })
            .filter(group => group.reports.length);
    }

    function trackedSet(payload) {
        return new Set((payload?.items || []).filter(item => item.enabled).map(item => item.ticker));
    }

    function create(options) {
        const apiClient = options.apiClient;
        const historyPanel = options.historyPanel;
        const notify = options.notify || { success: () => {}, error: () => {} };
        const elements = options.elements || {};
        const onChange = options.onChange || (() => {});
        let trackedTickers = new Set();

        function setSummary(payload) {
            if (!elements.summaryEl) return;
            const count = payload?.enabled_count || trackedTickers.size || 0;
            elements.summaryEl.textContent = count
                ? `每日決策追蹤：${count} 檔`
                : '每日決策追蹤：尚未加入股票';
        }

        function applyPayload(payload) {
            trackedTickers = trackedSet(payload);
            onChange(trackedTickers);
            setSummary(payload);
            historyPanel.renderTrackingGroups(trackedGroups(payload));
            return payload;
        }

        async function load() {
            try {
                return applyPayload(await apiClient.fetchDecisionTracking());
            } catch (err) {
                console.error('Failed to load decision tracking', err);
                if (elements.summaryEl) elements.summaryEl.textContent = '每日決策追蹤讀取失敗';
                historyPanel.renderTrackingGroups([]);
                return { items: [] };
            }
        }

        async function toggleDecisionTracking(report) {
            if (!report || !report.ticker) return;
            const ticker = report.ticker;
            try {
                const wasTracked = trackedTickers.has(ticker);
                const payload = wasTracked
                    ? await apiClient.deleteDecisionTrackingItem(ticker)
                    : await apiClient.saveDecisionTrackingItem({ ticker });
                applyPayload(payload);
                notify.success(wasTracked ? `已取消追蹤 ${ticker}` : `已加入追蹤 ${ticker}`);
            } catch (err) {
                console.error('Decision tracking toggle failed', err);
                notify.error(`追蹤設定失敗：${err.message || err}`);
            }
        }

        async function refresh() {
            if (elements.refreshBtn) elements.refreshBtn.disabled = true;
            try {
                const payload = await apiClient.refreshDecisionTracking();
                applyPayload(payload);
                notify.success(`已刷新 ${payload.updated_count || 0} 檔追蹤股價`);
            } catch (err) {
                console.error('Decision tracking refresh failed', err);
                notify.error(`刷新追蹤股價失敗：${err.message || err}`);
            } finally {
                if (elements.refreshBtn) elements.refreshBtn.disabled = false;
            }
        }

        if (elements.refreshBtn) elements.refreshBtn.addEventListener('click', refresh);
        return { load, refresh, toggleDecisionTracking, trackedTickers: () => trackedTickers };
    }

    window.StockAgentDecisionTrackingPanel = { create };
})();
