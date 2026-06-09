(function () {
    function formatDelta(delta) {
        if (!delta || delta.delta === null || delta.delta === undefined) return 'N/A';
        const number = Number(delta.delta);
        if (!Number.isFinite(number)) return 'N/A';
        const pct = Number(delta.delta_pct);
        const pctText = Number.isFinite(pct) ? ` (${pct > 0 ? '+' : ''}${pct.toFixed(2)}%)` : '';
        return `${number > 0 ? '+' : ''}${number.toLocaleString('zh-TW', { maximumFractionDigits: 2 })}${pctText}`;
    }

    function dateOrderLabel(order) {
        if (order === 'chronological') return '舊→新';
        if (order === 'reverse') return '新→舊';
        if (order === 'same') return '同時間';
        return '時間未知';
    }

    function decisionStatusLabel(freshness) {
        if (!freshness) return 'N/A';
        if (freshness.requires_rerun || freshness.status === 'needs_rerun') return '需重跑';
        if (freshness.status === 'current') return '有效';
        return freshness.status || 'N/A';
    }

    function create(options) {
        const apiClient = options.apiClient;
        const elements = options.elements || {};
        const escapeHtml = options.escapeHtml || ((value) => String(value ?? ''));
        let selected = [];

        function renderSelection() {
            if (!elements.summaryEl) return;
            if (!selected.length) {
                elements.summaryEl.textContent = '尚未選取比較報告';
                return;
            }
            elements.summaryEl.textContent = selected
                .map(report => `${report.ticker || 'N/A'} · ${report.pipeline_id || 'v1'} · ${report.date || ''}`)
                .join(' ↔ ');
        }

        function renderResult(payload) {
            if (!elements.resultEl) return;
            const diff = payload?.diff || {};
            const left = payload?.left || {};
            const right = payload?.right || {};
            const compatibility = payload?.compatibility || {};
            const warnings = Array.isArray(compatibility.warnings) ? compatibility.warnings : [];
            const compatibilityHtml = warnings.length
                ? `<div class="report-compare-compatibility">
                    ${warnings.map(item => `
                        <span class="provider-sla-chip is-${item.level === 'info' ? 'warning' : 'critical'}">
                            ${escapeHtml(item.message || item)}
                        </span>
                    `).join('')}
                </div>`
                : `<div class="report-compare-compatibility">
                    <span class="provider-sla-chip is-ok">
                        可比較 · ${escapeHtml(dateOrderLabel(compatibility.date_order))}
                    </span>
                </div>`;
            elements.resultEl.hidden = false;
            elements.resultEl.innerHTML = `
                ${compatibilityHtml}
                <div class="report-compare-grid">
                    <span>
                        <strong>${escapeHtml(left.ticker || 'Left')}</strong>
                        <em>${escapeHtml(left.filename || '')}</em>
                    </span>
                    <span>
                        <strong>${escapeHtml(right.ticker || 'Right')}</strong>
                        <em>${escapeHtml(right.filename || '')}</em>
                    </span>
                    <span>
                        <strong>建議</strong>
                        <em>${escapeHtml(diff.recommendation?.before || 'N/A')} → ${escapeHtml(diff.recommendation?.after || 'N/A')}</em>
                    </span>
                    <span>
                        <strong>當日股價</strong>
                        <em>${escapeHtml(formatDelta(diff.current_price))}</em>
                    </span>
                    <span>
                        <strong>3/6/12月目標</strong>
                        <em>${escapeHtml(formatDelta(diff.target_3m))} · ${escapeHtml(formatDelta(diff.target_6m))} · ${escapeHtml(formatDelta(diff.target_12m))}</em>
                    </span>
                    <span>
                        <strong>資料可信度</strong>
                        <em>${escapeHtml(diff.data_trust?.status_before || 'N/A')} → ${escapeHtml(diff.data_trust?.status_after || 'N/A')} · ${escapeHtml(formatDelta(diff.data_trust?.score))}</em>
                    </span>
                    <span>
                        <strong>決策狀態</strong>
                        <em>${escapeHtml(decisionStatusLabel(left.decision_freshness))} → ${escapeHtml(decisionStatusLabel(right.decision_freshness))}</em>
                    </span>
                    <span>
                        <strong>追蹤報酬</strong>
                        <em>${escapeHtml(formatDelta(diff.tracking?.return_pct))}</em>
                    </span>
                    <span>
                        <strong>最新股價</strong>
                        <em>${escapeHtml(formatDelta(diff.tracking?.latest_price))}</em>
                    </span>
                </div>
            `;
        }

        async function compare() {
            if (selected.length < 2) return;
            try {
                if (elements.addBtn) elements.addBtn.disabled = true;
                if (elements.resultEl) {
                    elements.resultEl.hidden = false;
                    elements.resultEl.innerHTML = '<span class="provider-sla-chip is-warning">比較中</span>';
                }
                const payload = await apiClient.compareReports(selected[0].filename, selected[1].filename);
                renderResult(payload);
            } catch (err) {
                console.error('Failed to compare reports', err);
                if (elements.resultEl) {
                    elements.resultEl.hidden = false;
                    elements.resultEl.innerHTML = `<span class="provider-sla-chip is-critical">比較失敗：${escapeHtml(err.message || err)}</span>`;
                }
            } finally {
                if (elements.addBtn) elements.addBtn.disabled = false;
            }
        }

        function addReport(report) {
            if (!report || !report.filename) return;
            selected = selected.filter(item => item.filename !== report.filename);
            selected.push(report);
            if (selected.length > 2) selected = selected.slice(-2);
            renderSelection();
            if (selected.length === 2) compare();
        }

        function clear() {
            selected = [];
            renderSelection();
            if (elements.resultEl) {
                elements.resultEl.hidden = true;
                elements.resultEl.innerHTML = '';
            }
        }

        function bindEvents(getReport) {
            if (elements.addBtn) {
                elements.addBtn.addEventListener('click', () => addReport(getReport ? getReport() : null));
            }
            if (elements.clearBtn) {
                elements.clearBtn.addEventListener('click', clear);
            }
        }

        renderSelection();
        return { addReport, bindEvents, clear };
    }

    window.StockAgentReportComparePanel = { create };
})();
