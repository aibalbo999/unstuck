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
        listEl.innerHTML = serviceMarkup + routeMarkup || '<span class="provider-sla-chip is-warning">尚無 LLM/API 本機觀測資料</span>';
    }

    window.StockAgentApiQuotaPanel = { render };
})();
