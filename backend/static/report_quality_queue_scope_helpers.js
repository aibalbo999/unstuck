(function () {
    function boundedItemsLabel(label, total, returned, truncated) {
        const prefix = String(label || '').trim();
        const valid = prefix && [total, returned].every(number => Number.isInteger(number) && number >= 0) && returned <= total;
        if (!valid) return '';
        const consistent = typeof truncated === 'boolean' && truncated === (returned < total);
        return consistent ? (returned < total ? `${prefix}（顯示 ${returned}/${total}）` : `${prefix}（${total}）`) : `${prefix}（顯示 ${returned}/${total}；範圍資料需確認）`;
    }

    function boundedRepairQueueScope(summary) {
        const value = summary && typeof summary === 'object' && !Array.isArray(summary) ? summary : {};
        const required = value.action_required, limit = value.items_limit, returned = value.items_returned;
        const valid = [required, limit, returned].every(number => Number.isInteger(number) && number >= 0) && returned <= required && returned <= limit && typeof value.items_truncated === 'boolean' && value.items_truncated === (returned < required);
        return valid && returned < required ? `修復 queue：顯示 ${returned} / 共 ${required}` : '';
    }

    window.StockAgentReportQualityQueueScope = { boundedItemsLabel, boundedRepairQueueScope };
})();
