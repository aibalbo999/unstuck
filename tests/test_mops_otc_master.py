"""Public boundary checks. Original private-data replay cases remain local."""
import time
import pytest
from data_fetch.market_sources import mops_otc_master as source
from search_provider_runtime import SourceResponseError

def test_adapter_reuses_same_url_cache_and_guards_and_rejects_other_routes():
    from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp, INDEX
    assert source.OtcMasterHttp.raw_cache_prefix == AurasConferenceHttp.raw_cache_prefix
    assert source.OtcMasterHttp.admission_prefix == AurasConferenceHttp.admission_prefix
    http = source.OtcMasterHttp(time.monotonic() + 5)
    with pytest.raises(SourceResponseError):
        http.get_receipt(INDEX)
