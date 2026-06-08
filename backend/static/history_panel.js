(function () {
    function formatPct(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'N/A';
        return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`;
    }

    function trackingTone(tracking) {
        const value = Number(tracking && tracking.return_pct);
        if (!Number.isFinite(value) || value === 0) return 'is-neutral';
        if (tracking.status === 'target_hit' || tracking.status === 'avoided_loss') return 'is-positive';
        if (tracking.recommendation === '避免') return value < 0 ? 'is-positive' : 'is-negative';
        return value > 0 ? 'is-positive' : 'is-negative';
    }

    function renderTrackingBadge(tracking, escapeHtml) {
        if (!tracking || !tracking.status || tracking.status === 'unavailable' || !Number.isFinite(Number(tracking.return_pct))) return '';
        const title = tracking.summary || '決策追蹤';
        return `<span class="history-tracking ${trackingTone(tracking)}" title="${escapeHtml(title)}">追蹤 ${escapeHtml(formatPct(tracking.return_pct))}</span>`;
    }

    function create(options) {
        const listEl = options.listEl;
        const paginationEl = options.paginationEl;
        const prevBtn = options.prevBtn;
        const nextBtn = options.nextBtn;
        const pageInfoEl = options.pageInfoEl;
        const escapeHtml = options.escapeHtml;

        function renderReports(reports, selectedFilename) {
            if (!listEl) return;
            if (!reports || reports.length === 0) {
                listEl.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.9rem; text-align: center; padding: 20px 0;">尚無報告紀錄</div>';
                return;
            }

            listEl.innerHTML = reports.map(r => `
                <div class="history-item" data-filename="${escapeHtml(r.filename)}" data-ticker="${escapeHtml(r.ticker)}" data-pipeline="${escapeHtml(r.pipeline_id || 'v1')}">
                    <div class="history-info" role="button" tabindex="0">
                        <div class="history-ticker">
                            ${escapeHtml(r.ticker)}${r.company_name && r.company_name !== r.ticker ? `<span class="history-company">${escapeHtml(r.company_name)}</span>` : ''}
                        </div>
                        <div class="history-date">
                            <span>${escapeHtml(r.date)}</span>
                            ${options.renderPipelineModeBadge(r.pipeline_id || 'v1')}
                            ${options.renderDataTrustBadge(r.data_trust)}
                            ${options.renderDataTrustReason(r.data_trust)}
                        </div>
                        <div class="history-decision">
                            <span class="history-rec ${options.recommendationTone(r.recommendation?.recommendation)}">${escapeHtml(options.normalizeRecommendation(r.recommendation?.recommendation))}</span>
                            <span>${escapeHtml(r.recommendation?.target_12m || 'N/A')}</span>
                            <span>${escapeHtml(r.recommendation?.confidence || 'N/A')}</span>
                            ${renderTrackingBadge(r.decision_tracking, escapeHtml)}
                        </div>
                    </div>
                    <button class="delete-btn" title="刪除報告" data-delete-filename="${escapeHtml(r.filename)}">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                    </button>
                </div>
            `).join('');
            select(selectedFilename);
        }

        function renderPagination(pagination) {
            if (!paginationEl || !prevBtn || !nextBtn || !pageInfoEl) return pagination?.page || 1;
            const totalPages = pagination.total_pages || 1;
            paginationEl.hidden = totalPages <= 1;
            prevBtn.disabled = !pagination.has_prev;
            nextBtn.disabled = !pagination.has_next;
            const page = pagination.page || 1;
            pageInfoEl.textContent = `${page} / ${totalPages}`;
            return page;
        }

        function select(filename) {
            if (!listEl) return;
            listEl.querySelectorAll('.history-item').forEach(item => {
                item.classList.toggle('is-selected', Boolean(filename) && item.dataset.filename === filename);
            });
        }

        function clearSelection() {
            select(null);
        }

        function bindEvents(callbacks) {
            if (!listEl) return;
            listEl.addEventListener('click', (event) => {
                const deleteBtn = event.target.closest('.delete-btn');
                if (deleteBtn) {
                    callbacks.onDelete(deleteBtn.dataset.deleteFilename, event);
                    return;
                }
                const item = event.target.closest('.history-item');
                if (item) callbacks.onSelect(item.dataset.filename);
            });

            listEl.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter') return;
                const item = event.target.closest('.history-item');
                if (item) callbacks.onSelect(item.dataset.filename);
            });
        }

        return {
            bindEvents,
            clearSelection,
            renderPagination,
            renderReports,
            select
        };
    }

    window.StockAgentHistoryPanel = { create };
})();
