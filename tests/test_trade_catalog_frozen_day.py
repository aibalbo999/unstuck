from copy import deepcopy
from datetime import datetime,timedelta,timezone,date
import pytest
from analysis_input_provenance import freeze_analysis_inputs
from trade_source_contract import source_catalog


def frozen():
 data={'ticker':'2838.TW','company_name':'聯邦銀','current_price':20.5,'price_as_of':'2026-10-29','price_history':[]}
 freeze_analysis_inputs(data,cutoff='2026-10-29T14:49:31.303812+00:00')
 return data


def test_resumed_catalog_uses_verified_original_input_day_without_mutation():
 data=frozen();before=deepcopy(data)
 assert source_catalog(data)['short_term_market_context']['as_of']=='2026-10-29'
 assert data==before


@pytest.mark.parametrize('mutate',[
 lambda d:d.update(current_price=99),
 lambda d:d.update(analysis_input_hash='0'*64),
 lambda d:d.update(analysis_input_cutoff='2026-10-28T14:49:31+00:00'),
 lambda d:d.update(analysis_input_cutoff='not-a-time'),
 lambda d:d.update(analysis_input_cutoff='2026-10-29T14:49:31'),
 lambda d:d.pop('_analysis_input_evidence'),
])
def test_unbound_or_tampered_cutoff_cannot_be_used_to_retime_catalog(mutate):
 data=frozen();mutate(data)
 with pytest.raises(ValueError):source_catalog(data)


def test_future_frozen_input_cannot_be_used_as_present_evidence():
 data={'ticker':'2838.TW','current_price':20.5}
 freeze_analysis_inputs(data,cutoff=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat())
 with pytest.raises(ValueError):source_catalog(data)


def test_explicit_future_day_cannot_override_frozen_input_boundary():
 with pytest.raises(ValueError):source_catalog(frozen(),as_of=date(2026,10,30))


def test_unfrozen_explicit_projection_day_keeps_existing_behavior():
 assert source_catalog({'ticker':'2838.TW'},as_of=date(2026,10,29))['short_term_market_context']['as_of']=='2026-10-29'


def test_oversized_private_receipt_keeps_existing_evidence_budget():
 from report_analysis_evidence import MAX_ANALYSIS_EVIDENCE_BYTES
 data=frozen();data['_analysis_input_evidence']=' '*(MAX_ANALYSIS_EVIDENCE_BYTES+1)
 with pytest.raises(ValueError):source_catalog(data)
