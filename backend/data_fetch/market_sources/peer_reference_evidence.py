"""Bind a missing peer P/E explanation to full current official originals.

There is no numeric P/E here. A derived nonpositive reference income is a
qualified mathematical explanation, not an exchange-published per-row cause.
"""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from cache_store import peek_cache_json
from .official_company_legal_name import read_cached_listed_roster_bytes
from .peer_reference_income import (SCHEMA, TICKER, CODE as CODE, SHORT as SHORT,
    LEGAL as LEGAL, UBN as UBN,
    APPLICABILITY, unique_json, parse_reference, parse_calendar_index,
    parse_cumulative_income, required_periods, derive_nonpositive_income, parse_methodology)
from .peer_reference_transport import PeerIncomeHttp, spec, receipt_body
from .peer_reference_issuers import consolidated_issuer


def _today():
    return datetime.now(ZoneInfo('Asia/Taipei')).date()


def _context(ticker, observed_at, today):
    consolidated_issuer(ticker)
    if not isinstance(observed_at, str):
        raise ValueError('unsupported reference-income issuer')
    observed = date.fromisoformat(observed_at)
    if observed.isoformat() != observed_at or not 0 <= (today - observed).days <= 7:
        raise ValueError('unverified valuation observation date')
    return observed


def _master(today, *, issuer_ticker=TICKER):
    issuer = consolidated_issuer(issuer_ticker)
    value = read_cached_listed_roster_bytes()
    if value is None:
        raise ValueError('current complete issuer master unavailable')
    raw, meta = value
    rows = unique_json(raw)
    if (not isinstance(rows, list) or not 800 <= len(rows) <= 2000
            or any(not isinstance(row, dict) for row in rows)
            or meta.get('source_payload_sha256') != sha256(raw).hexdigest()
            or meta.get('source_payload_bytes') != len(raw)):
        raise ValueError('complete issuer master unverified')
    codes = [str(row.get('公司代號') or '') for row in rows]
    if len(codes) != len(set(codes)) or codes.count(issuer.code) != 1:
        raise ValueError('issuer master duplicate identity')
    row = rows[codes.index(issuer.code)]
    expected = {'公司名稱': issuer.legal, '公司簡稱': issuer.short, '營利事業統一編號': issuer.ubn,
                '產業別': issuer.industry_code, '編制財務報表類型': '1', '特別股': '0'}
    if any(row.get(k) != v for k, v in expected.items()):
        raise ValueError('ordinary consolidated issuer identity unverified')
    shares = row.get('已發行普通股數或TDR原股發行股數')
    published = row.get('出表日期')
    if not isinstance(shares, str) or not shares.isascii() or not shares.isdigit() or int(shares) <= 0:
        raise ValueError('positive ordinary share identity unavailable')
    if issuer.ordinary_shares is not None:
        country=row.get('外國企業註冊地國')
        if (shares!=str(issuer.ordinary_shares)
                or not isinstance(country,str) or country.strip()!=issuer.registered_country):
            raise ValueError('qualified fixed ordinary-share or country basis changed')
    if not isinstance(published, str) or len(published) != 7 or not published.isascii() or not published.isdigit():
        raise ValueError('issuer master publication date unavailable')
    published_on = date(int(published[:3])+1911, int(published[3:5]), int(published[5:]))
    if not 0 <= (today-published_on).days <= 14:
        raise ValueError('issuer master publication stale')
    return meta


def _existing_annual(*, issuer_ticker=TICKER):
    """Hold an existing official annual original until its reuse is qualified.

    Reading a still valid core never licenses another request for that annual
    under a new key. This conservative branch neither deletes nor renews it.
    """
    issuer = consolidated_issuer(issuer_ticker)
    core = peek_cache_json('financial_data:' + issuer.ticker)
    if not isinstance(core, dict):
        return False
    audits = core.get('source_audit') or []
    return any(isinstance(audit, dict) and audit.get('source') == 'financial_statements'
               and audit.get('status') in {'success', 'degraded_enrichment'}
               and bool(audit.get('documents') or audit.get('recovered_documents'))
               for audit in audits if isinstance(audits, list))


def _cumulative_contract(raw):
    if not raw.rstrip().lower().endswith(b'</html>'):
        raise ValueError('public comparison homepage incomplete')
    soup = BeautifulSoup(raw.decode('utf-8', errors='strict'), 'html.parser')
    links = soup.select('a[name=IncomeStatement]')
    if len(links) != 1 or links[0].get_text(strip=True) != '綜合損益表(累計)':
        raise ValueError('cumulative income interpretation not published')


def _qualified_index(raw,year,quarters,observed,issuer_ticker,read_correction):
    from .gourmet_correction_notice import CorrectionRequired
    try:
        parse_calendar_index(raw,year,quarters,observed,issuer_ticker=issuer_ticker)
        return set()
    except CorrectionRequired as needed:
        # The exception is produced only after the complete index passes its
        # issuer/calendar/period/publication checks and publishes this action.
        key=f'correction:{needed.year}Q{needed.quarter}'
        request=spec('correction',peer_ticker=issuer_ticker,year=needed.year,
                     quarter=needed.quarter,published_action=needed.published_action)
        notice=read_correction(key,request)
        parse_calendar_index(raw,year,quarters,observed,issuer_ticker=issuer_ticker,
                             correction_originals={(needed.year,needed.quarter):notice})
        return {key}


def _replay(components, observed, *, now, issuer_ticker=TICKER):
    consolidated_issuer(issuer_ticker)
    def request_for(kind, **kwargs):
        return spec(kind, peer_ticker=issuer_ticker, **kwargs)
    def body(key, request):
        return receipt_body(components[key], request, now=now)
    reference = parse_reference(body('reference', request_for('reference', day=observed)), observed,
                                issuer_ticker=issuer_ticker)
    year, quarter = reference['year'], reference['quarter']
    periods = required_periods(year, quarter)
    years = sorted({y for y, _ in periods})
    expected = {'reference', 'home', 'methodology', *('index:'+str(y) for y in years),
                *(f'income:{y}Q{q}' for y, q in periods)}
    allowed=expected|({'correction:2025Q4'}if issuer_ticker=='2723.TW'else set())
    if not expected<=set(components)<=allowed:
        raise ValueError('required original set is incomplete or ambiguous')
    parse_methodology(body('methodology', request_for('methodology')))
    _cumulative_contract(body('home', request_for('home')))
    corrections=set()
    for y in years:
        corrections|=_qualified_index(body('index:'+str(y),request_for('index',year=y)),y,
            [q for yy,q in periods if yy==y],observed,issuer_ticker,body)
    if set(components)!=expected|corrections:
        raise ValueError('unpublished correction component supplied')
    incomes = {(y,q): parse_cumulative_income(body(f'income:{y}Q{q}', request_for('income', year=y, quarter=q)), y, q,
                                            issuer_ticker=issuer_ticker)
               for y, q in periods}
    return reference, derive_nonpositive_income(year, quarter, incomes)


def verified_reference_income(proof, *, ticker, observed_at, today=None):
    """Recompute from immutable complete originals and live independent owners."""
    try:
        today = today or _today()
        observed = _context(ticker, observed_at, today)
        if (not isinstance(proof, dict) or set(proof) != {
                'schema', 'ticker', 'observed_at', 'master', 'components', 'reference', 'derived'}
                or proof.get('schema') != SCHEMA or proof.get('ticker') != ticker
                or proof.get('observed_at') != observed_at
                or _master(today, issuer_ticker=ticker) != proof.get('master')):
            return None
        reference, derived = _replay(proof['components'], observed, now=time.time(), issuer_ticker=ticker)
        return derived if proof['derived'] == derived and proof['reference'] == reference else None
    except (ValueError, TypeError, KeyError, OSError, EOFError, OverflowError, AttributeError):
        return None


def collect_reference_income(ticker, observed_at, *, today=None, transport=None):
    if ticker != TICKER:
        from .ncc_mobile_peer_transport import peer_receipt_observation_enabled
        from provider_correlation import current_correlation, current_source_identity
        context = current_correlation()
        if (not peer_receipt_observation_enabled()
                or current_source_identity() != ('dynamic_peer_metrics', 'FinMind/yfinance')
                or not all(isinstance(context.get(key), str) and context[key]
                           for key in ('ticker', 'fetch_id', 'operation_id'))):
            raise ValueError('new consolidated acquisition requires the normal audited source operation')
    workflow_deadline = time.monotonic() + 20
    today = today or _today()
    observed = _context(ticker, observed_at, today)
    master = _master(today, issuer_ticker=ticker)
    if _existing_annual(issuer_ticker=ticker):
        raise ValueError('existing annual originals require qualified reuse before another annual fetch')
    http = transport or PeerIncomeHttp(seconds=max(0, workflow_deadline-time.monotonic()), peer_ticker=ticker)
    http.deadline = min(http.deadline, workflow_deadline)
    components = {}
    def request_for(kind, **kwargs):
        return spec(kind, peer_ticker=ticker, **kwargs)
    def get(key, request):
        raw, packet = http.get(request); components[key] = packet
        return raw
    reference = parse_reference(get('reference', request_for('reference', day=observed)), observed,
                                issuer_ticker=ticker)
    parse_methodology(get('methodology', request_for('methodology')))
    year, quarter = reference['year'], reference['quarter']
    periods = required_periods(year, quarter)
    for y in sorted({y for y, _ in periods}):
        _qualified_index(get('index:'+str(y),request_for('index',year=y)),y,
            [q for yy,q in periods if yy==y],observed,ticker,get)
    _cumulative_contract(get('home', request_for('home')))
    incomes = {(y,q): parse_cumulative_income(get(f'income:{y}Q{q}', request_for('income', year=y, quarter=q)), y, q,
                                            issuer_ticker=ticker)
               for y, q in periods}
    proof = {'schema': SCHEMA, 'ticker': ticker, 'observed_at': observed_at,
             'master': deepcopy(master), 'components': components, 'reference': reference,
             'derived': derive_nonpositive_income(year, quarter, incomes)}
    verified = verified_reference_income(proof, ticker=ticker, observed_at=observed_at, today=today)
    if time.monotonic() >= http.deadline or verified is None:
        raise ValueError('reference-income originals expired or changed before delivery')
    return {'reason': APPLICABILITY, 'observed_at': observed_at,
            'reference_quarter': reference['reference_quarter'],
            'period_start': proof['derived']['period_start'], 'period_end': proof['derived']['period_end'],
            'scope': 'consolidated_parent_income', 'currency': 'TWD',
            'source_url': spec('reference', day=observed)['url'],
            'reason_basis': 'derived_from_official_rule_and_period_bound_income; not_a_published_per_row_cause',
            'source_record_archive': proof}
