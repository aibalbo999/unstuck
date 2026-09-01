(function () {
    const fieldLabels = { report_conformance: '報告一致性', evidence_exit_gate: '證據關卡', content_credibility: '內容可信度' };
    const limitation = 'artifact 摘要僅供人工核對，不代表 gate 已通過；採用前需人工查看。';
    const targetWarning = 'artifact 摘要僅供人工核對，不代表 gate 已通過';
    const rerunContextLabels = {
        present: '局部重跑上下文：snapshot 可用',
        partial: '局部重跑上下文：snapshot 上下文不完整',
        missing: '局部重跑上下文：snapshot 無可用上下文',
        artifact_fallback_available: '局部重跑上下文：artifact 有完整前序段落（只代表上下文可查）'
    };
    const rerunExecutionLabels = {
        full_rerun_required: '重跑策略：目前資料 freshness 要求完整重跑',
        partial_rerun_available: '重跑策略：可嘗試只重跑最終建議',
        partial_rerun_review_required: '重跑策略：需先確認前序上下文完整性',
        partial_rerun_unavailable: '重跑策略：目前沒有可用的局部重跑上下文'
    };
    const reportVersionLabels = { current: '版本：目前版本（ticker/pipeline 最新）', historical: '版本：歷史版本（非目前最新）', unknown: '版本：新舊未判定' };
    const verificationReasonLabels = { analysis_metadata_not_evidence: '分析欄位不是證據', confidence_metadata_not_evidence: '信心欄位不是證據', legacy_conclusion_without_snapshot_path: '舊結論缺少快照路徑', missing_semantic_path: '缺少語意路徑', no_matching_snapshot_path: '找不到同路徑快照', news_source_not_canonical: '新聞來源非 canonical', research_source_not_canonical: '研究來源非 canonical', derived_metric_not_canonical: '衍生指標沒有 canonical 欄位', risk_control_not_canonical: '風險控制沒有 canonical 欄位', scenario_target_not_canonical: '情境目標沒有 canonical 欄位', technical_level_not_canonical: '技術價位沒有 canonical 欄位', snapshot_field_unavailable: '快照欄位不可用', snapshot_value_mismatch: '快照數值不一致' }, evidenceMismatchFreshnessLabels = { current: '本文目前版本', needs_rerun: '資料已更新、本文需完整重跑', unknown: 'freshness 未判定' }, labels = fields => (Array.isArray(fields) ? fields : []).map(field => fieldLabels[field] || field).filter(Boolean).join('、');
    function context(report) {
        const missingFields = Array.isArray(report?.missing_quality_fields) ? report.missing_quality_fields.filter(Boolean) : [];
        const artifact = report?.artifact_quality_summary && typeof report.artifact_quality_summary === 'object' ? report.artifact_quality_summary : {};
        const artifactFields = Array.isArray(artifact.fields) ? artifact.fields.filter(Boolean) : [];
        const missingFieldText = labels(missingFields), artifactFieldText = labels(artifactFields);
        const artifactText = artifact.status === 'present' && artifactFieldText ? `artifact 摘要可查：${artifactFieldText}` : artifact.status === 'not_found' ? 'artifact 未找到可查摘要' : artifact.status === 'unavailable' ? 'artifact 無法讀取' : 'artifact 摘要未記錄';
        const reasonCodes = Array.isArray(report?.reason_codes) ? report.reason_codes : [];
        const provenanceText = report?.quality_metadata_provenance === 'before_refresh' || reasonCodes.includes('quality_metadata_before_refresh') ? '來源：刷新前已有缺口' : report?.quality_metadata_provenance === 'after_refresh' || reasonCodes.includes('quality_metadata_after_refresh') ? '來源：有刷新歸因' : report?.quality_metadata_provenance === 'no_refresh_provenance' ? '來源：未標記刷新來源' : '';
        const targetProvenance = provenanceText;
        const rerunContextStatus = String(report?.rerun_context_status || '').trim().toLowerCase();
        const rerunContextText = rerunContextLabels[rerunContextStatus] || '';
        const rerunExecutionStatus = String(report?.rerun_execution_status || '').trim().toLowerCase();
        const rerunExecutionText = rerunExecutionLabels[rerunExecutionStatus] || '';
        const reportVersionStatus = String(report?.report_version_status || '').trim().toLowerCase();
        const reportVersionText = reportVersionLabels[reportVersionStatus] || '';
        const targetContext = [missingFieldText ? `結構化缺口：${missingFieldText}` : '', targetProvenance, artifact.status ? artifactText : '', reportVersionText, rerunContextText, rerunExecutionText].filter(Boolean).join('；');
        const summary = [missingFieldText ? `結構化品質 metadata：${missingFieldText}` : '', provenanceText, artifactText, reportVersionText, rerunContextText, rerunExecutionText].filter(Boolean).join('；');
        return { hasStructuredGap: missingFields.length > 0, missingFields, missingFieldText, artifactFields, artifactFieldText, artifactText, provenanceText, reportVersionStatus, reportVersionText, rerunContextStatus, rerunContextText, rerunExecutionStatus, rerunExecutionText, targetContext, summary, detail: missingFields.length ? `${summary}；${limitation}` : summary, limitation, targetWarning: missingFields.length ? targetWarning : '' };
    }
    function renderTargetContext(values, escapeHtml, classNames) {
        const e = escapeHtml || (value => String(value ?? '')), classes = { reviewStatus: 'quality-evidence-review-status', evidenceContext: 'quality-evidence-context', warning: 'quality-evidence-warning', ...(classNames || {}) };
        const parts = [['reviewStatus', values?.reviewStatus], ['evidenceContext', values?.evidenceContext], ['warning', values?.warning]].map(([key, value]) => [key, String(value || '').trim()]).filter(([, value]) => value);
        return { text: parts.map(([, value]) => value).join('；'), html: parts.map(([key, value]) => `<small class="${classes[key]}">${e(value)}</small>`).join('') };
    } function formatUnverifiableReasonSummary(counts) { const entries = counts && typeof counts === 'object' && !Array.isArray(counts) ? Object.entries(counts).map(([key, value]) => [String(key || '').trim(), Number(value)]).filter(([key, value]) => key && Number.isFinite(value) && value > 0).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])) : []; return entries.length ? `證據未驗證原因：${entries.map(([key, value]) => `${verificationReasonLabels[key] || key} ${Math.floor(value)}`).join('、')}` : ''; } function formatEvidenceMismatchFreshnessSummary(claims, reports) { const claimEntries = claims && typeof claims === 'object' && !Array.isArray(claims) ? Object.entries(claims).map(([key, value]) => [String(key || '').trim(), Number(value), Number(reports?.[key])]).filter(([key, value]) => key && Number.isFinite(value) && value > 0).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])) : []; return claimEntries.length ? `數值不一致分布：${claimEntries.map(([key, value, reportCount]) => `${evidenceMismatchFreshnessLabels[key] || key} ${Math.floor(value)} 筆${Number.isFinite(reportCount) && reportCount > 0 ? `／${Math.floor(reportCount)} 份` : ''}`).join('、')}` : ''; } function formatEvidenceMismatchFreshness(status, count) { const value = Number(count), key = String(status || '').trim().toLowerCase(); return evidenceMismatchFreshnessLabels[key] && Number.isFinite(value) && value > 0 ? `數值不一致來源：${evidenceMismatchFreshnessLabels[key]} ${Math.floor(value)} 筆` : ''; }
    window.StockAgentReportQualityEvidence = { context, fieldLabels, limitation, renderTargetContext, formatUnverifiableReasonSummary, formatEvidenceMismatchFreshnessSummary, formatEvidenceMismatchFreshness };
})();
