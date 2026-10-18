"""Visible numeric check trace, never independent or predictive validation."""
from html import escape


def _rows(context):
    gate = context.get('evidence_exit_gate') or {}
    return gate.get('sampled_claims', []) if isinstance(gate, dict) else []


def _parts(row):
    values = [str(row.get(k, '')) for k in ('label', 'reported_value', 'status', 'matched_path', 'matched_value', 'verification_reason_code')]
    values[2] = {'verified':'快照一致', 'unverifiable':'未能核實', 'mismatch':'數值矛盾'}.get(values[2], values[2])
    values[5] = {'matched_snapshot_value':'對應快照數值', 'generated_analysis_not_independent_evidence':'模型計畫，缺獨立事實證據', 'no_matching_snapshot_path':'沒有對應快照路徑', 'snapshot_value_mismatch':'與快照數值矛盾'}.get(values[5], values[5])
    values[5] = {'scenario_target_not_observed_fact': '情境推估，非觀測事實',
        'financial_original_input_unavailable': '原分析財務輸入未能核實',
        'financial_amount_scope_unbound': '月均、變動端點等金額口徑未綁定',
        'financial_period_currency_or_unit_unknown': '財期、幣別或單位尚未核實',
        'financial_projection_not_observed_fact': '財務情境推估，非觀測事實',
        'matched_financial_metric_period_unit': '同指標、財期、幣別及換算單位一致',
        'financial_metric_period_unit_mismatch': '同指標及財期的金額或單位矛盾',
        'pe_arithmetic_mismatch': '股價 ÷ EPS 與主張本益比不一致',
        'annual_eps_used_for_ttm_pe': '年度 EPS 不得用作 TTM 分母',
        'ttm_eps_snapshot_mismatch': 'TTM EPS 與保存快照不一致',
        'price_eps_currency_mismatch': '股價與 EPS 幣別不同',
        'derived_units_or_period_unbound': '衍生算式的單位或期間未確認',
        'derived_arithmetic_consistent': '算式及所述期間一致，並非獨立事實認證'}.get(values[5], values[5])
    if row.get('claim_type') == 'derived_calculation':
        values[2] = {'verified': '算式／期間一致', 'mismatch': '算式／期間矛盾', 'unverifiable': '算式口徑未核實'}.get(row.get('status'), values[2])
        values[3] = str(row.get('basis') or '') + '；股價 ÷ EPS'
        values[4] = str(row.get('calculated_value', ''))
    if row.get('financial_amount'):
        values[1] += ' ' + str(row.get('unit') or '單位未明')
        values[3] += '；財期=' + str(row.get('financial_period') or '未明')
        values[3] += '；幣別=' + str(row.get('financial_currency') or '未明')
        if row.get('source_unit'):
            values[3] += '；來源單位=' + str(row['source_unit'])
    return values


def evidence_ledger_markdown(context):
    rows = _rows(context)
    if not rows:
        return ''
    def clean(value):
        return value.replace('|', '\\|').replace('\n', ' ')
    lines = ['\n<!-- evidence-ledger:start -->', '\n### 數字主張逐項核對', '保存快照一致性核對；來源日期與口徑仍須核實。模型推論不是獨立事實證據。', '\n| 主張 | 報告值 | 結果 | 快照路徑 | 快照值 | 判準 |', '|---|---|---|---|---|---|']
    lines += ['| ' + ' | '.join(clean(v) for v in _parts(row)) + ' |' for row in rows]
    return '\n'.join(lines + ['<!-- evidence-ledger:end -->'])


def evidence_ledger_html(context):
    rows = _rows(context)
    if not rows:
        return ''
    body = ''.join('<tr>' + ''.join('<td style="overflow-wrap:anywhere">' + escape(v) + '</td>' for v in _parts(row)) + '</tr>' for row in rows)
    return '<details class="evidence-ledger"><summary>數字主張逐項核對</summary><p>保存快照一致性核對；模型推論不是獨立事實證據，通過不代表預測有效。</p><div style="overflow-x:auto"><table style="min-width:800px"><thead><tr>' + ''.join('<th>'+v+'</th>' for v in ['主張','報告值','結果','快照路徑','快照值','判準']) + '</tr></thead><tbody>' + body + '</tbody></table></div></details>'
