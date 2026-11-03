"""Whole MOPS JSON originals for a qualified five-year individual basis.

Discovery still replays the complete issuer index. JSON response scopes and
XBRL references stay A; no XML download or original taxonomy fact is claimed.
"""
from copy import deepcopy
from hashlib import sha256
import json,time
from .mops_public_annual import (INDEX_URL,STATEMENTS,api_url,template_url,payload,
    parse_statement,_receipt,FilingError)

PROTOCOL='mops-public-individual-three-statements.v1'
SUPPORTED={'2633.TW'}

def _parse(raw,ticker,year,statement,template):
    from .ordinary_individual_annual import FIELDS
    parsed=parse_statement(raw,ticker.split('.')[0],year,statement,template,
        include_prior=True,allow_reconciled_missing_purchases=True,report_scope='individual')
    return {year:{FIELDS[k]:v for k,v in parsed[year].items()},
            year-1:{FIELDS[k]:v for k,v in parsed[year-1].items()},
            'inferred_zero_facts':parsed.get('inferred_zero_facts',[])}

def _projection(rows,years,ticker):
    from .ordinary_individual_annual import COMMON_FIELDS,SCHEMA,NOTE
    from ..financial_history_basis import _history_projection
    labels={'reported_revenue':'營業收入合計','profit_loss':'本期淨利（淨損）',
        'gross_profit':'營業毛利（毛損）','operating_income':'營業利益（損失）',
        'assets':'資產總額','equity':'權益總額',
        'free_cash_flow':'營業活動淨現金流加明列設備及無形資產現金支出'}
    fields={key:(field,'mops-public-individual-row:'+labels[field],label)
            for key,(field,_fact,label)in COMMON_FIELDS.items()}
    return _history_projection(rows,years,ticker,schema=SCHEMA,common_fields=fields,
        unsupplied_fields=(),scope='individual',note=NOTE+' 此來源逐一重播官方JSON三表及原單位／年號前端契約，不宣稱下載iXBRL或JSON內含原始taxonomy標籤。')

def _assemble(documents,ticker,years):
    from .ordinary_individual_annual import _assemble as reconcile
    primary={};prior={};inferred=[];templates={}
    for year,doc in zip(years,documents):
        parts=doc['components'];facts={};comparison={}
        if (doc.get('year')!=year or type(doc['year'])is not int or doc.get('period_end')!=f'{year}-12-31'
                or doc.get('url')!=api_url('BalanceSheet')or doc.get('format')!=PROTOCOL
                or doc.get('provider')!='TWSE MOPS issuer annual statements'
                or doc.get('report_scope')!='individual'or not isinstance(parts,list)or len(parts)!=3):
            raise FilingError('public individual annual document invalid')
        for statement,part in zip(STATEMENTS,parts):
            if (part.get('statement')!=statement or type(part.get('year'))is not int or part['year']!=year
                    or part.get('url')!=api_url(statement)or part.get('request')!=payload(ticker.split('.')[0],year)):
                raise FilingError('public individual request differs')
            raw=_receipt(part['raw_receipt'],api_url(statement),not_before=_close(year))
            if sha256(raw).hexdigest()!=part.get('sha256'):raise FilingError('public individual original differs')
            receipt=part['unit_template_receipt'];key=json.dumps(receipt,sort_keys=True)
            if key not in templates:templates[key]=_receipt(receipt,template_url(statement),not_before=_close(years[-1]))
            parsed=_parse(raw,ticker,year,statement,templates[key]);facts.update(parsed[year]);comparison.update(parsed[year-1])
            inferred.extend(v for v in parsed['inferred_zero_facts']if v['period_year']==year)
        if doc.get('sha256')!=sha256(';'.join(p['sha256']for p in parts).encode()).hexdigest():
            raise FilingError('public individual manifest digest differs')
        primary[year]=facts
        if year>years[0]:prior[year-1]=comparison
    rows,revisions=reconcile(primary,prior)
    return rows,revisions,sorted(inferred,key=lambda v:(v['period_year'],v['fact']))

def _close(year):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime(year+1,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()

def project_history(value,ticker):
    from .ordinary_individual_annual import SCHEMA,select_basis,FIELDS
    from .official_xbrl_financial import _filing_urls
    try:
        if (ticker not in SUPPORTED or not isinstance(value,dict)or value.get('schema')!=SCHEMA
                or value.get('protocol')!=PROTOCOL or value.get('ticker')!=ticker
                or value.get('currency')!='TWD'or value.get('report_scope')!='individual'
                or value.get('source_url')!=INDEX_URL):return None
        years=value['years'];docs=value['documents']
        if (not isinstance(years,list)or len(years)!=5 or any(type(y)is not str or len(y)!=4 or not y.isdigit()for y in years)
                or not isinstance(docs,list)or len(docs)!=5):return None
        saved=value['raw_twd_by_year']
        if (not isinstance(saved,dict)or set(saved)!=set(years)
                or any(not isinstance(r,dict)or set(r)!=set(FIELDS.values())|{'free_cash_flow'}
                       or any(type(n)is not int for n in r.values())for r in saved.values())):return None
        index=_receipt(value['published_index_receipt'],INDEX_URL,2500000,not_before=_close(int(years[-1])))
        scope,selected=select_basis(index,ticker.split('.')[0])
        if scope!='individual'or years!=list(map(str,selected)):return None
        urls=_filing_urls(index,ticker.split('.')[0],report_id='A')
        if any(d.get('indexed_xbrl_url')!=urls[y]for d,y in zip(docs,selected)):return None
        rows,revisions,inferred=_assemble(docs,ticker,selected)
        if (rows!=saved or json.dumps(revisions,sort_keys=True)!=json.dumps(value['comparative_revisions'],sort_keys=True)
                or json.dumps(inferred,sort_keys=True)!=json.dumps(value['inferred_zero_facts'],sort_keys=True)):return None
        return {**_projection(rows,years,ticker),'sector_specific_financials':deepcopy(value)}
    except (KeyError,TypeError,ValueError,OverflowError,OSError,EOFError,AttributeError):return None

def fetch_histories(ticker,http):
    from .ordinary_individual_annual import select_basis,SCHEMA,PROVIDER
    from .official_xbrl_financial import _filing_urls
    if ticker not in SUPPORTED:raise FilingError('public individual issuer not admitted')
    issuer=ticker.split('.')[0]
    with http.batch():
        index,receipt=http.request(INDEX_URL,request={'step':'1','firstin':'ture','off':'1','queryName':'co_id','inpuType':'co_id','TYPEK':'all','co_id':issuer})
        scope,years=select_basis(index,issuer)
        if scope!='individual':raise FilingError('public individual latest basis changed')
        templates={s:http.request(template_url(s))for s in STATEMENTS};urls=_filing_urls(index,issuer,report_id='A');docs=[]
        for year in years:
            parts=[]
            for s in STATEMENTS:
                body,proof=http.request(api_url(s),json_body=payload(issuer,year))
                _parse(body,ticker,year,s,templates[s][0])
                parts.append({'statement':s,'year':year,'url':api_url(s),'request':payload(issuer,year),
                    'sha256':sha256(body).hexdigest(),'raw_receipt':proof,'unit_template_receipt':templates[s][1]})
            docs.append({'year':year,'period_end':f'{year}-12-31','provider':PROVIDER,'report_scope':'individual',
                'url':api_url('BalanceSheet'),'indexed_xbrl_url':urls[year],'format':PROTOCOL,'components':parts,
                'sha256':sha256(';'.join(p['sha256']for p in parts).encode()).hexdigest()})
        rows,revisions,inferred=_assemble(docs,ticker,years)
        value={'schema':SCHEMA,'protocol':PROTOCOL,'ticker':ticker,'currency':'TWD','report_scope':'individual',
            'source_url':INDEX_URL,'years':list(map(str,years)),'documents':docs,'published_index_receipt':receipt,
            'raw_twd_by_year':rows,'comparative_revisions':revisions,'inferred_zero_facts':inferred}
        if project_history(value,ticker)is None:raise FilingError('public individual original projection rejected')
        if time.monotonic()>=http.deadline:raise FilingError('public individual operation deadline exceeded')
        return value
