"""Engineering release must reject canary before admission, budget or child work."""
import asyncio
import hashlib
import json
import pytest


def test_frozen_input_rejected_before_boundary_or_body():
    from analysis_frozen_canary import frozen_canary_inputs
    source=json.dumps({'ticker':'2330.TW','fetch_date':'2026-09-12',
        'analysis_input_cutoff':'2026-09-12T07:30:00+00:00','data_trust':{}}).encode()
    calls=[]
    async def attempt():
        with frozen_canary_inputs(campaign_id='disabled-fixture',job_id='disabled-job',ticker='2330.TW',
            pipeline_id='v4',source_json=source,source_sha256=hashlib.sha256(source).hexdigest(),
            manifest_sha256='a'*64,boundary_check=lambda stage:calls.append(stage)or True):
            calls.append('scope_entered')
    with pytest.raises(RuntimeError,match='canary.*disabled'):
        asyncio.run(attempt())
    assert calls==[]


def test_reserved_runner_rejects_before_reservation_read(monkeypatch):
    import quality_campaign_runner as runner
    calls=[]
    def forbidden(*args):
        calls.append('reservation_read')
        raise AssertionError('reservation read before disabled gate')
    monkeypatch.setattr(runner,'check_reserved',forbidden)
    with pytest.raises(RuntimeError,match='canary.*disabled'):
        runner.execute_reserved_job(None,None,'disabled-job')
    assert calls==[]


def test_owned_runner_rejects_before_ticket_or_child(monkeypatch):
    import quality_campaign_runner as runner
    calls=[]
    def forbidden(*args,**kwargs):
        calls.append('ticket_read')
        raise AssertionError('ticket read before disabled gate')
    monkeypatch.setattr(runner,'regular_bytes',forbidden)
    with pytest.raises(RuntimeError,match='canary.*disabled'):
        runner.run_owned_job('/does-not-exist-disabled-ticket.json')
    assert calls==[]


def test_bound_dispatcher_rejects_before_plan_or_ledger_access(tmp_path):
    from test_maintenance_canary_dispatch_imports import guarded
    guarded(tmp_path, '''
import maintenance_entry as bootstrap
bundle=bootstrap.load_control_bundle(bootstrap.control_digest())
dispatch=bundle.module('maintenance_canary_dispatch')
try:
    dispatch.ClaimedCanaryDispatch(None,None,queue_name=None,registered_hashes=None,
        remaining=None,analysis_bindings=None,claimed=None,process_binding=None)
except RuntimeError as error:
    assert 'canary' in str(error) and 'disabled' in str(error)
else:
    raise AssertionError('disabled dispatcher accepted an execution request')
assert bundle.module('canary_release_policy').status()['canary_enabled'] is False
assert not any(name in sys.modules for name in ('config','api','analysis_jobs','dotenv'))
''')


@pytest.mark.parametrize('name',['CANARY_ENABLED','STOCK_AGENT_CANARY_ENABLED','STOCK_AGENT_TEST_NO_NETWORK'])
def test_environment_cannot_enable_release_canary(monkeypatch,name):
    import canary_release_policy
    monkeypatch.setenv(name,'true')
    assert canary_release_policy.status()['canary_enabled'] is False
    with pytest.raises(RuntimeError,match='canary.*disabled'):
        canary_release_policy.require_canary_enabled()


@pytest.mark.parametrize('operation', ['prepare', 'claim', 'raw_claim', 'enroll'])
def test_canary_queue_operations_reject_before_redis_or_payload(operation):
    import maintenance_canary_claim as claim
    import maintenance_canary_enrollment as enrollment
    class ForbiddenConnection:
        def __getattr__(self, name):
            raise AssertionError('Redis accessed before disabled gate: ' + name)
    options = dict(queue_name=None, registered_hashes=None, remaining=None, analysis_bindings=None)
    with pytest.raises(RuntimeError, match='canary.*disabled'):
        if operation == 'prepare':
            claim.prepare_analysis_job(ForbiddenConnection(), queue_name=None, binding=None)
        elif operation == 'claim':
            claim.claim_analysis_next(ForbiddenConnection(), **options)
        elif operation == 'raw_claim':
            claim.claim_next(ForbiddenConnection(), queue_name=None, registered_hashes=None, remaining=None)
        else:
            enrollment.enroll_analysis_jobs(ForbiddenConnection(), **options)


def test_public_arm_rejects_before_plan_or_namespace_access(monkeypatch):
    import maintenance_entry as entry
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError('arm touched state or plan before disabled gate')
    monkeypatch.setattr(entry, '_read_plan', forbidden)
    monkeypatch.setattr(entry, 'control_root', forbidden)
    assert entry.main(['--maintenance-arm', '/missing-disabled-plan.json']) == 75
    assert calls == []


@pytest.mark.parametrize('operation', ['create', 'run_next'])
def test_campaign_admission_rejects_before_anchor_lock_or_budget(operation):
    from quality_campaign_protocol import Campaign
    class ForbiddenCampaign:
        def __getattr__(self, name):
            raise AssertionError('Campaign touched before disabled gate: ' + name)
    with pytest.raises(RuntimeError, match='canary.*disabled'):
        if operation == 'create':
            Campaign.create(None, None, None)
        else:
            Campaign.run_next(ForbiddenCampaign())
