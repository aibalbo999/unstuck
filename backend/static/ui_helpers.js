(function () {
    const PIPELINE_META = {
        v1: { label: '模式 A：學術深度派', shortLabel: '學術深度派', reportSuffix: '深度分析報告', hint: '請稍候，10 個 AI 分析模組正在為您撰寫深度研報...' },
        v2: { label: '模式 B：實戰交易派', shortLabel: '實戰交易派', reportSuffix: '實戰交易決策報告', hint: '請稍候，8 個 AI 分析模組正在整合總經、籌碼與進出場策略...' },
        v3: { label: '模式 C：逆勢交易與泡沫狙擊', shortLabel: '逆勢泡沫狙擊', reportSuffix: '泡沫狙擊研究報告', hint: '請稍候，5 個 AI 逆勢分析模組正在檢驗題材泡沫、財務漏洞與做空觸發條件...' },
        v4: { label: '模式 D：極短線波段與事件驅動', shortLabel: '短線波段派', reportSuffix: '極短線交易策略報告', hint: '請稍候，AI 動能分析師正在比對技術突破點、籌碼集中度與近期事件催化劑...' },
        both: { label: '連續模式：模式 A → 模式 B → 模式 C', shortLabel: 'A+B+C 連續', reportSuffix: '三模式分析完成', hint: '將依序執行學術深度派、實戰交易派與逆勢泡沫狙擊；完成後會產出三份獨立報告。' }
    };
    function pipelineMeta(pipelineId) {
        return PIPELINE_META[pipelineId] || PIPELINE_META.v1;
    }
    function pipelineModeClass(pipelineId) {
        if (pipelineId === 'both') return 'is-both';
        if (pipelineId === 'v4') return 'is-v4';
        if (pipelineId === 'v3') return 'is-v3';
        return pipelineId === 'v2' ? 'is-v2' : 'is-v1';
    }
    function pipelineModeLabel(pipelineId) {
        if (pipelineId === 'both') return '連續 A+B+C · 三份報告';
        if (pipelineId === 'v4') return '模式 D · 短線波段派';
        if (pipelineId === 'v3') return '模式 C · 逆勢泡沫狙擊';
        return pipelineId === 'v2' ? '模式 B · 實戰交易派' : '模式 A · 學術深度派';
    }
    function providerSlaOnlyPartial(trust) {
        const codes = trust && Array.isArray(trust.reason_codes) ? trust.reason_codes : [], stale = trust && Array.isArray(trust.stale_sources) ? trust.stale_sources.filter(Boolean) : [], failures = trust && Array.isArray(trust.critical_failures) ? trust.critical_failures.filter(Boolean) : [];
        return trust?.status === 'partial' && codes.includes('provider_sla_critical') && !stale.length && !failures.length;
    }
    function dataTrustLabel(trust) {
        const status = trust && trust.status ? trust.status : 'unknown';
        const labels = {
            fresh: '本報告資料新鮮',
            partial: providerSlaOnlyPartial(trust) ? '本報告來源提醒' : '本報告資料需留意',
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
        if (text.includes('強烈放空')) return '強烈放空';
        if (text.includes('買進')) return '買進';
        if (text.includes('買入')) return '買入';
        if (text.includes('避免') || text.includes('賣出') || text.includes('放空')) return '避免';
        if (text.includes('持有')) return '持有';
        return text;
    }
    function recommendationTone(value) {
        const text = normalizeRecommendation(value);
        if (text === '買入' || text === '買進') return 'is-buy';
        if (text === '避免' || text === '強烈放空') return 'is-avoid';
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
        providerSlaOnlyPartial,
        renderPipelineModeBadge,
        renderDataTrustBadge,
        renderDataTrustReason
    };
})();
