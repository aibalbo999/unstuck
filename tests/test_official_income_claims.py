"""Official income is a separate dated source, never a vendor-scalar repair."""
from copy import deepcopy

import pytest

from evidence_exit_gate import evaluate_report_evidence
from official_financial_projection import project_official_financials
from test_tewc_income_reference import income_reference

TEXT = '大東電官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）淨利為 0.032 億元。'


def selected():
    return project_official_financials({'ticker': '1623.TW', 'company_name': '大東電',
        'financial_currency': 'TWD', 'net_income_ttm_raw': 860640000,
        'data_trust_score': 56}, income_reference()['financial_reference'])


def income_claims(text, data):
    return [r for r in evaluate_report_evidence(text, {'data': data})['sampled_claims']
            if r.get('financial_metric') in {'淨利', '稅後淨利'}]


def test_exact_official_individual_income_is_verified_without_changing_vendor_input():
    data = selected(); before = deepcopy(data)
    rows = income_claims(TEXT, data)
    assert len(rows) == 1
    row = rows[0]
    assert row['status'] == 'verified', row
    assert row['verification_scope'] == 'replayed_official_income_fact'
    assert row['independent_primary_source_verified'] is True
    assert row['financial_period'] == '2025-07-01/2026-06-30'
    assert row['expected_value_raw_twd'] == 3200000
    assert row['historical_pit_verified'] is False
    assert row['native_acquisition'] is False
    assert row['ttm_eps_verified'] is False
    assert row['share_count_bridge_verified'] is False
    assert len(row['financial_source_documents']) == 2
    assert all(len(doc['sha256']) == 64 and doc['url'].startswith('https://mopsov.twse.com.tw/')
               for doc in row['financial_source_documents'])
    assert 'raw_response_path' not in str(row)
    assert data == before and data['net_income_ttm_raw'] == 860640000
    assert data['data_trust_score'] == 56


@pytest.mark.parametrize('number', ['-0.032', '0.32', '8.6064'])
def test_wrong_amount_or_sign_mismatches_official_income_not_vendor(number):
    rows = income_claims(TEXT.replace('0.032', number), selected())
    assert len(rows) == 1 and rows[0]['status'] == 'mismatch', rows
    assert rows[0]['expected_value_raw_twd'] == 3200000


@pytest.mark.parametrize('text', [
    TEXT.replace('2025-07-01', '2024-07-01'),
    TEXT.replace('2026-06-30', '2025-06-30'),
    TEXT.replace('個別', '合併'), TEXT.replace('大東電', '台積電'),
    TEXT.replace('TWD', 'USD'), TEXT.replace('TWD ', ''),
    TEXT.replace('個別', ''), TEXT.replace('2025-07-01 至 ', ''),
    TEXT.replace('淨利', '預估淨利'),
    TEXT.replace('。', '，此為台積電資料。'),
    TEXT.replace('。', '，幣別為美元。'),
    TEXT.replace('。', '，合併口徑。'),
    '# 台積電\n' + TEXT,
    '# 2024年度財務分析\n' + TEXT,
    '台積電資料如下：\n' + TEXT,
])
def test_incomplete_or_other_period_issuer_currency_scope_stays_unknown(text):
    rows = income_claims(text, selected())
    assert rows and all(r['status'] == 'unverifiable' for r in rows), rows
    assert all(not r['independent_primary_source_verified'] for r in rows)


@pytest.mark.parametrize('damage', ['source_hash', 'projection_hash', 'source_issuer', 'caller_facts'])
def test_unqualified_originals_or_caller_income_never_supply_verified_fact(damage):
    data = selected()
    if damage == 'source_hash':
        data['official_financial_projection']['reference']['quarterly_document']['sha256'] = '0' * 64
    elif damage == 'projection_hash':
        data['official_financial_projection']['sha256'] = '0' * 64
    elif damage == 'source_issuer':
        data['ticker'] = '2330.TW'
    else:
        data.pop('official_financial_projection')
        data['official_income_facts'] = {'status': 'income_originals_verified', 'net_income_ttm_raw': 3200000}
    rows = income_claims(TEXT, data)
    assert rows and all(r['status'] == 'unverifiable' for r in rows), rows


def test_income_replay_does_not_certify_unsupported_ttm_eps():
    from evidence_financial_amounts import check_financial_amount
    row = check_financial_amount({'financial_amount': True, 'financial_metric': 'EPS',
        'reported_value': 13.61, 'unit': 'TWD', 'raw_text': TEXT.replace('淨利', 'EPS'),
        'financial_period_text': '大東電官方個別財報 TWD TTM（2025-07-01 至 2026-06-30）',
        'financial_actual': True}, {'data': selected()}, 1)
    assert row['status'] == 'unverifiable'
    assert row['independent_primary_source_verified'] is False


@pytest.mark.parametrize('currency', ['NTD', '新臺幣', '新台幣'])
def test_explicit_twd_equivalents_keep_the_same_qualified_source(currency):
    row = income_claims(TEXT.replace('TWD', currency), selected())[0]
    assert row['status'] == 'verified' and row['financial_currency'] == 'TWD'


@pytest.mark.parametrize('currency', ['TWD', 'NTD', '新臺幣', '新台幣'])
def test_immediately_adjacent_suffix_currency_is_also_explicit(currency):
    text = TEXT.replace('TWD ', '').replace('億元', '億元 ' + currency)
    row = income_claims(text, selected())[0]
    assert row['status'] == 'verified' and row['financial_currency'] == 'TWD'


def test_complete_own_income_clause_under_exact_dcf_structural_heading():
    text = '## 二、折現現金流（DCF）估值解讀\n' + TEXT
    assert income_claims(text, selected())[0]['status'] == 'verified'


@pytest.mark.parametrize('suffix', ['TWD，台積電資料', 'TWD，合併口徑', 'TWD USD',
                                   'USD TWD', 'TWDollars', 'NTD，2024年度',
                                   'TWD，未來預測', '台積電資料 TWD'])
def test_suffix_currency_cannot_hide_owner_period_fx_or_projection(suffix):
    text = TEXT.replace('TWD ', '').replace('億元。', '億元 ' + suffix + '。')
    assert income_claims(text, selected())[0]['status'] == 'unverifiable'


def test_caller_alias_cannot_relabel_official_issuer():
    data = selected(); data['company_name'] = '台積電'
    data['company_identity'] = {'allowed_aliases': ['台積電']}
    assert income_claims(TEXT.replace('大東電', '台積電'), data)[0]['status'] == 'unverifiable'


@pytest.mark.parametrize('suffix', ['，此為未知公司資料', '，為2025年度', '，轉為美元',
                                   '，預測仍可成長', '（來源：data.Yahoo）'])
def test_a_qualified_prefix_cannot_hide_incompatible_suffix(suffix):
    assert income_claims(TEXT.replace('。', suffix + '。'), selected())[0]['status'] == 'unverifiable'


def test_preserved_input_is_used_and_bad_packet_never_repairs_from_current_values():
    import hashlib
    import json
    from report_analysis_evidence import capture_analysis_evidence
    data = selected()
    data['analysis_input_hash'] = hashlib.sha256(json.dumps(data, ensure_ascii=False,
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    data['analysis_input_cutoff'] = '2026-10-24T02:00:00+08:00'
    packet = capture_analysis_evidence({'data': data})
    assert packet['input_verification'] == 'hash_verified'
    current = deepcopy(data); current['official_financial_projection']['sha256'] = '0' * 64
    snapshot = {'data': current, 'analysis_evidence': packet, 'refreshed_without_analysis_rerun': True}
    row = evaluate_report_evidence(TEXT, snapshot)['sampled_claims'][0]
    assert row['status'] == 'verified' and row['expected_value_raw_twd'] == 3200000
    packet['sections']['analysis_input']['data']['net_income_ttm_raw'] += 1
    assert evaluate_report_evidence(TEXT, snapshot)['sampled_claims'][0]['status'] == 'unverifiable'


@pytest.mark.parametrize('heading', ['## 二、獲利趨勢深析', '## 二、 獲利趨勢深析'])
def test_native_agent2_profit_heading_preserves_exact_dated_income_scope(heading):
    # Exact section mandated by agents.json; no semantic issuer/period content
    # is discarded. Keep the monetary statement independent of bullet labels.
    rows = income_claims(heading + '\n\n' + TEXT, selected())
    assert len(rows) == 1 and rows[0]['status'] == 'verified', rows
    assert rows[0]['financial_period'] == '2025-07-01/2026-06-30'


@pytest.mark.parametrize('heading', [
    '## 二、其他獲利趨勢深析', '## 二、獲利趨勢深析補充',
    '## 二、同業獲利趨勢深析', '## 二、台積電獲利趨勢深析',
    '## 二、2024年度獲利趨勢深析', '## 二、美元獲利趨勢深析',
    '## 二、預測獲利趨勢深析', '## 二、合併獲利趨勢深析',
])
def test_native_profit_heading_match_does_not_discard_semantic_qualifiers(heading):
    rows = income_claims(heading + '\n\n' + TEXT, selected())
    assert rows and all(row['status'] == 'unverifiable' for row in rows), rows


@pytest.mark.parametrize('body', [
    TEXT.replace('大東電', '台積電'), TEXT.replace('TWD', 'USD'),
    TEXT.replace('2025-07-01', '2024-07-01'), TEXT.replace('個別', '合併'),
    TEXT.replace('淨利', '預測淨利'), '未知公司資料如下：\n' + TEXT,
    '2024年度資料如下：\n' + TEXT,
    '- 淨利表現與 TTM 數據：' + TEXT,
])
def test_native_profit_heading_never_clears_body_or_parent_scope(body):
    rows = income_claims('## 二、獲利趨勢深析\n' + body, selected())
    assert rows and all(row['status'] == 'unverifiable' for row in rows), rows


# Native dated-evidence memo labels are structural, never issuer/date evidence.
def native_income_finding(text=TEXT):
    return '## 證據時點與來源\n- **發現**：' + text


def test_native_finding_exact_label_still_requires_the_original_official_scope():
    row = income_claims(native_income_finding(), selected())[0]
    assert row['status'] == 'verified'
    assert row['independent_primary_source_verified'] is True
    assert row['expected_value_raw_twd'] == 3200000


@pytest.mark.parametrize('change', [
    lambda s:s.replace('大東電','台積電'),
    lambda s:s.replace('個別','合併'),
    lambda s:s.replace('TWD','USD'),
    lambda s:s.replace('2025-07-01 至 2026-06-30','2024-07-01 至 2025-06-30'),
    lambda s:s.replace('（2025-07-01 至 2026-06-30）',''),
    lambda s:s.replace('TWD ',''),
    lambda s:s.replace('發現','公司預測'),
    lambda s:s.replace('## 證據時點與來源','## 同業證據時點與來源'),
    lambda s:'# 台積電\n'+s,
    lambda s:'# 合併財報\n'+s,
    lambda s:'# 2024年度財務\n'+s,
    lambda s:'# 美元財務\n'+s,
    lambda s:'# 未來預測\n'+s,
    lambda s:s.replace('億元。','億元，另有台積電資料。'),
])
def test_native_finding_cannot_hoist_other_scope_or_invent_missing_period(change):
    rows = income_claims(change(native_income_finding()), selected())
    assert rows and all(r['status']=='unverifiable' for r in rows)
    assert all(not r['independent_primary_source_verified'] for r in rows)


def test_native_finding_wrong_amount_remains_mismatch_against_official():
    row=income_claims(native_income_finding(TEXT.replace('0.032','0.32')),selected())[0]
    assert row['status']=='mismatch' and row['expected_value_raw_twd']==3200000


@pytest.mark.parametrize('amount',['0.032','8.6064','0.8606'])
def test_official_ttm_shorthand_cannot_fall_back_to_vendor_even_if_value_matches(amount):
    row=income_claims('大東電官方個別 TTM 淨利為 '+amount+' 億元新臺幣。',selected())[0]
    assert row['status']=='unverifiable' and row['candidate_count']==0
    assert row['matched_path']=='' and row['independent_primary_source_verified'] is False


def test_bare_vendor_ttm_keeps_its_original_scope_and_wrong_value_is_rejected():
    good=income_claims('TTM淨利為8.6064億元。',selected())[0]
    bad=income_claims('TTM淨利為0.8606億元。',selected())[0]
    assert good['status']=='verified' and good['matched_path']=='data.net_income_ttm_raw'
    assert good['independent_primary_source_verified'] is False
    assert bad['status']=='mismatch'


# Revision38: a dated, unbound money label must not use a current scalar.
def _annual_fcf_boundary_data():
    return {'ticker':'1623.TW','company_name':'大東電','financial_currency':'TWD',
            'years':[2022,2023,2024,2025],'fcf_history':[-0.3,-0.43,0.08,-0.23],
            'free_cash_flow':-2.47,'free_cash_flow_raw':-247269000,
            'unit_contract':{'money':'billion_twd'}}


@pytest.mark.parametrize('prefix', [
    '歷史年度 snapshot FCF（億元新臺幣）分別為 2022',
    '台積電年度 FCF（億元新臺幣）2022',
    '大東電合併年度 FCF（億元新臺幣）2022',
    '大東電年度 FCF（億美元）2022',
    '大東電2022年度與最新TTM FCF',
    '預測2030年度FCF',
])
@pytest.mark.parametrize('value', ['-3.0','-2.47'])
def test_dated_unitless_fcf_label_never_borrows_current_ttm(prefix,value):
    text=prefix+': '+value
    rows=evaluate_report_evidence(text,{'data':_annual_fcf_boundary_data()})['sampled_claims']
    assert len(rows)==1, rows
    row=rows[0]
    assert row['reported_value']==float(value) and row['raw_text']==text
    assert row['status']=='unverifiable' and row['candidate_count']==0, row
    assert row['matched_path']=='' and row['unit']=='', row
    assert not row['independent_primary_source_verified']


@pytest.mark.parametrize('text,status,source', [
    ('大東電2022年度FCF為-3.0億元。','verified','fcf_history[0]'),
    ('大東電2022年度FCF為-0.3億元。','mismatch','fcf_history[0]'),
    ('大東電2024年度FCF為0.8億元。','verified','fcf_history[2]'),
    ('大東電2024年度FCF為0.08億元。','mismatch','fcf_history[2]'),
    ('大東電TTM FCF為-0.247269億元。','mismatch','free_cash_flow_raw'),
])
def test_complete_fcf_periods_keep_native_year_or_ttm_comparator(text,status,source):
    rows=evaluate_report_evidence(text,{'data':_annual_fcf_boundary_data()})['sampled_claims']
    assert len(rows)==1 and rows[0]['status']==status,rows
    assert source in rows[0]['matched_path'],rows


@pytest.mark.parametrize('text', [
    '台積電2022年度FCF為-3.0億元。',
    '大東電2030年度FCF為-3.0億元。',
    '大東電2022年度FCF為-3.0億美元。',
    '大東電2022年度與TTM FCF為-3.0億元。',
])
def test_annual_boundary_fix_does_not_admit_unknown_owner_period_scope_or_fx(text):
    rows=evaluate_report_evidence(text,{'data':_annual_fcf_boundary_data()})['sampled_claims']
    assert rows and all(r['status']=='unverifiable' for r in rows),rows


@pytest.mark.parametrize('word', ['自由現金流','FCF'])
@pytest.mark.parametrize('join', ['與近','及約','和近'])
def test_postfix_fcf_and_following_debt_are_two_distinct_amounts(word,join):
    text=f'大東電TTM負2.47億元的{word}{join}29億元的有息負債壓力。'
    rows=evaluate_report_evidence(text,{'data':_annual_fcf_boundary_data()})['sampled_claims']
    assert len(rows)==2,rows
    fcf=[r for r in rows if r.get('financial_metric')in {'FCF','自由現金流'}]
    debt=[r for r in rows if r.get('financial_metric')=='有息負債']
    assert len(fcf)==len(debt)==1,rows
    assert fcf[0]['reported_value']==-2.47 and fcf[0]['status']=='unverifiable'
    assert fcf[0]['financial_arithmetic_consistent']is True and not fcf[0]['financial_period_verified']
    assert debt[0]['reported_value']==29 and debt[0]['status']=='unverifiable'
    assert debt[0]['candidate_count']==0 and not debt[0]['matched_path']
    assert all(r['raw_text']==text for r in rows)


@pytest.mark.parametrize('number,status', [('負2.47','unverifiable'),('2.47','mismatch'),
    ('正2.47','mismatch'),('-2.47','unverifiable'),('負0.247','mismatch')])
def test_postfix_ttm_sign_is_local_and_opposite_or_wrong_amount_still_fails(number,status):
    text=f'大東電TTM {number}億元的自由現金流。'
    rows=evaluate_report_evidence(text,{'data':_annual_fcf_boundary_data()})['sampled_claims']
    assert len(rows)==1 and rows[0]['status']==status,rows
    assert rows[0]['expected_value_raw_twd']==-247269000,rows
    assert not rows[0]['financial_period_verified']


@pytest.mark.parametrize('text', [
    '大東電TTM並非負2.47億元的自由現金流。',
    '大東電TTM不是不負2.47億元的自由現金流。',
    '大東電TTM負-2.47億元的自由現金流。',
    '大東電TTM負+2.47億元的自由現金流。',
    '台積電TTM負2.47億元的自由現金流。',
    '大東電USD TTM負2.47億元的自由現金流。',
    '大東電2023年度與TTM負2.47億元的自由現金流。',
])
def test_postfix_direction_does_not_certify_ambiguous_or_foreign_scope(text):
    rows=evaluate_report_evidence(text,{'data':_annual_fcf_boundary_data()})['sampled_claims']
    assert len(rows)==1 and rows[0]['status']=='unverifiable',rows
    assert not rows[0]['independent_primary_source_verified']


@pytest.mark.parametrize('prefix,amount,status', [
    ('大東電2024年度', '0.8','verified'),
    ('大東電2024年度負','0.8','mismatch'),
    ('大東電2022年度負','3.0','verified'),
    ('大東電2022年度','3.0','mismatch'),
])
def test_postfix_direction_keeps_explicit_annual_comparisons(prefix,amount,status):
    text=f'{prefix}{amount}億元的自由現金流。'
    rows=evaluate_report_evidence(text,{'data':_annual_fcf_boundary_data()})['sampled_claims']
    assert len(rows)==1 and rows[0]['status']==status,rows
    assert 'fcf_history' in rows[0]['matched_path']


def test_negative_fcf_elsewhere_does_not_flip_a_positive_postfix_amount():
    text='前期FCF為負。大東電TTM 2.47億元的自由現金流。'
    rows=evaluate_report_evidence(text,{'data':_annual_fcf_boundary_data()})['sampled_claims']
    assert len(rows)==1 and rows[0]['reported_value']==2.47 and rows[0]['status']=='mismatch',rows


# Revision40: one precise neutral outer heading, same strict whole-clause proof.
def _revision40_capex_clause(amount='0.0315'):
    return ('大東電官方個別 TTM（2025-07-01 至 2026-06-30）'
            'CapEx（PPE 及無形資產取得支出）為 '+amount+' 億元新臺幣。')


def _revision40_capex_text(clause=None, ancestor='## 估值解讀與資料品質警示'):
    return ancestor+'\n\n### 二、 現金流與獲利品質分析\n\n'+(clause or _revision40_capex_clause())


def test_revision40_exact_neutral_heading_consumes_full_capex_definition_and_replays_both_sources():
    data=selected();before=deepcopy(data);text=_revision40_capex_text()
    packet=evaluate_report_evidence(text,{'data':data});assert packet['claim_count']==1
    row=packet['sampled_claims'][0]
    assert row['status']=='verified' and row['independent_primary_source_verified']is True
    assert row['financial_definition']=='購置不動產廠房設備及無形資產現金支出合計'
    assert row['financial_component_signed_raw_twd']=={'ppe_purchase':-2250000,'intangible_purchase':-900000}
    assert row['expected_value_raw_twd']==3150000 and row['source_signed_raw_twd']==-3150000
    assert row['financial_amount_convention']=='cash_purchase_outflow_magnitude'
    assert row['financial_period']=='2025-07-01/2026-06-30'
    assert row['financial_period_formula']=='prior_annual + current_ytd - prior_ytd'
    assert len(row['financial_source_documents'])==2
    assert all(len(d['sha256'])==64 and d['url'].startswith('https://mopsov.twse.com.tw/') for d in row['financial_source_documents'])
    assert row['raw_text']==_revision40_capex_clause()
    assert row['financial_narrative_resolution']['original_claim_unchanged']is True
    assert not row['historical_pit_verified'] and data==before


@pytest.mark.parametrize('amount',['0.315','-0.0315','0.0225'])
def test_revision40_full_definition_wrong_total_or_sign_remains_mismatch(amount):
    row=evaluate_report_evidence(_revision40_capex_text(_revision40_capex_clause(amount)),{'data':selected()})['sampled_claims'][0]
    assert row['status']=='mismatch' and row['expected_value_raw_twd']==3150000


@pytest.mark.parametrize('ancestor',[
    '## 台積電估值解讀與資料品質警示', '## 同業估值解讀與資料品質警示',
    '## 合併估值解讀與資料品質警示', '## 2025年度估值解讀與資料品質警示',
    '## 美元估值解讀與資料品質警示', '## 預測估值解讀與資料品質警示',
    '## 公司未來分析', '# 台積電\n## 估值解讀與資料品質警示',
    '# 合併財報\n## 估值解讀與資料品質警示', '# 2024年度\n## 估值解讀與資料品質警示',
    '# 美元財報\n## 估值解讀與資料品質警示', '# 未來預測\n## 估值解讀與資料品質警示',
])
def test_revision40_does_not_strip_incompatible_or_unknown_ancestors(ancestor):
    rows=evaluate_report_evidence(_revision40_capex_text(ancestor=ancestor),{'data':selected()})['sampled_claims']
    assert len(rows)==1 and rows[0]['status']=='unverifiable'
    assert not rows[0]['independent_primary_source_verified']


@pytest.mark.parametrize('change',[
    lambda s:s.replace('大東電','台積電'),lambda s:s.replace('個別','合併'),
    lambda s:s.replace('2025-07-01','2024-07-01'),lambda s:s.replace('2026-06-30','2025-06-30'),
    lambda s:s.replace('（2025-07-01 至 2026-06-30）',''),
    lambda s:s.replace('新臺幣','美元'),lambda s:s.replace('億元新臺幣','億日圓'),
    lambda s:'若'+s,lambda s:'預計'+s,
    lambda s:s.replace('CapEx（PPE 及無形資產取得支出）','CapEx'),
    lambda s:s.replace('CapEx（PPE 及無形資產取得支出）','CapEx（PPE）'),
    lambda s:s.replace('取得支出','餘額'),lambda s:s.replace('取得支出','合併取得支出'),
    lambda s:s.replace('新臺幣。','新臺幣（淨流入）。'),
    lambda s:s.replace('新臺幣。','新臺幣，這是台積電資料。'),
    lambda s:s.replace('新臺幣。','新臺幣，屬2024年度。'),
])
def test_revision40_keeps_owner_period_currency_definition_and_postfix_boundaries(change):
    rows=evaluate_report_evidence(_revision40_capex_text(change(_revision40_capex_clause())),{'data':selected()})['sampled_claims']
    assert len(rows)==1 and rows[0]['status']=='unverifiable',rows
    assert not rows[0]['independent_primary_source_verified']


@pytest.mark.parametrize('damage',['annual_hash','quarter_hash','missing_annual','wrong_issuer'])
def test_revision40_requires_both_same_issuer_original_documents(damage):
    data=selected();ref=data['official_financial_projection']['reference']
    if damage=='annual_hash':ref['annual_document']['sha256']='0'*64
    elif damage=='quarter_hash':ref['quarterly_document']['sha256']='0'*64
    elif damage=='missing_annual':ref.pop('annual_document')
    else:data['ticker']='2330.TW'
    rows=evaluate_report_evidence(_revision40_capex_text(),{'data':data})['sampled_claims']
    assert len(rows)==1 and rows[0]['status']=='unverifiable'
    assert not rows[0]['independent_primary_source_verified']

# The complete own-period assertion remains bound under Agent 5's native
# financial-quality subsection; the subsection never supplies missing facts.
def test_explicit_official_income_under_native_financial_quality_subsection():
    text = '## 六、成長潛力總評\n\n### 現金流與獲利品質分析\n\n' + TEXT
    row = income_claims(text, selected())[0]
    assert row['status'] == 'verified'
    assert row['financial_period'] == '2025-07-01/2026-06-30'
    assert row['independent_primary_source_verified'] is True


@pytest.mark.parametrize('ancestor', [
    '# 台積電', '# 2024年度財務分析', '# 合併財務分析', '# 美元財務分析',
    '# 未來預測', '# 資金受限導致成長受阻',
])
def test_neutral_financial_quality_subsection_cannot_hide_other_scope(ancestor):
    text = ancestor + '\n\n### 現金流與獲利品質分析\n\n' + TEXT
    row = income_claims(text, selected())[0]
    assert row['status'] == 'unverifiable'
    assert row['independent_primary_source_verified'] is False


@pytest.mark.parametrize('changed', [
    TEXT.replace('大東電', '台積電'),
    TEXT.replace('2025-07-01', '2024-07-01'),
    TEXT.replace('個別', '合併'),
    TEXT.replace('TWD', 'USD'),
    TEXT.replace('TWD ', ''),
    TEXT.replace('淨利', '預估淨利'),
])
def test_neutral_financial_quality_subsection_never_supplies_missing_claim_scope(changed):
    text = '## 六、成長潛力總評\n\n### 現金流與獲利品質分析\n\n' + changed
    row = income_claims(text, selected())[0]
    assert row['status'] == 'unverifiable'
    assert row['independent_primary_source_verified'] is False


"""Explicit official-income citations cannot borrow a different vendor scope."""
from copy import deepcopy
import pytest
from evidence_exit_gate import evaluate_report_evidence
from official_financial_projection import project_official_financials
from test_tewc_income_reference import income_reference

def official_citation_selected():
 return project_official_financials({'ticker':'1623.TW','company_name':'大東電',
  'financial_currency':'TWD','net_income_ttm_raw':860640000},income_reference()['financial_reference'])
def official_citation_claims(text,data):
 return [r for r in evaluate_report_evidence(text,{'data':data})['sampled_claims']if r.get('financial_metric')in {'淨利','稅後淨利'}]
@pytest.mark.parametrize('path',['data.cash_flow.official_income_facts',
 'data.cash_flow.official_income_facts.source_documents[*].url',
 'cash_flow.official_income_facts.source_documents[].url',
 'data.cash_flow.official_income_facts.source_documents[0].url'])
def test_own_explicit_official_source_without_scope_stays_unknown(path):
 data=official_citation_selected();before=deepcopy(data)
 rows=official_citation_claims(f'TTM淨利為0.032億元新臺幣（來源：`{path}` 完整雙原件鏈）。',data)
 assert len(rows)==1
 assert rows[0]['status']=='unverifiable'and rows[0]['verification_reason_code']=='official_income_scope_unbound_no_vendor_fallback'
 assert rows[0]['candidate_count']==0 and rows[0]['matched_path']==''
 assert data==before and data['net_income_ttm_raw']==860640000

def test_pure_vendor_claim_keeps_its_comparison():
 rows=official_citation_claims('TTM淨利為8.6064億元新臺幣（來源：data.net_income_ttm_raw）。',official_citation_selected())
 assert rows[0]['status']=='verified'and rows[0]['matched_path']=='data.net_income_ttm_raw'

def test_wrong_fully_qualified_official_amount_still_mismatches_official_fact():
 rows=official_citation_claims('大東電官方個別財報TWD TTM（2025-07-01至2026-06-30）淨利為8.6064億元（來源：data.cash_flow.official_income_facts）。',official_citation_selected())
 assert rows[0]['status']=='mismatch'and rows[0]['expected_value_raw_twd']==3200000

@pytest.mark.parametrize('change',[
 ('大東電','台積電'),('2025-07-01','2024-07-01'),('TWD','USD'),('個別','合併')])
def test_citation_cannot_qualify_wrong_owner_period_currency_or_scope(change):
 text='大東電官方個別財報TWD TTM（2025-07-01至2026-06-30）淨利為0.032億元（來源：data.cash_flow.official_income_facts.source_documents[*].url）。'
 rows=official_citation_claims(text.replace(*change),official_citation_selected())
 assert rows and all(r['status']=='unverifiable'and not r['independent_primary_source_verified']for r in rows)

def test_neighbor_citation_cannot_supply_a_verified_official_scope():
 text='本次參考data.cash_flow.official_income_facts。\nTTM淨利為0.032億元新臺幣。'
 assert not any(r['status']=='verified'and r.get('independent_primary_source_verified')for r in official_citation_claims(text,official_citation_selected()))


"""Own qualified official-source citations retain all scope boundaries."""
from copy import deepcopy
import pytest
from evidence_exit_gate import evaluate_report_evidence
from official_financial_projection import project_official_financials
from test_tewc_income_reference import income_reference

QUALIFIED_NI_BASE='大東電官方個別財報TWD TTM（2025-07-01至2026-06-30）淨利為0.032億元'
QUALIFIED_NI_SOURCE='（來源：`data.cash_flow.official_income_facts.source_documents[*].url` 完整FY2025＋2026Q2官方個別雙原件鏈）'
def qualified_citation_selected():
 return project_official_financials({'ticker':'1623.TW','company_name':'大東電','financial_currency':'TWD','net_income_ttm_raw':860640000},income_reference()['financial_reference'])
def qualified_citation_rows(text,data=None):
 return [r for r in evaluate_report_evidence(text,{'data':qualified_citation_selected()if data is None else data})['sampled_claims']if r.get('financial_metric')in {'淨利','稅後淨利'}]
@pytest.mark.parametrize('source',[QUALIFIED_NI_SOURCE,QUALIFIED_NI_SOURCE.replace('完整FY2025＋2026Q2官方個別雙原件鏈','完整雙原件鏈'),QUALIFIED_NI_SOURCE.replace('完整FY2025＋2026Q2官方個別雙原件鏈','的 FY2025 全年與 2026Q2 官方個別雙原件鏈'),QUALIFIED_NI_SOURCE.replace('[*]','[]')])
def test_full_own_citation_verifies_replayed_fact(source):
 data=qualified_citation_selected();before=deepcopy(data);r=qualified_citation_rows(QUALIFIED_NI_BASE+source+'。',data)
 assert len(r)==1 and r[0]['status']=='verified'and r[0]['expected_value_raw_twd']==3200000
 assert data==before
@pytest.mark.parametrize('heading',['## Round 1：基本面與護城河','## Round 2：財務與估值','## Round 3：近期催化劑'])
def test_exact_native_round_headings_are_structural(heading):
 r=qualified_citation_rows(heading+'\n'+QUALIFIED_NI_BASE+QUALIFIED_NI_SOURCE+'。')
 assert r[0]['status']=='verified',r
@pytest.mark.parametrize('heading',['# 台積電','# 2024年度財務分析','# 美元財務分析','# 合併財報','# 預測財務分析'])
def test_round_heading_cannot_hide_foreign_ancestor(heading):
 r=qualified_citation_rows(heading+'\n## Round 2：財務與估值\n'+QUALIFIED_NI_BASE+QUALIFIED_NI_SOURCE+'。')
 assert r and all(x['status']=='unverifiable'for x in r),r
@pytest.mark.parametrize('old,new',[
 ('大東電','台積電'),('2025-07-01','2024-07-01'),('2026-06-30','2025-06-30'),
 ('TWD','USD'),('個別','合併'),('FY2025','FY2024'),('2026Q2','2026Q1'),('[*]','[0]'),('source_documents','unknown_documents')])
def test_owner_period_currency_document_or_chain_cannot_be_repaired_by_citation(old,new):
 r=qualified_citation_rows((QUALIFIED_NI_BASE+QUALIFIED_NI_SOURCE+'。').replace(old,new))
 assert r and all(x['status']=='unverifiable'for x in r),r

def test_wrong_official_value_remains_mismatch():
 r=qualified_citation_rows((QUALIFIED_NI_BASE+QUALIFIED_NI_SOURCE+'。').replace('0.032','8.6064'))
 assert r[0]['status']=='mismatch'and r[0]['expected_value_raw_twd']==3200000

def test_bare_second_claim_cannot_inherit_scope_or_first_citation():
 r=qualified_citation_rows(QUALIFIED_NI_BASE+QUALIFIED_NI_SOURCE+'。\nTTM淨利為0.032億元新臺幣'+QUALIFIED_NI_SOURCE+'。')
 assert len(r)==2 and r[0]['status']=='verified'and r[1]['status']=='unverifiable',r

def test_two_own_qualified_amounts_keep_separate_claims():
 r=qualified_citation_rows(QUALIFIED_NI_BASE+QUALIFIED_NI_SOURCE+'。\n'+QUALIFIED_NI_BASE.replace('0.032','8.6064')+QUALIFIED_NI_SOURCE+'。')
 assert len(r)==2 and [x['status']for x in r]==['verified','unverifiable'],r

def test_adjacent_owner_or_forecast_is_not_discarded():
 for tail in ('，此為台積電資料。','，合併口徑。','，此為美元。','，預測未來獲利。'):
  r=qualified_citation_rows(QUALIFIED_NI_BASE+QUALIFIED_NI_SOURCE+tail)
  assert r and all(x['status']=='unverifiable'for x in r),r

# Complete source-document lists and synonymous explicit two-original chains.
NI253_BASE='大東電官方個別財報TWD TTM（2025-07-01至2026-06-30）淨利為0.032億元'
def ni253_selected():
 return project_official_financials({'ticker':'1623.TW','company_name':'大東電',
  'financial_currency':'TWD','net_income_ttm_raw':860640000},income_reference()['financial_reference'])
def ni253_rows(text,data=None):
 return [r for r in evaluate_report_evidence(text,{'data':ni253_selected()if data is None else data})['sampled_claims']if r.get('financial_metric')in {'淨利','稅後淨利'}]
def ni253_source(path='source_documents',chain='之完整FY2025與2026Q2雙原件鏈'):
 return f'（來源：`data.cash_flow.official_income_facts.{path}` {chain}）'
@pytest.mark.parametrize('path',['source_documents','source_documents[*].url','source_documents[].url','source_documents[*]','source_documents[]'])
@pytest.mark.parametrize('chain',['之完整FY2025與2026Q2雙原件鏈','的 完整FY2025與2026Q2雙原件鏈'])
def test_ni253_complete_lists_and_synonymous_chain_are_qualified(path,chain):
 data=ni253_selected();before=deepcopy(data)
 r=ni253_rows(NI253_BASE+ni253_source(path,chain)+'。',data)
 assert len(r)==1 and r[0]['status']=='verified'and r[0]['expected_value_raw_twd']==3200000,r
 assert data==before
@pytest.mark.parametrize('old,new',[
 ('FY2025','FY2024'),('2026Q2','2026Q1'),('source_documents','source_documents[0]'),
 ('source_documents','source_documents.url'),('source_documents','source_document'),
 ('大東電','台積電'),('個別','合併'),('TWD','USD'),('2025-07-01','2024-07-01'),
 ('2026-06-30','2025-06-30'),('淨利為','預估淨利為')])
def test_ni253_wrong_document_chain_or_own_scope_remains_unknown(old,new):
 r=ni253_rows((NI253_BASE+ni253_source()+'。').replace(old,new))
 assert r and all(x['status']=='unverifiable'and not x['independent_primary_source_verified']for x in r),r
@pytest.mark.parametrize('ancestor',['# 台積電','# 2024年度財務分析','# 美元財務分析','# 合併財報','# 預測財務分析'])
def test_ni253_round_does_not_hide_unqualified_ancestor(ancestor):
 r=ni253_rows(ancestor+'\n## Round 2：財務與估值\n'+NI253_BASE+ni253_source()+'。')
 assert r and all(x['status']=='unverifiable'for x in r),r

def test_ni253_correct_source_does_not_make_a_wrong_amount_correct():
 r=ni253_rows((NI253_BASE+ni253_source()+'。').replace('0.032','8.6064'))
 assert r[0]['status']=='mismatch'and r[0]['expected_value_raw_twd']==3200000,r
@pytest.mark.parametrize('separator',['。\n','，','；'])
def test_ni253_bare_followup_does_not_inherit_prior_issuer_or_period(separator):
 r=ni253_rows(NI253_BASE+ni253_source()+separator+'TTM淨利為0.032億元新臺幣'+ni253_source()+'。')
 assert len(r)==2 and r[-1]['status']=='unverifiable'and not r[-1]['independent_primary_source_verified'],r

def test_ni253_bare_source_list_alone_cannot_qualify_official_income():
 r=ni253_rows('TTM淨利為0.032億元新臺幣'+ni253_source()+'。')
 assert r[0]['status']=='unverifiable'and r[0]['candidate_count']==0 and r[0]['matched_path']=='',r

def test_ni253_complete_list_annotation_without_intervening_whitespace():
 text=(NI253_BASE.replace('財報TWD ', ' ')+'新臺幣'
  '（來源：`data.cash_flow.official_income_facts.source_documents`之完整FY2025與2026Q2雙原件鏈）。')
 r=ni253_rows(text)
 assert r[0]['status']=='verified'and r[0]['expected_value_raw_twd']==3200000,r
