"""Explicit ordered financial periods must bind every amount or none."""
import copy
import json

import pytest

from evidence_financial_amounts import check_financial_amount, extract_financial_amounts
from evidence_financial_series import extract_financial_series, financial_series_owner_matches


def data():
    return {
        'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
        'years': ['2022', '2025'], 'revenue_history': [3.90, 6.61],
        'net_income_history': [.09, .82],
        'recent_monthly_revenue': [
            f'2026年{month}月: NT${value}億'
            for month, value in enumerate(['4.77', '3.56', '6.03', '6.19', '4.82', '5.19'], 4)
        ],
    }


def checked(text, source=None):
    source = data() if source is None else source
    extracted = extract_financial_series(text, extract_financial_amounts(text, []))
    result = []
    for claim in extracted:
        if not financial_series_owner_matches(claim, source):
            claim = {**claim, 'financial_scope_unbound': True}
        result.append(check_financial_amount(claim, {'data': source}, 1))
    return result


def test_annual_range_checks_both_endpoints_and_displayed_conversions():
    text = '- **發現**：大東電 2022 至 2025 年營收自 3.90 十億新臺幣（39.0 億元）增長至 6.61 十億新臺幣（66.1 億元），3 年期 CAGR 為 19.23%。'
    claims = checked(text)
    assert len(claims) == 4
    assert [claim['financial_period'] for claim in claims] == ['2022', '2022', '2025', '2025']
    assert all(claim['status'] == 'verified' for claim in claims)
    assert all(claim['independent_primary_source_verified'] is False for claim in claims)


@pytest.mark.parametrize('text', [
    '大東電2022至2025年營收自3.90 billion_twd成長至9.61 billion_twd。',
    '大東電2022至2025年營收自3.90十億新臺幣（39.0億元）成長至6.61十億新臺幣（96.1億元）。',
])
def test_wrong_last_endpoint_or_conversion_is_a_mismatch(text):
    claims = checked(text)
    assert claims[-1]['status'] == 'mismatch'
    assert claims[-1]['financial_period'] == '2025'


def test_same_values_in_both_years_remain_two_distinct_claims():
    claims = checked('大東電2022年至2025年營收由3.90億增長至3.90億。')
    assert len(claims) == 2
    assert [claim['financial_period'] for claim in claims] == ['2022', '2025']
    assert all(claim['status'] == 'mismatch' for claim in claims)


@pytest.mark.parametrize('owner', ['同業大亞', '大亞', '競爭對手', '未知公司'])
def test_other_issuer_cannot_borrow_target_annual_history(owner):
    claims = checked(f'{owner}2022至2025年營收自3.90B成長至6.61B。')
    assert len(claims) == 2
    assert all(claim['status'] == 'unverifiable' for claim in claims)


@pytest.mark.parametrize('prefix', ['同業大亞，', '大亞，', '大亞營收成長率為20%，且', '未知公司財報顯示，', '單位為美元，'])
def test_comma_does_not_erase_unknown_issuer_or_foreign_currency(prefix):
    for text in [prefix + '2022至2025年營收自3.90B成長至6.61B。', prefix + MONTHS]:
        claims = checked(text)
        assert claims and all(claim['status'] == 'unverifiable' for claim in claims)


def test_explicit_issuer_can_start_new_comparison_after_peer_clause():
    claims = checked('同業大亞2022年營收3.90B，大東電2022至2025年營收自3.90B成長至6.61B。')
    assert [claim['status'] for claim in claims] == ['unverifiable', 'verified', 'verified']


@pytest.mark.parametrize('prefix,suffix', [
    ('# 預測情境\n', ''), ('假設', ''), ('', '（forecast）'),
    ('# 同業比較\n', ''), ('', '，單位為美元'),
])
def test_projection_currency_and_peer_heading_do_not_gain_verified_status(prefix, suffix):
    claims = checked(prefix + '2022至2025年營收自3.90B成長至6.61B' + suffix)
    assert len(claims) == 2
    assert all(claim['status'] == 'unverifiable' for claim in claims)


@pytest.mark.parametrize('text', [
    '2025年營收從3.90B躍升至6.61B。',
    '毛利率由2022年的9.7%提升至2025年的18.6%，淨利由0.09十億新臺幣增長至0.82十億新臺幣。',
    '2022至2025年淨利每股由0.09元增長至0.82元。',
])
def test_ambiguous_or_per_share_series_does_not_infer_endpoints(text):
    before = extract_financial_amounts(text, [])
    assert extract_financial_series(text, before) == before


@pytest.mark.parametrize('text,count', [
    ('2025至2022年營收自3.90B成長至6.61B。', 2),
    ('2022至2022年營收自3.90B成長至6.61B。', 2),
    ('2022至2025年營收自3.90B成長至6.61B至8B。', 3),
    ('2022至2025年營收自3.90B成長至6.61B（66.1億元。', 3),
])
def test_invalid_or_incomplete_annual_mapping_never_guesses(text, count):
    claims = checked(text)
    assert len(claims) == count
    assert all(claim['status'] == 'unverifiable' for claim in claims)


MONTHS = '2026 年 4 月至 9 月單月營收分別為 4.77 億、3.56 億、6.03 億、6.19 億、4.82 億與 5.19 億元'


def test_exact_monthly_list_maps_every_amount_in_order():
    claims = checked('然而，資料集顯示 Yahoo 即期營收成長率為 -9.5%，且 ' + MONTHS + '，單月營收波動較大。')
    assert len(claims) == 6
    assert [claim['financial_period'] for claim in claims] == [f'2026-{month:02d}' for month in range(4, 10)]
    assert all(claim['status'] == 'verified' for claim in claims)


def test_wrong_monthly_item_is_mismatch_in_its_month_only():
    claims = checked(MONTHS.replace('6.03 億', '8.03 億'))
    assert [claim['status'] for claim in claims] == ['verified', 'verified', 'mismatch', 'verified', 'verified', 'verified']
    assert claims[2]['financial_period'] == '2026-06'


@pytest.mark.parametrize('text,count', [
    (MONTHS.replace('6.03 億、', ''), 5),
    (MONTHS + '、6.00億元', 7),
    (MONTHS.replace('4 月至 9 月', '9 月至 4 月'), 6),
    (MONTHS + '、未公布', 6),
])
def test_ambiguous_month_mapping_keeps_all_values_unverifiable(text, count):
    claims = checked(text)
    assert len(claims) == count
    assert all(claim['status'] == 'unverifiable' for claim in claims)
    assert all(claim['candidate_count'] == 0 for claim in claims)


def test_monthly_other_owner_forecast_and_currency_stay_unknown():
    for text in ['同業大亞' + MONTHS, '未知公司' + MONTHS, '# Forecast\n' + MONTHS,
                 MONTHS + '，單位為美元']:
        claims = checked(text)
        assert len(claims) == 6
        assert all(claim['status'] == 'unverifiable' for claim in claims)


def test_existing_claims_and_input_objects_are_preserved():
    text = '大東電2022至2025年營收自3.90B成長至6.61B，單月營收維持在3.56億至6.19億之間。'
    original = extract_financial_amounts(text, [])
    before = copy.deepcopy(original)
    extracted = extract_financial_series(text, original)
    assert original == before
    unrelated = [claim for claim in extracted if not claim.get('financial_series')]
    assert len(unrelated) == 1 and unrelated[0]['reported_value'] == 3.56
    assert unrelated[0]['financial_scope_unbound'] is True


def test_second_application_is_idempotent():
    text = '大東電2022至2025年營收自3.90B成長至6.61B。\n' + MONTHS
    first = extract_financial_series(text, extract_financial_amounts(text, []))
    assert extract_financial_series(text, first) == first


def test_same_first_value_in_another_claim_on_same_line_is_not_erased():
    text = '2022年營收3.90B，大東電2022至2025年營收自3.90B成長至6.61B。'
    claims = checked(text)
    assert len(claims) == 3
    assert [claim['financial_period'] for claim in claims] == ['2022', '2022', '2025']


def test_duplicate_or_wrong_currency_source_does_not_confirm_series():
    for mutation in [{'financial_currency': 'USD'}, {'years': ['2022', '2022']}]:
        claims = checked('大東電2022至2025年營收自3.90B成長至6.61B。', {**data(), **mutation})
        assert all(claim['status'] == 'unverifiable' for claim in claims)


def test_code_fence_and_non_series_claims_remain_untouched():
    text = '```\n' + MONTHS + '\n```\n2025年營收6.61B。'
    original = extract_financial_amounts(text, [])
    assert extract_financial_series(text, original) == original


@pytest.mark.parametrize('owner', ['同業大亞', '未知公司', '單位為美元'])
@pytest.mark.parametrize('layout', ['{owner}：\n- {series}', '{owner}：\n\n- {series}', '- {owner}：\n  - {series}', '- {owner}：\n\n  - {series}'])
def test_paragraph_and_parent_list_scopes_survive_newline(owner, layout):
    for series, count in [('2022至2025年營收自3.90B成長至6.61B。', 2), (MONTHS, 6)]:
        claims = checked(layout.format(owner=owner, series=series))
        assert len(claims) == count
        assert all(claim['status'] == 'unverifiable' for claim in claims)
        assert all(claim['candidate_count'] == 0 for claim in claims)


def test_explicit_issuer_resets_inherited_peer_but_not_currency():
    series = '本公司2022至2025年營收自3.90B成長至6.61B。'
    assert all(claim['status'] == 'verified' for claim in checked('同業大亞：\n- ' + series))
    assert all(claim['status'] == 'unverifiable' for claim in checked('單位為美元：\n- ' + series))


def test_inherited_forecast_never_becomes_an_observed_fact():
    claims = checked('假設情境：\n- 本公司' + MONTHS)
    assert len(claims) == 6
    assert all(claim['verification_reason_code'] == 'financial_projection_not_observed_fact' for claim in claims)


@pytest.mark.parametrize('suffix', ['至10.0億元', '或10.0億元', '至10.0億元或11.0億元', '～10.0億元'])
def test_monthly_range_or_alternative_tail_keeps_every_value_unknown(suffix):
    claims = checked(MONTHS + suffix)
    assert len(claims) == 6 + suffix.count('億元')
    assert all(claim['status'] == 'unverifiable' for claim in claims)
    assert all(claim['candidate_count'] == 0 for claim in claims)
    assert claims[6]['reported_value'] == 10.0


@pytest.mark.parametrize('overflow_first', [False, True])
def test_oversized_endpoint_is_retained_without_nonfinite_json_or_partial_success(overflow_first):
    huge = '9' * 400
    start, end = (huge, '6.61') if overflow_first else ('3.90', huge)
    text = f'本公司2022至2025年營收自{start}B成長至{end}B。'
    from evidence_exit_gate import evaluate_report_evidence
    gate = evaluate_report_evidence(text, {'data': data()})
    json.dumps(gate, allow_nan=False)
    claims = gate['sampled_claims']
    assert len(claims) == 2
    assert all(claim['status'] == 'unverifiable' for claim in claims)
    invalid = [claim for claim in claims if claim.get('financial_series_invalid_number')]
    assert len(invalid) == 1
    assert invalid[0]['reported_value'] is None
    assert invalid[0]['financial_series_amount_text'] == huge


def test_sibling_lists_do_not_share_issuer_scope():
    text = '- 同業大亞：\n  - ' + MONTHS + '\n- 本公司：\n  - ' + MONTHS
    claims = checked(text)
    assert len(claims) == 12
    assert [claim['status'] for claim in claims] == ['unverifiable'] * 6 + ['verified'] * 6


def test_excessive_decimal_precision_stays_a_retained_invalid_claim():
    number = '6.61' + '0' * 25
    claims = checked('本公司2022至2025年營收自3.90B成長至' + number + 'B。')
    assert len(claims) == 2
    assert all(claim['status'] == 'unverifiable' for claim in claims)
    assert claims[1]['financial_series_invalid_number'] == 'numeric_precision_out_of_bounds'
    json.dumps(claims, allow_nan=False)
