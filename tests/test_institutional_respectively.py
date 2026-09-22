"""Only explicit ordered two-member flow statements receive paired subjects."""
import copy
import pytest
from institutional_evidence import institutional_evidence_issues, institutional_evidence_diagnostics

TEXT = ('外資與自營商近30個交易日呈現賣超，分別達 -7,050.84 千股與 -670.01 千股；'
        '投信則買超3,035.00千股，法人整體呈現動能分歧。')


def data():
    return {'ticker': '2610.TW', 'institutional_trading': {
        'source': 'FinMind TaiwanStockInstitutionalInvestorsBuySell',
        'latest_date': '2026-09-22', 'lookback_trading_days': 30,
        'net_buy_thousand_shares_by_category': {
            'foreign': -7050.84, 'dealer': -670.01, 'investment_trust': 3035.0},
    }}


def test_ordered_subjects_and_one_shared_explicit_period_match_each_source():
    assert institutional_evidence_issues(TEXT, data()) == []


@pytest.mark.parametrize('text', [
    TEXT.replace('外資與自營商', '自營商與外資'),
    TEXT.replace('外資與自營商', '外資與投信'),
    TEXT.replace('近30', '近5'),
    TEXT.replace('-670.01', '-6700.1'),
    TEXT.replace('呈現賣超', '呈現買超').replace('-7,050.84', '7,050.84').replace('-670.01', '670.01'),
    TEXT.replace('千股與', '千張與'),
    TEXT.replace('；投信則', '；投信近5日則'),
    TEXT.replace('；投信則', '。\n投信則'),
    TEXT.replace('外資與自營商', '外資與外資'),
    TEXT.replace('外資與自營商', '投信與外資與自營商'),
    TEXT.replace('分別達', '合計達'),
])
def test_population_period_value_direction_and_boundary_mutations_still_block(text):
    assert institutional_evidence_issues(text, data())


def test_second_member_is_actually_checked_and_diagnostic_points_at_its_amount():
    bad = TEXT.replace('-670.01', '-6700.1')
    diagnostics = institutional_evidence_diagnostics(bad, data())
    assert any(d['population'] == 'dealer' and '-6700.1' in d['claim'] for d in diagnostics)


def test_paired_observations_must_share_as_of_date_for_period_carry():
    from institutional_evidence import institutional_evidence_records
    rows = institutional_evidence_records(data())
    rows[1]['observed_at'] = '2026-09-21'
    typed = {'ticker': '2610.TW', 'institutional_evidence': {'records': rows}}
    assert institutional_evidence_issues(TEXT, typed)


def test_allowed_source_filter_cannot_be_bypassed_by_ordered_enumeration():
    assert institutional_evidence_issues(TEXT, data(), allowed_paths=[
        'institutional_trading.net_buy_thousand_shares_by_category.foreign'])


@pytest.mark.parametrize('tail', [
    '（近5日）。', '，近5日。', '；近5日。',
    '，及999千股。', '；及999千股。', '（及999千股）。',
    '（來源未閉合。',
])
def test_pair_must_not_ignore_conflicting_or_unclaimed_tail(tail):
    pair = '外資與自營商近30個交易日賣超，分別7050.84千股與670.01千股'
    assert institutional_evidence_issues(pair + tail, data())


def test_explicit_third_subject_still_cannot_append_an_unbound_new_period():
    assert institutional_evidence_issues(TEXT.replace('，法人整體呈現動能分歧。', '（近5日）。'), data())


@pytest.mark.parametrize('suffix', ['（2026-09-21）。', '，截至2026-09-21。', '；9月21日。'])
def test_explicit_third_subject_cannot_borrow_pair_date_for_trailing_date(suffix):
    text = TEXT.replace('，法人整體呈現動能分歧。', suffix)
    assert institutional_evidence_issues(text, data())
