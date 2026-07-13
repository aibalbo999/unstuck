(function () {
    const labels = {
        pending: '品質 gate 尚未記錄',
        warning: '品質 gate 有警示',
        blocked: '品質 gate 未通過',
        passed: '已通過已知檢查'
    };
    const details = {
        pending: '品質 gate 尚未完整記錄；先核對來源與限制，勿直接採用報告結論。',
        warning: '品質 gate 有警示；先核對來源、快照與證據，再引用報告結論。',
        blocked: '品質 gate 未通過；先處理品質警示，暫勿直接採用報告結論。',
        passed: '已通過已知檢查，但不代表投資語意一定正確或未來結果有保證。'
    };
    const genericSnapshotIntegrityErrors = new Set([
        '資料快照完整性未通過，不能直接引用報告結論。'
    ]);
    const recorded = (report, key) => Object.prototype.hasOwnProperty.call(report || {}, key)
        && report[key] && typeof report[key] === 'object';

    function safeText(value) {
        try {
            return String(value ?? '').trim();
        } catch (_error) {
            return '';
        }
    }

    function snapshotIntegrityDetail(snapshotIntegrity) {
        const errors = snapshotIntegrity?.errors;
        const values = Array.isArray(errors) ? errors : [errors];
        const details = uniqueTexts(values.map(safeText).filter(Boolean));
        const hashMismatchDetail = snapshotIntegrityHashMismatchDetail(snapshotIntegrity);
        if (!details.length && hashMismatchDetail) {
            return hashMismatchDetail;
        }
        const specificDetails = details.filter(detail => !genericSnapshotIntegrityErrors.has(detail));
        if (!specificDetails.length && hashMismatchDetail) {
            return hashMismatchDetail;
        }
        return (specificDetails.length ? specificDetails : details).join('；');
    }

    function snapshotIntegrityHashMismatchDetail(snapshotIntegrity) {
        const hashValue = safeText(snapshotIntegrity?.hash);
        const expectedHash = safeText(snapshotIntegrity?.expected_hash);
        if (hashValue && expectedHash && hashValue !== expectedHash) {
            return 'snapshot_hash mismatch';
        }
        return '';
    }

    function uniqueTexts(values) {
        const seen = new Set();
        return values.filter(value => {
            if (seen.has(value)) {
                return false;
            }
            seen.add(value);
            return true;
        });
    }

    function snapshotIntegrityInvalid(snapshotIntegrity) {
        return String(snapshotIntegrity?.status || '') === 'invalid'
            || snapshotIntegrity?.valid === false;
    }

    function reportReadingBoundary(report) {
        const conformance = report?.report_conformance || {};
        const evidence = report?.evidence_exit_gate || {};
        const content = report?.content_credibility || {};
        const snapshotIntegrity = report?.snapshot_integrity || {};
        const conformanceStatus = String(conformance.status || '');
        const evidenceStatus = String(evidence.verdict || '');
        const contentStatus = String(content.status || '');
        const snapshotIntegrityStatus = String(snapshotIntegrity.status || '');
        const qualityKeys = ['report_conformance', 'evidence_exit_gate', 'content_credibility'];
        let state = 'warning';
        if (['blocked', 'failed', 'rejected'].includes(conformanceStatus)
            || ['blocked', 'failed', 'rejected'].includes(evidenceStatus)
            || ['blocked', 'failed', 'rejected'].includes(contentStatus)
            || snapshotIntegrityInvalid(snapshotIntegrity)) {
            state = 'blocked';
        } else if (!qualityKeys.some(key => recorded(report, key))) {
            state = 'pending';
        } else if (qualityKeys.every(key => recorded(report, key))
            && conformanceStatus === 'passed'
            && evidenceStatus === 'approved'
            && contentStatus === 'passed'
            && String(report?.data_trust?.status || 'unknown') === 'fresh'
            && (!recorded(report, 'snapshot_integrity') || snapshotIntegrityStatus === 'verified')) {
            state = 'passed';
        }
        let detail = details[state];
        if (snapshotIntegrityInvalid(snapshotIntegrity)) {
            const integrityDetail = snapshotIntegrityDetail(snapshotIntegrity);
            if (integrityDetail) {
                detail = `${detail} ${integrityDetail}`;
            }
        }
        return { state, label: labels[state], detail };
    }

    window.StockAgentReportReadingBoundaryPolicy = { reportReadingBoundary };
})();
