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
        const pipelineModeLabel = options.pipelineModeLabel
            || window.StockAgentUi?.pipelineModeLabel
            || ((pipelineId) => String(pipelineId || 'v1'));
        let selected = [];

        function compareWarningMessage(item, left, right) {
            if (item?.code === 'different_pipeline') return `兩份報告模式不同：${pipelineModeLabel(left.pipeline_id || 'v1')} 與 ${pipelineModeLabel(right.pipeline_id || 'v1')}；這是跨視角比較。`;
            if (item?.code?.includes('decision_needs_rerun')) return `${item.code.startsWith('left_') ? '左側' : '右側'}報告若要比較投資判斷，需先重跑結論。`;
            return item?.message || item;
        }

        function compareSummaryLabel(compatibility) {
            if (compatibility.same_ticker && compatibility.same_pipeline) return `同股票同模式 · ${dateOrderLabel(compatibility.date_order)}`;
            if (!compatibility.same_ticker) return `股票不同 · ${dateOrderLabel(compatibility.date_order)}`;
            if (!compatibility.same_pipeline) return `跨視角比較 · ${dateOrderLabel(compatibility.date_order)}`;
            return `需留意 · ${dateOrderLabel(compatibility.date_order)}`;
        }

        function gridCell(label, value) { return `<span><strong>${escapeHtml(label)}</strong><em>${escapeHtml(value)}</em></span>`; }

        function renderSelection() {
            if (!elements.summaryEl) return;
            if (!selected.length) {
                elements.summaryEl.textContent = '尚未選取比較報告';
                return;
            }
            elements.summaryEl.textContent = selected
                .map(report => `${report.ticker || 'N/A'} · ${pipelineModeLabel(report.pipeline_id || 'v1')} · ${report.date || ''}`)
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
                            ${escapeHtml(compareWarningMessage(item, left, right))}
                        </span>
                    `).join('')}
                </div>`
                : `<div class="report-compare-compatibility">
                    <span class="provider-sla-chip is-ok">
                        可比較 · ${escapeHtml(dateOrderLabel(compatibility.date_order))}
                    </span>
                </div>`;
            elements.resultEl.hidden = false;
            const gridRows = [
                ['比較結論', compareSummaryLabel(compatibility)],
                [left.ticker || 'Left', left.filename || ''],
                [right.ticker || 'Right', right.filename || ''],
                ['比較基準', `${pipelineModeLabel(left.pipeline_id || 'v1')} → ${pipelineModeLabel(right.pipeline_id || 'v1')}`],
                ['比較樣本', `${left.date || 'N/A'} → ${right.date || 'N/A'} · ${dateOrderLabel(compatibility.date_order)}`],
                ['使用提醒', '僅比較既有報告，不代表即時交易指令'],
                ['判讀層次', '報告差異不等於市場因果；搭配資料可信度與追蹤報酬判讀'],
                ['報告建議變化', `${diff.recommendation?.before || 'N/A'} → ${diff.recommendation?.after || 'N/A'}`],
                ['當日股價', formatDelta(diff.current_price)],
                ['3/6/12月目標', `${formatDelta(diff.target_3m)} · ${formatDelta(diff.target_6m)} · ${formatDelta(diff.target_12m)}`],
                ['資料可信度', `${diff.data_trust?.status_before || 'N/A'} → ${diff.data_trust?.status_after || 'N/A'} · ${formatDelta(diff.data_trust?.score)}`],
                ['決策狀態', `${decisionStatusLabel(left.decision_freshness)} → ${decisionStatusLabel(right.decision_freshness)}`],
                ['追蹤報酬', formatDelta(diff.tracking?.return_pct)],
                ['最新股價', formatDelta(diff.tracking?.latest_price)],
            ].map(([label, value]) => gridCell(label, value)).join('');
            elements.resultEl.innerHTML = `
                ${compatibilityHtml}
                <div class="report-compare-grid">${gridRows}</div>
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
