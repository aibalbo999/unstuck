(function () {
    const recorded = (report, key) => {
        const value = report?.[key];
        if (!value || typeof value !== 'object') return false;
        const signal = key === 'evidence_exit_gate' ? value.verdict : value.status;
        return String(signal || '').trim() !== '';
    };
    const structuredGapAction = report => { const evidence = window.StockAgentReportQualityEvidence?.context?.(report); return evidence?.hasStructuredGap ? { label: '結構化品質缺口', tone: 'critical', detail: evidence.detail } : null; }; function reportQualityGateAction(report, helpers = {}) {
        const conformance = report?.report_conformance || {};
        const gate = report?.evidence_exit_gate || {};
        const qualityKeys = ['report_conformance', 'evidence_exit_gate', 'content_credibility'];
        const persistedSnapshotVerified = report?.snapshot_integrity?.status === 'verified';
        const reportConformanceStatus = helpers.reportConformanceStatus
            || (item => String(item?.report_conformance?.status || ''));
        const evidenceExitGateVerdict = helpers.evidenceExitGateVerdict
            || (item => String(item?.evidence_exit_gate?.verdict || ''));
        const status = reportConformanceStatus(report);
        const verdict = evidenceExitGateVerdict(report);
        if (persistedSnapshotVerified && !qualityKeys.every(key => recorded(report, key))) {
            return structuredGapAction(report) || { label: '品質證據未記錄', tone: 'critical', detail: '報告缺少完整品質 gate 紀錄，採用前需人工查看。' };
        }
        if (status === 'blocked') {
            return { label: '報告符合性未通過', tone: 'critical', detail: conformance.summary || '報告未符合輸出契約，暫勿直接採用。' };
        }
        if (status === 'warning') {
            return { label: '報告符合性需確認', tone: 'warning', detail: conformance.summary || '報告符合主要契約，但仍需人工確認。' };
        }
        if (verdict === 'rejected') {
            return { label: '證據抽查未通過', tone: 'critical', detail: gate.summary || '報告數字未能對上資料快照，暫勿直接採用。' };
        }
        if (verdict === 'caution') {
            return { label: '數字證據需人工核對', tone: 'warning', detail: gate.summary || '部分報告數字需人工確認。' };
        }
        return null; }
    window.StockAgentReportQualityGatePolicy = { reportQualityGateAction };
})();
