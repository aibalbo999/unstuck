"""Independent virtual-wire timing boundaries; no actual HTTP or sleep."""
from hashlib import sha256
import time
import pytest
from test_mops_material_transport import offline, descriptor, wire, PDF
import mops_material_transport as transport
from search_provider_runtime import SourceResponseError
from test_mops_pptx_mime_review import RAW, selected, native_result


def install_wire(monkeypatch, response, duration):
    clock=[100.0];calls=[]
    monkeypatch.setattr(time,'monotonic',lambda:clock[0])
    def collect(args,stop,**kwargs):
        calls.append((args,stop,kwargs))
        clock[0]+=duration
        return response
    monkeypatch.setattr(transport,'collect_capped_process',collect)
    return clock,calls


@pytest.mark.parametrize('fmt,duration',[('pptx',6.0),('pptx',9.9),('pdf',6.0)])
def test_slow_complete_material_is_accepted_with_only_body_budget_changed(offline,monkeypatch,fmt,duration):
    spec=selected() if fmt=='pptx' else descriptor()
    raw=RAW if fmt=='pptx' else PDF
    _,calls=install_wire(monkeypatch,native_result() if fmt=='pptx' else wire(),duration)
    diagnostic={}
    assert transport.download_published_material(spec,deadline=125.0,diagnostics=diagnostic)==raw
    assert diagnostic['response_complete'] and diagnostic['response_sha256']==sha256(raw).hexdigest()
    assert len(calls)==1 and calls[0][1]==110.0 and calls[0][2]['body_limit']==16*1024*1024
    args=calls[0][0]
    for option,value in [('--max-time','10.0'),('--connect-timeout','2.0'),('--max-redirs','0'),('--retry','0')]:
        assert args[args.index(option)+1]==value
    assert '--location' not in args


@pytest.mark.parametrize('deadline,duration,stop',[(125.0,10.0,110.0),(125.0,10.1,110.0),(103.0,3.0,103.0)])
def test_body_never_exceeds_own_or_shorter_caller_deadline(offline,monkeypatch,deadline,duration,stop):
    _,calls=install_wire(monkeypatch,native_result(),duration)
    diagnostic={}
    with pytest.raises(SourceResponseError) as error:
        transport.download_published_material(selected(),deadline=deadline,diagnostics=diagnostic)
    assert error.value.error_kind=='timeout' and error.value.status_code==200
    assert len(calls)==1 and calls[0][1]==stop
    assert diagnostic['response_complete'] is False and diagnostic['http_request_sent'] is True
    assert diagnostic['response_sha256']==sha256(RAW).hexdigest()


def test_six_second_index_remains_rejected_at_original_five_second_bound(offline,monkeypatch):
    raw=b'<html><body>Complete index</body></html>'
    response=wire(raw,ctype='text/html',meta_changes={'url_effective':transport.INDEX_URL})
    _,calls=install_wire(monkeypatch,response,6.0)
    diagnostic={}
    with pytest.raises(SourceResponseError) as error:
        transport.download_conference_index('1229.TW',year=2026,deadline=125.0,diagnostics=diagnostic)
    assert error.value.error_kind=='timeout'
    assert len(calls)==1 and calls[0][1]==105.0 and calls[0][2]['body_limit']==1024*1024
    assert diagnostic['response_complete'] is False and diagnostic['http_status']==200


@pytest.mark.parametrize('valid',[True,False])
def test_late_validation_still_rejects_even_when_wire_completed_in_time(offline,monkeypatch,valid):
    clock,calls=install_wire(monkeypatch,native_result(),9.0)
    real=transport.validate_response_metadata
    def slow(meta,raw,spec):
        assert real(meta,raw,spec)
        clock[0]=110.0
        return valid
    monkeypatch.setattr(transport,'validate_response_metadata',slow)
    diagnostic={}
    with pytest.raises(SourceResponseError) as error:
        transport.download_published_material(selected(),deadline=125.0,diagnostics=diagnostic)
    assert error.value.error_kind=='timeout' and len(calls)==1
    assert diagnostic['response_complete'] is False


def test_partial_body_at_timeout_keeps_bytes_and_http_truth_without_retry(offline,monkeypatch):
    response=native_result(raw=RAW[:3293184]);response=(response[0],28,None)
    _,calls=install_wire(monkeypatch,response,10.0)
    diagnostic={}
    with pytest.raises(SourceResponseError) as error:
        transport.download_published_material(selected(),deadline=125.0,diagnostics=diagnostic)
    assert error.value.error_kind=='timeout' and len(calls)==1
    assert diagnostic['response_complete'] is False and diagnostic['http_request_sent'] is True
    assert diagnostic['response_bytes']==3293184 and diagnostic['http_status']==200
    assert diagnostic['response_sha256']==sha256(RAW[:3293184]).hexdigest()


def test_complete_public_presentation_above_8mb_fits_the_bounded_pdf_reader_limit(offline,monkeypatch):
    raw=PDF+b'0'*(8*1024*1024+1)
    response=wire(raw)
    _,calls=install_wire(monkeypatch,response,1.0)
    diagnostic={}
    accepted=transport.download_published_material(descriptor(),deadline=125.0,diagnostics=diagnostic)
    assert accepted==raw and diagnostic['response_complete'] is True
    assert diagnostic['response_bytes']==len(raw)
    assert len(calls)==1 and calls[0][2]['body_limit']==16*1024*1024
