(function () {
    function formatPct(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'N/A';
        return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`;
    }

    function formatNumber(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'N/A';
        return number.toLocaleString('zh-TW', { maximumFractionDigits: 2 });
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

    function dataTrustReasonCodes(report) {
        const codes = report?.data_trust?.reason_codes;
        return Array.isArray(codes) ? codes.map(code => String(code || '')) : [];
    }

    function dataTrustStaleSources(report) {
        const sources = report?.data_trust?.stale_sources;
        return Array.isArray(sources) ? sources.filter(Boolean) : [];
    }

    function hasRefreshableDataTrustIssue(report) {
        const status = report?.data_trust?.status || 'unknown';
        const reasonCodes = dataTrustReasonCodes(report);
        return status === 'stale'
            || dataTrustStaleSources(report).length > 0
            || reasonCodes.some(code => code.startsWith('source_stale:'));
    }

    function hasProviderSlaOnlyPartial(report) {
        const reasonCodes = dataTrustReasonCodes(report);
        return report?.data_trust?.status === 'partial'
            && !hasRefreshableDataTrustIssue(report)
            && reasonCodes.includes('provider_sla_critical');
    }

    function reportActionBadge(report, escapeHtml) {
        const status = report?.data_trust?.status || 'unknown';
        let label = '可直接使用';
        let tone = 'ok';
        let detail = '資料與結論可直接查看';
        if (status === 'error') {
            label = '暫勿採用';
            tone = 'critical';
            detail = '來源異常，請先重跑或改看其他報告';
        } else if (report?.analysis_text_stale || report?.decision_freshness?.requires_rerun || report?.requires_rerun) {
            label = '建議完整重跑';
            tone = 'critical';
            detail = '結論可能已落後於最新資料';
        } else if (hasRefreshableDataTrustIssue(report)) {
            label = '建議刷新資料';
            tone = 'warning';
            detail = '先刷新資料快照再決策';
        } else if (status === 'partial') {
            label = hasProviderSlaOnlyPartial(report) ? '來源需留意' : '資料需留意';
            tone = 'warning';
            detail = '資料已是最新快照，請查看來源審計與健康度';
        }
        return `<span class="history-action-badge is-${tone}" title="${escapeHtml(detail)}">${escapeHtml(label)}</span>`;
    }

    function targetComparisonCell(tracking, key, escapeHtml) {
        const comparison = tracking?.target_comparisons?.[key] || {};
        const period = { target_3m: '3月', target_6m: '6月', target_12m: '12月' }[key] || '目標';
        const fullPeriod = { target_3m: '3月目標', target_6m: '6月目標', target_12m: '12月目標' }[key] || '目標';
        const status = comparison.status || 'unavailable';
        const label = comparison.label || (status === 'below_target' ? '低於目標' : (status === 'near_target' ? '接近目標' : (status === 'above_target' ? '已高於目標' : '無法比較')));
        const shortLabel = { below_target: '低於', near_target: '接近', above_target: '高於' }[status] || '無法';
        const className = String(status).replace(/_/g, '-');
        const title = comparison.gap_pct === null || comparison.gap_pct === undefined ? `${fullPeriod} ${label}` : `${fullPeriod} ${label} ${formatPct(comparison.gap_pct)}`;
        return `<span class="tracking-target-cell tracking-target-chip is-${className}" title="${escapeHtml(title)}"><span class="tracking-target-period">${escapeHtml(period)}</span><strong class="tracking-target-value">${escapeHtml(formatNumber(comparison.target || tracking?.[key]))}</strong><span class="tracking-target-label">${escapeHtml(shortLabel)}</span></span>`;
    }

    function isActivationKey(event) {
        return event.key === 'Enter' || event.key === ' ';
    }

    function create(options) {
        const listEl = options.listEl;
        const trackingTableEl = options.trackingTableEl;
        const paginationEl = options.paginationEl;
        const prevBtn = options.prevBtn;
        const nextBtn = options.nextBtn;
        const pageInfoEl = options.pageInfoEl;
        const escapeHtml = options.escapeHtml;
        let trackedTickers = new Set();
        let trackingGroups = [];
        let trackingCompact = false;

        function reportTracked(report) {
            return trackedTickers.has(String(report?.ticker || '').toUpperCase());
        }

        function trackButton(report) {
            const tracked = reportTracked(report);
            const label = tracked ? '取消追蹤' : '加入追蹤';
            return `<button class="decision-track-toggle ${tracked ? 'is-tracked' : ''}" type="button" data-track-filename="${escapeHtml(report.filename)}" aria-label="${escapeHtml(label)} ${escapeHtml(report.ticker || '')}">${escapeHtml(label)}</button>`;
        }

        function reportHasTracking(report) {
            return report.decision_tracking && report.decision_tracking.status && report.decision_tracking.status !== 'unavailable';
        }

        function groupLatestReport(group) {
            return (group.reports || []).reduce((best, report) => (
                !best || Number(report.timestamp || 0) > Number(best.timestamp || 0) ? report : best
            ), null);
        }

        function reportCard(report) {
            const tracking = report.decision_tracking || {};
            return `
                <div class="tracking-report-card" data-filename="${escapeHtml(report.filename)}" role="button" tabindex="0" aria-label="預覽 ${escapeHtml(report.ticker || 'N/A')} ${escapeHtml(report.pipeline_label || '')} 追蹤">
                    <div class="tracking-report-cell tracking-report-head">
                        <strong>${escapeHtml(report.pipeline_label || report.pipeline_id || '報告')}</strong>
                        <span class="tracking-report-date">${escapeHtml(report.date || '')}</span>
                    </div>
                    <div class="tracking-report-line tracking-report-metrics">
                        <span class="tracking-recommendation">${escapeHtml(options.normalizeRecommendation(tracking.recommendation || report.recommendation?.recommendation))}</span>
                        <strong class="tracking-latest-price">${escapeHtml(formatNumber(tracking.latest_price))}</strong>
                        <span class="${trackingTone(tracking)}">${escapeHtml(tracking.tracking_summary_status || formatPct(tracking.return_pct))}</span>
                    </div>
                    ${trackingCompact ? '' : `<div class="tracking-target-grid">${targetComparisonCell(tracking, 'target_3m', escapeHtml)}${targetComparisonCell(tracking, 'target_6m', escapeHtml)}${targetComparisonCell(tracking, 'target_12m', escapeHtml)}</div>`}
                </div>
            `;
        }

        function renderTrackingGroups(groups) {
            if (!trackingTableEl) return;
            trackingGroups = groups || [];
            const visibleGroups = trackingGroups
                .map(group => ({ ...group, reports: (group.reports || []).filter(reportHasTracking) }))
                .filter(group => group.reports.length)
                .slice(0, 8);
            if (!visibleGroups.length) {
                trackingTableEl.hidden = true;
                trackingTableEl.innerHTML = '';
                return;
            }
            trackingTableEl.hidden = false;
            trackingTableEl.classList.toggle('is-compact', trackingCompact);
            trackingTableEl.innerHTML = `
                <div class="decision-tracking-title">每日決策追蹤表<span>${trackingCompact ? '精簡比較' : '高密度雙報告比較'}</span></div>
                <div class="tracking-group-list">
                    ${visibleGroups.map(group => {
                        const latest = groupLatestReport(group) || {};
                        const tracking = latest.decision_tracking || {};
                        return `
                            <section class="tracking-stock-group tracking-density-row">
                                <div class="tracking-stock-cell">
                                    <strong>${escapeHtml(group.ticker || latest.ticker || 'N/A')}</strong>
                                    <span class="tracking-company-name">${escapeHtml(group.company_name || latest.company_name || '')}</span>
                                    <span class="tracking-stock-price">最新 ${escapeHtml(formatNumber(tracking.latest_price))}</span>
                                </div>
                                <div class="tracking-group-reports">${group.reports.map(reportCard).join('')}</div>
                            </section>
                        `;
                    }).join('')}
                </div>
            `;
        }

        function renderTrackingTable(reports) {
            const groups = (reports || []).map(report => ({
                ticker: report.ticker,
                company_name: report.company_name,
                reports: [report]
            }));
            renderTrackingGroups(groups);
        }

        function setTrackingCompact(value) {
            trackingCompact = Boolean(value);
            renderTrackingGroups(trackingGroups);
        }

        function renderReports(reports, selectedFilename) {
            if (!listEl) return;
            if (!reports || reports.length === 0) {
                listEl.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.9rem; text-align: center; padding: 20px 0;">尚無報告紀錄</div>';
                return;
            }

            listEl.innerHTML = reports.map(r => `
                <div class="history-item" data-filename="${escapeHtml(r.filename)}" data-ticker="${escapeHtml(r.ticker)}" data-pipeline="${escapeHtml(r.pipeline_id || 'v1')}">
                    <div class="history-info" role="button" tabindex="0" aria-label="預覽 ${escapeHtml(r.ticker || 'N/A')} 報告">
                        <div class="history-ticker">
                            ${escapeHtml(r.ticker)}${r.company_name && r.company_name !== r.ticker ? `<span class="history-company">${escapeHtml(r.company_name)}</span>` : ''}
                        </div>
                        <div class="history-date">
                            <span>${escapeHtml(r.date)}</span>
                            ${options.renderPipelineModeBadge(r.pipeline_id || 'v1')}
                            ${options.renderDataTrustBadge(r.data_trust)}
                            ${options.renderDataTrustReason(r.data_trust)}
                            ${reportActionBadge(r, escapeHtml)}
                        </div>
                        <div class="history-decision">
                            <span class="history-rec ${options.recommendationTone(r.recommendation?.recommendation)}">${escapeHtml(options.normalizeRecommendation(r.recommendation?.recommendation))}</span>
                            <span>${escapeHtml(r.recommendation?.target_12m || 'N/A')}</span>
                            <span>${escapeHtml(r.recommendation?.confidence || 'N/A')}</span>
                            ${renderTrackingBadge(r.decision_tracking, escapeHtml)}
                        </div>
                    </div>
                    ${trackButton(r)}
                    <button class="delete-btn" title="刪除報告" aria-label="刪除 ${escapeHtml(r.ticker || r.filename)} 報告" data-delete-filename="${escapeHtml(r.filename)}">
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
            if (trackingTableEl) {
                trackingTableEl.querySelectorAll('[data-filename]').forEach(row => {
                    row.classList.toggle('is-selected', Boolean(filename) && row.dataset.filename === filename);
                });
            }
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

            if (trackingTableEl) {
                trackingTableEl.addEventListener('click', (event) => {
                    const row = event.target.closest('[data-filename]');
                    if (row) callbacks.onSelect(row.dataset.filename);
                });
                trackingTableEl.addEventListener('keydown', (event) => {
                    if (!isActivationKey(event)) return;
                    const row = event.target.closest('[data-filename]');
                    if (!row) return;
                    event.preventDefault();
                    callbacks.onSelect(row.dataset.filename);
                });
            }

            listEl.addEventListener('keydown', (event) => {
                if (!isActivationKey(event)) return;
                const item = event.target.closest('.history-item');
                if (!item) return;
                event.preventDefault();
                callbacks.onSelect(item.dataset.filename);
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
