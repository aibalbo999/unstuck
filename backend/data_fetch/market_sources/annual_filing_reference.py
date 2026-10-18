"""Complete official annual originals kept separate from saved financial inputs.

Short individual series and unresolved comparatives never become a qualified
five-year history. This adapter does not update reports, caches or quality gates.
"""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import base64
import time
import zlib
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from official_response_evidence import archive_response
from search_provider_runtime import SourceResponseError, cooldown_state, scope_key
from .issuer_news_transport import IssuerNewsHttp
from .mops_public_annual import PublicMopsHttp, PROVIDER, _receipt
from .official_xbrl_financial import INDEX_URL, FilingError, _filing_urls
from .official_annual_cash_flow import index_request

SCHEMA = 'official-annual-filing-reference:v1'
SOURCE = 'annual_filing_reference'
PROFILES = {
    '1623.TW': ('individual', 'ordinary_individual'),
    '7799.TW': ('individual', 'ordinary_individual'),
    '2845.TW': ('consolidated', 'bank'),
    '2855.TW': ('consolidated', 'broker'),
    '2851.TW': ('individual', 'insurer'),
    **{ticker: ('consolidated', 'financial_holding') for ticker in
       ('2883.TW', '2892.TW', '2884.TW', '2887.TW')},
}
MAX_BYTES = 6_000_000


def native_contract(url):
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    issuer = query.get('co_id', [''])[0]
    year = query.get('year', [''])[0]
    profile = PROFILES.get(issuer+'.TW')
    scope = 'A' if profile and profile[0] == 'individual' else 'C'
    if (not profile or not year.isascii() or len(year) != 4 or not year.isdigit()
            or not 2013 <= int(year) < date.today().year
            or parsed.scheme != 'https' or parsed.netloc != 'mopsov.twse.com.tw'
            or parsed.path != '/server-java/FileDownLoad' or parsed.fragment
            or query != {'functionName': ['t164sb01'], 'step': ['9'], 'co_id': [issuer],
                         'year': [year], 'season': ['4'], 'report_id': [scope]}):
        raise FilingError('annual reference native route invalid')
    return MAX_BYTES, {'application/xml', 'text/xml', 'application/xhtml+xml', 'text/html',
                       'application/octet-stream', ''}


class _NativeHttp(IssuerNewsHttp):
    route_contract = staticmethod(native_contract)


class AnnualReferenceHttp(PublicMopsHttp):
    def request(self, url, *, request=None, json_body=None):
        if url == INDEX_URL:
            return super().request(url, request=request, json_body=json_body)
        native_contract(url)
        if request is not None or json_body is not None:
            raise FilingError('annual reference filing requires GET')
        diag = {'url': url, 'request_method': 'GET', 'http_request_sent': False}
        self.components.append(diag)
        if cooldown_state(scope_key(PROVIDER, endpoint='mopsov.twse.com.tw')):
            raise SourceResponseError('cooldown')
        try:
            # Reuse the native capped transport: 5s, no retries/redirects or
            # original-body cache; its host cooldown also remains effective.
            value = _NativeHttp(self.deadline)._download(url, diag)
            raw = base64.b64decode(value['body_b64'], validate=True)
            proof = archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200)
            if _receipt(proof, url, MAX_BYTES) != raw:
                raise FilingError('annual reference original archive mismatch')
            diag.update(http_status=200, status='complete', response_sha256=sha256(raw).hexdigest(),
                        response_bytes=len(raw), raw_receipt=proof)
            if not raw.lstrip(b'\xef\xbb\xbf \t\r\n').startswith(b'<?xml'):
                diag['status'] = 'rejected_body'
                raise SourceResponseError('parse_error')
            return raw, proof
        except Exception as exc:
            diag.update(error_kind=getattr(exc, 'error_kind', type(exc).__name__))
            raise


def _parser(taxonomy):
    from . import financial_institution_xbrl as financial, broker_xbrl, insurer_xbrl
    if taxonomy in {'bank', 'financial_holding'}:
        return financial.parse_filing, financial.reconcile_comparatives, financial.assemble_histories
    module = broker_xbrl if taxonomy == 'broker' else insurer_xbrl
    return module.parse_filing, module.reconcile_comparatives, module.assemble_histories


def _financial_metadata(raw, issuer, year, taxonomy):
    from .official_xbrl_financial import IX, XBRLI, _context_period
    root = ET.fromstring(raw)
    contexts = {node.get('id'): _context_period(node, issuer) for node in root.iter(XBRLI+'context')}
    duration = ('duration', f'{year}-01-01', f'{year}-12-31')
    expected = {'CompanyID': issuer, 'Year': str(year), 'Quarter': '4',
                'ReportCategory': 'Individual report' if taxonomy == 'insurer' else 'Consolidated report',
                'ReportType': 'Financial report (general)',
                'IndustrySector': {'bank': 'Bank', 'financial_holding': 'Financial holding',
                                   'broker': 'Broker-dealer', 'insurer': 'Insurance'}[taxonomy]}
    metadata = {}
    for tag in (*expected, 'CompanyChineseName'):
        facts = [node for node in root.iter(IX+'nonNumeric') if node.get('name') == 'tifrs-notes:'+tag]
        if len(facts) != 1 or contexts.get(facts[0].get('contextRef')) != duration:
            raise FilingError('annual reference financial scope metadata missing or ambiguous: '+tag)
        text = ''.join(facts[0].itertext()).strip()
        accepted = {expected[tag]} if tag in expected else {text}
        if tag == 'ReportType' and (issuer, year) == ('2892', 2021):
            accepted.add('Financial Report (retrospective - material)')
        if text not in accepted or not 0 < len(text) <= 100:
            raise FilingError('annual reference financial scope metadata mismatch: '+tag)
        metadata[tag] = text
    return metadata


def _parse(raw, issuer, year, taxonomy):
    if taxonomy == 'ordinary_individual':
        from .ordinary_individual_annual import parse_individual_filing
        parsed = parse_individual_filing(raw, issuer, year, reference_only=True)
        from .ordinary_individual_annual import ISSUERS, REFERENCE_ISSUERS
        return parsed[year], parsed[year-1], parsed['inferred_zero_facts'], {
            'CompanyChineseName': {**ISSUERS, **REFERENCE_ISSUERS}[issuer+'.TW'],
            'ReportType': 'Financial report (first time adoption)' if (issuer, year) == ('7799', 2023)
            else 'Financial report (general)'}
    from .financial_institution_xbrl import BANK_FIELDS, FIELDS, _fact_fields
    parser, _, _ = _parser(taxonomy)
    current = parser(raw, issuer, year, allow_missing=True)
    prior = parser(raw, issuer, year-1, allow_missing=True)
    if not current:
        raise FilingError('annual reference current fiscal-year facts missing')
    if taxonomy in {'bank', 'financial_holding'} and _fact_fields(current) is not (
            BANK_FIELDS if taxonomy == 'bank' else FIELDS):
        raise FilingError('annual reference financial taxonomy mismatch')
    return current, prior, [], _financial_metadata(raw, issuer, year, taxonomy)


def _row(current, taxonomy):
    if taxonomy == 'ordinary_individual':
        result = dict(current)
    else:
        from .financial_institution_xbrl import BANK_FIELDS, FIELDS
        from .broker_xbrl import FIELDS as BROKER_FIELDS
        from .insurer_xbrl import FIELDS as INSURER_FIELDS
        fields = {'bank': BANK_FIELDS, 'financial_holding': FIELDS,
                  'broker': BROKER_FIELDS, 'insurer': INSURER_FIELDS}[taxonomy]
        result = {field: current[tag] for tag, field in fields.items() if tag in current}
    required = ('operating_cash_flow', 'ppe_purchase', 'intangible_purchase')
    result['free_cash_flow'] = sum(result[k] for k in required) if all(k in result for k in required) else None
    return result


def _comparative_diagnostics(primary, comparatives, taxonomy):
    if taxonomy == 'ordinary_individual':
        from .ordinary_individual_annual import FIELDS
        required = set(FIELDS.values())
    else:
        from .financial_institution_xbrl import BANK_FIELDS, FIELDS
        from .broker_xbrl import FIELDS as BROKER_FIELDS
        from .insurer_xbrl import FIELDS as INSURER_FIELDS
        required = set({'bank': BANK_FIELDS, 'financial_holding': FIELDS,
                        'broker': BROKER_FIELDS, 'insurer': INSURER_FIELDS}[taxonomy])
    output = []
    for year, prior in comparatives.items():
        original = primary[year]
        conflicts = {tag: {'original_twd': original[tag], 'comparative_twd': amount}
                     for tag, amount in prior.items() if tag in original and original[tag] != amount}
        missing = sorted(required-set(prior))
        if missing or conflicts:
            output.append({'period_year': year, 'original_filing_year': year,
                           'comparative_filing_year': year+1, 'missing_facts': missing,
                           'conflicting_facts': conflicts})
    return output


def replay_reference(value, ticker):
    """Re-read all complete receipts; never trust supplied arithmetic or periods."""
    result = {'status': 'unverified', 'raw_scalar_period_verified': False,
              'five_year_history_verified': False, 'historical_pit_verified': False,
              'industrial_dcf_applicable': False}
    try:
        if not isinstance(value, dict) or ticker not in PROFILES:
            raise FilingError('annual reference original collection unavailable or issuer not admitted')
        scope, taxonomy = PROFILES[ticker]
        if (value.get('schema') != SCHEMA or value.get('ticker') != ticker
                or value.get('report_scope') != scope or value.get('statement_taxonomy') != taxonomy):
            raise FilingError('annual reference identity/scope/taxonomy mismatch')
        issuer = ticker.split('.')[0]
        index = _receipt(value['published_index_receipt'], INDEX_URL, 2_500_000)
        published = _filing_urls(index, issuer, report_id='A' if scope == 'individual' else 'C')
        coverage = value.get('coverage', 'indexed_recent_annuals')
        if coverage not in {'indexed_recent_annuals', 'latest_annual_only'}:
            raise FilingError('annual reference coverage invalid')
        years = sorted(published)[-1 if coverage == 'latest_annual_only' else -5:]
        docs = value['documents']
        if (not years or years[-1] >= date.today().year or not isinstance(docs, list)
                or len(docs) != len(years)):
            raise FilingError('annual reference indexed originals incomplete')
        primary = {}; comparatives = {}; inferred = []; names = {}; report_types = {}
        for year, doc in zip(years, docs):
            close = datetime(year+1, 1, 1, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
            if (not isinstance(doc, dict) or type(doc.get('year')) is not int
                    or doc['year'] != year or doc.get('url') != published[year]):
                raise FilingError('annual reference document period or URL mismatch')
            raw = _receipt(doc['raw_receipt'], published[year], MAX_BYTES, not_before=close)
            if sha256(raw).hexdigest() != doc.get('sha256'):
                raise FilingError('annual reference body hash mismatch')
            primary[year], prior, zeros, metadata = _parse(raw, issuer, year, taxonomy)
            names[str(year)] = metadata['CompanyChineseName']
            report_types[str(year)] = metadata['ReportType']
            inferred.extend(zeros)
            if year-1 in years: comparatives[year-1] = prior
        _receipt(value['published_index_receipt'], INDEX_URL, 2_500_000,
                 not_before=datetime(years[-1]+1, 1, 1, tzinfo=ZoneInfo('Asia/Taipei')).timestamp())
        rows = {str(year): _row(facts, taxonomy) for year, facts in primary.items()}
        latest = rows[str(years[-1])]
        result.update(status='annual_originals_verified' if latest['free_cash_flow'] is not None
                      else 'annual_components_verified', report_scope=scope, statement_taxonomy=taxonomy,
                      currency='TWD', years=[str(year) for year in years],
                      issuer_name=names[str(years[-1])], issuer_names_by_year=names,
                      report_types_by_year=report_types,
                      restated_filing_years=[year for year in years if 'retrospective' in report_types[str(year)]],
                      period_start=f'{years[-1]}-01-01', period_end=f'{years[-1]}-12-31',
                      raw_twd_by_year=rows, inferred_zero_facts=inferred,
                      comparative_diagnostics=_comparative_diagnostics(primary, comparatives, taxonomy),
                      first_adoption_years=[2023] if ticker == '7799.TW' and 2023 in years else [],
                      consolidated_years=sorted(_filing_urls(index, issuer)),
                      individual_years=sorted(_filing_urls(index, issuer, report_id='A')))
        try:
            if taxonomy == 'ordinary_individual':
                from .ordinary_individual_annual import _assemble
                rebuilt, revisions = _assemble(primary, comparatives)
            else:
                _, reconcile, assemble = _parser(taxonomy)
                resolved, revisions = reconcile(primary, comparatives)
                rebuilt = assemble(resolved, expected_years=years)['raw_twd_by_year']
            result.update(comparative_revisions=revisions, reconciled_twd_by_year=rebuilt)
            result['five_year_history_verified'] = (coverage == 'indexed_recent_annuals' and len(years) == 5
                and years == list(range(years[0], years[0]+5))
                and all(row.get('free_cash_flow') is not None for row in rebuilt.values()))
        except FilingError as exc:
            result['comparative_issue'] = str(exc)[:240]
        return result
    except (KeyError, TypeError, ValueError, OSError, EOFError, OverflowError, zlib.error) as exc:
        return dict(result, status='unverified', reason=str(exc)[:240])


def cash_flow_reference(data, review):
    """Reader-compatible result for an explicitly separate supplemental review."""
    result = {'status': 'unverified', 'raw_scalar_period_verified': False,
              'five_year_history_verified': False, 'historical_pit_verified': False,
              'industrial_dcf_applicable': False,
              'reason': '尚未取得公司、年度範圍與原件均可重播的補充財報；原值與品質判定保持。'}
    if (not isinstance(data, dict) or not isinstance(review, dict)
            or data.get('financial_currency') != 'TWD'
            or review.get('schema') != 'official-annual-cash-flow-reference:v1'
            or review.get('ticker') != data.get('ticker') or type(review.get('year')) is not int):
        return result
    value = review.get('annual_filing_reference')
    verified = replay_reference(value, data.get('ticker'))
    if (verified['status'] not in {'annual_originals_verified', 'annual_components_verified'}
            or verified['years'][-1] != str(review['year'])):
        return result
    facts = verified['raw_twd_by_year'][str(review['year'])]
    if verified['status'] == 'annual_components_verified':
        labels = {'operating_cash_flow': '營業現金流', 'ppe_purchase': '設備購置支出',
                  'intangible_purchase': '無形資產購置支出'}
        missing = [key for key in labels if type(facts.get(key)) is not int]
        present = [label for key, label in labels.items() if key not in missing]
        reason = '官方完整年度原件可重播；'
        if present:
            reason += '已核對'+'、'.join(present)+'，但'
        reason += '尚缺明列'+'、'.join(labels[key] for key in missing)+'；缺列不當成零，年度 FCF 仍未知。'
        for issue in verified.get('comparative_diagnostics', []):
            if issue['conflicting_facts']:
                year = issue['period_year']
                reason += f'{issue["comparative_filing_year"]} 年報所列 {year} 比較欄與 {year} 原年度有衝突'
                if issue['missing_facts']:
                    reason += '，且比較欄仍缺必要科目'
                reason += '，未通過完整序列核對。'
        reason += '原資料與比較期檢查保留。'
        return dict(result, components_verified=True, missing_cash_flow_components=missing, reason=reason)
    scope = verified['report_scope']
    financial = verified['statement_taxonomy'] != 'ordinary_individual'
    count = len(verified['years'])
    reason = f'另存的 {count} 個年度原件已核對；'
    if not verified['five_year_history_verified']:
        reason += '未取得可完整核對的五年同口徑序列，不代表五年財報缺口已補齊；'
    if scope == 'individual':
        reason += '僅為本公司個別報表，不與合併集團序列拼接；'
    if verified.get('first_adoption_years'):
        reason += '2023 年報明示首次採用財報，不宣稱更早年度已具相同基礎；'
    if verified.get('restated_filing_years'):
        reason += '2021 年報明示重大追溯重編，僅確認本次取得版本，不證明當年已可取得；'
    if financial:
        reason += '依各年申報範圍核對，不證明集團組成歷年相同；金融業現金流不證明適用一般企業 DCF；'
    if verified.get('comparative_issue'):
        reason += '較早年度比較期仍有衝突或必要科目不完整；'
    reason += '原即期欄位期間、原值、圖表、分析與品質判定保持。'
    latest_doc = value['documents'][-1]
    return dict(result, status='official_annual_cash_flow_verified', currency='TWD', scope=scope,
                issuer_name=verified['issuer_name'],
                statement_taxonomy=verified['statement_taxonomy'], verified_years=verified['years'],
                five_year_history_verified=verified['five_year_history_verified'],
                period_start=verified['period_start'], period_end=verified['period_end'],
                source='公開資訊觀測站'+('金融業' if financial else '')+('個別年度財報' if scope == 'individual' else '合併年度財報'),
                acquired_at=datetime.fromtimestamp(latest_doc['raw_receipt']['retrieved_at'], ZoneInfo('Asia/Taipei')).isoformat(),
                operating_cash_flow_twd=facts['operating_cash_flow'], ppe_purchase_twd=facts['ppe_purchase'],
                intangible_purchase_twd=facts['intangible_purchase'], free_cash_flow_twd=facts['free_cash_flow'],
                reason=reason)


def fetch_reference(ticker, *, transport=None, coverage='indexed_recent_annuals'):
    """Audit a bounded supplementary collection, never canonical financial success."""
    from source_audit import audited_fetch
    from provider_resilience import _check_provider_state
    from provider_throttle import enforce_provider_throttle
    http = transport or AnnualReferenceHttp()
    def acquire():
        if ticker not in PROFILES:
            raise FilingError('annual reference issuer not admitted')
        if coverage not in {'indexed_recent_annuals', 'latest_annual_only'}:
            raise FilingError('annual reference coverage invalid')
        scope, taxonomy = PROFILES[ticker]
        # Check the established financial protocol as well as the public host.
        from .financial_institution_xbrl import PROVIDER as FINANCIAL_PROVIDER
        _check_provider_state(FINANCIAL_PROVIDER)
        enforce_provider_throttle(FINANCIAL_PROVIDER)
        with http.batch():
            index, proof = http.request(INDEX_URL, request=index_request(ticker.split('.')[0]))
            published = _filing_urls(index, ticker.split('.')[0], report_id='A' if scope == 'individual' else 'C')
            docs = []
            for year in reversed(sorted(published)[-1 if coverage == 'latest_annual_only' else -5:]):
                raw, receipt = http.request(published[year])
                docs.append({'year': year, 'url': published[year], 'sha256': sha256(raw).hexdigest(),
                             'raw_receipt': receipt})
            docs.sort(key=lambda document: document['year'])
        value = {'schema': SCHEMA, 'ticker': ticker, 'report_scope': scope,
                 'statement_taxonomy': taxonomy, 'coverage': coverage,
                 'published_index_receipt': proof, 'documents': docs}
        if time.monotonic() >= http.deadline:
            raise SourceResponseError('timeout')
        return value
    result = audited_fetch(SOURCE, PROVIDER, acquire, record_counter=lambda value: len(value['documents']),
                           success_message='已另存官方年度完整原件；科目與五年完整度須另行重播核對，不改寫原資料或品質判定。')
    components = deepcopy(http.components)
    count = sum(item.get('http_request_sent') is True for item in components)
    result['audit'].update(http_request_sent=bool(count), http_request_count=count,
                           component_statuses=components, coverage_status='supplementary_originals_only',
                           actual_provider='TWSE MOPS official annual iXBRL originals',
                           admission_provider=PROVIDER)
    return result
