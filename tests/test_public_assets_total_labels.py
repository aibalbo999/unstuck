"""Exact public-JSON asset totals retain parent equity and all metadata gates."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path

import pytest
from data_fetch.market_sources import mops_public_annual as public


def synthetic_balance(label='資產總計', *, individual=False):
    return {'code': 200, 'message': '查詢成功', 'result': {
        'reportType': '個別' if individual else '合併', 'year': '110', 'season': '4', 'fiscalYear': ' ',
        'companyAbbreviation': '台灣高鐵' if individual else 'Synthetic issuer', 'subsidiary': [],
        'urlList': [{'name': 'XBRL資訊平台', 'url': 'https://mopsov.twse.com.tw/server-java/t164sb01?step=1&CO_ID=' + ('2633' if individual else '2207') + '&SYEAR=2021&SSEASON=4&REPORT_ID=' + ('A' if individual else 'C')}],
        'titles': [{'main': '會計項目', 'sub': []}, *[{'main': str(year) + '年12月31日', 'sub': [{'main': '金額', 'sub': []}, {'main': '%', 'sub': []}]} for year in (110, 109)]],
        'reportList': [[label, '350,000', '100.00', '290,000', '100.00'],
            ['權益總額' if individual else '歸屬於母公司業主之權益合計', '73,000', '20.86', '65,000', '22.41'],
            ['權益總計', '94,000', '26.86', '83,000', '28.62'],
            ['非控制權益', '21,000', '6.00', '18,000', '6.21']]}}


@pytest.fixture
def synthetic_renderer(monkeypatch):
    # Synthetic behavioral contract only. The separate private native test
    # below uses the exact real fingerprinted official renderer, without mock.
    calls = []
    def verify(raw, statement):
        assert raw == b'explicit synthetic renderer seam' and statement == 'BalanceSheet'
        calls.append(statement)
    monkeypatch.setattr(public, '_template', verify)
    return calls


def parse(value, **kwargs):
    return public.parse_statement(json.dumps(value, ensure_ascii=False).encode(), '2207', 2021,
                                  'BalanceSheet', b'explicit synthetic renderer seam', **kwargs)


@pytest.mark.parametrize('label', ['資產總額', '資產總計'])
def test_exact_asset_total_labels_preserve_current_comparative_and_parent_equity(synthetic_renderer, label):
    result = parse(synthetic_balance(label))
    assert result[2021] == {'Assets': 350000000, 'EquityAttributableToOwnersOfParent': 73000000}
    assert result[2020] == {'Assets': 290000000, 'EquityAttributableToOwnersOfParent': 65000000}
    assert synthetic_renderer == ['BalanceSheet']


@pytest.mark.parametrize('kind', ['both_equal', 'both_conflicting', 'duplicate', 'subtotal_only', 'parent_missing'])
def test_ambiguous_total_or_missing_parent_equity_still_rejected(synthetic_renderer, kind):
    value = synthetic_balance(); rows = value['result']['reportList']
    if kind.startswith('both'):
        extra = deepcopy(rows[0]); extra[0] = '資產總額'
        if kind == 'both_conflicting': extra[1] = '351,000'
        rows.append(extra)
    elif kind == 'duplicate': rows.append(deepcopy(rows[0]))
    elif kind == 'subtotal_only': rows[0][0] = '流動資產合計'
    else: rows.pop(1)
    with pytest.raises(public.FilingError): parse(value)


@pytest.mark.parametrize('change', ['issuer', 'year', 'quarter', 'scope', 'currency', 'unit', 'amount', 'percentage_column'])
def test_alias_does_not_bypass_identity_period_unit_or_amount_gates(synthetic_renderer, change):
    value = synthetic_balance(); result = value['result']
    if change == 'issuer': result['urlList'][0]['url'] = result['urlList'][0]['url'].replace('2207', '2208')
    elif change == 'year': result['year'] = '111'
    elif change == 'quarter': result['season'] = '3'
    elif change == 'scope': result['reportType'] = '個別'
    elif change == 'currency': result['currency'] = 'USD'
    elif change == 'unit': result['unit'] = 'million'
    elif change == 'amount': result['reportList'][0][1] = '-'
    else: result['titles'][1]['sub'].reverse()
    with pytest.raises(public.FilingError): parse(value)


def test_consolidated_alias_is_not_admitted_for_individual_scope(synthetic_renderer):
    value = synthetic_balance(individual=True)
    with pytest.raises(public.FilingError):
        public.parse_statement(json.dumps(value, ensure_ascii=False).encode(), '2633', 2021,
            'BalanceSheet', b'explicit synthetic renderer seam', report_scope='individual')


def test_private_exact_native_2207_original_uses_real_renderer_and_parent_equity():
    path = Path(__file__).parent / 'fixtures/source_acquisition/mops_public_2207_20261104_balance.json'
    if not path.exists(): pytest.skip('Private original is intentionally not published')
    fixture = json.loads(path.read_text())
    raw, template = base64.b64decode(fixture['raw_b64']), base64.b64decode(fixture['template_b64'])
    assert hashlib.sha256(raw).hexdigest() == fixture['raw_sha256']
    assert hashlib.sha256(template).hexdigest() == fixture['template_sha256']
    result = public.parse_statement(raw, '2207', 2021, 'BalanceSheet', template)
    assert result[2021] == {'Assets': 349612784000, 'EquityAttributableToOwnersOfParent': 73770851000}
    assert result[2020] == {'Assets': 290490532000, 'EquityAttributableToOwnersOfParent': 65477704000}
