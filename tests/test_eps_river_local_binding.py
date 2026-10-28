"""EPS must not inherit a river-chart basis from a different sentence."""
import pytest
from evidence_exit_gate import evaluate_report_evidence, extract_numeric_claims

RIVER = ('依據FinMind歷史資料，2025年EPS為12.42元對應之河流圖區間為：'
         '16.2倍（201.2元）、19.2倍（238.46元）。')
PAIRS = '參考歷史 P/E 河流圖，最近完整年度 (2025) 估值通道為16.2x (201.2元)至19.2x (238.46元)。'


def snapshot():
    return {'data': {'forward_eps': 18.15, 'trailing_eps': 13.04,
        'pe_river_chart': {'years': ['2025'], 'eps_twd': [12.42],
            'multiples': [16.2, 19.2],
            'bands': {'16.2x': [201.2], '19.2x': [238.46]}}}}


def eps_rows(text):
    return [row for row in evaluate_report_evidence(text, snapshot())['sampled_claims']
            if row['label'] == 'EPS']


@pytest.mark.parametrize('prefix', [
    'Forward EPS 18.15元（股數橋接未核實）。',
    'Trailing EPS 13.04元。', 'TTM EPS 13.04元。',
    '2025年EPS為18.15元。', 'EPS 18.15元。',
    'Forward EPS 18.15元；', 'Forward EPS 18.15元! ',
])
def test_other_eps_is_retained_but_not_bound_to_later_river_sentence(prefix):
    rows = eps_rows(prefix + PAIRS)
    assert len(rows) == 1
    assert rows[0]['status'] == 'unverifiable'
    assert rows[0]['candidate_count'] == 0 and not rows[0]['matched_path']
    assert rows[0]['reported_value'] in (18.15, 13.04)
    claims = extract_numeric_claims(prefix + PAIRS)
    assert len([c for c in claims if c['label'] == '河流圖 PER']) == 2
    assert len([c for c in claims if c['label'] == '河流圖價位']) == 2


@pytest.mark.parametrize('prefix', ['Forward ', 'Trailing ', 'TTM ', '預估', ''])
def test_equal_digits_cannot_certify_an_unbound_eps(prefix):
    text = prefix + 'EPS 12.42元，河流圖區間16.2倍（201.2元）、19.2倍（238.46元）。'
    assert eps_rows(text)[0]['status'] == 'unverifiable'


def test_explicit_local_annual_river_relationship_retains_original_comparison():
    rows = eps_rows(RIVER)
    assert len(rows) == 1 and rows[0]['status'] == 'verified'
    assert 'pe_river_chart.eps_twd' in rows[0]['matched_path']


@pytest.mark.parametrize('before,after', [('12.42元', '22.42元'), ('16.2倍', '96.2倍'), ('201.2元', '901.2元')])
def test_genuine_wrong_river_values_are_still_rejected(before, after):
    result = evaluate_report_evidence(RIVER.replace(before, after), snapshot())
    assert result['failed_count'] >= 1 and result['coverage_complete']


def test_two_eps_claims_keep_their_separate_bases_and_denominator():
    rows = eps_rows('Forward EPS 18.15元（股數橋接未核實）。' + RIVER.replace('12.42元', '22.42元'))
    assert [(r['reported_value'], r['status']) for r in rows] == [(18.15, 'unverifiable'), (22.42, 'mismatch')]


def test_generic_forward_label_cannot_fall_back_to_any_eps_snapshot():
    result = evaluate_report_evidence('Forward EPS: 18.15元。' + PAIRS, snapshot())
    rows = [r for r in result['sampled_claims'] if 'EPS' in r['label']]
    assert rows and all(r['status'] == 'unverifiable' for r in rows)


def test_equal_forward_and_annual_digits_cannot_borrow_each_others_basis():
    text = 'Forward EPS: 12.42元，2025年EPS為12.42元對應之河流圖區間為16.2倍（201.2元）。'
    rows = evaluate_report_evidence(text, snapshot())['sampled_claims']
    forward = [row for row in rows if 'Forward' in row['label']]
    assert forward and all(row['status'] == 'unverifiable' for row in forward)
    eps = [row for row in rows if row['label'] == 'EPS']
    assert [row['status'] for row in eps] == ['unverifiable', 'verified']


def annual_snapshot():
    data=snapshot()['data'];data['pe_river_chart']['years']=['2024','2025']
    data['pe_river_chart']['eps_twd']=[11.06,12.42]
    return {'data':data}

def annual_eps_rows(text,data):
    return [row for row in evaluate_report_evidence(text,data)['sampled_claims'] if row['label']=='EPS']

@pytest.mark.parametrize('value,status', [('11.06','verified'),('12.42','mismatch'),('21.06','mismatch')])
def test_explicit_year_selects_only_its_same_index(value,status):
    text='Forward EPS18.15元。2024年EPS為'+value+'元對應之河流圖區間：16.2倍（201.2元）。'
    rows=annual_eps_rows(text,annual_snapshot())
    assert [(r['reported_value'],r['status'])for r in rows]==[(18.15,'unverifiable'),(float(value),status)]
    assert rows[1]['matched_value']==11.06 and rows[1]['matched_path']=='data.pe_river_chart.eps_twd[0]'

@pytest.mark.parametrize('years,values', [(['2025'],[12.42]), ([],[]), (['2024','2024'],[11.06,12.42]),
    (['2024','2025'],[11.06]), (None,[11.06]), (['2024'],[True]), (['2024'],[float('nan')])])
def test_missing_duplicate_or_malformed_year_mapping_stays_unknown(years,values):
    data=annual_snapshot();data['data']['pe_river_chart']['years']=years;data['data']['pe_river_chart']['eps_twd']=values
    text='Forward EPS18.15元。2024年EPS為12.42元對應之河流圖區間：16.2倍（201.2元）。'
    rows=annual_eps_rows(text,data)
    assert len(rows)==2 and all(r['status']=='unverifiable'for r in rows)
    assert rows[1]['candidate_count']==0 and not rows[1]['matched_path']

def test_multiple_annual_eps_get_distinct_year_slots():
    text=('2024年EPS為11.06元對應之河流圖區間：16.2倍（201.2元）。'
          '2025年EPS為11.06元對應之河流圖區間：19.2倍（238.46元）。')
    rows=annual_eps_rows(text,annual_snapshot())
    assert [r['status']for r in rows]==['verified','mismatch']
    assert [r['matched_value']for r in rows]==[11.06,12.42]

def test_kv_annual_eps_cannot_revert_to_generic_closest_year():
    text='2024年EPS: 12.42元對應之河流圖區間：16.2倍（201.2元）。'
    rows=[r for r in evaluate_report_evidence(text,annual_snapshot())['sampled_claims']if 'EPS'in r['label']]
    assert rows and all(r['status']=='mismatch'for r in rows)
