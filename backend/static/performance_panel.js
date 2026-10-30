(function () {
    function fmtPct(value) {
        if (value === null || value === undefined || value === '') return 'N/A';
        const num = Number(value);
        return Number.isFinite(num) ? `${num.toFixed(2)}%` : 'N/A';
    }
    function fmtPrice(value) {
        if (value === null || value === undefined || value === '') return 'N/A';
        const num = Number(value);
        return Number.isFinite(num) ? num.toLocaleString('zh-TW', { maximumFractionDigits: 2 }) : 'N/A';
    }
    function sampleConfidenceLabel(scored) {
        const count = Number(scored || 0);
        if (!count) return '尚無已評分樣本';
        return count < 2 ? '樣本不足，僅供觀察' : '描述性樣本；未證明策略勝率';
    }
    function coverage(row, total, includeReasons = true) {
        const scored = row.scored_count ?? (Number(row.hit_count || 0) + Number(row.miss_count || 0));
        const cost = row.cost_coverage || {};
        const costLabel = ` · 已評分成本已記錄 ${cost.scored_cost_recorded ?? "未知"}、未知 ${cost.scored_cost_unknown ?? "未知"}`;
        const reasons = includeReasons ? Object.entries(row.unscored_reason_counts || {}).map(([reason, count]) => `${reason} ${count}`).join('、') : '';
        return `已評分 ${scored}/${total} · 未評分 ${row.unscored_count ?? Math.max(0, total - scored)} · ${sampleConfidenceLabel(scored)}${costLabel}${reasons ? ' · 原因：' + reasons : ''}`;
    }
    function tone(row) {
        if ((row.outcome || '') === 'hit') return 'ok';
        if (Number(row.strategy_roi_pct || 0) < 0) return 'critical';
        return 'warning';
    }
    function horizonLabel(row) {
        return row.horizon_trading_days ? `${row.horizon_trading_days} 交易日` : `${row.horizon_months || '?'}M`;
    }
    function statusLabel(row) {
        const labels = {target_first: '先達目標', stop_first: '先觸停損', horizon_exit: '期滿退出',
            not_entered: '未成交', no_trade: '不交易', ambiguous: '日內順序不明', insufficient_data: '資料不足', evidence_quarantined: '證據隔離'};
        return labels[row.status] || row.outcome || '未評分';
    }
    function populationScopeNotice(population) {
        if (population.status !== 'complete_index') return '';
        const days = population.denominator_semantics?.retention_days;
        const retention = !Number.isInteger(days) ? '保留期限未確認' : (days > 0 ? `保留 ${days} 天（依檔案更新時間；HTML 到期清理整組）` : '到期清理已停用');
        const change = Number.isInteger(days) && days > 0 ? '到期清理會縮小母體' : '母體隨索引與檔案變動';
        return ` · 母體：仍存索引的 ${population.report_count ?? '未確認'} 份台股 v4 報告；交易日基準 ${population.as_of || '未確認'}（台北）。${retention}；${change}。不是固定完整歷史研究母體；跨期變動不代表策略改善`;
    }
    function render(payload, options) {
        const escapeHtml = options.escapeHtml;
        const summary = payload?.summary || {};
        const horizons = payload?.by_horizon || [];
        const details = payload?.details || [];
        const trade = payload?.trade_summary || {};
        const population = payload?.population || {};
        const populationLabel = population.status === "complete_index" ? `台股v4現存索引預期 ${population.expected_slots} 筆 · 10日不重疊決策 ${population.independent_candidate_count} · 可比成本假設淨結果 ${population.comparable_assumed_cost_net_result_count || 0}` : "現存索引績效母體不可用";
        const period = trade.observation_window?.evaluation_dates || {};
        const periodLabel = period.start && period.end ? `${period.start} 至 ${period.end}` : "未記錄";
        const blockers = population.net_result_diagnostics?.primary_nonoverlapping_slots?.partition;
        const blockerLabel = blockers ? ` · 10日原始決策分區（共 ${population.independent_candidate_count}）：待成熟 ${blockers.awaiting_maturity || 0}、成交結果未驗證 ${blockers.executed_result_unverified || 0}、結果或計畫缺漏 ${blockers.missing_result_or_plan || 0}、無成交 ${blockers.no_executed_position || 0}、舊資料或契約未通過 ${blockers.stored_data_or_contract_failure || 0}、證據隔離 ${blockers.price_or_session_evidence_quarantined || 0}；缺少保存的證據不等於缺行情` : "";
        options.summaryEl.textContent = `月度研究：${coverage(summary, summary.total_predictions || 0, false)}｜交易計畫：${coverage(trade, trade.total_evaluations || 0, false)} · 觀察 ${Object.keys(payload?.trade_by_horizon || {}).join("、") || "未記錄"} 交易日 · 評估期間 ${periodLabel} · 毛價格結果，成本未完整驗證；未成熟報告可能尚未入表 · ${populationLabel}`;
        options.summaryEl.textContent += blockerLabel;
        options.summaryEl.textContent += populationScopeNotice(population);
        const quarantine = payload?.performance_evidence_quarantine;
        if (quarantine) options.summaryEl.textContent += ` · 全歷史價格／交易日證據隔離 ${quarantine.quarantined_count || 0} 筆；原毛結果留存，不列當前績效`;
        const revisions = payload?.legacy_evidence_revisions;
        if (revisions?.approved_scope_count) {
            const revisionStates = revisions.revision_state_counts || {};
            const waiting = Number.isInteger(revisions.awaiting_maturity_count) ? revisions.awaiting_maturity_count : '未確認';
            const unscored = Number.isInteger(revisions.mature_unscored_scope_count) ? revisions.mature_unscored_scope_count : '未確認';
            options.summaryEl.textContent += ` · 核准取證範圍 ${revisions.approved_scope_count} 筆：已完成 ${revisions.terminal_scope_count ?? '未確認'} 筆、待成熟 ${waiting} 筆、已到期待補證 ${unscored} 筆；追加 ${revisions.revisions || 0} 版（不交易 ${revisionStates.no_trade || 0} 版）；原件保留，版本未代換上列原始績效、未驗證策略`;
            if (Number.isInteger(revisions.unscored_disposition_scope_count)) {
                options.summaryEl.textContent += ` · 未評分處置 ${revisions.unscored_disposition_scope_count} 筆（非不交易、非輸贏）；證據日 ${revisions.as_of_evidence_session || '未確認'}（台北22:30界線，非來源最終性保證）`;
            }
        }
        const horizonHtml = horizons.map(row => `
            <span class="performance-chip is-${Number(row.total || 0) >= 10 ? 'ok' : 'warning'}">
                <strong>${escapeHtml(row.horizon_months)}M</strong>
                <em>描述性命中率 ${escapeHtml(fmtPct(Number(row.scored_count ?? row.total ?? 0) ? row.hit_rate_pct : null))} · ${escapeHtml(coverage(row, row.total || 0))}</em>
                <span>平均 ROI ${escapeHtml(fmtPct(Number(row.total ?? row.total_evaluations ?? 0) ? row.average_strategy_roi_pct : null))} · ${escapeHtml(row.total || 0)} 筆</span>
            </span>
        `).join('');
        const tradeHtml = Object.entries(payload?.trade_by_horizon || {}).map(([days, row]) => `
            <span class="performance-chip is-warning">
                <strong>${escapeHtml(days)} 交易日</strong>
                <em>描述性命中率 ${escapeHtml(fmtPct(row.descriptive_hit_ratio_pct ?? row.hit_rate_pct))} · ${escapeHtml(coverage(row, row.total_evaluations || 0))}</em>
                <span>毛 平均 ROI ${escapeHtml(fmtPct(Number(row.total ?? row.total_evaluations ?? 0) ? row.average_strategy_roi_pct : null))} · ${escapeHtml(row.total_evaluations || 0)} 筆</span>
            </span>
        `).join('');
        const detailHtml = details.slice(0, 8).map(row => `
            <span class="performance-chip recent-backtest is-${tone(row)}">
                <strong>${escapeHtml(row.ticker || 'N/A')} · ${escapeHtml(horizonLabel(row))}</strong>
                <em>${escapeHtml(statusLabel(row))} · 毛 ROI ${escapeHtml(fmtPct(row.strategy_roi_pct))}</em>
                <span>${escapeHtml(row.recommendation || '')} ${escapeHtml(fmtPrice(row.entry_price ?? row.initial_price))} → ${escapeHtml(fmtPrice(row.exit_price ?? row.actual_price))}</span>
            </span>
        `).join('');
        options.listEl.innerHTML = (horizonHtml + tradeHtml + detailHtml) || '<span class="performance-chip is-warning">尚無到期回測結果</span>';
    }
    window.StockAgentPerformancePanel = { render };
})();
