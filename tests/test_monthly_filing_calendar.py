import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from datetime import date
import pytest
from data_fetch.market_sources import official_monthly_revenue as candidate
def rows(period):return [{'公司代號':'1623','公司名稱':'大東電','資料年月':period,'營業收入-上月營收':'482000','營業收入-當月營收':'519000','出表日期':'1151101','備註':''}]
@pytest.mark.parametrize('day',[1,9,10])
def test_not_due_latest_month_is_explicit_not_latest_or_complete(day):
 records,audit=candidate.select_monthly_records(rows('11509'),'1623.TW',date(2026,11,day))
 assert records==['2026年8月: NT$4.82億','2026年9月: NT$5.19億']
 assert audit['covered_months']==['2026-08','2026-09']
 assert audit['latest_calendar_month']=='2026-10'and audit['latest_calendar_month_in_snapshot']is False
 assert audit['latest_calendar_month_filing_due_on']=='2026-11-10'
 assert audit['coverage_status']=='partial_two_adjacent_months_latest_filing_pending'
 assert audit['window_complete']is False
@pytest.mark.parametrize('day',[11,12,30])
def test_after_deadline_missing_latest_stays_unavailable(day):
 with pytest.raises(ValueError,match='monthly_latest_period_unavailable'):candidate.select_monthly_records(rows('11509'),'1623.TW',date(2026,11,day))
def test_early_filed_latest_month_keeps_original_period():
 records,audit=candidate.select_monthly_records(rows('11510'),'1623.TW',date(2026,11,1))
 assert audit['covered_months']==['2026-09','2026-10']and audit['coverage_status']=='partial_two_adjacent_months'
 assert 'filing_calendar_status'not in audit
@pytest.mark.parametrize('period',['11508','11511'])
def test_old_or_future_not_admitted(period):
 with pytest.raises(ValueError):candidate.select_monthly_records(rows(period),'1623.TW',date(2026,11,1))
def test_year_rollover():
 _,a=candidate.select_monthly_records(rows('11511'),'1623.TW',date(2027,1,1));assert a['covered_months']==['2026-10','2026-11']and a['latest_calendar_month']=='2026-12'
def test_changed_issuer_not_substituted():
 assert candidate.select_monthly_records(rows('11509'),'2330.TW',date(2026,11,1))==([],{})

@pytest.mark.parametrize('key,value',[('latest_calendar_month','2026-09'),('latest_calendar_month_in_snapshot',True),('latest_calendar_month_filing_due_on','2026-11-11'),('filing_calendar_status','complete')])
def test_history_anchor_rejects_changed_pending_contract(key,value):
 _,a=candidate.select_monthly_records(rows('11509'),'1623.TW',date(2026,11,1));a[key]=value
 with pytest.raises(ValueError):candidate.history_month_anchor(a,date(2026,11,1))
def test_history_anchor_cannot_reuse_pending_period_after_deadline():
 _,a=candidate.select_monthly_records(rows('11509'),'1623.TW',date(2026,11,1))
 with pytest.raises(ValueError):candidate.history_month_anchor(a,date(2026,11,11))
