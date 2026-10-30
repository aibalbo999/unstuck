from datetime import datetime

from report_current_quality_summary import build_current_quality_summary


def row(day, blocks=(), warnings=()):
    return {'filename':day+'.html', 'ticker':'2356.TW', 'pipeline_id':'v4', 'report_date':day,
            'report_conformance':{'status':'warning'}, 'evidence_exit_gate':{'verdict':'caution'},
            'content_credibility':{'status':'blocked' if blocks else 'warning',
                 'blocking_issues':[{'id':code} for code in blocks],
                 'warnings':[{'id':code} for code in warnings]}}


def test_reason_counts_are_distinct_reports_and_cohorts_are_taipei_dates():
    rows = [row('2026-10-27 20:34', ['v4_market_session_integrity_invalid'],
                ['v4_raw_fcf_period_unverified']*2),
            row('2026-10-26 18:00', ['v4_trade_reason_source_missing','v4_market_observation_stale']),
            row('bad-date', [], ['future_unknown_code'])]
    result = build_current_quality_summary(rows, scope='all_indexed_reports',
                now=datetime.fromisoformat('2026-10-27T14:30:00+00:00'))
    assert result['audited_reports'] == 3
    assert result['report_date_cohorts']['counts'] == {'today':1,'older':1,'future':0,'unknown':1}
    assert result['content_credibility_warning_counts'] == {'future_unknown_code':1,'v4_raw_fcf_period_unverified':1}
    assert result['reason_classification']['counts_may_overlap'] is True
    assert result['reason_classification']['does_not_establish_root_cause'] is True
    assert result['reason_classification']['reports_by_category']['source_evidence_gap'] == 2
    assert result['reason_classification']['reports_by_category']['unknown'] == 1
    assert result['denominator']['unit'] == 'ticker_pipeline_latest_report'


def test_unknown_or_future_date_is_not_labeled_older_and_caller_rows_not_claimed_latest():
    result = build_current_quality_summary([row('2026-10-28T01:30:00+09:00'), row('bad-date')],
                now=datetime.fromisoformat('2026-10-27T12:00:00+08:00'))
    assert result['report_date_cohorts']['counts'] == {'today':0,'older':0,'future':1,'unknown':1}
    assert result['denominator']['unit'] == 'caller_supplied_report'
