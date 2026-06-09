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

    function returnTone(tracking) {
        const value = Number(tracking && tracking.return_pct);
        if (!Number.isFinite(value) || value === 0) return 'is-neutral';
        if (tracking.status === 'target_hit' || tracking.status === 'avoided_loss') return 'is-positive';
        if (tracking.recommendation === '避免') return value < 0 ? 'is-positive' : 'is-negative';
        return value > 0 ? 'is-positive' : 'is-negative';
    }

    function setButtonText(button, text) {
        const label = button ? button.querySelector('span') : null;
        if (label) label.textContent = text;
    }

    function configureRerunButtons(elements, pipelineId) {
        const isModeB = pipelineId === 'v2';
        setButtonText(elements.rerunFinalBtn, isModeB ? '重跑模式 B 最終建議' : '重跑模式 A 最終建議');
        setButtonText(elements.rerunFullBtn, isModeB ? '完整重跑模式 B' : '完整重跑模式 A');
        setButtonText(elements.rerunModeBBtn, isModeB ? '重跑完整模式 B' : '產生模式 B 報告');
    }

    function renderTracking(tracking, elements) {
        if (!elements.trackingRoot) return;
        if (!tracking || !tracking.status || tracking.status === 'unavailable') {
            elements.trackingRoot.hidden = true;
            return;
        }
        elements.trackingLatest.textContent = formatNumber(tracking.latest_price);
        elements.trackingReturn.textContent = formatPct(tracking.return_pct);
        elements.trackingReturn.className = returnTone(tracking);
        elements.trackingGap.textContent = formatPct(tracking.target_12m_gap_pct);
        elements.trackingGap.className = pctTone(tracking.target_12m_gap_pct);
        elements.trackingSummary.textContent = tracking.summary || '已建立決策追蹤。';
        elements.trackingRoot.hidden = false;
    }

    function create(options) {
        const elements = options.elements || {};
        elements.trackingRoot = elements.trackingRoot || document.getElementById('preview-tracking');
        elements.trackingLatest = elements.trackingLatest || document.getElementById('preview-tracking-latest');
        elements.trackingReturn = elements.trackingReturn || document.getElementById('preview-tracking-return');
        elements.trackingGap = elements.trackingGap || document.getElementById('preview-tracking-gap');
        elements.trackingSummary = elements.trackingSummary || document.getElementById('preview-tracking-summary');

        function setPreviewOpen(open) {
            if (elements.workspace) elements.workspace.classList.toggle('has-preview', open);
        }

        function show(report) {
            if (!report || !elements.root) return false;
            const rec = report.recommendation || {};
            const pipelineId = report.pipeline_id || 'v1';

            elements.mode.innerHTML = `${options.renderPipelineModeBadge(pipelineId)}${options.renderDataTrustBadge(report.data_trust)}<span class="preview-date">${options.escapeHtml(report.date || '')}</span>`;
            configureRerunButtons(elements, pipelineId);
            elements.title.textContent = `${report.ticker} 投資建議`;
            elements.price.textContent = rec.current_price || 'N/A';
            elements.recommendation.textContent = options.normalizeRecommendation(rec.recommendation);
            elements.recommendation.className = options.recommendationTone(rec.recommendation);
            elements.confidence.textContent = rec.confidence || 'N/A';
            elements.target3m.textContent = rec.target_3m || 'N/A';
            elements.target6m.textContent = rec.target_6m || 'N/A';
            elements.target12m.textContent = rec.target_12m || 'N/A';
            elements.summary.textContent = rec.summary || '這份報告沒有可讀的一頁式摘要，可直接查看完整報告。';
            renderTracking(report.decision_tracking, elements);

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
