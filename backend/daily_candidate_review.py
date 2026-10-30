"""Read-only explanations; dates and saved quality never become execution approval."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from two_week_market_eligibility import observation_readiness
from report_pipeline_identity import resolve_report_pipeline_id


def quality_context(item):
    choices = [safe_mapping_dict(item.get("quality_funnel")) or {}]
    choices += [safe_mapping_dict(t.get("quality_funnel")) or {} for t in safe_dict_list(item.get("triggers"))]
    known = [q for q in choices if safe_text(q.get("outcome")).strip().lower() in {"reject", "gray", "pass"}]
    priority = {"reject": 0, "gray": 1, "pass": 2}
    return min(known, key=lambda q: priority[safe_text(q.get("outcome")).strip().lower()]) if known else {}


def _date(value):
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def evidence_context(item, *, moment):
    metrics = safe_mapping_dict(item.get("metrics")) or {}
    price = _date(metrics.get("price_observation_date"))
    flow = _date(metrics.get("flow_observation_date"))
    readiness = observation_readiness(price_date=price, institutional_date=flow, moment=moment, ticker=item.get("ticker"))
    quality = quality_context(item)
    missing = safe_dict_list(quality.get("missing_rules"))
    notes = [readiness["reason"]]
    outcome = safe_text(quality.get("outcome")).strip().lower() or "unknown"
    if outcome == "gray":
        labels = [safe_text(r.get("label")) for r in missing if safe_text(r.get("label"))]
        notes.append("保存的品質漏斗為灰區" + ("：缺少" + "、".join(labels) if labels else "：指標不完整"))
    elif outcome == "unknown":
        notes.append("品質漏斗結果未保存或無法判讀")
    elif outcome == "pass":
        notes.append("保存的品質漏斗通過；不代表當前報告已核准或具有上漲機率")
    latest = safe_mapping_dict(item.get("latest_report")) or {}
    freshness = safe_mapping_dict(latest.get("decision_freshness")) or {}
    if not latest:
        notes.append("尚無可對應的最新報告")
    elif freshness.get("requires_rerun") is True:
        notes.append("保存的報告提示需重跑；本次只顯示原因")
    notes.append("兩週催化事件、進場／失效條件與可比成本仍需核對；本頁不補驗為通過")
    return {**readiness, "screen_date": _date(item.get("screen_date")),
            "screen_date_basis": "screen_date is scan bookkeeping;not an inferred source observation date",
            "volume_observation_date": _date(metrics.get("volume_observation_date")),
            "price_source": safe_text(metrics.get("price_source")).strip() or None,
            "flow_source": safe_text(metrics.get("flow_source")).strip() or None,
            "report_filename": safe_text(latest.get("filename")).strip() or None,
            "report_generated_at": safe_text(latest.get("date")).strip() or None,
            "saved_quality_outcome": outcome,
            "quality_basis": "saved screener/trigger quality;not independent current approval",
            "missing_quality_indicators": [safe_text(r.get("label")) for r in missing if safe_text(r.get("label"))],
            "readable_reasons": notes, "validation_scope": "saved screener fields only;source contents not independently verified"}


def build_candidate_review(items, candidates, withdrawn_reports, screener, performance, *, moment=None):
    moment = moment or datetime.now(ZoneInfo("Asia/Taipei"))
    selected = {c["ticker"] for c in candidates}
    blocked = {r.get("ticker"):r for r in withdrawn_reports if resolve_report_pipeline_id(r.get("filename") or "", stored_pipeline=r.get("pipeline_id")) == "v4"}
    partition = {"displayed_research":0, "quality_blocked":0, "saved_funnel_rejected":0, "outside_display_limit":0}
    excluded = []
    for item in items:
        ticker = safe_text(item.get("ticker")).strip()
        if ticker in blocked:
            bucket = "quality_blocked"
            row = blocked[ticker]
            credibility = safe_mapping_dict(row.get("content_credibility")) or {}
            reasons = [safe_text(x.get("message")) for x in safe_dict_list(credibility.get("blocking_issues"))]
            reasons = reasons or ["當前報告品質阻擋，已撤回研究候選"]
        elif safe_text(quality_context(item).get("outcome")).strip().lower() == "reject":
            bucket = "saved_funnel_rejected"
            reasons = ["保存的品質漏斗拒絕；本次未改寫歷史品質"]
        elif ticker in selected:
            bucket = "displayed_research"
            reasons = []
        else:
            bucket = "outside_display_limit"
            reasons = ["超過本頁五筆研究顯示上限；不表示股票已被基本面或方向判定淘汰"]
        partition[bucket] += 1
        if bucket != "displayed_research":
            excluded.append({"ticker":ticker,"state":bucket,"reasons":reasons,
                             "evidence":evidence_context(item,moment=moment),"research_only":True,"actionable":False})
    for candidate in candidates:
        item = next((i for i in items if safe_text(i.get("ticker")).strip() == candidate["ticker"]), {})
        candidate["evidence"] = evidence_context(item,moment=moment)
        candidate["selection_basis"] = "research display from returned screener page;not calibrated upside ranking"
    population = safe_mapping_dict(performance.get("population")) or {}
    diagnostics = safe_mapping_dict(population.get("net_result_diagnostics")) or {}
    primary = safe_mapping_dict(diagnostics.get("primary_nonoverlapping_slots")) or {}
    pagination = safe_mapping_dict(screener.get("pagination")) or {}
    return {"schema_version":"daily_candidate_review.v1","scope":"returned_screener_page",
            "returned_count":len(items),"screener_total_if_reported":pagination.get("total"),
            "partition":partition,"excluded_items":excluded,
            "display_order":"uncalibrated research display;no upward probability",
            "withdrawn_report_scope":"all indexed latest v4 report quality, separately available in withdrawn_reports",
            "performance_maturity_context":{"scope":"all indexed nonoverlapping10-session decisions;not per displayed candidate",
                "as_of":population.get("as_of"),"partition":primary.get("partition"),
                "status":"available" if primary else "unavailable"},
            "actionable_candidate_count":None,
            "actionable_evaluation_status":"not_independently_evaluated",
            "actionable_count_basis":"compatibility placeholder;not an evaluated count of rejected stocks",
            "research_only":True,
            "interpretation":"掃描日期、報告生成時間與行情／法人觀測日期分開。未知資料不補零；取樣名單不代表全市場。"}
