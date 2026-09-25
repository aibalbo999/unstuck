"""Company/time eligibility for acquired text; preserve rejected originals outside prompts."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import timedelta
import re

from news_record_utils import clean_text, parse_news_datetime, canonical_link


def company_aliases(data: dict) -> list[str]:
    identity = data.get('company_identity') or {}
    identity = identity if isinstance(identity, dict) else {}
    names = [identity.get(k) for k in ('official_name', 'legal_name', 'display_name')]
    names += list(identity.get('allowed_aliases') or []) + list(identity.get('english_names') or [])
    names += str(data.get('company_name') or '').split(' / ')
    ticker = str(data.get('ticker') or identity.get('ticker') or '').upper()
    forbidden = {clean_text(value).strip().strip('*').casefold()
                 for value in (identity.get('forbidden_aliases') or [])}
    aliases = []
    for value in names:
        name = clean_text(value).strip().strip('*').casefold()
        if len(name) < 2 or name in forbidden or name.upper() in {ticker, ticker.split('.')[0]} or name.isdigit():
            continue
        if name not in aliases:
            aliases.append(name)
    return aliases


def issuer_match(record: dict, data: dict) -> str | None:
    # URL parameters and publisher names are not issuer evidence. HTML attributes
    # are removed, so an unrelated anchor's href cannot create a match.
    text = clean_text(' '.join(str(record.get(k) or '') for k in ('title', 'headline', 'summary', 'snippet', 'text'))).casefold()
    for alias in company_aliases(data):
        if re.search(r'[\u3400-\u9fff]', alias):
            if alias in text:
                return alias
        elif re.search(r'(?<![\w])' + re.escape(alias) + r'(?![\w])', text):
            return alias
    ticker = str(data.get('ticker') or '').upper()
    stock_id = ticker.split('.')[0]
    if stock_id.isdigit():
        patterns = [rf'(?<!\d){re.escape(ticker)}(?!\w)' if '.' in ticker else r'(?!)',
                    rf'[（(]\s*{re.escape(stock_id)}\s*[)）]',
                    rf'(?:股票代[碼號]|代[碼號])\s*[:：]?\s*{re.escape(stock_id)}(?!\d)']
    elif len(stock_id) >= 2:
        patterns = [rf'(?<!\w)\${re.escape(stock_id)}(?!\w)',
                    rf'(?:NASDAQ|NYSE)\s*:\s*{re.escape(stock_id)}(?!\w)',
                    rf'\(\s*{re.escape(stock_id)}\s*\)']
    else:
        patterns = []
    return stock_id if any(re.search(p, text, re.I) for p in patterns) else None


def select_company_records(records, data: dict, *, cutoff=None, lookback_days=30, require_recent=True):
    from news_freshness_policy import news_cutoff
    reference = news_cutoff(cutoff)
    lower = reference - timedelta(days=max(1, int(lookback_days)))
    accepted, rejected, reasons, seen = [], [], Counter(), set()
    raw = [r for r in records or [] if isinstance(r, dict)]
    for original in raw:
        item = deepcopy(original)
        stamp = next((parsed for key in ('date','published_date','published_at','publication_date','pubDate')
                      if (parsed := parse_news_datetime(item.get(key))) is not None), None)
        reason = ''
        if require_recent:
            reason = 'unknown_date' if stamp is None else 'future' if stamp > reference else 'historical' if stamp < lower else ''
        match = issuer_match(item, data)
        if not reason and not match:
            reason = 'issuer_unverified'
        link = canonical_link(item.get('link') or item.get('url'))
        if not reason and not link:
            reason = 'invalid_link'
        key = (link, clean_text(item.get('title') or item.get('headline')).casefold())
        if not reason and key in seen:
            reason = 'duplicate'
        if reason:
            reasons[reason] += 1
            rejected.append({'reason':reason, 'record':item})
        else:
            seen.add(key)
            item.update(issuer_match=match, content_coverage='text_available' if item.get('text') else 'headline_or_snippet')
            accepted.append(item)
    audit = {'raw_count':len(raw), 'usable_count':len(accepted), 'rejected_count':len(rejected),
             'rejected_reason_counts':dict(reasons), 'selection_cutoff':reference.isoformat(),
             'selection_policy':'company-time-v1', 'retrieval_status':'records_received' if raw else 'no_records',
             'quality_status':'eligible_evidence' if accepted else 'no_eligible_evidence',
             'coverage_status':'partial' if rejected or not accepted else 'success',
             'source_record_archive':rejected}
    return accepted, audit


def annotate_result(result, data: dict, *, cutoff=None):
    """Apply text selection without converting retrieval failure into valid empty."""
    records, selection = select_company_records(result.value, data, cutoff=cutoff)
    result.value = records
    retrieval = result.audit.get('retrieval_status') or (result.status if result.status not in {'success', 'degraded_enrichment'} else selection['retrieval_status'])
    result.audit.update(selection, record_count=len(records), retrieval_status=retrieval)
    if result.status in {'success','degraded_enrichment'}:
        result.status = 'success' if records and not selection['rejected_count'] else 'degraded_enrichment'
        result.audit['status'] = result.status
    return result


def reselect_social_context(data: dict, *, cutoff=None):
    social = data.get('social_sentiment')
    if not isinstance(social, dict):
        return
    channels = ('dcard', 'mobile01', 'pttweb', 'ptt_stock_direct')
    original = [dict(r, social_channel=c) for c in channels for r in (social.get(c) or []) if isinstance(r,dict)]
    original += [r['record'] for r in social.get('source_record_archive',[]) if isinstance(r,dict) and isinstance(r.get('record'),dict)]
    selected, audit = select_company_records(original, data, cutoff=cutoff)
    updated = deepcopy(social)
    updated.update({c:[r for r in selected if r['social_channel']==c] for c in channels})
    updated.update(audit, sample_count=len(selected), status='partial' if audit['rejected_count'] else 'success' if selected else 'empty_unknown')
    data['social_sentiment'] = updated
    if isinstance(data.get('sentiment_context'), dict):
        data['sentiment_context'] = {**data['sentiment_context'], 'social_sentiment':updated}
