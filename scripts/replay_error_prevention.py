#!/usr/bin/env python3
"""Export read-only evidence, then replay it offline; never repair or call providers.

Export: project_python scripts/replay_error_prevention.py export --audit-dir DIR
        --corpus DIR --checkpoint-db FILE --operational-db FILE --output-root DIR
Replay (use isolated runner for verification): import replay_manifest(manifest_path).
CLI replay needs only the exported corpus, never a live database or service.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import re
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


_SENSITIVE_KEYS = {'apikey','authorization','headers','cookie','cookies','accesstoken','refreshtoken',
                   'password','env','environ','environment','keyhash','keyfingerprint','rawkey','secret'}

def redact_sensitive(value):
    paths=[]
    def visit(item,path):
        if isinstance(item,dict):
            output={}
            for key,child in item.items():
                location=f'{path}.{key}'
                if (re.sub(r'[_-]','',str(key)).lower() in _SENSITIVE_KEYS
                        or re.sub(r'[_-]','',str(key)).lower().endswith('apikey')):
                    paths.append(location)
                else:output[key]=visit(child,location)
            return output
        if isinstance(item,(list,tuple)):return [visit(child,f'{path}[{i}]') for i,child in enumerate(item)]
        if isinstance(item,str):
            clean=re.sub(r'AIza[0-9A-Za-z_-]{35}', '[REDACTED_API_KEY]', item)
            clean=re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer [REDACTED]', clean)
            clean=re.sub(r"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token)[\"']?\s*[:=]\s*[\"']?[^\s,;\"']+", '[REDACTED_CREDENTIAL]', clean)
            if clean!=item:paths.append(path)
            return clean
        return item
    return visit(value,'$'),paths


def original_report_input_verified(snapshot,data):
    from report_analysis_evidence import validate_analysis_evidence, capture_analysis_evidence
    if snapshot.get('refreshed_without_analysis_rerun'):return False
    if 'analysis_evidence' in snapshot:
        packet=validate_analysis_evidence(snapshot['analysis_evidence'])
        if packet.get('input_verification')!='hash_verified':return False
        section=packet.get('sections',{}).get('analysis_input',{})
        if section.get('status')!='preserved':return False
        from data_trust_snapshot_sanitizer import sanitize_for_snapshot
        current=sanitize_for_snapshot(data);current.pop('analysis_evidence',None)
        return section.get('data')==current
    return capture_analysis_evidence({'data':data},legacy=True).get('input_verification')=='hash_verified'


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()


def write_json(path,value):
    path.write_bytes(encoded(value));path.chmod(0o600)
    return sha256(path.read_bytes())


def labels(error):
    matches={'institutional':'法人','short_observation':'thesis_invalidation',
             'position_contradiction':'零部位','market_manifest':'來源引用無法綁定',
             'recommendation_return':'建議/報酬矛盾','missing_target':'缺少「目標價」'}
    return [key for key,needle in matches.items() if needle in (error or '')]


def normalized_context(context,data):
    context=copy.deepcopy(context or {})
    context['data']=copy.deepcopy(data)
    for field in ('analyses','structured_outputs','market_context_manifests'):
        context[field]={int(k) if str(k).isdigit() else k:v for k,v in (context.get(field) or {}).items()}
    return context


def replay_case(case):
    """Current gates only; repeated findings are not automatically called model errors."""
    from final_audit_mode_contracts import mode_execution_contract_issues
    from institutional_evidence import institutional_evidence_issues, institutional_evidence_diagnostics
    from market_context_assessment import assess_final_market_context
    from evidence_exit_gate import evaluate_report_evidence
    from reporting.content_credibility import evaluate_content_credibility
    result={'identity':case['identity'],'kind':case['kind'],'checks':{},'missing':[],
            'classification':'evidence_missing','manual_truth':'not_inferred_from_gate'}
    data=case.get('data') or {};context=normalized_context(case.get('context'),data)
    if not data:result['missing'].append('source input unavailable')
    if not context.get('analyses') and not context.get('parsed'):result['missing'].append('original output unavailable')
    if result['missing']:return result
    if case['kind']=='job':
        supported={'institutional','short_observation','position_contradiction','market_manifest',
                   'recommendation_return','missing_target','mode_execution'}
        families=set(case.get('labels',[]))
        result['original_failure_coverage']={'covered':sorted(families & supported),'uncovered':sorted(families-supported)}
        if not families or families-supported:
            result['missing'].append('original failure family/output not covered by this job replay; report evidence/contract gates need original markdown')
    pipeline=context.get('pipeline_id')
    if case['kind']=='job':
        from structured_output_parser import parse_structured_data
        context['parsed']=parse_structured_data(context)
        result['projection_basis']='current parser of retained original analyses/structured outputs; saved parsed remains in corpus'
    parsed=context.get('parsed') or {}
    if pipeline not in {'v1','v2','v3','v4'}:result['missing'].append('pipeline unavailable')
    checks=result['checks']
    checks['mode_execution']=mode_execution_contract_issues(parsed,position_plan_agent=16 if pipeline=='v2' else None,
        short_setup_agent=19 if pipeline=='v3' else None,trade_setup_agent=24 if pipeline=='v4' else None)
    checks['institutional']={str(k):institutional_evidence_issues(v,data)
        for k,v in context['analyses'].items() if k in {23,24}}
    checks['institutional_diagnostics']={str(k):institutional_evidence_diagnostics(v,data)
        for k,v in context['analyses'].items() if k in {23,24}}
    checks['market']=assess_final_market_context(context)
    if 'market_manifest' in case.get('labels',[]) and checks['market']['status']=='not_recorded':
        result['missing'].append('original market contract/receipt unavailable; do not synthesize it')
    if case['kind']=='report':
        markdown=case.get('markdown');snapshot=copy.deepcopy(case.get('snapshot') or {})
        if not markdown:result['missing'].append('original markdown unavailable')
        else:
            checks['evidence']=evaluate_report_evidence(markdown,snapshot)
            snapshot['evidence_exit_gate']=checks['evidence']
            # Keep recorded final-audit findings visible; do not erase history to gain a pass.
            checks['content']=evaluate_content_credibility(context,snapshot,markdown)
        result['original_input_verified']=original_report_input_verified(snapshot,data)
        if not result['original_input_verified']:
            result['missing'].append('original conclusion input binding unknown or mismatched; snapshot hash alone is not proof')
    from final_audit import run_final_report_audit
    checks['final_audit']=run_final_report_audit(copy.deepcopy(context),append_section=False)
    failed=bool(checks['mode_execution'] or any(checks['institutional'].values())
                or checks['market']['critical'] or checks['market']['warnings']
                or checks['final_audit'].get('critical'))
    if case['kind']=='report':failed=failed or checks.get('content',{}).get('status')!='passed'
    if not result['missing']:
        reviewed=case.get('manual_review') or {}
        confirmed=(reviewed.get('confirmed_true_error') and bool(case.get('input_hash'))
                   and reviewed.get('input_hash')==case.get('input_hash'))
        result['classification']=(('true_error_still_blocked' if failed else 'true_error_unexpectedly_passed') if confirmed
                                  else ('still_reproduced' if failed else 'fixed_in_scoped_replay'))
        if confirmed:result['manual_truth']=reviewed
    result['scope']='current deterministic gates only; no generation, repair, publication or automatic true-error verdict'
    return result


def replay_manifest(path):
    path=Path(path).resolve();manifest=json.loads(path.read_text());results=[]
    for entry in manifest['cases']:
        try:
            payload=(path.parent/entry['payload']).resolve()
            if not payload.is_relative_to(path.parent):raise ValueError('payload outside corpus')
            content=payload.read_bytes()
            if sha256(content)!=entry['sha256']:raise ValueError('payload hash mismatch')
            result=replay_case(json.loads(content))
        except Exception as exc:
            result={'identity':entry['identity'],'classification':'evidence_missing','missing':[('payload outside corpus' if isinstance(exc,ValueError) and str(exc)=='payload outside corpus'
                                                       else 'corpus read/validation failure: '+type(exc).__name__)]}
        results.append(result)
    from collections import Counter
    code_paths=sorted(set(ROOT.glob('backend/**/*.py')) | set(ROOT.glob('backend/prompts/*.json')) | {Path(__file__).resolve()})
    receipt={str(p.relative_to(ROOT)):sha256(p.read_bytes()) for p in code_paths}
    return {'schema_version':1,'replay_code_receipt':receipt,'manifest_sha256':sha256(path.read_bytes()),'results':results,
            'counts':dict(Counter(r['classification'] for r in results))}


def read_only(path):
    connection=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    connection.row_factory=sqlite3.Row
    connection.execute('PRAGMA query_only=ON');connection.execute('BEGIN')
    return connection


def candidate_responses(events):
    active={};results=[]
    for event in events:
        payload=event['payload'];agent=payload.get('agent_num');phase=event.get('phase')
        if phase=='llm_provider_request':active[agent]={'request_event':event['id'],'agent':agent,'raw':''}
        elif phase=='llm_stream_delta':
            active.setdefault(agent,{'agent':agent,'request_event':None,'raw':''})['raw']+=payload.get('delta','')
        elif phase in {'llm_model_response','llm_model_error'}:
            candidate=active.pop(agent,{'agent':agent,'request_event':None,'raw':''})
            candidate.update({'response_event':event['id'],'metadata':payload.get('metadata',{}),
                              'complete':phase=='llm_model_response','raw_sha256':sha256(candidate['raw'].encode())})
            results.append(candidate)
    results.extend({**c,'complete':False} for c in active.values())
    return results


def export_corpus(audit_dir,corpus,checkpoint_db,operational_db,output_root):
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from report_artifacts import ReportArtifactLocator
    from storage.report_storage import LocalFileStorage
    audit_dir=Path(audit_dir);corpus=Path(corpus);corpus.mkdir(parents=True,exist_ok=True);corpus.chmod(0o700)
    manifest={'schema_version':1,'origin':str(audit_dir),'cases':[],'constraints':'read-only source; no provider calls'}
    jobs=json.loads((audit_dir/'failed-job-fixture-index.json').read_text())
    reports=[r for r in json.loads((audit_dir/'reports.json').read_text()) if r.get('gates',{}).get('content_credibility')=='warning']
    def save(case):
        case,redactions=redact_sensitive(case)
        case['redaction_paths']=redactions
        filename=case['kind']+'-'+sha256(case['identity'].encode())[:20]+'.json'
        digest=write_json(corpus/filename,case)
        manifest['cases'].append({k:case.get(k) for k in ('identity','kind','labels','original_version','receipt','input_hash')}
                                 |{'payload':filename,'sha256':digest})
    with read_only(checkpoint_db) as checkpoints,read_only(operational_db) as operational:
        for job in jobs:
            events=[]
            for row in operational.execute('SELECT id,phase,event_type,created_at,payload FROM analysis_events WHERE job_id=? ORDER BY id',(job['job_id'],)):
                event=dict(row);event['payload']=json.loads(event['payload']);events.append(event)
            case={'identity':job['job_id'],'kind':'job','job':job,'labels':labels(job['error']),
                  'data':{},'context':{},'events':events,'candidates':candidate_responses(events)}
            rows=checkpoints.execute('SELECT thread_id,checkpoint_ns,checkpoint_id,type,checkpoint FROM checkpoints WHERE thread_id>=? AND thread_id<? ORDER BY checkpoint_id DESC',(job['job_id'],job['job_id']+'\uffff'))
            for row in rows:
                try:state=JsonPlusSerializer().loads_typed((row['type'],row['checkpoint'])).get('channel_values',{})
                except Exception:continue
                if not isinstance(state,dict) or not state.get('raw_financial_data'):continue
                raw=state.get('raw_financial_data') or {};data=raw.get('input')
                if not isinstance(data,dict):continue
                receipt={k:row[k] for k in ('thread_id','checkpoint_ns','checkpoint_id','type')}
                receipt['blob_sha256']=sha256(row['checkpoint'])
                receipt['raw_blob_not_exported']='Raw binary may contain credentials; retain source hash and read-only DB locator only'
                receipt['source_database']=str(Path(checkpoint_db).resolve())
                case.update({'context':state,'data':data,'receipt':receipt,'input_hash':sha256(encoded(data)),
                             'input_hash_basis':'canonical JSON of exact checkpoint raw_financial_data.input',
                             'original_version':state.get('code_commit') or None})
                break
            save(case)
    locator=ReportArtifactLocator(LocalFileStorage(str(output_root)))
    for report in reports:
        case={'identity':report['filename'],'kind':'report','report':report,'labels':['content_warning'],'data':{},'context':{}}
        try:
            bundle=locator.require_bundle(report['filename'],require_markdown=False)
            snapshot=bundle.read_data_snapshot();data=snapshot.get('data') or {};context=snapshot.get('rerun_context') or {}
            context={**{k:v for k,v in snapshot.items() if k.startswith('market_context_')},**context,
                     'pipeline_id':context.get('pipeline_id') or snapshot.get('pipeline'),'final_audit':snapshot.get('final_audit') or {}}
            markdown_item=bundle.storage.get_report(bundle.markdown_key) if bundle.markdown_key else None
            case.update({'data':data,'context':context,'snapshot':snapshot,
                         'markdown':markdown_item.content.decode('utf-8') if markdown_item else None,
                         'input_hash':sha256(encoded(data)),'input_hash_basis':'saved artifact data, not proof of original model input',
                         'original_version':(snapshot.get('reproducibility_packet') or {}).get('code_commit') or None,
                         'receipt':{'data_key':bundle.data_key,'markdown_key':bundle.markdown_key,
                                    'data_sha256':sha256(bundle.read_data_item().content)}})
        except Exception as exc:case['extraction_error']=type(exc).__name__
        save(case)
    write_json(corpus/'manifest.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    export=sub.add_parser('export')
    for name in ('audit-dir','corpus','checkpoint-db','operational-db','output-root'):export.add_argument('--'+name,required=True,type=Path)
    replay=sub.add_parser('replay');replay.add_argument('manifest',type=Path);replay.add_argument('--result',required=True,type=Path)
    args=parser.parse_args()
    if args.command=='export':
        result=export_corpus(args.audit_dir,args.corpus,args.checkpoint_db,args.operational_db,args.output_root)
        print(json.dumps({'exported':len(result['cases'])}))
    else:
        result=replay_manifest(args.manifest);write_json(args.result,result);print(json.dumps(result['counts']))
        if result['counts'].get('true_error_unexpectedly_passed'):raise SystemExit(2)

if __name__=='__main__':main()
