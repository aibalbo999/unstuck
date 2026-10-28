"""Bound topic/period witnesses, not a general economic-entailment certificate."""
from __future__ import annotations

import re

POLICY = 'research-quote-semantics:v1-topic-and-period'
_TOPIC = {
    'baseline': r'基期|基準|基礎|baseline|base.year|20\d{2}.{0,10}(?:歷史|實際|營收基期|年度EPS)',
    'period': r'20\d{2}|\d+\s*(?:年|個月|季)|[一二三四五十]+年|TTM|LTM|年度|期間|horizon',
    'growth': r'成長|增長|年增|CAGR|growth|YoY',
    'capex_margin': r'資本支出|產能|折舊|毛利率|淨利率|利潤率|營業利益率|CapEx|margin|capacity|depreciation',
    'calculation': r'計算|公式|算式|DCF|FCF|自由現金流|折現|本益比|倍數|WACC|EPS|[=×]',
}


def quote_topics(text):
    """Lexical candidates only; a topic label never certifies the rationale."""
    return tuple(topic for topic, pattern in _TOPIC.items() if re.search(pattern, text, re.I))


def _periods(text):
    years = set(re.findall(r'20\d{2}', text))
    durations = {int(number) * {'年': 12, '個月': 1, '季': 3}[unit]
                 for number, unit in re.findall(r'(\d+)\s*(年|個月|季)', text) if int(number) < 100}
    for number, value in zip('一二三四五六七八九十', range(1, 11)):
        for unit, scale in (('年', 12), ('個月', 1), ('季', 3)):
            if number + unit in text:
                durations.add(value * scale)
    return years, durations


def semantic_issues(rows):
    result = []
    for row in rows:
        if row.status == 'unassessed':
            continue
        quotes = [('valuation_quote', 4, row.valuation_quote), ('growth_quote', 5, row.growth_quote)]
        for field, agent, quote in quotes:
            if quote.strip() and row.topic not in quote_topics(quote):
                result.append({'topic': row.topic, 'field': field, 'source_agent': agent,
                               'reason': 'quote_does_not_cover_declared_topic'})
        if row.status == 'aligned' and row.topic in {'baseline', 'period'} and all(item[2].strip() for item in quotes):
            left_years, left_durations = _periods(row.valuation_quote)
            right_years, right_durations = _periods(row.growth_quote)
            common = (left_years & right_years) or (left_durations & right_durations)
            incompatible = ((left_years and right_years and not left_years & right_years)
                            or (left_durations and right_durations and not left_durations & right_durations))
            if not common or incompatible:
                result.append({'topic': row.topic, 'field': 'rationale', 'source_agent': None,
                               'reason': 'aligned_without_common_explicit_period'})
        if row.topic == 'calculation' and row.status == 'aligned' and re.search(r'DCF', row.rationale, re.I):
            for field, agent, quote in quotes:
                if quote.strip() and not re.search(r'DCF|FCF|自由現金流|折現', quote, re.I):
                    result.append({'topic': row.topic, 'field': field, 'source_agent': agent,
                                   'reason': 'dcf_rationale_not_supported_by_quote'})
    return result


def semantic_prompt():
    return (
        '【假設引文主題與期間核對】逐字出現不等於支持推論。baseline 的兩段須明示基期依據；'
        'period 的 aligned 須能從兩段直接核對共同年份或相同長度期間，2026展望不等於五年預測。'
        'growth 須引用成長假設，capex_margin 須引用產能／CapEx／利潤率，calculation 須引用計算或估值依據。'
        '若聲稱雙方DCF不可用，兩段須各直接談DCF／FCF／折現依據；衛星需求不是DCF計算證據。'
        '不以表頭、背景敘述或別的Agent補足原文未說的假設；無同主題／同期間依據時標unassessed並說明，'
        'unassessed 也不能使用不相干主題的 ref；沒有對應片段時將該引文留空，不填 ref。'
        '不能為過關改寫原文或把未評估改為一致。這是有界主題檢查，不是完整經濟語義或財報認證。'
    )
