"""Progress counts are unique approved scopes, never accumulated versions."""
import sqlite3
import legacy_evidence_revisions as revisions
import two_week_market_eligibility


def test_progress_separates_terminal_pending_and_mature_unscored(monkeypatch,tmp_path):
    path=tmp_path/'isolated.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE trade_evidence_revision_batches_v1(batch_id TEXT,active INTEGER)')
        conn.execute('INSERT INTO trade_evidence_revision_batches_v1 VALUES (?,?)',('batch',1))
        conn.execute('CREATE TABLE trade_evidence_revisions_v1(batch_id TEXT,scope_id TEXT,state TEXT)')
        conn.executemany('INSERT INTO trade_evidence_revisions_v1 VALUES (?,?,?)',[('batch','done','no_trade'),('batch','done','no_trade'),('batch','gap','insufficient_data')])
    monkeypatch.setattr(revisions.trade_backtest_store,'_path',lambda:path)
    monkeypatch.setattr(revisions,'active_manifests',lambda:[{'batch_id':'batch','rows':[{'scope_id':'done','maturity_date':'2026-10-01'},{'scope_id':'gap','maturity_date':'2026-10-02'},{'scope_id':'future','maturity_date':'2026-10-05'}]}])
    monkeypatch.setattr(two_week_market_eligibility,'completed_session',lambda moment, *, ticker=None:'2026-10-02')
    result=revisions.revision_summary()
    assert result['revisions']==3 and result['approved_scope_count']==3
    assert result['terminal_scope_count']==1 and result['remaining_scope_count']==2
    assert result['awaiting_maturity_count']==1 and result['mature_unscored_scope_count']==1
    assert result['terminal_scope_count']+result['awaiting_maturity_count']+result['mature_unscored_scope_count']==3
    assert result['performance_substitution'] is False
    monkeypatch.setattr(two_week_market_eligibility,'completed_session',lambda moment, *, ticker=None:None)
    unknown=revisions.revision_summary()
    assert unknown['awaiting_maturity_count'] is None and unknown['mature_unscored_scope_count'] is None
