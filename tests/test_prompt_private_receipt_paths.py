"""Private receipt locations stay server-side; public evidence stays in prompts."""
from copy import deepcopy
from dataclasses import dataclass
import pytest
from pydantic import BaseModel,ConfigDict
from prompt_evidence import prompt_evidence_copy
from prompt_builder import format_data_for_prompt

PATH='/private/fixture/official-response-evidence/private.gz'
URL='https://example.org/official.csv'
RECEIPT={'source_url':URL,'raw_response_path':PATH,'raw_response_sha256':'f'*64,
         'retrieved_at':12345,'http_status':200,'raw_response_bytes':128}

def test_projection_keeps_public_provenance_but_never_traverses_private_path():
 class Private:
  def __deepcopy__(self,memo):pytest.fail('Excluded receipt path must not be copied')
 value={'raw_response_path':Private(),'nested':{'_RAW_RESPONSE_PATH':Private(),'source_url':URL,'raw_response_sha256':'f'*64,'canonical_path':'institutional_trading.total_net_buy_shares','text':'QUALIFIED_BODY'}}
 out=prompt_evidence_copy(value)
 assert out=={'nested':{'source_url':URL,'raw_response_sha256':'f'*64,'canonical_path':'institutional_trading.total_net_buy_shares','text':'QUALIFIED_BODY'}}

def test_model_extra_and_dataclass_receipt_paths_are_excluded():
 class Evidence(BaseModel):
  model_config=ConfigDict(extra='allow')
  source_url:str
 @dataclass
 class Receipt:
  raw_response_path:str
  source_url:str
 out=prompt_evidence_copy({'model':Evidence(source_url=URL,RAW_RESPONSE_PATH=PATH),'dataclass':Receipt(PATH,URL)})
 assert out=={'model':{'source_url':URL},'dataclass':{'source_url':URL}}

@pytest.mark.parametrize('compact,dense,role_scoped',[(False,False,False),(True,True,False),(True,True,True)])
def test_financial_json_excludes_private_paths_before_table_packing(compact,dense,role_scoped):
 data={'ticker':'2330.TW','company_name':'Boundary fixture','_prompt_agent_num':2,
       'institutional_trading':{'source_provenance':deepcopy(RECEIPT),'latest_official_observation':{'raw_evidence':deepcopy(RECEIPT)}}}
 before=deepcopy(data);text=format_data_for_prompt(data,compact=compact,dense=dense,role_scoped=role_scoped)
 assert PATH not in text and 'raw_response_path'not in text
 assert URL in text and 'f'*64 in text and '12345'in text
 assert data==before

def test_full_role_prompt_cannot_reintroduce_private_path_from_context(monkeypatch):
 from agent_runtime import prompting
 monkeypatch.setattr(prompting,'get_agent_prompt_token_budget',lambda *args,**kwargs:1000000)
 monkeypatch.setitem(prompting.ANALYSIS_PROMPTS,2,'{{ data }}\n{{ context }}\n{{ fin_data }}')
 data={'ticker':'2330.TW','company_name':'Boundary fixture','institutional_trading':{'source_provenance':deepcopy(RECEIPT)}}
 context={'analyses':{},'structured_outputs':{},'data':data,'evidence':deepcopy(RECEIPT)}
 before=deepcopy((data,context));text=prompting.build_prompt(2,data,context)
 assert PATH not in text and 'raw_response_path'not in text
 assert URL in text and 'f'*64 in text and (data,context)==before


def test_rag_collection_cannot_bypass_private_or_rejected_source_boundary():
 from rag_runtime.documents import collect_rag_documents
 data={'filing':{'title':'QUALIFIED_PUBLIC_FILING','body':{'text':'QUALIFIED_BODY','raw_response_path':PATH}},
       'identity_rejected_catalysts':[{'title':'REJECTED_ISSUER_SENTINEL','body':'WRONG_ISSUER_BODY'}]}
 before=deepcopy(data);documents=collect_rag_documents(data);encoded=str(documents)
 assert 'QUALIFIED_BODY'in encoded and PATH not in encoded
 assert 'REJECTED_ISSUER_SENTINEL'not in encoded and 'WRONG_ISSUER_BODY'not in encoded
 assert data==before

def test_rag_projection_policy_changes_namespace_without_deleting_old_cache(monkeypatch):
 import rag_runtime.service as service
 data={'ticker':'2330.TW','filing':'PUBLIC_BODY'}
 current=service._rag_index_cache_key(data)
 monkeypatch.setattr(service,'DOCUMENT_PROJECTION_POLICY','old-policy')
 legacy=service._rag_index_cache_key(data)
 assert current!=legacy
 stored={legacy:{'schema_version':1,'chunks':[{'chunk_id':'old','source':'filing','text':'OLD_BODY','metadata':{}}]}}
 before=deepcopy(stored);monkeypatch.setattr(service,'get_cache_json',lambda key:stored.get(key));monkeypatch.setattr(service,'AGENT_STEP_CACHE_ENABLED',True)
 monkeypatch.setattr(service,'DOCUMENT_PROJECTION_POLICY','public-evidence-fields-v1')
 assert service._get_cached_rag_index(data)is None and stored==before
