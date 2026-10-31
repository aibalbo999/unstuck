"""Company/time eligibility for acquired text; preserve rejected originals outside prompts."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import timedelta
import re
from urllib.parse import urlsplit

from news_record_utils import clean_text, parse_news_datetime, canonical_link
from news_source_roles import is_finmind_forum_news_record, is_finmind_stock_overview_record


def company_aliases(data: dict) -> list[str]:
    identity = data.get('company_identity') or {}
    identity = identity if isinstance(identity, dict) else {}
    ticker = str(data.get('ticker') or identity.get('ticker') or '').upper()
    names = ['世紀民生'] if ticker == '5314.TWO' else []
    from company_news_queries import context_bound_search_alias, context_bound_bank_news_aliases
    names += context_bound_bank_news_aliases(data)
    news_alias = context_bound_search_alias(data)
    if news_alias:
        names.append(news_alias)
    names += [identity.get(k) for k in ('official_name', 'legal_name', 'display_name')]
    names += list(identity.get('allowed_aliases') or []) + list(identity.get('english_names') or [])
    names += str(data.get('company_name') or '').split(' / ')
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


def _broker_article_targets_other_stock(record: dict, data: dict) -> bool:
    """Reject explicit other-stock subjects in generic 2855 news metadata.

    A broker's analyst credit is not news about the brokerage itself. Direct
    social samples and typed original receipts retain their own validators.
    """
    if (str(data.get('ticker') or '').upper() != '2855.TW' or record.get('social_channel')
            or any(k in record for k in ('tdr_mops_receipt', 'trading_notice_receipt',
                                         'ltn_original_receipt', 'cmoney_stock_context',
                                         'sgx_issuer_receipt', 'issuer_news_receipt'))):
        return False
    title = clean_text(record.get('title') or record.get('headline'))
    if not re.search(r'統一(?:綜合)?證券', title):
        return False
    publisher = clean_text(record.get('publisher') or record.get('source')).casefold()
    if 'cmoney' in publisher and '股市爆料同學會' in title:
        # A board tag alone can accompany the broker's own results. Require
        # an analyst attribution, and keep explicit year labels as dates.
        subject = re.match(r'^\s*(\d{4,6})\s+([^\r\n\-–—－]{1,40})\s*[-–—－]\s*'
                           r'統一(?:綜合)?證券\s*[:：]', title)
        year_label = subject and re.match(r'^年(?:\s|度|初|底|第|統一(?:綜合)?證券)', subject[2].strip())
        if subject and not year_label and int(subject[1]) != 2855:
            return True
    # The other issuer must be the report's direct object. Do not cross a
    # financial-results clause and borrow a ticker from an attached report.
    report = re.search(r'^統一(?:綜合)?證券\s*(?:剛剛|今日|近日)?\s*'
                       r'(?:發布|發佈)(?:了)?(?:一份)?\s*'
                       r'[^（()）、，。；;：:\r\n]{1,50}[（(](\d{4,6})[）)]\s*'
                       r'(?:的)?\s*券商報告', title)
    return bool(report and int(report[1]) != 2855)


def _bank_authored_market_commentary(record: dict, data: dict) -> bool:
    """FEIB's credited FX column is evidence about currencies, not the bank."""
    if (str(data.get('ticker') or '').upper() != '2845.TW' or record.get('social_channel')
            or any(k in record for k in ('tdr_mops_receipt', 'trading_notice_receipt',
                                         'ltn_original_receipt', 'cmoney_stock_context',
                                         'sgx_issuer_receipt', 'issuer_news_receipt'))):
        return False
    publisher = clean_text(record.get('publisher') or record.get('source')).casefold()
    if publisher not in {'鉅亨網', '鉅亨網新聞中心', 'cnyes', 'news.cnyes.com', 'm.cnyes.com'}:
        return False
    title = clean_text(record.get('title') or record.get('headline'))
    column = re.match(r'^\s*【遠東商銀】\s*(.+)', title)
    if not column:
        return False
    subject = column[1]
    # Currency profit-taking/retracement is not the bank's own earnings.
    if re.search(r'遠銀|遠東商銀|本行|分行|營收|淨利|EPS|存款|信貸|聯貸|信用卡', subject, re.I):
        return False
    return bool(re.search(r'美元|日圓|澳幣|英鎊|歐元|\b(?:FED|BOJ|RBA)\b', subject, re.I))


def issuer_match(record: dict, data: dict, *, today=None) -> str | None:
    if ('mops_json_receipt' in record or record.get('source_type') == 'mops_issuer_announcement'
            or record.get('source_document_url') == 'https://mops.twse.com.tw/mops/api/t05st01_detail'
            or record.get('issuer_evidence_basis') == 'verified_mops_json_original'):
        from data_fetch.market_sources.mops_json_company_history import verified_json_record
        return verified_json_record(record, data)
    if ('tdr_mops_receipt' in record or record.get('source_type') == 'tdr_foreign_issuer_announcement'
            or record.get('source') == 'MOPS TDR issuer announcements'
            or record.get('issuer_evidence_basis') == 'verified_mops_tdr_original'):
        from data_fetch.market_sources.tdr_mops_history import verified_tdr_record
        return verified_tdr_record(record, data)
    if ('trading_notice_receipt' in record or record.get('source_type') == 'official_trading_risk_notice'
            or record.get('source') == 'TWSE 官方注意交易公告'
            or record.get('source_role') == 'exchange_trading_risk_notice'):
        from data_fetch.market_sources.twse_trading_notices import verified_notice_record
        return verified_notice_record(record,data)
    if ('ltn_original_receipt' in record or record.get('source_type') == 'publisher_original_news'
            or record.get('issuer_evidence_basis') == 'verified_ltn_publisher_original'):
        from data_fetch.market_sources.ltn_stock_news import verified_ltn_record
        return verified_ltn_record(record, data)
    if "cmoney_stock_context" in record or record.get("issuer_evidence_basis") == "verified_cmoney_single_stock_context":
        from data_fetch.market_sources.cmoney_stock_context import verified_stock_context
        return verified_stock_context(record, data)
    if "sgx_issuer_receipt" in record or record.get("source_type") == "foreign_exchange_issuer_announcement":
        from data_fetch.market_sources.sgx_issuer_news import verified_sgx_issuer_news
        return verified_sgx_issuer_news(record, data)
    if ("issuer_news_receipt" in record or record.get("source_type") in {"first_party_issuer_news", "issuer_hosted_press_republication", "group_published_issuer_news"}
            or record.get("source_role") in {"issuer_hosted_press_republication", "related_group_statement"}
            or record.get("publication_date_basis") == "group_page_displayed_day"
            or record.get("publication_date_basis") == "issuer_republication"):
        from data_fetch.market_sources.issuer_news import verified_issuer_news
        return verified_issuer_news(record, data, today=today)
    if _broker_article_targets_other_stock(record, data) or _bank_authored_market_commentary(record, data):
        return None
    # URL parameters and publisher names are not issuer evidence. HTML attributes
    # are removed, so an unrelated anchor's href cannot create a match.
    text = clean_text(' '.join(str(record.get(k) or '') for k in ('title', 'headline', 'summary', 'snippet', 'text'))).casefold()
    ticker = str(data.get('ticker') or '').upper()
    stock_id = ticker.split('.')[0]
    for alias in company_aliases(data):
        # 5314's two-character exchange shorthand is not issuer evidence by
        # itself; preserve direct stock-board posts that also state its code.
        if ticker == '5314.TWO' and alias == '世紀' and not re.search(r'(?<!\d)5314(?!\d)', text):
            continue
        if re.search(r'[\u3400-\u9fff]', alias):
            if alias in text:
                return alias
        elif re.search(r'(?<![\w])' + re.escape(alias) + r'(?![\w])', text):
            return alias
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


def _forum_original_unverified(item: dict, link: str) -> bool:
    if item.get('social_channel') not in {'dcard', 'mobile01', 'pttweb'}:
        return False
    parsed = urlsplit(link)
    host = (parsed.hostname or '').lower()
    # Google News timestamps describe indexing, not the original post. Its
    # wrapper can also point to a topic or job board instead of a stock post.
    if host == 'news.google.com':
        return True
    return host in {'dcard.tw', 'www.dcard.tw'} and parsed.path.startswith('/topics/')


def _indexed_non_article_unverified(item: dict, link: str) -> bool:
    """Known non-article roles cannot supply recent news evidence.

    A Google indexing date cannot substantiate a current stock overview or
    forum post. Keep editorial metadata and separately verified direct social
    samples on their existing paths; this does not infer an original URL.
    """
    parsed = urlsplit(link)
    host = (parsed.hostname or '').lower()
    if host in {'moneydj.com', 'www.moneydj.com'} and parsed.path.casefold() == '/kmdj/wiki/wikiviewer.aspx':
        return True
    if host != 'news.google.com':
        return False
    publisher = clean_text(item.get('publisher') or item.get('source')).casefold()
    title = clean_text(item.get('title') or item.get('headline'))
    if publisher in {'moneydj', 'moneydj理財網'}:
        # Observed legal-name-only RSS entry resolves to the company wiki.
        # Its update date does not establish a dated news event.
        return bool(re.fullmatch(r'[^\s，。:：]+股份有限公司\s*[-–—－]\s*MoneyDJ(?:理財網)?', title, re.I))
    if publisher == 'biggo 財經':
        # Observed RSS title is a quote index, not an original news article.
        return bool(re.fullmatch(
            r'.+?\s*[|｜]\s*\d{4,6}\.(?:TW|TWO)\s+股價走勢與即時報價'
            r'\s*[-–—－]\s*BigGo\s+財經', title, re.I))
    if publisher == 'tradingview':
        # This captured stock-statistics title identifies an indexed metric
        # page. Its RSS date cannot establish a news publication or event.
        return bool(re.fullmatch(
            r'.+?的股東人數\s*[-–—－]\s*(?:TWSE|TPEX):\d{4,6}'
            r'(?:\s*[-–—－]\s*TradingView)?', title, re.I))
    if publisher != 'cmoney':
        return False
    return bool(re.search(r'[-–—－]\s*股市爆料同學會(?:\s*[-–—－]\s*CMoney)?$', title, re.I)
                or re.fullmatch(r'.+?[（(]\d{4,6}[)）]\s*個股概覽\s*[|｜]\s*個股\s*[-–—－]\s*股市(?:\s*[-–—－]\s*CMoney)?', title, re.I))


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
        if not reason and item.get('social_channel') == 'yahoo_stock_direct':
            from data_fetch.market_sources.yahoo_stock_comments import verified_sample
            if not verified_sample(item, data):
                reason = 'yahoo_board_receipt_unverified'
        from zoneinfo import ZoneInfo
        match = issuer_match(item, data, today=reference.astimezone(ZoneInfo('Asia/Taipei')).date())
        if not reason and not match:
            reason = 'issuer_not_subject' if (_broker_article_targets_other_stock(item, data)
                                            or _bank_authored_market_commentary(item, data)) else 'issuer_unverified'
        link = canonical_link(item.get('link') or item.get('url'))
        if not reason and not link:
            reason = 'invalid_link'
        if not reason and is_finmind_forum_news_record(item, link):
            reason = 'forum_post_is_not_news'
        if not reason and is_finmind_stock_overview_record(item, link):
            reason = 'stock_overview_is_not_news'
        if not reason and _indexed_non_article_unverified(item, link):
            reason = 'indexed_non_article_unverified'
        if not reason and _forum_original_unverified(item, link):
            reason = 'forum_original_unverified'
        event_link = link
        if item.get('source_type') == 'mops_issuer_announcement' and not reason:
            from data_fetch.market_sources.mops_json_company_history import announcement_link_identity
            event_link = announcement_link_identity(item) or link
        key = ((item.get('message_board_id'), item.get('message_id'))
               if item.get('social_channel') == 'yahoo_stock_direct' and not reason else
               (event_link, clean_text(item.get('title') or item.get('headline')).casefold()))
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
    channels = ('dcard', 'mobile01', 'pttweb', 'ptt_stock_direct', 'cmoney_stock_direct', 'yahoo_stock_direct')
    original = [dict(r, social_channel=c) for c in channels for r in (social.get(c) or []) if isinstance(r,dict)]
    original += [r['record'] for r in social.get('source_record_archive',[]) if isinstance(r,dict) and isinstance(r.get('record'),dict)]
    selected, audit = select_company_records(original, data, cutoff=cutoff)
    updated = deepcopy(social)
    updated.update({c:[r for r in selected if r['social_channel']==c] for c in channels})
    updated.update(audit, sample_count=len(selected), status='partial' if audit['rejected_count'] else 'success' if selected else 'empty_unknown')
    data['social_sentiment'] = updated
    if isinstance(data.get('sentiment_context'), dict):
        data['sentiment_context'] = {**data['sentiment_context'], 'social_sentiment':updated}
