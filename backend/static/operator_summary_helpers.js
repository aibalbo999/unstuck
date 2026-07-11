(function () {
    const quotaErrorCount = service => Number(service?.usage?.observed_quota_errors_since_reset || service?.usage?.observed_24h_errors || 0);
    const quotaHealth = services => ({ errors: (services || []).reduce((sum, service) => sum + quotaErrorCount(service), 0) });
    function activeJobText(payload) {
        const active = Number(payload?.active_count || 0);
        const jobs = payload?.jobs || [];
        if (active) return { tone: 'warning', value: `${active} 個進行中`, detail: jobs[0]?.ticker || '' };
        return { tone: 'ok', value: '無進行中任務', detail: jobs[0] ? `最近 ${jobs[0].ticker || 'N/A'}` : '等待下一次分析' };
    }
    function quotaText(payload) {
        const services = payload?.services || [];
        const configured = services.filter(service => service.configured);
        const health = quotaHealth(services);
        if (health.errors) return { tone: 'warning', value: 'LLM 健康警示', detail: `${health.errors} 次額度/來源錯誤` };
        return { tone: 'ok', value: 'LLM 本機觀測正常', detail: `${configured.length} 個服務可用` };
    }
    const qualityHelpers = () => window.StockAgentOperatorSummaryQualityHelpers || {};
    const reportNeedsRerun = report => Boolean(qualityHelpers().reportNeedsRerun?.(report));
    const reportNeedsRecommendedRerun = report => {
        const action = qualityHelpers().reportRecommendedAction?.(report);
        return action?.type === 'rerun_full_report' || ((!qualityHelpers().reportRecommendedAction || (!action && !report.filename)) && reportNeedsRerun(report));
    };
    const hasRefreshableDataTrustIssue = report => Boolean(qualityHelpers().hasRefreshableDataTrustIssue?.(report));
    const recommendedAction = report => qualityHelpers().reportRecommendedAction?.(report);
    const requiresDataTrustAction = report => {
        const action = recommendedAction(report);
        return Boolean(action) || ((!qualityHelpers().reportRecommendedAction || (!action && !report.filename)) && Boolean(qualityHelpers().requiresDataTrustAction?.(report)));
    };
    const isSourceNotice = report => Boolean(qualityHelpers().isSourceNotice?.(report));
    const reportHasFreshData = report => Boolean(qualityHelpers().reportHasFreshData?.(report)), sourceNoticeReports = reports => qualityHelpers().sourceNoticeReports?.(reports || []) || [];
    function trustText(payload) {
        const reports = payload?.reports || [];
        if (!reports.length) return { tone: 'warning', value: '尚無報告', detail: '等待資料快照' };
        const fresh = reports.filter(reportHasFreshData).length;
        const actionCount = reports.filter(requiresDataTrustAction).length;
        if (actionCount) return { tone: 'warning', value: `${actionCount} 份需處理`, detail: `資料新鮮 ${fresh} / 抽樣 ${reports.length}` };
        const notices = sourceNoticeReports(reports).length;
        if (notices) return { tone: 'warning', value: `${notices} 份來源提醒`, detail: `無需刷新/重跑 · 資料新鮮 ${fresh} / 抽樣 ${reports.length}` };
        return { tone: 'ok', value: '近期資料正常', detail: `${reports.length} 份近期報告` };
    }
    function rerunText(payload) {
        const reports = payload?.reports || [];
        const needs = reports.filter(reportNeedsRecommendedRerun);
        if (needs.length) return { tone: 'warning', value: `${needs.length} 份需重跑`, detail: needs[0]?.ticker || '' };
        return { tone: 'ok', value: '無立即重跑', detail: reports.length ? '依近期報告判斷' : '尚無判斷資料' };
    }
    const reportAction = report => qualityHelpers().reportAction?.(report) || null;
    function watchlistActionDetail(items) {
        const missing = items.filter(item => item?.decision_alert?.reason === 'missing_report').length;
        const rerun = items.filter(item => item?.decision_alert?.reason === 'needs_rerun').length;
        const other = Math.max(0, items.length - missing - rerun);
        const parts = [];
        if (missing) parts.push(`${missing} 檔尚未建立報告`);
        if (rerun) parts.push(`${rerun} 檔資料更新需重跑`);
        if (other) parts.push(`${other} 檔需確認`);
        const samples = items.slice(0, 3).map(item => item.ticker).filter(Boolean).join('、');
        return `${parts.join('，')}${samples ? ` · 例如 ${samples}` : ''}`;
    }
    function operatorActionItems(jobsPayload, quotaPayload, reportPayload, watchlistPayload) {
        const items = [];
        (reportPayload?.reports || []).some(report => {
            const action = reportAction(report);
            if (!action) return false;
            items.push({ action: action.action || 'view-report', label: action.label || '查看報告', title: `${report.ticker || '報告'} ${action.title}`, detail: action.detail, filename: report.filename, ticker: report.ticker, pipeline: report.pipeline_id || 'v1' });
            return items.length >= 2;
        });
        const watchNeeds = (watchlistPayload?.items || []).filter(item => item.enabled !== false && ['high', 'medium'].includes(item.decision_priority));
        if (watchNeeds.length) items.push({ action: 'run-watchlist', label: '建立/更新報告', title: `${watchNeeds.length} 檔 watchlist 待建立/更新報告`, detail: watchlistActionDetail(watchNeeds) });
        const quotaErrors = quotaHealth(quotaPayload?.services).errors;
        if (quotaErrors) items.push({ action: 'open-ops', label: '系統維護', title: 'LLM 健康需留意', detail: `${quotaErrors} 次額度/來源錯誤` });
        const active = Number(jobsPayload?.active_count || 0);
        if (!items.length && active) items.push({ action: 'open-ops', label: '查看任務', title: `${active} 個任務進行中`, detail: '查看進度與近期事件' });
        if (!items.length) items.push({ action: 'monitor', label: '查看狀態', title: '目前沒有急件', detail: '可展開健康摘要查看細節' });
        return items.slice(0, 3);
    }
    window.StockAgentOperatorSummaryHelpers = {
        activeJobText,
        hasRefreshableDataTrustIssue,
        isSourceNotice,
        operatorActionItems,
        quotaHealth,
        quotaText,
        rerunText,
        requiresDataTrustAction,
        sourceNoticeReports,
        trustText,
        watchlistActionDetail
    };
})();
