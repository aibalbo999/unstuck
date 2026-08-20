(function () {
    const fieldLabels = { report_conformance: '報告一致性', evidence_exit_gate: '證據關卡', content_credibility: '內容可信度' };
    const limitation = 'artifact 摘要僅供人工核對，不代表 gate 已通過；採用前需人工查看。';
    const targetWarning = 'artifact 摘要僅供人工核對，不代表 gate 已通過';
    const labels = fields => (Array.isArray(fields) ? fields : []).map(field => fieldLabels[field] || field).filter(Boolean).join('、');
    function context(report) {
        const missingFields = Array.isArray(report?.missing_quality_fields) ? report.missing_quality_fields.filter(Boolean) : [];
        const artifact = report?.artifact_quality_summary && typeof report.artifact_quality_summary === 'object' ? report.artifact_quality_summary : {};
        const artifactFields = Array.isArray(artifact.fields) ? artifact.fields.filter(Boolean) : [];
        const missingFieldText = labels(missingFields), artifactFieldText = labels(artifactFields);
        const artifactText = artifact.status === 'present' && artifactFieldText ? `artifact 摘要可查：${artifactFieldText}` : artifact.status === 'not_found' ? 'artifact 未找到可查摘要' : artifact.status === 'unavailable' ? 'artifact 無法讀取' : 'artifact 摘要未記錄';
        const reasonCodes = Array.isArray(report?.reason_codes) ? report.reason_codes : [];
        const provenanceText = report?.quality_metadata_provenance === 'after_refresh' || reasonCodes.includes('quality_metadata_after_refresh') ? '來源：有刷新歸因' : report?.quality_metadata_provenance === 'no_refresh_provenance' ? '來源：未標記刷新來源' : '';
        const targetProvenance = provenanceText.replace('缺口', '');
        const targetContext = [missingFieldText ? `結構化缺口：${missingFieldText}` : '', targetProvenance, artifact.status ? artifactText : ''].filter(Boolean).join('；');
        const summary = [missingFieldText ? `結構化品質 metadata：${missingFieldText}` : '', provenanceText, artifactText].filter(Boolean).join('；');
        return { hasStructuredGap: missingFields.length > 0, missingFields, missingFieldText, artifactFields, artifactFieldText, artifactText, provenanceText, targetContext, summary, detail: missingFields.length ? `${summary}；${limitation}` : summary, limitation, targetWarning: missingFields.length ? targetWarning : '' };
    }
    function renderTargetContext(values, escapeHtml, classNames) {
        const e = escapeHtml || (value => String(value ?? '')), classes = { reviewStatus: 'quality-evidence-review-status', evidenceContext: 'quality-evidence-context', warning: 'quality-evidence-warning', ...(classNames || {}) };
        const parts = [['reviewStatus', values?.reviewStatus], ['evidenceContext', values?.evidenceContext], ['warning', values?.warning]].map(([key, value]) => [key, String(value || '').trim()]).filter(([, value]) => value);
        return { text: parts.map(([, value]) => value).join('；'), html: parts.map(([key, value]) => `<small class="${classes[key]}">${e(value)}</small>`).join('') };
    }
    window.StockAgentReportQualityEvidence = { context, fieldLabels, limitation, renderTargetContext };
})();
