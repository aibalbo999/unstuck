"""Only exact private Redis; original dispatcher and normal CLI with offline leaves."""
import json
import os
import subprocess
from pathlib import Path
import sys


def main():
    root, mode = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']), sys.argv[2]
    sys.path[:0] = [str(Path(__file__).resolve().parent),
        str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parents[1] / 'backend')]
    from test_maintenance_rq_private_integration_child import install_boundary
    install_boundary()
    import maintenance_entry as bootstrap
    control_bundle = bootstrap.load_control_bundle(bootstrap.control_digest())
    # Private Redis/socket-denied fixture only; no product activation switch.
    control_bundle.module('canary_release_policy').require_canary_enabled = lambda: None
    from maintenance_canary_dispatch import ClaimedCanaryDispatch
    import quality_campaign_runner as runner
    from test_quality_campaign_owned_normal import reserved_normal_fixture
    from maintenance_owned_process import OwnedProcess
    from maintenance_entry import control_digest
    from maintenance_canary_claim import prepare_analysis_job, claim_analysis_next
    from maintenance_canary_enrollment import enroll_analysis_jobs
    from redis import Redis
    from redis.retry import Retry
    from redis.backoff import NoBackoff
    case = sys.argv[3] if len(sys.argv) > 3 else 'published'
    source_root = root / 'campaign'
    source_root.mkdir(mode=0o700)
    plan, ledger = reserved_normal_fixture(source_root, mode,
        job_seconds=3 if case == 'blocked_ledger' else 12 if case == 'deadline_stop' else 45)
    binding = {'campaign_id': 'fixture', 'job_id': 'job', 'ticker': '2330.TW',
               'pipeline_id': mode, 'manifest_sha256': plan.expected_sha,
               'timeout_seconds': 1 if case == 'timeout_mismatch' else 45}
    connection = Redis(unix_socket_path=str(root / 'redis.sock'), socket_timeout=2,
        socket_connect_timeout=2, retry=Retry(NoBackoff(), 0), retry_on_error=[])
    job = prepare_analysis_job(connection, queue_name='owned-dispatch', binding=binding)
    job.enqueued_at, job._status = job.created_at, 'queued'
    values = {'queue_name': 'owned-dispatch', 'remaining': [job.id], 'analysis_bindings': {job.id: binding},
        'registered_hashes': {job.id: {key.encode(): value if type(value) is bytes else
            value.encode() if isinstance(value, str) else str(value).encode() for key, value in job.to_dict().items()}}}
    controller = None
    try:
        connection.rpush('rq:queue:ordinary', b'untouched')
        ordinary = connection.dump('rq:queue:ordinary')
        assert enroll_analysis_jobs(connection, **values)['outcome'] == 'enrolled'
        claimed = claim_analysis_next(connection, **values)
        assert claimed['outcome'] == 'claimed'
        original_job = ledger.snapshot()['jobs']['job']
        revision = subprocess.check_output(['git', '-C', str(Path(__file__).resolve().parents[1]), 'rev-parse', 'HEAD'],
                                           env={'PATH': '/usr/bin:/bin'}, text=True).strip()
        process_binding = {'operation_id': 'dispatch-fixture', 'control_sha256': control_digest(), 'backend_revision': revision}
        assert control_bundle.verify()['control_sha256'] == process_binding['control_sha256']
        bootstrap = Path(__file__).with_name('test_quality_campaign_owned_normal_child.py')
        original_start = OwnedProcess.start
        def offline_start(self, command, *, env, cwd, admission_fd=None, owned_session=False):
            # No product test flag: substitute only this test's outer bootstrap.
            # It installs explicit offline leaves and calls the real owned CLI.
            assert command[:4] == [sys.executable, '-I', '-B', str(Path(runner.__file__).resolve())]
            assert command[4] == '--owned-job' and command[6:] == ['--owned-admission-fd', str(admission_fd)]
            result = original_start(self, [sys.executable, '-I', '-B', str(bootstrap), command[5],
                'warm_stop' if case in ('warm_stop', 'deadline_stop') else 'blocked' if case == 'graph_blocked' else 'published', str(admission_fd)],
                env=env, cwd=cwd, admission_fd=admission_fd, owned_session=owned_session)
            if case == 'delivery_failure':
                raise OSError('Offline parent fails after launch, before admission delivery')
            if case == 'control_drift':
                import types
                sys.modules['maintenance_canary_claim'] = types.ModuleType('maintenance_canary_claim')
            return result
        if case == 'timeout_mismatch':
            try:
                ClaimedCanaryDispatch(plan, ledger, **values, claimed=claimed, process_binding=process_binding)
            except runner.ReplayAbort as error:
                assert 'timeout' in str(error), str(error)
            else:
                raise AssertionError('RQ one-second claim accepted a 45-second ledger reservation')
            assert not (source_root / 'job').exists()
            assert connection.lrange('rq:queue:owned-dispatch:intermediate', 0, -1) == [job.id.encode()]
            assert ledger.snapshot()['jobs']['job'] == original_job
            with open(sys.argv[1], 'x') as stream:
                json.dump({'case': case, 'launch_rejected': True, 'reservation_retained': True}, stream)
            return
        OwnedProcess.start = offline_start
        dispatch = ClaimedCanaryDispatch(plan, ledger, **values, claimed=claimed, process_binding=process_binding)
        try:
            if case == 'blocked_ledger':
                import time
                original_check = ledger.check
                blocked = []
                def stuck_check():
                    if dispatch._supervisor is None: return original_check()
                    blocked.append(time.monotonic())
                    time.sleep(4)  # No wait_for_exit/request_stop on the caller.
                    state = dispatch._supervisor.snapshot()
                    assert state['stop_reason'] == 'deadline', state
                    assert state['stop_requested'], state
                ledger.check = stuck_check
                try:
                    dispatch.start()
                except runner.ReplayAbort as error:
                    assert 'supervision stopped' in str(error), str(error)
                else:
                    raise AssertionError('Expired reservation admitted after blocked ledger call')
                finally:
                    ledger.check = original_check
                controller = dispatch.process_owner
                state = dispatch.wait_for_exit(15)
                assert len(blocked) == 1 and state['supervision_complete']
                assert state['stop_reason'] == 'deadline' and state['process_group_absence_verified']
                assert not (source_root / 'job/maintenance-admission.json').exists()
                assert not (source_root / 'job/child-started.json').exists()
                assert connection.hgetall('rq:job:' + job.id) == values['registered_hashes'][job.id]
                assert connection.lrange('rq:queue:owned-dispatch:intermediate', 0, -1) == [job.id.encode()]
                assert connection.dump('rq:queue:ordinary') == ordinary
                assert ledger.snapshot()['jobs']['job'] == original_job
                with open(sys.argv[1], 'x') as stream:
                    json.dump({'case': case, 'independent_deadline': True, 'admission_denied': True,
                               'reservation_retained': True, 'campaign_settled': False}, stream)
                return
            if case in ('delivery_failure', 'control_drift'):
                try:
                    try:
                        dispatch.start()
                    except (OSError, runner.ReplayAbort) as error:
                        assert ('Offline parent fails' if case == 'delivery_failure' else 'controller source or module drift') in str(error), str(error)
                    else:
                        raise AssertionError('Failed launch or changed controls admitted')
                finally:
                    controller = dispatch.process_owner
                lifecycle = dispatch.wait_for_exit(15)
                assert lifecycle['process_exited'] and lifecycle['returncode'] != 0
                output = source_root / 'job'
                for name in ('maintenance-admission.json', 'child-started.json', 'outcome.json'):
                    assert not (output / name).exists(), name
                try:
                    dispatch.start()
                except runner.ReplayAbort as error:
                    assert 'relaunch' in str(error)
                else:
                    raise AssertionError('Failed launch attempt was repeated')
                assert connection.hgetall('rq:job:' + job.id) == values['registered_hashes'][job.id]
                assert connection.lrange('rq:queue:owned-dispatch:intermediate', 0, -1) == [job.id.encode()]
                assert connection.dump('rq:queue:ordinary') == ordinary
                assert ledger.snapshot()['jobs']['job'] == original_job
                with open(sys.argv[1], 'x') as stream:
                    json.dump({'case': case, 'admission_denied': True, 'no_relaunch': True,
                        'reservation_retained': True, 'campaign_settled': False}, stream)
                return
            dispatch.start()
            controller = dispatch.process_owner
            output = source_root / 'job'
            if case == 'replay':
                try:
                    dispatch.start()
                except runner.ReplayAbort as error:
                    assert 'relaunch' in str(error)
                else:
                    raise AssertionError('Dispatcher launched twice')
            if case == 'warm_stop':
                from test_quality_campaign_warm_stop import wait_path
                wait_path(output / 'stop-ready.json', controller.process, seconds=15)
                dispatch.request_stop()
                dispatch.request_stop()
            assert dispatch.wait_for_exit(30)['returncode'] == (2 if case in ('warm_stop', 'deadline_stop', 'graph_blocked') else 0)
            assert not (output / 'offline-fixture-error.txt').exists()
            assert not (source_root / (ledger.path.name + '.job.watchdog-started.json')).exists()
            admission = json.loads((output / 'maintenance-admission.json').read_text())
            lifecycle = controller.snapshot()
            assert lifecycle['owned_session'] is True
            assert lifecycle['process_group_absence_verified'] is True
            assert dispatch.wait_for_exit(0)['supervision_complete'] is True
            assert admission['child_pid'] == lifecycle['pid'] and admission['parent_pid'] == os.getpid()
            assert admission['started_journal_sha256'] == lifecycle['started_journal_sha256']
            cleanup = json.loads((output / 'child-cleanup.json').read_text())
            intent = json.loads((output / 'dispatch-intent.json').read_text())
            assert cleanup['runtime_code_identity'] == intent['runtime_code_identity'] == {
                'commit': revision, 'dirty': bool(subprocess.check_output([
                    'git', '-C', str(Path(__file__).resolve().parents[1]), '-c', 'core.fsmonitor=false',
                    'status', '--porcelain=v1', '--untracked-files=normal'], env={'PATH': '/usr/bin:/bin'})),
                'code_sha256': original_job['actual_hashes']['code_sha256']}
            assert cleanup['owned_process_scope'] == {'policy': 'deny-python-process-creation-v1',
                'denied': 0, 'pid': lifecycle['pid'], 'pgid': lifecycle['pid'], 'sid': lifecycle['pid']}
            assert cleanup['application_cleanup_verified'] is True, {
                'cleanup': cleanup,
                'cleanup_error': json.loads((output / 'cleanup-error.json').read_text())
                    if (output / 'cleanup-error.json').exists() else None,
                'pending_http_reached': (output / 'stop-ready.json').exists()}
            if case in ('rq_lost_ack', 'rq_cancelled_ack', 'budget_lost_ack', 'ack_receipt_drift',
                        'scope_missing', 'scope_boolean', 'identity_missing', 'identity_boolean', 'identity_hash'):
                from redis.exceptions import ConnectionError
                original_pipeline, original_finish, original_json = connection.pipeline, ledger.finish_job, runner.exclusive_json
                finishes = []
                def finish(*args, **kwargs):
                    finishes.append(kwargs)
                    value = original_finish(*args, **kwargs)
                    if case == 'budget_lost_ack': raise OSError('Lost acknowledgement after actual budget commit')
                    return value
                def pipeline(*args, **kwargs):
                    pipe = original_pipeline(*args, **kwargs)
                    parse = pipe.parse_response
                    def lost(conn, command, **options):
                        value = parse(conn, command, **options)
                        if command == '_' and isinstance(value, list):
                            if case == 'rq_cancelled_ack': raise KeyboardInterrupt('Lost EXEC acknowledgement')
                            raise ConnectionError('Lost EXEC acknowledgement')
                        return value
                    pipe.parse_response = lost
                    return pipe
                def changed_ack(path, value):
                    digest = original_json(path, value)
                    if path.name == 'rq-settlement-ack.json': path.write_bytes(b'changed-ack')
                    return digest
                if case.startswith('rq_'): connection.pipeline = pipeline
                ledger.finish_job = finish
                if case == 'ack_receipt_drift': runner.exclusive_json = changed_ack
                invalid_receipt = case.startswith(('scope_', 'identity_'))
                if invalid_receipt:
                    path = output / 'child-cleanup.json'
                    cleanup = json.loads(path.read_text())
                    if case == 'scope_missing': del cleanup['owned_process_scope']
                    elif case == 'scope_boolean': cleanup['owned_process_scope']['denied'] = False
                    elif case == 'identity_missing': del cleanup['runtime_code_identity']
                    elif case == 'identity_boolean': cleanup['runtime_code_identity']['dirty'] = 1
                    else: cleanup['runtime_code_identity']['code_sha256'] = 'f' * 64
                    path.write_bytes(runner.encoded(cleanup))
                try:
                    if invalid_receipt:
                        try: dispatch.settle(connection)
                        except ValueError as error:
                            assert ('process_scope' if case.startswith('scope_') else 'runtime_code_identity') in str(error), str(error)
                        else: raise AssertionError('Unqualified process scope or code identity reached settlement')
                        assert connection.hgetall('rq:job:' + job.id) == values['registered_hashes'][job.id]
                    else:
                        result = dispatch.settle(connection)
                        assert result['outcome'] == 'uncertain' and result['budget_job_settled'] is False, result
                        assert result['stop_required'] is True and result['campaign_settled'] is False
                        assert connection.hget('rq:job:' + job.id, 'status') == b'finished'
                    state = ledger.snapshot()
                    if case == 'budget_lost_ack':
                        assert len(finishes) == 1 and state['jobs']['job']['status'] == 'completed'
                    else:
                        assert finishes == [] and state['jobs']['job'] == original_job, (finishes, state['jobs']['job'])
                    try: dispatch.settle(connection)
                    except runner.ReplayAbort as error: assert 'replay' in str(error)
                    else: raise AssertionError('Uncertain settlement repeated')
                    assert state['spent']['jobs'] == 2 and connection.dump('rq:queue:ordinary') == ordinary
                    with open(sys.argv[1], 'x') as stream:
                        json.dump({'case': case, 'one_shot_settlement': True,
                                   'budget_finish_calls': len(finishes), 'no_refund': True}, stream)
                finally:
                    connection.pipeline, ledger.finish_job, runner.exclusive_json = original_pipeline, original_finish, original_json
                return
            if case == 'expired_cleanup':
                ledger.clock = lambda: original_job['deadline_ms'] / 1000 + 1
            if case.startswith('downgrade'):
                ticket_path = output / 'child-ticket.json'
                ticket = json.loads(ticket_path.read_text())
                del ticket['maintenance_admission']
                ticket_path.write_bytes(runner.encoded(ticket))
                digest = runner.sha(ticket_path.read_bytes())
                for name in ('child-started.json', 'child-cleanup.json'):
                    path = output / name
                    row = json.loads(path.read_text())
                    del row['maintenance_admission_sha256']
                    row['ticket_sha256'] = digest
                    path.write_bytes(runner.encoded(row))
            if case == 'downgrade_helper':
                from maintenance_canary_settlement import settle_claimed_analysis
                result = settle_claimed_analysis(connection, **values, claimed=claimed,
                    process=controller, process_binding=process_binding, output_dir=output)
                assert result['outcome'] == 'rejected', result
                assert result['reason'] == 'owned_completion_or_queue_unconfirmed', result
            elif case == 'downgrade_dispatch':
                try:
                    dispatch.settle(connection)
                except runner.ReplayAbort as error:
                    assert 'admission' in str(error), str(error)
                    result = {'outcome': 'rejected', 'campaign_settled': False, 'handover_verified': False}
                else:
                    raise AssertionError('Original dispatcher accepted a downgraded ticket')
            else:
                result = dispatch.settle(connection)
                assert result['outcome'] == 'settled', result
                assert result['terminal_status'] == ('failed' if case in ('warm_stop', 'deadline_stop', 'graph_blocked') else 'finished'), result
                if case == 'replay':
                    stored = connection.dump('rq:job:' + job.id)
                    try:
                        dispatch.settle(connection)
                    except runner.ReplayAbort as error:
                        assert 'replay' in str(error)
                    else:
                        raise AssertionError('Dispatcher settled twice')
                    assert connection.dump('rq:job:' + job.id) == stored
            if case.startswith('downgrade'):
                assert connection.hgetall('rq:job:' + job.id) == values['registered_hashes'][job.id]
                assert connection.lrange('rq:queue:owned-dispatch:intermediate', 0, -1) == [job.id.encode()]
                assert not connection.exists('stock-agent:maintenance:canary-settlement:owned-dispatch:' + job.id)
            else:
                assert connection.hget('rq:job:' + job.id, 'status') == (b'failed' if case in ('warm_stop', 'deadline_stop', 'graph_blocked') else b'finished')
                assert connection.llen('rq:queue:owned-dispatch:intermediate') == 0
            assert connection.dump('rq:queue:ordinary') == ordinary
            final_job = ledger.snapshot()['jobs']['job']
            if case.startswith('downgrade'):
                assert final_job == original_job
            else:
                expected = 'cancelled' if case == 'warm_stop' else 'failed' if case in ('deadline_stop', 'graph_blocked') else 'completed'
                assert final_job['status'] == expected, final_job
                assert result['budget_job_settled'] is True
                assert final_job['settlement_evidence_sha256'] == result['budget_evidence_sha256']
                assert {k: v for k, v in final_job.items() if k not in ('status', 'settlement_evidence_sha256')} == {
                    k: v for k, v in original_job.items() if k != 'status'}
                assert ledger.snapshot()['spent']['jobs'] == 2
                assert ledger.snapshot()['stages']['S2'] == 'open'
                if case in ('expired_cleanup', 'deadline_stop'):
                    assert ledger.snapshot()['blocked'] == 'deadline exceeded'
                    assert result['stop_required'] is True
            assert result['campaign_settled'] is result['handover_verified'] is False
            with open(sys.argv[1], 'x') as stream:
                json.dump({'mode': mode, 'case': case, 'outcome': result['outcome'], 'watchdog_fixture_removed': True,
                    'original_parent_admission': True, 'ordinary_unchanged': True,
                    'campaign_settled': False, 'live_qualified': False}, stream)
        finally:
            OwnedProcess.start = original_start
    finally:
        if controller is not None:
            if controller.process is not None: controller.process.wait(timeout=30)
            controller.close()
        connection.close()


if __name__ == '__main__': main()
