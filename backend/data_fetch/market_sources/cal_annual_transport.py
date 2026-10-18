"""Fixed native public routes; the official IR page supplies every PDF URL."""
import base64,csv,io,json,re,time
from hashlib import sha256
from datetime import datetime,date
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from .issuer_news_transport import IssuerNewsHttp
from .mops_public_annual import PublicMopsHttp,api_url,template_url,STATEMENTS,INDEX_URL,_receipt
from .official_xbrl_financial import FilingError
from official_response_evidence import archive_response
from search_provider_runtime import SourceResponseError
from .annual_issuer_master import request_master

PROVIDER='China Airlines official audited cash and MOPS annual bridge'
MASTER_URL='https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
MASTER_JSON_URL='https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
IR_URL='https://www.china-airlines.com/nz/en/about-china-airlines/investor-relations?tab=FinancialReportsTab'
PDF_ROOT='https://cms-externalcontent-prod.s3.ap-northeast-1.amazonaws.com/ci/Investor-relations/Consolidated-Financial-Statements/EN/'
PDF_YEARS=(2022,2024,2025)
PDF_URLS={PDF_ROOT+str(y)+'Q4.pdf' for y in PDF_YEARS}

def _bad(message):raise FilingError('China Airlines '+message)
def _unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:_bad('duplicate JSON field')
        out[k]=v
    return out

def parse_index(raw):
    """Decode published Next flight data as JSON, never execute its script."""
    try:
        if not isinstance(raw,bytes)or not 0<len(raw)<=1_500_000:_bad('IR index size invalid')
        soup=BeautifulSoup(raw.decode('utf-8','strict'),'html.parser');roots=[]
        for tag in soup.find_all('script'):
            text=tag.string or ''
            if not text.startswith('self.__next_f.push('):continue
            entry=json.loads(text[len('self.__next_f.push('):-1],object_pairs_hook=_unique)
            if not isinstance(entry,list)or len(entry)!=2 or entry[0]!=1 or not isinstance(entry[1],str):continue
            for line in entry[1].splitlines():
                if not re.match(r'^[0-9a-f]+:\[',line):continue
                try:v=json.loads(line.split(':',1)[1],object_pairs_hook=_unique)
                except json.JSONDecodeError:continue
                if isinstance(v,list)and len(v)==4 and isinstance(v[3],dict)and v[3].get('title')=='Investor relations - Tab set':roots.append(v[3])
        if len(roots)!=1:_bad('IR publication root not unique')
        root=roots[0]
        if (root['resolvedLink']!='/nz/en/about-china-airlines/investor-relations'
                or root['componentTemplate']['view']!='TabSet'
                or root['content']['tabType']['keywordData']['key']!='InvestorRelations'):_bad('IR publication scope invalid')
        tabs=[t['linkedData'] for t in root['content']['tabs']['$values']
              if t['linkedData']['tabName']['keywordData']['key']=='FinancialReportsTab']
        if len(tabs)!=1:_bad('financial report tab not unique')
        blocks=[b for b in tabs[0]['tabContentBlocks']['$values'] if b.get('heading')=='Consolidated Financial Statements']
        if len(blocks)!=1:_bad('consolidated statement block not unique')
        content=blocks[0]['mainContent']
        if content['title']!='Consolidated financial statements - reports list' or content['componentTemplate']['view']!='ReportsList':_bad('consolidated report role invalid')
        output={}
        for y in PDF_YEARS:
            rows=[r for r in content['linkedData']['linkList']['$values']if r.get('headingForButtonList')==f'{y} Q4']
            if len(rows)!=1:_bad('annual consolidated publication not unique')
            r=rows[0];buttons=r['buttonList']['$values']
            if r['year']['keywordData']['key']!=str(y)or len(buttons)!=1:_bad('annual year or PDF publication invalid')
            b=buttons[0];link=b['s3Link'];url=link['s3Url']
            ecl='ecl:0-s3b-ci!2F;Investor!2D;relations!2F;Consolidated!2D;Financial!2D;Statements!2F;EN!2F;'+str(y)+'Q4.pdf-S3BucketFile-file'
            if b['buttonText']['keywordData']['key']!='PDF'or link['title']!=ecl or url!=PDF_ROOT+str(y)+'Q4.pdf':_bad('published annual PDF binding invalid')
            output[str(y)]=url
        return output
    except (KeyError,TypeError,ValueError,IndexError,RecursionError)as e:
        raise FilingError('China Airlines complete IR publication invalid')from e

def parse_master(raw,*,today=None,source_url=MASTER_URL):
    if not isinstance(raw,bytes)or not 0<len(raw)<=2_500_000:_bad('issuer roster size invalid')
    if source_url==MASTER_URL:
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig','strict'))))
    elif source_url==MASTER_JSON_URL:
        rows=json.loads(raw.decode('utf-8-sig','strict'),object_pairs_hook=_unique)
        if not isinstance(rows,list)or any(not isinstance(r,dict)for r in rows):_bad('issuer JSON roster shape invalid')
    else:_bad('issuer roster source invalid')
    if not 1<=len(rows)<=2000:_bad('issuer roster count invalid')
    selected=[r for r in rows if r.get('公司代號')=='2610']
    if len(selected)!=1:_bad('issuer not unique')
    r=selected[0];expected={'公司名稱':'中華航空股份有限公司','公司簡稱':'華航','營利事業統一編號':'11145904','網址':'http://www.china-airlines.com'}
    if any(r.get(k)!=v for k,v in expected.items()):_bad('issuer identity mismatch')
    stamp=r.get('出表日期','')
    if not re.fullmatch(r'\d{7}',stamp):_bad('issuer date invalid')
    as_of=date(int(stamp[:3])+1911,int(stamp[3:5]),int(stamp[5:]));today=today or datetime.now(ZoneInfo('Asia/Taipei')).date()
    if not 0<=(today-as_of).days<=7:_bad('issuer roster stale')
    return {'ticker':'2610.TW','legal_name':expected['公司名稱'],'official_name':'華航','official_ubn':'11145904',
            'registered_website':expected['網址'],'master_as_of':as_of.isoformat(),'master_response_sha256':sha256(raw).hexdigest()}

def contract(url):
    if url==MASTER_URL:return 2_500_000,{'text/csv','application/octet-stream'}
    if url==MASTER_JSON_URL:return 2_500_000,{'application/json','text/json'}
    if url==IR_URL:return 1_500_000,{'text/html','application/xhtml+xml'}
    if url in PDF_URLS:return 3_000_000,{'application/pdf'}
    _bad('native route invalid')

class _NativeHttp(IssuerNewsHttp):
    route_contract=staticmethod(contract)

def fetch_master(http):
    """The master transport owns the single CSV-to-JSON fallback."""
    return http.request(MASTER_URL)

class BridgeHttp(PublicMopsHttp):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.native=_NativeHttp(self.deadline)
    def request(self,url,*,request=None,json_body=None):
        if url in{INDEX_URL}|{api_url(s)for s in STATEMENTS}|{template_url(s)for s in STATEMENTS}:
            return super().request(url,request=request,json_body=json_body)
        limit,_=contract(url)
        if request is not None or json_body is not None:_bad('native request must be GET')
        if url==MASTER_URL:return request_master(self)
        if url==MASTER_JSON_URL:raise SourceResponseError('transport_url_invalid')
        diag={'url':url,'http_request_sent':False,'request_method':'GET'};self.components.append(diag)
        # All native calls share the original overall deadline and host cooldown.
        # Calling _download deliberately adds no renewed body cache.
        try:
            if url==IR_URL:
                from .cal_ir_gzip import request_original
                return request_original(self.native,diag,parse_index)
            value=self.native._download(url,diag)
        except Exception as exc:
            diag.update(error_kind=getattr(exc,'error_kind',type(exc).__name__),
                        http_status=getattr(exc,'status_code',None) if getattr(exc,'status_code',None) is not None else diag.get('http_status'));raise
        # _download only returns after status, URL, no redirects, content type,
        # size and the native process completion have all been verified.
        diag.update(http_status=200,http_status_observed=True)
        raw=base64.b64decode(value['body_b64'],validate=True)
        receipt=archive_response(raw,source_url=url,retrieved_at=time.time(),http_status=200)
        if _receipt(receipt,url,limit)!=raw:_bad('native archive mismatch')
        diag.update(status='complete',response_sha256=sha256(raw).hexdigest(),response_bytes=len(raw),fetched_at_epoch=receipt['retrieved_at'])
        return raw,receipt
