"""Taiwan equity analysis levels are not silently rounded into executable quotes."""
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
from trade_price_inputs import parse_price_range
from trade_execution_contract import evaluate_trade_execution

SOURCE = "https://www.twse.com.tw/downloads/zh/trading/introduce/introduce004.pdf"


def equity_tick(price):
    value = Decimal(str(price))
    if not value.is_finite() or value <= 0: return None
    for ceiling, tick in ((10, ".01"), (50, ".05"), (100, ".1"), (500, ".5"), (1000, "1")):
        if value < ceiling: return Decimal(tick)
    return Decimal("5")


def grid_assessment(data, setup):
    result = {"source": SOURCE, "scope": "TWSE equity limit-order price grid; analysis levels unchanged", "status": "unverified", "invalid_levels": [], "actionable": False, "checked_levels": [], "instrument_type": data.get("quote_type"), "instrument_type_source": data.get("instrument_type_source"), "reason": "instrument_type_or_market_not_verified"}
    if not str(data.get("ticker") or "").endswith(".TW") or data.get("quote_type") != "EQUITY": return result
    result["reason"] = "equity_analysis_grid_checked;not_order_approval"
    checked = []
    for field in ("entry_zone", "target_price", "stop_loss"):
        numbers = parse_price_range(setup.get(field))
        if not numbers: continue
        for number in sorted(set(numbers)):
            try:
                tick = equity_tick(number)
                legal = bool(tick and Decimal(str(number)) % tick == 0)
            except (InvalidOperation, ValueError):
                tick, legal = None, False
            item = {"field": field, "analysis_price": number, "tick": str(tick) if tick else None, "legal_order_quote": legal}
            checked.append(item)
            if not legal: result["invalid_levels"].append(item)
    result["checked_levels"] = checked
    result["status"] = "off_grid_analysis_levels" if result["invalid_levels"] else "grid_aligned_analysis_levels" if checked else "no_trade_prices"
    return result


def proposed_order_contract(data, setup):
    """A separately labeled review proposal; never rewrite source plan or SMA."""
    result={"status":"unavailable","approved":False,"actionable":False,"analysis_prices_unchanged":True,
            "price_basis_verified":False,"fill_verified":False,"source":SOURCE}
    if grid_assessment(data,setup)["status"]=="unverified":
        return dict(result,reason="instrument_type_or_market_not_verified")
    direction=setup.get("trade_direction")
    if direction not in {"Long","Short"}:return dict(result,reason="no_executable_direction")
    converted={};changes=[]
    for field in ("entry_zone","target_price","stop_loss"):
        numbers=parse_price_range(setup.get(field))
        if not numbers:return dict(result,reason="missing_or_ambiguous_analysis_level")
        # Worst-case review: long entry up/target down/stop down; short converse.
        upward=(field=="entry_zone") if direction=="Long" else (field!="entry_zone")
        rounding=ROUND_CEILING if upward else ROUND_FLOOR
        values=[]
        for number in sorted(set(numbers)):
            original=Decimal(str(number));tick=equity_tick(number)
            value=(original/tick).to_integral_value(rounding=rounding)*tick
            if value<=0 or value % equity_tick(value)!=0:return dict(result,reason="conversion_not_on_legal_grid")
            values.append(float(value))
            changes.append({"field":field,"analysis_price":number,"proposed_price":float(value),"delta":float(value-original),
                            "tick":str(tick),"direction":direction,"rule":"ceil_to_equity_grid" if upward else "floor_to_equity_grid"})
        converted[field]="-".join(f"{value:g}" for value in sorted(set(values)))
    evaluated=evaluate_trade_execution(direction=direction,**converted,transaction_cost=setup.get("transaction_cost"))
    return {**result,"status":"review_proposal_requires_explicit_acceptance","proposed_levels":converted,"conversions":changes,
            "conversion_policy":"adverse_entry;conservative_target;wider_stop;recalculate_risk_after_conversion:v1",
            "recomputed_execution":evaluated["details"],"issues":evaluated["issues"],
            "limitation":"合法格點只驗價位；未核對價格基準、觸發、成交、成本及來源，不自動使策略有效。"}


def execution_evidence(data, setup):
    evaluated = evaluate_trade_execution(direction=setup.get("trade_direction"), entry_zone=setup.get("entry_zone"), target_price=setup.get("target_price"), stop_loss=setup.get("stop_loss"), transaction_cost=setup.get("transaction_cost"))
    return {"price_grid": grid_assessment(data, setup), "execution": evaluated["details"], "issues": evaluated["issues"], "order_review_proposal":proposed_order_contract(data,setup),"actionable": False}


def execution_rows(data, setup):
    evidence = execution_evidence(data, setup)
    grid, details = evidence["price_grid"], evidence["execution"]
    bad = grid["invalid_levels"]
    grid_text = "；".join(f"{item['field']} {item['analysis_price']:g} 非 {item['tick']} 元合法跳動價" for item in bad) if bad else "分析價符合價格格點；仍未確認進場觸發與成交" if grid["status"] == "grid_aligned_analysis_levels" else "未確認股票類型或沒有可執行價位"
    ratio = details.get("worst_case_risk_reward")
    net = details.get("net_risk_reward")
    proposal=evidence["order_review_proposal"]
    proposed=proposal.get("proposed_levels")
    conversions="；".join(f"{x['analysis_price']:g}→{x['proposed_price']:g}（格點{x['tick']}，{'向上' if x['rule'].startswith('ceil') else '向下'}）" for x in proposal.get("conversions",[]) if x["analysis_price"]!=x["proposed_price"])
    conversions=conversions or "參考價已在合法格點，未改值"
    proposal_text=("待明確接受的換算提案：" + "; ".join(f"{dict(entry_zone='進場區間',target_price='目標',stop_loss='停損')[k]}={v}" for k,v in proposed.items()) + "; 原值換算："+conversions+"；進場朝不利方向換算、目標保守、停損擴大；換算後條件毛風險報酬=" + str(proposal["recomputed_execution"].get("worst_case_risk_reward")) + "；原 SMA／分析價不變；不自動核准策略或下單，成本、價格基準及成交仍待查驗") if proposed else "無換算提案：" + proposal.get("reason","unavailable")
    return [
        {"label": "價格跳動單位", "value": grid_text + "；不自動四捨五入或下單"},
        {"label": "條件毛風險報酬", "value": f"{ratio:.3f}（最差進場端點；假設能成交及按停損退出，尚未扣成本）" if ratio is not None else "未能驗算／不交易"},
        {"label": "來回成本與淨風險報酬", "value": f"已提供每股成本 {details.get('transaction_cost')}；條件淨風險報酬 {net:.3f}，非成交保證" if net is not None else "未驗證；手續費、適用交易稅及滑價未提供，不當作零成本，也不宣稱淨報酬"},
        {"label":"可執行價位換算審閱", "value":proposal_text},
    ]
