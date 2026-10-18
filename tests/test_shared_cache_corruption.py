"""Corrupt metadata must recover through single flight and preserve cooldowns."""
import hashlib
import math

import pytest

from test_shared_provider_cache import memory_cache


@pytest.mark.parametrize('field', ['fetched_at_epoch', 'fresh_until_epoch',
                                  'retained_until_epoch', 'retry_after_epoch'])
@pytest.mark.parametrize('bad', ['bad', {}, True, -1, math.inf, math.nan, 10**500])
def test_corrupt_time_is_replaced_once_under_shared_lock(monkeypatch, field, bad):
    import shared_provider_cache as shared
    from cache_store import get_cache_json, set_cache_json
    monkeypatch.setattr(shared.time, 'time', lambda: 1000.)
    key = 'shared_provider:v1:' + hashlib.sha256(b'corruption').hexdigest()
    set_cache_json(key, {'value': {'old': True}, 'fetched_at_epoch': 990.,
                        'fresh_until_epoch': 1050., 'retained_until_epoch': 1060.,
                        field: bad}, ttl_seconds=60)
    calls = []
    def acquire():
        calls.append(1)
        return {'new': True}
    value, meta = shared.shared_fetch('corruption', acquire, freshness_seconds=60)
    warm, warm_meta = shared.shared_fetch('corruption', acquire, freshness_seconds=60)
    assert value == warm == {'new': True}
    assert calls == [1] and meta['cache_hit'] is False
    assert warm_meta['cache_hit'] is True
    assert get_cache_json(key)['fetched_at_epoch'] == 1000.


def test_corrupt_data_does_not_remove_a_valid_error_cooldown(monkeypatch):
    import shared_provider_cache as shared
    from cache_store import set_cache_json
    monkeypatch.setattr(shared.time, 'time', lambda: 1000.)
    key = 'shared_provider:v1:' + hashlib.sha256(b'cooldown').hexdigest()
    set_cache_json(key, {'value': {'old': True}, 'fetched_at_epoch': 990.,
                        'fresh_until_epoch': 'bad', 'retained_until_epoch': 1060.,
                        'retry_after_epoch': 1030., 'error_kind': 'TimeoutError'}, ttl_seconds=60)
    calls = []
    value, meta = shared.shared_fetch('cooldown', lambda: calls.append(1), freshness_seconds=60)
    assert value is None and calls == []
    assert meta['cooldown'] is True and meta['retry_after_epoch'] == 1030.
    assert meta['error_kind'] == 'TimeoutError'


def test_corrupt_retention_does_not_break_failure_writeback(monkeypatch):
    import shared_provider_cache as shared
    from cache_store import get_cache_json, set_cache_json
    monkeypatch.setattr(shared.time, 'time', lambda: 1000.)
    key = 'shared_provider:v1:' + hashlib.sha256(b'failure').hexdigest()
    set_cache_json(key, {'value': {'old': True}, 'fetched_at_epoch': 990.,
                        'fresh_until_epoch': 995., 'retained_until_epoch': 'bad'}, ttl_seconds=60)
    calls = []
    def fail():
        calls.append(1)
        raise TimeoutError('private exception detail')
    value, meta = shared.shared_fetch('failure', fail, freshness_seconds=60)
    warm, warm_meta = shared.shared_fetch('failure', fail, freshness_seconds=60)
    assert value is warm is None and calls == [1]
    assert meta['error_kind'] == 'TimeoutError' and warm_meta['cooldown'] is True
    assert get_cache_json(key)['retry_after_epoch'] == 1060.
