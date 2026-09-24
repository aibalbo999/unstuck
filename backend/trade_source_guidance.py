"""Bounded factual examples from the same visible catalog, never adopted assertions."""
import copy
import json
import re


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
                          'limit': '累計淨額不證明每日連續、持續或趨勢；不得改主體或期間'})
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
        cards.append({'ref': ref, 'roles': ref_roles, 'fact': fact})
    # A fact example must also survive the actual combined source predicates.
    # This is an isolated probe, never an adopted candidate or direction change.
    from trade_source_contract import bind_trade_payload, CONTRACT_VERSION
    context = {'_trade_source_manifest': {'version': CONTRACT_VERSION, 'visible': True, 'catalog': catalog}}
    verified = []
    for card in cards:
        probe = {'trade_direction': 'Neutral', 'entry_zone': 'N/A', 'target_price': 'N/A',
                 'stop_loss': 'N/A', 'core_catalyst': card['fact'], 'support_source_refs': [],
                 'resistance_source_refs': [], 'catalyst_source_refs': [card['ref']]}
        if bind_trade_payload(probe, context)[1]['status'] == 'observation':
            verified.append(card)
    return verified


def source_guidance_text(catalog):
    cards = source_fact_cards(catalog)
    return ('\n【同一來源的有限事實句示例；不是方向建議】\n'
            '以下僅示範來源可以證明的範圍，不是完整來源清單，也不取代原始資料。'
            '依研究需要自行選擇並引用，不得為通過 gate 強迫方向、刪除反證或把未知當成事實。'
            '額外推論仍須自己的同期間來源；單根日K高點不證明52週高點；新聞出版不證明未來排程。\n'
            + '\n'.join('- ' + c['fact'] + ' source ref=' + c['ref'] + '；' +
                        json.dumps({k: v for k, v in c.items() if k not in {'fact', 'ref'}},
                                   ensure_ascii=False, separators=(',', ':')) for c in cards))
