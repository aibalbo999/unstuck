from copy import deepcopy
import pytest
from test_official_income_native_summary_heading import data_with_english
from test_official_income_claims import income_claims
TEXT="大東電官方個別 TTM（2025-07-01 至 2026-06-30）淨利為 0.032 億元新臺幣。"
TITLE='# 1623.TW（大東電）投資銀行等級估值解讀報告'
@pytest.mark.parametrize('heading',['## 二、獲利趨勢深析','## 已觀測財務與歷史反證','## 企業體質總結','## 六、成長潛力總評\n### 現金流與獲利品質分析','## Round 2：財務與估值'])
def test_explicit_original_bound_fact_inside_observed_section(heading):
 data=data_with_english();before=deepcopy(data)
 rows=income_claims(TITLE+'\n'+heading+'\n'+TEXT,data)
 assert rows and all(r['status']=='verified' for r in rows),rows
 assert data==before
@pytest.mark.parametrize('scope',['# 台積電','## 2024年度','## 合併財報','## 美元','## 未來預測','## 同業比較'])
def test_conflicting_scope_cannot_hide_in_observed_section(scope):
 rows=income_claims(TITLE+'\n'+scope+'\n### 已觀測財務與歷史反證\n'+TEXT,data_with_english())
 assert rows and all(r['status']=='unverifiable' for r in rows),rows
