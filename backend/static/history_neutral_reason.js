(function () {
    const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    function render(report, escapeHtml = escape, options = {}) {
        if (report?.pipeline_id !== 'v4') return '';
        const reason = report.neutral_explanation || {};
        const age = report.analysis_age || {};
        const days = Number.isInteger(age.age_calendar_days) && age.age_calendar_days >= 0 ? age.age_calendar_days : null;
        const ageText = days === null ? '分析時間未確認' : `分析距今 ${days} 日${age.over_14_calendar_days === true ? '（超過 14 日）' : ''}`;
        const stale = age.conclusion_stale === true ? '資料已更新，結論未同步' : '';
        const original = reason.direction_changed_by_gate === true && ['Long', 'Short'].includes(reason.original_direction)
            ? `原 ${reason.original_direction} → Neutral`
            : reason.original_direction === 'Neutral' && reason.category === 'source_rejection' ? '原已 Neutral，另有退件' : '';
        const label = [reason.label, original].filter(Boolean).join('｜');
        const date = typeof age.analysis_generated_at === 'string' ? age.analysis_generated_at : '';
        const heading = [label, ageText, stale].filter(Boolean).join(' · ');
        if (!options.detailed) return `<div class="history-date history-neutral-reason"><span title="${escapeHtml(reason.summary || '')}">${escapeHtml(heading)}</span></div>`;
        const evidence = Array.isArray(reason.evidence) ? reason.evidence.slice(0, 2) : [];
        return `<details class="preview-reading-notice preview-neutral-reason"><summary>${escapeHtml(heading)}</summary>
            ${date ? `<p>原分析時間：${escapeHtml(date)}（日齡以台灣日期計算；僅表示報告年齡，非有效期判定）</p>` : '<p>缺少可核實的原分析時間，不代填為今天。</p>'}
            ${reason.summary ? `<p>${escapeHtml(reason.summary)}</p>` : ''}
            ${evidence.map(item => `<p>保存原文：${escapeHtml(item.text || '')}</p>`).join('')}
            <p>原因分類不代表品質通過；仍須核對既有品質警示。補資料不會自動重跑結論。</p></details>`;
    }
    window.StockAgentHistoryNeutralReason = { render };
})();
