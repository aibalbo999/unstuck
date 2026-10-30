import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import pandas as pd
import pytest
from test_financial_statement_observation import statement_frames, StatementStock
import data_fetch.yfinance_extractors as module

@pytest.mark.parametrize('field,label,table',[
 ('fcf_history','Capital Expenditure','cashflow'),
 ('gross_profit_history','Gross Profit','financials'),
 ('operating_income_history','Operating Income','financials')])
@pytest.mark.parametrize('statement_date,filled',[('2024-12-31',True),('2024-06-30',False)])
def test_isolated_partial_field_requests_existing_fallback_once(monkeypatch,field,label,table,statement_date,filled):
 frames=statement_frames();frames[table].loc[label,pd.Timestamp('2024-12-31')]=float('nan')
 calls=[];key={'fcf_history':'free_cash_flow','gross_profit_history':'gross_profit','operating_income_history':'operating_income'}[field]
 def fallback(*args,**kwargs):
  calls.append(args)
  return {'audit':{'source':'financial_statements','provider':'FinMind financial statement fallback','status':'degraded_enrichment','record_count':2},'value':{'years':['2024','2025'],'rows_by_year':{'2024':{'statement_date':statement_date,key:0.123},'2025':{'statement_date':'2025-12-31',key:999}}}}
 monkeypatch.setattr(module,'audited_finmind_financial_statement_fallback',fallback)
 result=module.extract_financial_histories(StatementStock(frames),'5314.TWO',[],data_loader_cls=object)
 assert len(calls)==1
 assert result[field][0]==(0.123 if filled else None)
 assert result[field][1] !=999 and result[field][1] is not None
 assert result['years']==['2024','2025']
 assert result['primary_financial_audit']['status']=='degraded_enrichment'
 assert result['finmind_financial_fallback_audit'] is not None
