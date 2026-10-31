"""Published originals replay through the shared collector without live HTTP."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64
import gzip
import time
import pytest

ROOT = Path(__file__).parents[1]
D = ROOT / 'docs/evidence/source-acquisition/20261014/remaining-gap-next'
MASTER = ROOT / 'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW = 1791933000.


def valid_data(ticker='1229.TW'):
    if ticker == '1229.TW':
        name, legal, en, raw = ('聯華', '聯華實業控股股份有限公司', 'Lien Hwa Industrial Holdings Corporation', 'LIEN HWA INDUSTRIAL HOLDINGS CO')
    elif ticker == '2353.TW':
        name, legal, en, raw = ('宏碁', '宏碁股份有限公司', 'Acer Incorporated', 'ACER INC')
    elif ticker == '2382.TW':
        name, legal, en, raw = ('廣達', '廣達電腦股份有限公司', 'Quanta Computer Inc.', 'QCI')
    elif ticker == '1301.TW':
        name, legal, en, raw = ('台塑', '台灣塑膠工業股份有限公司', 'Formosa Plastics Corporation', 'FORMOSA PLASTICS CORP')
    elif ticker == '1102.TW':
        name, legal, en, raw = ('亞泥', '亞洲水泥股份有限公司', 'Asia Cement Corporation', 'ASIA CEMENT CORP')
    elif ticker == '1216.TW':
        name, legal, en, raw = ('統一', '統一企業股份有限公司', 'Uni-President Enterprises Corp.', 'UNI-PRESIDENT ENTERPRISES CORP')
    elif ticker == '3531.TWO':
        name, legal, en, raw = ('先益', '先益電子工業股份有限公司', 'Shian Yih Electronic Industry Co., Ltd.', 'Shian Yih')
    elif ticker == '1104.TW':
        name, legal, en, raw = ('環泥', '環球水泥股份有限公司', 'Universal Cement Corporation', 'UNIVERSAL CEMENT CORP')
    elif ticker == '2838.TW':
        name, legal, en, raw = ('聯邦銀', '聯邦商業銀行股份有限公司', 'Union Bank of Taiwan', 'UBOT')
    elif ticker == '3703.TW':
        name, legal, en, raw = ('欣陸', '欣陸投資控股股份有限公司', 'Continental Holdings Corporation', 'CHC')
    elif ticker == '2023.TW':
        name, legal, en, raw = ('燁輝', '燁輝企業股份有限公司', 'YP', 'Yieh Phui')
    elif ticker == '2845.TW':
        name, legal, en, raw = ('遠東銀','遠東國際商業銀行股份有限公司','Far Eastern International Bank Ltd.','FEIB')
    else:
        name, legal, en, raw = ('台積電', '台灣積體電路製造股份有限公司', 'Taiwan Semiconductor Manufacturing Company Limited', 'TAIWAN SEMICONDUCTOR MANUFACTUR')
    return {'ticker':ticker, 'instrument_type':'EQUITY', 'company_name':name+' / '+en,
        'raw_company_name':en, 'company_identity':{'ticker':ticker, 'stock_id':ticker.split('.')[0],
        'official_name':name, 'legal_name':legal, 'official_ubn':{'2353.TW':'20828393','2382.TW':'22822281','1301.TW':'75708007','1102.TW':'03244509','1216.TW':'73251209','3531.TWO':'52543363','1104.TW':'07568009','2838.TW':'86380802','3703.TW':'28993629','2023.TW':'75947936','2845.TW':'86517096'}.get(ticker),
        'display_name':name+' / '+en, 'allowed_aliases':[name,ticker,ticker.split('.')[0],name+' / '+en,raw],
        'english_names':[en,raw], 'forbidden_aliases':[]}}


@pytest.mark.parametrize(('ticker','short_name'),[
    ('3703.TW','CONTINENTAL HLDGS CORP'),
    ('2023.TW','YIEH PHUI ENTERPRISE CO'),
    ('1301.TW','FORMOSA PLASTIC'),
    ('2382.TW','QUANTA COMPUTER'),
])
def test_known_quote_short_names_do_not_reject_consistent_issuer(ticker,short_name):
    from data_fetch.market_sources import mops_presentation as source
    data=valid_data(ticker)
    data['company_identity']['english_names'].append(short_name)
    data['company_identity']['allowed_aliases'].append(short_name)
    assert source.validate_context(data,ticker)
    data['company_identity']['official_ubn']='11111111'
    assert not source.validate_context(data,ticker)
    data=valid_data(ticker)
    data['company_identity']['allowed_aliases'].append('UNRELATED COMPANY')
    assert not source.validate_context(data,ticker)


@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch.market_sources import mops_presentation as source
    from mops_material_transport import index_request
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time,'time',lambda:NOW)
    bodies = {
        'master':MASTER.read_bytes(),
        '2353.TW:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-electronics-entries/2353.TW.index.gz').read_bytes()),
        '2353.TW:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-electronics-entries/2353.TW.material.gz').read_bytes()),
        '2382.TW:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-electronics-entries/2382.TW.index.gz').read_bytes()),
        '2382.TW:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-electronics-entries/2382.TW.material.gz').read_bytes()),
        '1301.TW:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-industrial-entries/1301.TW.index.gz').read_bytes()),
        '1301.TW:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-industrial-entries/1301.TW.material.gz').read_bytes()),
        '1102.TW:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-next-entries/1102.TW.index.gz').read_bytes()),
        '1102.TW:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-next-entries/1102.TW.material.gz').read_bytes()),
        '1216.TW:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-next-entries/1216.TW.index.gz').read_bytes()),
        '1216.TW:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-next-entries/1216.TW.material.gz').read_bytes()),
        '3531.TWO:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/free-entry-continuation/3531.TWO.2026-index.gz').read_bytes()),
        '3531.TWO:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/free-entry-continuation/353120261008E001.pptx.gz').read_bytes()),
        '1104.TW:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/free-entry-continuation/1104.TW.2026-index.gz').read_bytes()),
        '1104.TW:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/free-entry-continuation/110420260522E001.pdf.gz').read_bytes()),
        '2330.TW:index':(D/'largecap-conference/tsmc-mops-index.body').read_bytes(),
        '2330.TW:material':(D/'largecap-conference/tsmc-mops-presentation.body').read_bytes(),
        '1229.TW:index':(D/'lienhwa/lienhwa-mops-index.body').read_bytes(),
        '1229.TW:material':(D/'lienhwa/lienhwa-mops-presentation.body').read_bytes(),
        '2838.TW:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/2838-mops-presentation/index.html.gz').read_bytes()),
        '2838.TW:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/2838-mops-presentation/presentation.pdf.gz').read_bytes()),
        '3703.TW:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/3703-mops-presentation/index.html.gz').read_bytes()),
        '3703.TW:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/3703-mops-presentation/presentation.pdf.gz').read_bytes()),
        '2023.TW:index':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/2023-mops-presentation/index.html.gz').read_bytes()),
        '2023.TW:material':gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/2023-mops-presentation/presentation.pdf.gz').read_bytes()),
    }
    calls=[]
    def master(self,url,diagnostic):
        raw=bodies['master']; calls.append('master'); self.http_request_count+=1
        diagnostic.update(http_request_sent=True,http_status=200,status='complete',response_bytes=len(raw),response_sha256=sha256(raw).hexdigest())
        from data_fetch.market_sources.official_issuer_master import master_metadata
        meta=master_metadata({'http_status':200,'effective_url':url,'num_redirects':0,
            'size_download':len(raw),'content_type':'text/csv','content_length':len(raw),
            'method':'GET','proxy_used':0,'cache_control':''},raw,{})
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
            'request_method':'GET','request_body':None,'response_metadata':meta}
    def post(spec, diagnostic):
        key=spec['ticker']+(':'+ 'index' if spec['format']=='html' else ':material')
        raw=bodies[key];calls.append(key)
        diagnostic.update(http_request_sent=True,http_request_count=1,http_status=200,response_complete=True,
            response_sha256=sha256(raw).hexdigest(),response_metadata={'http_status':200,'effective_url':spec['url'],
            'num_redirects':0,'size_download':len(raw),'content_type':{'html':'text/html','pdf':'application/pdf',
            'pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation'}[spec['format']],
            'content_length':len(raw),'method':spec['method'],'proxy_used':0})
        return raw
    monkeypatch.setattr(source.MasterHttp,'download_original',master)
    monkeypatch.setattr(source,'download_conference_index',lambda ticker,year,deadline,diagnostics:post(index_request(ticker,year=year),diagnostics))
    def material(spec,deadline,diagnostics,**wire_options):
        assert not wire_options or (spec['ticker']=='5314.TWO' and wire_options=={'wire_budget_seconds':15.})
        return post(spec,diagnostics)
    monkeypatch.setattr(source,'download_published_material',material)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()


@pytest.mark.parametrize('ticker', ['2330.TW','1229.TW'])
def test_real_public_original_recovers_body_with_limits_and_warm_truth(harness,monkeypatch,ticker):
    from data_fetch.market_sources import mops_presentation as source
    assert source.validate_context(valid_data(ticker),ticker)
    d={};value=source.fetch_presentation_context(ticker,diagnostics=d)
    doc=value['documents'][0]
    assert d['mops_material_originals_verified'] and d['http_request_count']==3 and not d['cache_hit']
    assert harness[1]==['master',ticker+':index',ticker+':material']
    assert doc['event_date']==('2026-09-14' if ticker=='2330.TW' else '2026-09-30')
    assert doc['material_file_date']==('2026-07-16' if ticker=='2330.TW' else '2026-09-30')
    assert doc['content_period']==('2026Q2' if ticker=='2330.TW' else None)
    assert doc['coverage_status']=='partial' and not doc['full_content_coverage_verified']
    assert not value['transcript_available'] and not doc['q_and_a_transcript_available']
    assert doc['published_at'] is None and doc['visual_semantics_caution']
    if ticker=='1229.TW':
        assert doc['page_count']==30 and doc['total_slide_count']==32 and doc['hidden_pages']==[31,32]
        assert doc['missing_text_pages']==[2,3,21,29] and doc['native_text_coverage']=='partial'
        assert all(p['page_number'] not in doc['hidden_pages'] for p in doc['pages'])
    else:
        assert doc['page_count']==12 and doc['native_text_coverage']=='complete'
    assert source.verify_context(value,ticker)
    harness[1].clear();monkeypatch.setattr(time,'time',lambda:NOW+1700)
    d={};warm=source.fetch_presentation_context(ticker,diagnostics=d)
    assert not harness[1] and d['http_request_count']==0 and d['cache_hit']
    assert warm['fetched_at_epoch']==value['fetched_at_epoch']==NOW
    assert source.verify_context(warm,ticker)
    monkeypatch.setattr(time,'time',lambda:NOW+1800)
    assert not source.verify_context(warm,ticker)


def test_ubot_published_mops_presentation_is_a_qualified_partial_source(harness):
    from data_fetch.market_sources import mops_presentation as source

    ticker='2838.TW'; data=valid_data(ticker); diagnostics={}
    assert source.supports(ticker)
    assert source.validate_context(data,ticker)
    value=source.fetch_presentation_context(ticker,diagnostics=diagnostics)
    doc=value['documents'][0]
    assert diagnostics['mops_material_originals_verified']
    assert diagnostics['coverage_status']=='native_presentation_text_partial'
    assert doc['event_date']=='2026-08-06' and doc['material_file_date']=='2026-08-05'
    assert doc['page_count']==20 and doc['native_text_coverage']=='partial'
    assert doc['missing_text_pages']==[] and doc['garbled_pages']==list(range(2,21))
    assert doc['content_period']=='2026Q2'
    assert doc['financial_statement_complete'] is False
    assert doc['unresolved_native_glyphs']
    assert any('原始私用區碼' in note for note in value['coverage_notes'])
    assert value['transcript_available'] is False
    assert source.verify_context(value,ticker)


def test_chc_published_mops_presentation_is_a_qualified_partial_source(harness):
    from data_fetch.market_sources import mops_presentation as source

    ticker='3703.TW';data=valid_data(ticker);diagnostics={}
    assert source.supports(ticker)
    assert source.validate_context(data,ticker)
    value=source.fetch_presentation_context(ticker,diagnostics=diagnostics)
    doc=value['documents'][0]
    assert diagnostics['mops_material_originals_verified']
    assert doc['event_date']=='2026-08-10' and doc['material_file_date']=='2026-08-10'
    assert doc['filename']=='370320260810E001.pdf'
    assert doc['page_count']==16 and doc['native_text_coverage']=='partial'
    assert doc['missing_text_pages']==[] and doc['garbled_pages']==[2]
    assert doc['content_period']=='2026Q2'
    assert doc['unresolved_native_glyphs']==[{'page_number':2,'codepoints':['U+F06C']}]
    assert not doc['full_content_coverage_verified'] and not value['transcript_available']
    assert source.verify_context(value,ticker)


def test_yieh_phui_large_published_mops_presentation_is_a_qualified_partial_source(harness):
    from data_fetch.market_sources import mops_presentation as source

    ticker='2023.TW';data=valid_data(ticker);diagnostics={}
    assert source.supports(ticker)
    assert source.validate_context(data,ticker)
    value=source.fetch_presentation_context(ticker,diagnostics=diagnostics)
    doc=value['documents'][0]
    assert diagnostics['mops_material_originals_verified']
    assert diagnostics['http_request_count']==3
    assert doc['event_date']=='2026-08-21' and doc['material_file_date']=='2026-08-21'
    assert doc['filename']=='202320260821E001.pdf'
    assert doc['page_count']==27 and doc['native_text_coverage']=='complete'
    assert doc['content_period']=='2026Q2'
    assert doc['coverage_status']=='partial' and not doc['full_content_coverage_verified']
    assert doc['financial_statement_complete'] is False
    assert not value['transcript_available']
    assert source.verify_context(value,ticker)


def test_yieh_phui_static_get_keeps_the_published_post_and_actual_wire_separate(harness):
    from data_fetch.market_sources import mops_presentation as source
    value=source.fetch_presentation_context('2023.TW')
    proof=value['mops_material_receipt']
    assert proof['policy']=='mops-published-presentation-static-get-v1'
    assert proof['selected']['method']=='POST'
    assert proof['material_request']['method']=='GET'
    assert proof['material']['request_method']=='GET'
    assert proof['material']['source_url']==value['documents'][0]['url']
    assert value['materials'][0]['request_method']=='GET'
    assert source.verify_context(value,'2023.TW')
    for damage in ('wire_url','receipt_method','legacy_disguise'):
        invalid=deepcopy(value);broken=invalid['mops_material_receipt']
        if damage=='wire_url':broken['material_request']['url']='https://mopsov.twse.com.tw/nas/STR/202320260821E002.pdf'
        elif damage=='receipt_method':broken['material']['request_method']='POST'
        else:broken['policy']=source.POLICY
        assert not source.verify_context(invalid,'2023.TW')


def test_legacy_yieh_phui_post_receipt_still_replays(harness):
    from data_fetch.market_sources import mops_presentation as source
    from mops_material_originals import get_original
    value=source.fetch_presentation_context('2023.TW');proof=deepcopy(value['mops_material_receipt'])
    published=proof['selected'];deadline=time.monotonic()+25
    (native,period),receipt=get_original(published,
        lambda d:source.download_published_material(published,deadline=deadline,diagnostics=d),
        deadline=deadline,owns=lambda:True,diagnostic={},force_refresh=True,
        parser=lambda raw,r:source.native_material(raw,published,deadline))
    proof.pop('material_request');proof.update(policy=source.POLICY,material=receipt)
    legacy=source._context(published,native,period,proof)
    assert legacy['materials'][0]['request_method']=='POST'
    assert source.verify_context(legacy,'2023.TW')


def test_ubot_unreviewed_private_use_glyph_is_rejected(harness,monkeypatch):
    from data_fetch.market_sources import mops_presentation as source

    extract=source.extract_pdf_pages
    def add_unreviewed_glyph(raw,*,timeout_seconds):
        native=extract(raw,timeout_seconds=timeout_seconds)
        native['pages'][1]['text'] += '\uf123'
        return native
    monkeypatch.setattr(source,'extract_pdf_pages',add_unreviewed_glyph)
    selected={'ticker':'2838.TW','format':'pdf','material_file_date':'2026-08-05'}
    with pytest.raises(ValueError,match='native text garbled'):
        source.native_material(harness[0]['2838.TW:material'],selected,time.monotonic()+20)


def test_chc_unreviewed_private_use_glyph_is_rejected(harness,monkeypatch):
    from data_fetch.market_sources import mops_presentation as source

    extract=source.extract_pdf_pages
    def add_unreviewed_glyph(raw,*,timeout_seconds):
        native=extract(raw,timeout_seconds=timeout_seconds)
        native['pages'][1]['text'] += '\uf123'
        return native
    monkeypatch.setattr(source,'extract_pdf_pages',add_unreviewed_glyph)
    selected={'ticker':'3703.TW','format':'pdf','material_file_date':'2026-08-10'}
    with pytest.raises(ValueError,match='native text garbled'):
        source.native_material(harness[0]['3703.TW:material'],selected,time.monotonic()+20)


def test_ubot_material_flows_through_provider_with_separate_acquisition_and_coverage_status(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest

    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2838.TW'),{'data':valid_data('2838.TW')})
    assert result.status=='success'
    assert result.audit['status']=='success'
    assert result.audit['record_count']==1
    assert result.audit['http_request_sent'] is True
    assert result.audit['http_request_count']==3
    assert result.audit['coverage_status']=='native_presentation_text_partial'
    assert result.value['documents'][0]['full_content_coverage_verified'] is False
    assert result.value['documents'][0]['unresolved_native_glyphs']


def test_chc_material_flows_through_provider_with_separate_acquisition_and_coverage_status(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest

    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('3703.TW'),{'data':valid_data('3703.TW')})
    assert result.status=='success'
    assert result.audit['status']=='success'
    assert result.audit['record_count']==1
    assert result.audit['http_request_sent'] is True
    assert result.audit['http_request_count']==3
    assert result.audit['coverage_status']=='native_presentation_text_partial'
    assert result.value['documents'][0]['full_content_coverage_verified'] is False
    assert result.value['documents'][0]['unresolved_native_glyphs']==[{'page_number':2,'codepoints':['U+F06C']}]


def test_yieh_phui_material_flows_through_provider_with_separate_acquisition_and_coverage_status(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest

    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2023.TW'),{'data':valid_data('2023.TW')})
    assert result.status=='success'
    assert result.audit['status']=='success'
    assert result.audit['record_count']==1
    assert result.audit['http_request_sent'] is True
    assert result.audit['http_request_count']==3
    assert result.audit['coverage_status']=='native_presentation_text_complete'
    assert result.value['documents'][0]['content_period']=='2026Q2'
    assert result.value['documents'][0]['coverage_status']=='partial'
    assert result.value['documents'][0]['full_content_coverage_verified'] is False


@pytest.mark.parametrize('opts',[{'force_refresh':True},{'use_cache':False}])
def test_explicit_body_refresh_reuses_fresh_shared_identity(harness,opts):
    from data_fetch.market_sources.mops_presentation import fetch_presentation_context
    fetch_presentation_context('1229.TW');harness[1].clear()
    d={};fetch_presentation_context('1229.TW',diagnostics=d,**opts)
    assert harness[1]==['1229.TW:index','1229.TW:material']
    assert d['http_request_count']==2 and d['cache_hit'] is False
    assert d['component_statuses'][0]['cache_hit'] is True


@pytest.mark.parametrize('change', ['text','period','hidden','date','request','response','ttl','archive','ticker'])
def test_replayed_proof_cannot_substitute_or_extend_originals(harness,change):
    from data_fetch.market_sources import mops_presentation as source
    value=source.fetch_presentation_context('1229.TW');doc=value['documents'][0];proof=value['mops_material_receipt']
    if change=='text':doc['pages'][0]['text']+=' forged'
    elif change=='period':doc['content_period']='2026Q2'
    elif change=='hidden':doc['hidden_pages']=[]
    elif change=='date':doc['event_date']='2026-10-01'
    elif change=='request':proof['material']['request']['request_body']+='&other=1'
    elif change=='response':proof['material']['response_metadata']['method']='GET'
    elif change=='ttl':proof['material']['fresh_until_epoch']+=1
    elif change=='archive':proof['material']['raw_response_sha256']='0'*64
    else:value['ticker']='2330.TW'
    assert not source.verify_context(value,'1229.TW')


@pytest.mark.parametrize('field,value',[('ticker','2330.TW'),('quoteType','ETF'),('company_name','聯成'),('company_identity',[]),('company_identity',False)])
def test_conflicting_original_context_is_not_equity_identity(field,value):
    from data_fetch.market_sources.mops_presentation import validate_context
    data=valid_data();data[field]=value
    assert not validate_context(data,'1229.TW')


def test_documentless_marker_check_is_total():
    from data_fetch.market_sources.mops_presentation import is_marked
    assert not is_marked({'documents':None}) and not is_marked({'documents':False})


def test_actual_download_failure_is_typed_and_no_blind_repeat(harness,monkeypatch):
    from data_fetch.market_sources import mops_presentation as source
    from search_provider_runtime import SourceResponseError
    attempts=[]
    def deny(spec,*,deadline,diagnostics):
        attempts.append(spec['request_sha256']);diagnostics.update(http_request_sent=True,http_status=429)
        raise SourceResponseError('rate_limited')
    monkeypatch.setattr(source,'download_published_material',deny)
    d={}
    with pytest.raises(SourceResponseError) as e:source.fetch_presentation_context('1229.TW',diagnostics=d)
    assert e.value.error_kind=='rate_limited' and d['http_request_count']==3
    for opts in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):source.fetch_presentation_context('1229.TW',**opts)
    assert len(attempts)==1


def test_cold_guard_storage_error_remains_typed_not_provider_cooldown(harness,monkeypatch):
    import cache_store
    from mops_material_transport import index_request
    from mops_material_originals import get_original,GUARD
    from search_provider_runtime import SourceResponseError
    original=cache_store.get_cache_json
    cause=OSError('isolated guard storage failure')
    def fail_guard(key):
        if key==GUARD:raise cause
        return original(key)
    monkeypatch.setattr(cache_store,'get_cache_json',fail_guard)
    with pytest.raises(SourceResponseError) as e:
        get_original(index_request('1229.TW',year=2026),lambda d:pytest.fail('guard failure must prevent HTTP'),
            deadline=time.monotonic()+10,owns=lambda:True,diagnostic={})
    assert e.value.error_kind=='guard_storage_unavailable'
    assert e.value.__cause__ is cause


def test_ucc_official_material_recovers_readable_text_without_claiming_full_content(harness):
    from data_fetch.market_sources import mops_presentation as source
    ticker='1104.TW'
    assert source.supports(ticker)
    assert source.validate_context(valid_data(ticker),ticker)
    diag={}
    value=source.fetch_presentation_context(ticker,diagnostics=diag)
    doc=value['documents'][0]
    assert doc['page_count']==12 and doc['native_text_coverage']=='complete'
    assert doc['content_period']=='2026Q1' and doc['event_date']=='2026-05-22'
    assert not doc['full_content_coverage_verified'] and not doc['financial_statement_complete']
    assert doc['symbol_mapping_evidence'] and not value['transcript_available']
    assert diag['http_request_count']==3 and source.verify_context(value,ticker)
    forged=deepcopy(value);forged['documents'][0]['content_period']='2026Q2'
    assert not source.verify_context(forged,ticker)
    harness[1].clear()
    warm_diag={};warm=source.fetch_presentation_context(ticker,diagnostics=warm_diag)
    assert not harness[1] and warm_diag['http_request_count']==0 and warm_diag['cache_hit']
    assert warm['fetched_at_epoch']==value['fetched_at_epoch']
    wrong=valid_data(ticker);wrong['company_identity']['official_ubn']='11111111'
    assert not source.validate_context(wrong,ticker)


@pytest.fixture
def otc_harness(harness,monkeypatch):
    from data_fetch.market_sources import mops_presentation as source
    monkeypatch.setattr(time,'time',lambda:1792248000.)
    raw=gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/shianyih-mops-integration/otc-master.json.gz').read_bytes())
    def master(self,url,diagnostic):
        harness[1].append('otc-master')
        diagnostic.update(http_request_sent=True,http_status=200,response_complete=True)
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()}
    monkeypatch.setattr(source.OtcMasterHttp,'download_original',master)
    return harness


def test_shianyih_otc_material_keeps_market_and_embedded_gaps(otc_harness):
    from data_fetch.market_sources import mops_presentation as source
    harness=otc_harness
    assert source.supports('3531.TWO') and not source.supports('3531.TW')
    assert source.validate_context(valid_data('3531.TWO'),'3531.TWO')
    d={};v=source.fetch_presentation_context('3531.TWO',diagnostics=d)
    doc=v['documents'][0]
    assert doc['page_count']==14 and doc['native_text_coverage']=='complete'
    assert doc['content_period']=='2026Q2' and doc['event_date']=='2026-10-16'
    assert doc['material_file_date']=='2026-10-08'
    assert doc['embedded_object_count']==4 and not doc['full_content_coverage_verified']
    assert d['http_request_count']==3 and source.verify_context(v,'3531.TWO')
    harness[1].clear()
    warm_diag={};w=source.fetch_presentation_context('3531.TWO',diagnostics=warm_diag)
    assert not harness[1] and warm_diag['http_request_count']==0
    assert w['fetched_at_epoch']==v['fetched_at_epoch']
    wrong=deepcopy(v);wrong['mops_material_receipt']['master']['source_url']=source.MASTER_URL
    assert not source.verify_context(wrong,'3531.TWO')
    altered=deepcopy(v);altered['documents'][0]['embedded_object_count']=0
    assert not source.verify_context(altered,'3531.TWO')


@pytest.fixture
def halfyear_harness(harness,monkeypatch):
    monkeypatch.setattr(time,'time',lambda:1792248000.)
    harness[0]['master']=gzip.decompress((ROOT/'docs/evidence/source-acquisition/20261017/mops-next-entries/master.csv.gz').read_bytes())
    return harness


@pytest.mark.parametrize(('ticker','pages','event'),[('1102.TW',29,'2026-08-17'),('1216.TW',15,'2026-08-11')])
def test_halfyear_original_keeps_h1_separate_from_q2(halfyear_harness,ticker,pages,event):
    from data_fetch.market_sources import mops_presentation as source
    assert source.supports(ticker) and source.validate_context(valid_data(ticker),ticker)
    diag={};value=source.fetch_presentation_context(ticker,diagnostics=diag)
    doc=value['documents'][0]
    assert doc['content_period']=='2026H1' and doc['event_date']==event
    assert doc['page_count']==pages and doc['native_text_coverage']=='complete'
    assert not doc['full_content_coverage_verified'] and not doc['financial_statement_complete']
    assert 'H1' in doc['period_scope_caution'] and diag['http_request_count']==3
    assert source.verify_context(value,ticker)
    altered=deepcopy(value);altered['documents'][0]['content_period']='2026Q2'
    assert not source.verify_context(altered,ticker)
    halfyear_harness[1].clear()
    warm_diag={};warm=source.fetch_presentation_context(ticker,diagnostics=warm_diag)
    assert not halfyear_harness[1] and warm_diag['http_request_count']==0
    assert warm['fetched_at_epoch']==value['fetched_at_epoch']


@pytest.mark.parametrize('ticker',['1102.TW','1216.TW'])
def test_halfyear_material_cannot_bind_to_a_different_event(halfyear_harness,ticker):
    from data_fetch.market_sources import mops_presentation as source
    from mops_published_materials import select_published_material
    selected=select_published_material(halfyear_harness[0][ticker+':index'],ticker,as_of_epoch=time.time(),
                                       company_name='亞泥' if ticker=='1102.TW' else '統一')
    selected['event_date']='2026-09-01'
    with pytest.raises(ValueError):source.native_material(halfyear_harness[0][ticker+':material'],selected,time.monotonic()+15)


def test_fpc_original_keeps_quarter_and_mapped_bullet_evidence(halfyear_harness):
    from data_fetch.market_sources import mops_presentation as source
    ticker='1301.TW'
    assert source.supports(ticker) and source.validate_context(valid_data(ticker),ticker)
    value=source.fetch_presentation_context(ticker)
    doc=value['documents'][0]
    assert doc['content_period']=='2026Q2' and doc['event_date']=='2026-09-16'
    assert doc['material_file_date']=='2026-09-08' and doc['page_count']==5
    assert doc['native_text_coverage']=='complete' and doc['symbol_mapping_evidence']
    assert not doc['full_content_coverage_verified'] and source.verify_context(value,ticker)
    altered=deepcopy(value);altered['documents'][0]['content_period']='2026H1'
    assert not source.verify_context(altered,ticker)


@pytest.fixture
def electronics_harness(harness,monkeypatch):
    import json
    folder=ROOT/'docs/evidence/source-acquisition/20261017/mops-electronics-entries'
    stamp=json.loads((folder/'master-receipt.json').read_text())['retrieved_at']+1
    monkeypatch.setattr(time,'time',lambda:stamp)
    harness[0]['master']=gzip.decompress((folder/'master.csv.gz').read_bytes())
    return harness


@pytest.mark.parametrize(('ticker','pages'),[('2353.TW',10),('2382.TW',6)])
def test_electronics_originals_have_exact_issuer_and_quarter(electronics_harness,ticker,pages):
    from data_fetch.market_sources import mops_presentation as source
    assert source.supports(ticker) and source.validate_context(valid_data(ticker),ticker)
    d={};v=source.fetch_presentation_context(ticker,diagnostics=d);doc=v['documents'][0]
    assert doc['content_period']=='2026Q2' and doc['page_count']==pages
    assert doc['native_text_coverage']=='complete' and not doc['full_content_coverage_verified']
    assert 'H1' in doc['period_scope_caution'] and d['http_request_count']==3
    assert source.verify_context(v,ticker)
    forged=deepcopy(v);forged['documents'][0]['content_period']='2026H1'
    assert not source.verify_context(forged,ticker)
    electronics_harness[1].clear()
    warm_diag={};warm=source.fetch_presentation_context(ticker,diagnostics=warm_diag)
    assert not electronics_harness[1] and warm_diag['http_request_count']==0
    assert warm['fetched_at_epoch']==v['fetched_at_epoch']


@pytest.mark.parametrize('ticker',['2353.TW','2382.TW'])
def test_electronics_native_issuer_binding_is_required(electronics_harness,monkeypatch,ticker):
    from data_fetch.market_sources import mops_presentation as source
    from mops_published_materials import select_published_material
    from copy import deepcopy
    import json
    selected=select_published_material(electronics_harness[0][ticker+':index'],ticker,
             as_of_epoch=time.time(),company_name='宏碁' if ticker=='2353.TW' else '廣達')
    native=json.loads((ROOT/'docs/evidence/source-acquisition/20261017/mops-electronics-entries'/ (ticker+'.native.json')).read_text())
    changed=deepcopy(native)
    for page in changed['pages']:
        if ticker=='2353.TW':page['text']=page['text'].replace('https://www.acer.com/corporate/en/investor-relations','https://example.com/')
        else:page['text']=page['text'].replace('(2382.TW/2382.TT)','(9999.TW/9999.TT)')
    monkeypatch.setattr(source,'extract_pdf_pages',lambda *a,**k:changed)
    with pytest.raises(ValueError):source.native_material(electronics_harness[0][ticker+':material'],selected,time.monotonic()+15)
