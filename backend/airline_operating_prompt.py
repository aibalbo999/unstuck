"""Qualified carrier facts for business, growth, adversarial and final roles."""
from copy import deepcopy

# Technical-only Mode D retains its price/chip mandate. Management sentiment
# needs management quotations; traffic measurements cannot substitute for them.
ROLES=frozenset({1,5,6,7,12,13,14,16,18,19,21})

def qualified_alternative_context(data,agent_num):
    if agent_num not in ROLES or not isinstance(data,dict):return None
    payload=data.get('alternative_data')
    if not isinstance(payload,dict)or not isinstance(payload.get('operating_metrics_official'),dict):return None
    from data_fetch.market_sources.caa_operating_evidence import verified_count
    if verified_count(payload['operating_metrics_official'],data)!=1:return None
    result=deepcopy(payload)
    note='航空營運資料須沿本月／累計、具名公司、單位與原日期引用；不是招聘、集團財報、未來成長率、估值或即時買賣觸發的證據。'
    notes=result.get('coverage_notes');result['coverage_notes']=[*(notes if isinstance(notes,list)else[]),note]
    result['operating_citation_rule']='每個營運數字獨立成行：民航局 {官方簡稱} {西元年}年{月}月 全球{指標}：{原顯示值} {單位}。累計改為{西元年}年1至{月}月累計。指標限旅客人數、人；載客率、%；貨運噸數（含郵件、貨物及行李）、公噸；載貨率、%。依保存原件逐欄引用，不把本月、累計或不同公司互換，不加成長、財報、雇用或估值推論。'
    return result
