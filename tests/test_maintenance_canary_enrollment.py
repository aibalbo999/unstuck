"""Create-only enrollment through real RQ serialization and a private Redis."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('case', ['existing_job', 'replay', 'valid', 'queue', 'intermediate',
    'dependency', 'dependent', 'result', 'first_seen', 'registered_empty', 'failed_registry',
    'worker_registry', 'scheduler', 'cleaner', 'marker_only', 'wrong_registry_type',
    'race', 'lost_reply', 'cancel_after_exec', 'cancel_before_exec', 'cancel_after_readback', 'runtime_error',
    'readback_mismatch', 'caller_mutation', 'retry_nonzero'])
def test_real_private_canary_enrollment_preserves_existing_state(case, request):
    from test_maintenance_rq_private_integration import private_redis
    def record(label, value):
        request.node.user_properties.append((label, json.dumps(value, sort_keys=True)))
    with private_redis(record) as (root, sock):
        output = root / 'enrollment-evidence.json'
        process = subprocess.Popen([sys.executable, '-I', '-B',
            str(Path(__file__).with_name('test_maintenance_canary_enrollment_child.py')), str(output), case],
            env={'PATH': '/usr/bin:/bin', 'TMPDIR': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
                'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(sock)},
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, (stdout + stderr).decode(errors='replace')[-5000:]
            record('real_private_canary_enrollment', json.loads(output.read_text()))
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)


@pytest.mark.parametrize('change', ['subset', 'duplicate', 'empty', 'too_many', 'callback', 'mixed_campaign', 'bad_queue'])
def test_invalid_enrollment_is_rejected_before_any_redis_access(change, monkeypatch):
    import copy
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    from maintenance_canary_enrollment import enroll_analysis_jobs
    from test_maintenance_canary_claim import analysis_enrollment
    values = analysis_enrollment()
    if change == 'subset':
        values['registered_hashes']['analysis:two'] = dict(values['registered_hashes']['analysis:one'])
        values['analysis_bindings']['analysis:two'] = dict(values['analysis_bindings']['analysis:one'], job_id='two')
        # Build a semantically valid second payload: the sole defect is a subset roster.
        from maintenance_canary_claim import prepare_analysis_job
        job = prepare_analysis_job(object(), queue_name=values['queue_name'], binding=values['analysis_bindings']['analysis:two'])
        job.enqueued_at, job._status = job.created_at, 'queued'
        values['registered_hashes'][job.id] = {
            key.encode(): value if type(value) is bytes else value.encode() if isinstance(value, str) else str(value).encode()
            for key, value in job.to_dict().items()}
    elif change == 'duplicate': values['remaining'] = ['analysis:one'] * 2
    elif change == 'empty': values['registered_hashes'] = {}
    elif change == 'too_many':
        for index in range(5): values['registered_hashes'][f'analysis:extra-{index}'] = {b'data': b'not-loaded'}
    elif change == 'callback': values['registered_hashes']['analysis:one'][b'failure_callback_name'] = b'os.system'
    elif change == 'mixed_campaign': values['analysis_bindings']['analysis:one']['campaign_id'] = 'other-campaign'
    elif change == 'bad_queue': values['queue_name'] = 'rq:queue:ordinary'
    before, calls = copy.deepcopy(values), []
    class NoRedis:
        def pipeline(self, **kwargs):
            calls.append(True)
            raise AssertionError('Invalid roster reached Redis')
    result = enroll_analysis_jobs(NoRedis(), **values)
    assert result['outcome'] == 'rejected' and result['stop_required'] is True
    assert 'enrollment' not in result and not calls and before == values


@pytest.mark.parametrize('error_type', [OSError, KeyboardInterrupt, SystemExit])
def test_enrollment_early_failure_preserves_cancel_intent_and_hides_exception_text(error_type, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    from maintenance_canary_enrollment import enroll_analysis_jobs
    from test_maintenance_canary_claim import analysis_enrollment
    class Unavailable:
        def pipeline(self, **kwargs): raise error_type('private-endpoint-must-not-leak')
    result = enroll_analysis_jobs(Unavailable(), **analysis_enrollment())
    assert result['outcome'] == ('rejected' if error_type is OSError else 'cancelled')
    assert result['cancellation_requested'] is (error_type is not OSError)
    assert result['stop_required'] is True and 'enrollment' not in result
    assert 'private-endpoint' not in json.dumps(result)
