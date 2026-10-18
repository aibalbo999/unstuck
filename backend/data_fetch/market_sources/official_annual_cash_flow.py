"""One official annual cash-flow reference, never a five-year history repair."""
from datetime import datetime
from copy import deepcopy
import re
import time
import zlib
from zoneinfo import ZoneInfo

SCHEMA = 'official-annual-cash-flow-reference:v1'
SOURCE = 'annual_cash_flow_reference'


def index_request(issuer):
    return {'step': '1', 'firstin': 'ture', 'off': '1', 'queryName': 'co_id',
            'inpuType': 'co_id', 'TYPEK': 'all', 'co_id': issuer}


def replay_reference(data, review):
    result = {'status': 'unverified', 'raw_scalar_period_verified': False,
              'five_year_history_verified': False, 'historical_pit_verified': False,
              'reason': '尚未取得可重播的單一年度官方現金流原件；不改寫原值或原品質判定。'}
    if not isinstance(review, dict):
        return result
    try:
        from .mops_public_annual import _receipt, parse_statement, api_url, template_url, payload
        from .official_xbrl_financial import INDEX_URL, _filing_urls, FilingError
        ticker = data['ticker']
        year = review['year']
        if (not isinstance(ticker, str) or not re.fullmatch(r'[1-9]\d{3}\.TW(?:O)?', ticker)
                or review.get('schema') != SCHEMA or review.get('ticker') != ticker
                or data.get('financial_currency') != 'TWD' or type(year) is not int
                or not 2013 <= year < datetime.now(ZoneInfo('Asia/Taipei')).year):
            raise ValueError('Annual reference identity or period not verified')
        if 'annual_filing_reference' in review:
            from .annual_filing_reference import cash_flow_reference
            return cash_flow_reference(data, review)
        if 'individual_history' in review:
            from .ordinary_individual_annual import project_individual_history
            value = review['individual_history']
            projected = project_individual_history(deepcopy(value), ticker)
            if projected is None or projected['years'][-1] != str(year):
                raise ValueError('Individual annual originals not verified')
            facts = value['raw_twd_by_year'][str(year)]
            at = value['documents'][-1]['raw_receipt']['retrieved_at']
            return dict(result, status='official_annual_cash_flow_verified', scope='individual',
                currency='TWD', period_start=f'{year}-01-01', period_end=f'{year}-12-31',
                source='公開資訊觀測站個別年度財報', five_year_history_verified=True,
                acquired_at=datetime.fromtimestamp(at, ZoneInfo('Asia/Taipei')).isoformat(),
                operating_cash_flow_twd=facts['operating_cash_flow'], ppe_purchase_twd=facts['ppe_purchase'],
                intangible_purchase_twd=facts['intangible_purchase'], free_cash_flow_twd=facts['free_cash_flow'],
                reason='另存的五年個別原件通過核對，但不改寫原報告序列、不當作集團合併數字，也不證明原即期欄位的期間；原分析及品質警示保留。')
        issuer = ticker.split('.')[0]
        if (review.get('index_request') != index_request(issuer)
                or review.get('statement_request') != payload(issuer, year)):
            raise ValueError('Annual reference request not verified')
        close = datetime(year+1, 1, 1, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
        index = _receipt(review['index_receipt'], INDEX_URL, 2500000, not_before=close)
        published = _filing_urls(index, issuer)
        if not published or year != max(published):
            raise ValueError('Not the latest published consolidated annual period')
        newer_individual = sorted(y for y in _filing_urls(index, issuer, report_id='A') if y > year)
        template = _receipt(review['template_receipt'], template_url('CashflowStatement'), not_before=close)
        raw = _receipt(review['statement_receipt'], api_url('CashflowStatement'), not_before=close)
        try:
            facts = parse_statement(raw, issuer, year, 'CashflowStatement', template, include_prior=False)[year]
        except FilingError as exc:
            return dict(result, reason='官方年度現金流表未通過科目、期間或單位檢查：'+str(exc)[:180])
        operating, ppe, intangible = [facts[tag] for tag in (
            'CashFlowsFromUsedInOperatingActivities',
            'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities',
            'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities')]
        at = review['statement_receipt']['retrieved_at']
        return dict(result, status='official_annual_cash_flow_verified', scope='consolidated',
            currency='TWD', period_start=f'{year}-01-01', period_end=f'{year}-12-31',
            source='公開資訊觀測站年度合併現金流量表', acquired_at=datetime.fromtimestamp(at, ZoneInfo('Asia/Taipei')).isoformat(),
            newer_individual_years=newer_individual,
            operating_cash_flow_twd=operating, ppe_purchase_twd=ppe,
            intangible_purchase_twd=intangible, free_cash_flow_twd=operating+ppe+intangible,
            reason='只核對此完整年度的官方現金流表與明列支出；不是五年年度三表、近十二個月或原即期欄位的期間證明，原值、圖表、分析及品質警示保留。')
    except ModuleNotFoundError as exc:
        if not (exc.name or '').startswith('data_fetch.'):
            raise
        result['reason'] = '此版本未安裝對應官方原件核對器，不能將補充年度資料標成已核實。'
    except (KeyError, TypeError, ValueError, AttributeError, OSError, EOFError, OverflowError, zlib.error):
        result['reason'] = '補充年度的公司、完整期間、合併範圍、單位、必要支出或官方原件未通過核對；原值與品質警示保留。'
    return result


def fetch_reference(data, *, transport=None):
    from data_fetch.annual_financial_source_provider import validate_context
    from .mops_public_annual import PublicMopsHttp, api_url, template_url, payload, PROVIDER
    from .official_xbrl_financial import INDEX_URL, _filing_urls, FilingError
    from source_audit import audited_fetch
    ticker = data.get('ticker')
    validate_context(data, ticker)
    if data.get('financial_history_basis') or data.get('sector_specific_financials'):
        raise ValueError('Use the declared sector-specific annual source')
    http = transport or PublicMopsHttp()

    def acquire():
        issuer = ticker.split('.')[0]
        with http.batch():
            index, index_proof = http.request(INDEX_URL, request=index_request(issuer))
            years = _filing_urls(index, issuer)
            if not years:
                raise FilingError('no published consolidated annual filing for this issuer')
            year = max(years)
            _, template_proof = http.request(template_url('CashflowStatement'))
            _, statement_proof = http.request(api_url('CashflowStatement'), json_body=payload(issuer, year))
        review = {'schema': SCHEMA, 'ticker': ticker, 'year': year,
            'index_request': index_request(issuer), 'statement_request': payload(issuer, year),
            'index_receipt': index_proof, 'template_receipt': template_proof,
            'statement_receipt': statement_proof}
        verified = replay_reference(data, review)
        if time.monotonic() >= http.deadline:
            raise FilingError('single annual cash-flow original exceeded existing deadline')
        if verified['status'] != 'official_annual_cash_flow_verified':
            raise FilingError(verified['reason'])
        return review

    result = audited_fetch(SOURCE, PROVIDER, acquire, record_counter=lambda value: 1 if value else 0,
        success_message='單一完整年度合併現金流及明列支出原件已核對；不代表五年財報或原即期欄位期間已核實。')
    components = deepcopy(http.components)
    sent = sum(row.get('http_request_sent') is True for row in components)
    result['audit'].update(coverage_status='single_annual_cash_flow_only',
        http_request_count=sent, http_request_sent=bool(sent), component_statuses=components)
    return result
