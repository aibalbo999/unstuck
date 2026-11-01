"""Offline leaf fixtures around the actual owned runner and normal report job.

Invoked only by the test's real watchdog; no application startup/test-hook flag
is added to production. Network is denied before any application import. Model
responses, source review, billing review and legacy contexts are NOT real proof.
"""
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import signal
import socket
import sys
from types import SimpleNamespace
import traceback


def main():
    ticket, case = Path(sys.argv[1]), sys.argv[2]
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline owned normal test forbids external network')
    socket.socket.connect = socket.socket.connect_ex = forbidden
    # The real boundary still installs; its explicit DNS step sees only inert
    # fixture addresses. Neither Redis nor provider sockets may actually connect.
    socket.getaddrinfo = lambda host, port, *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', port))]
    def no_env(event, args):
        if event == 'open' and not isinstance(args[0], int) and Path(os.fsdecode(args[0])).name == '.env':
            raise AssertionError('Operator .env must not be read')
    sys.addaudithook(no_env)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    import canary_release_policy
    # Only this network-denied fixture simulates the dormant implementation.
    canary_release_policy.require_canary_enabled = lambda: None
    import quality_campaign_runner as runner
    import quality_campaign_graph as graph
    real_normal = graph.run_normal_job
    retained_generators = []  # Keep the shutdown fixture alive until Runner.close.
    async def offline_leaves(**kwargs):
        # owned_job has already installed its real environment/SQLite/write/
        # PostgreSQL/socket boundaries. Keep its normal-job adapter unchanged.
        import analysis_jobs, workflow_services, workflow_graph, llm_client, llm_transport, httpx
        from agent_runtime import AnalysisResult, routing
        from google.genai import types
        from quality_campaign_safety import Evidence
        model, key = 'gemini-3.6-flash', 'dummy-test-key'
        routing.get_agent_model_sequence = lambda agent: [model]
        routing.get_audit_model_sequence = lambda: [model]
        pings, calls = [], []
        limiter = SimpleNamespace(_client=SimpleNamespace(ping=lambda: pings.append(True) or True))
        llm_client.KeyRotator = lambda keys: SimpleNamespace(_shared_limiter=limiter)
        def reply(request):
            calls.append(True)
            return httpx.Response(200, json={'modelVersion': 'offline-test-model', 'candidates': [
                {'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [{'text': 'Offline public response'}]}}],
                'usageMetadata': {'promptTokenCount': 3, 'candidatesTokenCount': 2, 'totalTokenCount': 5}})
        async def stopped_reply(request):
            if calls:
                return reply(request)
            calls.append(True)
            Evidence(kwargs['output']).save('stop-ready.json', {'offline_http_pending': True})
            # Only a test failsafe, not a production timeout or stop mechanism.
            await asyncio.sleep(12)
            raise AssertionError('Parent did not stop the offline pending request')
        warm_stop = case.startswith('warm_stop')
        mock = httpx.MockTransport(stopped_reply if warm_stop else reply)
        llm_transport._genai_http_options = lambda: types.HttpOptions(
            client_args={'transport': mock}, async_client_args={'transport': mock})
        def no_fresh(*args, **kw):
            raise AssertionError('Frozen normal job attempted fresh data, memory or retry renewal')
        analysis_jobs.STOCK_DATA_SERVICE = SimpleNamespace(fetch_async=no_fresh)
        analysis_jobs.build_temporal_memory = analysis_jobs.prepare_analysis_retry = no_fresh
        from reporting import ReportRenderer
        class FixtureRenderer:
            async def render_async(self, request):
                return await ReportRenderer().render_async(replace(request, generated_at='2026-09-12T07:30:00+00:00'))
        analysis_jobs.REPORT_RENDERER = FixtureRenderer()
        if case == 'blocked':
            factory = workflow_services.create_default_workflow_services
            first = {'v1': 1, 'v2': 11, 'v3': 17, 'v4': 22}[kwargs['mode']]
            async def agent(number, state):
                if number == first:
                    await llm_transport.generate_content_async(key, model, 'Offline owned normal graph',
                        types.GenerateContentConfig(max_output_tokens=64))
                return {'analyses': {str(number): 'Offline diagnostic, not qualified'}}
            async def audit(state):
                return {'status': 'blocked', 'blocking_issues': ['offline_not_qualified']}
            def services(**options):
                return replace(factory(**options), run_agent=agent, final_audit=audit)
            workflow_services.create_default_workflow_services = workflow_graph.create_default_workflow_services = services
        else:
            # Explicit synthetic legacy upstream, real renderer/gates/storage.
            async def legacy(request):
                if case == 'published_executor':
                    await asyncio.to_thread(lambda: None)
                if warm_stop:
                    await llm_transport.generate_content_async(key, model, 'Offline stop fixture',
                        types.GenerateContentConfig(max_output_tokens=64))
                context = {'ticker': request.data['ticker'], 'data': request.data,
                    'pipeline_id': request.pipeline_id, 'analyses': {}, 'final_audit': {'status': 'passed'}}
                if request.pipeline_id == 'v4':
                    context['analyses'][24] = '## 極短線交易計畫\n本測試不建立部位；待補齊來源後重新評估。'
                    context['parsed'] = {'trade_setup': {'trade_direction': 'Neutral', 'entry_zone': 'N/A',
                        'target_price': 'N/A', 'stop_loss': 'N/A', 'risk_level': 'High',
                        'core_catalyst': '本測試不建立部位；待補齊來源後重新評估。'}}
                return AnalysisResult(context=context, pipeline_id=request.pipeline_id)
            analysis_jobs.PIPELINE_RUNNER = SimpleNamespace(run_async=legacy)
        if warm_stop:
            close_clients = llm_transport.close_cached_clients_async
            async def observed_close():
                # A repeated external TERM must not interrupt the first cleanup.
                if case == 'warm_stop_duplicate':
                    os.kill(os.getpid(), signal.SIGTERM)
                await asyncio.sleep(.02)
                await close_clients()
                Evidence(kwargs['output']).save('stop-sdk-cleaned.json', {'real_close_returned': True})
                if case == 'warm_stop_close_error':
                    raise RuntimeError('Offline close failure after real resource cleanup')
            llm_transport.close_cached_clients_async = observed_close
        outcome = await real_normal(**kwargs)
        if case in ('warm_stop_pending_task', 'warm_stop_pending_send', 'warm_stop_pending_error', 'warm_stop_pending_generator'):
            async def pending():
                try:
                    await asyncio.sleep(5)
                finally:
                    await asyncio.sleep(.02)
                    if case == 'warm_stop_pending_send':
                        from quality_campaign_wire import ReplayAbort
                        try:
                            await llm_transport.generate_content_async(key, model, 'Forbidden cleanup generation',
                                types.GenerateContentConfig(max_output_tokens=64))
                        except ReplayAbort:
                            Evidence(kwargs['output']).save('stop-new-send-denied.json', {'denied_before_http': True})
                    Evidence(kwargs['output']).save('stop-pending-cleaned.json', {
                        'task_finally_returned': True, 'http_calls_total': len(calls)})
                    if case == 'warm_stop_pending_error':
                        raise RuntimeError('Offline pending-task cleanup failed')
                    if case == 'warm_stop_pending_generator':
                        async def generator():
                            try:
                                yield 'offline'
                            finally:
                                Evidence(kwargs['output']).save('stop-generator-cleaned.json', {'finally_entered': True})
                                raise RuntimeError('Offline shutdown generator cleanup failed')
                        retained_generators.append(generator())
                        assert await anext(retained_generators[-1]) == 'offline'
            asyncio.create_task(pending())
            await asyncio.sleep(0)  # Enter finally scope before Runner shutdown.
        proof = {'case': case, 'mode': kwargs['mode'], 'normal_entry_called': True,
            'normal_module': str(Path(real_normal.__code__.co_filename).resolve()),
            'mock_http_calls': len(calls), 'shared_quota_fixture_pings': len(pings),
            'sdk_clients_closed': not llm_transport._client_cache,
            'transport_restored': kwargs['transport']._restore is None,
            'task_cancel_requests': asyncio.current_task().cancelling(),
            'qualified_for_campaign': False, 'network_connections_allowed': False}
        Evidence(kwargs['output'], kwargs['secrets']).save('owned-normal-test-proof.json', proof)
        return outcome
    graph.run_normal_job = offline_leaves
    try:
        options = {'admission_fd': int(sys.argv[3])} if len(sys.argv) > 3 else {}
        return runner.run_owned_job(ticket, **options)
    except BaseException:
        # All inputs here are dummy fixtures, never an operator credential file.
        ticket.with_name('offline-fixture-error.txt').write_text(traceback.format_exc())
        return 2


if __name__ == '__main__': raise SystemExit(main())
