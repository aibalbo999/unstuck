"""Bounded, dated observations for the mode-D visible source contract."""
from datetime import date
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urlparse
from short_term_events import parse_market_date


def recent_news_evidence(data, as_of):
    """A publication is past news, never evidence of a scheduled future event."""
    ticker = str(data.get('ticker') or '').split('.')[0]
    records = []
    raw = data.get('recent_catalysts')
    for item in (raw if isinstance(raw, list) else [])[:30]:
        if not isinstance(item, dict):
            continue
        published = parse_market_date(item.get('date'))
        if published is None:
            try:
                published = parsedate_to_datetime(str(item.get('date'))).date()
            except (TypeError, ValueError, OverflowError):
                continue
        title, provider = str(item.get('title') or ''), str(item.get('source') or '')
        link = str(item.get('link') or item.get('url') or '')
        # Search-result provenance is not enough to infer issuer relevance.
        if (not ticker or not re.search(r'(?<![A-Za-z0-9])'+re.escape(ticker)+r'(?![A-Za-z0-9])', title)
                or not provider or not 0 <= (as_of-published).days <= 14
                or urlparse(link).scheme not in {'http', 'https'} or not urlparse(link).netloc):
            continue
        records.append({'title':title[:500], 'published_at':published.isoformat(),
                        'provider':provider[:240], 'url':link[:2000], 'ticker':str(data.get('ticker')),
                        'evidence_role':'reported_news_not_scheduled_event'})
        if len(records) == 5:
            break
    return {'items':records, 'availability':'available' if records else 'unavailable'}


def add_catalog_observations(value, data):
    as_of = parse_market_date(value.get('as_of')) or date.today()
    value['ticker'] = str(data.get('ticker') or '')
    value['recent_news'] = recent_news_evidence(data, as_of)
    value['ownership_evidence'] = ownership_evidence(data, as_of)
    # Explicit units/populations come from the same validator used for prose.
    from institutional_evidence import institutional_evidence_records
    records = institutional_evidence_records(data)
    records = [r for r in records if parse_market_date(r.get('observed_at')) is not None
               and 0 <= (as_of-parse_market_date(r['observed_at'])).days <= 7]
    value['institutional_evidence'] = {'records':records, 'availability':'available' if records else 'unavailable'}
    return value


def ownership_evidence(data, as_of):
    chip = data.get('chip_data') or {}
    tdcc = chip.get('tdcc_shareholder_distribution') or {}
    observed = parse_market_date(tdcc.get('as_of_date'))
    records = []
    if (tdcc.get('status') == 'success' and tdcc.get('source') and observed
            and 0 <= (as_of-observed).days <= 14):
        for field, population, threshold in [('major_holders_gt_1000_lots_pct','major_holders','gt_1000_lots'),
                                             ('retail_holders_lt_50_lots_pct','retail_holders','lt_50_lots')]:
            value = tdcc.get(field)
            if isinstance(value,(int,float)) and not isinstance(value,bool) and 0 <= value <= 100:
                records.append({'value':value,'unit':'percent','population':population,'threshold':threshold,
                                'observed_at':observed.isoformat(),'provider':tdcc['source'],
                                'window':{'kind':'point_in_time'},'path':'chip_data.tdcc_shareholder_distribution.'+field})
    return {'records':records, 'availability':'available' if records else 'unavailable'}


def ownership_claim_supported(text, records):
    """One observation cannot establish increasing/decreasing ownership."""
    if re.search(r'增加|減少|上升|下降|集中|連續|持續|增持|減持|加碼|減碼|買超|賣超|improv|increas|decreas', text, re.I):
        return False
    dates = re.findall(r'20\d{2}[-/]\d{1,2}[-/]\d{1,2}', text)
    if any(parse_market_date(day) is None or not any(r.get('observed_at') == parse_market_date(day).isoformat() for r in records) for day in dates):
        return False
    for clause in re.split(r'[，。；;\n]', text):
        if not re.search(r'大戶|散戶', clause):
            continue
        for match in re.finditer(r'(\d[\d,]*(?:\.\d+)?)(千|萬)?(股|張)', clause):
            amount, scale, unit = match.groups()
            lots = float(amount.replace(',', '')) * {'':1, None:1, '千':1000, '萬':10000}[scale] / (1000 if unit == '股' else 1)
            before, after = clause[:match.start()], clause[match.end():]
            major = lots == 1000 and bool(re.search(r'超過$|逾$|大於$', before) or re.match(r'大戶', after))
            retail = lots == 50 and bool(re.search(r'不足$|未滿$|低於$', before))
            group = 'major_holders' if '大戶' in clause else 'retail_holders'
            if not any(r.get('population') == group and ((r.get('threshold')=='gt_1000_lots' and major) or (r.get('threshold')=='lt_50_lots' and retail)) for r in records):
                return False
    for year, month, day in re.findall(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', text):
        try:
            observed = date(int(year),int(month),int(day)).isoformat()
        except ValueError:
            return False
        if not any(r.get('observed_at') == observed for r in records):
            return False
    claims = re.findall(r'(大戶|散戶)[^，。；;]{0,28}?(\d+(?:\.\d+)?)\s*[%％]', text)
    if not claims:
        return False
    for group, raw in claims:
        population = 'major_holders' if group == '大戶' else 'retail_holders'
        if not any(r.get('population')==population and r.get('unit')=='percent'
                   and abs(r['value']-float(raw)) <= 0.01 for r in records):
            return False
    return True


def institutional_catalyst_has_numeric_claim(text):
    """Do not turn an arbitrary flow record into proof of a qualitative trend."""
    if re.search(r'連續|持續|逐日|加速|趨勢|轉買|轉賣', text):
        return False
    populations = list(re.finditer(r'三大法人|三類法人|法人合計|法人總計|法人(?!說明會)|外資|投信|自營商', text))
    if not populations:
        return False
    for i, population in enumerate(populations):
        fragment = text[population.end():populations[i+1].start() if i+1<len(populations) else len(text)]
        if not re.search(r'(?:買超|賣超|買賣超|淨買入|淨賣出)[^\d。；;]{0,15}[+-]?\d[\d,.]*\s*(?:千|萬)?(?:股|張)', fragment):
            return False
    return True



INSTITUTIONAL_PROMPT_RULE = (
    '【法人與籌碼來源語意】institutional_trading 中 *_thousand_shares 的單位是千股，不是千張；'
    '台股1張=1000股，千股與張數值相同，千張必須再除1000。'
    'total及last_5_trading_days是法人合計，不是外資分項；by_category 的期間由lookback_trading_days限定，不能當單日或5日。'
    'daily_total只支持該日法人合計。數值、正負、主體、日期與期間均須相符；單筆持股比例不能證明增加或集中趨勢。'
    '資料缺失或單位/日期不明時保留未知，禁止借用其他分項或把null當0。'
)


def news_catalyst_supported(text, records):
    """News refs support attributed literal titles, never scheduled-event assertions."""
    if re.search(r'將於|將在|已排定|確定舉行|明日|明天|下週|scheduled', text, re.I):
        return False
    return bool(records) and all(isinstance(r, dict) and r.get('title') and r['title'] in text for r in records)
