"""Read-only evidence recovery; never changes financial facts or quality gates."""
from collections import Counter
from datetime import date
from functools import lru_cache
import json
import math
import zlib


def _map(value):
    return value if isinstance(value, dict) else {}


def _number(value):
    try:
        return value if type(value) in (int, float) and math.isfinite(value) else None
    except OverflowError:
        return None


@lru_cache(maxsize=96)
def _institutional_rows(body, market, day):
    from official_institutional_source import _parse_report
    return _parse_report(json.loads(body), market, day)['rows']


@lru_cache(maxsize=4)
def _volume_rows(body, ticker, day):
    if ticker.endswith('.TWO'):
        from data_fetch.market_sources.tpex_session_observation import parse_observation
        return parse_observation(json.loads(body), ticker, day)
    from data_fetch.market_sources.twse_session_observation import parse_session
    return parse_session(json.loads(body), day)


def _day(value):
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) else None
    except ValueError:
        return None


def _annual_detail(result, value, provider, scope):
    year = value['years'][-1]
    facts = value['raw_twd_by_year'][year]
    return dict(result, status='annual_originals_verified', period_start=year+'-01-01',
        period_end=year+'-12-31', currency='TWD', scope=scope,
        operating_cash_flow_twd=facts['operating_cash_flow'],
        ppe_purchase_twd=facts['ppe_purchase' if scope == 'individual' else 'property_purchase'],
        intangible_purchase_twd=facts['intangible_purchase'],
        free_cash_flow_twd=facts['free_cash_flow'], source=provider,
        reason='年度數字已由保存官方原件、單位契約與比較期間重算；不證明即期數值的所屬期間。')


def cash_flow_detail(data):
    currency = data.get('financial_currency')
    result = {'status': 'unverified', 'raw_scalar': _number(data.get('free_cash_flow_raw')),
              'raw_scalar_currency': currency if isinstance(currency, str) and currency in {'TWD', 'USD'} else None,
              'raw_scalar_period_verified': False,
              'reason': '未保存可重新核對的完整年度現金流原件；即期數值的期間不能由年度數值推定。'}
    schema = _map(data.get('financial_history_basis')).get('statement_schema')
    if schema:
        result['reason'] = '已保存金融業專用年度口徑；本補充檢查未將其改成一般企業現金流，金融業現金流也不直接等於可用於一般企業估值的股東現金流。' if schema != 'ordinary_individual.v1' else '已保存個別財報口徑；不轉換為集團合併財報或代填集團現金流。'
    try:
        from data_fetch.annual_financial_source_provider import HISTORY_FIELDS, SCHEMA, project_source_value
        from data_fetch.market_sources.mops_public_annual import SOURCE_URL
        from data_fetch.market_sources.cal_annual_bridge import SOURCE_URL as CAL_URL
        from data_fetch.market_sources.syntec_annual_bridge import SOURCE_URL as SYNTEC_URL
    except ModuleNotFoundError as exc:
        if not (exc.name or '').startswith('data_fetch.'):
            raise
        result['reason'] = '目前安裝版本未包含此年度原件格式的核對器；保留原值與原品質檢查，不將其標為已核實。'
        return result
    if schema == 'ordinary_individual.v1':
        from data_fetch.market_sources.ordinary_individual_annual import project_individual_history, PROVIDER
        statement = _map(data.get('sector_specific_financials'))
        try:
            projected = project_individual_history(statement, data.get('ticker'))
        except (OSError, EOFError, AttributeError, zlib.error):
            projected = None
        if projected is not None and all(projected.get(key) == data.get(key) for key in HISTORY_FIELDS):
            return _annual_detail(result, statement, PROVIDER, 'individual')
    audits = data.get('source_audit')
    financial_rows = [row for row in audits if isinstance(row, dict)
                      and row.get('source') == 'financial_statements'] if isinstance(audits, list) else []
    candidates = [row for row in audits if isinstance(row, dict)
                  and row.get('source') == 'financial_statements'
                  and row.get('status') in {'success', 'skipped_fresh_cache'}
                  and isinstance(row.get('source_url'), str) and row['source_url'] in {SOURCE_URL, CAL_URL, SYNTEC_URL}
                  and isinstance(row.get('raw_twd_by_year'), dict)] if isinstance(audits, list) else []
    if candidates:
        row = candidates[-1]
        value = {key: data.get(key) for key in HISTORY_FIELDS}
        value.update({key: row[key] for key in ('source_url', 'documents', 'raw_twd_by_year',
                      'comparative_revisions', 'comparative_coverage', 'inferred_zero_facts',
                      'source_basis', 'source_origin_note', 'issuer_anchor', 'issuer_master_receipt',
                      'published_annual_index_receipt', 'issuer_ir_index_receipt', 'supplement_documents') if key in row})
        value.update(ticker=data.get('ticker'), schema=SCHEMA, currency='TWD', report_scope='consolidated')
        try:
            verified = project_source_value(value, data.get('ticker'))
        except (OSError, EOFError, AttributeError, zlib.error):
            verified = None
        if verified is not None:
            return _annual_detail(result, verified, row.get('provider'), 'consolidated')
        result['reason'] = '年度憑據未通過現行原件重播；可能缺少完整原件、必要科目或比較期來源標記，保留原值而不升級為已核實。'
    elif not schema:
        failures = [row for row in financial_rows if row.get('status') == 'error' and isinstance(row.get('message'), str)]
        annual = [row for row in financial_rows if row.get('raw_twd_by_year')]
        if failures:
            message = failures[-1]['message'][:300]
            if 'fewer than five contiguous' in message:
                result['reason'] = '官方公開入口未提供連續五年的同口徑年度申報；最新季報未含現金流量表，不能代替年度自由現金流。'
            elif 'conflicting incomplete' in message:
                result['reason'] = '官方金融業2022比較期間不完整且有衝突，不能拼成完整年度現金流；原比較期檢查保留。'
            else:
                result['reason'] = '保存的財報來源未通過核對：'+message
        elif annual:
            result['reason'] = '已保存 '+str(annual[-1].get('provider', '其他官方來源'))+' 的年度序列；此補充層尚未重播該格式所需的全部身分、單位與補充原件，不代表沒有財報。'
        elif financial_rows and all(row.get('provider') == 'cache' for row in financial_rows):
            result['reason'] = '此舊快照只保存快取摘要，沒有完整原來源憑據；快取有效不等於現金流期間與支出組成已核實。'
    return result


def volume_detail(data, supplemental_observation=None):
    from market_price_reconciliation import reconcile
    from official_response_evidence import read_response
    daily = _map(data.get('daily_market_data'))
    if isinstance(supplemental_observation, dict) and _map(daily.get('official_observation')).get('status') != 'observed':
        daily = {**daily, 'official_observation': supplemental_observation}
    result = {'status': 'unverified', 'cross_provider_comparable': False,
              'official_original_verified': False,
              'reason': '原快照未保存可比較的同日官方原件或原始行情採樣；不能以新行情冒充原分析資料。',
              'same_provider_ratio_policy': '技術量比只用同一保存來源的最後20筆（含當日）成交量，不拼接官方當日量。'}
    if not daily:
        return result
    try:
        basis = reconcile(daily)
        raw, official = _map(daily.get('provider_raw_observation')), _map(daily.get('official_observation'))
        result['provider_label'] = 'Yahoo' if any(word in str(raw.get('source') or daily.get('source') or '').lower() for word in ('yahoo', 'yfinance')) else '原保存來源'
        result.update(date=basis['sample_date'], provider_volume=_number(raw.get('volume')),
            official_volume=_number(official.get('volume')), provider_unit=raw.get('volume_unit'),
            official_unit=official.get('volume_unit'), provider_scope_verified=raw.get('volume_scope_verified') is True,
            official_scope_note=None)
        day = _day(official.get('date'))
        ticker = data.get('ticker')
        receipt = _map(official.get('raw_evidence'))
        if not day or not isinstance(ticker, str) or official.get('ticker') != ticker:
            return result
        if ticker.endswith('.TWO'):
            from data_fetch.market_sources.tpex_session_observation import source_url
            expected_url = source_url(ticker, day)
        else:
            expected_url = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date='+day.replace('-', '')+'&type=ALL&response=json'
        if receipt.get('http_status') != 200 or receipt.get('source_url') != expected_url:
            return result
        parsed = _volume_rows(read_response(receipt), ticker if ticker.endswith('.TWO') else '.TW', day)
        if not ticker.endswith('.TWO'):
            parsed = parsed.get(ticker.split('.')[0])
        if not isinstance(parsed, dict) or parsed.get('volume') != official.get('volume'):
            return result
        unit = parsed.get('volume_unit', 'shares')
        if unit != official.get('volume_unit'):
            return result
        result.update(official_original_verified=True, official_scope_note=parsed.get('volume_scope_note'))
        if not basis['session_aligned']:
            result['reason'] = '官方原件已補入，但原報告缺少或未對齊同日原始行情採樣，不能直接比較。'
            return result
        if raw.get('volume_unit') != unit:
            return dict(result, status='unit_mismatch', reason='保存行情以股列示、官方資料以張列示或單位不同，原單位保留，不直接相減。')
        result.update(status=basis['volume']['status'], delta_shares=basis['volume']['delta'])
        result['reason'] = '同日數值不同；來源未證明交易類型相同，不能從差額反推零股或盤後交易。' if basis['volume']['status'] == 'different' else '數值核對不等於交易類型已核實，仍須保留來源口徑限制。'
        # The original gate remains authoritative; unknown provider scope stays unknown.
        result['cross_provider_comparable'] = bool(basis['cross_provider_volume_comparable']
            and parsed.get('volume_scope_verified') is True
            and parsed.get('volume_scope') == official.get('volume_scope'))
        return result
    except (KeyError, ValueError, TypeError, OSError, EOFError, zlib.error):
        return result


def institutional_detail(data, supplemental_reports=()):
    from official_institutional_source import _url
    from official_response_evidence import read_response
    raw = _map(data.get('institutional_trading'))
    rows = raw.get('daily_category_observations')
    rows = rows if isinstance(rows, list) else []
    categories = ('foreign', 'investment_trust', 'dealer')
    dates = raw.get('observation_dates')
    dates = sorted(set(day for day in dates if _day(day))) if isinstance(dates, list) else []
    result = {'status': 'unverified', 'matched_values': 0, 'expected_values': len(dates)*3,
              'matched_dates': [], 'missing_dates': [], 'issues': [],
              'prior_receipt_issues': [], 'conflicts': [],
              'historical_pit_verified': False, 'prediction_verified': False,
              'official_totals_shares': {key: 0 for key in categories}}
    ticker = data.get('ticker')
    if not isinstance(ticker, str) or not dates or len(dates) > 30:
        result['issues'].append('未保存可核對的30日內逐日觀測窗')
        return result
    market = 'TPEX' if ticker.endswith('.TWO') else 'TWSE'
    reports = _map(raw.get('official_recovery')).get('reports')
    reports = list(reports) if isinstance(reports, list) else []
    reports.extend(supplemental_reports if isinstance(supplemental_reports, (list, tuple)) else [])
    reports.append(_map(raw.get('latest_official_observation')))
    archive = data.get('source_record_archive')
    for entry in archive if isinstance(archive, list) else []:
        if not isinstance(entry, dict) or entry.get('source') != 'institutional_trading':
            continue
        prior = _map(entry.get('record'))
        prior_reports = _map(prior.get('official_recovery')).get('reports')
        if isinstance(prior_reports, list):
            reports.extend(prior_reports)
        reports.append(_map(prior.get('latest_official_observation')))
    official, seen = {}, set()
    for report in reports:
        report = _map(report)
        day, proof = report.get('date'), _map(report.get('raw_evidence'))
        digest = proof.get('raw_response_sha256')
        identity = (day, digest if isinstance(digest, str) else None)
        if not isinstance(day, str) or day not in dates or identity in seen:
            continue
        seen.add(identity)
        try:
            url = _url(market, day)
            urls = {url, url.replace('https://www.twse.com.tw/', 'https://wwwc.twse.com.tw/', 1)}
            if proof.get('source_url') not in urls or proof.get('http_status') != 200:
                raise ValueError('official URL/status mismatch')
            parsed = _institutional_rows(read_response(proof), market, day)
            row = parsed.get(ticker.split('.')[0])
            if row is None:
                raise ValueError('security absent; not zero trades')
            versions = official.setdefault(day, {category: set() for category in categories})
            for category in categories:
                versions[category].add(row[category])
        except (KeyError, ValueError, TypeError, OSError, EOFError, zlib.error):
            result['prior_receipt_issues'].append(day+' 早先原件缺漏或雜湊／身分未通過核對；不取消原失敗紀錄')
    valid_rows = [row for row in rows if isinstance(row, dict)
                  and isinstance(row.get('date'), str) and isinstance(row.get('category'), str)]
    if len(valid_rows) != len(rows):
        result['issues'].append('保存分項包含無法辨識的日期或類別')
    keys = [(row.get('date'), row.get('category')) for row in valid_rows]
    duplicates = {key for key, count in Counter(keys).items() if count > 1}
    indexed = {(row.get('date'), row.get('category')): row for row in valid_rows}
    for day in dates:
        source = official.get(day)
        if source is None:
            result['missing_dates'].append(day)
            continue
        matched = 0
        for category in categories:
            key = (day, category)
            label = {'foreign': '外資', 'investment_trust': '投信', 'dealer': '自營商'}[category]
            row = indexed.get(key, {})
            value = row.get('net_buy_shares')
            versions = source[category]
            if len(versions) != 1:
                result['conflicts'].append({'date': day, 'category': category, 'official_values': sorted(versions)})
                result['issues'].append(day+' '+label+' 官方原件版本數值有衝突，原值未替換')
            elif key in duplicates or type(value) is not int or row.get('unit') != 'shares':
                result['issues'].append(day+' '+label+' 保存分項缺漏、重複或單位未核實')
            elif value != next(iter(versions)):
                result['issues'].append(day+' '+label+' 官方與保存值不一致，原值保留')
            else:
                result['matched_values'] += 1
                result['official_totals_shares'][category] += value
                matched += 1
        if matched == 3:
            result['matched_dates'].append(day)
    if result['missing_dates']:
        result['issues'].append('缺少部分歷史日期的官方原件，不能把最新日核對擴大成全期認證')
    result['status'] = 'matched_saved_dates' if not result['issues'] and result['matched_values'] == result['expected_values'] else 'partial' if result['matched_values'] else 'unverified'
    # Partial totals are explicitly restricted to matched cells, never a 30-day total.
    result['totals_scope'] = 'matched_cells_only'
    return result


def evidence_gap_details(data, supplemental_reports=(), supplemental_volume=None):
    data = _map(data)
    return {'cash_flow': cash_flow_detail(data), 'volume': volume_detail(data, supplemental_volume),
            'institutional': institutional_detail(data, supplemental_reports)}
