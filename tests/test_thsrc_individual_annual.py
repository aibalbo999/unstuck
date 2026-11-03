"""Issuer-specific normal annual routing; synthetic cases are not HTTP proof."""
from copy import deepcopy
import pytest
from test_ordinary_individual_annual import index, synthetic_filing, transport
import time,httpx

def test_thsrc_uses_latest_five_individual_originals_and_typed_basis():
    from data_fetch.market_sources import ordinary_individual_annual as m
    from data_fetch.annual_financial_source_provider import project_source_value
    assert m.ISSUERS['2633.TW'] == '台灣高速鐵路股份有限公司'
    http,calls=transport(index_body=index(a=range(2013,2026),issuer='2633'),
        bodies={y:synthetic_filing(y,issuer='2633',company_name='台灣高速鐵路股份有限公司')for y in range(2021,2026)})
    result=m.fetch_annual_result('2633.TW',transport=http,protocol='individual_xbrl')
    assert result['audit']['status']=='success'and len(calls)==6
    value=result['value'];p=project_source_value(value,'2633.TW')
    assert value['years']==['2021','2022','2023','2024','2025']
    assert p['financial_history_basis']['report_scope']=='individual'
    assert p['financial_history_basis']['field_sources']['net_income_history']['fact']=='ifrs-full:ProfitLoss'
    altered=deepcopy(value);altered['report_scope']='consolidated'
    assert project_source_value(altered,'2633.TW')is None

@pytest.mark.parametrize('key,value',[('official_ubn','16446275'),('official_name','台鐵'),('legal_name','台灣鐵路股份有限公司')])
def test_thsrc_context_rejects_different_employer_or_ubn(key,value):
    from data_fetch.market_sources.ordinary_individual_annual import validate_context
    data={'ticker':'2633.TW','quote_type':'EQUITY','company_identity':{'official_name':'台灣高鐵','legal_name':'台灣高速鐵路股份有限公司','official_ubn':'16446274'}}
    validate_context(data,'2633.TW');data['company_identity'][key]=value
    with pytest.raises(ValueError):validate_context(data,'2633.TW')

@pytest.mark.parametrize('issuer,total,delay,budget,success',[
    ('2633',45,3,5,True),('2633',4,6,4,False),('2646',45,6,5,False)])
def test_transport_keeps_original_wire_and_whole_deadline_bounded(monkeypatch,issuer,total,delay,budget,success):
    from data_fetch.market_sources import mops_public_annual as public
    from data_fetch.market_sources.ordinary_individual_annual import IndividualMopsHttp
    from search_provider_runtime import SourceResponseError
    base=time.monotonic();clock={'elapsed':0.};calls=[]
    monkeypatch.setattr(public.time,'monotonic',lambda:base+clock['elapsed'])
    raw=b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"/>'
    class SlowBody(httpx.SyncByteStream):
        def __iter__(self):
            clock['elapsed']+=delay
            yield raw
    def response(request):
        calls.append(request)
        return httpx.Response(200,stream=SlowBody(),headers={'content-type':'application/xml'})
    http=IndividualMopsHttp(client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(response),**kw),seconds=total)
    url='https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id='+issuer+'&year=2021&season=4&report_id=A'
    if success:
        body,receipt=http.request(url)
        assert body==raw and receipt['http_status']==200
        assert http.components[0]['response_complete']is True
    else:
        with pytest.raises(SourceResponseError)as failure:http.request(url)
        assert failure.value.error_kind=='timeout'
        assert http.components[0]['response_complete']is False
        assert http.components[0]['response_bytes']==len(raw)
    assert len(calls)==1 and calls[0].extensions['timeout']['read']==budget
