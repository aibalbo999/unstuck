(function () {
    const copyById = {
        slow_route: {
            tone: 'warning', label: '模型回應較慢', state: '不代表分析失敗',
            impact: '影響：分析可能需要等比較久，但不代表報告內容錯誤。',
            action: '若任務最後有完成，現在不用處理；若持續卡住，再查看任務狀態。'
        },
        retry_storm: {
            tone: 'warning', label: '模型重試次數偏多', state: '系統正在重試',
            impact: '影響：分析可能變慢，系統會嘗試重新呼叫模型。',
            action: '若今日工作台沒有失敗任務，現在不用處理。'
        },
        quality_gate_failures: {
            tone: 'warning', label: '模型輸出曾被品質檢查擋下', state: '不合格輸出未採用',
            impact: '影響：該次模型輸出沒有直接成為正式報告，系統會重試或改用其他結果。',
            action: '若今日工作台沒有要求人工核對，現在不用處理。'
        },
        provider_quota_errors: {
            tone: 'warning', label: '模型額度或頻率曾受限', state: '系統會自動處理',
            impact: '影響：部分請求可能延後，或改用其他 key／模型；不等於整份報告失敗。',
            action: '若今日工作台沒有失敗任務，現在不用處理。'
        },
        provider_errors: {
            tone: 'warning', label: '模型供應商曾回傳錯誤', state: '系統會自動重試',
            impact: '影響：部分請求可能延後；不代表所有模型或所有報告都不可用。',
            action: '若今日工作台沒有失敗任務，現在不用處理。'
        },
        other: {
            tone: 'warning', label: '其他模型路由提醒', state: '需要查看',
            impact: '影響：最近執行紀錄中有尚未分類的模型路由事件。',
            action: '先查看技術明細；只有今日工作台同時顯示失敗任務時才需介入。'
        }
    };
    const displayOrder = ['provider_quota_errors', 'provider_errors', 'quality_gate_failures', 'retry_storm', 'slow_route', 'other'];

    function routeWarnings(payload) {
        return Array.isArray(payload?.model_route_budget?.warnings)
            ? payload.model_route_budget.warnings.filter(item => item && typeof item === 'object')
            : [];
    }
    function groupedRouteWarnings(warnings) {
        const groups = new Map();
        for (const warning of warnings) {
            const id = Object.hasOwn(copyById, String(warning.id)) ? String(warning.id) : 'other';
            if (!groups.has(id)) groups.set(id, []);
            groups.get(id).push(warning);
        }
        return displayOrder.filter(id => groups.has(id)).map(id => ({ id, warnings: groups.get(id) }));
    }
    function routeWarningMarkup(group, escapeHtml) {
        const copy = copyById[group.id], visible = group.warnings.slice(0, 8);
        const remaining = group.warnings.length - visible.length;
        const rows = visible.map(warning => `<li><strong>${escapeHtml(warning.route || 'unknown')}</strong><span>${escapeHtml(warning.message || '尚無詳細訊息')}</span></li>`).join('');
        return `<article class="provider-sla-chip provider-sla-insight provider-sla-route-group is-${copy.tone}"><span class="provider-sla-insight-top"><strong>${escapeHtml(copy.label)}</strong><em>${escapeHtml(copy.state)}</em></span><span class="provider-sla-detail">${escapeHtml(copy.impact)}</span><span class="provider-sla-meta">涉及 ${escapeHtml(group.warnings.length)} 條路由 · 最近執行紀錄</span><span class="provider-sla-detail"><strong>現在怎麼做：</strong>${escapeHtml(copy.action)}</span><details class="provider-sla-technical"><summary>技術明細（${escapeHtml(group.warnings.length)} 條路由）</summary><ul>${rows}${remaining > 0 ? `<li>另有 ${escapeHtml(remaining)} 條路由未展開</li>` : ''}</ul></details></article>`;
    }
    function serviceIssueText(service) {
        const today = service?.usage?.quota_day_profile?.today;
        if (today) {
            const quota = Number(today.provider_quota_errors || 0) + Number(today.unclassified_quota_errors || 0);
            const other = Number(today.other_errors || 0), parts = [];
            if (quota) parts.push(`${quota} 次額度或頻率事件`);
            if (other) parts.push(`${other} 次其他請求異常`);
            return parts.length
                ? `目前配額日記錄 ${parts.join('、')}；這是請求事件，不等於同樣數量的報告失敗。`
                : '目前配額日尚未記錄模型請求異常。';
        }
        const usage = service?.usage || {};
        const errors = window.StockAgentApiQuotaUsage?.errorCount(usage) ?? Number(usage.observed_quota_errors_since_reset || usage.observed_24h_errors || 0);
        return errors ? `本機記錄到 ${errors} 次請求事件；不等於同樣數量的報告失敗。` : '本機尚未記錄模型請求異常。';
    }
    function summaryText(payload, services, errors, warnings, groups) {
        const configured = services.filter(service => service.configured).length;
        const sampleSize = Number(payload?.model_route_budget?.summary?.sample_size);
        const observations = groups.length
            ? `最近 ${Number.isFinite(sampleSize) ? sampleSize : '一批'} 筆執行紀錄整理出 ${groups.length} 類提醒（涉及 ${warnings.length} 條路由紀錄）`
            : '';
        const requests = errors ? `目前配額日 ${errors} 次請求事件需留意；不等於 ${errors} 份報告失敗` : '';
        if (services.length) return `LLM/API：${configured}/${services.length} 組服務已設定${requests ? `；${requests}` : ''}${observations ? `；${observations}` : ''}`;
        return observations ? `LLM/API：${observations}` : 'LLM/API 本機觀測尚無資料';
    }

    window.StockAgentApiQuotaObservations = { groupedRouteWarnings, routeWarningMarkup, routeWarnings, serviceIssueText, summaryText };
})();
