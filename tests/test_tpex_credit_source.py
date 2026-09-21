from chip_data_fetcher import fetch_twse_margin_short_sales
from test_chip_source_contract import Response
from short_term_output_validator import short_term_evidence_issues

class Session:
    def __init__(self,rows=None):self.calls=[];self.rows=rows
    def get(self,url,**kw):
        self.calls.append(url)
        assert '/tpex_mainboard_margin_balance' in url
        return Response(self.rows if self.rows is not None else [{'Date':'1150921','SecuritiesCompanyCode':'3324','CompanyName':'雙鴻','MarginPurchaseBalance':'6961','ShortSaleBalance':'136','CashRedemption':'0','StockRedemption':'--'}])


def test_two_uses_official_market_endpoint_and_preserves_roc_date_and_units():
    session=Session();result=fetch_twse_margin_short_sales('3324.TWO',session=session)
    assert len(session.calls)==1
    assert result['source']=='TPEx OpenAPI tpex_mainboard_margin_balance'
    assert result['margin_as_of_date']=='2026-09-21'
    assert result['margin_unit']=='thousand_shares'
    assert result['margin_balance']==6961
    assert result['margin_cash_repayment']==0 and result['short_cash_repayment'] is None
    assert result['borrowed_short_status']=='unavailable'
    data={'ticker':'3324.TWO','chip_data':{'twse_margin_short_sales':result}}
    assert not short_term_evidence_issues(23,'融資餘額6961張；融券餘額136張。',data)
    assert short_term_evidence_issues(23,'融資餘額6961股。',data)


def test_no_matching_tpex_row_is_unknown_not_zero_or_twse_fallback():
    session=Session([]);result=fetch_twse_margin_short_sales('3324.TWO',session=session)
    assert len(session.calls)==1 and result['reason_code']=='record_not_found'
    assert 'margin_balance' not in result


def test_invalid_tpex_date_remains_unknown():
    session=Session([{'Date':'1151399','SecuritiesCompanyCode':'3324','MarginPurchaseBalance':'0'}])
    result=fetch_twse_margin_short_sales('3324.TWO',session=session)
    assert result['margin_as_of_date'] is None and result['margin_date_status']=='unknown'
    assert result['margin_balance']==0


def test_tpex_identity_without_quantities_is_unavailable():
    result=fetch_twse_margin_short_sales('3324.TWO',session=Session([
        {'Date':'1150921','SecuritiesCompanyCode':'3324','MarginPurchaseBalance':'--'}]))
    assert result['status']=='unavailable'
    assert result['reason_code']=='quantities_unavailable'
