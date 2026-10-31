"""Public transport behavior; all subprocesses and HTTP observation are stubbed."""
from pathlib import Path
import hashlib,io,json,sys,time,zipfile
from urllib.parse import urlencode
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import mops_material_transport as transport
from search_provider_runtime import SourceResponseError

PDF=b'%PDF-1.7\ncomplete fixture\n%%EOF\n'

def descriptor(symbol='2330',suffix='.TW',fmt='pdf',filename=None):
 filename=filename or f'{symbol}20260716E001.{fmt}'
 body=urlencode([('step','9'),('filePath','/home/html/nas/STR/'),('fileName',filename),('functionName','t100sb02_1')])
 result={'url':transport.DOWNLOAD_URL,'method':'POST','request_body':body,'ticker':symbol+suffix,'symbol':symbol,'filename':filename,'format':fmt,'row_date':'2026-09-14'}
 result['request_sha256']=hashlib.sha256(('POST\n'+result['url']+'\n'+body).encode('ascii')).hexdigest()
 return result

def wire(raw=PDF,*,status=200,ctype='application/pdf',meta_changes=None,extra_headers=b'',rc=0,error=None,started=True):
 meta={'http_code':status,'url_effective':transport.DOWNLOAD_URL,'num_redirects':0,'size_download':len(raw),'content_type':ctype,'method':'POST','proxy_used':0}
 meta.update(meta_changes or {})
 headers=f'HTTP/1.1 {status} status\r\nContent-Type: {ctype}\r\nContent-Length: {len(raw)}\r\n'.encode()+extra_headers+b'\r\n'
 return {'body':raw,'headers':headers,'metadata':json.dumps(meta).encode(),'process_started':started,'body_bytes_read':len(raw)},rc,error

@pytest.fixture
def offline(monkeypatch):
 for key in ('STOCK_AGENT_TEST_NO_NETWORK','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
  monkeypatch.delenv(key,raising=False)
 monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
 calls=[];observations=[]
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:calls.append((a,k)) or wire())
 monkeypatch.setattr(transport,'observe_http_response',observations.append)
 return calls,observations

@pytest.mark.parametrize('change',[
 {'filename':'230320260716E001.pdf'}, {'method':'GET'},
 {'url':'https://example.com/server-java/FileDownLoad'}, {'request_sha256':'0'*64},
])
def test_invalid_descriptor_never_starts_subprocess(offline,change):
 d=descriptor();d.update(change);diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(d,deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind=='transport_request_invalid' and offline[0]==[]
 assert diag['http_request_sent'] is False and diag['response_complete'] is False

def test_exact_post_returns_full_body_and_complete_metadata(offline):
 d=descriptor();diag={}
 assert transport.download_published_material(d,deadline=time.monotonic()+20,diagnostics=diag)==PDF
 args=offline[0][0][0][0]
 assert args[0]=='/usr/bin/curl' and args[args.index('--data')+1]==d['request_body'] and args[-1]==d['url']
 assert diag['http_request_sent'] is True and diag['response_complete'] is True
 assert diag['response_sha256']==hashlib.sha256(PDF).hexdigest() and diag['response_bytes']==len(PDF)
 assert diag['response_metadata']['method']=='POST' and diag['response_metadata']['proxy_used']==0
 assert transport.validate_response_metadata(diag['response_metadata'],PDF,d) is True
 assert len(offline[1])==1 and offline[1][0].status_code==200

@pytest.mark.parametrize('change,kind',[
 ({'meta_changes':{'method':'GET'}},'transport_metadata_invalid'),
 ({'meta_changes':{'size_download':len(PDF)+1}},'transport_metadata_invalid'),
 ({'raw':b'<html>Just a moment</html>','ctype':'application/pdf'},'access_denied'),
 ({'extra_headers':b'Content-Length: 1\r\n'},'transport_metadata_invalid'),
 ({'rc':18},'transport_error'),
])
def test_incomplete_or_colliding_post_never_becomes_full_original(monkeypatch,offline,change,kind):
 response=wire(**change);monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind==kind and diag['http_request_sent'] is True
 assert diag['response_complete'] is False and diag['response_sha256']==hashlib.sha256(response[0]['body']).hexdigest()
 assert diag['http_status']==200 and e.value.diagnostic['response_bytes']==len(response[0]['body'])

def test_expired_workflow_never_starts_HTTP(offline):
 diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()-1,diagnostics=diag)
 assert e.value.error_kind=='timeout' and offline[0]==[] and diag['http_request_sent'] is False

def test_late_false_metadata_validation_is_timeout_not_fallback_error(monkeypatch,offline):
 clock=[100.]
 monkeypatch.setattr(transport.time,'monotonic',lambda:clock[0])
 def slow_validation(*a):clock[0]=111.;return False
 monkeypatch.setattr(transport,'validate_response_metadata',slow_validation)
 diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=125.,diagnostics=diag)
 assert e.value.error_kind=='timeout' and e.value.status_code==200
 assert diag['http_request_sent'] is True and diag['response_complete'] is False
 assert e.value.diagnostic['response_sha256']==hashlib.sha256(PDF).hexdigest()

def test_malformed_huge_content_length_remains_typed_with_HTTP_truth(monkeypatch,offline):
 parts,rc,error=wire();parts['headers']=b'HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\nContent-Length: '+b'9'*4500+b'\r\n\r\n'
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:(parts,rc,error));diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind=='transport_metadata_invalid' and e.value.status_code==200
 assert diag['http_request_sent'] is True and diag['response_complete'] is False
 assert diag['response_sha256']==hashlib.sha256(PDF).hexdigest()

@pytest.mark.parametrize('ticker,market',[('2330.TW','sii'),('2480.TW','sii'),('6257.TWO','otc')])
def test_index_uses_exact_market_year_POST_and_1MiB_cap(monkeypatch,offline,ticker,market):
 d=transport.index_request(ticker,2026)
 expected=urlencode([('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('TYPEK',market),('co_id',ticker.split('.')[0]),('year','115'),('month','')])
 assert d['request_body']==expected and d['format']=='html'
 assert d['request_sha256']==hashlib.sha256(('POST\n'+transport.INDEX_URL+'\n'+expected).encode('ascii')).hexdigest()
 raw=b'<!DOCTYPE html><html><title>MOPS public index</title><body>complete index</body></html>'
 response=wire(raw,ctype='text/html',meta_changes={'url_effective':transport.INDEX_URL})
 calls=[]
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:calls.append((a,k)) or response)
 diag={};assert transport.download_conference_index(ticker,year=2026,deadline=time.monotonic()+20,diagnostics=diag)==raw
 assert calls[0][1]['body_limit']==1024*1024 and diag['response_complete'] is True
 assert calls[0][0][0][calls[0][0][0].index('--data')+1]==expected
 assert transport.validate_response_metadata(diag['response_metadata'],raw,d) is True

@pytest.mark.parametrize('ticker,year',[('2330',2026),('2330.US',2026),('2330.TW',True),('2330.TW',1911),('2330.TWO',10000)])
def test_invalid_index_identity_or_year_never_starts_HTTP(offline,ticker,year):
 diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_conference_index(ticker,year=year,deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind=='transport_request_invalid' and offline[0]==[] and diag['http_request_sent'] is False

@pytest.mark.parametrize('filename',['233020260230E001.pdf','233020261332E001.pdf','233019110101E001.pdf','233020260716e001.pdf','233020260716E0001.pdf','233020260716E001.PDF'])
def test_file_calendar_and_extension_fail_before_HTTP(offline,filename):
 diag={}
 with pytest.raises(SourceResponseError):transport.download_published_material(descriptor(filename=filename),deadline=time.monotonic()+20,diagnostics=diag)
 assert offline[0]==[] and diag['http_request_sent'] is False

@pytest.mark.parametrize('edit',[
 lambda b:b.replace('step=9','step=8'),lambda b:b.replace('filePath=%2Fhome','filePath=%2fhome'),
 lambda b:b+'&step=9',lambda b:'&'.join(reversed(b.split('&'))),lambda b:b.replace('t100sb02_1','other'),
])
def test_rehashed_but_noncanonical_or_wrong_form_is_rejected(offline,edit):
 d=descriptor();d['request_body']=edit(d['request_body']);d['request_sha256']=hashlib.sha256(('POST\n'+d['url']+'\n'+d['request_body']).encode('ascii')).hexdigest()
 diag={}
 with pytest.raises(SourceResponseError):transport.download_published_material(d,deadline=time.monotonic()+20,diagnostics=diag)
 assert offline[0]==[]

def test_material_validator_preserves_additional_provenance_fields_without_mutating():
 d=descriptor();copy=dict(d);validated=transport.validate_download_request(d)
 assert validated==copy and d==copy and validated is not d

@pytest.mark.parametrize('meta_changes',[
 {'http_code':False},{'url_effective':transport.DOWNLOAD_URL+'?issuer=other'},
 {'num_redirects':1},{'num_redirects':False},{'proxy_used':1},{'proxy_used':False},
 {'size_download':float('nan')},{'size_download':True},{'content_type':'text/html'},
])
def test_native_metadata_mismatch_retains_wire_status_and_body(monkeypatch,offline,meta_changes):
 response=wire(meta_changes=meta_changes);monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind=='transport_metadata_invalid' and e.value.status_code==200
 assert diag['response_complete'] is False and diag['response_sha256']==hashlib.sha256(PDF).hexdigest()

@pytest.mark.parametrize('header',[
 b'Content-Type: application/pdf\r\n',b'content-encoding: identity\r\nContent-Encoding: identity\r\n',
 b'Retry-After: 1\r\nretry-after: 1\r\n',b'Content-Length: +33\r\n',
])
def test_ambiguous_protected_headers_are_rejected(monkeypatch,offline,header):
 response=wire(extra_headers=header);monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind=='transport_metadata_invalid' and diag['http_status']==200
 assert diag['response_complete'] is False

@pytest.mark.parametrize('status,kind',[(401,'authentication'),(403,'access_denied'),(429,'rate_limited'),(503,'server_error')])
def test_refusal_HTTP_and_full_error_body_survive_in_exception(monkeypatch,offline,status,kind):
 raw=b'<html>upstream refused</html>';response=wire(raw,status=status,ctype='text/html',extra_headers=b'Retry-After: 30\r\n')
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response);diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind==kind and e.value.status_code==status and diag['http_status']==status
 assert e.value.response.headers['retry-after']=='30' and offline[1][0].status_code==status
 assert diag['response_bytes']==len(raw) and e.value.diagnostic['response_sha256']==hashlib.sha256(raw).hexdigest()
 assert diag['response_complete'] is False

@pytest.mark.parametrize('env',['HTTP_PROXY','https_proxy','ALL_PROXY'])
def test_proxy_environment_blocked_before_subprocess(monkeypatch,offline,env):
 monkeypatch.setenv(env,'http://proxy.invalid:8080');diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind=='proxy_configuration_unsupported' and offline[0]==[]

def test_provider_proxy_and_test_network_guard_block_before_HTTP(monkeypatch,offline):
 monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:'http://configured-proxy.invalid')
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics={})
 assert e.value.error_kind=='proxy_configuration_unsupported' and offline[0]==[]
 monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','1')
 with pytest.raises(SourceResponseError) as e:transport.download_conference_index('2330.TW',year=2026,deadline=time.monotonic()+20,diagnostics={})
 assert e.value.error_kind=='test_network_disabled' and offline[0]==[]

def pptx():
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w') as z:
  z.writestr('[Content_Types].xml','<Types/>');z.writestr('ppt/presentation.xml','<presentation/>')
 return stream.getvalue()

@pytest.mark.parametrize('fmt,ctype,raw',[('pdf','application/octet-stream',PDF),('pptx',transport.PPTX_TYPE,pptx()),('pptx','application/octet-stream',pptx())])
def test_expected_native_mime_or_octet_package_signature_is_accepted(monkeypatch,offline,fmt,ctype,raw):
 response=wire(raw,ctype=ctype);monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 d=descriptor(fmt=fmt);diag={}
 assert transport.download_published_material(d,deadline=time.monotonic()+20,diagnostics=diag)==raw
 assert transport.validate_response_metadata(diag['response_metadata'],raw,d) is True

@pytest.mark.parametrize('fmt,raw',[('pdf',b'<html>empty upstream</html>'),('pptx',b'PK\x03\x04not a complete package'),('pptx',PDF)])
def test_declared_MIME_cannot_promote_wrong_or_truncated_signature(monkeypatch,offline,fmt,raw):
 response=wire(raw,ctype='application/octet-stream');monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 with pytest.raises(SourceResponseError):transport.download_published_material(descriptor(fmt=fmt),deadline=time.monotonic()+20,diagnostics={})

def test_exact_time_limit_includes_response_observation_and_native_error(monkeypatch,offline):
 clock=[100.];monkeypatch.setattr(transport.time,'monotonic',lambda:clock[0])
 def observed(response):clock[0]=110.
 monkeypatch.setattr(transport,'observe_http_response',observed)
 diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=200.,diagnostics=diag)
 assert e.value.error_kind=='timeout' and e.value.status_code==200 and diag['response_complete'] is False
 clock[0]=100.
 response=wire(status=503,rc=28,error='timeout');monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=102.,diagnostics=diag)
 assert e.value.error_kind=='timeout' and e.value.status_code==503

@pytest.mark.parametrize('deadline',[True,float('nan'),float('inf'),None])
def test_nonfinite_or_non_numeric_deadline_rejected_without_HTTP(offline,deadline):
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=deadline,diagnostics={})
 assert e.value.error_kind=='transport_deadline_invalid' and offline[0]==[]

def test_complete_response_without_length_header_and_actual_research_bytes(monkeypatch,offline):
 D=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261014/remaining-gap-next/largecap-conference'
 raw=(D/'tsmc-mops-presentation.body').read_bytes();assert hashlib.sha256(raw).hexdigest()=='c9f2e4685f8eb978f1f6d9f5aa657d899251d6d8515bedd77d27685e0ced3471'
 response=wire(raw);response[0]['headers']=(D/'tsmc-mops-presentation.headers').read_bytes()
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response);diag={}
 assert transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics=diag)==raw
 assert diag['response_metadata']['content_length'] is None and diag['response_complete'] is True


def test_nonASCII_protected_header_fails_typed_without_losing_status(monkeypatch,offline):
 response=wire(extra_headers=b'Retry-After: \xff\r\n');monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response);diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind=='transport_metadata_invalid' and e.value.status_code==200
 assert diag['response_sha256']==hashlib.sha256(PDF).hexdigest() and diag['response_complete'] is False

def test_security_words_inside_native_PDF_are_not_an_HTML_challenge(monkeypatch,offline):
 raw=b'%PDF-1.7\n(Captcha and access denied are product interface examples)\n%%EOF\n'
 response=wire(raw);monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response);diag={}
 assert transport.download_published_material(descriptor(),deadline=time.monotonic()+20,diagnostics=diag)==raw
 assert diag['response_complete'] is True

@pytest.mark.parametrize('change',[
 {'http_status':True},{'content_length':True},{'content_length':999},
 {'content_type':[]},{'method':'GET'},{'proxy_used':True},{'size_download':float('inf')},
])
def test_pure_replay_metadata_rejects_tampering_without_HTTP_or_observation(offline,change):
 meta={'http_status':200,'effective_url':transport.DOWNLOAD_URL,'num_redirects':0,'size_download':len(PDF),'content_type':'application/pdf','content_length':len(PDF),'method':'POST','proxy_used':0}
 meta.update(change)
 assert transport.validate_response_metadata(meta,PDF,descriptor()) is False
 assert offline[0]==[] and offline[1]==[]


def test_wrong_PPTX_zip_with_unrelated_members_is_not_package_signature(monkeypatch,offline):
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w') as z:z.writestr('other.xml','<notPowerPoint/>')
 response=wire(stream.getvalue(),ctype='application/octet-stream')
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 with pytest.raises(SourceResponseError):transport.download_published_material(descriptor(fmt='pptx'),deadline=time.monotonic()+20,diagnostics={})

LIENHWA_ORIGINAL_SHA='4ab60e7e57d57255e9d93ffcf25e54bab12db5e3718086000ae956a057ba160c'
LIENHWA_FIXTURE=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261014/remaining-gap-next/lienhwa'

def test_actual_blank_mime_PPTX_with_exact_disposition_passes_wire_and_native_reader(monkeypatch,offline):
 raw=(LIENHWA_FIXTURE/'lienhwa-mops-presentation.body').read_bytes()
 assert len(raw)==3883370 and hashlib.sha256(raw).hexdigest()==LIENHWA_ORIGINAL_SHA
 native=json.loads((LIENHWA_FIXTURE/'lienhwa-mops-presentation.curl-meta.json').read_text())
 parts={'body':raw,'headers':(LIENHWA_FIXTURE/'lienhwa-mops-presentation.headers').read_bytes(),'metadata':json.dumps(native).encode(),'process_started':True,'body_bytes_read':len(raw)}
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:(parts,0,None))
 d=descriptor('1229',fmt='pptx',filename='122920260930E001.pptx');diag={}
 assert transport.download_published_material(d,deadline=time.monotonic()+20,diagnostics=diag)==raw
 meta=diag['response_metadata']
 assert meta['content_type']=='' and meta['content_disposition']=='attachment; filename="122920260930E001.pptx"'
 assert set(meta)==transport.META_FIELDS|{'content_disposition'}
 assert transport.validate_response_metadata(meta,raw,d) is True
 assert diag['response_complete'] is True and diag['response_sha256']==LIENHWA_ORIGINAL_SHA
 # The MIME exception does not replace the existing isolated native reader.
 monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','1')
 from source_pptx_reader import extract_pptx_pages
 native_result=extract_pptx_pages(raw)
 assert native_result['content_sha256']==LIENHWA_ORIGINAL_SHA
 assert native_result['total_slide_count']==32 and native_result['page_count']==30
 assert native_result['hidden_pages']==[31,32] and native_result['coverage_status']=='partial'

@pytest.mark.parametrize('disposition_headers',[
 b'Content-Disposition: attachment; filename="233020260716E001.pptx"\r\ncontent-disposition: attachment; filename="233020260716E001.pptx"\r\n',
 b'Content-Disposition: attachment; filename="\xff.pptx"\r\n',
])
def test_content_disposition_protected_even_for_normal_MIME(monkeypatch,offline,disposition_headers):
 raw=pptx();response=wire(raw,ctype=transport.PPTX_TYPE,extra_headers=disposition_headers)
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response);diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(fmt='pptx'),deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind=='transport_metadata_invalid' and diag['http_status']==200
 assert diag['response_complete'] is False and diag['response_sha256']==hashlib.sha256(raw).hexdigest()

@pytest.mark.parametrize('disposition',[
 None,'attachment; filename="230320260716E001.pptx"','inline; filename="233020260716E001.pptx"',
 'attachment; filename="../../233020260716E001.pptx"','attachment; filename="233020260716E001.pdf"',
 'attachment; filename="233020260716E001.pptx"; filename="other.pptx"',
 'attachment; filename="233020260716E001.pptx"; filename*=utf-8\'\'233020260716E001.pptx',
])
def test_blank_PPTX_MIME_requires_only_exact_published_attachment_filename(monkeypatch,offline,disposition):
 headers=b'' if disposition is None else f'Content-Disposition: {disposition}\r\n'.encode()
 response=wire(pptx(),ctype='; charset=iso-8859-1',extra_headers=headers)
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response);diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(fmt='pptx'),deadline=time.monotonic()+20,diagnostics=diag)
 assert e.value.error_kind=='transport_metadata_invalid' and diag['http_status']==200 and diag['response_complete'] is False


def test_normal_PPTX_MIME_retains_legacy_8_metadata_fields(monkeypatch,offline):
 raw=pptx();response=wire(raw,ctype=transport.PPTX_TYPE,extra_headers=b'Content-Disposition: attachment; filename="233020260716E001.pptx"\r\n')
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response);diag={};d=descriptor(fmt='pptx')
 assert transport.download_published_material(d,deadline=time.monotonic()+20,diagnostics=diag)==raw
 assert set(diag['response_metadata'])==transport.META_FIELDS
 assert transport.validate_response_metadata(diag['response_metadata'],raw,d) is True

@pytest.mark.parametrize('fmt,raw',[('pdf',PDF),('html',b'<html>complete public index</html>')])
def test_blank_MIME_is_not_permitted_for_PDF_or_index(monkeypatch,offline,fmt,raw):
 spec=descriptor() if fmt=='pdf' else transport.index_request('2330.TW',2026)
 response=wire(raw,ctype='; charset=iso-8859-1',extra_headers=b'Content-Disposition: attachment; filename="233020260716E001.pdf"\r\n',meta_changes={'url_effective':spec['url']})
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response);diag={}
 with pytest.raises(SourceResponseError):
  if fmt=='pdf':transport.download_published_material(spec,deadline=time.monotonic()+20,diagnostics=diag)
  else:transport.download_conference_index('2330.TW',year=2026,deadline=time.monotonic()+20,diagnostics=diag)
 assert diag['response_complete'] is False

@pytest.mark.parametrize('raw',[b'<html>upstream document missing</html>',b'PK\x03\x04truncated',PDF])
def test_blank_MIME_exact_disposition_does_not_replace_package_signature(monkeypatch,offline,raw):
 response=wire(raw,ctype='',extra_headers=b'Content-Disposition: attachment; filename="233020260716E001.pptx"\r\n')
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 with pytest.raises(SourceResponseError):transport.download_published_material(descriptor(fmt='pptx'),deadline=time.monotonic()+20,diagnostics={})


def test_blank_MIME_replay_requires_ninth_field_and_cannot_change_regular_metadata_schema(offline):
 raw=pptx();spec=descriptor(fmt='pptx')
 meta={'http_status':200,'effective_url':transport.DOWNLOAD_URL,'num_redirects':0,'size_download':len(raw),'content_type':'','content_length':len(raw),'method':'POST','proxy_used':0}
 assert transport.validate_response_metadata(meta,raw,spec) is False
 meta['content_disposition']='attachment; filename="233020260716E001.pptx"'
 assert transport.validate_response_metadata(meta,raw,spec) is True
 for value in (None,True,'attachment; filename="230320260716E001.pptx"'):
  bad={**meta,'content_disposition':value};assert transport.validate_response_metadata(bad,raw,spec) is False
 normal={**meta,'content_type':transport.PPTX_TYPE}
 assert transport.validate_response_metadata(normal,raw,spec) is False
 normal.pop('content_disposition');assert transport.validate_response_metadata(normal,raw,spec) is True
 assert offline[0]==[] and offline[1]==[]


def test_missing_or_inconsistent_native_blank_MIME_metadata_is_not_attested(monkeypatch,offline):
 raw=pptx();response=wire(raw,ctype='',extra_headers=b'Content-Disposition: attachment; filename="233020260716E001.pptx"\r\n')
 native=json.loads(response[0]['metadata']);native.pop('content_type');response[0]['metadata']=json.dumps(native).encode()
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 with pytest.raises(SourceResponseError):transport.download_published_material(descriptor(fmt='pptx'),deadline=time.monotonic()+20,diagnostics={})
 native['content_type']='application/pdf';response[0]['metadata']=json.dumps(native).encode()
 with pytest.raises(SourceResponseError):transport.download_published_material(descriptor(fmt='pptx'),deadline=time.monotonic()+20,diagnostics={})


def test_missing_content_type_header_does_not_receive_blank_MIME_exception(monkeypatch,offline):
 raw=pptx();response=wire(raw,ctype='',extra_headers=b'Content-Disposition: attachment; filename="233020260716E001.pptx"\r\n')
 response[0]['headers']=response[0]['headers'].replace(b'Content-Type: \r\n',b'')
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response)
 with pytest.raises(SourceResponseError):transport.download_published_material(descriptor(fmt='pptx'),deadline=time.monotonic()+20,diagnostics={})


def test_blank_PPTX_MIME_does_not_bypass_invalid_native_package_gate(monkeypatch,offline):
 raw=pptx();d=descriptor(fmt='pptx')
 response=wire(raw,ctype='',extra_headers=b'Content-Disposition: attachment; filename="233020260716E001.pptx"\r\n')
 monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:response);diag={}
 accepted=transport.download_published_material(d,deadline=time.monotonic()+20,diagnostics=diag)
 assert accepted==raw and diag['response_complete'] is True
 monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','1')
 from source_pptx_reader import extract_pptx_pages,SourcePptxError
 with pytest.raises(SourcePptxError):extract_pptx_pages(accepted)

@pytest.mark.parametrize('fmt',['pdf','pptx'])
def test_material_body_budget_accepts_complete_six_second_response(monkeypatch,offline,fmt):
 clock=[100.];monkeypatch.setattr(transport.time,'monotonic',lambda:clock[0])
 raw=PDF if fmt=='pdf' else pptx();response=wire(raw,ctype='application/pdf' if fmt=='pdf' else transport.PPTX_TYPE)
 captured=[]
 def complete_after_six(args,stop,**kwargs):
  captured.append((args,stop,kwargs));clock[0]=106.;return response
 monkeypatch.setattr(transport,'collect_capped_process',complete_after_six);diag={}
 assert transport.download_published_material(descriptor(fmt=fmt),deadline=125.,diagnostics=diag)==raw
 args,stop,kwargs=captured[0]
 assert stop==110. and float(args[args.index('--max-time')+1])==10.
 assert float(args[args.index('--connect-timeout')+1])==2. and kwargs['body_limit']==16*1024*1024
 assert args[args.index('--retry')+1]=='0' and args[args.index('--max-redirs')+1]=='0'
 assert diag['http_status']==200 and diag['http_request_sent'] is True and diag['response_complete'] is True
 assert diag['response_sha256']==hashlib.sha256(raw).hexdigest()

@pytest.mark.parametrize('fmt',['pdf','pptx'])
def test_material_body_budget_rejects_exact_ten_second_completion(monkeypatch,offline,fmt):
 clock=[100.];monkeypatch.setattr(transport.time,'monotonic',lambda:clock[0])
 raw=PDF if fmt=='pdf' else pptx();response=wire(raw,ctype='application/pdf' if fmt=='pdf' else transport.PPTX_TYPE)
 captured=[]
 def complete_at_ten(args,stop,**kwargs):
  captured.append(stop);clock[0]=110.;return response
 monkeypatch.setattr(transport,'collect_capped_process',complete_at_ten);diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(fmt=fmt),deadline=125.,diagnostics=diag)
 assert captured==[110.] and e.value.error_kind=='timeout' and e.value.status_code==200
 assert diag['http_request_sent'] is True and diag['response_complete'] is False
 assert e.value.diagnostic['response_bytes']==len(raw) and e.value.diagnostic['response_sha256']==hashlib.sha256(raw).hexdigest()

@pytest.mark.parametrize('fmt',['pdf','pptx'])
def test_material_body_budget_preserves_shorter_three_second_caller_deadline(monkeypatch,offline,fmt):
 clock=[100.];monkeypatch.setattr(transport.time,'monotonic',lambda:clock[0])
 raw=PDF if fmt=='pdf' else pptx();response=wire(raw,ctype='application/pdf' if fmt=='pdf' else transport.PPTX_TYPE)
 captured=[]
 def complete_at_three(args,stop,**kwargs):
  captured.append((args,stop));clock[0]=103.;return response
 monkeypatch.setattr(transport,'collect_capped_process',complete_at_three);diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(descriptor(fmt=fmt),deadline=103.,diagnostics=diag)
 assert captured[0][1]==103. and float(captured[0][0][captured[0][0].index('--max-time')+1])==3.
 assert float(captured[0][0][captured[0][0].index('--connect-timeout')+1])==2.
 assert e.value.error_kind=='timeout' and diag['http_status']==200 and diag['response_complete'] is False
 assert e.value.diagnostic['response_sha256']==hashlib.sha256(raw).hexdigest()


def test_index_body_budget_stays_five_seconds_and_keeps_HTTP_truth(monkeypatch,offline):
 clock=[100.];monkeypatch.setattr(transport.time,'monotonic',lambda:clock[0])
 raw=b'<html>complete public conference index</html>'
 response=wire(raw,ctype='text/html',meta_changes={'url_effective':transport.INDEX_URL});captured=[]
 def complete_at_five(args,stop,**kwargs):
  captured.append((args,stop,kwargs));clock[0]=105.;return response
 monkeypatch.setattr(transport,'collect_capped_process',complete_at_five);diag={}
 with pytest.raises(SourceResponseError) as e:transport.download_conference_index('1229.TW',year=2026,deadline=125.,diagnostics=diag)
 args,stop,kwargs=captured[0]
 assert stop==105. and float(args[args.index('--max-time')+1])==5.
 assert float(args[args.index('--connect-timeout')+1])==2. and kwargs['body_limit']==1024*1024
 assert e.value.error_kind=='timeout' and diag['http_status']==200 and diag['response_complete'] is False
 assert e.value.diagnostic['response_bytes']==len(raw) and e.value.diagnostic['response_sha256']==hashlib.sha256(raw).hexdigest()


def test_material_body_budget_preserves_partial_saved_original_HTTP_diagnostics(monkeypatch,offline):
 clock=[100.];monkeypatch.setattr(transport.time,'monotonic',lambda:clock[0])
 full=(LIENHWA_FIXTURE/'lienhwa-mops-presentation.body').read_bytes()
 assert hashlib.sha256(full).hexdigest()==LIENHWA_ORIGINAL_SHA
 # A bounded prefix of the saved original models the measured partial-byte
 # count; its hash is not asserted to be the formal event's unknown prefixhash.
 partial=full[:3293184];native=json.loads((LIENHWA_FIXTURE/'lienhwa-mops-presentation.curl-meta.json').read_text());native['size_download']=len(partial)
 parts={'body':partial,'headers':(LIENHWA_FIXTURE/'lienhwa-mops-presentation.headers').read_bytes(),'metadata':json.dumps(native).encode(),'process_started':True,'body_bytes_read':len(partial)}
 captured=[]
 def stopped_at_ten(args,stop,**kwargs):
  captured.append(stop);clock[0]=110.;return parts,28,'timeout'
 monkeypatch.setattr(transport,'collect_capped_process',stopped_at_ten);diag={}
 d=descriptor('1229',fmt='pptx',filename='122920260930E001.pptx')
 with pytest.raises(SourceResponseError) as e:transport.download_published_material(d,deadline=125.,diagnostics=diag)
 assert captured==[110.] and e.value.error_kind=='timeout' and e.value.status_code==200
 assert diag['response_complete'] is False and diag['http_request_sent'] is True
 assert diag['response_bytes']==3293184 and diag['response_sha256']==hashlib.sha256(partial).hexdigest()
 assert e.value.diagnostic['response_metadata']['content_disposition']=='attachment; filename="122920260930E001.pptx"'
