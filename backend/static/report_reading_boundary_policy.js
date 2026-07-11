(function () {
    const labels = {
        pending: '品質 gate 尚未記錄',
        warning: '品質 gate 有警示',
        blocked: '品質 gate 未通過',
        passed: '已通過已知檢查'
    };
    const details = {
        pending: '品質 gate 尚未完整記錄；先核對來源與限制，勿直接採用報告結論。',
        warning: '品質 gate 有警示；先查看資料與證據，再引用報告結論。',
        blocked: '品質 gate 未通過；先處理品質警示，暫勿直接採用報告結論。',
        passed: '已通過已知檢查，但不代表投資語意一定正確或未來結果有保證。'
    };
    const recorded = (report, key) => Object.prototype.hasOwnProperty.call(report || {}, key)
        && report[key] && typeof report[key] === 'object';

    function reportReadingBoundary(report) {
        const conformance = report?.report_conformance || {};
        const evidence = report?.evidence_exit_gate || {};
        const content = report?.content_credibility || {};
        const conformanceStatus = String(conformance.status || '');
        const evidenceStatus = String(evidence.verdict || '');
        const contentStatus = String(content.status || '');
        const qualityKeys = ['report_conformance', 'evidence_exit_gate', 'content_credibility'];
        let state = 'warning';
        if (['blocked', 'failed', 'rejected'].includes(conformanceStatus)
            || ['blocked', 'failed', 'rejected'].includes(evidenceStatus)
            || ['blocked', 'failed', 'rejected'].includes(contentStatus)) {
            state = 'blocked';
        } else if (!qualityKeys.some(key => recorded(report, key))) {
            state = 'pending';
        } else if (qualityKeys.every(key => recorded(report, key))
            && conformanceStatus === 'passed'
            && evidenceStatus === 'approved'
            && contentStatus === 'passed'
            && String(report?.data_trust?.status || 'unknown') === 'fresh') {
            state = 'passed';
        }
        return { state, label: labels[state], detail: details[state] };
    }

    window.StockAgentReportReadingBoundaryPolicy = { reportReadingBoundary };
})();
