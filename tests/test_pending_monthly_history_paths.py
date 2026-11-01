import sys,json,importlib
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pytest
from test_twse_monthly_history import original_http as twse_http
from test_auras_monthly_history import original_http as auras_http
from test_myson_monthly_history import original_http as myson_http
from data_fetch.taiwan_providers import MonthlyRevenueProvider
from data_fetch.types import FetchRequest

@pytest.mark.parametrize('kind,ticker',[('twse','2466.TW'),('auras','3324.TWO'),('myson','5314.TWO')])
def test_all_history_paths_use_snapshot_period_and_retain_pending_flags(request,monkeypatch,kind,ticker):
 fixture=request.getfixturevalue(kind+'_http')
 if kind!='twse':
  # Synthetic calendar-only variant of retained test master; never native production evidence.
  module=importlib.import_module('test_'+kind+'_monthly_history');bodies=fixture[1];raw=json.loads(bodies[module.MASTER])
  assert all('Date'in row for row in raw)
  for row in raw:row['Date']='1151101'
  bodies[module.MASTER]=json.dumps(raw,ensure_ascii=False).encode()
 from data_fetch.market_sources import official_monthly_revenue as source,official_monthly_transport as transport
 monkeypatch.setattr(source,'_today',lambda:date(2026,11,1));monkeypatch.setattr(transport,'_today',lambda:date(2026,11,1))
 first=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker(ticker))
 assert len(first.value)==6,first.audit
 assert first.audit['covered_months']==['2026-04','2026-05','2026-06','2026-07','2026-08','2026-09']
 assert first.audit['latest_calendar_month']=='2026-10'
 assert first.audit['latest_calendar_month_in_snapshot']is False
 assert first.audit['coverage_status']=='complete_six_contiguous_month_amounts_latest_filing_pending'
 second=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker(ticker))
 assert second.value==first.value and second.audit['cache_hit']is True and second.audit['http_request_sent']is False
 assert second.audit['fetched_at_epoch']==first.audit['fetched_at_epoch']
 assert second.audit['latest_calendar_month_in_snapshot']is False
