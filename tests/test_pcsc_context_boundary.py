"""Public provider rejects explicit contradictory context before acquisition."""
import pytest
from test_pcsc_conference import harness

@pytest.mark.parametrize('edit',['top_stock_id','identity_quote_type','identity_quoteType','false_data'])
def test_explicit_identity_conflict_blocks_before_acquisition(harness,edit):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    data={'ticker':'2912.TW','company_name':'統一超','quote_type':'EQUITY','company_identity':{}}
    if edit=='top_stock_id':data['stock_id']='1216'
    elif edit=='identity_quote_type':data['company_identity']['quote_type']='ETF'
    elif edit=='identity_quoteType':data['company_identity']['quoteType']='ETF'
    else:data=False
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2912.TW'),{'data':data})
    assert result.status=='unavailable' and not harness[1], (result.status,harness[1])
    assert result.audit['error_kind']=='context_unverified'
