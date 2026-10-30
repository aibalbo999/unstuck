from legacy_source_wait_log import source_wait_log

def test_scope_wait_has_safe_reason_and_no_price_payload():
    line=source_wait_log({'scope_id':'a'*64,'ticker':'3324.TWO','maturity_date':'2026-10-07','source_gate':{'reason':'latest_official_price_raw_evidence_missing','provider':999,'raw_evidence':{'secret':'DO-NOT-LOG'}}})
    assert 'ticker=3324.TWO' in line and 'attempt_recorded=false' in line
    assert 'latest_official_price_raw_evidence_missing' in line
    assert 'DO-NOT-LOG' not in line and '999' not in line

def test_untrusted_fields_cannot_inject_payload_or_newline():
    line=source_wait_log({'scope_id':'secret\n','ticker':'3324.TWO\nsecret','maturity_date':'secret','source_gate':{'reason':'error secret'}})
    assert 'secret' not in line and '\n' not in line and 'source_evidence_unavailable' in line

def test_scheduler_emits_scope_wait_without_recording_payload(monkeypatch):
    import asyncio
    import decision_tracking_scheduler as scheduler
    messages=[]
    async def refresh(**kw):return {}
    async def stop(*a):raise asyncio.CancelledError
    monkeypatch.setattr(scheduler.decision_tracking_service,'refresh_tracking_items',refresh)
    monkeypatch.setattr(scheduler.decision_tracking_service,'run_due_backtests',lambda **kw:{'legacy_evidence_revisions':{'source_waits':[{'scope_id':'a'*64,'ticker':'3324.TWO','maturity_date':'2026-10-07','source_gate':{'reason':'latest_official_price_raw_evidence_missing','private':'SECRET'}}]}})
    monkeypatch.setattr(scheduler.asyncio,'sleep',stop)
    import pytest
    with pytest.raises(asyncio.CancelledError):asyncio.run(scheduler._decision_tracking_scheduler_forever(get_output_dir=lambda:'isolated',get_refresh_service=lambda:None,emit_log=messages.append))
    waits=[x for x in messages if 'scope_id=' in x]
    assert len(waits)==1 and '3324.TWO' in waits[0] and 'SECRET' not in ''.join(messages)


def test_validation_rejection_log_distinguishes_errors_and_redacts_payload():
    from legacy_source_wait_log import validation_rejection_log
    line = validation_rejection_log({'scope_id':'a'*64, 'ticker':'3016.TW', 'evidence_session':'2026-10-21',
        'reason':'plan_price_basis_unverified', 'provider':'SECRET', 'price':999})
    assert 'evidence_session=2026-10-21' in line and 'exception=false' in line and 'scored=false' in line
    assert 'plan_price_basis_unverified' in line and 'SECRET' not in line and '999' not in line
    assert '\n' not in validation_rejection_log({'scope_id':'a\nb','reason':'private\nsecret'})


def test_exception_log_names_stage_without_provider_secrets():
    from legacy_source_wait_log import revision_exception_log
    line = revision_exception_log({'scope_id':'a'*64,'ticker':'3016.TW','evidence_session':'2026-10-22',
        'stage':'source_fetch','exception_type':'OSError','error':'PRIVATE TOKEN VALUE'})
    assert 'stage=source_fetch' in line and 'exception_type=OSError' in line and 'exception=true' in line
    assert 'PRIVATE' not in line and 'TOKEN' not in line
