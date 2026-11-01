"""Exact fact captions are presentation, never replacement evidence."""
from copy import deepcopy
from decimal import Decimal
import pytest
from evidence_exit_gate import evaluate_report_evidence
from test_official_income_claims import selected,TEXT
from test_cashflow_component_issuer_alias import component_data

def rows(text,data):
 return [x for x in evaluate_report_evidence(text,{'data':data})['sampled_claims']if x.get('financial_amount')]

@pytest.mark.parametrize('caption',['官方 TTM 淨利','官方 TTM 獲利事實'])
def test_income_caption_replays_same_original_fact(caption):
 data=selected();before=deepcopy(data);result=rows('- **'+caption+'**：'+TEXT,data)
 assert len(result)==1 and result[0]['status']=='verified',result
 assert result[0]['independent_primary_source_verified']is True and data==before

@pytest.mark.parametrize('caption',['官方 TTM 自由現金流','官方 TTM 現金流事實'])
def test_fcf_caption_replays_exact_original(caption):
 data=selected();f=data['official_financial_projection']['facts'];v=Decimal(str(f['cashflows']['ttm']['free_cash_flow']))/Decimal(100000000)
 text=f'- **{caption}**：大東電官方個別財報 TWD TTM（{f["period_start"]} 至 {f["period_end"]}）自由現金流為 {v} 億元。'
 result=rows(text,data);assert len(result)==1 and result[0]['status']=='verified',result

def test_component_caption_does_not_change_metric_or_motive():
 data=component_data();text='- **官方 TTM 存貨變動現金影響**：大東電官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）存貨變動現金影響為 -0.08000 億元。'
 result=rows(text,data);assert len(result)==1 and result[0]['status']=='verified',result
 assert result[0]['underlying_business_motive']=='unverified'

@pytest.mark.parametrize('change',[lambda s:s.replace('TWD ',''),lambda s:s.replace('個別','合併'),lambda s:s.replace('大東電','台積電'),lambda s:s.replace('2025-07-01','2024-07-01'),lambda s:'# 台積電\n'+s,lambda s:s.replace('官方 TTM 淨利','2024年度官方 TTM 淨利'),lambda s:s.replace('官方 TTM 淨利','官方 TTM 自由現金流')])
def test_caption_cannot_supply_or_overwrite_scope(change):
 text=change('- **官方 TTM 淨利**：'+TEXT);result=rows(text,selected())
 assert result and all(x['status']=='unverifiable'for x in result),result

def test_caption_wrong_amount_still_mismatches():
 result=rows('- **官方 TTM 淨利**：'+TEXT.replace('0.032','0.32'),selected())
 assert len(result)==1 and result[0]['status']=='mismatch',result

def test_caption_missing_original_never_verifies():
 data=selected();data['official_financial_projection']['reference']['quarterly_document']['sha256']='0'*64
 result=rows('- **官方 TTM 淨利**：'+TEXT,data)
 assert result and all(x['status']=='unverifiable'for x in result),result


def test_caption_and_exact_negative_motive_note_compose_without_changing_claim():
 data=selected();f=data['official_financial_projection']['facts'];v=Decimal(str(f['cashflows']['ttm']['free_cash_flow']))/Decimal(100000000)
 fact=f'- **官方 TTM 現金流事實**：大東電官方個別財報 TWD TTM（{f["period_start"]} 至 {f["period_end"]}）自由現金流為 {v} 億元。'
 note='此現金流總額無法判定備料、存貨、應收款或擴產原因，任何用途解釋僅是待驗證假設。'
 result=rows(fact+note,data)
 assert len(result)==1 and result[0]['status']=='verified',result
 assert result[0]['raw_text']==fact+note
 assert result[0]['underlying_business_motive']=='unverified'


def test_nested_component_under_exact_native_memo_parent_retains_ancestors():
 from test_official_income_native_summary_heading import TITLE
 text=(TITLE+'\n\n## 已觀測財務與歷史反證\n- 官方現金流組成科目引用：\n'
       '  - 大東電官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）存貨變動現金影響為 -0.08000 億元。')
 result=rows(text,component_data());assert len(result)==1 and result[0]['status']=='verified',result
 for qualifier in ('台積電','2024年度','合併','USD','預估'):
  bad=text.replace('官方現金流組成科目引用',qualifier+'官方現金流組成科目引用')
  result=rows(bad,component_data());assert result and all(x['status']=='unverifiable'for x in result),result

def test_source_owned_valuation_memo_title():
 from test_official_income_native_summary_heading import TITLE,data_with_english
 wrapper='## 估值解讀與財務驗證報告：大東電 (1623.TW)'
 text=TITLE+'\n\n'+wrapper+'\n\n### 二、 已觀測財務與歷史反證\n- **官方 TTM 獲利事實**：'+TEXT
 result=rows(text,data_with_english());assert len(result)==1 and result[0]['status']=='verified',result
 for bad in (wrapper.replace('大東電','台積電'),wrapper.replace('1623.TW','2330.TW'),wrapper+' 2024年度',wrapper+' USD',wrapper+' 合併'):
  result=rows(text.replace(wrapper,bad),data_with_english());assert result and all(x['status']=='unverifiable'for x in result),result

def test_native_chip_conclusion_confidence_pair_rechecks_full_fact():
 from test_official_income_native_summary_heading import TITLE,data_with_english
 prefix=TITLE+'\n\n## 籌碼面與研究結論定調\n### 信心依據\n'
 result=rows(prefix+'- **具體佐證**: '+TEXT,data_with_english())
 assert len(result)==1 and result[0]['status']=='verified',result
 for bad in (prefix.replace('信心依據','信心依據 USD'),prefix.replace('籌碼面與研究結論定調','台積電籌碼面與研究結論定調'),prefix.replace('### 信心依據','## 2024年度\n### 信心依據')):
  result=rows(bad+'- **具體佐證**: '+TEXT,data_with_english());assert result and all(x['status']=='unverifiable'for x in result),result


@pytest.mark.parametrize('metric',['應收帳款變動現金影響','營業資產淨變動現金影響','營業負債淨變動現金影響','營業資產及負債淨變動現金影響'])
def test_caption_never_substitutes_inventory_for_missing_component(metric):
 text=f'- **官方 TTM {metric}**：大東電官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）{metric}為 -0.08000 億元。'
 result=rows(text,component_data());assert result and all(x['status']=='unverifiable'for x in result),result

def test_component_caption_wrong_amount_still_mismatches():
 text='- **官方 TTM 存貨變動現金影響**：大東電官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）存貨變動現金影響為 -0.80000 億元。'
 result=rows(text,component_data());assert len(result)==1 and result[0]['status']=='mismatch',result
