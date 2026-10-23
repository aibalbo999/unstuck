"""Saved Neutral attribution is independent of current quality projections."""
import copy
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


def snapshot(setup, **fields):
    return {'pipeline': 'v4', 'rerun_context': {'parsed': {'trade_setup': setup}}, **fields}


def explanation(setup, **fields):
    from report_neutral_reason import build_neutral_explanation
    return build_neutral_explanation(snapshot(setup, **fields), direction='Neutral')


def test_local_fallback_never_claims_model_completed_or_market_observation():
    value = explanation({'trade_direction': 'Neutral', 'source_assessment': {
        'status': 'degraded', 'origin': 'local_deterministic_fallback',
        'output_completion': {'status': 'local_fallback'}}})
    assert value['category'] == 'model_incomplete'
    assert value['model_completed'] is False
    assert '模型結論未完成' in value['summary']


@pytest.mark.parametrize('original,changed', [('Neutral', False), ('Long', True), ('Short', True), (None, None)])
def test_rejection_does_not_invent_original_direction_or_gate_causation(original, changed):
    assessment = {'status': 'degraded', 'reason_codes': ['catalyst_claim_scope_mismatch']}
    if original: assessment['original_direction'] = original
    value = explanation({'trade_direction': 'Neutral', 'source_assessment': assessment})
    assert value['category'] == 'source_rejection'
    assert value['direction_changed_by_gate'] is changed
    assert value['original_direction'] == (original or 'unknown')
    assert value['quality_certified'] is False


@pytest.mark.parametrize('text', ['等待資料可信度恢復正常後再評估',
    '法人資料新鮮度恢復 fresh 後再重新評估', '事件日曆缺漏，等待補件',
    'data_trust 標示 institutional_trading 為 stale'])
def test_explicit_data_wait_uses_saved_reason_instead_of_current_warning(text):
    value = explanation({'trade_direction': 'Neutral', 'observed_signal': text,
                         'source_assessment': {'status': 'observation'}})
    assert value['category'] == 'data_wait'
    assert value['basis'] == 'saved_explicit_data_limitation'
    assert value['evidence'][0]['text'] == text


def test_market_conditions_and_present_quality_warning_are_separate_axes():
    setup = {'trade_direction': 'Neutral', 'core_catalyst': '等待成交量放大突破20日均線後再評估',
             'financial_risk_flags': ['資料限制：FCF期間未核實'],
             'source_assessment': {'status': 'observation'}}
    value = explanation(setup, content_credibility={'status': 'blocked'})
    assert value['category'] == 'market_conditions'
    assert value['quality_certified'] is False
    assert value['direction_changed_by_gate'] is None
    # A missing future event is not proof that the event data feed failed.
    setup['core_catalyst'] = '未來14日無已排定事件，等待股價突破後再評估'
    assert explanation(setup)['category'] == 'market_conditions'
    setup['core_catalyst'] = '資料可信度為 fresh，資料更新於今日；等待股價突破後再評估'
    assert explanation(setup)['category'] == 'market_conditions'


def test_unrecorded_legacy_market_text_stays_unknown():
    assert explanation({'trade_direction': 'Neutral', 'core_catalyst': '等待價格突破20日線'})['category'] == 'unknown'


def test_legacy_explicit_data_or_degradation_prefix_retains_basis_without_invented_origin():
    value = explanation({'trade_direction': 'Neutral', 'core_catalyst': '來源不足，原方向不可執行；等待資料'})
    assert value['category'] == 'data_wait'
    assert value['original_direction'] == 'unknown'
    assert value['direction_changed_by_gate'] is None


def test_reason_projection_is_read_only_and_does_not_apply_to_other_modes_or_directions():
    from report_neutral_reason import build_neutral_explanation
    source = snapshot({'trade_direction': 'Neutral', 'source_assessment': {'status': 'observation'}})
    before = copy.deepcopy(source)
    assert build_neutral_explanation(source, direction='Long') == {}
    assert build_neutral_explanation({**source, 'pipeline': 'v1'}, direction='Neutral') == {}
    assert source == before


def test_conflicting_role_receipt_is_not_attached_to_displayed_setup():
    source = snapshot({'trade_direction': 'Neutral', 'core_catalyst': '等待股價突破'})
    source['rerun_context']['structured_outputs'] = {'24': {'trade_direction': 'Long',
        'source_assessment': {'status': 'degraded', 'original_direction': 'Long'}}}
    from report_neutral_reason import build_neutral_explanation
    value = build_neutral_explanation(source, direction='Neutral')
    assert value['category'] == 'unknown'


def test_age_is_from_original_conclusion_and_update_does_not_make_analysis_new():
    from report_neutral_reason import build_analysis_age
    now = datetime(2026, 10, 23, 8, tzinfo=ZoneInfo('Asia/Taipei'))
    value = build_analysis_age({'conclusion_generated_at': '2026-09-23T09:00:00+08:00',
        'generated_at': '2026-10-23T06:00:00+08:00', 'snapshot_refreshed_at': '2026-10-23T06:00:00+08:00',
        'refreshed_without_analysis_rerun': True}, now=now)
    assert value['age_calendar_days'] == 30
    assert value['basis'] == 'snapshot.conclusion_generated_at'
    assert value['conclusion_stale'] is True
    assert value['over_14_calendar_days'] is True


def test_missing_invalid_or_future_time_does_not_receive_invented_analysis_age():
    from report_neutral_reason import build_analysis_age
    now = datetime(2026, 10, 23, tzinfo=ZoneInfo('Asia/Taipei'))
    for source in ({}, {'generated_at': 'not-a-time'}, {'generated_at': '2026-10-24T00:00:00+08:00'},
                   {'conclusion_generated_at': 'invalid', 'generated_at': '2026-10-22T00:00:00+08:00'}):
        value = build_analysis_age(source, now=now)
        assert value['age_calendar_days'] is None
        assert value['status'] == 'unknown'


def test_refresh_time_is_not_reused_as_original_analysis_time_when_conclusion_date_missing():
    from report_neutral_reason import build_analysis_age
    value = build_analysis_age({'generated_at': '2026-10-23T07:00:00+08:00',
                               'refreshed_without_analysis_rerun': True},
                              now=datetime(2026, 10, 23, 8, tzinfo=ZoneInfo('Asia/Taipei')))
    assert value['age_calendar_days'] is None
    assert value['analysis_generated_at'] == ''
    assert value['conclusion_stale'] is True


def test_naive_saved_timestamp_is_taipei_and_date_precision_is_preserved():
    from report_neutral_reason import build_analysis_age
    now = datetime(2026, 10, 23, 0, 1, tzinfo=ZoneInfo('Asia/Taipei'))
    result = build_analysis_age({'generated_at': '2026-10-22'}, now=now)
    assert result['age_calendar_days'] == 1
    assert result['precision'] == 'date'
    assert result['analysis_generated_at'] == '2026-10-22'


def test_row_payload_adds_readonly_explanation_and_age_without_changing_direction(tmp_path, monkeypatch):
    import json
    import report_index
    monkeypatch.setattr(report_index, 'CACHE_DB_PATH', str(tmp_path / 'index.sqlite3'))
    name = '2330_TW_v4_report_20261022_090000.html'
    (tmp_path / name).write_text('<html></html>')
    (tmp_path / name.replace('.html', '.md')).write_text('# 2330 台積電')
    path = tmp_path / name.replace('.html', '.data.json')
    path.write_text(json.dumps(snapshot({'trade_direction': 'Neutral', 'core_catalyst': '等待量能放大',
        'source_assessment': {'status': 'observation'}}, conclusion_generated_at='2026-10-22T09:00:00+08:00')))
    original = path.read_bytes()
    report_index.upsert_report_metadata(name, output_dir=str(tmp_path), data_trust={'status': 'fresh'})
    reports, _ = report_index.query_report_metadata(page=1, limit=10, output_dir=str(tmp_path), sync_metadata=False)
    assert reports[0]['history_decision']['value'] == 'Neutral'
    assert reports[0]['neutral_explanation']['category'] == 'market_conditions'
    assert reports[0]['analysis_age']['analysis_generated_at'] == '2026-10-22T09:00:00+08:00'
    assert 'analysis_completeness' in reports[0]
    assert path.read_bytes() == original
