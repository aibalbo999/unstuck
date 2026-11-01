import json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from curl_cffi.requests import Response,Headers
from curl_cffi.requests.models import Request
from provider_correlation import correlation_scope
from yahoo_annual_original import capture_annual_response
B={'ticker':'1623.TW','fetch_id':'fetch','operation_id':'annual'}
def response():
 url='https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/1623.TW?symbol=1623.TW&type=annualOperatingIncome&crumb=private-test-value'
 r=Response(request=Request(url,Headers({'Cookie':'private-test-value'}),'GET'));r.url=url;r.content=json.dumps({'timeseries':{'result':[{'meta':{'symbol':['1623.TW'],'type':['annualOperatingIncome']},'timestamp':[1703980800],'annualOperatingIncome':[{'asOfDate':'2023-12-31','periodType':'12M','currencyCode':'TWD','reportedValue':{'raw':440044000}}]}],'error':None}}).encode();return r

def test_native_bytes_preserved_without_private_query():
 from official_response_evidence import read_response
 r=response()
 with correlation_scope(replace=True,**B):p=capture_annual_response(r,binding=B)
 assert p and read_response(p)==r.content
 assert 'private-test-value'not in json.dumps(p)and 'crumb'not in p['source_url']
 assert p['financial_semantics_verified']is False

@pytest.mark.parametrize('case',['owner','status','cache','redirect','stream','issuer','quarterly','private_body','authorization','duplicate','unknown_type','malformed'])
def test_fail_closed_without_archive(monkeypatch,case):
 import official_response_evidence
 monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:pytest.fail('No rejected response may be archived'))
 r=response();b=dict(B);payload=json.loads(r.content)
 if case=='owner':b['operation_id']='wrong'
 if case=='status':r.status_code=429
 if case=='cache':r.from_cache=True
 if case=='redirect':r.redirect_count=1
 if case=='stream':r.queue=object()
 if case=='authorization':r.request.headers['Authorization']='secret'
 if case=='issuer':payload['timeseries']['result'][0]['meta']['symbol']=['2330.TW']
 if case=='quarterly':r.url=r.url.replace('annualOperatingIncome','quarterlyOperatingIncome');r.request.url=r.url
 if case=='private_body':payload['timeseries']['credentials']={'token':'secret'}
 if case=='duplicate':payload['timeseries']['result']*=2
 if case=='unknown_type':payload['timeseries']['result'][0]['meta']['type']=['annualFake']
 r.content=b'bad'if case=='malformed'else json.dumps(payload).encode()
 with correlation_scope(replace=True,**B):assert capture_annual_response(r,binding=b)is None
