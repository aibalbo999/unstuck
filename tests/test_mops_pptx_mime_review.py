"""Independent exact native-header replay; no actual subprocess or provider I/O."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import json
import time
import pytest

from test_mops_material_transport import offline, descriptor, PDF
import mops_material_transport as transport
from search_provider_runtime import SourceResponseError

ROOT = Path(__file__).parents[1]
D = ROOT / 'docs/evidence/source-acquisition/20261014/remaining-gap-next/lienhwa'
RAW = (D / 'lienhwa-mops-presentation.body').read_bytes()
HEADERS = (D / 'lienhwa-mops-presentation.headers').read_bytes()
META = json.loads((D / 'lienhwa-mops-presentation.curl-meta.json').read_text())
FILENAME = '122920260930E001.pptx'
DISPOSITION = 'attachment; filename="' + FILENAME + '"'


def selected():
    from mops_published_materials import select_published_material
    return select_published_material((D / 'lienhwa-mops-index.body').read_bytes(),
                                     '1229.TW', as_of_epoch=1791932179.488388,
                                     company_name='聯華')


def native_result(*, raw=RAW, headers=HEADERS, meta=None):
    return {'body': raw, 'headers': headers, 'metadata': json.dumps(META if meta is None else meta).encode(),
            'process_started': True, 'body_bytes_read': len(raw)}, 0, None


def test_exact_saved_blank_mime_headers_admit_complete_published_original(offline, monkeypatch):
    calls = []
    def run(*a, **kw):
        calls.append((a, kw))
        return native_result()
    monkeypatch.setattr(transport, 'collect_capped_process', run)
    diag = {}
    raw = transport.download_published_material(selected(), deadline=time.monotonic()+20, diagnostics=diag)
    assert raw == RAW and sha256(raw).hexdigest() == '4ab60e7e57d57255e9d93ffcf25e54bab12db5e3718086000ae956a057ba160c'
    assert diag['response_complete'] is True and diag['http_request_sent'] is True
    assert diag['response_metadata']['content_type'] == ''
    assert diag['response_metadata']['content_disposition'] == DISPOSITION
    assert transport.validate_response_metadata(diag['response_metadata'], RAW, selected())
    assert len(calls) == 1 and calls[0][1]['body_limit'] == 16*1024*1024
    args = calls[0][0][0]
    assert args[args.index('--retry')+1] == '0' and args[args.index('--max-redirs')+1] == '0'
    assert float(args[args.index('--max-time')+1]) <= 10
    assert float(args[args.index('--connect-timeout')+1]) <= 2


@pytest.mark.parametrize('disposition', [None, '', 'inline; filename="'+FILENAME+'"',
    'attachment; filename="233020260716E001.pptx"',
    'attachment; filename="../'+FILENAME+'"',
    'attachment; filename="'+FILENAME+'"; filename="other.pptx"',
    "attachment; filename*=UTF-8''"+FILENAME])
def test_cached_blank_mime_requires_exact_published_filename_binding(disposition):
    meta = {'http_status':200,'effective_url':transport.DOWNLOAD_URL,'num_redirects':0,
            'size_download':len(RAW),'content_type':'','content_length':None,'method':'POST','proxy_used':0}
    if disposition is not None: meta['content_disposition'] = disposition
    assert not transport.validate_response_metadata(meta, RAW, selected())


@pytest.mark.parametrize('extra', [
    b'Content-Disposition: attachment; filename="122920260930E001.pptx"\r\n',
    b'Content-Disposition: attachment; filename="233020260716E001.pptx"\r\n'])
def test_duplicate_native_disposition_cannot_be_flattened_to_trusted_header(offline,monkeypatch,extra):
    headers = HEADERS.rstrip(b'\r\n') + b'\r\n' + extra + b'\r\n'
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**kw:native_result(headers=headers))
    diag={}
    with pytest.raises(SourceResponseError):
        transport.download_published_material(selected(),deadline=time.monotonic()+20,diagnostics=diag)
    assert diag['response_complete'] is False and diag['http_status'] == 200
    assert diag['response_sha256'] == sha256(RAW).hexdigest()


def test_header_and_curl_mime_contradiction_still_fails(offline,monkeypatch):
    meta = deepcopy(META);meta['content_type']='application/pdf'
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**kw:native_result(meta=meta))
    with pytest.raises(SourceResponseError):
        transport.download_published_material(selected(),deadline=time.monotonic()+20,diagnostics={})


@pytest.mark.parametrize('fmt', ['pdf','html'])
def test_blank_mime_exception_is_never_extended_to_pdf_or_index(fmt):
    raw = PDF if fmt == 'pdf' else b'<html><body>Index</body></html>'
    spec = descriptor() if fmt=='pdf' else transport.index_request('1229.TW',2026)
    meta={'http_status':200,'effective_url':spec['url'],'num_redirects':0,'size_download':len(raw),
          'content_type':'','content_length':len(raw),'method':'POST','proxy_used':0,
          'content_disposition':DISPOSITION}
    assert not transport.validate_response_metadata(meta,raw,spec)
    meta.pop('content_disposition');meta['content_type']='application/pdf' if fmt=='pdf' else 'text/html'
    assert transport.validate_response_metadata(meta,raw,spec)


def test_exact_filename_does_not_admit_truncated_zip_or_html_challenge():
    for raw in (RAW[:-100],b'<html>For security reasons access denied</html>'):
        meta={'http_status':200,'effective_url':transport.DOWNLOAD_URL,'num_redirects':0,
              'size_download':len(raw),'content_type':'','content_length':len(raw),'method':'POST','proxy_used':0,
              'content_disposition':DISPOSITION}
        assert not transport.validate_response_metadata(meta,raw,selected())


from test_mops_presentation import harness


def test_blank_mime_ninth_field_survives_original_cache_and_consumer_replay(harness,offline,monkeypatch):
    from data_fetch.market_sources import mops_presentation as source
    calls=[]
    def run(*args, **kwargs):
        calls.append(True)
        return native_result()
    monkeypatch.setattr(transport,'collect_capped_process',run)
    monkeypatch.setattr(source,'download_published_material',transport.download_published_material)
    first_diag={};first=source.fetch_presentation_context('1229.TW',diagnostics=first_diag)
    second_diag={};second=source.fetch_presentation_context('1229.TW',diagnostics=second_diag)
    assert len(calls)==1
    assert first_diag['http_request_count']==3 and not first_diag['cache_hit']
    assert second_diag['http_request_count']==0 and second_diag['cache_hit']
    assert first['fetched_at_epoch']==second['fetched_at_epoch']
    assert first['documents']==second['documents']
    meta=second['mops_material_receipt']['material']['response_metadata']
    assert len(meta)==9 and meta['content_disposition']==DISPOSITION and meta['content_type']==''
    assert source.verify_context(second,'1229.TW')
