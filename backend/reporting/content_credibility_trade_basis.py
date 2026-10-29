"""Recheck saved trade reasons; unsupported material claims cannot justify direction."""
import re
from trade_financial_risk import NEGATIVE_FCF_WARNING, LEGACY_NEGATIVE_FCF_WARNING, negative_fcf_value
from trade_catalyst_claims import catalyst_observation_text
from trade_source_contract import source_catalog, reference_is_evidence, catalyst_claim_issues
from trade_catalyst_semantics import _event_issues
from institutional_claim_lineage import institutional_claim_lineage
from trade_source_contract import resolve_reference

_NEWS = re.compile(r"新聞|公告|法說|訂單|調價|漲價|收購|併購|出貨|新產能|(?<![A-Za-z])AI(?![A-Za-z])|MLCC", re.I)
_FCF = re.compile(r"自由現金流|(?<![A-Za-z])FCF(?![A-Za-z])|free cash flow", re.I)


def evaluate_trade_basis(context, data, pipeline, *, snapshot=None):
    result = {"blocking_issues": [], "warnings": [], "checks": []}
    if pipeline != "v4": return result
    parsed = context.get("parsed")
    setup = parsed.get("trade_setup", {}) if isinstance(parsed, dict) else {}
    if not isinstance(setup, dict) or not setup: return result
    def block(key, message):
        result["blocking_issues"].append({"id": key, "message": message})
    flags = setup.get("financial_risk_flags")
    if isinstance(flags, list) and any(flag in flags for flag in (NEGATIVE_FCF_WARNING, LEGACY_NEGATIVE_FCF_WARNING)) and negative_fcf_value(data) is None:
        block("v4_fcf_flag_without_negative_input", "負FCF風險旗標沒有對應負值即期輸入；不得沿用快取財務判斷。")
    catalog = None
    identity = None
    lineage_data = data
    temporal = {}
    if isinstance(snapshot, dict) and (snapshot.get("analysis_evidence") or snapshot.get("rerun_context")):
        from saved_trade_source_identity import saved_trade_source_catalog
        catalog, identity = saved_trade_source_catalog(snapshot)
        lineage_data = identity.get("analysis_input", {})
    lineage = {}
    for text_key, refs_key in (("core_catalyst", "catalyst_source_refs"), ("observed_signal", "observed_source_refs")):
        text = str(setup.get(text_key) or "")
        claim_text = catalyst_observation_text(text) if text_key == "core_catalyst" else text
        refs = setup.get(refs_key); refs = refs if isinstance(refs, list) else []
        if _FCF.search(claim_text):
            block("v4_unverified_fcf_as_catalyst", "即期FCF期間與完整CapEx未核實，不可作為方向或催化依據。")
        if re.search(r"外資|投信|自營商|法人(?!說明會)|大戶", claim_text) and re.search(r"買超|賣超|增持|減持|持股|連續|持續|集中",claim_text) and not refs:
            block("v4_trade_reason_source_missing", "法人方向理由缺少逐項來源引用，不可用未引用彙總或未來等待條件代替。")
        news_refs = [ref for ref in refs if isinstance(ref, str) and ".recent_news.items[" in ref]
        event = setup.get("event_catalyst")
        known_event = isinstance(event, dict) and event.get("status") in {"scheduled", "confirmed", "date_range"} and bool(event.get("date"))
        if _NEWS.search(claim_text) and not news_refs and not known_event:
            block("v4_material_news_without_source", "重大新聞或產業主張缺少對應來源，技術或法人路徑不能替訂單、漲價或併購背書。")
        if refs:
            catalog = catalog if catalog is not None else source_catalog(data)
            if identity:
                from saved_trade_source_identity import evaluation_day, reference_temporal_status
                if identity["status"] != "bound_saved_catalog":
                    block("v4_trade_reason_source_binding_unverified", "保存引用缺少可核對的原始輸入／輸出綁定；不可用今天重新編號的目錄補證。")
                else:
                    for ref in refs:
                        if isinstance(ref, str) and ref not in temporal:
                            temporal[ref] = reference_temporal_status(catalog, ref, as_of=evaluation_day(context))
                            state = temporal[ref]["status"]
                            if state == "stale":
                                block("v4_trade_reason_source_stale", "原引用身分可追溯，但觀測已超過目前有效窗口；不能當最新方向證據。")
                            elif state in {"future_at_source_binding", "future_at_evaluation"}:
                                block("v4_trade_reason_source_future", "引用的觀測日晚於保存來源基準或查核日；不得回填為當時已知。")
                            elif state == "date_unverified":
                                block("v4_trade_reason_source_date_unverified", "保存引用缺少可核對的觀測日或來源基準日。")
            for ref in refs:
                if claim_text.strip() and isinstance(ref,str) and ".institutional_evidence.records[" in ref and ref not in lineage:
                    record = resolve_reference(catalog,ref)
                    if isinstance(record,dict):
                        lineage[ref] = institutional_claim_lineage(lineage_data,record)
                        if lineage[ref]['status'] != 'recomputed':
                            block("v4_institutional_lineage_"+lineage[ref]['status'], "法人方向理由無法由保存的完整逐日分項重算，或與彙總矛盾。")
            if any(not isinstance(ref, str) or not reference_is_evidence(catalog, ref, "catalyst_source_refs") for ref in refs):
                block("v4_trade_reason_source_missing", "方向理由引用的保存資料路徑不存在或不具可用證據。")
            elif catalyst_claim_issues(claim_text, catalog, refs):
                block("v4_trade_reason_scope_mismatch", "方向理由超過保存來源的內容、族群、期間或新聞範圍。")
    event = setup.get("event_catalyst")
    if event:
        catalog = catalog if catalog is not None else source_catalog(data)
        if identity and identity["status"] == "bound_saved_catalog":
            from saved_trade_source_identity import evaluation_day, reference_temporal_status
            for ref in event.get("source_refs", []) if isinstance(event, dict) and isinstance(event.get("source_refs"), list) else []:
                if isinstance(ref, str) and ref not in temporal:
                    temporal[ref] = reference_temporal_status(catalog, ref, as_of=evaluation_day(context))
                    if temporal[ref]["status"] == "stale":
                        block("v4_trade_reason_source_stale", "保存事件日期已過，不可沿用為未來兩週的已排定催化。")
        if _event_issues(event, catalog, True):
            block("v4_event_source_scope_mismatch", "事件日、狀態或來源不符保存事件證據；新聞發布日不可冒充未來事件日。")
    result["checks"] = [{"id": "v4_trade_basis", "status": "blocked" if result["blocking_issues"] else "passed", "message": "方向理由重新核對保存資料；非新聞原文獨立驗證。"}]
    if identity:
        result["checks"].append({"id": "v4_trade_source_identity", "status": "blocked" if identity["status"] != "bound_saved_catalog" else "warning",
            "message": "保存來源身分與目前時效分開查核；身分綁定不代表官方原件或歷史PIT已驗證。",
            "details": {**{key: value for key, value in identity.items() if key != "analysis_input"}, "reference_freshness": temporal}})
    if lineage:
        result['checks'].append({'id':'v4_institutional_claim_lineage','status':'blocked' if any(r['status']!='recomputed' for r in lineage.values()) else 'warning',
                                 'message':'逐日來源重算與官方數值核對；歷史PIT與價格上漲尚未驗證。' if all(r.get('independent_primary_source_verified') for r in lineage.values()) else '逐日來源重算；未獨立核對官方原始來源，不代表價格上漲。', 'details':{'references':lineage}})
        if all(r['status']=='recomputed' for r in lineage.values()) and not all(r.get('independent_primary_source_verified') for r in lineage.values()):
            result['warnings'].append({'id':'v4_institutional_primary_source_unverified','message':'法人觀測可由保存分項重算，但官方原始來源與歷史可用時點未獨立驗證。'})
    if lineage and all(r.get('independent_primary_source_verified') for r in lineage.values()):
        result['warnings'].append({'id':'v4_institutional_pit_and_prediction_unverified','message':'法人逐日數值與事後取得的官方資料一致；原報告時點可取得性與未来報酬仍未驗證。'})
    return result
