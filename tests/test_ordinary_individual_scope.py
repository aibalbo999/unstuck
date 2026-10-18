"""RED uses existing public consumers; no missing-module failure is evidence."""
from quant_input_contract import read_quant_inputs
from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
from data_fetch.types import FetchRequest

def data():
    return {'ticker':'2646.TW','quote_type':'EQUITY','financial_currency':'TWD','currency':'TWD',
            'sector':'Industrials','industry':'Airlines','shares_raw':1e8,'current_price':20,
            'market_cap_raw':2e9,'total_debt_raw':1e8,'total_cash_raw':1e8,'free_cash_flow_raw':1e8,'trailing_eps':2,
            'financial_history_basis':{'schema':'financial_history_basis.v1','statement_schema':'ordinary_individual.v1'}}

def test_unknown_individual_scope_must_not_enable_group_dcf():
    assert 'ordinary_individual_group_basis_unverified' in read_quant_inputs(data())[2]['dcf']

def test_individual_basis_must_not_dispatch_airline_to_bank_parser(monkeypatch):
    import data_fetch.annual_financial_source_provider as m
    called=[]
    def audited(source,provider,fn,args,**kwargs):
        called.append(provider)
        return {'value':None,'audit':{'source':source,'provider':provider,'status':'unavailable','record_count':0}}
    monkeypatch.setattr(m,'audited_fetch',audited)
    # Prevent any actual ordinary-provider callback in either version.
    import data_fetch.official_financial_gap_cache as ordinary
    monkeypatch.setattr(ordinary,'fetch_official_financial_result',lambda ticker:{'value':None,'audit':{'source':'financial_statements','provider':'synthetic','status':'unavailable','record_count':0}})
    try:
        import data_fetch.market_sources.ordinary_individual_annual as candidate
    except ImportError:pass
    else:
        monkeypatch.setattr(candidate,'fetch_annual_result',lambda ticker:{'value':None,'audit':{'source':'financial_statements','provider':candidate.PROVIDER,'status':'unavailable','record_count':0}})
    AnnualFinancialSourceProvider().fetch(FetchRequest('2646.TW'),{'data':data()})
    assert 'TWSE MOPS official financial-institution iXBRL' not in called
