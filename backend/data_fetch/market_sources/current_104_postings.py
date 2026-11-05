"""Current publisher-enabled ads; pure parsing is not native acquisition proof.

This is separate from the unchanged recent30-day posting contract. Source dates
are appear/update dates, not verified first publication or new hiring demand.
"""
from dataclasses import dataclass,asdict
from datetime import datetime
from hashlib import sha256
import json
import math
import re
import time
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

POLICY='104-current-enabled-advertisements:v1'
MIXED_POLICY='104-current-enabled-advertisements:mixed-expiry:v2'
MAX_LIST_BYTES=300000
MAX_DETAIL_BYTES=150000
MAX_SAMPLES=5
TZ=ZoneInfo('Asia/Taipei')

class SnapshotError(ValueError):
    def __init__(self,reason):
        self.reason=reason
        super().__init__(reason)

def _unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise SnapshotError('duplicate_json_key')
        result[k]=v
    return result

def _json(raw,maximum):
    if not isinstance(raw,bytes)or not 0<len(raw)<=maximum:raise SnapshotError('original_body_size')
    try:
        p=json.loads(raw.decode('utf8','strict'),object_pairs_hook=_unique,
                     parse_constant=lambda _:(_ for _ in ()).throw(SnapshotError('nonfinite_json')))
    except (UnicodeError,ValueError,RecursionError)as exc:
        if isinstance(exc,SnapshotError):raise
        raise SnapshotError('original_json_invalid')from None
    if not isinstance(p,dict)or set(p)!={'data','metadata'}or not isinstance(p['data'],dict)or not isinstance(p['metadata'],dict):
        raise SnapshotError('original_envelope')
    return p['data']

def _text(value,maximum):
    if not isinstance(value,str)or not 0<len(value.strip())<=maximum:raise SnapshotError('original_text')
    return value.strip()

def _day(value):
    if not isinstance(value,str)or not re.fullmatch(r'20[0-9]{2}/[0-9]{2}/[0-9]{2}',value):raise SnapshotError('source_date_format')
    try:return datetime.strptime(value,'%Y/%m/%d').date()
    except ValueError:raise SnapshotError('source_date_invalid')from None

def _deadline(value):
    # The publisher uses ISO dates for closeDate and slash dates for headers.
    if isinstance(value,str)and re.fullmatch(r'20[0-9]{2}-[0-9]{2}-[0-9]{2}',value):
        return _day(value.replace('-','/'))
    return _day(value)

@dataclass(frozen=True)
class Posting:
    job_id:str
    title:str
    url:str
    employer:str
    source_employer:str
    source_enabled_state:str
    source_appear_or_update_date:str
    source_date_age_days:int
    deadline:str|None
    deadline_provided:bool
    description_character_count:int
    description_sha256:str

@dataclass(frozen=True)
class ParsedSnapshot:
    ticker:str
    company_name:str
    official_short_name:str
    official_ubn:str
    source_company_id:str
    observed_at_epoch:float
    postings:tuple[Posting,...]
    selected_job_ids:tuple[str,...]=()
    excluded_postings:tuple[dict,...]=()

    def public_value(self):
        value={'schema':POLICY,'status':'parsed_unverified',
            'ticker':self.ticker,'company_name':self.company_name,'official_ubn':self.official_ubn,
            'source_company_id':self.source_company_id,'observed_at_epoch':self.observed_at_epoch,
            'source':'104 publisher-enabled company advertisements',
            'query_scope':'exact_company_current_enabled_advertisements',
            'coverage_status':'bounded_enabled_advertisement_sample','record_unit':'advertised_posting',
            'observed_sample_posting_count':len(self.postings),'job_postings':[asdict(p)for p in self.postings],
            'job_count':None,'current_open_job_count':None,'recent_company_job_count':None,'hiring_headcount':None,
            'first_publication_verified':False,'hiring_growth_verified':False,'native_originals_verified':False,
            'source_date_kind':'publisher_appear_or_update_date_not_first_publication',
            'message':'僅為當時公開啟用的徵才廣告樣本；來源日期可能為更新日，不代表首次刊登、近30天新職缺、實際缺額人數或擴編。截止日未提供者保持未知；原件與身分證據需另行核實。'}
        if self.excluded_postings:
            value.update(schema=MIXED_POLICY,selected_detail_count=len(self.selected_job_ids),
                         selected_job_ids=list(self.selected_job_ids),
                         excluded_postings=[dict(p)for p in self.excluded_postings])
            value['message']+='固定選中的完整廣告原件含明示已到期紀錄；已另列排除理由，不計入合格樣本，並非全部廣告或缺額總量。'
        return value


def parse_snapshot(listing_raw,detail_bodies,*,issuer,observed_at,now=None):
    from alternative_data_fetcher import _base36,_official_104_employer_label
    now=time.time()if now is None else now
    if (type(observed_at)not in(int,float)or type(now)not in(int,float)
        or not math.isfinite(observed_at)or not math.isfinite(now)or not 0<observed_at<=now):
        raise SnapshotError('observation_time')
    try:today=datetime.fromtimestamp(observed_at,TZ).date()
    except (OverflowError,ValueError,OSError):raise SnapshotError('observation_time')from None
    if not isinstance(issuer,dict):raise SnapshotError('issuer_context')
    ticker=issuer.get('ticker');legal=issuer.get('legal_name');short=issuer.get('official_short_name');ubn=issuer.get('official_ubn')
    if (not isinstance(ticker,str)or not re.fullmatch(r'[1-9][0-9]{3,5}\.(TW|TWO)',ticker)or ticker.startswith('91')
        or not isinstance(legal,str)or not 4<=len(legal)<=100 or not legal.endswith('股份有限公司')
        or not isinstance(short,str)or not 1<=len(short)<=50
        or not isinstance(ubn,str)or not re.fullmatch(r'[0-9]{8}',ubn)or int(ubn)<=0):
        raise SnapshotError('issuer_context')
    company_id=_base36(int(str(int(ubn))+'000'));company_url='https://www.104.com.tw/company/'+company_id
    listing=_json(listing_raw,MAX_LIST_BYTES)
    if (any(type(listing.get(k))is not int for k in('totalCount','totalPages','page','pageSize'))
        or not 1<=listing['totalCount']<=100000 or not 1<=listing['totalPages']<=10000
        or listing['page']!=1 or not 1<=listing['pageSize']<=100):raise SnapshotError('listing_pagination')
    cards=listing.get('list')
    if not isinstance(cards,dict)or not all(isinstance(cards.get(k),list)for k in('topJobs','normalJobs')):raise SnapshotError('listing_rows')
    rows=cards['topJobs']+cards['normalJobs']
    if not 1<=len(rows)<=100:raise SnapshotError('listing_rows')
    seen={}
    for row in rows:
        if not isinstance(row,dict):raise SnapshotError('listing_row')
        ident=row.get('jobNo');title=_text(row.get('jobName'),200);stamp=row.get('appearDate')
        if (not isinstance(ident,str)or not re.fullmatch(r'[a-z0-9]{3,12}',ident)
            or row.get('jobUrl')!='https://www.104.com.tw/job/'+ident
            or not isinstance(stamp,str)or not re.fullmatch(r'[0-9]{1,2}/[0-9]{1,2}',stamp)):
            raise SnapshotError('listing_identity_or_date')
        compact=(title,row['jobUrl'],stamp)
        if ident in seen and seen[ident]!=compact:raise SnapshotError('conflicting_listing_duplicate')
        seen.setdefault(ident,compact)
    if listing['totalCount']<len(seen):raise SnapshotError('listing_count_inconsistent')
    selected=list(seen)[:MAX_SAMPLES]
    if not isinstance(detail_bodies,dict)or set(detail_bodies)!=set(selected):raise SnapshotError('selected_detail_set')
    postings=[];excluded=[]
    for ident in selected:
        d=_json(detail_bodies[ident],MAX_DETAIL_BYTES);h=d.get('header')
        if d.get('switch')!='on':raise SnapshotError('publisher_not_enabled')
        if not isinstance(h,dict)or d.get('custNo')!=company_id or h.get('custUrl')!=company_url:
            raise SnapshotError('detail_company_identity')
        title,job_url,listed_stamp=seen[ident]
        employer=_text(h.get('custName'),200)
        if h.get('jobName')!=title or not _official_104_employer_label(legal,short,employer,official_ubn=ubn):raise SnapshotError('detail_title_or_employer')
        appeared=_day(h.get('appearDate'))
        if appeared>today or tuple(map(int,listed_stamp.split('/')))!=(appeared.month,appeared.day):raise SnapshotError('listing_detail_date')
        if 'closeDate'not in d or not isinstance(d['closeDate'],str):raise SnapshotError('deadline_observation_missing')
        deadline=None;expired=False
        if d['closeDate']:
            ending=_deadline(d['closeDate'])
            expired=ending<=today
            deadline=ending.isoformat()
        detail=d.get('jobDetail');description=detail.get('jobDescription')if isinstance(detail,dict)else None
        if not isinstance(description,str):raise SnapshotError('concrete_description_missing')
        soup=BeautifulSoup(description,'html.parser')
        for node in soup(['script','style','noscript']):node.decompose()
        text=' '.join(soup.get_text(' ',strip=True).split())
        if not 20<=len(text)<=20000:raise SnapshotError('concrete_description_missing')
        pool=r'人才庫|履歷(?:資料)?庫|(?:無|暫無)(?:實際|現有|任何)?職缺|(?:常年|歡迎常年).{0,12}投遞履歷|talent pool|not currently recruiting'
        if re.search(pool,title+' '+text,re.I):raise SnapshotError('talent_pool_not_posting')
        if expired:
            # Exclude only a fully validated, explicitly past deadline. No
            # malformed/identity/content error is downgraded to a skipped row.
            excluded.append({'job_id':ident,'url':job_url,'deadline':deadline,
                             'reason_code':'deadline_not_proven_future'})
            continue
        postings.append(Posting(ident,title,job_url,legal,employer,'on',appeared.isoformat(),(today-appeared).days,
            deadline,bool(d['closeDate']),len(text),sha256(text.encode()).hexdigest()))
    if not postings:raise SnapshotError('deadline_not_proven_future')
    return ParsedSnapshot(ticker,legal,short,ubn,company_id,float(observed_at),tuple(postings),tuple(selected),tuple(excluded))
