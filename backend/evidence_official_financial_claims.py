"""Narrow period/definition matching against replayed official analysis facts."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
import re
from zoneinfo import ZoneInfo


def _ttm_display_matches(literal, expected, direction=None):
    integer, _, fraction = literal.lstrip('+-').partition('.')
    if len(literal) > 64 or len(integer.replace(',', '')) > 20 or len(fraction) > 20:
        return False
    try:
        value = Decimal(literal.replace(',', ''))
        if direction in {'淨流入', '淨流出'}:
            if value < 0:
                return False
            value = -value if direction == '淨流出' else value
        source = Decimal(str(expected)) / Decimal('100000000')
        return value == source.quantize(Decimal(1).scaleb(-len(fraction)), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return False


def _ttm_narrative_suffix_matches(claim, fact):
    suffix = re.sub(r'[*`\s]', '', str(claim.get('financial_amount_suffix') or ''))
    if re.fullmatch(r'(?:[，,]顯示(?:成長過程伴隨高度營運資金占用|營運資金占用嚴重(?:[，,]限制股利發放空間)?))?', suffix):
        return True
    number = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
    ocf = fact['cashflows']['ttm']['operating_cash_flow']
    purchase = -(fact['cashflows']['ttm']['ppe_purchase'] + fact['cashflows']['ttm']['intangible_purchase'])
    match = re.fullmatch(r'[，,]主因營業現金流淨流出(?P<ocf>' + number + r')億元及資本支出(?P<capex>' + number + r')億元', suffix)
    if match:
        return (_ttm_display_matches(match['ocf'], ocf, '淨流出')
                and _ttm_display_matches(match['capex'], purchase))
    match = re.fullmatch(r'[，,]其中營業活動淨現金流為(?P<ocf>' + number + r')億元[，,]反映營運面現金流出壓力', suffix)
    return bool(match and ocf < 0 and _ttm_display_matches(match['ocf'], ocf))


def _explicit_ttm_narrative_scope(claim, data, projection):
    """Resolve a new explicit TTM clause without inheriting a prior fiscal year.

    Only consumed structural text and known monetary observations may precede
    the exact dated clause. Unknown owners, qualifiers and periods survive and
    fail the ordinary issuer check. Bare TTM is not upgraded by this helper.
    """
    from financial_local_amounts import clean_observed_prefix, observation_prefix
    from financial_money_claims import _target_revenue_scope
    text = observation_prefix(clean_observed_prefix(str(claim.get('financial_period_text') or ''), data))
    text = re.sub(r'[*`\s]', '', text)
    fact = projection['facts']
    interval = re.escape(fact['period_start']) + r'至' + re.escape(fact['period_end'])
    anchor = re.search(r'官方個別(?:財報)?TTM(?:期間)?[（(]' + interval + r'[）)]', text, re.I)
    if anchor is None:
        return None
    if not _ttm_narrative_suffix_matches(claim, fact):
        return None
    before, after = text[:anchor.start()], text[anchor.end():]
    before = re.sub(r'^風險摘要[:：]', '', before)
    before = re.sub(r'^\d+[.)]獲利品質受限於持續性負現金流[:：]接受Agent\d+觀點[。.]', '', before)
    # A completed annual monetary/ratio observation can end before an explicit
    # TTM period. Its numeric value remains a separate extracted claim.
    number = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
    before = re.sub(r'20\d{2}年度(?:FCF|自由現金流)(?:轉換率)?(?:為)?' + number
                    + r'(?:億元|%)(?:[（(]來源：工具計算[）)])?[，,]?', '', before, flags=re.I)
    before = re.sub(r'^(?:另)?(?:根據|依據|觀察|在)?', '', before)
    before = re.sub(r'^(?:且|另|而)', '', before)
    if not _target_revenue_scope(data, before, ''):
        return None
    # Scope may continue through explicitly stated OCF and total-purchase
    # observations. Validate every consumed amount, not just their spelling.
    ocf = re.compile(r'營業(?:活動)?(?:淨)?現金流(?P<direction>淨流出|淨流入|為)?'
                     r'(?P<value>' + number + r')億元', re.I)
    capex = re.compile(r'(?:加計)?總資本支出(?:[（(]CapEx[）)])?'
                       r'(?P<value>' + number + r')億元', re.I)
    for pattern, expected in ((ocf, fact['cashflows']['ttm']['operating_cash_flow']),
                              (capex, -(fact['cashflows']['ttm']['ppe_purchase']
                                        + fact['cashflows']['ttm']['intangible_purchase']))):
        match = pattern.search(after)
        if match is None:
            continue
        literal = match['value']
        direction = match.groupdict().get('direction')
        if not _ttm_display_matches(literal, expected, direction):
            return None
        after = after[:match.start()] + after[match.end():]
    after = re.sub(r'數據|後|TTM', '', after, flags=re.I)
    if re.sub(r'[，,]', '', after):
        return None
    return '官方個別TTM(' + fact['period_start'] + '至' + fact['period_end'] + ')'


def official_capex_claim(claim, data, *, tolerance_pct):
    """Match purchase outflow magnitudes to explicit FY or TTM components.

    Bare CapEx has no universal definition. A PPE amount is not a total, and
    unknown/missing intangible purchases never become zero by default.
    """
    if not claim.get('financial_capex'):
        return None
    from official_financial_projection import read_official_financial_projection
    from financial_money_claims import _SCALES, _target_revenue_scope
    projection = read_official_financial_projection(data)
    if projection is None:
        return None
    original_claim = claim
    resolution = None
    definition = claim.get('financial_capex_definition')
    if definition not in {'ppe_purchase', 'ppe_and_intangible_purchase'}:
        from evidence_capex_narrative_scope import resolve_capex_narrative_scope
        resolution = resolve_capex_narrative_scope(claim, data)
        if resolution is not None:
            claim = {**claim, **{key: resolution[key] for key in (
                'financial_period_text', 'financial_capex_definition')},
                'financial_amount_suffix': ''}
            definition = claim['financial_capex_definition']
    if definition not in {'ppe_purchase', 'ppe_and_intangible_purchase'}:
        return None
    prefix = str(claim.get('financial_period_text') or '')
    heading = str(claim.get('financial_heading') or '')
    parent = str(claim.get('financial_parent_context') or '')
    suffix = str(claim.get('financial_amount_suffix') or '')
    # A trailing qualifier owns the amount too. Only an immediately adjacent
    # explicit purchase component can end this suffix, not arbitrary prose.
    parts = re.split(r'[，,、]', suffix, maxsplit=1)
    if not re.fullmatch(r'\s*(?:[（(](?:現金)?流出[）)])?\s*', parts[0]):
        return None
    if len(parts) == 2:
        from evidence_financial_amounts import _CAPEX_AMOUNT
        next_amount = _CAPEX_AMOUNT.search(parts[1])
        if next_amount is None or not re.fullmatch(
                r'\s*(?:(?:本公司)?(?:TTM|20\d{2}\s*年(?:度)?))?\s*',
                parts[1][:next_amount.start()], re.I):
            return None
    scoped = prefix + heading + parent + parts[0] + str(claim.get('unit') or '')
    if re.search(r'合併|集團|分部|部門|產品|美元|美金|USD|CNY|人民幣|港元|港幣|HKD|日圓|日元|JPY|歐元|EUR|韓元|KRW', scoped, re.I):
        return None
    if parent and not _target_revenue_scope(data, parent, heading):
        return None
    prefix = re.sub(r'^\s*[-+]?\s*(?:CapEx\s*與產能擴充\s*[:：]\s*)?', '', prefix, flags=re.I)
    normalized = re.sub(r'(20\d{2})年(\d{1,2})月(\d{1,2})日',
                        lambda m:f'{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}', prefix)
    fact = projection['facts']
    dates = re.findall(r'20\d{2}-\d{2}-\d{2}', normalized)
    residual = re.sub(r'20\d{2}-\d{2}-\d{2}', '', normalized)
    years = re.findall(r'(?<!\d)(20\d{2})\s*年(?:度)?', residual)
    if re.search(r'TTM', residual, re.I):
        if years or (dates and dates not in ([fact['period_start'], fact['period_end']], [fact['period_end']])):
            return None
        period_key = 'ttm'; start = fact['period_start']; end = fact['period_end']
        document = projection['reference']['quarterly_document']
    elif len(years) == 1 and not dates and int(years[0]) == fact['prior_annual_year']:
        period_key = 'prior_annual'; start = years[0] + '-01-01'; end = years[0] + '-12-31'
        document = projection['reference']['annual_document']
    else:
        return None
    owner = re.sub(r'20\d{2}\s*年(?:度)?|TTM|官方|個別|截至|至|涵蓋|期間', '', residual, flags=re.I)
    if not _target_revenue_scope(data, owner, heading):
        return None
    unit = str(claim.get('unit') or '').lower()
    scale = _SCALES.get(unit.removesuffix('元'), _SCALES.get(unit))
    if scale is None:
        return None
    keys = ['ppe_purchase'] + (['intangible_purchase'] if definition == 'ppe_and_intangible_purchase' else [])
    values = [fact['cashflows'][period_key].get(key) for key in keys]
    if any(type(v) is not int or v > 0 for v in values):
        return None
    signed = sum(values)
    paths = ['data.official_financial_projection.facts.cashflows.' + period_key + '.' + key for key in keys]
    result = _result(original_claim, projection, -signed, paths[0], scale, tolerance_pct)
    if resolution is not None:
        result['financial_capex_narrative_resolution'] = resolution
    result.update(financial_period=start + '/' + end,
        financial_definition=('購置不動產廠房設備現金支出' if definition == 'ppe_purchase'
                              else '購置不動產廠房設備及無形資產現金支出合計'),
        financial_component_paths=paths, financial_component_signed_raw_twd=dict(zip(keys, values)),
        financial_amount_convention='cash_purchase_outflow_magnitude',
        source_signed_raw_twd=signed, source_value=signed, source_unit='signed_TWD',
        expected_value_raw_twd=-signed, reported_value_raw_twd=float(claim['reported_value']) * scale,
        source_url=document['url'], source_document_sha256=document['sha256'],
        source_acquired_at=datetime.fromtimestamp(document['raw_receipt']['retrieved_at'], ZoneInfo('Asia/Taipei')).isoformat())
    documents = [document] if period_key == 'prior_annual' else [projection['reference']['annual_document'], document]
    result['financial_source_documents'] = [
        {'url':doc['url'], 'sha256':doc['sha256'],
         'acquired_at':datetime.fromtimestamp(doc['raw_receipt']['retrieved_at'], ZoneInfo('Asia/Taipei')).isoformat()}
        for doc in documents]
    if period_key == 'ttm':
        result['financial_period_formula'] = fact['ttm_formula']
    if len(keys) == 2:
        result.update(matched_path='data.official_financial_projection.facts.cashflows.' + period_key,
                      financial_formula='-(ppe_purchase + intangible_purchase)')
    else:
        result['financial_formula'] = '-ppe_purchase'
    if '流入' in str(claim.get('financial_capex_link') or ''):
        result.update(status='mismatch', verification_reason_code='official_financial_direction_mismatch')
    return result


def _result(claim, projection, expected, path, scale, tolerance):
    fact = projection['facts']
    reported = Decimal(str(claim['reported_value']))
    expected = Decimal(str(expected)) / Decimal(str(scale))
    precision = claim.get('financial_display_precision', len(str(claim['reported_value']).partition('.')[2]))
    rounded = expected.quantize(Decimal(1).scaleb(-min(20, precision)), rounding=ROUND_HALF_UP)
    difference = abs(reported - expected) / max(abs(expected), Decimal('1e-12')) * 100
    matches = reported * expected >= 0 and (reported == rounded or difference <= Decimal(str(tolerance)))
    return {**claim, 'status': 'verified' if matches else 'mismatch',
            'verification_reason_code': 'official_financial_fact_matched' if matches else 'official_financial_fact_mismatch',
            'verification_scope': 'replayed_official_financial_fact', 'candidate_count': 1,
            'matched_path': path, 'matched_value': float(expected), 'diff_pct': round(float(difference), 4),
            'independent_primary_source_verified': True, 'financial_period_verified': True,
            'financial_period': fact['period_start'] + '/' + fact['period_end'],
            'financial_currency': 'TWD', 'source_url': fact['source_url'],
            'source_acquired_at': fact['acquired_at'], 'historical_pit_verified': False}


def official_fcf_claim(claim, data, *, scale, tolerance_pct):
    if claim.get('financial_metric') not in {'FCF', '自由現金流'}:
        return None
    from official_financial_projection import read_official_financial_projection
    projection = read_official_financial_projection(data)
    if projection is None:
        return None
    from financial_money_claims import other_financial_owner, _target_revenue_scope
    prefix = str(claim.get('financial_period_text') or '')
    heading = str(claim.get('financial_heading') or '')
    parent = str(claim.get('financial_parent_context') or '')
    raw_scope = str(claim.get('financial_owner_text') or claim.get('raw_text') or '')
    suffix = str(claim.get('financial_amount_suffix') or '')
    local = _explicit_ttm_narrative_scope(claim, data, projection)
    parent_scope = '' if local and re.fullmatch(r'\s*風險摘要\s*[:：]\s*', parent) else parent
    if (re.search(r'合併|本集團|集團口徑|同業|同儕|此為|屬於|美元|美金|USD|CNY|人民幣', prefix + heading + parent + raw_scope + suffix, re.I)
            or (parent_scope and not _target_revenue_scope(data, parent_scope, heading))):
        return None
    for qualifier in re.finditer(r'(?:^|[，,;；（(])([^，。；;()（）]+?)資料', suffix):
        if not _target_revenue_scope(data, qualifier[1], ''):
            return None
    if local is not None:
        prefix = local
    owner = re.sub(r'20\d{2}(?:-\d{2}-\d{2}|年\d{1,2}月\d{1,2}日)', '', prefix)
    owner = re.sub(r'涵蓋|起訖|期間|截至|至|近十二個月|近12個月|官方|個別|計算|依', '', owner)
    if other_financial_owner(data, owner, heading) or not _target_revenue_scope(data, owner, heading):
        return None
    fact = projection['facts']
    # A different explicit period cannot borrow the selected TTM input.
    normalized = re.sub(r'(20\d{2})年(\d{1,2})月(\d{1,2})日',
                        lambda m: f'{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}', prefix)
    dates = re.findall(r'20\d{2}-\d{2}-\d{2}', normalized)
    without_dates = re.sub(r'20\d{2}-\d{2}-\d{2}', '', normalized)
    if (re.search(r'20\d{2}|年度|全年|單季|季度|[上下]半年|去年|前年', without_dates)
            or (dates and dates not in ([fact['period_start'], fact['period_end']], [fact['period_end']]))):
        return None
    if not (re.search(r'TTM|近十二個月|近12個月', prefix, re.I)
            or dates == [fact['period_start'], fact['period_end']]):
        return None
    expected = fact['cashflows']['ttm']['free_cash_flow']
    result = _result(claim, projection, expected,
                     'data.official_financial_projection.facts.cashflows.ttm.free_cash_flow', scale, tolerance_pct)
    if ((expected > 0 and re.search(r'淨流出', raw_scope))
            or (expected < 0 and re.search(r'淨流入', raw_scope))):
        result.update(status='mismatch', verification_reason_code='official_financial_direction_mismatch')
    return result


def official_ratio_claim(claim, snapshot, tolerance_pct):
    label = str(claim.get('label') or '')
    if not re.search(r'負債.*權益|借款.*權益|debt.to.equity|D/E', label, re.I):
        return None
    from official_financial_projection import read_official_financial_projection
    data = snapshot.get('data') or {}
    projection = read_official_financial_projection(data)
    if projection is None:
        return None
    raw = re.sub(r'[*`\s]', '', str(claim.get('raw_text') or ''))
    fact = projection['facts']
    result = {**claim, 'status': 'unverifiable', 'candidate_count': 0,
              'verification_reason_code': 'official_ratio_period_or_definition_unbound',
              'verification_scope': 'replayed_official_financial_fact',
              'independent_primary_source_verified': False}
    context = str(claim.get('financial_heading') or '') + str(claim.get('financial_parent_context') or '')
    if (claim.get('unit') != '%' or re.findall(r'20\d{2}-\d{2}-\d{2}', raw) != [fact['balance']['as_of']]
            or claim.get('scenario_projection')
            or re.search(r'同業|同儕|合併|集團|假設|預估|預計|預期|預測|目標|情境|未來|門檻|條件|若|如果|美元|美金|USD|CNY|人民幣', raw + context, re.I)):
        return result
    # A trailing owner/definition cannot be discarded by the short KV label.
    suffix = raw.rsplit('%', 1)[-1]
    if re.sub(r'[。．.，,;；|)）\]】]+', '', suffix):
        return result
    definition = re.sub(r'[*`\s]', '', label)
    match = re.search(r'總負債(?:[/／]|除以(?:同日)?)(?:股東)?權益', definition)
    if match:
        key = 'total_liabilities_to_equity_pct'
    else:
        match = re.search(r'(?:所列五項)?借款(?:與|及|含)租賃負債(?:合計)?(?:[/／]|除以(?:同日)?)(?:股東)?權益', definition)
        if not match:
            return result
        key = 'debt_including_leases_to_equity_pct'
    from financial_money_claims import _target_revenue_scope
    parent = str(claim.get('financial_parent_context') or '')
    if parent and not _target_revenue_scope(data, parent, ''):
        return result
    owner = re.sub(r'20\d{2}-\d{2}-\d{2}', '', definition[:match.start()])
    owner = re.sub(r'官方|個別|截至', '', owner)
    if not _target_revenue_scope(data, owner, ''):
        return result
    checked = _result(claim, projection, fact['ratios'][key],
                      'data.official_financial_projection.facts.ratios.' + key, 1, tolerance_pct)
    checked['financial_period'] = fact['balance']['as_of']
    checked['financial_definition'] = fact['ratio_definitions'][key]
    return checked


def official_debt_component_claims(markdown, snapshot, tolerance_pct=1.0):
    """Check explicit dated individual current-debt amounts, never their total."""
    label = r'(?:長期借款流動部分|一年內到期(?:之)?長期借款)'
    number = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
    unit = r'(?:十億|百萬|億|萬)?(?:新臺幣|新台幣)?(?:港元|港幣|日圓|日元|歐元|韓元|美金|美元|人民幣|元)|TWD'
    pattern = re.compile(r'(?P<label>'+label+r')\s*(?:預期|預估|預測|假設)?\s*(?:為|約|[:：])?\s*(?P<number>'+number+r')\s*(?P<unit>'+unit+r')', re.I)
    from official_financial_projection import read_official_financial_projection
    data = snapshot.get('data') or {}
    projection = None
    results = []; heading = ''; in_code = False
    foreign = re.compile(r'同業|同儕|比較公司|合併|本集團|集團口徑|此為|屬於|預期|預估|預測|假設|情境|未來|如果|若|美元|美金|USD|CNY|人民幣|港元|港幣|HKD|日圓|日元|JPY|歐元|EUR|韓元|KRW', re.I)
    for line_number, original in enumerate(str(markdown).splitlines(), 1):
        if original.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        if original.lstrip().startswith('#'):
            heading = original
        line = re.sub(r'[*`\s]', '', original).replace('−', '-')
        line = re.sub(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', lambda m:f'{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}', line)
        for match in pattern.finditer(line):
            reported = match['number'].replace(',', '')
            claim = {'claim_type':'financial', 'official_debt_component':'current_portion_longterm_borrowings',
                     'label':match['label'], 'reported_value':float(reported), 'unit':match['unit'],
                     'financial_display_precision':len(reported.partition('.')[2]), 'raw_text':original,
                     'line_number':line_number, 'status':'unverifiable', 'candidate_count':0,
                     'verification_reason_code':'official_debt_component_scope_unbound',
                     'independent_primary_source_verified':False}
            if projection is None:
                projection = read_official_financial_projection(data)
            if projection is None or foreign.search(line + heading):
                results.append(claim); continue
            fact = projection['facts']; date = fact['balance']['as_of']
            if set(re.findall(r'20\d{2}-\d{2}-\d{2}', line)) != {date}:
                results.append(claim); continue
            owners = [data.get('company_name'), fact.get('issuer_name'), '本公司']
            identity_record = data.get('company_identity') or {}
            if (identity_record.get('ticker') == data.get('ticker')
                    and identity_record.get('legal_name') == fact.get('issuer_name')):
                owners.append(identity_record.get('official_name'))
            owner = '(?:'+'|'.join(re.escape(str(v)) for v in owners if v)+')'
            prefix = line[:match.start()]
            prefix = re.sub(r'^[-+]?\s*(?:(?:發現|(?:負債|債務)水準與結構分析)[:：])?', '', prefix)
            identity = (r'(?:(?:根據|截至)?'+owner+r'(?:官方)?個別(?:財報)?(?:於|截至)?'+re.escape(date)+r'(?:之)?'
                        r'|根據'+re.escape(date)+r'官方個別財報，'+owner+r'之)')
            preceding = (r'(?:借款與租賃負債[/／]權益比率為'+number+r'%[（(]分子含)?'
                         r'(?:短期借款(?:為)?'+number+r'億元、)?')
            scales = {'元':1, 'TWD':1, '萬元':10000, '百萬元':1000000, '億元':100000000, '十億元':1000000000}
            scale = scales.get(match['unit'])
            narrative_identity = (r'截至'+re.escape(date)+r'[，,]'+owner+r'個別借款與租賃負債總額為'
                                  +number+r'億元。結構包含[:：]短期借款'+number+r'億元、')
            direct_scope = re.fullmatch(identity + preceding, prefix) is not None
            narrative_scope = re.fullmatch(narrative_identity, prefix) is not None
            if not scale or not (direct_scope or narrative_scope):
                results.append(claim); continue
            # Only known adjacent component clauses may inherit the local owner/date.
            # An unknown trailing issuer/scope cannot hide behind the valid prefix.
            suffix = line[match.end():]
            following = r'、長期借款(?:為)?'+number+r'億元、流動與非流動租賃負債(?:合計為)?'+number+r'億元，'
            simple_total = r'五項借款與租賃負債總額為'+number+r'billion_twd（折合'+number+r'億元）。'
            detail_total = (r'總計'+number+r'億元；同日權益為'+number+r'億元），同日總負債[/／]權益比率則為'+number+r'%。'
                r'（來源：data\.balance_sheet\.debt_to_equity_basis；'+re.escape(date)+r'官方個別財報(?:申報日|基準日)）；反證：此比率專指借款含租賃，不等於全公司總負債比率。')
            narrative_following = (r'、長期借款'+number+r'億元，以及租賃負債約'+number+r'億元。'
                                   r'短期償債壓力（一年內需償還金額約'+number+r'億元）相對較高。')
            suffix_bound = (
                direct_scope and re.fullmatch(r'[。.]?|'+following+r'(?:'+simple_total+'|'+detail_total+')', suffix)
                or narrative_scope and re.fullmatch(narrative_following, suffix))
            if not suffix_bound:
                results.append(claim); continue
            expected = fact.get('debt_components',{}).get('current_portion_longterm_borrowings')
            if expected is None:
                results.append(claim); continue
            checked = _result(claim, projection, expected,
                'data.official_financial_projection.facts.debt_components.current_portion_longterm_borrowings', scale, tolerance_pct)
            checked['financial_period'] = date
            checked['financial_definition'] = '個別財報長期借款流動部分；非長期借款總額或借款合計'
            results.append(checked)
    return results
