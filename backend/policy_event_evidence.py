"""Bound Chinese Fed action-date claims to replayed official statement originals."""
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import re

_SUBJECT = r'(?:美國聯準會|聯準會|Federal\s+Reserve|FOMC|Fed)'
_DATE = r'(?P<year>20\d{2})\s*(?:年|[-/])\s*(?P<month>\d{1,2})\s*(?:(?:月|[-/])\s*(?P<day>\d{1,2})\s*日?|月)?'
_ACTION = r'(?P<action>升息|加息|降息|調降利率|維持利率不變)'
_PATTERNS = (re.compile(_SUBJECT+r'[^。；;\n]{0,24}?'+_DATE+r'[^。；;\n]{0,16}?'+_ACTION,re.I),
             re.compile(_DATE+r'[^。；;\n]{0,12}?'+_SUBJECT+r'[^。；;\n]{0,20}?'+_ACTION,re.I))

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.skip=0; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','noscript'}: self.skip+=1
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript'} and self.skip: self.skip-=1
    def handle_data(self,value):
        if not self.skip: self.parts.append(value)

def qualified_policy_statement(item, *, as_of=None):
    """An annotation alone never grants a date; replay the canonical raw archive."""
    if not isinstance(item,dict): return None
    supplied=item.get('official_policy_reference')
    if not isinstance(supplied,dict): return None
    proof=dict(supplied)
    if (proof.get('status')!='archived' or type(proof.get('http_status'))is not int
            or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'):
        return None
    try:
        url=urlsplit(proof['source_url'])
        match=re.fullmatch(r'/newsevents/pressreleases/monetary(20\d{6})a\.htm',url.path)
        if (url.scheme!='https' or url.hostname!='www.federalreserve.gov' or url.port not in (None,443)
                or url.username or url.password or url.query or url.fragment or not match): return None
        receipt=proof.get('original_http_receipt')
        if (not isinstance(receipt,dict) or receipt.get('request_sent')is not True
                or receipt.get('response_complete')is not True or receipt.get('cache_hit')is not False
                or receipt.get('method')!='GET' or receipt.get('source_url')!=proof['source_url']
                or type(receipt.get('http_status'))is not int or receipt['http_status']!=200
                or receipt.get('response_sha256')!=proof.get('raw_response_sha256')
                or receipt.get('response_bytes')!=proof.get('raw_response_bytes')):return None
        date=datetime.strptime(match[1],'%Y%m%d').date()
        digest=proof['raw_response_sha256']
        if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest): return None
        from runtime_paths import current_runtime_paths
        expected=current_runtime_paths().cache_dir/'official-response-evidence'/(digest+'.gz')
        if proof.get('raw_response_path') and Path(proof['raw_response_path']).resolve()!=expected.resolve(): return None
        proof['raw_response_path']=str(expected)
        from official_response_evidence import read_response
        raw=read_response(proof,max_bytes=1024*1024)
        if type(proof.get('raw_response_bytes'))is not int or len(raw)!=proof['raw_response_bytes'] or not raw.rstrip().lower().endswith(b'</html>'): return None
        parser=_Text();parser.feed(raw.decode('utf-8'));text=re.sub(r'\s+',' ',' '.join(parser.parts))
        if ('Federal Reserve issues FOMC statement'not in text or 'Board of Governors of the Federal Reserve System'not in text
                or ('January','February','March','April','May','June','July','August','September','October','November','December')[date.month-1]+' '+str(date.day)+', '+str(date.year)not in text): return None
        actions=re.findall(r'The Committee decided to (raise|lower|maintain) the target range for the federal funds rate',text)
        if len(actions)!=1:return None
        release=re.search(r'For release at 2:00 p\.m\. (EDT|EST)',text)
        if release is None:return None
        released=datetime(date.year,date.month,date.day,14,tzinfo=ZoneInfo('America/New_York'))
        if released.tzname()!=release[1]:return None
        if as_of is None:cutoff=datetime.now(timezone.utc)
        elif isinstance(as_of,str):
            cutoff=datetime.fromisoformat(as_of.replace('Z','+00:00'))
            if cutoff.tzinfo is None:cutoff=cutoff.replace(tzinfo=timezone.utc)
        else:return None
        if released>cutoff:return None
        return {'decision_date':date.isoformat(),'action':actions[0],
                'published_at':released.astimezone(timezone.utc).isoformat(),
                'source_url':proof['source_url'],'raw_response_sha256':digest,
                'historical_first_availability_verified':False,'native_acquisition':False}
    except (KeyError,TypeError,ValueError,OSError,UnicodeError,EOFError):
        return None

def policy_event_date_issues(text, items, *, as_of=None):
    """Metadata dates cannot certify policy action dates; explicit uncertainty survives."""
    facts=[fact for item in items if (fact:=qualified_policy_statement(item,as_of=as_of))]
    issues=[];seen=set()
    for pattern in _PATTERNS:
        for match in pattern.finditer(str(text or '')):
            before=str(text)[max(0,match.start()-24):match.start()]
            after=str(text)[match.end():match.end()+24]
            if (re.search(r'(?:未(?:能)?核實|尚未確認|不能確認|假設|若)[^。；;\n]{0,12}$',before)
                    or re.match(r'(?:事件|一事|日期|的日期)?(?:尚)?未(?:能)?(?:核實|確認)',after)):
                continue
            token=match['year']+'-'+match['month'].zfill(2)
            if match['day']:token+='-'+match['day'].zfill(2)
            if re.search(r'(?:預計|預期|預估|可能|假設|若)[^。；;\n]{0,18}$',match[0][:match.start('action')-match.start()]):continue
            action={'升息':'raise','加息':'raise','降息':'lower','調降利率':'lower','維持利率不變':'maintain'}[match['action']]
            if any(f['decision_date'].startswith(token)and f['action']==action for f in facts):continue
            key=(token,action)
            if key not in seen:issues.append({'reason_code':'policy_action_date_unverified','reported_period':token,'action':action})
            seen.add(key)
    return issues


def policy_items_from_data(data):
    if not isinstance(data,dict):return []
    result=[]
    for source,field in (('global_market_context','items'),('international_news_context','topics')):
        value=data.get(source)
        rows=value.get(field,[])if isinstance(value,dict)else[]
        if isinstance(rows,list):result.extend(row for row in rows if isinstance(row,dict))
    return result
