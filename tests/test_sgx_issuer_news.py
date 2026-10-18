from data_fetch.issuer_news_provider import IssuerNewsProvider
from data_fetch.types import FetchRequest


def test_unproven_machine_auth_route_is_not_in_formal_provider_plan():
    assert not IssuerNewsProvider().supports(FetchRequest.from_ticker('9103.TW'))

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from hashlib import sha256
import json
import pytest
from data_fetch.market_sources import sgx_issuer_news as source
from source_content_selection import select_company_records
from news_freshness_policy import apply_news_freshness
from search_provider_runtime import SourceResponseError

ROOT=Path(__file__).parent/'fixtures/source_acquisition'
FIXTURE=json.loads((ROOT/'sgx_medtecs_selected_20261009.json').read_text())
NOW=datetime.fromisoformat(FIXTURE['reference_now'])
ITEM=FIXTURE['api_selected']['data'][0]
PDF_URL='https://links.sgx.com/FileOpen/Medtecs%20-%20Completion%20of%20the%20RMKH%20Disposal.ashx?App=Announcement&FileID=906536'
DATA={'ticker':'9103.TW','company_name':'Medtecs International Corp. Ltd.',
      'company_identity':{'official_name':'美德醫療-DR','legal_name':'美德向邦醫療國際股份有限公司'}}


class Http:
    def __init__(self):
        self.roster=deepcopy(FIXTURE['roster_selected']);self.api=deepcopy(FIXTURE['api_selected'])
        self.detail=FIXTURE['detail_utf8'].encode();self.pdf=(ROOT/'sgx_medtecs_completion_20261009.pdf').read_bytes()
        self.calls=[];self.components=[];self.http_request_count=0
    def get(self,url):
        self.calls.append(url);self.http_request_count+=1
        self.components.append({'url':url,'cache_hit':False,'http_request_sent':True,'fetched_at_epoch':NOW.timestamp()})
        if url==source.ROSTER_URL:return json.dumps(self.roster,ensure_ascii=False).encode()
        if url==source.query_url(NOW):return json.dumps(self.api,ensure_ascii=False).encode()
        if url==ITEM['url']:return self.detail
        if url==PDF_URL:return self.pdf
        raise AssertionError('out-of-contract test HTTP')


@pytest.fixture
def extraction(monkeypatch):
    result=deepcopy(FIXTURE['pdf_bounded_extraction'])
    monkeypatch.setattr(source,'extract_pdf_pages',lambda raw,**kwargs:deepcopy(result))
    return result


def fetch(http=None):
    return source.fetch_sgx_issuer_news('9103.TW',now=NOW,http=http or Http())


def test_complete_observed_pdf_through_bounded_reader_and_company_gate():
    http=Http();records,audit=fetch(http)
    assert len(records)==1 and audit['status']=='success'
    record=records[0]
    assert http.calls==[source.ROSTER_URL,source.query_url(NOW),ITEM['url'],PDF_URL]
    assert record['date']=='2026-10-09T09:31:58+00:00'
    assert 'US$ 13,144,512' in record['text'] or 'US$13,144,512' in record['text']
    assert record['source_role']=='issuer_statement' and record['event_assessment']=='not_assessed'
    assert record['sgx_issuer_receipt']['original_share_isin']=='BMG5958R1043'
    assert record['sgx_issuer_receipt']['pdf_response_sha256']==sha256(http.pdf).hexdigest()
    assert record['sgx_issuer_receipt']['pdf_page_count']==1
    accepted,selection=select_company_records(records,DATA,cutoff=NOW)
    assert len(accepted)==1 and selection['rejected_count']==0
    before=deepcopy(DATA);data=deepcopy(DATA);apply_news_freshness(data,records=records,cutoff=NOW)
    assert len(data['recent_catalysts'])==1 and data['company_identity']==before['company_identity']
    assert audit['window_complete'] is False


@pytest.mark.parametrize('field,value',[('公司名稱','不同公司股份有限公司'),('公司簡稱','其他-DR'),
                                      ('英文簡稱','OTHER'),('網址','www.medtecs.com.evil.test'),
                                      ('外國企業註冊地國','US 美國'),('出表日期','1150801')])
def test_wrong_official_tdr_binding_stops_before_sgx_query(extraction,field,value):
    http=Http();http.roster[0][field]=value;records,audit=fetch(http)
    assert records==[] and audit['status']=='error' and http.calls==[source.ROSTER_URL]


@pytest.mark.parametrize('field,value',[('issuer_name','OTHER'),('security_name','OTHER'),('stock_code','999'),('isin_code','BMGOTHER12345')])
def test_sgx_original_share_identity_mismatch_does_not_fetch_detail(extraction,field,value):
    http=Http();http.api['data'][0]['issuers'][0][field]=value;records,audit=fetch(http)
    assert records==[] and audit['status']=='degraded_enrichment'
    assert http.calls==[source.ROSTER_URL,source.query_url(NOW)]


@pytest.mark.parametrize('bad',['future','historical','boolean','submission_mismatch','reference_mismatch','id_mismatch','mixed_issuers'])
def test_unverified_index_candidate_never_fetches_original(extraction,bad):
    http=Http();item=http.api['data'][0]
    if bad in ('future','historical'):
        day=NOW+timedelta(days=1) if bad=='future' else NOW-timedelta(days=40)
        item.update(broadcast_date_time=int(day.timestamp()*1000),submission_date_time=int(day.timestamp()*1000),submission_date=day.astimezone(source.SG).strftime('%Y%m%d'),ref_id='SG'+day.astimezone(source.SG).strftime('%y%m%d')+'OTHRW6Y4')
    elif bad=='boolean':item['broadcast_date_time']=True
    elif bad=='submission_mismatch':item['submission_date']='20261008'
    elif bad=='reference_mismatch':item['ref_id']='SG261008OTHRW6Y4'
    elif bad=='id_mismatch':item['id']='UNRELATED'
    else:item['issuers'].append(deepcopy(item['issuers'][0]))
    records,audit=fetch(http);assert records==[] and len(http.calls)==2


@pytest.mark.parametrize('old,new',[('09-Oct-2026 17:31:58','08-Oct-2026 17:31:58'),
                                    ('SG261009OTHRW6Y4','SG261008OTHRW6Y4'),
                                    ('BMG5958R1043','BMGOTHER12345'),
                                    ('Completion of the Disposal','Completion of a Different Disposal'),
                                    ('<dd>New</dd>','<dd>Replaced</dd>')])
def test_original_metadata_must_match_exact_index_before_pdf(extraction,old,new):
    http=Http();assert old.encode()in http.detail;http.detail=http.detail.replace(old.encode(),new.encode())
    records,audit=fetch(http);assert records==[] and audit['status']=='error' and len(http.calls)==3


@pytest.mark.parametrize('old,new',[('906536_Medtecs','906536_../Medtecs'),
                                    ('/1.0.0/corporate-announcements/NS5OFIA2R7WXB5B4/906536_','https://evil.test/906536_'),
                                    ('.pdf" target=', '.pdf?session=not-real" target=')])
def test_attachment_path_is_bound_to_same_notice_and_public_pdf(extraction,old,new):
    http=Http();http.detail=http.detail.replace(old.encode(),new.encode());records,audit=fetch(http)
    assert records==[] and len(http.calls)==3


@pytest.mark.parametrize('bad',['wrong_company','wrong_date','wrong_title','incomplete','too_many_pages'])
def test_pdf_full_content_identity_date_and_coverage_remain_required(extraction,bad):
    if bad=='wrong_company':extraction['pages'][0]['text']=extraction['pages'][0]['text'].replace(source.ENGLISH,'OTHER COMPANY LIMITED')
    elif bad=='wrong_date':extraction['pages'][0]['text']=extraction['pages'][0]['text'].replace('9 October 2026','8 October 2026')
    elif bad=='wrong_title':extraction['pages'][0]['text']=extraction['pages'][0]['text'].replace('COMPLETION OF THE DISPOSAL','COMPLETION OF SOMETHING ELSE')
    elif bad=='incomplete':extraction['coverage_status']='partial'
    else:extraction['page_count']=9
    records,audit=fetch();assert records==[] and audit['status']=='error'


@pytest.mark.parametrize('field,value',[('text','MEDTECS made up content'*20),('summary','fake summary'),
                                      ('date','2026-10-08T09:31:58+00:00'),('source_document_url','https://evil.test/file.pdf'),
                                      ('source','SGX verified and approved'),('event_assessment','positive'),('original_attachment_url','https://evil.test/')])
def test_saved_record_mutation_cannot_use_generic_alias_fallback(extraction,field,value):
    records,_=fetch();assert records
    records[0][field]=value;selected,_=select_company_records(records,DATA,cutoff=NOW);assert selected==[]


def test_receipt_is_scoped_to_tdr_and_never_changes_market_identity(extraction):
    records,_=fetch()
    assert not source.verified_sgx_issuer_news(records[0],{'ticker':'546.SI'},today=NOW.date())
    assert not source.verified_sgx_issuer_news(records[0],{'ticker':'9103.TWO'},today=NOW.date())
    assert not source.verified_sgx_issuer_news(records[0],{'ticker':'9103.TW','company_identity':{'forbidden_aliases':['MEDTECS']}},today=NOW.date())
    _,audit=source.fetch_sgx_issuer_news('546.SI',now=NOW,http=Http());assert audit['status']=='not_applicable'


def test_one_exact_30_day_query_and_no_arbitrary_urls_or_credentials():
    url=source.query_url(NOW);source.url_contract(url)
    for wrong in (url+'&session=x',url.replace('pagesize=20','pagesize=200'),url.replace('exactsearch=true','exactsearch=false'),
                  url.replace('api.sgx.com','api.sgx.com.evil.test'),PDF_URL+'&session=x',PDF_URL.replace('/FileOpen/','/private/')):
        with pytest.raises((SourceResponseError,ValueError)):source.url_contract(wrong)


def test_disabled_route_never_queries_sgx_through_formal_provider(monkeypatch):
    from data_fetch.provider_registry import ProviderRegistry
    monkeypatch.setattr(source,'fetch_sgx_issuer_news',lambda *a,**k:pytest.fail('unverified SGX route was enabled'))
    request=FetchRequest.from_ticker('9103.TW')
    assert 'Verified issuer news' not in ProviderRegistry().provider_names(request,'recent_catalysts')
    result=IssuerNewsProvider().fetch(request,{'data':DATA})
    assert result.status=='not_applicable' and result.audit['http_request_sent'] is False


def test_forbidden_alias_uses_shared_markup_and_star_normalization(extraction):
    records,_=fetch();data=deepcopy(DATA);data['company_identity']['forbidden_aliases']=['<b>*MeDtEcS*</b>']
    selected,_=select_company_records(records,data,cutoff=NOW);assert selected==[]


@pytest.mark.parametrize('field,value',[('source_document_url',source.ROSTER_URL),
 ('original_attachment_url','https://links.sgx.com/1.0.0/corporate-announcements/AAAAAAAAAAAAAAAA/906536_Medtecs.pdf')])
def test_saved_receipt_rechecks_attachment_binding_even_with_updated_content_digest(extraction,field,value):
    records,_=fetch();record=records[0];record[field]=value
    record['sgx_issuer_receipt']['parsed_content_sha256']=source._digest(record)
    selected,_=select_company_records(records,DATA,cutoff=NOW);assert selected==[]


def test_damaged_receipt_cannot_fall_through_after_source_type_is_removed(extraction):
    records,_=fetch();records[0].pop('source_type');records[0]['sgx_issuer_receipt']['pdf_response_sha256']='0'*64
    data=deepcopy(DATA);data['company_identity']['allowed_aliases']=['MEDTECS']
    selected,_=select_company_records(records,data,cutoff=NOW);assert selected==[]
