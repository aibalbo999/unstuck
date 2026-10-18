"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

def valid_data():
    return {'ticker': '1229.TW', 'company_name': '聯華 / Lien Hwa Industrial Holdings Corporation', 'raw_company_name': 'Lien Hwa Industrial Holdings Corporation', 'instrument_type': 'EQUITY', 'quote_type': 'EQUITY', 'company_identity': {'ticker': '1229.TW', 'stock_id': '1229', 'official_name': '聯華', 'legal_name': '聯華實業控股股份有限公司', 'official_ubn': '11996904', 'instrument_type': 'EQUITY', 'allowed_aliases': ['聯華', 'LHIHC', '1229.TW', '1229'], 'english_names': ['Lien Hwa Industrial Holdings Corporation'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('change', ['root_name', 'alias', 'ubn', 'quote', 'forbidden', 'foreign_suffix'])
def test_identity_does_not_borrow_good_name_to_hide_contradiction(change):
    from data_fetch.market_sources.lienhwa_conference import validate_context
    v = valid_data()
    if change == 'root_name':
        v['company_name'] = 'ARES'
    elif change == 'alias':
        v['company_identity']['english_names'] = {}
    elif change == 'ubn':
        v['company_identity']['official_ubn'] = '00000000'
    elif change == 'quote':
        v['quote_type'] = 'ETF'
    elif change == 'forbidden':
        v['company_identity']['forbidden_aliases'] = ['聯華']
    else:
        v['raw_company_name'] = 'KINIK Electric Co.,Ltd. unrelated'
    assert not validate_context(v, '1229.TW')

@pytest.mark.parametrize('bucket', ['documents', 'materials'])
@pytest.mark.parametrize('remaining_marker', ['projection_policy', 'lienhwa_glyph_evidence'])
def test_stripped_typed_document_still_requires_original_verification(bucket, remaining_marker):
    from data_fetch.market_sources import lienhwa_conference as s
    marker = s.PROJECTION_POLICY if remaining_marker == 'projection_policy' else False
    value = {bucket: [{remaining_marker: marker, 'title': 'Unverified presentation'}]}
    assert s.is_marked(value) is True
    assert s.verify_context(value, '1229.TW', max_age=1800) is False
    assert s.is_marked({bucket: [{'title': 'Unrelated ordinary conference'}]}) is False
