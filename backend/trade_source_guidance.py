"""Bounded factual examples from the same visible catalog, never adopted assertions."""
import copy
import json
import re


def price_source_observations(catalog):
    """Expose exactly the date/window/basis consumed by the price validator."""
    from trade_source_contract import allowed_source_refs
    from trade_price_reference import _observation
    allowed = allowed_source_refs(catalog)
    observations = {}
    for role in ('support_source_refs', 'resistance_source_refs'):
        for ref in allowed[role]:
            value = _observation(catalog, ref, role)
            if value is not None:
                observations[ref] = value
    return list(observations.values())


def technical_comparison_facts(catalog):
    """Single-session comparisons; never infer a cross or trend from a point."""
    root = catalog.get('short_term_market_context', {})
    if not isinstance(root, dict):
        return []
    daily = root.get('daily_market_data', {})
    technical = root.get('technical_indicators', {})
    if not isinstance(daily, dict) or not isinstance(technical, dict):
        return []
    bars = daily.get('bars', [])
    if not bars or not isinstance(bars[-1], dict):
        return []
    if (not technical.get('as_of') or bars[-1].get('date') != technical.get('as_of')
            or daily.get('price_adjustment_basis') in {None, '', 'unknown', 'unavailable'}
            or daily.get('price_adjustment_basis') != technical.get('price_adjustment_basis')):
        return []
    from quant_input_contract import finite_number
    close = finite_number(bars[-1].get('close'))
    if close is None or close <= 0:
        return []
    close_ref = f'short_term_market_context.daily_market_data.bars[{len(bars)-1}].close'
    facts = []
    for field in ('sma_5', 'sma_10', 'sma_20', 'sma_60'):
        average = finite_number(technical.get(field))
        if average is not None and average > 0:
            facts.append({'observed_date': technical['as_of'], 'price_basis': daily['price_adjustment_basis'],
                          'close': close, 'average': average,
                          'relation': 'above' if close > average else 'below' if close < average else 'equal',
                          'source_refs': [close_ref, 'short_term_market_context.technical_indicators.' + field]})
    averages = [finite_number(technical.get('sma_' + str(n))) for n in (5, 10, 20)]
    if all(value is not None for value in averages):
        facts.append({'observed_date': technical['as_of'], 'price_basis': daily['price_adjustment_basis'],
                      'sma_5_10_20': averages, 'bullish_order': averages[0] > averages[1] > averages[2],
                      'bearish_order': averages[0] < averages[1] < averages[2],
                      'source_refs': ['short_term_market_context.technical_indicators.sma_' + str(n) for n in (5, 10, 20)]})
    return facts


def technical_comparison_prompt(catalog):
    facts = technical_comparison_facts(catalog)
    technical = catalog.get('short_term_market_context', {}).get('technical_indicators', {})
    comparison = technical.get('macd_histogram_comparison') if isinstance(technical, dict) else None
    if isinstance(comparison, dict):
        facts.append({'macd_histogram_comparison': comparison})
    return ('【同日同價格基準的可重算相對位置】\n'
            'below才表示低於，above表示高於；不得把高於寫成跌破。'
            '此處只證明當日相對位置，不證明穿越、轉正、斜率、趨勢或動能加速；'
            '突破/跌破/黃金交叉/轉正必須另列前後兩個日期的同基準觀測。'
            'SMA5>SMA10>SMA20才是5/10/20日多頭排列；其他均線組合需明寫組合。'
            'MACD柱的擴張比較絕對值，不是帶符號大小：負柱-0.57到-0.44為收斂，仍負值不代表擴張。'
            '正柱也以絕對值判斷；跨零須寫跨零，不能沿用負柱收斂／擴張。'
            '只可使用下列同一完整輸入窗與EMA種子的兩日計算收據；缺前日或基準時標未評估。\n'
            + json.dumps(facts, ensure_ascii=False, allow_nan=False)) if facts else ''


def canonical_catalog(catalog):
    """Keep record indexes/values; references identify the visible catalog, not raw input."""
    result = copy.deepcopy(catalog)
    root = result.get('short_term_market_context', {})
    if not isinstance(root, dict):
        return result
    for kind in ('institutional_evidence', 'ownership_evidence'):
        section = root.get(kind)
        records = section.get('records') if isinstance(section, dict) else None
        for index, record in enumerate(records if isinstance(records, list) else []):
            if isinstance(record, dict):
                record['path'] = f'short_term_market_context.{kind}.records[{index}]'
    return result


def source_fact_cards(catalog):
    from trade_source_contract import allowed_source_refs, resolve_reference
    from institutional_evidence_prompt import build_institutional_source_prompt
    from trade_catalog_evidence import ownership_claim_supported, news_catalyst_supported

    allowed = allowed_source_refs(catalog)
    roles = {}
    for role, refs in allowed.items():
        for ref in refs:
            roles.setdefault(ref, []).append(role)
    cards = []
    canonical = canonical_catalog(catalog)
    # Reuse the numeric/date/unit validator's existing source-sentence renderer.
    for line in build_institutional_source_prompt(canonical).splitlines():
        if not line.startswith('- ') or ' source ref=' not in line:
            continue
        fact, tail = line[2:].split(' source ref=', 1)
        ref = tail.split('；provider=', 1)[0]
        if ref in roles:
            cards.append({'ref': ref, 'roles': roles[ref], 'fact': fact,
                          'limit': '累計淨額不證明每日連續、持續或趨勢；不得改主體或期間',
                          'supports': ['dated_numeric_net_flow'],
                          'unsupported': ['daily_alternation', 'continuous_flow', 'turning_trend']})
        if len(cards) >= 12:
            break
    root = catalog.get('short_term_market_context', {})
    counts = {}
    limits = {'news': 2, 'ownership': 2, 'technical': 6, 'daily': 2, 'event': 2}
    for ref, ref_roles in roles.items():
        value = resolve_reference(catalog, ref)
        fact = None
        if '.recent_news.items[' in ref:
            kind = 'news'
            fact = f"{value['published_at']} {value['provider']}新聞報導「{value['title']}」"
            if not news_catalyst_supported(fact, [value]):
                continue
        elif '.ownership_evidence.records[' in ref:
            kind = 'ownership'
            group = {'major_holders': '持股超過1000張大戶', 'retail_holders': '持股不足50張散戶'}[value['population']]
            fact = f"{value['observed_at']}，{group}持股比例{value['value']}%。"
            if not ownership_claim_supported(fact, [value]):
                continue
        elif '.technical_indicators.' in ref:
            kind = 'technical'
            metadata = root.get('technical_indicators', {})
            field = ref.rsplit('.', 1)[-1]
            fact = f"{metadata['as_of']} {metadata['source']}觀測 {field}={value}"
            if field.startswith('volume_') and field != 'volume_ratio_20':
                fact += ' ' + metadata['volume_unit']
        elif re.fullmatch(r'.*\.bars\[\d+\]\.(?:high|low|close)', ref):
            kind = 'daily'
            bar = resolve_reference(catalog, ref.rsplit('.', 1)[0])
            if not isinstance(bar, dict) or not bar.get('date'):
                continue
            fact = f"{bar['date']} {ref.rsplit('.', 1)[-1]}={value}（單根日K，不代表52週高低點）"
        elif '.event_calendar.events[' in ref:
            kind = 'event'
            fact = f"{value['source']}事件紀錄：{value['date']} {value['label']}"
        else:
            continue
        if counts.get(kind, 0) >= limits[kind]:
            continue
        counts[kind] = counts.get(kind, 0) + 1
        card = {'ref': ref, 'roles': ref_roles, 'fact': fact}
        if kind == 'ownership':
            card.update(supports=['dated_ownership_percentage'],
                        unsupported=['ownership_increase', 'ownership_decrease', 'multiweek_trend'])
        cards.append(card)
    # A fact example must also survive the actual combined source predicates.
    # This is an isolated probe, never an adopted candidate or direction change.
    from trade_source_contract import bind_trade_payload, CONTRACT_VERSION
    context = {'_trade_source_manifest': {'version': CONTRACT_VERSION, 'visible': True, 'catalog': catalog}}
    verified = []
    for card in cards:
        probe = {'trade_direction': 'Neutral', 'entry_zone': 'N/A', 'target_price': 'N/A',
                 'stop_loss': 'N/A', 'core_catalyst': card['fact'], 'support_source_refs': [],
                 'resistance_source_refs': [], 'catalyst_source_refs': [card['ref']],
                 'observed_signal': card['fact'], 'observed_source_refs': [card['ref']],
                 'event_catalyst': None, 'recheck_condition': None, 'financial_risk_flags': []}
        if bind_trade_payload(probe, context)[1]['status'] == 'observation':
            verified.append(card)
    return verified


def source_guidance_text(catalog):
    from trade_output_contract_guidance import trade_fact_output_instruction
    cards = source_fact_cards(catalog)
    return ('\n【同一來源的有限事實句示例；不是方向建議】\n'
            '以下僅示範來源可以證明的範圍，不是完整來源清單，也不取代原始資料。'
            '依研究需要自行選擇並引用，不得為通過 gate 強迫方向、刪除反證或把未知當成事實。'
            '額外推論仍須自己的同期間來源；單根日K高點不證明52週高點；新聞出版不證明未來排程。'
            '生成 observed_signal 前逐句核對：每個事實須有自己的 observed_source_refs；'
            '不可在已引用的累計數值後附加「近10日買賣交錯」，也不可在單次持股比例後附加「連續兩週減少」。'
            '下列 unsupported 是目前契約不能由該引用證明的論述；不要把這些論述寫成已觀測事實。'
            '尚待發生的改善只能放 recheck_condition；事件資料 unavailable 時保留未知，不能當成催化證據。\n'
            + trade_fact_output_instruction(24) + '\n'
            + '\n'.join('- ' + c['fact'] + ' source ref=' + c['ref'] + '；' +
                        json.dumps({k: v for k, v in c.items() if k not in {'fact', 'ref'}},
                                   ensure_ascii=False, separators=(',', ':')) for c in cards)
            + '\n【逐引用價格輸入收據；只供引用，不指定支撐壓力或方向】\n'
            'price_level_evidence.inputs逐項原樣沿用下列ref、observed_date、window_sessions、price_basis；'
            '不得把Yahoo還原OHLC改稱交易所未還原價、unadjusted_high或adjusted_analysis_series。'
            '來源缺metadata保留null，不靠名稱猜測；數字相同也不證明基準相同。\n'
            + json.dumps(price_source_observations(catalog), ensure_ascii=False, allow_nan=False)
            + ('\n' + technical_comparison_prompt(catalog) if technical_comparison_prompt(catalog) else ''))
