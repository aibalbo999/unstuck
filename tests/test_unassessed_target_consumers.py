"""Unassessed target explanations must not become comparison/backtest prices."""
from datetime import date

import pytest


@pytest.mark.parametrize('missing', [
    'N/A／未評估（需觀察 2026 Q3/Q4 毛利率是否回升）',
    'N/A／未評估（GDS 發行價 908.32 元為歷史參考）',
])
def test_due_backtest_keeps_unknown_target_and_still_measures_actual_return(monkeypatch, missing):
    import decision_backtest_service as service
    report = {'filename': 'TEST_v1_report.html', 'ticker': 'TEST', 'pipeline_id': 'v1',
              'date': '2025-01-01', 'recommendation': {'recommendation': '買入',
              **{f'target_{h}m': missing for h in (3, 6, 12)}}}
    saved = []
    monkeypatch.setattr(service.report_history_service, 'list_reports', lambda **kw: {'reports': [report]})
    monkeypatch.setattr(service.decision_tracking_store, 'backtest_result_exists', lambda *args: False)
    monkeypatch.setattr(service.decision_tracking_store, 'upsert_backtest_result', saved.append)
    result = service.run_due_backtests(output_dir='unused', as_of=date(2026, 2, 1),
        price_fetcher=lambda *args: {'initial_price': 100, 'actual_price': 110})
    assert result['success'] is True and len(saved) == 3
    assert all(row['target_price'] is None and row['target_error_pct'] is None for row in saved)
    assert all(row['market_return_pct'] == pytest.approx(10) for row in saved)


def test_report_comparison_does_not_compute_fake_target_change_from_na_explanations(monkeypatch):
    import report_compare_service as service
    missing = 'N/A／未評估（需觀察2026 Q3/Q4；當時股價908.32元）'
    def metadata(name, _output):
        return {'filename': name, 'ticker': 'TEST', 'pipeline_id': 'v1',
                'recommendation': {'recommendation': '買入', 'current_price': 100 if name == 'a' else 110,
                  **{f'target_{h}m': missing if name == 'a' else 'NT$120' for h in (3, 6, 12)}}}
    monkeypatch.setattr(service, '_metadata', metadata)
    compared = service.compare_reports('a', 'b', output_dir='unused')['diff']
    for key in ('target_3m', 'target_6m', 'target_12m'):
        assert compared[key]['delta'] is None and compared[key]['delta_pct'] is None
        assert compared[key]['before'] == missing
    assert compared['current_price']['delta'] == 10
    assert compared['current_price']['delta_pct'] == pytest.approx(10)


def test_report_comparison_keeps_real_target_and_market_price_changes(monkeypatch):
    import report_compare_service as service
    def metadata(name, _output):
        return {'filename': name, 'ticker': 'TEST', 'pipeline_id': 'v1',
                'recommendation': {'recommendation': '買入', 'current_price': 100 if name == 'a' else 110,
                  'target_12m': '目標價 NT$120（部分指標 N/A）' if name == 'a' else '目標價 NT$150'}}
    monkeypatch.setattr(service, '_metadata', metadata)
    compared = service.compare_reports('a', 'b', output_dir='unused')['diff']
    assert compared['target_12m']['delta'] == 30
    assert compared['target_12m']['delta_pct'] == pytest.approx(25)
    assert compared['current_price']['delta'] == 10
