(function () {
    function trackedGroups(payload) {
        return (payload?.items || [])
            .filter(item => item.enabled)
            .map(item => {
                const reports = (item.latest_reports && item.latest_reports.length ? item.latest_reports : [item.latest_report])
                    .filter(report => report && report.filename)
                    .map(report => ({ ...report, tracking_item: item }));
                return {
                    ticker: reports.find(report => report.ticker)?.ticker || item.ticker,
                    company_name: reports[0]?.company_name || item.company_name || '',
                    tracking_item: item,
                    reports
                };
            })
            .filter(group => group.reports.length);
    }
    const trackedSet = payload => new Set((payload?.items || []).filter(item => item.enabled).map(item => item.ticker));
    function dataTrustReasonCodes(report) {
        const codes = report?.data_trust?.reason_codes;
        return Array.isArray(codes) ? codes.map(code => String(code || '')) : [];
    }

    function hasRefreshableDataTrustIssue(report) {
        const status = report?.data_trust?.status || 'unknown';
        const reasonCodes = dataTrustReasonCodes(report), staleSources = report?.data_trust?.stale_sources;
        return status === 'stale'
            || (Array.isArray(staleSources) && staleSources.filter(Boolean).length > 0)
            || reasonCodes.some(code => code.startsWith('source_stale:'));
    }
    const needsFullReportRerun = report => Boolean(report?.analysis_text_stale || report?.decision_freshness?.requires_rerun || report?.requires_rerun);
    function recommendedActionForReport(report) {
        if (!report || !report.filename) return null;
        if (needsFullReportRerun(report)) return { type: 'rerun_full_report', filename: report.filename };
        if (hasRefreshableDataTrustIssue(report) || report?.data_trust?.status === 'partial') return { type: 'refresh_data_snapshot', filename: report.filename };
        return null;
    }

    function uniqueRecommendedActions(payload) {
        const seen = new Set(), actions = [];
        trackedGroups(payload).flatMap(group => group.reports || []).forEach(report => {
            const action = recommendedActionForReport(report);
            if (!action) return;
            const key = `${action.type}:${action.filename}`;
            if (seen.has(key)) return;
            seen.add(key);
            actions.push(action);
        });
        return actions;
    }

    function create(options) {
        const apiClient = options.apiClient;
        const historyPanel = options.historyPanel;
        const notify = options.notify || { success: () => {}, error: () => {} };
        const elements = options.elements || {};
        const onChange = options.onChange || (() => {});
        let trackedTickers = new Set();
        let latestPayload = { items: [] };

        function setSummary(payload) {
            if (!elements.summaryEl) return;
            const count = payload?.enabled_count || trackedTickers.size || 0;
            const actionCount = uniqueRecommendedActions(payload).length;
            elements.summaryEl.textContent = count
                ? `每日決策追蹤：${count} 檔${actionCount ? ` · ${actionCount} 個警示動作` : ''}`
                : '每日決策追蹤：尚未加入股票';
        }

        function applyPayload(payload) {
            latestPayload = payload || { items: [] };
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

        async function runAllRecommendedActions() {
            const actions = uniqueRecommendedActions(latestPayload);
            if (!actions.length) {
                notify.success('目前追蹤報告沒有待處理警示');
                return;
            }
            if (elements.runActionsBtn) elements.runActionsBtn.disabled = true;
            try {
                let finished = 0, failed = 0;
                for (const action of actions) {
                    try {
                        if (action.type === 'refresh_data_snapshot') {
                            await apiClient.refreshReportDataSnapshot(action.filename);
                        } else if (action.type === 'rerun_full_report') {
                            await apiClient.requestJson(`/api/report/${encodeURIComponent(action.filename)}/rerun?scope=full_report`, { method: 'POST' });
                        }
                        finished += 1;
                    } catch (err) {
                        failed += 1;
                        console.error(`Decision tracking action failed for ${action.filename}`, err);
                    }
                }
                applyPayload(await apiClient.fetchDecisionTracking());
                if (failed) notify.error(`警示動作完成 ${finished} 個，失敗 ${failed} 個`);
                else notify.success(`已送出 ${finished} 個追蹤報告警示動作`);
            } catch (err) {
                console.error('Decision tracking bulk actions failed', err);
                notify.error(`一鍵處理警示失敗：${err.message || err}`);
            } finally {
                if (elements.runActionsBtn) elements.runActionsBtn.disabled = false;
            }
        }

        if (elements.refreshBtn) elements.refreshBtn.addEventListener('click', refresh); if (elements.runActionsBtn) elements.runActionsBtn.addEventListener('click', runAllRecommendedActions);
        return { load, refresh, runAllRecommendedActions, toggleDecisionTracking, trackedTickers: () => trackedTickers };
    }

    window.StockAgentDecisionTrackingPanel = { create };
})();
