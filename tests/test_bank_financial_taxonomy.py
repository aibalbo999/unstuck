"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import gzip
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import pytest
FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'

def original(year):
    return gzip.decompress((FIXTURES / f'bank_2834_{year}_captured_20261011.xhtml.gz').read_bytes())

def acquired(monkeypatch):
    import data_fetch.market_sources.financial_institution_xbrl as source
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    index = gzip.decompress((FIXTURES / 'bank_2834_index_captured_20261011.html.gz').read_bytes())

    def request(client, method, url, *, data=None):
        if url == INDEX_URL:
            assert method == 'POST' and data['co_id'] == '2834'
            return index
        query = parse_qs(urlsplit(url).query)
        assert method == 'GET' and query['co_id'] == ['2834'] and (query['report_id'] == ['C'])
        return original(int(query['year'][0]))
    monkeypatch.setattr(source, '_bounded_request', request)
    return source.fetch_financial_institution_histories('2834.TW', client=object())

def test_captured_bank_three_required_lines_are_acquired_without_holding_aliases():
    from data_fetch.market_sources.financial_institution_xbrl import parse_filing
    values = parse_filing(original(2021), '2834', 2021)
    assert values['tifrs-bsci-basi:NetIncomeLossOfInterest'] == 17805776000
    assert values['tifrs-bsci-basi:NetServiceFeeChargeIncomeLosses'] == 3334199000
    assert values['tifrs-bsci-basi:NetIncome'] == 24106024000
    assert not any((key.startswith('tifrs-bsci-fh:') for key in values))
    assert len(values) == 10

def test_five_bank_originals_reach_projection_with_actual_tag_basis(monkeypatch):
    from data_fetch.financial_history_basis import project_financial_institution_histories
    from official_response_evidence import read_response
    value = acquired(monkeypatch)
    projected = project_financial_institution_histories(value, '2834.TW')
    assert value['statement_taxonomy'] == 'bank' and projected is not None
    assert projected['net_revenue_history'] == [24.106024, 28.529123, 31.913544, 34.114587, 35.088039]
    assert projected['revenue_history'] == projected['gross_profit_history'] == projected['operating_income_history'] == [None] * 5
    assert projected['financial_history_basis']['field_sources']['net_revenue_history']['fact'] == 'tifrs-bsci-basi:NetIncome'
    for doc in value['documents']:
        assert doc['statement_taxonomy'] == 'bank'
        assert read_response(doc['source_record_archive']) == original(doc['year'])

def test_bank_partial_comparative_preserves_available_history_without_inventing_fcf(monkeypatch):
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    import data_fetch.market_sources.financial_institution_xbrl as source
    from data_fetch.financial_history_basis import project_financial_institution_histories
    from prompt_builder_helpers import _prompt_financial_institution_history
    from data_fetch import yfinance_extractors as extractors
    from test_financial_institution_history_projection import NoAnnualSdk
    issuer = '2845'
    intangible = 'ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'
    interest = 'ifrs-full:RevenueFromInterest'
    instant_fields = {'ifrs-full:Assets', 'ifrs-full:EquityAttributableToOwnersOfParent'}

    def annual_values(year):
        values = {}
        for offset, tag in enumerate(source.BANK_FIELDS):
            if tag == intangible:
                continue
            value = 1000 + year + offset
            if tag == 'ifrs-full:CashFlowsFromUsedInOperatingActivities':
                value = 10000 + year
            if tag == 'ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities':
                value = -(100 + year)
            values[tag] = value
        return values

    def document(periods):
        contexts = []
        facts = []
        for year, values in periods.items():
            for kind, period in [('duration', f'<xbrli:startDate>{year}-01-01</xbrli:startDate><xbrli:endDate>{year}-12-31</xbrli:endDate>'), ('instant', f'<xbrli:instant>{year}-12-31</xbrli:instant>')]:
                contexts.append(f'<xbrli:context id="{kind}{year}"><xbrli:entity><xbrli:identifier scheme="http://www.twse.com.tw">{issuer}</xbrli:identifier></xbrli:entity><xbrli:period>{period}</xbrli:period></xbrli:context>')
            for tag, value in values.items():
                kind = 'instant' if tag in instant_fields else 'duration'
                sign = ' sign="-"' if value < 0 else ''
                facts.append(f'<ix:nonFraction name="{tag}" contextRef="{kind}{year}" unitRef="TWD" scale="3" decimals="-3" format="ixt:numdotdecimal"{sign}>{abs(value)}</ix:nonFraction>')
        return ('<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:xbrli="http://www.xbrl.org/2003/instance"><xbrli:unit id="TWD"><xbrli:measure>iso4217:TWD</xbrli:measure></xbrli:unit>' + ''.join(contexts) + ''.join(facts) + '</html>').encode()
    docs = {}
    for year in range(2021, 2026):
        periods = {year: annual_values(year)}
        if year > 2021:
            prior = annual_values(year - 1)
            if year == 2022:
                prior[interest] += 500
            periods[year - 1] = prior
        docs[year] = document(periods)
    hrefs = ''.join((f'<a href="/server-java/FileDownLoad?functionName=t164sb01&amp;step=9&amp;season=4&amp;report_id=C&amp;year={year}&amp;co_id={issuer}">annual</a>' for year in range(2021, 2026)))
    index = f'<html>{hrefs}</html>'.encode()

    def request(_client, method, url, *, data=None):
        if url == INDEX_URL:
            assert method == 'POST' and data['co_id'] == issuer
            return index
        assert method == 'GET'
        from urllib.parse import parse_qs, urlsplit
        year = int(parse_qs(urlsplit(url).query)['year'][0])
        return docs[year]
    monkeypatch.setattr(source, '_bounded_request', request)
    value = source.fetch_financial_institution_histories(issuer + '.TW', client=object())
    projection = project_financial_institution_histories(value, issuer + '.TW')
    prompt = _prompt_financial_institution_history({'ticker': issuer + '.TW', 'sector_specific_financials': value})
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    monkeypatch.setattr(extractors, 'fetch_financial_institution_histories', lambda _ticker: value)
    extracted = extractors.extract_financial_histories(NoAnnualSdk(), issuer + '.TW', [], data_loader_cls=None, industry_context='Banks')
    assert value['schema'] == 'bank_consolidated.v1'
    assert any((revision['year'] == 2021 and revision['fact'] == interest and (revision['kind'] == 'restatement') for revision in value['comparative_revisions']))
    assert value['raw_twd_by_year']['2021']['intangible_purchase'] is None
    assert value['raw_twd_by_year']['2021']['free_cash_flow'] is None
    assert projection is not None and projection['fcf_history'] == [None] * 5
    assert all((row['free_cash_flow_billion_twd'] is None for row in prompt['rows']))
    assert 'not zero' in prompt['basis_note']
    assert extracted['sector_specific_financial_audit']['status'] == 'success'
    assert extracted['sector_specific_financial_audit']['coverage_status'] == 'sector_specific_partial_optional_cashflow'
    assert extracted['fcf_history'] == [None] * 5
    assert '不以零補值' in extracted['sector_specific_financial_audit']['message']

@pytest.mark.parametrize('change', ['missing_marker', 'wrong_marker', 'missing_archive', 'changed_fact', 'changed_sha', 'changed_http', 'changed_source_url', 'changed_epoch', 'before_period_close', 'float_size'])
def test_bank_receipt_tampering_cannot_publish_projection(monkeypatch, change):
    from data_fetch.financial_history_basis import project_financial_institution_histories
    value = deepcopy(acquired(monkeypatch))
    if change == 'missing_marker':
        value.pop('statement_taxonomy')
    elif change == 'wrong_marker':
        value['statement_taxonomy'] = 'financial_holding'
    elif change == 'changed_fact':
        value['raw_twd_by_year']['2021']['net_revenue'] += 1
    else:
        proof = value['documents'][0]['source_record_archive']
        if change == 'missing_archive':
            value['documents'][0].pop('source_record_archive')
        elif change == 'changed_sha':
            value['documents'][0]['sha256'] = '0' * 64
        elif change == 'changed_http':
            proof['http_status'] = True
        elif change == 'changed_source_url':
            proof['source_url'] += '&co_id=2882'
        elif change == 'changed_epoch':
            proof['retrieved_at'] = True
        elif change == 'before_period_close':
            proof['retrieved_at'] = 1
        elif change == 'float_size':
            proof['raw_response_bytes'] = float(proof['raw_response_bytes'])
    assert project_financial_institution_histories(value, '2834.TW') is None

@pytest.mark.parametrize('change', ['wrong_issuer', 'wrong_currency', 'missing_bank_line', 'mixed_holding_line'])
def test_bank_format_keeps_identity_currency_completeness_and_unique_taxonomy(change):
    from data_fetch.market_sources.financial_institution_xbrl import parse_filing
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    raw = original(2021)
    if change == 'wrong_issuer':
        issuer = '2882'
    else:
        issuer = '2834'
    if change == 'wrong_currency':
        raw = raw.replace(b'iso4217:TWD', b'iso4217:USD')
    elif change == 'missing_bank_line':
        raw = raw.replace(b'tifrs-bsci-basi:NetIncome"', b'tifrs-bsci-basi:UnsupportedLine"')
    elif change == 'mixed_holding_line':
        extra = b'<ix:nonFraction name="tifrs-bsci-fh:NetIncomeLoss" contextRef="From20210101To20211231" unitRef="TWD" scale="3" decimals="-3" format="ixt:numdotdecimal">1</ix:nonFraction>'
        raw = raw.replace(b'</body>', extra + b'</body>')
    with pytest.raises(FilingError):
        parse_filing(raw, issuer, 2021)

def test_legacy_malformed_documents_are_rejected_without_exception():
    from data_fetch.financial_history_basis import project_financial_institution_histories
    assert project_financial_institution_histories({'schema': 'financial_institution_consolidated.v1', 'documents': None}, '2834.TW') is None

def test_unverified_bank_receipt_cannot_enter_prompt_raw_history(monkeypatch):
    from prompt_builder_helpers import _prompt_financial_institution_history
    value = acquired(monkeypatch)
    value['raw_twd_by_year']['2021']['net_revenue'] += 1
    assert _prompt_financial_institution_history({'ticker': '2834.TW', 'sector_specific_financials': value}) == {}

def test_bank_basis_and_complete_receipts_survive_prompt_state_and_size_governance(monkeypatch):
    from data_fetch.financial_history_basis import project_financial_institution_histories, prompt_history_basis
    from prompt_builder import format_data_for_prompt
    from data_trust import apply_snapshot_size_governance
    from state_memory import initialize_agent_state, state_view_for
    value = acquired(monkeypatch)
    projection = project_financial_institution_histories(value, '2834.TW')
    data = {'ticker': '2834.TW', 'financial_currency': 'TWD', 'currency': 'TWD', 'sector': 'Financial Services', 'industry': 'Banks', 'sector_specific_financials': value, **projection}
    encoded = format_data_for_prompt(data)
    assert 'tifrs-bsci-basi:NetIncome' in encoded and 'raw_response_path' not in encoded
    view = state_view_for('valuation', initialize_agent_state(data))['normalized_financials']
    assert view['financial_history_basis'] == projection['financial_history_basis'] and view['net_revenue_history'] == projection['net_revenue_history']
    snapshot = apply_snapshot_size_governance({'data': {**data, 'non_core_debug': 'x' * 20000}}, max_bytes=11000)
    assert prompt_history_basis(snapshot['data']) == projection['financial_history_basis']

@pytest.mark.parametrize('bad', [None, False, [], 'invalid'])
def test_malformed_bank_archive_is_rejected_by_projection_and_prompt(monkeypatch, bad):
    from data_fetch.financial_history_basis import project_financial_institution_histories
    from prompt_builder_helpers import _prompt_financial_institution_history
    value = acquired(monkeypatch)
    value['documents'][0]['source_record_archive'] = bad
    assert project_financial_institution_histories(value, '2834.TW') is None
    assert _prompt_financial_institution_history({'ticker': '2834.TW', 'sector_specific_financials': value}) == {}

def test_missing_ticker_is_rejected_before_bank_original_replay(monkeypatch):
    from data_fetch.financial_history_basis import project_financial_institution_histories
    assert project_financial_institution_histories(acquired(monkeypatch), None) is None

def test_bank_schema_retains_origin_when_all_optional_metadata_is_removed(monkeypatch):
    from data_fetch.financial_history_basis import project_financial_institution_histories
    from prompt_builder_helpers import _prompt_financial_institution_history
    value = acquired(monkeypatch)
    value.pop('statement_taxonomy')
    for document in value['documents']:
        document.pop('statement_taxonomy')
        document.pop('source_record_archive')
    assert project_financial_institution_histories(value, '2834.TW') is None
    assert _prompt_financial_institution_history({'ticker': '2834.TW', 'sector_specific_financials': value}) == {}

def test_bank_source_keeps_distinct_schema_across_annual_prompt_metrics_and_money_checks(monkeypatch):
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.financial_history_basis import financial_institution_history_metrics
    from prompt_builder_helpers import _prompt_history_rows
    from financial_money_claims import _source
    value = acquired(monkeypatch)
    assert value['schema'] == 'bank_consolidated.v1'
    data = {'ticker': '2834.TW', 'financial_currency': 'TWD', **project_source_value(value, '2834.TW')}
    assert data['financial_history_basis']['statement_schema'] == 'bank_consolidated.v1'
    metrics = financial_institution_history_metrics(data)
    assert metrics['net_revenue_cagr']['statement_schema'] == 'bank_consolidated.v1'
    assert _prompt_history_rows(data)[-1]['net_revenue_billion_twd'] == 35.088
    assert _source(data, '淨收益', '2025年')[0] == 35088039000

def test_unverified_bank_basis_does_not_admit_financial_fcf_as_industrial_dcf(monkeypatch):
    from data_fetch.financial_history_basis import project_financial_institution_histories
    from quant_input_contract import read_quant_inputs
    value = acquired(monkeypatch)
    projection = project_financial_institution_histories(value, '2834.TW')
    data = {'ticker': '2834.TW', 'sector_specific_financials': value, **projection}
    value['documents'][0]['source_record_archive'] = None
    _facts, _provenance, reasons = read_quant_inputs(data)
    assert 'financial_institution_basis_unverified' in reasons['dcf']

def test_bank_five_year_extraction_avoids_redundant_sdk_and_preserves_net_revenue(monkeypatch):
    from data_fetch import yfinance_extractors as source
    from test_financial_institution_history_projection import NoAnnualSdk
    value = acquired(monkeypatch)
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    monkeypatch.setattr(source, 'fetch_financial_institution_histories', lambda ticker: deepcopy(value))
    monkeypatch.setattr(source, 'fetch_finmind_financial_statement_fallback', lambda *a, **kw: pytest.fail('complete bank must avoid redundant FinMind'))
    data = source.extract_financial_histories(NoAnnualSdk(), '2834.TW', [], industry_context='金融保險')
    assert data['years'] == ['2021', '2022', '2023', '2024', '2025']
    assert data['financial_history_basis']['statement_schema'] == 'bank_consolidated.v1'
    assert data['net_revenue_history'][-1] == 35.088039 and data['revenue_history'] == [None] * 5

def test_bank_same_period_capital_notes_use_net_revenue_and_actual_bank_basis(monkeypatch):
    from data_fetch.annual_financial_source_provider import project_source_value
    from data_fetch.yfinance_capital_notes import build_capital_structure_notes
    from test_financial_institution_history_projection import NoAnnualSdk
    data = {'ticker': '2834.TW', **project_source_value(acquired(monkeypatch), '2834.TW')}
    notes = build_capital_structure_notes(NoAnnualSdk(), {}, revenue_history=data['revenue_history'], net_income_history=data['net_income_history'], total_assets_history=data['total_assets_history'], total_equity_history=data['total_equity_history'], market_cap=None, total_debt=None, financial_history_data=data)
    assert '金融業' in notes['dupont_identity_note'] and '合併淨收益' in notes['dupont_identity_note']
    assert notes['equity_multiplier'] != 'N/A'
