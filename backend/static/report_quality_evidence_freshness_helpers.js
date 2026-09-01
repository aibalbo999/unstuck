(function () {
    const freshnessLabels = { current: '本文目前版本', needs_rerun: '資料已更新、本文需完整重跑', unknown: 'freshness 未判定' };
    const reasonLabels = { analysis_metadata_not_evidence: '分析欄位不是證據', confidence_metadata_not_evidence: '信心欄位不是證據', legacy_conclusion_without_snapshot_path: '舊結論缺少快照路徑', missing_semantic_path: '缺少語意路徑', no_matching_snapshot_path: '找不到同路徑快照', news_source_not_canonical: '新聞來源非 canonical', research_source_not_canonical: '研究來源非 canonical', derived_metric_not_canonical: '衍生指標沒有 canonical 欄位', risk_control_not_canonical: '風險控制沒有 canonical 欄位', scenario_target_not_canonical: '情境目標沒有 canonical 欄位', technical_level_not_canonical: '技術價位沒有 canonical 欄位', snapshot_field_unavailable: '快照欄位不可用', snapshot_value_mismatch: '快照數值不一致' };
    const freshnessOrder = { needs_rerun: 0, current: 1, unknown: 2 };

    function reasonEntries(counts) {
        return counts && typeof counts === 'object' && !Array.isArray(counts)
            ? Object.entries(counts).map(([key, value]) => [String(key || '').trim(), Number(value)]).filter(([key, value]) => key && Number.isFinite(value) && value > 0).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
            : [];
    }

    function formatUnverifiableReasonFreshnessSummary(groups, reports) {
        const entries = groups && typeof groups === 'object' && !Array.isArray(groups)
            ? Object.entries(groups).map(([key, value]) => [String(key || '').trim().toLowerCase(), value]).filter(([key, value]) => freshnessLabels[key] && value && typeof value === 'object' && !Array.isArray(value)).sort((a, b) => (freshnessOrder[a[0]] ?? 9) - (freshnessOrder[b[0]] ?? 9))
            : [];
        const parts = entries.map(([key, counts]) => {
            const reasons = reasonEntries(counts);
            const reportCount = Number(reports?.[key]);
            const reportSummary = Number.isFinite(reportCount) && reportCount >= 0 ? `；涉及 ${Math.floor(reportCount)} 份報告` : '';
            return reasons.length ? `${freshnessLabels[key]}（${reasons.map(([reason, count]) => `${reasonLabels[reason] || reason} ${Math.floor(count)}`).join('、')}${reportSummary}）` : '';
        }).filter(Boolean);
        return parts.length ? `證據未驗證版本：${parts.join('、')}` : '';
    }

    function formatUnverifiableReasonFreshnessStatus(status, counts) {
        const key = String(status || '').trim().toLowerCase();
        return freshnessLabels[key] && reasonEntries(counts).length ? freshnessLabels[key] : '';
    }

    window.StockAgentReportQualityEvidence = {
        ...(window.StockAgentReportQualityEvidence || {}),
        formatUnverifiableReasonFreshnessSummary,
        formatUnverifiableReasonFreshnessStatus,
    };
})();
