(function () {
    function isWarning(delivery) {
        return !!delivery && (
            Number(delivery.failed_count || 0) > 0 ||
            Number(delivery.retry_exhausted_count || 0) > 0 ||
            delivery.health === 'warning'
        );
    }

    function chip(delivery, escapeHtml) {
        if (!delivery) return '';
        const failed = Number(delivery.failed_count || 0);
        const exhausted = Number(delivery.retry_exhausted_count || 0);
        const pending = Number(delivery.pending_count || 0);
        const total = Number(delivery.total_count || 0);
        const channels = Object.entries(delivery.channel_counts || {}).map(([channel, count]) => `${channel} ${count}`).join(' · ') || '無通道紀錄';
        const reasons = Object.entries(delivery.failure_reason_counts || {}).map(([reason, count]) => `${reason} ${count}`).join(' · ');
        const attention = window.StockAgentDailyQueueContext?.attentionContextText?.({ attention_contexts: delivery.attention_contexts });
        return `
            <span class="provider-sla-chip maintenance-chip ${isWarning(delivery) ? 'is-warning' : 'is-ok'}">
                通知通道 <strong>${escapeHtml(String(total))}</strong>
                <em>失敗 ${escapeHtml(String(failed))} · 重試耗盡 ${escapeHtml(String(exhausted))} · 待送 ${escapeHtml(String(pending))} · ${escapeHtml(channels)}${reasons ? ` · 失敗原因 ${escapeHtml(reasons)}` : ''}${attention ? ` · ${escapeHtml(attention)}` : ''}</em>
            </span>
        `;
    }

    window.StockAgentMaintenanceNotificationDelivery = { chip, isWarning };
})();
