"""Separate saved direction, evidence gaps, quality and unfinished independent review."""
import math
from datetime import date
from report_source_admission import admission_reason_label


def _map(value):return value if isinstance(value,dict) else {}

def _official(value):return _map(_map(value).get("latest_official_observation"))

def compare_institutional_versions(before,after):
    """Compare saved excerpts, not proof that a hash or newer version is correct."""
    base={"status":"unverified","impact":"claim_recheck_pending",
          "raw_bodies_independently_verified":False,"changed_components":[]}
    before,after=_official(before),_official(after)
    for key in ("date","ticker","market","unit"):
        if not before.get(key) or not after.get(key):return base
    try:
        first,last=date.fromisoformat(before["date"]),date.fromisoformat(after["date"])
    except (ValueError,TypeError):return base
    if any(before[key]!=after[key] for key in ("ticker","market","unit")) or before["unit"]!="shares":
        return {**base,"status":"scope_mismatch"}
    rb,ra=_map(before.get("raw_evidence")),_map(after.get("raw_evidence"))
    receipt={"analyzed_date":before["date"],"current_snapshot_date":after["date"],
             "analyzed_retrieved_at":rb.get("retrieved_at"),"snapshot_retrieved_at":ra.get("retrieved_at"),
             "analyzed_sha256":rb.get("raw_response_sha256"),"snapshot_sha256":ra.get("raw_response_sha256")}
    if last!=first:return {**base,**receipt,"status":"newer_session" if last>first else "older_session"}
    changes=[]
    for category in ("foreign","investment_trust","dealer"):
        a,b=_map(before.get("categories")).get(category),_map(after.get("categories")).get(category)
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (a,b)):return {**base,**receipt}
        if a!=b:changes.append({"population":category,"before":a,"after":b,"delta_shares":b-a,
                              "sign_changed":(a<0)!=(b<0) if a!=0 and b!=0 else None})
    hashes=[rb.get("raw_response_sha256"),ra.get("raw_response_sha256")]
    complete=all(isinstance(h,str) and len(h)==64 and all(c in "0123456789abcdef" for c in h) for h in hashes)
    if not complete:return {**base,**receipt,"changed_components":changes}
    status=("excerpt_conflict_same_receipt" if hashes[0]==hashes[1] else "revised_same_session") if changes else (
        "saved_receipt_unchanged" if hashes[0]==hashes[1] else "version_changed_values_equal")
    return {**base,**receipt,"status":status,"changed_components":changes,
            "impact":"requires_claim_recheck;materiality_not_established" if changes else "latest_official_version_not_checked"}


def explain_report_decision(snapshot,latest=None,*,moment=None):
    snapshot=_map(snapshot);latest=_map(latest);context=_map(snapshot.get("rerun_context"))
    outputs=_map(context.get("structured_outputs"));setup=_map(outputs.get("24",outputs.get(24))) or _map(_map(context.get("parsed")).get("trade_setup"))
    pipeline=snapshot.get("pipeline") or snapshot.get("pipeline_id")
    direction=setup.get("trade_direction") if pipeline=="v4" else None
    mode_recommendation=_map(_map(outputs.get("19",outputs.get(19))).get("recommendation")).get("建議") if pipeline=="v3" else None
    direction_label={"Neutral":"Neutral：目前非看多交易構想，可保留觀察",
                     "Long":"Long構想：仍需獨立查核來源與交易條件",
                     "Short":"Short構想：不屬於短期看多候選"}.get(direction,"方向尚未確認／此模式非兩週交易判定")
    if pipeline=="v3" and mode_recommendation:
        direction_label="模式C原建議："+str(mode_recommendation)+"；不是兩週Long／Short交易訊號"
    credibility=_map(latest.get("content_credibility")) or _map(snapshot.get("content_credibility"))
    quality=credibility.get("status") or "unknown"
    gate=_map(latest.get("evidence_exit_gate")) or _map(snapshot.get("evidence_exit_gate"))
    source=_map(gate.get("source_admission"))
    blockers=list(dict.fromkeys(source.get("blockers") or []));warnings=list(dict.fromkeys(source.get("source_warnings") or []))
    from technical_reasoning import technical_reasoning_checks, histogram_data_from_snapshot
    text=_map(context.get("analyses")).get("22", _map(context.get("analyses")).get(22, ""))
    checks=technical_reasoning_checks(text,histogram_data_from_snapshot(snapshot))
    reasoning_failed=any(c["status"]=="mismatch" for c in checks)
    from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError
    publication_blocked=False
    projection={**snapshot, **{key:latest[key] for key in ("content_credibility","evidence_exit_gate","report_conformance","report_lint","final_audit","blocking_issues") if key in latest}}
    try:assert_report_publishable(projection, observe=False)
    except ReportPublicationBlockedError:publication_blocked=True
    withdrawn=publication_blocked or reasoning_failed or quality in {"blocked","failed","rejected"} or gate.get("verdict") in {"rejected","blocked"}
    reasons=[]
    if reasoning_failed:
        for check in checks:
            if check["status"]=="mismatch":
                reasons.append({"kind":"contradictory_reasoning","code":check.get("claim_type") or "macd_histogram_magnitude_mismatch","message":"技術敘述與同一原分析輸入窗數據矛盾；保留原文，需修正後再作候選依據"})
    if withdrawn:reasons.append({"kind":"quality_withdrawal","code":"saved_or_current_quality_blocked","message":"報告有明確品質阻擋；保留原件，暫停作候選依據"})
    for code in blockers:reasons.append({"kind":"hard_evidence_gap","code":code,"message":admission_reason_label(code),"next_evidence":"補齊該來源、口徑或合法價格的可核驗原件，再重新查核"})
    for code in warnings:reasons.append({"kind":"source_review_pending","code":code,"message":admission_reason_label(code),"next_evidence":"逐項核對來源日期、版本及引用；警示不自動等於方向錯誤"})
    for issue in credibility.get("blocking_issues") or []:
        if isinstance(issue,dict):
            reasons.append({"kind":"quality_issue","code":issue.get("id") or "reported_quality_issue",
                            "message":issue.get("message") or "品質主張仍需修正", "next_evidence":"修正所指主張並重新完成相同品質查核；保留原文"})
    next_evidence={
        "v4_raw_fcf_period_unverified":"核對FCF所屬財期、幣別、合併口徑與完整CapEx原件；不能只由負值推定成因",
        "v4_volume_scope_mismatch":"取得同日期、同涵蓋交易範圍的成交量；股單位相同仍不可跨來源混算法人占比或量比",
        "v4_institutional_primary_source_unverified":"重播對應日期／分類的官方raw，核對取得版本及與原分析引用的差異",
    }
    for issue in credibility.get("warnings") or []:
        if isinstance(issue,dict):
            code=issue.get("id") or "reported_warning"
            reasons.append({"kind":"reported_warning","code":code,"message":issue.get("message") or "報告警示待核",
                            "next_evidence":next_evidence.get(code,"按所指來源核對日期、期間、單位與原件；不以模型同意補證"),
                            "alone_blocks_observation":False})
    if quality in {"warning","caution"}:reasons.append({"kind":"general_warning","code":"quality_warning","message":"一般品質警示；不是單獨否決觀察名單的條件"})
    if direction=="Neutral":reasons.append({"kind":"direction","code":"neutral_not_long","message":"Neutral是原方向，不代表所有資料取得失敗"})
    completion=_map(setup.get("source_assessment"))
    if completion.get("origin")=="local_deterministic_fallback":
        reasons.append({"kind":"incomplete_analysis","code":"local_fallback","message":"本機備援保留觀測，但模型結論未完成；需完成分析才能評估方向"})
    analyzed=_map(_map(_map(snapshot.get("analysis_evidence")).get("sections")).get("analysis_input")).get("data")
    analyzed=_map(analyzed);data=_map(snapshot.get("data"))
    version=compare_institutional_versions(analyzed.get("institutional_trading"),data.get("institutional_trading"))
    if version["status"] in {"revised_same_session","excerpt_conflict_same_receipt"}:
        reasons.append({"kind":"source_revision","code":version["status"],"message":"同日法人數值版本不同；須重核引用與結論影響，不能直接改寫原分析"})
    elif version["status"]=="older_session":
        reasons.append({"kind":"source_staleness","code":"older_source_session","message":"當前資料快照法人日期早於原分析輸入；不能當最新版本"})
    source_state = _source_evidence_state(snapshot, latest, source, moment)
    return {"source_evidence_state":source_state,"schema_version":"candidate_decision_explanation.v1","direction":direction,
            "direction_label":direction_label,"mode_recommendation":mode_recommendation,"quality_status":quality,
            "quality_label":"明確品質阻擋" if withdrawn else "可保留研究觀察；來源未准入，非可執行候選" if source.get("source_eligible") is False else "一般警示，可觀察但查核未完成" if quality in {"warning","caution"} else "品質狀態仍須核對",
            "withdrawn":withdrawn,"reasons":reasons,"technical_reasoning_checks":checks,"source_version_comparison":version,
            "source_dates":{"price":_map(data.get("daily_market_data")).get("as_of"),"institutional":_map(data.get("institutional_trading")).get("latest_date")},
            "analysis_generated_at":snapshot.get("conclusion_generated_at") or snapshot.get("generated_at"),
            "snapshot_refreshed_at":snapshot.get("snapshot_refreshed_at"),
            "requires_rerun":bool(snapshot.get("refreshed_without_analysis_rerun") or _map(latest.get("decision_freshness")).get("requires_rerun")),
            "qualification_evaluation_status":"not_independently_evaluated",
            "independent_factual_correctness":"not_established_by_saved_approval_hash_or_model_agreement",
            "observation_allowed":not withdrawn,"actionable":False,
            "performance_context":"validated strategy counts are aggregate context;not a per-stock observation veto"}


def summarize_report_decisions(observations,*,requested_count):
    explanations=[row["decision_explanation"] for row in observations.values()
                  if isinstance(row,dict) and row.get("status")=="available" and isinstance(row.get("decision_explanation"),dict)]
    return {"scope":"at_most_20_reports_on_returned_screener_page;not_whole_market",
            "loaded_report_count":len(explanations),"not_read_count":max(0,requested_count-len(explanations)),
            "direction_counts":{key:sum((e.get("direction") or "not_a_v4_direction")==key for e in explanations) for key in ("Long","Short","Neutral","not_a_v4_direction")},
            "research_observation_count":sum(e.get("observation_allowed") is True for e in explanations),
            "quality_withdrawal_count":sum(e.get("withdrawn") is True for e in explanations),
            "source_pending_count":sum(any(r["kind"] in {"hard_evidence_gap","source_review_pending","source_revision"} for r in e["reasons"]) for e in explanations),
            "actionable_candidate_count":None,"actionable_evaluation_status":"not_independently_evaluated",
            "interpretation":"方向、觀察、缺證與品質是不同軸；計數可重疊，警示及validated=0不單獨否決觀察"}


def _source_evidence_state(snapshot,latest,source,moment):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from market_evidence_policy import session_cache_scope
    from candidate_report_identity import bound_report_ticker
    moment=moment or datetime.now(ZoneInfo('Asia/Taipei'))
    ticker=bound_report_ticker(snapshot, metadata=latest)
    expected,phase=session_cache_scope(moment, ticker=ticker) if ticker else (None,'unknown')
    data=_map(snapshot.get('data'));institution=_map(data.get('institutional_trading'))
    observed=institution.get('latest_date')
    saved=_map(_map(snapshot.get('evidence_exit_gate')).get('source_admission'))
    state='latest_session_missing_from_snapshot' if expected and observed and observed<expected else 'latest_session_in_snapshot' if expected and observed==expected else 'unknown'
    return {'source_eligible':source.get('source_eligible'),'saved_gate_source_eligible':saved.get('source_eligible'),
            'basis':'current_readonly_projection' if latest.get('_quality_projection_basis')=='current_rules_readonly' or _map(latest.get('evidence_exit_gate_projection')).get('status')=='projected' else 'latest_metadata_basis_unverified' if _map(latest.get('evidence_exit_gate')).get('source_admission') else 'saved_gate_only',
            'expected_completed_session':expected,'evaluation_phase':phase,'institutional_observed_date':observed,
            'ticker':ticker,'calendar_identity_status':'bound' if ticker else 'unconfirmed',
            'institutional_snapshot_state':state,'snapshot_stale_flag':institution.get('stale'),
            'external_newer_evidence_checked':False,'historical_available_at_verified':False,
            'interpretation':'研究觀察與來源准入分列；新取得資料不倒填為原分析當時已知，也不自動重跑結論'}
