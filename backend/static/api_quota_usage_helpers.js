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
        if (budget.available === false) return '本機每日用量暫時無法讀取';
        const scope = '（key slot 記錄；project 對應未驗證）';
        if (budget.enforced === false) {
            const observed = Object.entries(budget.models || {})
                .filter(([, value]) => count(value.observed_requests) !== null)
                .map(([model, value]) => `${model} ${value.observed_requests} 次`);
            return `供應商回饋決定每日額度是否耗盡；本機預算預留紀錄僅供觀測${scope}${observed.length ? '：' + observed.join('；') : ''}`;
        }
        const models = Object.entries(budget.models || {})
            .filter(([, value]) => count(value.remaining) !== null && count(value.total_slot_budget ?? value.total_budget) !== null)
            .map(([model, value]) => `${model} ${value.remaining}/${value.total_slot_budget ?? value.total_budget}`);
        return models.length ? `本機剩餘／每日 slot 總預算${scope}：${models.join('；')}` : '';
    }
    function observationLines(observation) {
        if (!observation) return [];
        if (observation.available === false) return ['執行觀測暫時無法讀取'];
        const totals = observation.totals || {}, quota = observation.quota || {};
        const parts = Object.entries(observation.model_request_events || {})
            .filter(([, value]) => count(value) !== null).map(([model, value]) => `${model} ${value} 次`);
        const lines = parts.length ? [`實際記錄的 Agent 請求：${parts.join('；')}`] : [];
        if (count(totals.local_preflight_events) !== null) lines.push(`本機提前拒絕／跳過 ${totals.local_preflight_events} 次事件（含歷史路由跳過）`);
        if (count(totals.sdk_callback_attempts) > 0) lines.push(`新增 SDK 呼叫觀測 ${totals.sdk_callback_attempts} 次；此為 SDK 入口計數，非 HTTP 送達收據`);
        if (count(quota.events) > 0) lines.push(`429 可分類比例 ${quota.classified_pct ?? '未知'}%；原因未知 ${quota.kinds?.unknown || 0} 次`);
        const cooldown = observation.cooldowns || {};
        if (count(cooldown.observed_incidents) > 0) lines.push(`有識別的冷卻 ${cooldown.observed_incidents} 輪，已恢復 ${cooldown.recovered_incidents || 0} 輪`);
        const quality = observation.quality || {};
        lines.push(Object.keys(quality).length ? `已記錄品質決策：通過 ${quality.gate_passed || 0}、擋下 ${quality.gate_blocked || 0}；通過不代表已發布` : '歷史品質決策未完整記錄，不能由任務完成推定品質通過');
        if (observation.evidence?.jobs_with_requests > 0) lines.push(`分批摘錄：${observation.evidence.jobs_with_requests} 個任務有請求，${observation.evidence.jobs_with_appendix || 0} 個有附錄採用，${observation.evidence.jobs_with_appendix_gate_passed || 0} 個有品質通過紀錄`);
        if (observation.sample_truncated) lines.push('目前為有界樣本，已達讀取上限；統計可能不完整');
        if (observation.telemetry_health?.dropped_events > 0) lines.push(`目前 API 程序有 ${observation.telemetry_health.dropped_events} 次觀測寫入缺口；其他 worker 須各自查核`);
        return lines;
    }
    window.StockAgentApiQuotaUsage = { usageLabel, errorCount, limitLabel, budgetLabel, observationLines };
})();
