"""Public boundary checks. Original private-data replay cases remain local."""
import hashlib
import time
import pytest
import mops_material_transport as transport
from search_provider_runtime import SourceResponseError
from test_mops_material_transport import descriptor, wire, offline, PDF

def static_spec():
    value = descriptor('2023', filename='202320260821E001.pdf')
    value.update(method='GET', url='https://mopsov.twse.com.tw/nas/STR/202320260821E001.pdf', request_body='', language='en')
    value['request_sha256'] = hashlib.sha256(('GET\n' + value['url'] + '\n').encode()).hexdigest()
    return value

def test_qualified_get_records_the_actual_wire_identity(monkeypatch, offline):
    spec = static_spec()
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: offline[0].append((a, k)) or wire(meta_changes={'method': 'GET', 'url_effective': spec['url']}))
    diag = {}
    assert transport.download_published_material(spec, deadline=time.monotonic() + 20, diagnostics=diag) == PDF
    args = offline[0][0][0][0]
    assert '--data' not in args and args[-1] == spec['url']
    assert diag['request_method'] == 'GET' and diag['response_metadata']['method'] == 'GET'
    assert transport.validate_response_metadata(diag['response_metadata'], PDF, spec)
    assert offline[1][0].request.method == 'GET'

@pytest.mark.parametrize('change', [{'url': 'https://example.com/nas/STR/202320260821E001.pdf'}, {'url': 'https://mopsov.twse.com.tw/nas/STR/202320260821E001.pdf?x=1'}, {'ticker': '2330.TW', 'symbol': '2330'}, {'request_body': 'fileName=x'}, {'filename': '202320260821M001.pdf'}, {'method': 'POST'}])
def test_static_get_does_not_admit_unqualified_or_changed_requests(offline, change):
    spec = static_spec()
    spec.update(change)
    with pytest.raises(SourceResponseError):
        transport.download_published_material(spec, deadline=time.monotonic() + 20, diagnostics={})
    assert not offline[0]

@pytest.mark.parametrize('method,rc', [('POST', 0), ('GET', 28)])
def test_mislabeled_or_incomplete_wire_response_is_rejected(monkeypatch, offline, method, rc):
    spec = static_spec()
    monkeypatch.setattr(transport, 'collect_capped_process', lambda *a, **k: wire(meta_changes={'method': method, 'url_effective': spec['url']}, rc=rc))
    diag = {}
    with pytest.raises(SourceResponseError):
        transport.download_published_material(spec, deadline=time.monotonic() + 20, diagnostics=diag)
    assert diag['response_complete'] is False
