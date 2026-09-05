(function () {
    function count(value) {
        return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
    }
    function usageLabel(usage) {
        const daily = usage?.daily_profile, quotaDay = usage?.quota_day_profile?.today;
        if (!daily?.today || !quotaDay) return '';
        const parts = [], complete = daily.complete_days || {};
        if (count(daily.today.requests) !== null) parts.push(`台北今日 ${daily.today.requests} 次`);
        if (count(complete.average_requests) !== null) parts.push(`近 ${complete.count} 個完整日，日均 ${complete.average_requests} 次、最高 ${complete.peak_requests} 次`);
        if (count(quotaDay.requests) !== null) parts.push(`Pacific 配額日請求紀錄 ${quotaDay.requests} 次`);
        for (const [field, label] of [['provider_quota_errors', '供應商配額錯誤'], ['local_blocks', '本機攔截'], ['other_errors', '其他錯誤'], ['unclassified_quota_errors', '待分類配額事件']]) {
            if (count(quotaDay[field]) > 0) parts.push(`${label} ${quotaDay[field]} 次`);
        }
        const input = daily.today.input_tokens;
        if (input?.total !== null && count(input?.total) !== null) parts.push(`已記錄輸入 ${input.total} tokens（回應用量覆蓋 ${input.coverage_pct}%）`);
        return parts.join(' · ');
    }
    function errorCount(usage) {
        const today = usage?.quota_day_profile?.today;
        return today ? (today.provider_quota_errors || 0) + (today.other_errors || 0) + (today.unclassified_quota_errors || 0) : null;
    }
    function limitLabel(limit) {
        if (count(limit) > 0) return String(limit);
        if (!limit || typeof limit !== 'object') return '未確認';
        return Object.entries(limit).filter(([, value]) => count(value) > 0)
            .map(([key, value]) => `${key.replaceAll('_', ' ')} ${value}`).join(' · ') || '未確認';
    }
    function budgetLabel(budget) {
        if (!budget) return '';
        if (budget.available === false) return '本機每日預算暫時無法讀取，請求已暫停';
        const models = Object.entries(budget.models || {})
            .filter(([, value]) => count(value.remaining) !== null && count(value.total_budget) !== null)
            .map(([model, value]) => `${model} ${value.remaining}/${value.total_budget}`);
        return models.length ? `本機剩餘／每日總預算：${models.join('；')}` : '';
    }
    window.StockAgentApiQuotaUsage = { usageLabel, errorCount, limitLabel, budgetLabel };
})();
