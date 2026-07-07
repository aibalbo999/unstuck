(function () {
    function formatNumber(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'N/A';
        return number.toLocaleString('zh-TW', { maximumFractionDigits: 2 });
    }

    function formatPct(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 'N/A';
        return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`;
    }

    function pctTone(value) {
        const number = Number(value);
        if (!Number.isFinite(number) || number === 0) return 'is-neutral';
        return number > 0 ? 'is-positive' : 'is-negative';
    }

    function normalizeTrackingRecommendation(value) {
        return window.StockAgentUi?.normalizeRecommendation
            ? window.StockAgentUi.normalizeRecommendation(value)
            : String(value || '');
    }

    function returnTone(tracking) {
        const value = Number(tracking && tracking.return_pct);
        if (!Number.isFinite(value) || value === 0) return 'is-neutral';
        if (tracking.status === 'target_hit' || tracking.status === 'avoided_loss') return 'is-positive';
        if (['避免', '放空'].includes(normalizeTrackingRecommendation(tracking.recommendation))) return value < 0 ? 'is-positive' : 'is-negative';
        return value > 0 ? 'is-positive' : 'is-negative';
    }

    function awaitingTrackingPrice(tracking) {
        return tracking?.status === 'tracked'
            && !tracking.snapshot_refreshed_at
            && Number(tracking.return_pct) === 0
            && Number(tracking.initial_price) === Number(tracking.latest_price);
    }

    function setButtonText(button, text) {
        const label = button ? button.querySelector('span') : null;
        if (label) label.textContent = text;
    }

    const FALLBACK_SUMMARY = '這份報告沒有可讀的一頁式摘要，可直接查看完整報告；報告建議仍需自行判斷。';

    function legacyPreview(report, rec, options) {
        return {
            title: `${report.ticker} 報告建議`,
            primary: { label: '報告建議', value: options.normalizeRecommendation(rec.recommendation), tone: options.recommendationTone(rec.recommendation) },
            metrics: [{ label: '當日股價', value: rec.current_price || 'N/A' }, { label: '信心', value: rec.confidence || 'N/A' }],
            targets: [{ label: '3個月', value: rec.target_3m || 'N/A' }, { label: '6個月', value: rec.target_6m || 'N/A' }, { label: '12個月', value: rec.target_12m || 'N/A' }],
            summary: rec.summary || FALLBACK_SUMMARY
        };
    }

    function metricCard(item, className, escapeHtml) {
        const tone = item?.tone ? ` class="${escapeHtml(item.tone)}"` : '';
        const cardClass = className ? ` class="${className}"` : '';
        return `<div${cardClass}><span class="preview-label">${escapeHtml(item?.label || '')}</span><strong${tone}>${escapeHtml(item?.value || 'N/A')}</strong></div>`;
    }

    function renderMetrics(container, metrics, className, escapeHtml) {
        if (!container) return;
        const items = (metrics || []).filter(Boolean);
        container.hidden = !items.length;
        container.innerHTML = items.map(item => metricCard(item, className, escapeHtml)).join('');
    }

    function configureRerunButtons(elements, pipelineId, pipelineMeta) {
        const meta = typeof pipelineMeta === 'function' ? pipelineMeta(pipelineId) : null;
        const shortLabel = meta?.shortLabel || pipelineId.toUpperCase();
        const isModeB = pipelineId === 'v2';
        setButtonText(elements.rerunFinalBtn, `重跑${shortLabel}報告結論`);
        setButtonText(elements.rerunFullBtn, `完整重跑${shortLabel}`);
        if (elements.rerunModeBBtn) {
            elements.rerunModeBBtn.hidden = isModeB;
            if (!isModeB) setButtonText(elements.rerunModeBBtn, '產生模式 B 報告');
        }
    }

    function reportQualityBadge(report, escapeHtml) {
        const conformance = report?.report_conformance || {};
        const gate = report?.evidence_exit_gate || {};
        let label = '', tone = '', detail = '';
        if (conformance.status === 'blocked') { label = '報告符合性未通過'; tone = 'critical'; detail = conformance.summary || '報告未符合輸出契約，暫勿直接採用。'; }
        else if (conformance.status === 'warning') { label = '報告符合性需確認'; tone = 'warning'; detail = conformance.summary || '報告符合主要契約，但仍需人工確認。'; }
        else if (gate.verdict === 'rejected') { label = '證據抽查未通過'; tone = 'critical'; detail = gate.summary || '報告數字未能對上資料快照，暫勿直接採用。'; }
        else if (gate.verdict === 'caution') { label = '數字證據需人工核對'; tone = 'warning'; detail = gate.summary || '部分報告數字需人工確認。'; }
        return label ? `<span class="history-action-badge is-${tone}" title="${escapeHtml(detail)}">${escapeHtml(label)}</span>` : '';
    }

    function renderTracking(tracking, elements) {
        if (!elements.trackingRoot) return;
        if (!tracking || !tracking.status || tracking.status === 'unavailable') {
            elements.trackingRoot.hidden = true;
            return;
        }
        elements.trackingLatest.textContent = formatNumber(tracking.latest_price);
        elements.trackingReturn.textContent = awaitingTrackingPrice(tracking) ? '待新價格' : formatPct(tracking.return_pct);
        elements.trackingReturn.className = returnTone(tracking);
        elements.trackingGap.textContent = formatPct(tracking.target_12m_gap_pct);
        elements.trackingGap.className = pctTone(tracking.target_12m_gap_pct);
        elements.trackingSummary.textContent = awaitingTrackingPrice(tracking) ? '尚待新價格更新後計算建議後報酬。' : (tracking.summary || '已建立決策追蹤。');
        elements.trackingRoot.hidden = false;
    }

    function create(options) {
        const elements = options.elements || {};
        const doc = typeof document === 'undefined' ? null : document;
        elements.decisionRow = elements.decisionRow || elements.root?.querySelector?.('.preview-decision-row');
        elements.targets = elements.targets || elements.root?.querySelector?.('.preview-targets');
        elements.trackingRoot = elements.trackingRoot || doc?.getElementById('preview-tracking');
        elements.trackingLatest = elements.trackingLatest || doc?.getElementById('preview-tracking-latest');
        elements.trackingReturn = elements.trackingReturn || doc?.getElementById('preview-tracking-return');
        elements.trackingGap = elements.trackingGap || doc?.getElementById('preview-tracking-gap');
        elements.trackingSummary = elements.trackingSummary || doc?.getElementById('preview-tracking-summary');
        elements.temporalMemoryRoot = elements.temporalMemoryRoot || doc?.getElementById('preview-temporal-memory');

        function setPreviewOpen(open) {
            if (elements.workspace) elements.workspace.classList.toggle('has-preview', open);
        }

        function show(report) {
            if (!report || !elements.root) return false;
            const rec = report.recommendation || {};
            const pipelineId = report.pipeline_id || 'v1';
            const preview = report.preview || legacyPreview(report, rec, options);
            const decisionMetrics = [preview.primary, ...(preview.metrics || [])].filter(Boolean);

            elements.mode.innerHTML = `${options.renderPipelineModeBadge(pipelineId)}${options.renderDataTrustBadge(report.data_trust)}${reportQualityBadge(report, options.escapeHtml)}<span class="preview-date">${options.escapeHtml(report.date || '')}</span>`;
            configureRerunButtons(elements, pipelineId, options.pipelineMeta);
            elements.title.textContent = preview.title || `${report.ticker} 報告建議`;
            renderMetrics(elements.decisionRow, decisionMetrics, 'preview-decision', options.escapeHtml);
            renderMetrics(elements.targets, preview.targets, '', options.escapeHtml);
            elements.summary.textContent = preview.summary || rec.summary || FALLBACK_SUMMARY;
            renderTracking(report.decision_tracking, elements);
            if (window.StockAgentTemporalMemoryPanel) {
                window.StockAgentTemporalMemoryPanel.render(report.temporal_memory, elements.temporalMemoryRoot, options.escapeHtml);
            }

            if (elements.staleNotice) {
                const freshness = report.decision_freshness || {};
                const staleMessage = freshness.message
                    || freshness.requires_rerun_reason
                    || report.analysis_text_stale_message
                    || '資料快照已刷新，但這份 HTML/Markdown 分析本文尚未重新執行。';
                elements.staleNotice.textContent = staleMessage;
                elements.staleNotice.hidden = !(report.analysis_text_stale || freshness.requires_rerun);
            }

            elements.root.hidden = false;
            setPreviewOpen(true);
            return true;
        }

        function hide() {
            if (elements.root) elements.root.hidden = true;
            if (elements.trackingRoot) elements.trackingRoot.hidden = true;
            if (elements.temporalMemoryRoot) elements.temporalMemoryRoot.hidden = true;
            setPreviewOpen(false);
        }

        function setStatus(message) {
            if (!elements.staleNotice) return;
            elements.staleNotice.textContent = message || '';
            elements.staleNotice.hidden = !message;
        }

        return { hide, setStatus, show };
    }

    window.StockAgentReportPreviewPanel = { create };
})();
