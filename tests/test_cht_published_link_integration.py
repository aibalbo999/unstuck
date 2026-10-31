"""Actual formal calendar variant across provider and source-only public boundaries."""
from pathlib import Path
import pytest
from test_cht_conference import harness, valid_data
from test_cht_presentation_integration import test_public_source_only_preserves_report_and_checks_native_proof as source_only_check
from data_fetch.market_sources.cht_conference_transport import INDEX_URL, PDF_URL

PUBLISHED_URL='https://www.cht.com.tw/home/eshop/-/media/web/pdf/investors/shareholder-services/en/ir-calendar-en/20261013/2q26-en.pdf'

@pytest.fixture
def live_originals(harness):
    path=Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261014/remaining-gaps-after-csc/cht-integration/integration/first-formal-diagnosis/index.body'
    harness[0][INDEX_URL]=path.read_bytes()
    harness[0][PUBLISHED_URL]=harness[0][PDF_URL]
    return harness


def test_actual_published_link_provider_records_exact_url_and_warm_no_new_acquisition(live_originals):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    request=FetchRequest.from_ticker('2412.TW')
    cold=EarningsCallProvider().fetch(request,{'data':valid_data()})
    assert cold.provider=='CHT official conference presentation' and cold.audit['status']=='success'
    assert cold.value['documents'][0]['url']==PUBLISHED_URL
    assert cold.value['cht_conference_receipt']['pdf']['source_url']==PUBLISHED_URL
    assert live_originals[1][-1]==PUBLISHED_URL and len(live_originals[1])==3
    warm=EarningsCallProvider().fetch(request,{'data':valid_data()})
    assert warm.audit['status']=='skipped_fresh_cache' and warm.audit['http_request_count']==0
    assert cold.value['documents']==warm.value['documents']


@pytest.mark.parametrize('tamper',[False,'q_and_a_transcript_available','projection_policy'])
def test_actual_published_link_source_only_preserves_analyses_and_checks_proof(live_originals,tmp_path,monkeypatch,tamper):
    source_only_check(live_originals,tmp_path,monkeypatch,'2412.TW',tamper)
