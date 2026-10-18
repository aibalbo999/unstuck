from report_publication_identity import publication_identity,replay_notice,non_prediction_reason
from data_trust_snapshot import build_data_snapshot
from decision_tracking import build_decision_tracking


def test_saved_data_real_model_repair_has_true_analysis_time_and_not_forecast():
    context={'ticker':'1301.TW','conclusion_generated_at':'2026-10-03T05:00:00+00:00','data':{'analysis_input_cutoff':'2026-10-03T03:40:45+00:00','daily_market_data':{'as_of':'2026-10-02'}},'saved_data_repair_validation':{'source_filename':'old.html','source_conclusion_generated_at':'2026-10-03T03:41:24+00:00','new_model_calls':2}}
    value=build_data_snapshot(context,pipeline_id='v4',generated_at='2026-10-03T05:01:00+00:00')
    identity=publication_identity(value)
    assert identity['kind']=='saved_data_repair_validation' and not identity['prediction_eligible']
    assert identity['analysis_generated_at']==context['conclusion_generated_at']
    assert identity['analysis_input_cutoff']==context['data']['analysis_input_cutoff']
    assert value['saved_data_repair_validation']==context['saved_data_repair_validation']
    notice=replay_notice(value)
    assert '本次重新呼叫模型' in notice and '未產生新模型預測' not in notice
    assert build_decision_tracking({},snapshot=value)['status']=='excluded_validation'
    assert non_prediction_reason(identity)=='saved_data_repair_validation_not_prediction'


def test_ordinary_forecast_still_eligible():
    assert publication_identity({'generated_at':'2026-10-03T05:00:00Z'})['prediction_eligible']
