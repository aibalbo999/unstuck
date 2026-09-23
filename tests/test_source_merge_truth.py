from data_fetch.enrichment_merge import _merge_optional_http_bundle


def test_partial_fallback_survives_merge_and_keeps_actual_provider():
    value = {'status': 'partial', 'actual_provider': 'open.er-api.com',
             'rates': {'USD': {'spot': '31.5'}, 'EUR': None}, 'coverage': {'EUR': 'unsupported'}}
    data = {'ticker': '2330.TW', 'source_audit': [{'source': 'taiwan_open_data',
            'provider': 'open.er-api.com', 'status': 'degraded_enrichment', 'record_count': 1,
            'cache_hit': True, 'stale': False, 'fetched_at_epoch': 100.0}]}
    result = _merge_optional_http_bundle(data, {'taiwan_open_data': value}, ('taiwan_open_data',))
    audit = result['source_audit'][-1]
    assert audit['status'] == 'degraded_enrichment'
    assert audit['provider'] == 'open.er-api.com'
    assert audit['cache_hit'] is True
    assert audit['coverage_status'] == 'partial'
    assert result['source_freshness']['taiwan_open_data']['fetched_at_epoch'] == 100.0


def test_failed_refresh_retains_old_payload_without_refreshing_timestamp():
    data = {'ticker': 'AAPL', 'macro_indicators': {'indicators': {'vix': {'value': 18}}},
            'source_freshness': {'macro_indicators': {'fetched_at_epoch': 100.0}},
            'source_audit': [{'source': 'macro_indicators', 'provider': 'FRED', 'status': 'error',
                             'record_count': 0, 'error_kind': 'timeout'}]}
    result = _merge_optional_http_bundle(data, {'macro_indicators': {}}, ('macro_indicators',))
    audit = result['source_audit'][-1]
    assert audit['status'] == 'degraded_enrichment'
    assert audit['stale'] is True
    assert audit['error_kind'] == 'timeout'
    assert result['source_freshness']['macro_indicators']['fetched_at_epoch'] == 100.0


def test_stale_macro_never_becomes_fresh_after_merge():
    value = {'status': 'stale', 'stale': True, 'indicators': {'vix': {'value': 18, 'stale': True}}}
    result = _merge_optional_http_bundle({'ticker': 'AAPL'}, {'macro_indicators': value}, ('macro_indicators',))
    assert result['source_audit'][-1]['stale'] is True
    assert result['source_freshness']['macro_indicators']['is_fresh'] is False
