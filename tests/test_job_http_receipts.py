import httpx,pytest
import alternative_data_fetcher as jobs
import provider_sla

def invoke(session=None):return jobs._get_job_search_response('https://www.104.com.tw/jobs/search/api/jobs',params={'token':'secret-query'},headers={'Authorization':'secret-header'},timeout=2,provider='104 Company Jobs API',session=session)

def test_native_receipt_records_metadata_but_not_body_url_or_secrets(monkeypatch):
 entries=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:entries.extend(rows))
 response=httpx.Response(200,content=b'secret-body',request=httpx.Request('GET','https://example.com?token=secret-url'))
 monkeypatch.setattr(jobs,'sync_get',lambda *a,**k:response)
 assert invoke() is response
 assert len(entries)==1 and entries[0]['http_request_sent'] is True and entries[0]['record_count']==0
 assert entries[0]['response_bytes']==11 and len(entries[0]['response_sha256'])==64
 assert 'secret' not in str(entries)

@pytest.mark.parametrize('status',[429,504])
def test_http_failure_preserves_error_and_one_receipt(monkeypatch,status):
 entries=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:entries.extend(rows))
 response=httpx.Response(status,request=httpx.Request('GET','https://example.com'))
 def fail(*a,**k):response.raise_for_status()
 monkeypatch.setattr(jobs,'sync_get',fail)
 with pytest.raises(jobs._JobSearchTransportError):invoke()
 assert len(entries)==1 and entries[0]['http_status']==status and entries[0]['record_count']==0


def test_custom_session_does_not_invent_outward_sample(monkeypatch):
 entries=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:entries.extend(rows))
 class Session:
  def get(self,*a,**k):return httpx.Response(200,request=httpx.Request('GET','https://example.com'))
 invoke(Session());assert entries and 'http_request_sent' not in entries[0]


def test_diagnostic_failure_cannot_discard_valid_response(monkeypatch):
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:(_ for _ in ()).throw(RuntimeError('unavailable')))
 response=httpx.Response(200);monkeypatch.setattr(jobs,'sync_get',lambda *a,**k:response)
 assert invoke() is response
