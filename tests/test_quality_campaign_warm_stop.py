"""One owned TERM through a real private normal job; never a formal handover.

Manifest/billing/source/Redis/model leaves are offline fixtures. A pre-existing
watchdog claim is explicitly simulated here: no claim/enrollment/controller or
descendant-settlement coverage is implied. The real OwnedProcess retains its
handle; no process lookup, kill escalation, or campaign job finalization occurs.
"""
import json
from pathlib import Path
import asyncio
import signal
import sys

import pytest
import quality_campaign_runner as runner
from test_maintenance_owned_process import binding, module, wait_path
from test_quality_campaign_owned_normal import reserved_normal_fixture


@pytest.mark.parametrize('case', ['warm_stop', 'warm_stop_duplicate', 'warm_stop_close_error',
                                'warm_stop_pending_task', 'warm_stop_pending_send', 'warm_stop_pending_error',
                                'warm_stop_pending_generator'])
def test_owned_term_unwinds_normal_sdk_without_settling_campaign(tmp_path, case):
    plan, ledger = reserved_normal_fixture(tmp_path, 'v4')
    original = ledger.snapshot()['jobs']['job']
    output = tmp_path / 'job'
    output.mkdir(mode=0o700)
    ticket = output / 'child-ticket.json'
    runner.exclusive_json(ticket, {'manifest_path': str(plan.path), 'manifest_sha256': plan.expected_sha,
        'ledger_pin': runner.ledger_pin(ledger), 'job_id': 'job', 'output': str(output)})
    # Explicit fixture for owned_job's prior-reservation guard, NOT a real
    # watchdog launch or permission for a future formal controller to synthesize it.
    runner.exclusive_json(tmp_path / (ledger.path.name + '.job.watchdog-started.json'), {
        'job_id': 'job', 'ledger_binding_sha256': ledger.binding,
        'deadline_ms': original['deadline_ms'], 'actual_hashes': original['actual_hashes']})
    namespace = tmp_path / 'owner'
    namespace.mkdir(mode=0o700)
    controller = module().OwnedProcess(namespace, binding())
    child = Path(__file__).with_name('test_quality_campaign_owned_normal_child.py')
    try:
        controller.start([sys.executable, '-I', '-B', str(child), str(ticket), case],
            env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}, cwd=tmp_path)
        wait_path(output / 'stop-ready.json', controller.process, seconds=15)
        controller.request_stop()
        controller.request_stop()  # The real handle sends at most one signal.
        lifecycle = controller.wait_for_exit(15)
        assert lifecycle['process_exited'] and lifecycle['returncode'] == 2, lifecycle
        assert lifecycle['stop_requested'] and lifecycle['signal_call_returned']
        assert lifecycle['cleanup_verified'] is lifecycle['handover_verified'] is False
        diagnostic = output / 'offline-fixture-error.txt'
        assert not diagnostic.exists(), diagnostic.read_text() if diagnostic.exists() else ''
        outcome = json.loads((output / 'outcome.json').read_text())
        proof = json.loads((output / 'owned-normal-test-proof.json').read_text())
        assert outcome['status'] == 'partial' and outcome['failure']['error_type'] == 'CancelledError'
        assert (output / 'stop-sdk-cleaned.json').is_file()
        assert proof['sdk_clients_closed'] and proof['transport_restored']
        assert proof['task_cancel_requests'] == 1 and proof['mock_http_calls'] == 1
        cleanup = json.loads((output / 'child-cleanup.json').read_text())
        assert cleanup['stop_requested'] is True and cleanup['job_id'] == 'job'
        assert cleanup['ticket_sha256'] == runner.sha(ticket.read_bytes())
        assert cleanup['manifest_sha256'] == plan.expected_sha
        assert cleanup['outcome_sha256'] == runner.sha((output / 'outcome.json').read_bytes())
        assert cleanup['sdk_cleanup_verified'] is (case != 'warm_stop_close_error')
        assert cleanup['transport_restored'] and cleanup['pending_async_tasks'] == 0
        assert cleanup['pending_async_generators'] == 0
        assert cleanup['pre_shutdown_pending_async_tasks'] == int(case.startswith('warm_stop_pending_'))
        assert cleanup['event_loop_closed'] and cleanup['background_threads'] == 0
        assert cleanup['application_cleanup_verified'] is (case not in ('warm_stop_close_error', 'warm_stop_pending_send', 'warm_stop_pending_error', 'warm_stop_pending_generator'))
        if case.startswith('warm_stop_pending_'):
            pending_proof = json.loads((output / 'stop-pending-cleaned.json').read_text())
            assert pending_proof['task_finally_returned'] and pending_proof['http_calls_total'] == 1
        if case == 'warm_stop_pending_send':
            assert (output / 'stop-new-send-denied.json').is_file()
        assert cleanup['shutdown_http_denials'] == int(case == 'warm_stop_pending_send')
        assert cleanup['shutdown_async_error_types'] == (['RuntimeError'] if case in ('warm_stop_pending_error', 'warm_stop_pending_generator') else [])
        assert cleanup['shutdown_async_error_count'] == int(case in ('warm_stop_pending_error', 'warm_stop_pending_generator'))
        if case == 'warm_stop_pending_generator':
            assert (output / 'stop-generator-cleaned.json').is_file()
        assert cleanup['descendant_settlement_verified'] is cleanup['handover_verified'] is False
        assert (output / 'cleanup-error.json').exists() is (case == 'warm_stop_close_error')
        state = ledger.snapshot()
        assert state['jobs']['job'] == original  # No refund, fail/done, retry or stage promotion.
        assert state['spent']['http'] == state['spent']['transport'] == 1
        assert state['batches']['batch']['ended_ms'] is None and state['stages']['S2'] == 'open'
        assert not (output / 'parent-receipt.json').exists()
    finally:
        if controller.process is not None:
            controller.process.wait(timeout=30)  # Child's offline failsafe is finite; never SIGKILL.
        controller.close()


def test_cli_owns_one_cancel_and_restores_signal_after_cleanup_error(monkeypatch):
    previous = signal.getsignal(signal.SIGTERM)
    observations = []
    async def work(path, *, stop_requested, completion):
        try:
            signal.raise_signal(signal.SIGTERM)
            await asyncio.sleep(0)
            pytest.fail('TERM did not reach owned task')
        finally:
            signal.raise_signal(signal.SIGTERM)
            await asyncio.sleep(0)
            observations.append((stop_requested(), asyncio.current_task().cancelling()))
            raise RuntimeError('Offline cleanup failure')
    monkeypatch.setattr(runner, 'owned_job', work)
    with pytest.raises(RuntimeError, match='Offline cleanup failure'):
        runner.run_owned_job('unused-fixture')
    assert observations == [(True, 1)]
    assert signal.getsignal(signal.SIGTERM) == previous


@pytest.mark.parametrize('case', ['async_generator', 'callback', 'previous_handler'])
def test_shutdown_errors_not_raised_by_runner_close_are_observed(case):
    loop_runner = asyncio.Runner()
    loop = loop_runner.get_loop()
    retained, seen = [], []
    def previous(loop, context):
        seen.append(type(context['exception']).__name__)
        if case == 'previous_handler':
            raise ValueError('Offline handler failure')
    loop.set_exception_handler(previous)
    async def generator():
        try:
            yield 'offline'
        finally:
            raise RuntimeError('Offline async-generator close failure')
    async def begin():
        retained.append(generator())
        assert await anext(retained[0]) == 'offline'
    def failed_callback():
        raise RuntimeError('Offline shutdown callback failed')
    try:
        if case == 'async_generator':
            runner._run_owned_loop(loop_runner, begin())
        else:
            loop.call_soon(failed_callback)
        result = runner._close_owned_loop(loop_runner)
        assert loop.is_closed() and loop.get_exception_handler() is previous
        assert seen == ['RuntimeError'] and result['http_denials'] == 0
        assert result['async_error_types'] == (['RuntimeError', 'ValueError'] if case == 'previous_handler' else ['RuntimeError'])
        assert result['async_error_count'] == len(result['async_error_types'])
    finally:
        loop_runner.close()


@pytest.mark.parametrize('when', ['before', 'during', 'shutdown'])
def test_owned_cli_tracks_async_generators_despite_finmind_loop_patch(tmp_path, when):
    # Real FinMind import globally patches asyncio. Keep it in a fresh guarded
    # process so this regression never changes another test's loop implementation.
    from test_quality_campaign_safety import layout, fresh_guarded_child
    ledger, output = layout(tmp_path)
    result = fresh_guarded_child(ledger, output, 'import canary_release_policy\ncanary_release_policy.require_canary_enabled = lambda: None\nwhen = ' + repr(when) + '\n' + '''
import asyncio
import quality_campaign_runner as runner
def no_env(event, args):
    if event == 'open' and not isinstance(args[0], int) and Path(os.fsdecode(args[0])).name == '.env':
        raise AssertionError('Operator environment must not be read')
sys.addaudithook(no_env)
if when == 'before':
    import FinMind.utility.request
before_hooks = sys.get_asyncgen_hooks()
retained, closed, observed = [], [], []
async def generator():
    try:
        yield 'offline'
    finally:
        closed.append(True)
        raise RuntimeError('Offline async-generator close failure')
async def begin():
    retained.append(generator())
    assert await anext(retained[-1]) == 'offline'
async def work(*args, **kwargs):
    if when != 'before':
        import FinMind.utility.request
    assert asyncio.get_running_loop().run_until_complete.__func__.__module__ == 'nest_asyncio'
    asyncio.get_running_loop().set_exception_handler(
        lambda loop, context: observed.append(type(context['exception']).__name__))
    if when == 'shutdown':
        async def pending():
            try:
                await asyncio.sleep(10)
            finally:
                await begin()
        asyncio.create_task(pending())
        await asyncio.sleep(0)
    else:
        await begin()
    raise ValueError('Offline main-job failure')
runner.owned_job = work
try:
    runner.run_owned_job('unused-offline-ticket')
except ValueError as error:
    assert str(error) == 'Offline main-job failure'
else:
    raise AssertionError('Main job failure was hidden')
assert closed == [True], 'Owned loop omitted a registered async-generator finalizer'
assert observed == ['RuntimeError'], 'Shutdown cleanup error was not observed'
assert sys.get_asyncgen_hooks() == before_hooks, 'Caller async-generator hooks changed'
print('real FinMind patch kept owned async-generator cleanup observable')
''')
    assert 'cleanup observable' in result


def test_owned_asyncgen_tracking_restores_callers_hooks_after_main_failure():
    original = sys.get_asyncgen_hooks()
    caller = (lambda generator: None, lambda generator: None)
    loop_runner = asyncio.Runner()
    async def failed():
        raise ValueError('Offline failure with caller hooks')
    try:
        sys.set_asyncgen_hooks(*caller)
        with pytest.raises(ValueError, match='Offline failure with caller hooks'):
            runner._run_owned_loop(loop_runner, failed())
        assert sys.get_asyncgen_hooks() == caller
        assert runner._close_owned_loop(loop_runner)['async_error_count'] == 0
        assert sys.get_asyncgen_hooks() == caller
    finally:
        sys.set_asyncgen_hooks(*original)
        loop_runner.close()


def test_owned_asyncgen_tracking_rejects_drift_without_overwriting_new_owner():
    original = sys.get_asyncgen_hooks()
    foreign = (lambda generator: None, lambda generator: None)
    loop_runner = asyncio.Runner()
    try:
        with pytest.raises(runner.ReplayAbort, match='hook ownership changed'):
            with runner._owned_asyncgen_tracking(loop_runner.get_loop()):
                sys.set_asyncgen_hooks(*foreign)
        assert sys.get_asyncgen_hooks() == foreign
    finally:
        sys.set_asyncgen_hooks(*original)
        loop_runner.close()
