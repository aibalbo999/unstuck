(function () {
    const helpers = window.StockAgentHistoryPanelHelpers;
    const renderersFactory = window.StockAgentHistoryPanelRenderers;
    function create(options) {
        const listEl = options.listEl;
        const trackingTableEl = options.trackingTableEl;
        const paginationEl = options.paginationEl;
        const prevBtn = options.prevBtn;
        const nextBtn = options.nextBtn;
        const pageInfoEl = options.pageInfoEl;
        let trackedTickers = new Set();
        let trackingGroups = [];
        let trackingCompact = false;
        function reportTracked(report) {
            return trackedTickers.has(String(report?.ticker || '').toUpperCase());
        }
        const renderers = renderersFactory.create({ ...options, helpers, reportTracked });
        function renderTrackingGroups(groups) {
            if (!trackingTableEl) return;
            trackingGroups = groups || [];
            const html = renderers.renderTrackingGroups(trackingGroups, trackingCompact);
            trackingTableEl.hidden = !html;
            trackingTableEl.innerHTML = html;
            if (html) trackingTableEl.classList.toggle('is-compact', trackingCompact);
        }
        function renderTrackingTable(reports) {
            renderTrackingGroups((reports || []).map(report => ({
                ticker: report.ticker,
                company_name: report.company_name,
                reports: [report]
            })));
        }
        function setTrackingCompact(value) {
            trackingCompact = Boolean(value);
            renderTrackingGroups(trackingGroups);
        }
        function renderReports(reports, selectedFilename) {
            if (!listEl) return;
            listEl.innerHTML = renderers.renderHistoryList(reports || []);
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
            if (!trackingTableEl) return;
            trackingTableEl.querySelectorAll('[data-filename]').forEach(row => {
                row.classList.toggle('is-selected', Boolean(filename) && row.dataset.filename === filename);
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
                const trackBtn = event.target.closest('.decision-track-toggle');
                if (trackBtn) {
                    callbacks.onToggleTracking(trackBtn.dataset.trackFilename, event);
                    return;
                }
                const item = event.target.closest('.history-item');
                if (item) callbacks.onSelect(item.dataset.filename);
            });
            listEl.addEventListener('keydown', (event) => {
                if (!helpers.isActivationKey(event)) return;
                const item = event.target.closest('.history-item');
                if (!item) return;
                event.preventDefault();
                callbacks.onSelect(item.dataset.filename);
            });
            if (!trackingTableEl) return;
            trackingTableEl.addEventListener('click', (event) => {
                const snapshotButton = event.target.closest('[data-tracking-snapshot]');
                if (snapshotButton) {
                    callbacks.onOpenSnapshot?.(snapshotButton.dataset.trackingSnapshot);
                    return;
                }
                const row = event.target.closest('[data-filename]');
                if (row) callbacks.onSelect(row.dataset.filename);
            });
            trackingTableEl.addEventListener('keydown', (event) => {
                if (!helpers.isActivationKey(event)) return;
                const row = event.target.closest('[data-filename]');
                if (!row) return;
                event.preventDefault();
                callbacks.onSelect(row.dataset.filename);
            });
        }
        return {
            bindEvents,
            clearSelection,
            renderPagination,
            renderReports,
            renderTrackingTable,
            renderTrackingGroups,
            select,
            setTrackingCompact,
            setTrackedTickers: (value) => { trackedTickers = value || new Set(); }
        };
    }
    window.StockAgentHistoryPanel = { create };
})();
