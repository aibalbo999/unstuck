(function () {
    const helpers = window.StockAgentProviderSlaHelpers;
    const {
        LEVEL_WEIGHT,
        formatSuccessRate,
        providerSlaStatsForWindow,
        providerSlaWindowLabel,
        groupedProviderRows,
        mergeExpectedContextRows,
        visibleProviderRows,
        readableSource,
        rowStateLabel,
        insightText,
        summaryText,
        sourceIsCore,
        providerStatusIsHealthy,
        providerStatusLabel
    } = helpers;

    function providerDetailsHtml(row, escapeHtml) {
        const providerRows = (row.providerRows || []).slice().sort((a, b) => {
            const healthyDelta = Number(providerStatusIsHealthy(b.lastStatus)) - Number(providerStatusIsHealthy(a.lastStatus));
            const levelDelta = (LEVEL_WEIGHT[a.level] || 0) - (LEVEL_WEIGHT[b.level] || 0);
            return healthyDelta || levelDelta || Number(b.totalRecords || 0) - Number(a.totalRecords || 0) || Number(b.attempts || 0) - Number(a.attempts || 0);
        }).slice(0, 4);
        if (!providerRows.length) return '';
        return `
            <span class="provider-sla-provider-list" aria-label="來源明細">
                <span class="provider-sla-provider-title">來源明細</span>
                ${providerRows.map(provider => `
                    <span class="provider-sla-provider is-${provider.level}" title="${escapeHtml(provider.lastMessage || '')}">
                        <strong>${escapeHtml(provider.provider)}</strong>
                        <em>${escapeHtml(formatSuccessRate(provider.successRate))} · ${escapeHtml(providerStatusLabel(provider.lastStatus, provider, row.level === 'ok'))} · ${escapeHtml(String(provider.attempts || 0))} 次</em>
                    </span>
                `).join('')}
            </span>
        `;
    }

    function render(payload, options) {
        const summaryEl = options.summaryEl;
        const listEl = options.listEl;
        const windowEl = options.windowEl;
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        if (!summaryEl || !listEl) return;

        const providers = payload?.providers || [];
        const selectedWindow = windowEl ? windowEl.value : 'all';
        const windowLabel = providerSlaWindowLabel(selectedWindow);
        const rows = mergeExpectedContextRows(groupedProviderRows(providers, selectedWindow));
        summaryEl.textContent = summaryText(rows, windowLabel, providers);
        listEl.innerHTML = rows.length
            ? visibleProviderRows(rows).map(row => {
                const successRate = row.availabilityAttempts ? row.healthyCount / row.availabilityAttempts : NaN;
                const recordsLabel = row.totalRecords ? `取得 ${row.totalRecords} 筆資料` : '資料量尚少';
                const checksLabel = row.attempts ? `檢查 ${row.attempts} 次` : '尚未檢查';
                const title = `${readableSource(row.source)}：${rowStateLabel(row)}。${insightText(row)}`;
                return `
                    <span class="provider-sla-chip provider-sla-insight is-${row.level}" title="${escapeHtml(title)}">
                        <span class="provider-sla-insight-top">
                            <strong>${escapeHtml(readableSource(row.source))}</strong>
                            <em>${escapeHtml(rowStateLabel(row))}</em>
                        </span>
                        <span class="provider-sla-detail">${escapeHtml(insightText(row))}</span>
                        <span class="provider-sla-meta">${escapeHtml(recordsLabel)} · 資料取得率 ${escapeHtml(formatSuccessRate(successRate))} · ${escapeHtml(checksLabel)}</span>
                        ${providerDetailsHtml(row, escapeHtml)}
                    </span>
                `;
            }).join('')
            : '<span class="provider-sla-chip is-ok">下一次分析後會更新全系統資料來源狀態</span>';
    }

    window.StockAgentProviderSlaPanel = { render, providerSlaStatsForWindow, providerSlaWindowLabel, groupedProviderRows, mergeExpectedContextRows, visibleProviderRows, sourceIsCore };
})();
