from datetime import date
import pytest,pandas as pd
from market_screener_sources import TwseFreeScreenerDataSource
from market_screener_candidates import build_screener_candidates
from market_screener_utils import clean_tw_stock_id,is_common_tw_stock_id
ROWS=[['2002','中鋼','27,995,185','19.25'],['2002A','中鋼特','51,310','37.45'],['2891','中信金','50,114,684','75.80'],['2891B','中信金乙特','326','--'],['2891C','中信金丙特','1,029','--'],['0050','台灣50','999','100']]
def source():
 s=TwseFreeScreenerDataSource()
 s._json_get=lambda url:([{'Date':'1151030','Code':'2002','MonthlyAveragePrice':'18.9'},{'Date':'1151030','Code':'2002A','MonthlyAveragePrice':'37.6'}] if 'AVG' in url else [{'Date':'1151029','Code':'2002','ClosingPrice':'19','TradeVolume':'100'}])
 class Response:
  def json(self):return {'stat':'OK','date':'20261030','tables':[{'fields':['證券代號','證券名稱','成交股數','收盤價'],'data':ROWS}]}
 s._get=lambda *a,**kw:Response()
 return s

def test_raw_security_codes_cannot_collapse_to_ordinary_equity():
 for code in ('2002A','2891B','2891C','00A50','20 02','２００２','2002.TW'):
  assert not is_common_tw_stock_id(clean_tw_stock_id(code)),code
 for code in ('2002',' 2891 ',2002):assert is_common_tw_stock_id(clean_tw_stock_id(code))
 assert not is_common_tw_stock_id('0050')
def test_daily_and_monthly_average_keep_exact_common_share_identity():
 f=source().fetch_daily_frame(date(2026,10,30))
 assert list(f.stock_id)==['2002','2891']
 steel=f[f.stock_id=='2002'].iloc[0];bank=f[f.stock_id=='2891'].iloc[0]
 assert steel.close==19.25 and steel.Trading_Volume==27995185 and steel.monthly_average_close==18.9
 assert bank.close==75.8 and bank.Trading_Volume==50114684

def test_institutional_preferred_codes_and_funds_cannot_join_common_shares():
 payload={'date':'20261030','data':[[1,'2002','中鋼','1000','0'],[2,'2002A','中鋼特','1000000','0'],[3,'0050','台灣50','999999','0']]}
 rows=source()._institutional_records_from_payload(payload,'Foreign_Investor',date(2026,10,30))
 assert [r['stock_id'] for r in rows]==['2002'] and rows[0]['buy']==1000

def test_same_session_flow_uses_common_share_volume_not_preferred_last_row():
 daily=source().fetch_daily_frame(date(2026,10,30));flow=pd.DataFrame([{'date':'2026-10-30','stock_id':'2002','name':'Foreign_Investor','buy':937936,'sell':0},{'date':'2026-10-30','stock_id':'2002','name':'Investment_Trust','buy':209000,'sell':0}])
 row=next(r for r in build_screener_candidates(flow,daily,scan_date=date(2026,10,30),top_n=1) if r['ticker']=='2002.TW')
 assert row['metrics']['normalized_flow_pct']==pytest.approx(1146936/27995185*100)
 assert row['metrics']['close']==19.25 and row['actionable'] is False
