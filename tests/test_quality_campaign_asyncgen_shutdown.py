"""Real owned CLI with synthetic completion prerequisites, no source/model proof."""
import pytest

from test_quality_campaign_safety import layout, fresh_guarded_child


@pytest.mark.parametrize('close_nested', [False, True])
def test_generator_created_during_shutdown_must_be_closed_before_success(tmp_path, close_nested):
    ledger, output = layout(tmp_path)
    fresh_guarded_child(ledger, output, 'import canary_release_policy\ncanary_release_policy.require_canary_enabled = lambda: None\nclose_nested = ' + repr(close_nested) + '\n' + '''
import asyncio, threading
import quality_campaign_runner as runner
def no_env(event, args):
    if event == 'open' and not isinstance(args[0], int) and Path(os.fsdecode(args[0])).name == '.env':
        raise AssertionError('Operator environment must not be read')
sys.addaudithook(no_env)
import FinMind.utility.request
ticket = output / 'child-ticket.json'
outcome_path = output / 'outcome.json'
runner.exclusive_json(ticket, {'fixture': 'original private ticket'})
runner.exclusive_json(outcome_path, {'status': 'published', 'sdk_cleanup_verified': True})
sys.modules['llm_transport'] = SimpleNamespace(_client_lock=threading.Lock(), _client_cache={})
retained, closed, errors = [], [], []
async def nested():
    try:
        yield 'nested'
    finally:
        closed.append('nested')
async def outer():
    try:
        yield 'outer'
    finally:
        retained.append(nested())
        assert await anext(retained[-1]) == 'nested'
        if close_nested:
            await retained[-1].aclose()
        closed.append('outer')
async def work(path, *, stop_requested, completion):
    asyncio.get_running_loop().set_exception_handler(lambda loop, context: errors.append(context))
    retained.append(outer())
    assert await anext(retained[0]) == 'outer'
    completion.update(output=output, ticket_path=ticket,
        transport=SimpleNamespace(_restore=None), observation={
            'ticket_sha256': runner.sha(ticket.read_bytes()),
            'outcome_sha256': runner.sha(outcome_path.read_bytes()),
            'sdk_cleanup_verified': True})
    return 0
runner.owned_job = work
code = runner.run_owned_job(ticket)
cleanup = json.loads((output / 'child-cleanup.json').read_text())
assert closed == (['nested', 'outer'] if close_nested else ['outer'])
assert (retained[-1].ag_frame is None) is close_nested
assert not errors and cleanup['shutdown_async_error_count'] == 0
assert code == (0 if close_nested else 2), cleanup
assert cleanup['application_cleanup_verified'] is close_nested, cleanup
assert cleanup['pending_async_generators'] == int(not close_nested)
''')
