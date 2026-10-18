"""Optional local acquired-body replay; no private originals are test fixtures."""
from copy import deepcopy
import gzip
from hashlib import sha256
import json
from pathlib import Path

import pytest

EVIDENCE = Path(__file__).resolve().parents[1]/'docs/evidence/report-data-gaps/20261018/annual-next'
EXPECTED = {
    '1623.TW': (False, -228354000, 'individual'),
    '7799.TW': (False, -514480000, 'individual'),
    '2892.TW': (True, 61359575000, 'consolidated'),
    '2851.TW': (True, 2320176000, 'individual'),
    '2883.TW': (False, None, 'consolidated'),
    '2884.TW': (True, 34007696000, 'consolidated'),
    '2887.TW': (True, -84887296000, 'consolidated'),
    '2855.TW': (True, -10230221000, 'consolidated'),
}


def isolated_receipts(value):
    from official_response_evidence import archive_response
    if isinstance(value, list): return [isolated_receipts(item) for item in value]
    if not isinstance(value, dict): return value
    if value.get('status') == 'archived' and 'raw_response_path' in value:
        source = Path(value['raw_response_path']).resolve()
        assert source.is_relative_to(EVIDENCE/'receipt-store/official-response-evidence')
        raw = gzip.decompress(source.read_bytes())
        assert sha256(raw).hexdigest() == value['raw_response_sha256']
        assert len(raw) == value['raw_response_bytes']
        # Keep the true source URL, body identity, time and response status.
        proof = archive_response(raw, source_url=value['source_url'], retrieved_at=value['retrieved_at'],
                                 evidence_kind=value['evidence_kind'], http_status=value['http_status'])
        assert {k: v for k, v in proof.items() if k != 'raw_response_path'} == {
            k: v for k, v in value.items() if k != 'raw_response_path'}
        return proof
    return {key: isolated_receipts(item) for key, item in value.items()}


@pytest.mark.parametrize('ticker', EXPECTED)
def test_acquired_annual_originals_replay_with_actual_periods_and_scope(ticker):
    from data_fetch.market_sources.annual_filing_reference import replay_reference, cash_flow_reference
    source = EVIDENCE/(ticker+'.annual-cash-flow-review.json')
    if not source.exists(): pytest.skip('Local acquired originals are not part of the source checkout')
    review = isolated_receipts(json.loads(source.read_text()))
    original = deepcopy(review)
    detail = replay_reference(review['annual_filing_reference'], ticker)
    five, fcf, scope = EXPECTED[ticker]
    assert detail['status'] == ('annual_components_verified' if fcf is None else 'annual_originals_verified')
    assert detail['five_year_history_verified'] is five
    assert detail['report_scope'] == scope
    assert detail['raw_twd_by_year']['2025']['free_cash_flow'] == fcf
    assert detail['historical_pit_verified'] is False and detail['industrial_dcf_applicable'] is False
    reader = cash_flow_reference({'ticker': ticker, 'financial_currency': 'TWD', 'free_cash_flow_raw': -999}, review)
    assert reader['raw_scalar_period_verified'] is False
    if fcf is None:
        assert reader['status'] == 'unverified'
        assert reader['missing_cash_flow_components'] == ['intangible_purchase']
        assert '尚缺明列無形資產購置支出' in reader['reason']
        assert '2023 年報所列 2022 比較欄與 2022 原年度有衝突' in reader['reason']
        assert 'raw_response_path' not in json.dumps(reader)
        assert detail['comparative_issue'].endswith('for 2022')
        conflicts = next(item for item in detail['comparative_diagnostics'] if item['period_year'] == 2022)
        assert conflicts['conflicting_facts']['ifrs-full:CashFlowsFromUsedInOperatingActivities'] == {
            'original_twd': 60166247000, 'comparative_twd': 9952969000}
    else:
        assert reader['status'] == 'official_annual_cash_flow_verified' and reader['free_cash_flow_twd'] == fcf
    if ticker == '2892.TW':
        assert detail['restated_filing_years'] == [2021]
        assert '追溯重編' in reader['reason']
    if ticker == '7799.TW': assert detail['first_adoption_years'] == [2023]
    if ticker == '2851.TW': assert reader['issuer_name'] == '中央再保險股份有限公司'
    assert review == original


def test_existing_bank_missing_cash_purchase_stays_unknown_without_new_requests():
    from data_fetch.market_sources.financial_institution_xbrl import parse_filing, BANK_FIELDS
    source = EVIDENCE/'legacy-inputs.json'
    if not source.exists(): pytest.skip('Local original inventory is not part of the source checkout')
    data = json.loads(source.read_text())['2845.TW']
    for document in data['statement']['documents']:
        proof = document['source_record_archive']
        # Offline read only; never invoke the provider or archive into production.
        raw = gzip.decompress(Path(proof['raw_response_path']).read_bytes())
        assert sha256(raw).hexdigest() == document['sha256']
        parsed = parse_filing(raw, '2845', document['year'], allow_missing=True)
        assert set(BANK_FIELDS)-set(parsed) == {
            'ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'}
        assert data['statement']['raw_twd_by_year'][str(document['year'])]['free_cash_flow'] is None
