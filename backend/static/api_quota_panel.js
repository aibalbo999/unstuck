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
        if (!limit) return '依方案';
        if (typeof limit === 'number') return String(limit);
        if (typeof limit !== 'object') return String(limit);
        return Object.entries(limit)
            .map(([key, value]) => `${key.replaceAll('_', ' ')} ${value}`)
            .join(' · ');
    }

    function usageLabel(usage) {
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
        return parts.join(' · ') || '尚無本機觀測';
    }

    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        if (!summaryEl || !listEl) return;

        const services = payload?.services || [];
        const configured = services.filter(service => service.configured).length;
        summaryEl.textContent = services.length
            ? `${configured}/${services.length} 組 API 已設定`
            : 'API 額度狀態尚無資料';
        listEl.innerHTML = services.length
            ? services.map(service => {
                const tone = service.configured ? 'ok' : 'warning';
                const usage = usageLabel(service.usage || {});
                const notes = Array.isArray(service.notes) ? service.notes.slice(0, 2).join('；') : '';
                return `
                    <span class="provider-sla-chip provider-sla-insight is-${tone}">
                        <span class="provider-sla-insight-top">
                            <strong>${escapeHtml(service.service || 'API')}</strong>
                            <em>${service.configured ? '已設定' : '未設定'}</em>
                        </span>
                        <span class="provider-sla-detail">重置：${escapeHtml(service.reset_label || 'N/A')}</span>
                        <span class="provider-sla-meta">台灣時間 ${escapeHtml(formatDateTime(service.next_reset_taipei))} · key ${escapeHtml(service.key_count ?? 0)} · limit ${escapeHtml(limitLabel(service.daily_limit))}</span>
                        <span class="provider-sla-meta">${escapeHtml(usage)}</span>
                        ${notes ? `<span class="provider-sla-detail">${escapeHtml(notes)}</span>` : ''}
                    </span>
                `;
            }).join('')
            : '<span class="provider-sla-chip is-warning">尚無 API 額度資料</span>';
    }

    window.StockAgentApiQuotaPanel = { render };
})();
