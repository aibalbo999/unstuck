(function () {
    function render(payload, escapeHtml) {
        const review = payload?.candidate_review;
        if (!review || review.schema_version !== 'daily_candidate_review.v1') return '';
        const e = value => escapeHtml(String(value ?? '未確認'));
        const candidates = payload.top_candidates || [], excluded = review.excluded_items || [];
        const row = item => {
            const evidence = item.evidence || {};
            const reasons = item.reasons || evidence.readable_reasons || [];
            const report = item.report_evidence;
            const reportText = report?.status === 'available' ? `<em>報告快照：行情 ${e(report.price_observation_date)}（${e(report.price_source)}）、法人 ${e(report.institutional_observation_date)}（${e(report.flow_source)}）；日期${report.latest_source_dates_aligned ? '對齊' : '未對齊'}。${e(report.reason)} 歷史價格調整基準：${e(report.price_adjustment_basis)}。</em>` : report ? `<em>${e(report.reason)}</em>` : '';
            const decision = report?.decision_explanation;
            const decisionText = decision ? `<em>${e(decision.direction_label)}；${e(decision.quality_label)}。${e((decision.reasons || []).map(r => r.message).join('；'))}</em>` : '';
            return `<div class="operator-action-row"><span><strong>${e(item.ticker)} · ${e(item.company_name || item.state || '研究待查')}</strong><em>${e(item.reason || reasons[0] || '證據待核對')}</em><em>篩選訊號：掃描 ${e(evidence.screen_date)} · 行情 ${e(evidence.price_observation_date)} · 法人 ${e(evidence.institutional_observation_date)} · 最近完成交易日 ${e(evidence.expected_completed_session)}</em>${reportText}${decisionText}<em>${e(reasons.join('；'))}</em></span></div>`;
        };
        const decisions = review.report_decision_summary || {};
        const checkedText = decisions.loaded_report_count ? `已讀取 ${decisions.loaded_report_count} 份對應報告；可保留觀察 ${decisions.research_observation_count} 份，原Long構想 ${decisions.direction_counts?.Long || 0} 份（不是交易核准）` : '對應報告方向與缺證尚未逐檔取得';
        const partition = review.partition || {};
        const maturity = review.performance_maturity_context || {};
        const waiting = maturity.partition?.awaiting_maturity;
        const maturityText = Number.isInteger(waiting) ? `全索引10日不重疊決策待成熟 ${waiting} 筆（截至 ${maturity.as_of || '未確認'}；不代表本頁候選）` : '全索引成熟度摘要未取得';
        return `<div class="operator-action-list-header"><strong>兩週研究名單 · 可執行候選尚未逐檔獨立判定</strong><span>取樣 ${e(review.returned_count)} 筆／${e(review.screener_total_if_reported)} 筆；顯示 ${e(candidates.length)} 筆，無校準上漲排名</span></div><p>${e(review.interpretation)} ${e(checkedText)}。${e(maturityText)}。品質阻擋 ${e(partition.quality_blocked || 0)}、保存漏斗拒絕 ${e(partition.saved_funnel_rejected || 0)}、顯示上限外 ${e(partition.outside_display_limit || 0)}。</p>${candidates.length ? candidates.map(row).join('') : '<p>本次沒有可顯示的研究候選。</p>'}<details><summary>本取樣排除或未顯示原因（${e(excluded.length)}筆）</summary>${excluded.map(row).join('')}</details>`;
    }
    window.StockAgentDailyCandidateReview = { render };
})();
