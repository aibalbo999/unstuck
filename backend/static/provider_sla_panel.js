(function () {
    const helpers = window.StockAgentProviderSlaHelpers;
    const { count, formatSuccessRate, providerSlaWindowLabel, groupedProviderRows, mergeExpectedContextRows,
        visibleProviderRows, readableSource, rowStateLabel, insightText, summaryText,
        breakdownText, providerStatusLabel, sourceGroupLevel } = helpers;
    const escapeText = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

    function providerDetailsHtml(row, escapeHtml) {
        const providers = (row.providers || []).slice().sort((a, b) =>
            count(b, 'failed_count') - count(a, 'failed_count') || count(b, 'unknown_count') - count(a, 'unknown_count') || count(b, 'empty_count') - count(a, 'empty_count') || String(a.provider).localeCompare(String(b.provider)));
        if (!providers.length) return '';
        return `<details class="provider-sla-provider-list" ${row.level === 'critical' ? 'open' : ''}>
            <summary class="provider-sla-provider-title">來源明細（全部 ${providers.length} 個，失敗優先）</summary>
            ${providers.map(provider => `<div class="provider-sla-provider is-${sourceGroupLevel({...provider, source: row.source})}">
                <strong>${escapeHtml(provider.provider)}</strong>
                <em>${escapeHtml(formatSuccessRate(provider.nonempty_rate))} · ${escapeHtml(providerStatusLabel(provider.last_kind))}</em>
                <span class="provider-sla-provider-breakdown">${escapeHtml(breakdownText(provider))}</span>
                <span class="provider-sla-provider-breakdown">已辨識 HTTP 請求 ${count(provider, 'http_attempt_count')} 次${provider.last_details?.error_kind ? ` · ${escapeHtml(provider.last_details.error_kind)}` : ''}${provider.last_details?.retry_at ? ` · 可重試時間 ${escapeHtml(new Date(provider.last_details.retry_at * 1000).toLocaleString('zh-TW', {timeZone: 'Asia/Taipei', hour12: false}))}` : ''}</span>
            </div>`).join('')}
        </details>`;
    }

    function render(payload, options) {
        const { summaryEl, listEl } = options;
        if (!summaryEl || !listEl) return;
        const escapeHtml = options.escapeHtml || escapeText;
        const acquisition = payload?.acquisition;
        if (!acquisition || acquisition.available !== true || !Array.isArray(acquisition.sources)) {
            summaryEl.textContent = '來源觀測紀錄暫時無法讀取';
            listEl.innerHTML = '<span class="provider-sla-chip is-warning">無法判定取得資料情況，請稍後重新整理；若持續出現，請確認統計服務已更新。</span>';
            return;
        }
        const selectedWindow = options.windowEl?.value || acquisition.selected_window;
        if (selectedWindow !== acquisition.selected_window) return;
        const rows = mergeExpectedContextRows(groupedProviderRows(acquisition.sources));
        const updated = new Date(acquisition.generated_at * 1000).toLocaleString('zh-TW', {hour12: false, timeZone: 'Asia/Taipei'});
        summaryEl.textContent = `${summaryText(rows, providerSlaWindowLabel(selectedWindow))} · 更新 ${updated}（台灣時間）`;
        listEl.innerHTML = `<p class="provider-sla-explanation">取得資料率＝成功且有資料的供應商觀測／抓取觀測。快取、冷卻略過及彙總結果不列入分子或分母；降級資料列入分母。觀測次數不等於 API 請求數，HTTP 僅計明確記錄的請求，舊紀錄不推算。資料筆數不代表內容已驗證。</p>` +
            visibleProviderRows(rows).map(row => `<section class="provider-sla-chip provider-sla-insight is-${row.level}" data-source="${escapeHtml(row.source)}">
                <div class="provider-sla-insight-top"><strong>${escapeHtml(readableSource(row.source))}</strong><em>${escapeHtml(rowStateLabel(row))}</em></div>
                <span class="provider-sla-rate">${escapeHtml(formatSuccessRate(row.nonempty_rate))}${count(row, 'fetch_attempts') ? ' 取得資料率' : ''}</span>
                <span class="provider-sla-meta">成功且有資料 ${count(row, 'fetched_count')}／抓取觀測 ${count(row, 'fetch_attempts')} 次</span>
                <span class="provider-sla-detail">${escapeHtml(breakdownText(row))}</span>
                <span class="provider-sla-meta">${escapeHtml(insightText(row))}</span>
                ${row.last_selection ? `<span class="provider-sla-meta">最近一次內容篩選（${escapeHtml(row.last_selection.provider)}）：原始 ${count(row.last_selection, 'raw_count')} 筆 · 可用 ${count(row.last_selection, 'usable_count')} 筆 · 排除 ${count(row.last_selection, 'rejected_count')} 筆；不代表全文或獨立來源皆已驗證。</span>` : ''}
                ${count(row, 'aggregate_count') ? `<span class="provider-sla-meta">已排除 ${count(row, 'aggregate_count')} 筆彙總紀錄</span>` : ''}
                ${providerDetailsHtml(row, escapeHtml)}
            </section>`).join('');
    }
    window.StockAgentProviderSlaPanel = { render };
})();
