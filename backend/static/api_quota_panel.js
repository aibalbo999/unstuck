(function () {
    function formatDateTime(value) {
        if (!value) return 'N/A';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString('zh-TW', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    function limitLabel(limit) {
        return window.StockAgentApiQuotaUsage?.limitLabel(limit) || '依方案';
    }

    function usageLabel(usage) {
        const daily = window.StockAgentApiQuotaUsage?.usageLabel(usage);
        if (daily) return daily;
        const parts = [];
        if (Number.isFinite(Number(usage?.observed_calls_since_reset))) {
            parts.push(`LLM ${Number(usage.observed_calls_since_reset)} 次`);
        }
        if (Number.isFinite(Number(usage?.observed_quota_errors_since_reset)) && Number(usage.observed_quota_errors_since_reset) > 0) {
            parts.push(`額度錯誤 ${Number(usage.observed_quota_errors_since_reset)} 次`);
        }
        if (Number.isFinite(Number(usage?.observed_24h_attempts))) {
            parts.push(`24h ${Number(usage.observed_24h_attempts)} 次`);
        }
        if (Number.isFinite(Number(usage?.observed_24h_errors)) && Number(usage.observed_24h_errors) > 0) {
            parts.push(`錯誤 ${Number(usage.observed_24h_errors)} 次`);
        }
        const model = modelUsageLabel(usage);
        if (model) parts.push(`模型 ${model}`);
        return parts.join(' · ') || '尚無本機觀測';
    }
    function modelUsageLabel(usage) { const errors = usage?.observed_model_quota_errors || {}; return Object.entries(usage?.observed_model_calls || {}).slice(0, 6).map(([model, calls]) => { const count = Number(calls || 0), error = Number(errors[model] || 0), rate = count ? Math.round(error / count * 1000) / 10 : 0; return `${model} ${count} 次${error ? ` · 額度錯誤 ${error} 次 (${rate}%)` : ''}`; }).join('；'); }
    function quotaErrorCount(service) {
        const usage = service?.usage || {};
        return window.StockAgentApiQuotaUsage?.errorCount(usage) ?? Number(usage.observed_quota_errors_since_reset || usage.observed_24h_errors || 0);
    }
    function quotaHealth(service) {
        const errors = quotaErrorCount(service);
        if (errors) return { tone: 'warning', label: '有請求事件' };
        if (service.usage?.quota_day_profile?.today?.local_blocks > 0) return { tone: 'warning', label: '有本機攔截' };
        return { tone: service.configured ? 'ok' : 'warning', label: service.configured ? '已設定' : '未設定' };
    }
    const observations = window.StockAgentApiQuotaObservations;

    function reportExecutionMarkup(metrics, escapeHtml) {
        if (!metrics || !metrics.sample_size) return '';
        const mean = metrics.mean_observed_requests_per_completed_report;
        const reasons = {provider_daily_quota_exhausted: '供應商每日額度用完', model_cooldown: '暫時冷卻', input_capacity: '完整輸入超過容量', temporary_provider_failure: '供應商暫時失敗', local_key_admission_timeout: '等候可用額度逾時', legacy_unspecified: '舊紀錄未分類'};
        const statuses = {running: '執行中', waiting_retry: '等待重試', queued: '排隊中', pending: '待執行', error: '失敗', cancelled: '已取消'};
        const skips = (metrics.route_skips || []).slice(0, 12).map(row => `<li>${escapeHtml(row.model_id)}：${escapeHtml(reasons[row.reason_code] || row.reason_code)} ${escapeHtml(row.count)} 次</li>`).join('');
        const jobs = (metrics.reports || []).filter(row => row.status !== 'done').slice(0, 10).map(row => `<li>${escapeHtml(row.ticker)} ${escapeHtml(row.pipeline_id === 'rerun:full_report' ? '完整重跑' : row.pipeline_id)}：${escapeHtml(statuses[row.status] || row.status)}；最近階段 ${escapeHtml(row.last_agent == null ? '未記錄' : 'Agent ' + row.last_agent)}；已觀測請求 ${escapeHtml(row.observed_provider_requests ?? '無資料')}</li>`).join('');
        return `<article class="provider-sla-chip provider-sla-insight"><strong>整份報告的模型用量</strong><span class="provider-sla-detail">${mean == null ? '尚無可計算的已完成報告請求紀錄' : `有請求紀錄的 ${escapeHtml(metrics.completed_with_request_evidence)} 份已完成報告，平均觀測到 ${escapeHtml(mean)} 次模型請求`}</span><span class="provider-sla-detail">完成報告平均歷時 ${escapeHtml(metrics.mean_completed_elapsed_seconds ?? '無資料')} 秒，包含排隊與延後重試。請求數涵蓋 Agent 正文與證據分批，不含摘要與反思。統計取最近有限筆紀錄，缺少資料不視為零。</span><details class="provider-sla-technical"><summary>備援跳過原因與未完成任務</summary><ul>${skips}${jobs}</ul></details></article>`;
    }

    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        if (!summaryEl || !listEl) return;

        const services = payload?.services || [];
        const warnings = observations.routeWarnings(payload);
        const warningGroups = observations.groupedRouteWarnings(warnings);
        const errors = services.reduce((sum, service) => sum + quotaErrorCount(service), 0);
        summaryEl.textContent = observations.summaryText(payload, services, errors, warnings, warningGroups);
        const serviceMarkup = services.length
            ? services.map(service => {
                const usage = usageLabel(service.usage || {});
                const budget = window.StockAgentApiQuotaUsage?.budgetLabel(service.usage?.daily_budget) || '';
                const notes = Array.isArray(service.notes) ? service.notes.slice(0, 2).join('；') : '';
                return `
                    <article class="provider-sla-chip provider-sla-insight is-${quotaHealth(service).tone}">
                        <span class="provider-sla-insight-top">
                            <strong>${escapeHtml(service.service || 'API')}</strong>
                            <em>${escapeHtml(quotaHealth(service).label)}</em>
                        </span>
                        <span class="provider-sla-detail">${escapeHtml(observations.serviceIssueText(service))}</span>
                        <span class="provider-sla-detail">重置：${escapeHtml(service.reset_label || 'N/A')}</span>
                        <span class="provider-sla-meta">下次重置（台灣時間）${escapeHtml(formatDateTime(service.next_reset_taipei))}</span>
                        <details class="provider-sla-technical">
                            <summary>用量與設定明細</summary>
                            <div>key ${escapeHtml(service.key_count ?? 0)} · ${service.usage?.daily_budget?.enforced === false ? '本機數字只供參考，不會攔截' : service.limit_basis ? '本機每日預算' : '方案限制'} ${escapeHtml(limitLabel(service.daily_limit))}</div>
                            <div>${escapeHtml(usage)}</div>
                            ${budget ? `<div>${escapeHtml(budget)}</div>` : ''}
                            ${notes ? `<div>${escapeHtml(notes)}</div>` : ''}
                        </details>
                    </article>
                `;
            }).join('')
            : '';
        const routeMarkup = warningGroups.map(group => observations.routeWarningMarkup(group, escapeHtml)).join('');
        listEl.innerHTML = reportExecutionMarkup(payload?.model_route_budget?.report_execution, escapeHtml) + serviceMarkup + routeMarkup || '<span class="provider-sla-chip is-warning">尚無 LLM/API 本機觀測資料</span>';
    }

    window.StockAgentApiQuotaPanel = { render };
})();
