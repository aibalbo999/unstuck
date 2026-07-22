def test_token_bucket_reserves_peeks_and_penalizes_with_fixed_clock(monkeypatch):
    import llm_rate_limit_buckets
    from llm_rate_limit_buckets import TokenBucket

    now = {"value": 100.0}
    monkeypatch.setattr(llm_rate_limit_buckets.time, "monotonic", lambda: now["value"])

    bucket = TokenBucket.per_minute(60)

    assert bucket.capacity == 60.0
    assert bucket.refill_per_second == 1.0
    assert bucket.reserve(10) == 0.0
    assert bucket.tokens == 50.0

    now["value"] = 105.0
    assert bucket.peek_wait(56) == 1.0
    assert bucket.reserve(56) == 1.0
    assert bucket.tokens == 0.0
    assert bucket.updated_at == 106.0

    now["value"] = 104.0
    assert bucket.peek_wait(1) == 3.0
    assert bucket.reserve(1) == 3.0
    assert bucket.updated_at == 107.0

    now["value"] = 108.0
    bucket.penalize(5)

    assert bucket.tokens == 0.0
    assert bucket.updated_at == 113.0
