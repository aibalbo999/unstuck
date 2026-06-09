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
            fresh: '本報告資料新鮮',
            partial: '本報告部分異常',
            stale: '本報告部分過期',
            error: '本報告來源異常',
            unknown: '本報告未記錄'
        };
        return labels[status] || labels.unknown;
    }
    function dataTrustClass(trust) {
        const status = trust && trust.status ? trust.status : 'unknown';
        return ['fresh', 'partial', 'stale', 'error'].includes(status) ? status : 'unknown';
    }
    function dataTrustReasonLabel(code) {
        const parts = String(code || '').split(':');
        const base = parts[0];
        const source = parts[1] || '';
        const labels = {
            fresh_core_sources: '核心資料新鮮',
            critical_sources_error: '核心來源異常',
            missing_usable_critical_data: '缺少核心資料',
            data_source_notes_present: '含口徑註記',
            provider_sla_critical: '系統來源當時不穩',
            provider_sla_warning_note: '來源穩定度提醒',
            missing_data_trust_snapshot: '未記錄報告資料狀態',
            source_error: '來源異常',
            source_stale: '來源過期'
        };
        const sourceLabels = { market_data: '市場資料', financial_statements: '年度財報', monthly_revenue: '月營收', institutional_trading: '法人籌碼', dynamic_peer_metrics: '同業指標', pe_river_chart: 'P/E 河流圖', recent_catalysts: '近期催化劑', peer_discovery: '同業搜尋' };
        return `${labels[base] || base}${source ? `：${sourceLabels[source] || source}` : ''}`;
    }

    function dataTrustReasonSummary(trust) {
        const codes = trust && Array.isArray(trust.reason_codes) ? trust.reason_codes : [];
        const reasons = codes.slice(0, 2).map(dataTrustReasonLabel);
        const scoreReasons = trust && Array.isArray(trust.score_reasons) ? trust.score_reasons : [];
        if (!reasons.length && scoreReasons.length) return scoreReasons.slice(0, 2).join('、');
        return reasons.join('、');
    }

    function dataTrustScoreLabel(trust) {
        const score = trust && Number(trust.score);
        if (!Number.isFinite(score)) return '';
        return `${Math.max(0, Math.min(100, Math.round(score)))}分`;
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
        const label = dataTrustLabel(trust);
        const score = dataTrustScoreLabel(trust);
        const text = score ? `${label} · ${score}` : label;
        return `<span class="data-trust-badge is-${dataTrustClass(trust)}" title="${escapeHtml(text)}">${escapeHtml(text)}</span>`;
    }

    function renderDataTrustReason(trust) {
        const summary = dataTrustReasonSummary(trust);
        return summary ? `<span class="data-trust-reason">${escapeHtml(summary)}</span>` : '';
    }

    window.StockAgentUi = {
        PIPELINE_META,
        pipelineMeta,
        pipelineModeClass,
        pipelineModeLabel,
        dataTrustLabel,
        dataTrustClass,
        dataTrustReasonSummary,
        dataTrustScoreLabel,
        normalizeRecommendation,
        recommendationTone,
        escapeHtml,
        renderPipelineModeBadge,
        renderDataTrustBadge,
        renderDataTrustReason
    };
})();
