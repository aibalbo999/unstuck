"""Read-only, bounded observations; counts and eventual success are not causality."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import math

from llm_daily_usage import LOCAL_BLOCK_KINDS


def metadata(row):
    try:
        value = json.loads(row.get('metadata_json') or '{}')
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def number(value):
    return float(value) if isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value) and value >= 0 else None


def union_seconds(intervals):
    end, total = None, 0.0
    for start, stop in sorted(intervals):
        total += max(0.0, stop-max(start, end if end is not None else start))
        end = max(stop, end if end is not None else stop)
    return round(total, 3)


def percentile(values, fraction):
    values = sorted(v for v in values if number(v) is not None)
    return round(values[math.ceil(len(values)*fraction)-1], 3) if values else None


def build_execution_observations(rows, jobs, *, truncated=False, since=None, until=None):
    rows = [dict(row) for row in rows]
    parsed = [(row, metadata(row)) for row in rows]
    starts, terminals, transport_attempts = {}, {}, set()
    for row,m in parsed:
        if row['operation']=='llm_transport_observation' and isinstance(m.get('transport_attempt_id'),str):
            identity=m['transport_attempt_id']
            if row['status']=='attempt':starts[identity]=(row,m)
            else:terminals[identity]=(row,m)
            if row['status']!='attempt' and m.get('attempt_id'):transport_attempts.add(m['attempt_id'])
    totals=Counter(agent_request_events=0,sdk_callback_attempts=len(starts),
                   sdk_callback_terminal_events=len(terminals),local_preflight_events=0)
    by_job=defaultdict(lambda: {'requests':0,'tokens':[],'token_events':0,'waits':[], 'local':0})
    quotas,kinds,detail_statuses=[],Counter(),Counter()
    local_reasons, purposes, model_calls=Counter(),Counter(),Counter()
    logical_attempts=defaultdict(set); logical_success=set()
    evidence=Counter(request_events=0,valid_batch_responses=0,cache_hits=0,appendix_events=0)
    appendix_jobs=set(); appendix_reports=set(); evidence_jobs=set()
    quality={}; cooldowns={}; recoveries=set(); seen_decisions=set(); seen_waits=set(); quota_seen=set()
    versions=Counter(); process_gaps={}
    token_records=[]
    for row,m in parsed:
        operation,model,status=row['operation'],row.get('model_id') or 'unknown',row.get('status')
        job=m.get('job_id'); bucket=by_job[job] if job else None
        version=m.get('effective_settings_sha256')
        if isinstance(version,str) and len(version)==64:versions[version]+=1
        process=m.get('observer_process_id');process_started=m.get('observer_process_started_at')
        if number(process) is not None and number(process_started) is not None:
            key=(int(process),process_started)
            process_gaps[key]=max(process_gaps.get(key,0),int(number(m.get('telemetry_dropped_events_before')) or 0))
        if operation=='llm_provider_request':
            units=int(number(row.get('units')) or 0)
            totals['agent_request_events']+=units
            model_calls[model]+=units;purposes[m.get('call_purpose') or 'analysis_or_legacy_unspecified']+=units
            if bucket:bucket['requests']+=units
            if m.get('logical_call_id') and m.get('attempt_id') and m.get('call_purpose')!='evidence_batch':
                logical_attempts[m['logical_call_id']].add(m['attempt_id'])
            if m.get('call_purpose')=='evidence_batch':
                evidence['request_events']+=units
                if job:evidence_jobs.add(job)
        elif operation=='llm_model_response':
            if m.get('logical_call_id') and m.get('call_purpose')!='evidence_batch':logical_success.add(m['logical_call_id'])
            if m.get('call_purpose')=='evidence_batch':evidence['valid_batch_responses']+=1
        elif operation=='llm_admission_decision':
            identity=m.get('observation_event_id') or f"legacy:{row.get('id')}"
            phase=m.get('phase')
            if identity not in seen_decisions and phase in {'model_circuit_open','model_input_capacity','model_config_error'}:
                seen_decisions.add(identity)
                totals['local_preflight_events']+=1;local_reasons[phase]+=1
                if bucket:bucket['local']+=1
        elif operation=='llm_model_error' and m.get('error_kind') in LOCAL_BLOCK_KINDS:
            totals['local_preflight_events']+=1;local_reasons[m['error_kind']]+=1
            if bucket:bucket['local']+=1
        elif operation=='llm_wait_interval':
            identity=m.get('wait_id') or f"legacy:{row.get('id')}"
            if identity not in seen_waits:
                seen_waits.add(identity)
                start,elapsed=number(m.get('started_at')),number(m.get('elapsed_seconds'))
                if bucket and start is not None and elapsed is not None:bucket['waits'].append((start,start+elapsed))
        elif operation=='llm_evidence_progress':
            if m.get('phase')=='gemma_evidence_cache_hit':evidence['cache_hits']+=1
            if m.get('phase')=='gemma_evidence_appendix_prepared' and m.get('evidence_appendix_attached') is True:
                evidence['appendix_events']+=1
                if job:
                    appendix_jobs.add(job)
                    appendix_reports.add((job,m.get('pipeline_id')))
        elif operation=='llm_report_quality_observation' and job:
            quality[(job,m.get('pipeline_id'))]=(row.get('created_at',0),status,m.get('gates') or {})
        elif operation=='llm_congestion_transition':
            identity=m.get('cooldown_id')
            if identity:
                cooldowns[identity]=m
                if m.get('transition')=='recovered':recoveries.add(identity)

        provider_terminal = (operation=='llm_transport_observation' and status!='attempt'
                             and m.get('transport_attempt_id') in terminals
                             and terminals[m['transport_attempt_id']][0] is row)
        # Rows are dictionaries retained in parsed; terminal events are deduplicated by transport identity.
        legacy_terminal = (operation in {'llm_model_error','llm_model_response'}
                           and m.get('attempt_id') not in transport_attempts
                           and m.get('error_kind') not in LOCAL_BLOCK_KINDS)
        if provider_terminal or legacy_terminal:
            usage=m.get('usage') if provider_terminal else (m.get('response_diagnostics') or {}).get('usage')
            usage=usage if isinstance(usage,dict) else {}
            token_records.append((job,number(usage.get('input_tokens'))))
            is_quota=m.get('provider_status_code')==429 or (legacy_terminal and status in {'quota_error','rate_limited'} and m.get('error_kind')=='ClientError')
            if is_quota:
                identity=m.get('transport_attempt_id') or m.get('attempt_id') or f"legacy:{row.get('id')}"
                if identity not in quota_seen:
                    quota_seen.add(identity);quotas.append((row,m))
                    detail=m.get('quota_observation') or {}
                    violations=detail.get('violations') or (m.get('provider_quota') or {}).get('violations') or []
                    observed={v.get('kind') for v in violations if isinstance(v,dict) and v.get('kind') in {'rpm','rpd','tpm','input_tpm'}}
                    kinds.update(observed or {'unknown'})
                    detail_statuses[detail.get('detail_status') or 'legacy_not_recorded']+=1
    for job,tokens in token_records:
        if job:
            by_job[job]['token_events']+=1
            if tokens is not None:by_job[job]['tokens'].append(int(tokens))
    reports=[]
    for job in jobs:
        job=dict(job);identity=job['job_id'];bucket=by_job.get(identity)
        quality_row=quality.get((identity,job.get('pipeline_id')))
        created,started,finished=number(job.get('created_at')),number(job.get('started_at')),number(job.get('finished_at'))
        reports.append({'job_id':identity,'pipeline_id':job.get('pipeline_id'),'status':job.get('status'),
                        'artifact_recorded':bool(job.get('filename')),
                        'quality_outcome':quality_row[1] if quality_row else 'not_recorded',
                        'quality_gates':quality_row[2] if quality_row else {},
                        'observed_request_events':bucket['requests'] if bucket else None,
                        'known_input_tokens':sum(bucket['tokens']) if bucket and bucket['tokens'] else None,
                        'input_token_samples':len(bucket['tokens']) if bucket else 0,
                        'input_token_terminal_events':bucket['token_events'] if bucket else 0,
                        'observed_wait_union_seconds':union_seconds(bucket['waits']) if bucket and bucket['waits'] else None,
                        'queue_seconds':max(0,started-created) if started is not None and created is not None else None,
                        'completed_elapsed_seconds':max(0,finished-created) if finished is not None and created is not None else None,
                        'window_contains_job_start':created is not None and (since is None or created>=since),
                        'sample_truncated':truncated})
    known_tokens=[value for _,value in token_records if value is not None]
    quality_counts=Counter(value[1] for value in quality.values())
    passed_reports={key for key,(_,outcome,_) in quality.items()
                    if outcome=='gate_passed' and key[1] in {'v1','v2','v3','v4'}}
    durations=[m.get('elapsed_seconds') for _,m in terminals.values() if number(m.get('elapsed_seconds')) is not None]
    retried={identity for identity,attempts in logical_attempts.items() if len(attempts)>1}
    return {'schema_version':1,'available':True,'since':since,'until':until,'sample_truncated':truncated,
            'sample_events':len(rows),'totals':dict(totals),'model_request_events':dict(model_calls),'request_purposes':dict(purposes),
            'quota':{'events':len(quotas),'kinds':dict(kinds),'detail_statuses':dict(detail_statuses),
                     'classified_pct':round(100*(len(quotas)-kinds['unknown'])/len(quotas),1) if quotas else None},
            'local_preflight_reasons':dict(local_reasons),
            'cooldowns':{'observed_incidents':len(cooldowns),'recovered_incidents':len(recoveries)},
            'retry':{'logical_calls_with_multiple_attempts':len(retried),
                     'eventually_returned_role_response':len(retried & logical_success), 'causal_improvement_verified':False},
            'transport_latency_seconds':{'p50':percentile(durations,.5),'p95':percentile(durations,.95)},
            'tokens':{'known_input_tokens':int(sum(known_tokens)) if known_tokens else None,'samples':len(known_tokens),
                      'terminal_events':len(token_records),'coverage_pct':round(100*len(known_tokens)/len(token_records),1) if token_records else None},
            'evidence':{**dict(evidence),'jobs_with_requests':len(evidence_jobs),'jobs_with_appendix':len(appendix_jobs),
                        'jobs_with_appendix_gate_passed':len({job for job,_ in appendix_reports & passed_reports})},
            'quality':dict(quality_counts),'reports':reports,
            'configuration_versions':dict(versions),
            'observed_process_gaps':[{'process_id':pid,'process_started_at':at,'dropped_events':value}
                                     for (pid,at),value in process_gaps.items()],
            'basis':'bounded_event_sample; sdk_callbacks_are_not_http_receipts; legacy_agent_scope_excludes_auxiliary_calls',
            'coverage_note':'缺少識別、tokens 或品質結果保留未知；重試後成功是關聯，並非因果改善；等待區間按任務合併重疊，不跨任務加總。'}
