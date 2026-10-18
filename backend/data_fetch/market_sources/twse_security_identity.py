"""Explicit listed/OTC security type from the public ISIN table, never inference."""
from copy import deepcopy
from datetime import datetime,date
from hashlib import sha256
import json,math,re,time
from urllib.parse import urlsplit,parse_qs
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp,ROSTER_URL,url_contract
from .official_company_legal_name import URLS,FIELDS

PROVIDER='TWSE ISIN security classification'
SCHEMA='twse_isin_security_identity.v1'
LIMIT=300_000
HEADERS=['頁面編號','國際證券編碼','有價證券代號','有價證券名稱','市場別','有價證券別','產業別','公開發行/上市(櫃)/發行日','CFICode','備註']
TYPE_PAIRS={('上市','股票','ESVUFR'):'EQUITY',('上市臺灣創新板','創新板','ESVUFR'):'EQUITY',('上市','ETF','CEOGEU'):'ETF',('上櫃','股票','ESVUFR'):'EQUITY'}


def query_url(ticker):
 if not isinstance(ticker,str)or not re.fullmatch(r'\d{4,6}\.TW(?:O)?',ticker):raise ValueError('listed_security_context_not_supported')
 return 'https://isin.twse.com.tw/isin/single_main.jsp?owncode='+ticker.split('.')[0]+'&stockname='


def _master_contract(ticker):
 query_url(ticker)
 suffix='.TWO'if ticker.endswith('.TWO')else'.TW'
 return ('otc_master'if suffix=='.TWO'else'listed_master'),URLS[suffix],FIELDS[suffix],(500 if suffix=='.TWO'else 1000)


class SecurityIdentityHttp(IssuerNewsHttp):
 @staticmethod
 def route_contract(url):
  if url==ROSTER_URL:return url_contract(url)
  if url==URLS['.TWO']:return 2_500_000,{'application/json','text/json'}
  p=urlsplit(url);q=parse_qs(p.query,keep_blank_values=True)
  if p.scheme=='https'and p.netloc=='isin.twse.com.tw'and p.path=='/isin/single_main.jsp'and not p.fragment and set(q)=={'owncode','stockname'}and len(q['owncode'])==1 and re.fullmatch(r'\d{4,6}',q['owncode'][0])and q['stockname']==['']:
   return LIMIT,{'text/html','application/xhtml+xml'}
  raise SourceResponseError('transport_url_invalid')


def valid_isin(value):
 if not isinstance(value,str)or not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}\d',value):return False
 digits=''.join(str(ord(c)-55)if c.isalpha()else c for c in value)
 total=0
 for n,d in enumerate(reversed(digits)):
  v=int(d)*(2 if n%2 else 1);total+=v//10+v%10
 return total%10==0


def parse_security(raw,ticker,observed_epoch):
 url=query_url(ticker)
 if not isinstance(raw,bytes)or not 0<len(raw)<=LIMIT:raise ValueError('security_response_invalid')
 # This fixed official page has no meta charset; the captured native table is
 # Big5. Native Acer contains the CP950 extension for 碁. Preserve earlier
 # receipts' Big5 policy; use strict extension decoding only if needed.
 try:text=raw.decode('big5',errors='strict');encoding='strict_big5_fixed_table.v1'
 except UnicodeDecodeError:text=raw.decode('cp950',errors='strict');encoding='strict_cp950_extension_fixed_table.v1'
 soup=BeautifulSoup(text,'html.parser');tables=[]
 for table in soup.find_all('table'):
  rows=[[re.sub(r'\s+','',c.get_text())for c in tr.find_all(['th','td'],recursive=False)]for tr in table.find_all('tr')]
  if rows and rows[0]==HEADERS:tables.append(rows)
 if len(tables)!=1:raise ValueError('security_table_not_verified')
 if any(len(r)!=len(HEADERS)for r in tables[0][1:]):raise ValueError('security_result_row_malformed')
 matches=[r for r in tables[0][1:]if r[2]==ticker.split('.')[0]]
 if len(matches)!=1:raise ValueError('security_issuer_not_unique')
 row=matches[0];type_=TYPE_PAIRS.get((row[4],row[5],row[8]))
 market_matches=row[4]=='上櫃'if ticker.endswith('.TWO')else row[4]in {'上市','上市臺灣創新板'}
 if not market_matches or not type_ or not row[3]or not valid_isin(row[1]):raise ValueError('security_type_or_market_not_verified')
 listed=datetime.strptime(row[7],'%Y/%m/%d').date();observed=datetime.fromtimestamp(observed_epoch,ZoneInfo('Asia/Taipei')).date()
 if listed>observed:raise ValueError('security_listing_in_future')
 return {'schema':SCHEMA,'ticker':ticker,'security_code':row[2],'security_name':row[3],'isin':row[1],'market':row[4],'security_type':row[5],'industry':row[6],'listing_date':listed.isoformat(),'cfi_code':row[8],'instrument_type':type_,'source_url':url,'observed_at_epoch':observed_epoch,'encoding_policy':encoding,'first_publication_time_verified':False}


def _proof(raw,url,epoch):
 proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
 if proof.get('status')!='archived'or read_response(proof)!=raw:raise ValueError('security_original_not_archived')
 return proof


def _raw(proof,url,limit):
 if not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('evidence_kind')!='raw_http_response_bytes'or proof.get('source_url')!=url or type(proof.get('http_status'))is not int or proof['http_status']!=200:raise ValueError('security_receipt_invalid')
 epoch=proof.get('retrieved_at')
 if type(epoch)not in (int,float)or not math.isfinite(epoch)or not 0<=time.time()-epoch<=86400:raise ValueError('security_original_age_invalid')
 raw=read_response(proof)
 if not 0<len(raw)<=limit or type(proof.get('raw_response_bytes'))is not int or proof['raw_response_bytes']!=len(raw):raise ValueError('security_original_size_invalid')
 return raw,epoch


def _master_name(raw,ticker,epoch):
 _,_,fields,minimum=_master_contract(ticker);code,name,short,stamp_field=fields
 rows=json.loads(raw)
 if not isinstance(rows,list)or not minimum<=len(rows)<=2000 or any(not isinstance(r,dict)for r in rows):raise ValueError('incomplete_listed_master')
 codes=[r.get(code)for r in rows]
 if any(not isinstance(c,str)or not re.fullmatch(r'\d{4,6}',c)for c in codes)or len(set(codes))!=len(codes):raise ValueError('master_issuer_not_unique')
 selected=[r for r in rows if r.get(code)==ticker.split('.')[0]]
 if len(selected)!=1:raise ValueError('issuer_not_in_listed_master')
 row=selected[0];stamp=row.get(stamp_field);match=re.fullmatch(r'(\d{3})(\d{2})(\d{2})',str(stamp))
 if not match:raise ValueError('master_publication_not_verified')
 published=date(int(match[1])+1911,int(match[2]),int(match[3]));acquired=datetime.fromtimestamp(epoch,ZoneInfo('Asia/Taipei')).date()
 if not 0<=(acquired-published).days<=14:raise ValueError('master_publication_outside_original_period')
 if not isinstance(row.get(name),str)or not row[name]or not isinstance(row.get(short),str)or not row[short]:raise ValueError('master_name_not_verified')
 return row[short],row[name]


def verified_security_identity(value,ticker):
 try:
  if not isinstance(value,dict)or value.get('ticker')!=ticker:return False
  proofs=value['source_record_archive'];raw,epoch=_raw(proofs['identity'],query_url(ticker),LIMIT);parsed=parse_security(raw,ticker,epoch)
  if parsed['instrument_type']=='EQUITY':
   key,url,_,_=_master_contract(ticker);master,master_epoch=_raw(proofs[key],url,2_500_000);short,legal=_master_name(master,ticker,master_epoch)
   if parsed['security_name']!=short:return False
   parsed['listed_company_legal_name']=legal
  parsed['source_record_archive']=deepcopy(proofs)
  return value==parsed
 except (KeyError,ValueError,TypeError,UnicodeError,OverflowError,OSError,EOFError):return False


def fetch_security_identity(ticker,*,diagnostics):
 url=query_url(ticker);http=SecurityIdentityHttp(time.monotonic()+15)
 try:
  raw=http.get(url);identity_meta=http.components[-1];epoch=identity_meta['fetched_at_epoch'];value=parse_security(raw,ticker,epoch);proofs={'identity':_proof(raw,url,epoch)}
  if value['instrument_type']=='EQUITY':
   key,master_url,_,_=_master_contract(ticker);master=http.get(master_url);meta=http.components[-1];proofs[key]=_proof(master,master_url,meta['fetched_at_epoch']);short,legal=_master_name(master,ticker,meta['fetched_at_epoch'])
   if short!=value['security_name']:raise ValueError('master_security_name_conflict')
   value['listed_company_legal_name']=legal
  value['source_record_archive']=proofs
  if not verified_security_identity(value,ticker):raise ValueError('security_receipt_not_replayable')
  if time.monotonic()>=http.deadline:raise SourceResponseError('timeout')
  return value
 except (KeyError,ValueError,TypeError,UnicodeError,OverflowError,OSError,EOFError)as exc:
  # A second read of the same malformed raw cache cannot repair its facts.
  # Stop here so audited_fetch retains the first actual HTTP provenance.
  raise SourceResponseError('parse_error',parser_version=SCHEMA)from exc
 finally:
  diagnostics.update(fetched_at_epoch=http.components[0].get('fetched_at_epoch')if http.components else None,http_request_count=http.http_request_count,http_request_sent=bool(http.http_request_count),cache_hit=bool(http.components)and all(c.get('cache_hit')for c in http.components),components=deepcopy(http.components))
