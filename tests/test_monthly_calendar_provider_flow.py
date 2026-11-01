import sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_official_monthly_revenue import native_csv,isolated_cache
from data_fetch.taiwan_providers import MonthlyRevenueProvider
from data_fetch.types import FetchRequest

def test_month_start_provider_and_cache_keep_exact_period_and_pending_flag(monkeypatch):
 calls=native_csv(monkeypatch)
 from data_fetch.market_sources import official_monthly_revenue as source,official_monthly_transport as transport
 monkeypatch.setattr(source,'_today',lambda:date(2026,11,1));monkeypatch.setattr(transport,'_today',lambda:date(2026,11,1))
 first=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
 second=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2330.TW'))
 assert first.value==second.value==['2026年8月: NT$5148.05億','2026年9月: NT$5118.57億']
 assert first.audit['coverage_status']=='partial_two_adjacent_months_latest_filing_pending'
 assert first.audit['latest_calendar_month']=='2026-10'and first.audit['latest_calendar_month_in_snapshot']is False
 assert first.audit['window_complete']is False
 assert second.status=='skipped_fresh_cache'and second.audit['http_request_sent']is False
 assert first.audit['fetched_at_epoch']==second.audit['fetched_at_epoch']
 assert calls==['https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv']


def test_pending_calendar_survives_telemetry_and_prompt_without_latest_claim():
 from provider_observation_details import observation_details,monthly_filing_details
 from prompt_source_audit import prompt_source_audit_summary
 entry={'source':'monthly_revenue','provider':'official-test','status':'success',
        'record_count':2,'observed_month':'2026-09','latest_calendar_month':'2026-10',
        'latest_calendar_month_in_snapshot':False,'latest_calendar_month_filing_due_on':'2026-11-10',
        'filing_calendar_status':'latest_month_not_yet_in_snapshot_before_deadline'}
 expected=monthly_filing_details(entry);assert len(expected)==5
 details=observation_details(entry)
 prompt=prompt_source_audit_summary({'source_audit':[entry],'recent_monthly_revenue':['a','b']})[0]
 assert all(details[k]==v and prompt[k]==v for k,v in expected.items())
 for key,value in [('latest_calendar_month','2026-11'),('latest_calendar_month_in_snapshot',True),
                   ('observed_month','2026-08'),('latest_calendar_month_filing_due_on','2026-11-11'),
                   ('source','financial_statements'),('latest_calendar_month','token=secret'),
                   ('latest_calendar_month_filing_due_on','20261110')]:
  changed={**entry,key:value};assert monthly_filing_details(changed)=={}
