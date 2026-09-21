"""September 21 report evidence failures and conservative semantic boundaries."""
import pytest
from evidence_exit_gate import evaluate_report_evidence, extract_numeric_claims


def snapshot(**changes):
    technical = {"as_of": "2026-09-21", "source": "yfinance 5y history", "availability": "available",
                 "sma_5": 53.23, "sma_10": 45.91, "sma_20": 38.04, "sma_60": 34.08,
                 "volume_sma_20": 38.04, "missing_indicators": [], **changes}
    return {"data": {"technical_indicators": technical, "current_price": 38.04, "risk_price": 38.04}}


def claims(text, data):
    return evaluate_report_evidence(text, data, sample_ratio=1, max_sample=100)["sampled_claims"]


REAL_SMA = '- **多頭排列確立**：全友 (2305.TW) 目前 5/10/20/60 日均線呈現標準多頭排列（SMA 5: 53.23 > SMA 10: 45.91 > SMA 20: 38.04 > SMA 60: 34.08），顯示趨勢結構極為強勁。'


def test_multiple_explicit_sma_assignments_bind_each_value_to_its_own_period():
    result = claims(REAL_SMA, snapshot())
    assert len(result) == 4
    assert [c["matched_path"] for c in result] == [f"data.technical_indicators.sma_{p}" for p in (5,10,20,60)]
    assert all(c["status"] == "verified" and c["candidate_count"] == 1 for c in result)


def test_explicit_sma_assignment_with_other_sentence_numbers_is_still_exact():
    text = '"finding": "均線呈多頭排列（SMA5: 30.45 > SMA10: 28.77 > SMA20: 26.76 > SMA60: 20.41），股價收於 3'
    result = claims(text, snapshot(sma_5=30.45, sma_10=28.77, sma_20=26.76, sma_60=20.41))
    assert len(result) == 4 and all(c["status"] == "verified" for c in result)


def test_multi_sma_cannot_borrow_neighbor_period_or_volume_with_equal_value():
    result = claims(REAL_SMA, snapshot(sma_20=22.5, sma_200=38.04))
    actual = next(c for c in result if c["reported_value"] == 38.04)
    assert actual["status"] == "mismatch" and actual["matched_value"] == 22.5


@pytest.mark.parametrize("prefix", ["2026-09-20 ", "2026-09-20與2026-09-21 ", "昨日 ", "新聞報導 ", "成交量 ", "預估 ", "假設 "])
def test_multi_sma_different_date_or_noncanonical_basis_cannot_verify(prefix):
    assert all(c["status"] == "unverifiable" for c in claims(prefix + 'SMA 5: 53.23 > SMA 20: 38.04', snapshot()))


@pytest.mark.parametrize("text", ['SMA 20: 38.04 > SMA 20: 22.5', 'SMA 20: 38.04% > SMA 5: 53.23', 'SMA 20: 38.04-45.0 > SMA 5: 53.23'])
def test_duplicate_period_or_nonprice_claim_does_not_verify_ambiguous_sma(text):
    relevant = [c for c in claims(text,snapshot()) if "20" in c['label']]
    assert all(c["status"] != "verified" for c in relevant)


def test_explicit_same_date_sma_assignments_still_verify():
    assert all(c["status"] == "verified" for c in claims('2026-09-21 SMA5: 53.23 > SMA20: 38.04', snapshot()))


@pytest.mark.parametrize("text", ['- **發現**：5/10/20/60 日均線呈現多頭排列', '- 發現：5／10／20／60日移動平均線呈現向上', '- 週期：5、10、20、60 日均線'])
def test_moving_average_period_enumeration_is_not_a_numeric_price_claim(text):
    assert extract_numeric_claims(text) == []


def test_period_list_does_not_hide_price_on_same_line():
    result = extract_numeric_claims('發現：5/10/20/60 日均線向上；股價：100元')
    assert len(result) == 1 and result[0]['reported_value'] == 100


@pytest.mark.parametrize("text", ['營收：5/10/20/60億元', '股價：5元；10/20/60 日均線', '營收：5；10/20/60 日均線'])
def test_real_values_are_not_discarded_as_period_lists(text):
    assert any(c['reported_value'] == 5 for c in extract_numeric_claims(text))


def stop_snapshot(value='NT$34.20 (突破 30.8x PER 河流圖壓力位)'):
    return {'pipeline': 'v3', 'rerun_context': {'pipeline_id': 'v3', 'parsed': {'short_setup': {'cover_stop': value}}},
            'data': {'current_price': 34.2, 'risk_price': 34.2}, 'other': {'short_setup': {'cover_stop':34.2}}}


def test_cover_stop_matches_only_saved_plan_price_not_valuation_annotation():
    text='- **回補停損:** NT$34.20 (突破 30.8x PER 河流圖壓力位)'
    actual=claims(text,stop_snapshot())[0]
    assert actual['status']=='verified' and actual['candidate_count']==1
    assert actual['matched_path']=='rerun_context.parsed.short_setup.cover_stop'
    assert claims('回補停損：30.8',stop_snapshot())[0]['status']=='mismatch'


@pytest.mark.parametrize('value',[None,'N/A','NT$34.2 或 NT$40','NT$34.2（現價30.5）',True])
def test_missing_or_ambiguous_stop_does_not_borrow_equal_unrelated_price(value):
    assert claims('回補停損：34.2',stop_snapshot(value))[0]['status']=='unverifiable'


def test_missing_canonical_stop_never_borrows_nested_field():
    data=stop_snapshot();del data['rerun_context']['parsed']['short_setup']['cover_stop']
    assert claims('回補停損：34.2',data)[0]['candidate_count']==0


@pytest.mark.parametrize('text',['9/20 SMA20:38.04 > SMA5:53.23', '9月20日 SMA20:38.04 > SMA5:53.23', 'SMA20:38.04 > SMA20:資料不足'])
def test_undated_history_or_duplicate_missing_assignment_does_not_verify(text):
    assert all(c['status']=='unverifiable' for c in claims(text,snapshot()))


@pytest.mark.parametrize('text',['回補停損：34.2（新聞估計）','回補停損：34.2（2026-09-20）'])
def test_stop_from_other_date_or_external_research_is_not_the_saved_plan(text):
    assert claims(text,stop_snapshot())[0]['status']=='unverifiable'


def test_stop_plan_from_another_pipeline_is_not_canonical_v3_evidence():
    data=stop_snapshot();data['pipeline']='v4';data['rerun_context']['pipeline_id']='v4'
    assert claims('回補停損：34.2',data)[0]['status']=='unverifiable'
