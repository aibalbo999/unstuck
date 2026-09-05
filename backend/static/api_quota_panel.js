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
        if (errors) return { tone: 'warning', label: '有錯誤' };
        if (service.usage?.quota_day_profile?.today?.local_blocks > 0) return { tone: 'warning', label: '有本機攔截' };
        return { tone: service.configured ? 'ok' : 'warning', label: service.configured ? '已設定' : '未設定' };
    }
    const routeWarningCopy = { slow_route: { tone: 'warning', label: '路由延遲偏高' }, retry_storm: { tone: 'critical', label: '模型重試過多' }, quality_gate_failures: { tone: 'critical', label: '品質檢查失敗' }, provider_quota_errors: { tone: 'critical', label: 'Provider 配額錯誤' }, provider_errors: { tone: 'critical', label: 'Provider 錯誤' } };
    function routeWarnings(payload) { return Array.isArray(payload?.model_route_budget?.warnings) ? payload.model_route_budget.warnings.filter(item => item && typeof item === 'object').slice(0, 20) : []; }
    function routeWarningMarkup(warning, escapeHtml) {
        const copy = routeWarningCopy[String(warning.id)] || { tone: 'warning', label: '模型路由警示' };
        return `<span class="provider-sla-chip provider-sla-insight is-${copy.tone}"><span class="provider-sla-insight-top"><strong>${escapeHtml(copy.label)}</strong><em>維運觀測</em></span><span class="provider-sla-detail">路由：${escapeHtml(warning.route || 'unknown')}</span><span class="provider-sla-meta">${escapeHtml(warning.message || '尚無詳細訊息')}</span><span class="provider-sla-detail">單份報告是否重跑，請以資料可信度與今日工作台判斷。</span></span>`;
    }

    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        if (!summaryEl || !listEl) return;

        const services = payload?.services || [];
        const warnings = routeWarnings(payload);
        const configured = services.filter(service => service.configured).length;
        const errors = services.reduce((sum, service) => sum + quotaErrorCount(service), 0);
        summaryEl.textContent = 'LLM/API 本機觀測尚無資料';
        if (errors && warnings.length) summaryEl.textContent = `LLM/API 本機觀測需留意：${errors} 次錯誤、${warnings.length} 個路由警示，${configured}/${services.length} 組服務已設定`;
        else if (warnings.length) summaryEl.textContent = `LLM/API 本機觀測需留意：${warnings.length} 個路由警示，${configured}/${services.length} 組服務已設定`;
        else if (errors) summaryEl.textContent = `LLM/API 本機觀測需留意：${errors} 次錯誤，${configured}/${services.length} 組服務已設定`;
        else if (services.length) summaryEl.textContent = `LLM/API 本機觀測：${configured}/${services.length} 組服務已設定`;
        const serviceMarkup = services.length
            ? services.map(service => {
                const usage = usageLabel(service.usage || {});
                const budget = window.StockAgentApiQuotaUsage?.budgetLabel(service.usage?.daily_budget) || '';
                const notes = Array.isArray(service.notes) ? service.notes.slice(0, 2).join('；') : '';
                return `
                    <span class="provider-sla-chip provider-sla-insight is-${quotaHealth(service).tone}">
                        <span class="provider-sla-insight-top">
                            <strong>${escapeHtml(service.service || 'API')}</strong>
                            <em>${escapeHtml(quotaHealth(service).label)}</em>
                        </span>
                        <span class="provider-sla-detail">重置：${escapeHtml(service.reset_label || 'N/A')}</span>
                        <span class="provider-sla-meta">台灣時間 ${escapeHtml(formatDateTime(service.next_reset_taipei))} · key ${escapeHtml(service.key_count ?? 0)} · ${service.limit_basis ? '每專案本機每日預算' : 'limit'} ${escapeHtml(limitLabel(service.daily_limit))}</span>
                        <span class="provider-sla-meta">${escapeHtml(usage)}</span>
                        ${budget ? `<span class="provider-sla-meta">${escapeHtml(budget)}</span>` : ''}
                        ${notes ? `<span class="provider-sla-detail">${escapeHtml(notes)}</span>` : ''}
                    </span>
                `;
            }).join('')
            : '';
        const routeMarkup = warnings.map(warning => routeWarningMarkup(warning, escapeHtml)).join('');
        listEl.innerHTML = serviceMarkup + routeMarkup || '<span class="provider-sla-chip is-warning">尚無 LLM/API 本機觀測資料</span>';
    }

    window.StockAgentApiQuotaPanel = { render };
})();
