"""Public boundary checks. Original private-data replay cases remain local."""
import time
import pytest
from search_provider_runtime import SourceResponseError
from test_official_issuer_master_json import JSON_URL

@pytest.mark.parametrize('url', ['https://www.gce.com.tw/', 'https://www.winbond.com.tw/', JSON_URL + '?x=1', 'http://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'])
def test_dedicated_native_surface_has_no_issuer_or_arbitrary_url_route(monkeypatch, url):
    from data_fetch.market_sources import official_issuer_master_transport as transport
    monkeypatch.setattr(transport.native.ConferenceHttp, 'download_original', lambda *a: pytest.fail('unexpected delegated URL'))
    http = transport.IssuerMasterHttp(time.monotonic() + 25)
    with pytest.raises(SourceResponseError):
        http.download_original(url, {})
    with pytest.raises(SourceResponseError):
        http.get_receipt(url)
    assert http.http_request_count == 0
