"""Private graph/SDK/artifact integration, not a live launcher or qualifier.

The caller owns the clean environment, exact filesystem/socket boundary, frozen
input qualification, active ledger job and outer process/cleanup watchdog.
Nothing at import reads credentials, installs patches, contacts services or
opens a database. No stage/job completion or formal publication is performed.
"""
import asyncio
import copy
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import replace
import functools
import hashlib
import inspect
import json
from pathlib import Path
import re
import sys
import time
import math
import canary_release_policy


def publication_quality_receipt(snapshot, mode):
    """Local diagnostic metadata only; never resurrect removed quality claims."""
    return {'pipeline_id':mode,'snapshot_sha256':hashlib.sha256(json.dumps(snapshot,
        sort_keys=True,ensure_ascii=True,allow_nan=False).encode()).hexdigest(),
        'qualified_for_campaign':False,'formal_publication':False,
        'quality_assessment':'not_qualified_by_diagnostic_receipt'}


def diagnostic_event_projection(jobs, events, *, cutoff, scope=None):
    """Pure private-cohort counts, never current DB metrics or qualified rates."""
    if isinstance(cutoff,bool) or not isinstance(cutoff,(int,float)) or not math.isfinite(cutoff):
        raise ValueError('finite diagnostic cutoff required')
    from llm_daily_usage import LOCAL_BLOCK_KINDS
    selected={r['job_id']:r for r in jobs if isinstance(r,dict) and isinstance(r.get('job_id'),str)}
    counts={k:0 for k in ('provider_request_events','provider_quota_error_events',
        'local_block_events','other_error_events','quality_rejection_events','publication_events')}
    seen=set();phases={};malformed=duplicates=future=outside=0
    for row in events:
        if not isinstance(row,dict) or row.get('job_id') not in selected:
            outside+=1;continue
        event_id=row.get('id');at=row.get('created_at');payload=row.get('payload')
        if (type(event_id)is not int or isinstance(at,bool) or not isinstance(at,(int,float))
                or not math.isfinite(at) or not isinstance(payload,dict)):
            malformed+=1;continue
        if at>cutoff:future+=1;continue
        identity=(row['job_id'],event_id)
        if identity in seen:duplicates+=1;continue
        seen.add(identity)
        phase=payload.get('phase')
        phase=phase if isinstance(phase,str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}',phase) else 'unrecorded'
        phases[phase]=phases.get(phase,0)+1
        meta=payload.get('metadata') if isinstance(payload.get('metadata'),dict) else {}
        status=meta.get('provider_status_code',payload.get('provider_status_code'))
        error_type=meta.get('error_kind',meta.get('error_type',payload.get('error_kind',payload.get('error_type'))))
        category=meta.get('error_category',payload.get('error_category'))
        if phase=='llm_provider_request':counts['provider_request_events']+=1
        if phase in ('report_quality_blocked','quality_rejected'):counts['quality_rejection_events']+=1
        if payload.get('type')=='report_done':counts['publication_events']+=1
        if error_type in LOCAL_BLOCK_KINDS or (isinstance(category,str) and category.startswith('local_')) or phase in ('llm_local_block','local_circuit_block'):
            counts['local_block_events']+=1
        elif type(status)is int and status==429:counts['provider_quota_error_events']+=1
        elif phase not in ('report_quality_blocked','quality_rejected') and (payload.get('type')=='error' or phase=='llm_model_error'):
            counts['other_error_events']+=1
    job_states={}
    for row in selected.values():
        state=row.get('status') if row.get('status')in('queued','running','waiting_retry','done','error','cancelled')else 'unknown'
        job_states[state]=job_states.get(state,0)+1
    boundary=dict(scope or {})
    boundary.update(jobs_selected=len(selected),events_selected=len(seen),events_malformed=malformed,
        duplicate_events_excluded=duplicates,future_events_excluded=future,outside_cohort_excluded=outside)
    return {'schema_version':'private_campaign_diagnostic.v1','observed_at':cutoff,
        'status':'partial' if malformed or boundary.get('truncated') else 'diagnostic_available',
        'scope':boundary,'event_counts':counts,'event_counts_by_phase':phases,'job_status_counts':job_states,
        'qualified_for_campaign':False,'formal_publication':False,'qualified_success_rate':None,
        'limitations':['Retained request/error events are not physical HTTP delivery or report-failure counts.',
                       'Local blocks, quota errors, other errors and quality rejections remain separate.',
                       'No current database, account, provider or production runtime is read by this projection.']}


def frozen_services(services):
    async def prepare(state):
        return {'rag_status': {'status': 'unavailable', 'reason': 'frozen_replay_no_original_rag_index',
                               'exact_original_prompt_replay': False}}
    async def repair(state):
        return {'tool_results': {'official_reconciliation': {'status': 'unavailable',
            'reason': 'frozen_replay_external_refresh_forbidden'}}}
    return replace(services, prepare=prepare, repair=repair)


async def execute_graph(initial, services, mode, output, job_id, timeout, *, evidence=None):
    from workflow_graph import build_analysis_graph_builder
    from workflow_checkpoints import open_sqlite_checkpointer
    from workflow_quality_drafts import checkpoint_draft_scope
    config = {'configurable': {'thread_id': job_id, 'checkpoint_ns': ''}, 'recursion_limit': 200}
    async with open_sqlite_checkpointer(Path(output) / 'checkpoint.sqlite3') as saver:
        graph = build_analysis_graph_builder(mode, services).compile(checkpointer=saver)
        primary = None
        try:
            with checkpoint_draft_scope(saver, job_id):
                return dict(await asyncio.wait_for(graph.ainvoke(initial, config=config), timeout))
        except BaseException as error:
            primary = error
            raise
        finally:
            if evidence is not None:
                try:
                    snapshot = await graph.aget_state(config)
                    evidence.save('checkpoint-state.json', {'values': dict(snapshot.values), 'next': list(snapshot.next)})
                except BaseException as error:
                    try:
                        evidence.save('checkpoint-capture-error.json', {'error_type': type(error).__name__,
                            'original_error_type': type(primary).__name__ if primary is not None else None})
                    except BaseException:
                        pass  # A secondary evidence failure must not replace the actual graph stop.
                    if primary is None:
                        raise


def project_outcome(job_id, mode, started, cutoff, status, events, *, filename=None):
    mapped = {'published': 'done', 'blocked': 'error', 'error': 'error', 'partial': 'cancelled'}
    job = {'job_id': job_id, 'pipeline_id': mode, 'created_at': started, 'finished_at': cutoff,
           'status': mapped.get(status, 'error'), 'filename': filename if status == 'published' else None}
    metrics = diagnostic_event_projection([job], events, cutoff=cutoff,
        scope={'basis': 'one_private_campaign_graph_job', 'population_estimate': False,
               'truncated': status == 'partial', 'events_truncated': status == 'partial',
               'transport_detail_basis': 'separate_transport_and_physical_http_evidence', 'interrupted': status == 'partial'})
    return job, metrics


class _PublicCalls:
    def __init__(self, transport, evidence):
        self.transport, self.evidence = transport, evidence
        self.active = ContextVar('campaign_public_call', default=None)
        self.agent = ContextVar('campaign_agent', default=None)
        self.rows = []
        self.cleanup_verified = False

    def _start(self, args, options):
        current = self.transport.active.get()
        from quality_campaign_safety import ReplayAbort
        if current is None:
            raise ReplayAbort('Public response capture requires a reserved transport')
        row = {'attempt_id': current['id'], 'model': current['model'], 'agent_num': self.agent.get(),
               'started_at': time.time(), 'status': 'started', 'completed_response': False}
        self.rows.append(row)
        self.evidence.append('calls.jsonl', dict(row))
        prompt = args[2] if len(args) > 2 else options.get('prompt')
        config = args[3] if len(args) > 3 else options.get('config')
        if hasattr(config, 'model_dump'): config = config.model_dump(exclude_none=True)
        self.evidence.append('prompts.jsonl', {'attempt_id': row['attempt_id'], 'prompt': prompt, 'config': config})
        return row

    def _finish(self, row, response, error):
        from llm_response_diagnostics import response_diagnostics
        from llm_transport import response_text
        row.update(finished_at=time.time(), completed_response=response is not None,
            status='completed' if response is not None else 'error' if isinstance(error, Exception) else 'interrupted',
            error_type=type(error).__name__ if error is not None else None,
            diagnostics=response_diagnostics(response, error=error))
        if response is not None:
            self.evidence.append('raw.jsonl', {'attempt_id': row['attempt_id'],
                'kind': 'completed_public_text', 'text': response_text(response)})
        self.evidence.append('calls.jsonl', dict(row))

    def _finish_preserving_stop(self, row, response, error):
        try:
            self._finish(row, response, error)
        except BaseException as capture_error:
            row['evidence_error_type'] = type(capture_error).__name__
            if error is None:
                raise

    def wrap_sync(self, original):
        @functools.wraps(original)
        def run(*args, **options):
            if self.active.get() is not None: return original(*args, **options)
            row = self._start(args, options)
            token = self.active.set(row['attempt_id'])
            response = error = None
            try:
                response = original(*args, **options)
                return response
            except BaseException as exc:
                error = exc
                raise
            finally:
                self.active.reset(token)
                self._finish_preserving_stop(row, response, error)
        return run

    def wrap_async(self, original, *, stream=False):
        @functools.wraps(original)
        async def run(*args, **options):
            if self.active.get() is not None: return await original(*args, **options)
            row = self._start(args, options)
            token = self.active.set(row['attempt_id'])
            response = error = None
            if stream:
                callback = options.get('on_delta')
                async def delta(text):
                    self.transport.check_stream()
                    self.evidence.append('raw.jsonl', {'attempt_id': row['attempt_id'], 'kind': 'public_delta', 'text': text})
                    if callback:
                        result = callback(text)
                        if inspect.isawaitable(result): await result
                options['on_delta'] = delta
            try:
                response = await original(*args, **options)
                return response
            except BaseException as exc:
                error = exc
                raise
            finally:
                self.active.reset(token)
                self._finish_preserving_stop(row, response, error)
        return run


class _WireEvidence:
    def __init__(self, journal, evidence):
        self.journal, self.evidence = journal, evidence
    def record(self, row): return self.journal.record(row)
    def append(self, name, value):
        # Capture public wire evidence before an accounting stop can interrupt
        # this callback. The original journal still owns every usage settlement.
        capture_error = None
        try:
            self.evidence.append(name, value)
        except BaseException as error:
            capture_error = error
        try:
            result = self.journal.append(name, value)
        except BaseException:
            if capture_error is not None:
                raise capture_error from None
            raise
        if capture_error is not None:
            raise capture_error
        return result


@asynccontextmanager
async def sdk_context(transport, evidence, strict, check_frozen):
    """Install reversible SDK/call capture only; transport owns HTTP hooks."""
    import llm_transport
    from google.genai import types, _api_client
    from quality_campaign_safety import ReplayAbort
    if llm_transport._client_cache:
        raise ReplayAbort('Fresh SDK client cache required; existing clients are not adopted or closed')
    patches, recorder, primary = [], _PublicCalls(transport, evidence), None
    def patch(owner, name, value):
        previous = getattr(owner, name)
        setattr(owner, name, value)
        patches.append((owner, name, previous, value))
    original_options, original_send = llm_transport._genai_http_options, transport.before_send
    original_stream_check = transport.check_stream
    def options():
        current = original_options() or types.HttpOptions()
        return current.model_copy(update={'retry_options': types.HttpRetryOptions(attempts=1),
            'client_args': {**(current.client_args or {}), 'follow_redirects': False, 'trust_env': False},
            'async_client_args': {**(current.async_client_args or {}), 'follow_redirects': False, 'trust_env': False}})
    def checked_send(row):
        strict.assert_available()
        if check_frozen() != transport.actual_hashes:
            raise ReplayAbort('Frozen code/source/route hashes changed before physical send')
        original_send(row)  # Preserve transport's own verifier and ledger check.
        strict.assert_available()
    def no_embed(*args, **kwargs):
        raise ReplayAbort('Frozen campaign has no original RAG; embeddings are forbidden')
    def checked_stream():
        strict.assert_available()
        original_stream_check()
        strict.assert_available()
    try:
        patch(_api_client.BaseApiClient, '_use_aiohttp', lambda self: False)
        patch(llm_transport, '_genai_http_options', options)
        patch(llm_transport, 'generate_content', transport.wrap_sync(recorder.wrap_sync(llm_transport.generate_content)))
        patch(llm_transport, 'generate_content_async', transport.wrap_async(recorder.wrap_async(llm_transport.generate_content_async)))
        patch(llm_transport, 'generate_content_stream_async',
              transport.wrap_async(recorder.wrap_async(llm_transport.generate_content_stream_async, stream=True)))
        patch(llm_transport, 'embed_content', no_embed)
        patch(llm_transport, 'embed_content_async', no_embed)
        patch(transport, 'before_send', checked_send)
        patch(transport, 'check_stream', checked_stream)
        patch(transport, 'evidence', _WireEvidence(transport.evidence, evidence))
        patch(transport, 'secrets', tuple(dict.fromkeys((*transport.secrets, *evidence.secrets))))
        yield recorder
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup_error = None
        cleanup_cancellation = None
        close_errors = []
        def observe_close(close, *, asynchronous):
            def sync_close(*args, **kwargs):
                try:
                    return close(*args, **kwargs)
                except BaseException as error:
                    close_errors.append(type(error).__name__)
                    raise
            async def async_close(*args, **kwargs):
                try:
                    result = close(*args, **kwargs)
                    return await result if inspect.isawaitable(result) else result
                except BaseException as error:
                    close_errors.append(type(error).__name__)
                    raise
            return async_close if asynchronous else sync_close
        try:
            # The app shutdown helper suppresses individual close errors. Keep
            # its real close behavior, but observe only clients this scope made
            # so such suppression cannot be mistaken for successful cleanup.
            with llm_transport._client_lock:
                clients = list(llm_transport._client_cache.values())
            for client in clients:
                for owner, name, asynchronous in ((client, 'close', False), (getattr(client, 'aio', None), 'aclose', True)):
                    close = getattr(owner, name, None)
                    if callable(close):
                        patch(owner, name, observe_close(close, asynchronous=asynchronous))
            # A first TERM can arrive after the job timeout but during close.
            # Keep the same bounded close task alive; never retry the helper or
            # restart its ten-second deadline when the owner is cancelled.
            close_task = asyncio.create_task(asyncio.wait_for(llm_transport.close_cached_clients_async(), 10))
            while True:
                try:
                    await asyncio.shield(close_task)
                    break
                except asyncio.CancelledError as error:
                    if close_task.cancelled():
                        raise  # The close itself failed; do not label it clean.
                    cleanup_cancellation = error
            with llm_transport._client_lock:
                if llm_transport._client_cache:
                    raise ReplayAbort('Owned SDK client cache remained populated after close')
        except BaseException as error:
            cleanup_error = type(error).__name__
        if close_errors and cleanup_error is None:
            cleanup_error = close_errors[0]
        changed = []
        for owner, name, previous, installed in reversed(patches):
            if getattr(owner, name) is not installed:
                changed.append(name)
            else:
                setattr(owner, name, previous)
        if cleanup_error or changed:
            try:
                evidence.save('cleanup-error.json', {'error_type': cleanup_error, 'close_error_types': close_errors,
                    'changed_hooks': changed, 'original_error_type': type(primary).__name__ if primary is not None else None})
            except BaseException:
                pass  # Private output may already be exhausted; preserve the original hard stop.
            if primary is None:
                if cleanup_cancellation is not None:
                    raise cleanup_cancellation
                raise ReplayAbort('SDK cleanup or patch ownership failed')
        else:
            recorder.cleanup_verified = True
        if primary is None and cleanup_cancellation is not None:
            raise cleanup_cancellation


async def render_and_persist(context, mode, output, filename, check, *, secrets=()):
    from quality_campaign_safety import ReplayAbort
    from reporting.renderer import ReportRenderer
    from reporting.types import ReportRequest
    from report_persistence import persist_report_bundle
    from storage.report_storage import LocalFileStorage
    check()
    bundle = await ReportRenderer().render_async(ReportRequest(context=context, pipeline_id=mode, filename=filename))
    check()
    serialized = json.dumps({'html': bundle.html, 'markdown': bundle.markdown, 'snapshot': bundle.data_snapshot}, default=str)
    if any(secret in serialized for secret in secrets if secret) or re.search(r'AIza[\w-]{20,}', serialized):
        raise ReplayAbort('Credential-shaped report rejected; validated prose is not silently edited')
    persisted = persist_report_bundle(filename=filename, html_content=bundle.html, markdown_content=bundle.markdown,
        data_snapshot=bundle.data_snapshot, storage=LocalFileStorage(Path(output) / 'reports'), output_dir=str(Path(output) / 'reports'))
    check()
    from data_trust import sanitize_for_snapshot
    expected = {'html_key': bundle.html.encode('utf-8'), 'md_key': bundle.markdown.encode('utf-8'),
        'data_key': json.dumps(sanitize_for_snapshot(bundle.data_snapshot), ensure_ascii=False, indent=2).encode('utf-8')}
    root, artifacts = (Path(output) / 'reports').resolve(), {}
    for key, content in expected.items():
        path = root / persisted[key]
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file() or path.read_bytes() != content:
            raise ReplayAbort('Private artifact readback does not match the rendered bundle')
        artifacts[key] = {'key': persisted[key], 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
    check()
    return persisted, bundle, artifacts


@contextmanager
def _backend_scope(dev):
    from quality_campaign_safety import ReplayAbort
    backend = Path(dev).resolve() / 'backend'
    if not backend.is_dir(): raise ReplayAbort('Explicit development backend required')
    before = list(sys.path)
    sys.path.insert(0, str(backend))
    try:
        import config, llm_transport, workflow_graph, report_persistence
        for module in (config, llm_transport, workflow_graph, report_persistence):
            if not Path(module.__file__).resolve().is_relative_to(backend):
                raise ReplayAbort('Loaded backend does not match frozen development checkout')
        yield
    finally:
        sys.path[:] = before


async def run_graph_job(*, dev, source_job, output, job_id, mode, ledger, transport, check_frozen, secrets=()):
    """Run one already-reserved private job; caller alone may finish the ledger job."""
    canary_release_policy.require_canary_enabled()
    from quality_campaign_safety import ReplayAbort, Evidence, StrictSharedQuota, redact
    from quality_campaign_budget import BudgetDenied
    output = Path(output)
    if (not output.is_absolute() or output.is_symlink() or not output.is_dir()
            or not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}', job_id)):
        raise ReplayAbort('Existing private output and explicit safe job identity required')
    evidence = Evidence(output, secrets)
    started, events = time.time(), []
    status, failure, persisted, bundle, artifacts = 'partial', None, None, None, None
    recorder, frozen_verified, primary = None, False, None
    limitations = [
        'Private artifact pipeline only; formal_publication=false and qualified_for_campaign=false.',
        'Independent full-text review, paired denominator and campaign acceptance remain external; no population success estimate.',
        'Original frozen snapshot only; no prior analyses, receipts or checkpoints adopted. RAG/embeddings/external repair unavailable.',
        'New run_id/runtime date/upstream outputs affect prompt bytes; this is not exact original prompt replay.',
        'Normal graph, quality, final audit, renderer and publication gates retained; no thinking override or Gemma batching enablement.',
        'HTTPX only; SDK retry=1. Graph/role retries remain bounded by shared ledger and existing shared quota.',
        'Returned provider model labels/HTTP responses are not research success; missing/partial usage is not zero.',
        'The caller owns outer watchdog, process cleanup and job/stage completion. This function never finishes or passes the ledger.',
    ]
    def remaining():
        ledger.check()
        job = ledger.snapshot()['jobs'].get(job_id)
        if not job or job['status'] != 'active': raise ReplayAbort('Campaign ledger job is not active')
        left = (job['deadline_ms'] - ledger.clock() * 1000) / 1000
        if left <= 0: raise ReplayAbort('Campaign job deadline reached')
        return left
    def checked():
        nonlocal frozen_verified
        remaining()
        if check_frozen() != transport.actual_hashes:
            raise ReplayAbort('Frozen job hashes changed; no publication')
        frozen_verified = True
    def event(payload):
        if not isinstance(payload, dict): payload = {'type': 'status', 'message': str(payload)}
        if recorder is not None and type(payload.get('agent_num')) is int: recorder.agent.set(payload['agent_num'])
        row = redact({'id': len(events) + 1, 'job_id': job_id, 'created_at': time.time(),
                      'payload': {**copy.deepcopy(payload), 'pipeline_id': mode}}, secrets)
        events.append(row)
        evidence.append('events.jsonl', row)
    try:
        if (mode not in ('v1', 'v2', 'v3', 'v4') or not isinstance(source_job, dict)
                or source_job.get('pipeline_id') != mode or not isinstance(source_job.get('data_snapshot'), dict)
                or not source_job['data_snapshot']):
            raise ReplayAbort('Original frozen pipeline and nonempty data_snapshot required')
        if transport.ledger is not ledger or transport.job_id != job_id or transport._restore is not None:
            raise ReplayAbort('Unentered transport must belong to the same reserved ledger job')
        checked()
        with _backend_scope(dev):
            import config
            from llm_client import KeyRotator
            from workflow_services import create_default_workflow_services, initialize_graph_state
            from workflow_context import legacy_context_from_graph
            from analysis_job_telemetry import analysis_node_telemetry_event
            from agent_runtime.routing import get_agent_model_sequence, get_audit_model_sequence
            from pipeline_modes import get_pipeline_agents
            all_secrets = tuple(dict.fromkeys([*secrets, *(key for values in config.LLM_API_KEYS_BY_PROVIDER.values() for key in values if key)]))
            secrets = all_secrets
            evidence.secrets = all_secrets
            evidence.save('source-copy.json', source_job)
            routes = {str(agent): get_agent_model_sequence(agent) for agent in get_pipeline_agents(mode)}
            configured = {model for sequence in routes.values() for model in sequence}
            configured.update(get_audit_model_sequence())
            configured.add(config.CONTEXT_DIGEST_MODEL)
            if (not transport.policies or not set(transport.policies).issubset(configured)
                    or config.GEMMA_EVIDENCE_BATCHING_ENABLED):
                raise ReplayAbort('Existing route allowlist required; Gemma batching must remain OFF')
            if config.LLM_SEMANTIC_CACHE_ENABLED or config.AGENT_STEP_CACHE_ENABLED:
                raise ReplayAbort('Fresh campaign requires semantic and agent step caches disabled')
            rotator = KeyRotator(config.LLM_API_KEYS_BY_PROVIDER)
            strict = StrictSharedQuota(rotator._shared_limiter)
            strict.assert_available()
            if strict.limiter._client.ping() is not True: raise ReplayAbort('Shared quota PING failed')
            strict.assert_available()
            rotator._shared_limiter = strict
            def telemetry(payload):
                evidence.append('node-telemetry.jsonl', payload)
                event(analysis_node_telemetry_event(payload))
            evidence.save('manifest.json', {'schema': 'private_campaign_graph.v1', 'job_id': job_id, 'mode': mode,
                'started_at': started, 'actual_hashes': transport.actual_hashes, 'allowed_models': sorted(transport.policies),
                'configured_agent_routes': routes, 'limitations': limitations})
            with transport:
                async with sdk_context(transport, evidence, strict, check_frozen) as recorder:
                    services = frozen_services(create_default_workflow_services(rotator=rotator,
                        progress_callback=event, cancel_check=transport.check_stream, telemetry_callback=telemetry))
                    initial = initialize_graph_state(copy.deepcopy(source_job['data_snapshot']), pipeline_id=mode)
                    initial.update(job_id=job_id, run_id=job_id, started_at=started)
                    state = await execute_graph(initial, services, mode, output, job_id, remaining(), evidence=evidence)
                    evidence.save('graph-result.json', state)
                    if state.get('status') != 'done' or state.get('blocking_issues'):
                        status = 'blocked'
                    else:
                        context = legacy_context_from_graph(state, services)
                        persisted, bundle, artifacts = await asyncio.wait_for(render_and_persist(context, mode, output,
                            f'{job_id}.html', checked, secrets=all_secrets), remaining())
            if persisted is not None:
                checked()
                status = 'published'
                event({'type': 'report_done', 'filename': persisted['filename'],
                    'quality_observation': publication_quality_receipt(bundle.data_snapshot, mode)})
    except BaseException as error:
        primary = error
        status = 'partial' if isinstance(error, (ReplayAbort, BudgetDenied, asyncio.CancelledError, TimeoutError, KeyboardInterrupt)) else 'error'
        failure = {'error_type': type(error).__name__,
            'boundary_reason': str(error) if isinstance(error, (ReplayAbort, BudgetDenied)) else None,
            'issues': getattr(error, 'issues', None)}
    try:
        cutoff = time.time()
        with _backend_scope(dev):
            job, metrics = project_outcome(job_id, mode, started, cutoff, status, events,
                                          filename=persisted['filename'] if status == 'published' else None)
        outcome = redact({'status': status, 'job_id': job_id, 'mode': mode, 'job': job, 'failure': failure,
            'cutoff': cutoff, 'provider_transport_calls': recorder.rows if recorder else [],
            'http_attempts': list(transport.http_rows.values()), 'artifacts': artifacts if status == 'published' else None,
            'publication': publication_quality_receipt(bundle.data_snapshot, mode) if status == 'published' else None,
            'frozen_verified': frozen_verified, 'formal_publication': False, 'qualified_for_campaign': False,
            'limitations': limitations}, secrets)
        evidence.save('outcome.json', outcome)
        evidence.save('metrics.json', metrics)
        return outcome
    except BaseException:
        if primary is not None:
            raise primary
        raise


async def run_normal_job(*, dev, source_job, output, job_id, mode, ledger, transport,
                         check_frozen, manifest_sha256, secrets=()):
    """Run the normal job in a caller-owned child; never finish its campaign ledger.

    The outer runner still owns source/billing review, exact environment, write/
    socket guards, watchdog and cleanup. This entry does not install or infer them.
    Diagnostic artifacts cannot be promoted to qualified samples here.
    """
    canary_release_policy.require_canary_enabled()
    from quality_campaign_safety import Evidence, ReplayAbort, StrictSharedQuota, private_path, redact
    from quality_campaign_budget import BudgetDenied
    output = Path(output)
    evidence = Evidence(output, secrets)
    status, failure, recorder, primary = 'partial', None, None, None
    durable, events, expected, artifacts = {}, [], {}, {}
    admitted = False
    frozen_verified = False
    bundle_snapshot = None
    strict = rotator = None
    started = time.time()
    limitations = [
        'Normal job/quant/provenance/graph/quality/renderer/private publication, not a qualified sample.',
        'Original frozen cutoff retained; no new source/RAG/memory or prior checkpoint/analysis adoption.',
        'Shared SDK and physical HTTP budgets retained; public call agent labels may be unknown.',
        'Caller owns source/billing qualification, socket/write isolation, watchdog and cleanup.',
        'No queue submission, retry renewal, stage passage or campaign completion here.',
    ]
    def remaining():
        ledger.check()
        job = ledger.snapshot()['jobs'].get(job_id)
        if not job or job['status'] != 'active':
            raise ReplayAbort('Campaign ledger job is not active')
        left = (job['deadline_ms'] - ledger.clock() * 1000) / 1000
        if left <= 0: raise ReplayAbort('Campaign job deadline reached')
        return left

    try:
        if (transport.ledger is not ledger or transport.job_id != job_id or transport._restore is not None
                or mode not in ('v1', 'v2', 'v3', 'v4') or not isinstance(source_job, dict)
                or source_job.get('pipeline_id') != mode or not isinstance(source_job.get('data_snapshot'), dict)):
            raise ReplayAbort('Normal job requires the exact frozen mode and unentered reserved transport')
        with _backend_scope(dev):
            import config, analysis_jobs, job_store, report_index
            from analysis_frozen_canary import frozen_canary_inputs
            from runtime_dependencies import RuntimeSettings
            from llm_client import KeyRotator
            from agent_runtime.routing import get_agent_model_sequence, get_audit_model_sequence
            from pipeline_modes import get_pipeline_agents
            from data_trust import sanitize_for_snapshot
            from report_persistence import report_bundle_keys_for_filename
            from report_repository import ReportRepository, ReportListQuery
            backend = Path(dev).resolve() / 'backend'
            for module in (analysis_jobs, job_store, report_index):
                if not Path(module.__file__).resolve().is_relative_to(backend):
                    raise ReplayAbort('Normal job module is not from the frozen backend')

            def check_paths():
                settings = RuntimeSettings.from_environment()
                expected_paths = ((analysis_jobs.OUTPUT_DIR, 'reports'), (settings.output_dir, 'reports'),
                    (job_store.TASK_DB_PATH, 'operational.sqlite3'), (report_index.CACHE_DB_PATH, 'cache.sqlite3'),
                    (settings.cache_db_path, 'cache.sqlite3'), (settings.checkpoint_path, 'checkpoint.sqlite3'))
                for value, suffix in expected_paths:
                    if private_path(output, value) != output / suffix:
                        raise ReplayAbort('Normal job runtime path differs from private child layout')
                if (settings.checkpoint_backend != 'sqlite'
                        or settings.checkpoint_postgres_dsn not in ('', 'isolated-postgres-disabled')
                        or settings.report_storage_backend != 'local' or settings.cache_backend != 'memory'):
                    raise ReplayAbort('Normal campaign requires private SQLite/local reports and memory cache')
                if config.GEMMA_EVIDENCE_BATCHING_ENABLED or config.LLM_SEMANTIC_CACHE_ENABLED or config.AGENT_STEP_CACHE_ENABLED:
                    raise ReplayAbort('Batching and reusable model caches must remain disabled')

            def checked(stage=None):
                nonlocal frozen_verified
                remaining()
                check_paths()
                if check_frozen() != transport.actual_hashes:
                    raise ReplayAbort('Frozen normal job hashes changed')
                if strict is not None:
                    if rotator._shared_limiter is not strict:
                        raise ReplayAbort('Normal job shared quota wrapper replaced')
                    strict.assert_available()
                frozen_verified = True
                return True

            secrets = tuple(dict.fromkeys((*secrets, *(key for values in config.LLM_API_KEYS_BY_PROVIDER.values()
                                                       for key in values if key))))
            evidence.secrets = secrets
            data = source_job['data_snapshot']
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            checked()
            routes = {str(agent): get_agent_model_sequence(agent) for agent in get_pipeline_agents(mode)}
            configured = {model for sequence in routes.values() for model in sequence}
            configured.update(get_audit_model_sequence())
            configured.add(config.CONTEXT_DIGEST_MODEL)
            if not transport.policies or not set(transport.policies).issubset(configured):
                raise ReplayAbort('Existing route allowlist required')

            def validate_bundle(bundle):
                nonlocal bundle_snapshot
                checked()
                snapshot_bytes = json.dumps(sanitize_for_snapshot(bundle.data_snapshot), ensure_ascii=False, indent=2).encode('utf-8')
                contents = {'html_key': bundle.html.encode('utf-8'), 'md_key': bundle.markdown.encode('utf-8'),
                            'data_key': snapshot_bytes}
                for value in contents.values():
                    text = value.decode('utf-8')
                    if any(secret in text for secret in secrets if secret) or re.search(r'AIza[\w-]{20,}', text):
                        raise ReplayAbort('Credential-shaped report rejected before private persistence')
                if expected: raise ReplayAbort('Normal job attempted a second publication')
                expected.update({key: {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
                                 for key, value in contents.items()})
                bundle_snapshot = copy.deepcopy(bundle.data_snapshot)
                return True

            # Validate source/identity before constructing a rotator or making a
            # Redis PING. The same async task owns scope admission and the job.
            with frozen_canary_inputs(campaign_id=ledger.identity['campaign_id'], job_id=job_id,
                    ticker=data.get('ticker'), pipeline_id=mode, source_json=raw,
                    source_sha256=hashlib.sha256(raw).hexdigest(), manifest_sha256=manifest_sha256,
                    boundary_check=checked):
                pass
            evidence.save('source-copy.json', source_job)
            evidence.save('manifest.json', {'schema': 'private_campaign_normal_job.v1', 'job_id': job_id,
                'mode': mode, 'started_at': started, 'manifest_sha256': manifest_sha256,
                'actual_hashes': transport.actual_hashes, 'allowed_models': sorted(transport.policies),
                'configured_agent_routes': routes, 'limitations': limitations})
            # Never attach to a preexisting normal job or overwrite its events.
            if job_store.get_job(job_id) or job_store.find_active_job(data['ticker'], mode):
                raise ReplayAbort('Normal job identity or active ticker already exists')
            created = job_store.create_or_attach_active_job(data['ticker'], mode, job_id=job_id, resume=False)
            if not created['created'] or created['job']['job_id'] != job_id or created['cancelled_job_ids']:
                raise ReplayAbort('Normal job registration was not create-only')
            admitted = True
            rotator = KeyRotator(config.LLM_API_KEYS_BY_PROVIDER)
            strict = StrictSharedQuota(rotator._shared_limiter)
            strict.assert_available()
            if strict.limiter._client.ping() is not True: raise ReplayAbort('Shared quota PING failed')
            strict.assert_available()
            rotator._shared_limiter = strict
            root = output / 'reports'
            root.mkdir(mode=0o700, exist_ok=True)
            with transport:
                async with sdk_context(transport, evidence, strict, check_frozen) as recorder:
                    async with asyncio.timeout(remaining()):
                        with frozen_canary_inputs(campaign_id=ledger.identity['campaign_id'], job_id=job_id,
                                ticker=data['ticker'], pipeline_id=mode, source_json=raw,
                                source_sha256=hashlib.sha256(raw).hexdigest(), manifest_sha256=manifest_sha256,
                                boundary_check=checked, publication_output_dir=str(root),
                                workflow_rotator=rotator, publication_validator=validate_bundle):
                            filename = await analysis_jobs.run_stock_analysis_job_async(job_id, data['ticker'], mode)
            checked()  # SDK cleanup and budgets must pass before reporting success.
            durable = job_store.get_job(job_id)
            events = job_store.get_events_since(job_id)
            if filename:
                if (durable.get('status') != 'done' or durable.get('filename') != filename
                        or not any(e['payload'].get('type') == 'report_done' and e['payload'].get('filename') == filename for e in events)
                        or len(expected) != 3):
                    raise ReplayAbort('Normal job completion lacks durable publication evidence')
                keys = report_bundle_keys_for_filename(filename)
                for key, digest in expected.items():
                    path = private_path(output, root / getattr(keys, key))
                    content = path.read_bytes()
                    if {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()} != digest:
                        raise ReplayAbort('Normal artifact readback differs from validated renderer bytes')
                    artifacts[key] = {'key': getattr(keys, key), **digest}
                rows, _ = ReportRepository().query(ReportListQuery(page=1, limit=10, output_dir=str(root), sync_metadata=False))
                if not any(row['filename'] == filename and row['pipeline_id'] == mode for row in rows):
                    raise ReplayAbort('Normal private report index readback missing')
                status = 'published'
            else:
                status = 'blocked' if any(e['payload'].get('phase') in ('report_quality_blocked', 'data_trust') for e in events) else 'error'
    except BaseException as error:
        primary = error
        status = 'partial' if isinstance(error, (ReplayAbort, BudgetDenied, asyncio.CancelledError, TimeoutError, KeyboardInterrupt)) else 'error'
        failure = {'error_type': type(error).__name__, 'boundary_reason': str(error) if isinstance(error, (ReplayAbort, BudgetDenied)) else None}
    try:
        if admitted:
            check_paths()  # Never follow changed DB globals even to capture failure.
            durable, events = job_store.get_job(job_id), job_store.get_events_since(job_id)
            evidence.save('normal-job.json', durable)
            for event in events: evidence.append('events.jsonl', event)
        outcome = redact({'status': status, 'job_id': job_id, 'mode': mode, 'job': durable, 'failure': failure,
            'cutoff': time.time(), 'provider_transport_calls': recorder.rows if recorder else [],
            'http_attempts': list(transport.http_rows.values()), 'artifacts': artifacts if status == 'published' else None,
            'publication': publication_quality_receipt(bundle_snapshot, mode) if status == 'published' else None,
            'frozen_verified': frozen_verified, 'formal_publication': False, 'qualified_for_campaign': False,
            'sdk_cleanup_verified': recorder is not None and recorder.cleanup_verified,
            'limitations': limitations}, secrets)
        evidence.save('outcome.json', outcome)
        with _backend_scope(dev):
            bound_events=[dict(row,job_id=job_id) if 'job_id' not in row else row for row in events]
            evidence.save('metrics.json', diagnostic_event_projection([durable] if durable else [], bound_events,
                cutoff=outcome['cutoff'], scope={'basis': 'one_private_normal_job', 'population_estimate': False,
                    'truncated': status == 'partial', 'events_truncated': status == 'partial'}))
        return outcome
    except BaseException:
        if primary is not None: raise primary
        raise
