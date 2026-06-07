(function () {
    const PIPELINE_META = {
        v1: {
            label: '模式 A：學術深度派',
            shortLabel: '學術深度派',
            reportSuffix: '深度分析報告',
            hint: '請稍候，7 位 AI 分析師正在為您撰寫深度研報...'
        },
        v2: {
            label: '模式 B：實戰交易派',
            shortLabel: '實戰交易派',
            reportSuffix: '實戰交易決策報告',
            hint: '請稍候，6 位 AI 分析師正在整合總經、籌碼與進出場策略...'
        },
        both: {
            label: '連續模式：模式 A → 模式 B',
            shortLabel: 'A+B 連續',
            reportSuffix: '雙模式分析完成',
            hint: '將先執行學術深度派，再接續實戰交易派；完成後會產出兩份獨立報告。'
        }
    };

    function pipelineMeta(pipelineId) {
        return PIPELINE_META[pipelineId] || PIPELINE_META.v1;
    }

    function pipelineModeClass(pipelineId) {
        if (pipelineId === 'both') return 'is-both';
        return pipelineId === 'v2' ? 'is-v2' : 'is-v1';
    }

    function pipelineModeLabel(pipelineId) {
        if (pipelineId === 'both') return '連續 A+B · 兩份報告';
        return pipelineId === 'v2' ? '模式 B · 實戰交易派' : '模式 A · 學術深度派';
    }

    function dataTrustLabel(trust) {
        const status = trust && trust.status ? trust.status : 'unknown';
        const labels = {
            fresh: '資料新鮮',
            partial: '部分異常',
            stale: '部分過期',
            error: '來源異常',
            unknown: '未記錄'
        };
        return labels[status] || labels.unknown;
    }

    function dataTrustClass(trust) {
        const status = trust && trust.status ? trust.status : 'unknown';
        return ['fresh', 'partial', 'stale', 'error'].includes(status) ? status : 'unknown';
    }

    function normalizeRecommendation(value) {
        const text = String(value || 'N/A');
        if (text.includes('買入')) return '買入';
        if (text.includes('避免') || text.includes('賣出')) return '避免';
        if (text.includes('持有')) return '持有';
        return text;
    }

    function recommendationTone(value) {
        const text = normalizeRecommendation(value);
        if (text === '買入') return 'is-buy';
        if (text === '避免') return 'is-avoid';
        return 'is-hold';
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[char]));
    }

    function renderPipelineModeBadge(pipelineId) {
        return `<span class="history-mode ${pipelineModeClass(pipelineId)}">${escapeHtml(pipelineModeLabel(pipelineId))}</span>`;
    }

    function renderDataTrustBadge(trust) {
        return `<span class="data-trust-badge is-${dataTrustClass(trust)}">${escapeHtml(dataTrustLabel(trust))}</span>`;
    }

    window.StockAgentUi = {
        PIPELINE_META,
        pipelineMeta,
        pipelineModeClass,
        pipelineModeLabel,
        dataTrustLabel,
        dataTrustClass,
        normalizeRecommendation,
        recommendationTone,
        escapeHtml,
        renderPipelineModeBadge,
        renderDataTrustBadge
    };
})();
