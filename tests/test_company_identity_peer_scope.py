"""Peer comparisons must remain separate from the target issuer's identity."""
from copy import deepcopy
import pytest
from company_identity_validator import validate_company_identity

DATA = {'ticker': '1623.TW', 'company_identity': {
    'ticker': '1623.TW', 'stock_id': '1623', 'official_name': '大東電',
    'allowed_aliases': ['大東電', '大東電業廠股份有限公司', '1623.TW'],
    'forbidden_aliases': ['大亞', '大亞電線電纜'],
    'same_industry_peers': [{'stock_name': '大亞', 'stock_id': '1609'},
                            {'stock_name': '大山', 'stock_id': '1615'}],
}}


def peer_report(line='- **大亞（1609.TW）**：估值與大東電相近。'):
    return ('大東電（1623.TW）分析。\n## 三、同業估值水準參考\n'
            '- 大山（1615.TW）：比較數據僅作產業參考，並不代表本公司估值結論。\n'
            + line + '\n' + line)


def test_explicit_peer_list_and_peer_section_do_not_change_target_identity():
    text = ('大東電（1623.TW）分析。\n- 同業推論：對比同業：大山（1615.TW）本益比9.59倍、'
            '宏泰（1612.TW）本益比8.57倍、大亞（1609.TW）本益比14.41倍。\n'
            '## 三、同業估值水準參考\n'
            '- 大山（1615.TW）：數據只作比較參考；未用同業資訊補造本公司結論。\n'
            '- **大亞（1609.TW）**：估值與大東電相近。')
    before = deepcopy(DATA)
    assert validate_company_identity(text, DATA) == []
    assert DATA == before


@pytest.mark.parametrize('heading', ['## 同業估值', '### 三、同業估值水準參考', '## Peer valuation'])
def test_exact_peer_code_in_explicit_peer_section(heading):
    text = peer_report().replace('## 三、同業估值水準參考', heading)
    assert validate_company_identity(text, DATA) == []


@pytest.mark.parametrize('line', [
    '- 本公司是大亞（1609.TW）。',
    '- 本次標的為大亞（1609.TW）。',
    '- 分析主體：大亞（1609.TW）。',
    '- 大亞（1609.TW）就是本公司。',
    '- 大東電就是大亞（1609.TW）。',
    '- 大亞（1609.TW）即大東電。',
    '- 同業比較：本公司是大亞（1609.TW）。',
    '- 同業比較：大亞（1609.TW）就是本公司。',
    '- 本公司（即大亞（1609.TW））營運良好。',
    '- 大亞（1609.TW）（本公司）營運良好。',
    '- 標的公司為大亞（1609.TW）。',
    '- 大東電（1623.TW）即大亞（1609.TW）。',
])
def test_peer_section_and_code_cannot_rename_target(line):
    assert validate_company_identity(peer_report(line), DATA)


@pytest.mark.parametrize('line', [
    '- 大亞（1623.TW）估值偏低。',
    '- 1623.TW 大亞估值偏低。',
    '- 大亞（1609.TW），本次標的代碼大亞（1623.TW）。',
])
def test_current_ticker_binding_still_rejected(line):
    assert any('錯置' in item for item in validate_company_identity(peer_report(line), DATA))


@pytest.mark.parametrize('boundary', ['## 本公司營運', '### 本公司營運', '# 結論'])
def test_peer_heading_scope_ends_at_next_heading(boundary):
    text = ('大東電（1623.TW）分析。\n## 同業估值\n- 大山（1615.TW）。\n'
            + boundary + '\n大亞（1609.TW）營運良好。\n大亞（1609.TW）成長良好。')
    assert validate_company_identity(text, DATA)


@pytest.mark.parametrize('line', [
    '- 大亞（1615.TW）估值偏低。',
    '- 大亞（16090.TW）估值偏低。',
    '- 大亞（1609.TW.other）估值偏低。',
    '- 大亞估值偏低；另列參考代碼1609.TW。',
])
def test_peer_scope_cannot_borrow_wrong_or_unbound_code(line):
    assert validate_company_identity(peer_report(line), DATA)


def test_unknown_forbidden_alias_cannot_borrow_known_peer_code():
    data = deepcopy(DATA)
    data['company_identity']['forbidden_aliases'].append('其他公司')
    assert validate_company_identity(peer_report('- 其他公司（1609.TW）估值偏低。'), data)


def test_inline_peer_mentions_remain_valid():
    assert validate_company_identity('大東電與同業大亞比較。同業大亞估值較高。', DATA) == []


def test_inline_peer_word_does_not_cross_sentence_boundary():
    assert validate_company_identity('大東電同業比較。大亞是本公司。大亞是本公司。', DATA)


def test_single_markdown_formatted_current_ticker_binding_is_rejected():
    assert any('錯置' in item for item in validate_company_identity(
        '大東電分析。\n## 同業估值\n- **大亞**（1623.TW）估值偏低。', DATA))


@pytest.mark.parametrize('legitimate_count', [1, 2])
@pytest.mark.parametrize('bad', [
    '本公司是大亞（1609.TW）。', '本次標的為大亞（1609.TW）。',
    '大亞（1609.TW）就是本公司。', '本公司（即大亞（1609.TW））營運良好。',
])
def test_single_explicit_rename_is_hard_failure_after_legitimate_peers(legitimate_count, bad):
    text = ('大東電分析。\n## 同業估值\n' + '- 大亞（1609.TW）：同業比較資料。\n' * legitimate_count
            + '- ' + bad)
    assert any('錯置' in issue for issue in validate_company_identity(text, DATA))


@pytest.mark.parametrize('line', [
    '- 大亞（1609.TW）是本公司供應商。',
    '- 本公司是大亞（1609.TW）的主要客戶。',
    '- 大亞（1609.TW）為大東電的同業。',
    '- 本公司為大亞（1609.TW）提供原料。',
])
def test_peer_relationship_is_not_a_same_company_identity_claim(line):
    assert validate_company_identity(peer_report(line), DATA) == []
