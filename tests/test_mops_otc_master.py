"""Market, roster and original transport boundaries for OTC presentations."""
import gzip
import json
import time
from pathlib import Path
import pytest
from data_fetch.market_sources import mops_otc_master as source
from data_fetch.market_sources.mops_presentation import parse_master, MASTER_URL
from search_provider_runtime import SourceResponseError

RAW=gzip.decompress((Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261017/shianyih-mops-integration/otc-master.json.gz').read_bytes())


def test_complete_native_otc_master_and_market_identity(monkeypatch):
    monkeypatch.setattr(time,'time',lambda:1792248000.)
    result=parse_master(RAW,'3531.TWO',1792247900.,source.OTC_MASTER)
    assert result['official_ubn']=='52543363' and result['short_name']=='先益'
    with pytest.raises(ValueError):parse_master(RAW,'3531.TWO',1792247900.,MASTER_URL)
    with pytest.raises(ValueError):parse_master(RAW,'1104.TW',1792247900.,source.OTC_MASTER)


@pytest.mark.parametrize('kind',['duplicate_code','too_short','missing_field','wrong_type','duplicate_json_key'])
def test_incomplete_or_ambiguous_master_cannot_authorize_a_company(kind):
    rows=json.loads(RAW)
    if kind=='duplicate_code':rows.append(rows[0])
    if kind=='too_short':rows=rows[:10]
    if kind=='missing_field':rows[0].pop('WebAddress')
    if kind=='wrong_type':rows[0]['SecuritiesCompanyCode']=True
    raw=json.dumps(rows).encode()
    if kind=='duplicate_json_key':raw=raw.replace(b'"Date":',b'"Date":"1151017","Date":',1)
    with pytest.raises(ValueError):source.parse_rows(raw)


def test_adapter_reuses_same_url_cache_and_guards_and_rejects_other_routes():
    from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp,INDEX
    assert source.OtcMasterHttp.raw_cache_prefix==AurasConferenceHttp.raw_cache_prefix
    assert source.OtcMasterHttp.admission_prefix==AurasConferenceHttp.admission_prefix
    http=source.OtcMasterHttp(time.monotonic()+5)
    with pytest.raises(SourceResponseError):http.get_receipt(INDEX)
