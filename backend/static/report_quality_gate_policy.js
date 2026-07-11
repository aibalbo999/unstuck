(function () {
    function reportQualityGateAction(report, helpers = {}) {
        const conformance = report?.report_conformance || {};
        const gate = report?.evidence_exit_gate || {};
        const reportConformanceStatus = helpers.reportConformanceStatus
            || (item => String(item?.report_conformance?.status || ''));
        const evidenceExitGateVerdict = helpers.evidenceExitGateVerdict
            || (item => String(item?.evidence_exit_gate?.verdict || ''));
        const status = reportConformanceStatus(report);
        const verdict = evidenceExitGateVerdict(report);

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
        return null;
    }

    window.StockAgentReportQualityGatePolicy = { reportQualityGateAction };
})();
