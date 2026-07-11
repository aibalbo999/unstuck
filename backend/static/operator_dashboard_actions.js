(function () {
    const queueItems = payload => Array.isArray(payload?.decision_queue?.items) ? payload.decision_queue.items : [];
    const sampleTickers = items => { const samples = [...new Set((items || []).map(item => item?.ticker).filter(Boolean))].slice(0, 3).join('、'); return samples ? `例如 ${samples}` : ''; };
    const dashboardActionMap = { rerun_report: ['rerun-report', '完整重跑'], run_watchlist: ['run-watchlist', '建立/更新報告'], refresh_data_snapshot: ['refresh-report', '刷新資料'], manual_review: ['view-report', '查看報告'], wait_provider_recovery: ['open-ops', '查看來源'], backtest_due: ['open-ops', '查看回測'], model_route_warning: ['open-ops', '查看路由'], fix_notification_delivery: ['open-ops', '查看通知通道'], monitor_provider: ['open-ops', '查看來源'], fix_free_mode: ['open-ops', '修免費模式'], review_candidate: ['candidate-snapshot', '查看股票快照'], monitor: ['monitor', '查看狀態'] };
    const targetPanelForAction = item => item?.target_panel || ({ wait_provider_recovery: 'provider-sla-panel', monitor_provider: 'provider-sla-panel', backtest_due: 'performance-panel', model_route_warning: 'api-quota-panel', fix_notification_delivery: 'maintenance-panel', fix_free_mode: 'provider-sla-panel', run_watchlist: 'watchlist-panel' }[item?.type] || 'active-jobs-panel');
    const targetTabForPanel = panel => panel === 'watchlist-panel' ? 'tracking' : (panel === 'market-screener-panel' ? 'screener' : 'ops');
    const attentionContextText = item => window.StockAgentDailyQueueContext?.attentionContextText?.(item) || '';
    const sourceLabel = source => window.StockAgentDailyQueueContext?.sourceLabel?.(source) || source;
    const actionDetail = item => [item?.detail, attentionContextText(item), item?.source ? `來源：${sourceLabel(item.source)}` : '', item?.priority_score != null ? `priority_score ${item.priority_score}` : ''].filter(Boolean).join(' · ');
    const actionableActionCount = items => items.filter(item => item.action !== 'monitor').length;
    const candidateActionModel = item => ({
        ticker: String(item?.ticker || '').trim(),
        companyName: String(item?.company_name || '').trim(),
        reason: String(item?.candidate_reason || item?.reason || item?.detail || '市場掃描候選').trim(),
    });

    function dashboardText(payload) {
        const queue = payload?.decision_queue || {};
        const summary = queue.summary || payload?.summary || {};
        const total = Number(summary.total_actionable || 0);
        const shown = Number(summary.displayed_count || queueItems(payload).length || 0);
        const secondary = Number(queue.secondary_count || 0);
        if (total) return { tone: 'warning', value: `${total} 件待處理`, detail: `顯示 ${shown} / 次要待辦 ${secondary}` };
        const old = payload?.summary || {};
        const repairs = Number(old.report_repairs_required || 0);
        const reruns = Number(old.reports_needing_rerun || 0);
        const watchHigh = Number(old.watchlist_high_priority || 0);
        if (repairs || reruns || watchHigh) return { tone: 'warning', value: `${repairs + reruns + watchHigh} 件待處理`, detail: `修復 ${repairs} / 重跑 ${reruns} / watchlist ${watchHigh}` };
        if (payload?.free_mode?.can_run_without_paid_keys === false) return { tone: 'warning', value: '免費模式需處理', detail: 'provider 有付費依賴缺口' };
        return { tone: 'ok', value: '今日節奏正常', detail: `${Number(old.top_candidate_count || 0)} 個候選` };
    }

    function mappedDashboardAction(item) {
        const mapped = dashboardActionMap[item?.type] || ['open-ops', '查看狀態'];
        const panel = targetPanelForAction(item);
        if (item?.type === 'review_candidate') {
            const candidate = candidateActionModel(item);
            const reasons = [...new Set([item?.candidate_reason || item?.reason, item?.detail].map(value => String(value || '').trim()).filter(Boolean))];
            const detail = [...reasons, item?.source ? `來源：${sourceLabel(item.source)}` : ''].filter(Boolean).join(' · ');
            const title = [candidate.ticker, candidate.companyName].filter(Boolean).join(' · ') || String(item?.title || '').trim() || '候選股票';
            return { action: mapped[0], type: item.type, label: mapped[1], title, detail, ticker: candidate.ticker, companyName: candidate.companyName, reason: candidate.reason, score: item?.score, candidate };
        }
        return { action: item.operator_action || mapped[0], label: item.operator_action_label || item.action_label || mapped[1], title: item.title || '今日待處理', detail: actionDetail(item), filename: item.filename, ticker: item.ticker, pipeline: item.pipeline_id || 'v1', targetPanel: panel, targetTab: item.target_tab || targetTabForPanel(panel) };
    }

    function dashboardActionItems(payload) {
        const decisionItems = queueItems(payload);
        if (decisionItems.length) return decisionItems.map(mappedDashboardAction).slice(0, 24);
        const rerunReports = Array.isArray(payload?.rerun_reports) ? payload.rerun_reports.filter(item => item?.filename) : [];
        const repairItems = Array.isArray(payload?.repair_queue?.items) ? payload.repair_queue.items : [];
        const items = [];
        if (rerunReports.length > 1) items.push({ action: 'rerun-all-reports', label: '全部重跑', title: `${rerunReports.length} 份報告待完整重跑`, detail: sampleTickers(rerunReports), filenames: rerunReports.map(item => item.filename).filter(Boolean) });
        rerunReports.forEach(item => items.push({ action: 'rerun-report', label: '完整重跑', title: item.title || `${item.ticker || '報告'} 結論需重跑`, detail: item.detail || '資料快照與結論不同步', filename: item.filename, ticker: item.ticker, pipeline: item.pipeline_id || 'v1' }));
        if (!items.length && repairItems.length) repairItems.forEach(item => items.push(mappedDashboardAction({ ...item, type: item.recommended_action === 'rerun_analysis' ? 'rerun_report' : item.recommended_action, title: item.title || '報告需處理' })));
        (payload?.actions || []).forEach(item => {
            if (item?.type === 'rerun_report' && rerunReports.length) return;
            if (['manual_review', 'refresh_data_snapshot', 'wait_provider_recovery'].includes(item?.type) && repairItems.length && items.some(existing => existing.filename && existing.filename === item.filename)) return;
            items.push(mappedDashboardAction(item));
        });
        return items.slice(0, 24);
    }

    window.StockAgentOperatorDashboardActions = { actionableActionCount, candidateActionModel, dashboardActionItems, dashboardText };
})();
