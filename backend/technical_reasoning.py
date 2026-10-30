"""Bounded current histogram assertions; no forecast, paraphrase or direction scoring."""
import math
import re
from datetime import date
from short_term_technical_indicators import calculate_technical_indicators


def _verification_scope(data):
    from market_session_admission import assess_daily_session_integrity
    data = data if isinstance(data, dict) else {}
    daily = data.get('daily_market_data')
    integrity = assess_daily_session_integrity(daily, ticker=data.get('ticker'))
    return {'verification_scope': 'saved_window_arithmetic',
            'session_integrity': integrity,
            'independent_primary_source_verified': False,
            'historical_point_in_time_verified': False}


def comparison_from_data(data):
    daily=data.get("daily_market_data", {})
    technical=data.get("technical_indicators", {})
    if not isinstance(daily,dict) or not isinstance(technical,dict):return None
    bars=daily.get("bars")
    if not isinstance(bars,list) or len(bars)<35 or not daily.get("source"):return None
    basis=daily.get("price_adjustment_basis")
    if not basis or basis in {"unknown","unavailable"} or basis!=technical.get("price_adjustment_basis"):return None
    if daily.get("as_of")!=technical.get("as_of") or daily.get("source")!=technical.get("source"):return None
    try:
        dates=[date.fromisoformat(b["date"]) for b in bars]
        if any(a>=b for a,b in zip(dates,dates[1:])) or dates[-1].isoformat()!=daily.get("as_of"):return None
        if any(not isinstance(b,dict) or any(type(b.get(k)) not in (int,float) or not math.isfinite(b[k]) for k in ("close","volume")) for b in bars):return None
        recalculated=calculate_technical_indicators(daily)
        observed=technical.get("macd_histogram")
        if type(observed) not in (int,float) or not math.isfinite(observed) or abs(observed-recalculated["macd_histogram"])>1e-7:return None
        if technical.get("input_window",{}).get("bars_sha256")!=recalculated["input_window"]["bars_sha256"]:return None
        return recalculated.get("macd_histogram_comparison")
    except (ValueError,TypeError,KeyError,OverflowError):return None


def histogram_reasoning_checks(text,data):
    checks=[];comparison=None;scope=_verification_scope(data)
    for number,line in enumerate(str(text).splitlines(),1):
        # Fixed ledger and hypothetical/negated/history claims are outside scope.
        if not re.search(r"MACD",line,re.I) or not re.search(r"柱狀體|柱體|負柱|正柱|histogram",line,re.I):continue
        for clause in re.split(r"[。；;]",line):
            if not re.search(r"MACD",clause,re.I) or not re.search(r"柱狀體|柱體|負柱|正柱|histogram",clause,re.I):continue
            if re.search(r"如果|若|假設|預估|未來|等待|情境|劇本|需帶量|需站|必須|才能|曾經|過去|並非|不是|不能|不代表|未擴|未收",clause):continue
            predicate=re.search(r"擴張|擴大|收斂|縮小",clause)
            if not predicate:continue
            if re.search(r"(?:未|不|沒)[^，,。；;]{0,8}$",clause[:predicate.start()]):continue
            histogram=re.search(r"柱狀體|柱體|負柱|正柱|histogram",clause,re.I)
            ambiguous=histogram is not None and bool(re.search(r"動能|上攻|多方|空方",clause[histogram.end():predicate.start()]))
            if comparison is None:comparison=comparison_from_data(data)
            claimed="expansion" if predicate.group() in {"擴張","擴大"} else "contraction"
            status="unverifiable"
            if comparison:
                dates=re.findall(r"20\d{2}-\d{2}-\d{2}",clause)
                if any(d not in {comparison["observed_date"],comparison["previous_date"]} for d in dates):continue
                actual=comparison["relation"]
                status="unverifiable" if ambiguous else "verified" if actual.endswith("_"+claimed) else "mismatch"
            arithmetic_status = status
            if status == 'verified' and not scope['session_integrity']['eligible']:
                status = 'unverifiable'
            checks.append({"line_number":number,"raw_text":clause,"claimed_change":claimed,
                           "status":status, "arithmetic_status": arithmetic_status, "comparison":comparison, **scope,
                           "reason":"technical_session_integrity_unverified" if arithmetic_status == 'verified' and not scope['session_integrity']['eligible'] else "histogram_assertion_scope_ambiguous" if ambiguous else "histogram_magnitude_relation" if comparison else "histogram_two_session_evidence_missing"})
    return checks


def histogram_data_from_snapshot(snapshot):
    evidence=snapshot.get("analysis_evidence")
    evidence=evidence if isinstance(evidence,dict) else {}
    sections=evidence.get("sections")
    sections=sections if isinstance(sections,dict) else {}
    entry=sections.get("analysis_input")
    entry=entry if isinstance(entry,dict) else {}
    original=entry.get("data")
    if isinstance(original,dict):return original
    return {} if snapshot.get("refreshed_without_analysis_rerun") else snapshot.get("data",{})


def _sma_input(data):
    """Recompute from one identified frozen window; do not mix current prices."""
    daily=data.get('daily_market_data',{}) if isinstance(data,dict) else {}
    technical=data.get('technical_indicators',{}) if isinstance(data,dict) else {}
    try:
        bars=daily['bars'];dates=[date.fromisoformat(b['date']) for b in bars]
        if not bars or any(a>=b for a,b in zip(dates,dates[1:])) or dates[-1].isoformat()!=daily.get('as_of'):return None
        if not daily.get('source') or daily['source']!=technical.get('source') or daily.get('as_of')!=technical.get('as_of'):return None
        basis=daily.get('price_adjustment_basis')
        if not basis or basis in {'unknown','unavailable'} or basis!=technical.get('price_adjustment_basis'):return None
        if any(type(b.get(k)) not in (int,float) or not math.isfinite(b[k]) for b in bars for k in ('close','volume')):return None
        calculated=calculate_technical_indicators(daily)
        if technical.get('input_window',{}).get('bars_sha256')!=calculated['input_window']['bars_sha256']:return None
        return {'close':bars[-1]['close'],'calculated':calculated,'recorded':technical,
                'observed_date':daily['as_of'],'source':daily['source'],'price_adjustment_basis':basis,
                'bars_sha256':calculated['input_window']['bars_sha256']}
    except (KeyError,TypeError,ValueError,OverflowError,IndexError):return None


def _named_sma_periods(text):
    periods={int(match[1]) for match in re.finditer(r'SMA[_ ]?(5|10|20|60)\b',text,re.I)}
    for match in re.finditer(r'(?<![\d-])((?:5|10|20|60)\s*(?:日)?(?:\s*[/、,與及]\s*(?:5|10|20|60)\s*(?:日)?)+)\s*(?:均線|日線|日均線|日)|(?<![\d-])(5|10|20|60)\s*日(?:均)?線',text):
        periods.update(int(p) for p in re.findall(r'5|10|20|60',match[1] or match[2]))
    return periods


def sma_reasoning_checks(text,data):
    """Check explicit scoped SMA relations; ambiguous period scope stays unknown."""
    checks=[];inputs=None;scope=_verification_scope(data)
    for number,line in enumerate(str(text).splitlines(),1):
        for clause in re.split(r'[。；;]|[，,]?(?:但|惟|然而)',line):
            if re.search(r'若|如果|假設|預估|未來|等待|情境|劇本|需帶量|需站|必須|才能|曾經|過去|並非|不是|不代表|未站|未突破|未高於|不高於|未低於|不低於|尚未',clause):continue
            statement=re.split(r'[（(]來源|來源[:：]',clause)[0]
            periods=_named_sma_periods(statement)
            ordering='多頭排列' in statement and not re.search(r'未達|不符合|未形成|未呈|非完整|非多頭|(?:非|未|不|無)[^。；]{0,12}多頭排列',statement)
            # Price comparisons stop before a separate ordering/qualifying claim.
            price_statement=re.split(r'[，,]?(?:且|同時)|[，,](?:相較|其餘|整體|此外|另外|顯示)',statement)[0]
            subject=re.search(r'收盤價|股價|收盤',price_statement)
            price_statement=price_statement[subject.start():] if subject else ''
            price_periods=_named_sma_periods(price_statement)
            above=bool(re.search(r'(?:收盤價|股價|收盤).{0,65}(?:站上|站穩|高於|位於)',price_statement)) and bool(re.search(r'站上|高於|之上',price_statement))
            below=bool(re.search(r'(?:收盤價|股價|收盤).{0,65}(?:低於|位於)',price_statement)) and bool(re.search(r'低於|之下',price_statement))
            order_periods=None
            if ordering:
                # Associate the period list nearest the ordering predicate;
                # a separate mention of SMA60 must not widen 5/10/20 scope.
                pattern=r'((?:5|10|20|60)\s*(?:日)?(?:\s*[/、,與及]\s*(?:5|10|20|60)\s*(?:日)?)+)\s*(?:日|均線|日均線|日線)?[^。；，,]{0,10}多頭排列'
                explicit=list(re.finditer(pattern,statement))
                chain=list(re.finditer(r'(?:SMA[_ ]?(?:5|10|20|60)(?:\s*[（(][^()（）]{0,24}[）)])?\s*>\s*)+SMA[_ ]?(?:5|10|20|60)(?:\s*[（(][^()（）]{0,24}[）)])?',statement,re.I))
                if explicit:order_periods=sorted(_named_sma_periods(explicit[-1][1]+'日均線'))
                elif chain and len(statement[chain[-1].end():statement.index('多頭排列')])<25:
                    order_periods=sorted(_named_sma_periods(chain[-1][0]))
                elif '短中長期' in statement and periods=={5,10,20,60}:order_periods=sorted(periods)
            predicates=[]
            if price_periods and above!=below:predicates.append(('close_above_sma' if above else 'close_below_sma',sorted(price_periods)))
            if ordering and len(periods)>=2:predicates.append(('bullish_sma_order',order_periods))
            if not predicates:continue
            if inputs is None:inputs=_sma_input(data)
            dates=re.findall(r'20\d{2}-\d{2}-\d{2}',statement)
            if inputs and any(d!=inputs['observed_date'] for d in dates):continue
            for claim,ps in predicates:
                values={p:inputs['calculated'].get('sma_'+str(p)) for p in ps or []} if inputs else {}
                valid=inputs is not None and ps is not None and bool(values) and all(type(v) in (int,float) and math.isfinite(v) and type(inputs['recorded'].get('sma_'+str(p))) in (int,float) and abs(inputs['recorded']['sma_'+str(p)]-v)<=1e-7 for p,v in values.items())
                verified=valid and (all(values[a]>values[b] for a,b in zip(ps,ps[1:])) if claim=='bullish_sma_order' else all(inputs['close']>v if claim=='close_above_sma' else inputs['close']<v for v in values.values()))
                checks.append({'line_number':number,'raw_text':clause,'claim_type':claim,
                               'status':'unverifiable' if not valid or (verified and not scope['session_integrity']['eligible']) else 'verified' if verified else 'mismatch',
                               'arithmetic_status':'unverifiable' if not valid else 'verified' if verified else 'mismatch',
                               **scope,
                               'comparison':{'periods':ps,'sma_values':values,'observed_date':inputs['observed_date'] if inputs else None,
                                             'close':inputs['close'] if inputs else None,'input_basis':'frozen_analysis_input;not_later_refresh',
                                             'bars_sha256':inputs['bars_sha256'] if inputs else None},
                               'reason':'sma_period_scope_ambiguous' if ps is None else 'technical_session_integrity_unverified' if verified and not scope['session_integrity']['eligible'] else 'same_window_sma_relation' if valid else 'frozen_sma_input_missing_or_inconsistent'})
    return checks


def technical_reasoning_checks(text,data):
    return histogram_reasoning_checks(text,data)+sma_reasoning_checks(text,data)
