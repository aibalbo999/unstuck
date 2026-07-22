(function () {
    const labels = { pending: '品質 gate 尚未記錄', warning: '品質 gate 有警示', blocked: '品質 gate 未通過', passed: '已通過已知檢查' };
    const details = { pending: '品質 gate 尚未完整記錄；先核對來源與限制，勿直接採用報告結論。', warning: '品質 gate 有警示；先核對來源、快照與證據，再引用報告結論。', blocked: '品質 gate 未通過；先處理品質警示，暫勿直接採用報告結論。', passed: '已通過已知檢查，但不代表投資語意一定正確或未來結果有保證。' };
    const genericSnapshotErrors = new Set(['資料快照完整性未通過，不能直接引用報告結論。']);
    const qualityKeys = ['report_conformance', 'evidence_exit_gate', 'content_credibility'];
    const recorded = (report, key) => Object.prototype.hasOwnProperty.call(report || {}, key)
        && report[key] && typeof report[key] === 'object';
    const safeText = value => {
        try {
            return String(value ?? '').trim();
        } catch (_error) {
            return '';
        }
    };
    const uniqueTexts = values => {
        const seen = new Set();
        return values.filter(value => !seen.has(value) && seen.add(value));
    };
    const snapshotIntegrityInvalid = snapshot => String(snapshot?.status || '') === 'invalid'
        || snapshot?.valid === false;
    const hashMismatchDetail = snapshot => {
        const hashValue = safeText(snapshot?.hash);
        const expectedHash = safeText(snapshot?.expected_hash);
        return hashValue && expectedHash && hashValue !== expectedHash ? 'snapshot_hash mismatch' : '';
    };
    const snapshotIntegrityDetail = snapshot => {
        const values = Array.isArray(snapshot?.errors) ? snapshot.errors : [snapshot?.errors];
        const errorDetails = uniqueTexts(values.map(safeText).filter(Boolean));
        const mismatch = hashMismatchDetail(snapshot);
        const specific = errorDetails.filter(detail => !genericSnapshotErrors.has(detail));
        return (specific.length ? specific : (mismatch ? [mismatch] : errorDetails)).join('；');
    };

    function reportReadingBoundary(report) {
        const conformance = report?.report_conformance || {};
        const evidence = report?.evidence_exit_gate || {};
        const content = report?.content_credibility || {};
        const snapshot = report?.snapshot_integrity || {};
        const blockedStatuses = ['blocked', 'failed', 'rejected'];
        let state = 'warning';
        if (blockedStatuses.includes(String(conformance.status || ''))
            || blockedStatuses.includes(String(evidence.verdict || ''))
            || blockedStatuses.includes(String(content.status || ''))
            || snapshotIntegrityInvalid(snapshot)) state = 'blocked';
        else if (!qualityKeys.some(key => recorded(report, key))) state = 'pending';
        else if (qualityKeys.every(key => recorded(report, key))
            && String(conformance.status || '') === 'passed'
            && String(evidence.verdict || '') === 'approved'
            && String(content.status || '') === 'passed'
            && String(report?.data_trust?.status || 'unknown') === 'fresh'
            && (!recorded(report, 'snapshot_integrity') || String(snapshot.status || '') === 'verified')) state = 'passed';
        const integrityDetail = snapshotIntegrityInvalid(snapshot) ? snapshotIntegrityDetail(snapshot) : '';
        return { state, label: labels[state], detail: `${details[state]} ${integrityDetail}`.trim() };
    }

    window.StockAgentReportReadingBoundaryPolicy = { reportReadingBoundary };
})();
