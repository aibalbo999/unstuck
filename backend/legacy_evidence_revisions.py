"""Authorized finite legacy scope; append-only evidence, reversible activation.

No calls to save_result and no update/delete of original trade rows. Revisions
are research evidence only and are not silently substituted into performance.
"""
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

import trade_backtest_store
from backtest_session_contract import session_window

POLICY = 'legacy_evidence_revision.v1;strict_existing_contract;no_pit_or_actual_cost_claim'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def _connect():
    return sqlite3.connect(trade_backtest_store._path(), timeout=15)


def activate_scope(manifest):
    rows = manifest.get('rows', [])
    if len(rows) != 76 or len({r['scope_id'] for r in rows}) != 76:
        raise ValueError('exactly 76 distinct approved scope IDs required')
    if manifest.get('schema_version') != 'legacy-revision-scope-v1' or not manifest.get('authorized_by'):
        raise ValueError('explicit authorization manifest required')
    for row in rows:
        original = trade_backtest_store.get_result(report_filename=row['report_filename'], horizon_trading_days=10)
        if row.get('horizon_trading_days') != 10 or original is None or digest(original) != row['original_payload_sha256']:
            raise ValueError('original scope changed;activation aborted')
        if original.get('status') != 'insufficient_data' or original.get('reason') != 'missing_ohlc':
            raise ValueError('original outside approved missing-OHLC scope')
        window = session_window(date.fromisoformat(row['generated_date']),10)
        if window.get('status') != 'verified' or window['sessions'] != row['sessions'] or window['maturity_date'] != row['maturity_date']:
            raise ValueError('verified calendar differs from frozen scope')
    payload=encoded(manifest)
    with closing(_connect()) as conn, conn:
        conn.execute('CREATE TABLE IF NOT EXISTS trade_evidence_revision_batches_v1 (batch_id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, active INTEGER NOT NULL, activated_at TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS trade_evidence_revisions_v1 (revision_id TEXT PRIMARY KEY,batch_id TEXT NOT NULL,scope_id TEXT NOT NULL,as_of_session TEXT NOT NULL,state TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL)')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_revision_session ON trade_evidence_revisions_v1(batch_id,scope_id,as_of_session)')
        old=conn.execute('SELECT manifest_sha256 FROM trade_evidence_revision_batches_v1 WHERE batch_id=?',(manifest['batch_id'],)).fetchone()
        if old and old[0] != hashlib.sha256(payload.encode()).hexdigest():
            raise ValueError('immutable batch manifest differs')
        conn.execute('INSERT OR IGNORE INTO trade_evidence_revision_batches_v1 VALUES (?,?,?,?,?)',(manifest['batch_id'],payload,hashlib.sha256(payload.encode()).hexdigest(),1,datetime.now(timezone.utc).isoformat()))
    return manifest['batch_id']


def deactivate_batch(batch_id):
    with closing(_connect()) as conn,conn:
        conn.execute('UPDATE trade_evidence_revision_batches_v1 SET active=0 WHERE batch_id=?',(batch_id,))


def active_manifests():
    path=trade_backtest_store._path()
    if not path.exists(): return []
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='trade_evidence_revision_batches_v1'").fetchone(): return []
        return [json.loads(r[0]) for r in conn.execute('SELECT manifest_json FROM trade_evidence_revision_batches_v1 WHERE active=1')]


def append_revision(batch_id,scope_id,as_of,payload):
    revision_id=digest({'batch_id':batch_id,'scope_id':scope_id,'as_of':as_of,'payload':payload,'policy':POLICY})
    with closing(_connect()) as conn,conn:
        active=conn.execute('SELECT active FROM trade_evidence_revision_batches_v1 WHERE batch_id=?',(batch_id,)).fetchone()
        if not active or not active[0]: return False
        cursor=conn.execute('INSERT OR IGNORE INTO trade_evidence_revisions_v1 VALUES (?,?,?,?,?,?,?)',(revision_id,batch_id,scope_id,as_of,payload['state'],encoded(payload),datetime.now(timezone.utc).isoformat()))
        return bool(cursor.rowcount)


def revision_summary():
    manifests=active_manifests()
    if not manifests: return {'active_batches':0,'approved_scope_count':0,'revisions':0,'original_rows_modified':0}
    from zoneinfo import ZoneInfo
    from two_week_market_eligibility import completed_session
    as_of=completed_session(datetime.now(ZoneInfo('Asia/Taipei')))
    from legacy76_dispositions import BATCH_ID, MANIFEST_SHA256, active_for_connection
    from market_evidence_policy import completed_evidence_session
    with closing(sqlite3.connect(trade_backtest_store._path().as_uri()+'?mode=ro',uri=True)) as conn:
        rows=conn.execute('SELECT r.state,count(*) FROM trade_evidence_revisions_v1 r JOIN trade_evidence_revision_batches_v1 b USING(batch_id) WHERE b.active=1 GROUP BY r.state').fetchall()
        terminal=set(conn.execute("SELECT DISTINCT r.batch_id,r.scope_id FROM trade_evidence_revisions_v1 r JOIN trade_evidence_revision_batches_v1 b USING(batch_id) WHERE b.active=1 AND r.state IN ('target_first','stop_first','horizon_exit','not_entered','no_trade','ambiguous')").fetchall())
        closed = active_for_connection(conn, BATCH_ID) if any(m['batch_id'] == BATCH_ID for m in manifests) else {}
    for manifest in manifests:
        if manifest['batch_id'] == BATCH_ID and closed and digest(manifest) != MANIFEST_SHA256:
            raise ValueError('disposition manifest binding changed')
    disposed={(BATCH_ID,s['scope_id']) for m in manifests if m['batch_id']==BATCH_ID for s in m['rows'] if s['scope_id'] in closed}
    if terminal & disposed: raise ValueError('disposition conflicts with trading terminal state')
    remaining=[s for m in manifests for s in m['rows'] if (m['batch_id'],s['scope_id']) not in terminal | disposed]
    waiting=sum(s['maturity_date']>as_of for s in remaining) if as_of else None
    return {'active_batches':len(manifests),'approved_scope_count':sum(len(m['rows']) for m in manifests),'revisions':sum(r[1] for r in rows),'revision_state_counts':dict(rows),'terminal_scope_count':len(terminal),'unscored_disposition_scope_count':len(disposed),'settled_scope_count':len(terminal | disposed),'remaining_scope_count':len(remaining),'awaiting_maturity_count':waiting,'mature_unscored_scope_count':len(remaining)-waiting if waiting is not None else None,'as_of_completed_session':as_of,'as_of_evidence_session':completed_evidence_session(datetime.now(ZoneInfo('Asia/Taipei'))),'evidence_session_policy':'Asia/Taipei 22:30 acquisition boundary;not source finality','original_rows_modified':0,'performance_substitution':False,'validated_strategy_results':0}


def run_due_revisions(*,output_dir,as_of,bar_fetcher):
    from mode_trade_backtest import _parsed_snapshot,_plan_inputs,_execution_context
    from report_history_storage import storage_for_existing_output_dir
    from report_artifacts import ReportArtifactLocator
    from trade_path_backtest import evaluate_trade_path
    from legacy76_dispositions import BATCH_ID, MANIFEST_SHA256, active_for_path
    result={'new_revisions':0,'awaiting_maturity':0,'already_attempted_session':0,'already_terminal':0,'awaiting_source_evidence':0,'source_waits':[],'errors':[],
            'closed_unscored':0,'validation_rejections':[],'validation_rejection_count':0,'as_of_evidence_session':as_of.isoformat()}
    for manifest in active_manifests():
        closed = active_for_path(trade_backtest_store._path()) if manifest.get('batch_id') == BATCH_ID else {}
        if closed and digest(manifest) != MANIFEST_SHA256:
            raise ValueError('disposition manifest binding changed')
        for scope in manifest['rows']:
            if scope['scope_id'] in closed:
                result['closed_unscored']+=1;continue
            if scope['maturity_date']>as_of.isoformat():
                result['awaiting_maturity']+=1;continue
            with closing(_connect()) as conn:
                terminal=conn.execute("SELECT 1 FROM trade_evidence_revisions_v1 WHERE batch_id=? AND scope_id=? AND state IN ('target_first','stop_first','horizon_exit','not_entered','no_trade','ambiguous')",(manifest['batch_id'],scope['scope_id'])).fetchone()
                attempted=conn.execute('SELECT 1 FROM trade_evidence_revisions_v1 WHERE batch_id=? AND scope_id=? AND as_of_session=?',(manifest['batch_id'],scope['scope_id'],as_of.isoformat())).fetchone()
            if terminal:
                result['already_terminal']+=1;continue
            if attempted:
                result['already_attempted_session']+=1;continue
            stage = 'original_binding'
            try:
                original = trade_backtest_store.get_result(report_filename=scope['report_filename'], horizon_trading_days=10)
                if original is None or scope.get('horizon_trading_days', 10) != 10 or digest(original) != scope['original_payload_sha256']:
                    raise ValueError('original row changed;no revision')
                generated=date.fromisoformat(scope['generated_date'])
                window=session_window(generated,10)
                if window.get('status')!='verified' or window['sessions']!=scope['sessions']:
                    raise ValueError('calendar changed;no revision')
                stage = 'report_contract'
                report={'filename':scope['report_filename'],'ticker':scope['ticker']}
                storage=storage_for_existing_output_dir(output_dir,None)
                item=storage.get_report(ReportArtifactLocator(storage).require_key(scope['report_filename'],kind='data'))
                raw=item.content.decode('utf-8');snapshot=json.loads(raw)
                parsed=_parsed_snapshot(report,output_dir)
                inputs,horizons,issue=_plan_inputs('v4',parsed)
                if issue or 10 not in horizons: raise ValueError(issue or 'horizon not in original plan')
                # Query exactly the approved window; acquisition time is not historical availability.
                stage = 'source_fetch'
                bars=bar_fetcher(scope['ticker'],generated,date.fromisoformat(scope['maturity_date']))
                from maturity_source_admission import assess_maturity_source
                stage = 'source_admission'
                source_gate=assess_maturity_source(bars,scope['ticker'],scope['maturity_date'])
                if not source_gate['eligible']:
                    result['awaiting_source_evidence']+=1
                    result['source_waits'].append({'scope_id':scope['scope_id'],'ticker':scope['ticker'],'maturity_date':scope['maturity_date'],'source_gate':source_gate})
                    continue
                stage = 'validation'
                metrics=evaluate_trade_path(**inputs,bars=bars,generated_date=generated,as_of=as_of,horizon_trading_days=10,market='tw',execution_context=_execution_context(report,output_dir,parsed,inputs))
                if manifest['batch_id'] == BATCH_ID and metrics['status'] == 'insufficient_data':
                    result['validation_rejections'].append({'batch_id':BATCH_ID,'scope_id':scope['scope_id'],'ticker':scope['ticker'],'maturity_date':scope['maturity_date'],
                        'evidence_session':as_of.isoformat(),'reason':metrics.get('reason','validation_rejected'),
                        'provider':(bars[0].get('observation_provenance') or {}).get('provider') if bars else None})
                    result['validation_rejection_count']+=1
                payload={'source_gate_version':'maturity_raw_alignment:v1','source_admission':source_gate,'state':metrics['status'],'metrics':metrics,'scope':scope,'policy':POLICY,'bars':bars,'bars_sha256':digest(bars),'report_snapshot':snapshot,'report_snapshot_raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),'retrieved_at':datetime.now(timezone.utc).isoformat(),'point_in_time_verified':False,'actual_cost_verified':False,'strategy_validated':False,'original_row_unchanged':True,'performance_substitution':False}
                stage = 'append_revision'
                if append_revision(manifest['batch_id'],scope['scope_id'],as_of.isoformat(),payload): result['new_revisions']+=1
            except Exception as exc:
                error={'scope_id':scope['scope_id'],'error':str(exc)[:240]}
                if manifest['batch_id'] == BATCH_ID:
                    error.update(batch_id=BATCH_ID,ticker=scope['ticker'],evidence_session=as_of.isoformat(),stage=stage,exception_type=type(exc).__name__)
                result['errors'].append(error)
    return result
