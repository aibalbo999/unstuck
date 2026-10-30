"""Local DuPont periods cannot borrow unrelated TTM mentions or caveats."""
import re
import pytest
from audit_rule_engine import evaluate_configured_audit_rules

ISSUE='不可把 Yahoo TTM'

def issues(text, caveat=False):
    normalized=re.sub(r'[^\S\n]+','',text)
    return [x for x in evaluate_configured_audit_rules(2,normalized,has_data_quality_caveat=caveat) if ISSUE in x]

ANNUAL='2025年年度杜邦分析顯示ROE為27.9%，由淨利率12.4%、資產周轉率0.928x與權益乘數2.422x共同驅動（2025年度財務數據口徑）。'
TTM='官方個別財報TTM自由現金流為-2.47億元，期間2025-07-01至2026-06-30。'
BAD='杜邦分析使用Yahoo TTM淨利率12.4%與最新年度資產周轉率0.928x及權益乘數2.422x拼接，並解釋口徑差距。'

@pytest.mark.parametrize('text',[
 ANNUAL+'\n\n'+TTM,
 '- 發現：'+ANNUAL+'\n- 發現：'+TTM,
 ANNUAL+TTM,
 TTM+'\n\n'+ANNUAL,
 '## TTM現金流\n'+TTM+'\n\n## 2025年度杜邦分析\n'+ANNUAL,
 '## 年度杜邦分析\n| 項目 | 2025年度值 |\n|---|---|\n| 淨利率 |12.4%|\n|資產周轉率|0.928x|\n|權益乘數|2.422x|\n\n## TTM現金流\n'+TTM,
 '年度杜邦分析使用淨利率12.4%×資產周轉率0.928x×權益乘數2.422x。Yahoo TTM ROE與ROA僅供對照，屬不同期間口徑偏差。',
 '不可把Yahoo TTM ROE/ROA/淨利率與最新年度資產周轉率或權益乘數拼接成TTM杜邦公式；應用同期間年度口徑。',
 '若混用Yahoo TTM淨利率與最新年度資產周轉率及權益乘數，杜邦公式會出現口徑偏差，不得如此計算。',
])
def test_separate_period_claims_and_local_warnings_are_not_mixed(text):
    assert issues(text)==[]

@pytest.mark.parametrize('text',[
 BAD,
 'TTM杜邦分析使用淨利率、資產周轉率與權益乘數，並解釋ROE差距。',
 '杜邦分析：\n- TTM淨利率12.4%。\n- 最新年度資產周轉率0.928x與權益乘數2.422x，相乘得到ROE。',
 '不可把TTM與年度拼成杜邦公式，但是目前仍使用TTM淨利率與最新年度資產周轉率及權益乘數相乘。',
 'TTM杜邦分析：淨利率12.4%×2025年度資產周轉率0.928x×權益乘數2.422x=ROE27.9%。',
 '杜邦分析採TTM淨利率12.4%。資產周轉率0.928x與權益乘數2.422x採最新年度值，三者相乘得到ROE。',
 '## 杜邦分析\nTTM淨利率12.4%。\n最新年度資產周轉率0.928x與權益乘數2.422x相乘計算ROE。',
 '## 杜邦計算\n|指標|期間|值|\n|---|---|---|\n|淨利率|TTM|12.4%|\n|資產周轉率|2025年度|0.928x|\n|權益乘數|2025年度|2.422x|',
 BAD+'\n\n## 資料品質警示\n其他資料尚未核實，只供對照。',
 '資料品質警示：其他資料有期間差距。\n\n'+BAD,
 '不應混用不同口徑。'+BAD,
 BAD+'但另有資料品質警示。',
])
@pytest.mark.parametrize('global_caveat',[False,True])
def test_actual_local_mixed_calculation_blocks_despite_global_caveat(text,global_caveat):
    assert issues(text,global_caveat)


def test_numeric_formula_in_warning_section_still_blocks():
    text='## 資料品質警示\n'+BAD
    assert issues(text,True)


@pytest.mark.parametrize('caveat',[False,True])
@pytest.mark.parametrize('metrics,periods',[
 ('淨利率|資產周轉率|權益乘數|ROE','TTM|2025年度|2025年度|TTM'),
 ('ROE|權益乘數|淨利率|資產週轉率','TTM|2025年度|TTM|2025年度'),
 ('資產周轉率|ROA|權益乘數','2025年度|LTM|2025年度'),
])
def test_transposed_table_binds_each_period_to_its_metric(metrics,periods,caveat):
    count=len(metrics.split('|'))
    table='## 杜邦分析\n|指標|'+metrics+'|\n|---'+('|---'*count)+'|\n|期間|'+periods+'|\n|值|'+('|'.join(['1']*count))+'|\n以上因子相乘得到杜邦ROE。'
    assert issues(table,caveat)


@pytest.mark.parametrize('body',[
 '|期間|2025年度|2025年度|2025年度|2025年度|\n|值|12%|1x|2x|24%|',
 '|期間|TTM|TTM|TTM|TTM|\n|值|12%|1x|2x|24%|',
 '|期間|2025年度|2025年度|2025年度|2025年度|\n|期間|TTM|TTM|TTM|TTM|',
])
def test_transposed_table_complete_same_period_rows_remain_separate(body):
    table='## 杜邦分析\n|指標|淨利率|資產周轉率|權益乘數|ROE|\n|---|---|---|---|---|\n'+body
    assert issues(table)==[]


def test_separate_annual_and_ttm_comparison_tables_do_not_mix_columns():
    table='|指標|淨利率|資產周轉率|權益乘數|ROE|\n|---|---|---|---|---|\n'
    text='## 杜邦對照\n'+table+'|期間|2025年度|2025年度|2025年度|2025年度|\n\n'+table+'|期間|TTM|TTM|TTM|TTM|\n各表僅計算同期間恒等式。'
    assert issues(text)==[]
