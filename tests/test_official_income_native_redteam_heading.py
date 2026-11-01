"""Native red-team headings never supply missing issuer/period evidence."""
import pytest
from test_official_income_claims import TEXT,selected,income_claims
WRAPPER='## 獨立反證審查報告：大東電 (1623.TW)'
HEADING='### 二、 已觀測財務'
def test_exact_native_redteam_wrapper_replays_official_fact():
 rows=income_claims(WRAPPER+'\n\n'+HEADING+'\n\n'+TEXT,selected())
 assert len(rows)==1 and rows[0]['status']=='verified',rows
@pytest.mark.parametrize('wrapper',[WRAPPER.replace('大東電','台積電'),WRAPPER.replace('1623.TW','2330.TW'),WRAPPER+' 美元',WRAPPER+' 2024年度',WRAPPER+' 合併財報','# 台積電\n'+WRAPPER])
def test_conflicting_ancestor_not_erased(wrapper):
 rows=income_claims(wrapper+'\n\n'+HEADING+'\n\n'+TEXT,selected())
 assert rows and all(x['status']=='unverifiable'for x in rows),rows
@pytest.mark.parametrize('text',[TEXT.replace('TWD ',''),TEXT.replace('個別','合併'),TEXT.replace('2025-07-01','2024-07-01'),TEXT.replace('大東電','台積電')])
def test_neutral_heading_does_not_grant_missing_scope(text):
 rows=income_claims(WRAPPER+'\n\n'+HEADING+'\n\n'+text,selected())
 assert rows and all(x['status']=='unverifiable'for x in rows),rows
def test_wrong_amount_still_mismatches():
 rows=income_claims(WRAPPER+'\n\n'+HEADING+'\n\n'+TEXT.replace('0.032','0.32'),selected())
 assert len(rows)==1 and rows[0]['status']=='mismatch',rows
