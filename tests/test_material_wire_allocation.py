import time
import pytest
import mops_material_transport as transport
from test_mops_material_transport import offline,descriptor,wire,PDF
from test_mops_body_budget_review import install_wire
from search_provider_runtime import SourceResponseError

def test_explicit_large_original_allocation_fits_unchanged_caller_deadline(offline,monkeypatch):
 _,calls=install_wire(monkeypatch,wire(),13.)
 d={}
 assert transport.download_published_material(descriptor(),deadline=125.,diagnostics=d,wire_budget_seconds=15.)==PDF
 assert calls[0][1]==115. and len(calls)==1 and d['response_complete']
 args=calls[0][0]
 assert args[args.index('--max-time')+1]=='15.0'
 assert args[args.index('--retry')+1]=='0' and calls[0][2]['body_limit']==16*1024*1024

@pytest.mark.parametrize('deadline,duration,stop',[(125.,15.,115.),(112.,12.,112.)])
def test_allocated_body_still_fails_at_own_or_caller_bound(offline,monkeypatch,deadline,duration,stop):
 _,calls=install_wire(monkeypatch,wire(),duration);d={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=deadline,diagnostics=d,wire_budget_seconds=15.)
 assert e.value.error_kind=='timeout' and calls[0][1]==stop and len(calls)==1
 assert d['response_complete'] is False

@pytest.mark.parametrize('budget',[True,False,0,-1,15.01,float('nan'),float('inf'),'15'])
def test_invalid_allocation_never_starts_request(offline,budget):
 d={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()+25,diagnostics=d,wire_budget_seconds=budget)
 assert e.value.error_kind=='transport_budget_invalid' and not offline[0] and d['http_request_sent'] is False

from test_myson_mops_workflow import packet,common_harness

def test_only_qualified_myson_profile_allocates_longer_wire_budget(packet,monkeypatch):
 from data_fetch.market_sources import mops_presentation as source
 assert {k:v['material_wire_seconds'] for k,v in source.PROFILES.items() if 'material_wire_seconds' in v}=={'5314.TWO':15.}
 original=source.download_published_material;budgets=[]
 def download(spec,*,deadline,diagnostics,wire_budget_seconds):
  budgets.append(wire_budget_seconds)
  return original(spec,deadline=deadline,diagnostics=diagnostics)
 monkeypatch.setattr(source,'download_published_material',download)
 d={};v=source.fetch_presentation_context('5314.TWO',diagnostics=d)
 assert budgets==[15.] and d['http_request_count']==3 and source.verify_context(v,'5314.TWO')
 assert len(v['documents'][0]['pages'])==93
