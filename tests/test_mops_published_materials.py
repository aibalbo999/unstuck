from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup
from copy import deepcopy

from mops_published_materials import select_published_material

FIX = Path(__file__).parent / 'fixtures/source_acquisition/mops_materials_20261014'
URL = 'https://mopsov.twse.com.tw/server-java/FileDownLoad'
TAIPEI = ZoneInfo('Asia/Taipei')
AS_OF = datetime(2026, 10, 14, 8, tzinfo=TAIPEI).timestamp()
FIELDS = {'ticker','symbol','company_name','event_date','event_end_date','event_time',
          'event_location','event_summary','material_file_date','filename','format','language',
          'index_sha256','row_sha256','url','method','request_body','request_sha256'}


def index_raw(symbol='2330'):
    return (FIX / (symbol + '-index.html')).read_bytes()


@pytest.mark.parametrize('symbol,name,event,filename', [
    ('2330','台積電','2026-09-14','233020260716E001.pdf'),
    ('2303','聯電','2026-09-14','230320260729E001.pdf'),
    ('1229','聯華','2026-09-30','122920260930E001.pptx'),
])
def test_complete_original_selects_published_english_request(symbol,name,event,filename):
    raw=index_raw(symbol)
    value=select_published_material(raw,symbol+'.TW',as_of_epoch=AS_OF,company_name=name)
    assert isinstance(value,dict), 'Published complete original must yield a request descriptor'
    assert set(value)==FIELDS
    assert value['ticker']==symbol+'.TW' and value['symbol']==symbol
    assert value['company_name']==name and value['event_date']==event
    assert value['filename']==filename and value['language']=='en'
    assert value['format']==filename.rsplit('.',1)[1]
    assert value['index_sha256']==sha256(raw).hexdigest()
    body=urlencode([('step','9'),('filePath','/home/html/nas/STR/'),('fileName',filename),('functionName','t100sb02_1')])
    assert value['url']==URL and value['method']=='POST' and value['request_body']==body
    assert value['request_sha256']==sha256(('POST\n'+URL+'\n'+body).encode('ascii')).hexdigest()
    assert value['material_file_date']==f'{filename[4:8]}-{filename[8:10]}-{filename[10:12]}'
    assert len(value['row_sha256'])==64


def test_fixture_bytes_are_prior_originals_not_refetched():
    manifest=json.loads((FIX/'manifest.json').read_text())
    assert manifest['new_HTTP']==0
    for row in manifest['fixtures']:
        raw=index_raw(row['symbol'])
        assert len(raw)==row['bytes'] and sha256(raw).hexdigest()==row['sha256']


def edited(change, symbol='2330'):
    soup=BeautifulSoup(index_raw(symbol),'html.parser')
    change(soup)
    return str(soup).encode()


def body_rows(soup):
    return soup.select('#myTable tr[data-type="body"]')


def latest_row(soup):
    return next(r for r in body_rows(soup) if r.find_all('td')[2].get_text(' ',strip=True)=='115/09/14')


def select(raw, **kw):
    return select_published_material(raw,kw.pop('ticker','2330.TW'),as_of_epoch=kw.pop('as_of_epoch',AS_OF),**kw)


@pytest.mark.parametrize('change',[
    lambda s:s.select_one('form#fm_fileDownload').__setitem__('action','https://evil.invalid/server-java/FileDownLoad'),
    lambda s:s.select_one('form#fm_fileDownload').__setitem__('method','get'),
    lambda s:s.select_one('form#fm_fileDownload').__setitem__('name','another_form'),
    lambda s:s.select_one('form#fm_fileDownload input[name="step"]').__setitem__('value','8'),
    lambda s:s.select_one('form#fm_fileDownload input[name="filePath"]').__setitem__('value','/tmp/'),
    lambda s:s.select_one('form#fm_fileDownload input[name="fileName"]').__setitem__('value','233020260716E001.pdf'),
    lambda s:s.select_one('form#fm_fileDownload input[name="functionName"]').__setitem__('value','other'),
    lambda s:s.select_one('form#fm_fileDownload').append(deepcopy(s.select_one('form#fm_fileDownload input'))),
    lambda s:s.select_one('form#fm_fileDownload').insert_after(deepcopy(s.select_one('form#fm_fileDownload'))),
    lambda s:s.select_one('input[name="TYPEK"]').__setitem__('value','otc'),
    lambda s:s.select_one('input[name="TYPEK"]').__setitem__('value',''),
    lambda s:s.select_one('input[name="TYPEK"]').decompose(),
    lambda s:s.select_one('input[name="TYPEK"]').insert_after(deepcopy(s.select_one('input[name="TYPEK"]'))),
    lambda s:s.select_one('#myTable thead th').__setattr__('string','股票代號'),
    lambda s:latest_row(s).find_all('td')[0].__setattr__('string','2303'),
    lambda s:latest_row(s).find_all('td')[1].__setattr__('string','錯誤公司'),
    lambda s:latest_row(s).find_all('td')[-1].decompose(),
    lambda s:latest_row(s).append(s.new_tag('td')),
    lambda s:latest_row(s).find_all('td')[4].__setitem__('colspan','2'),
    lambda s:latest_row(s).find_all('td')[7].select_one('a').__setitem__('onclick','document.fm_fileDownload.fileName.value="230320260716E001.pdf";document.fm_fileDownload.submit();'),
    lambda s:latest_row(s).find_all('td')[7].select_one('a').__setitem__('href','/nas/STR/233020260716E001.pdf'),
    lambda s:latest_row(s).find_all('td')[7].select_one('a').attrs.pop('onclick'),
    lambda s:latest_row(s).find_all('td')[7].append(deepcopy(latest_row(s).find_all('td')[7].select_one('a'))),
])
def test_identity_form_and_shape_mutations_cannot_grant_download(change):
    with pytest.raises(ValueError):select(edited(change),company_name='台積電')


@pytest.mark.parametrize('filename',[
    '230320260716E001.pdf','233020261332E001.pdf','233020260716M001.pdf',
    '233020260716E001.pdf?x=1','233020260716E001.pdf#x','../233020260716E001.pdf',
    '%2F233020260716E001.pdf','233020260716E001.ppt','233020260716E001.PDF',
    '233020260716E001.pdf.exe',
])
def test_filename_scope_and_grammar_are_exact(filename):
    def change(s):
        a=latest_row(s).find_all('td')[7].select_one('a');a.string=filename
        a['onclick']=f'document.fm_fileDownload.fileName.value="{filename}";document.fm_fileDownload.submit();'
    with pytest.raises(ValueError):select(edited(change))


@pytest.mark.parametrize('ticker',['2330','2330.tw','2330.TWO','2330.TW.evil','2330.TW ','2330.US',True,None])
def test_explicit_market_required(ticker):
    with pytest.raises(ValueError):select(index_raw(),ticker=ticker)


@pytest.mark.parametrize('epoch',[True,None,'1791931591',0,-1,float('nan'),float('inf'),10**500])
def test_invalid_epoch_rejected(epoch):
    with pytest.raises(ValueError):select(index_raw(),as_of_epoch=epoch)


@pytest.mark.parametrize('company',['台積電股份有限公司','聯電','',True,[]])
def test_independent_short_name_must_match(company):
    with pytest.raises(ValueError):select(index_raw(),company_name=company)


def test_duplicate_protected_attribute_cannot_be_silently_chosen():
    original=str(BeautifulSoup(index_raw(),'html.parser')).encode()
    needle=b'action="/server-java/FileDownLoad"'
    assert needle in original
    raw=original.replace(needle,b'action="/evil" action="/server-java/FileDownLoad"')
    with pytest.raises(ValueError):select(raw)


def test_latest_past_no_attachments_does_not_fall_back_to_previous_quarter():
    after=datetime(2026,10,15,14,0,tzinfo=TAIPEI).timestamp()
    assert select(index_raw(),as_of_epoch=after) is None
    before=after-1
    assert select(index_raw(),as_of_epoch=before)['filename']=='233020260716E001.pdf'


def test_english_absent_selects_same_row_chinese_not_older_english():
    def change(s):latest_row(s).find_all('td')[7].string='內容檔案於當日會後公告於公開資訊觀測站'
    value=select(edited(change))
    assert value['filename']=='233020260716M001.pdf' and value['language']=='zh-TW'


def test_same_day_latest_time_not_first_dom_row_controls_selection():
    def change(s):
        row=deepcopy(latest_row(s));row.find_all('td')[3].string='16:00'
        for cell in row.find_all('td')[6:8]:cell.string=''
        latest_row(s).insert_before(row)
    assert select(edited(change)) is None


def test_same_day_unknown_time_is_ambiguous():
    def change(s):
        row=latest_row(s);row.find_all('td')[2].string='115/10/14';row.find_all('td')[3].string=''
    with pytest.raises(ValueError):select(edited(change))


def test_identical_duplicate_rows_can_share_request():
    baseline=select(index_raw())
    value=select(edited(lambda s:latest_row(s).insert_after(deepcopy(latest_row(s)))))
    assert value['request_sha256']==baseline['request_sha256']
    assert value['event_date']==baseline['event_date']


def test_conflicting_older_same_event_is_not_silently_discarded():
    def change(s):
        row=deepcopy(body_rows(s)[0]);row.find_all('td')[5].string='相同事件但衝突擇要'
        body_rows(s)[0].insert_after(row)
    with pytest.raises(ValueError):select(edited(change))


def test_multiday_requires_final_day_to_have_passed():
    raw=index_raw('2303')
    value=select(raw,ticker='2303.TW',as_of_epoch=datetime(2026,9,15,23,59,tzinfo=TAIPEI).timestamp())
    assert value['event_date']=='2026-09-10'
    value=select(raw,ticker='2303.TW',as_of_epoch=datetime(2026,9,16,0,0,tzinfo=TAIPEI).timestamp())
    assert value['event_date']=='2026-09-14' and value['event_end_date']=='2026-09-15'


@pytest.mark.parametrize('raw',[b'',b'<html>access denied</html>',b'\xff',b'not an index',b'x'*2_500_001])
def test_invalid_or_denied_original_cannot_grant_request(raw):
    with pytest.raises(ValueError):select(raw)


@pytest.mark.parametrize('date_text',['115/02/30','115/09/14 junk','115/09/14 至 115/09/13'])
def test_invalid_event_dates(date_text):
    with pytest.raises(ValueError):select(edited(lambda s:latest_row(s).find_all('td')[2].__setattr__('string',date_text)))


def test_otc_shape_requires_matching_market_without_claiming_live_qualification():
    value=select(edited(lambda s:s.select_one('input[name="TYPEK"]').__setitem__('value','otc')),ticker='2330.TWO')
    assert value['ticker']=='2330.TWO'
    # This synthetic parser boundary does not establish an actual OTC issuer.


@pytest.mark.parametrize('where',['body','head'])
def test_extra_mixed_header_data_cells_do_not_preserve_valid_shape(where):
    def change(s):
        row=latest_row(s) if where=='body' else s.select_one('#myTable thead tr')
        row.append(s.new_tag('th' if where=='body' else 'td'))
    with pytest.raises(ValueError):select(edited(change))


@pytest.mark.parametrize('cut',['future-row','html-end'])
def test_incomplete_original_cannot_select_older_material(cut):
    soup=BeautifulSoup(index_raw(),'html.parser');text=str(soup)
    stop=text.index(str(body_rows(soup)[-1])) if cut=='future-row' else text.rindex('</html>')
    with pytest.raises(ValueError):select(text[:stop].encode())


def test_malformed_declaration_uses_public_value_error_contract():
    with pytest.raises(ValueError):select(b'<![not-html]>'+index_raw())


@pytest.mark.parametrize('file_date,allowed', [('20261015', False), ('20261014', True)])
def test_selected_material_cannot_be_dated_after_taipei_observation(file_date, allowed):
    original = index_raw('1229')
    old = b'122920260930E001.pptx'
    assert original.count(old) == 2  # exact anchor text and static onclick
    raw = original.replace(old, f'1229{file_date}E001.pptx'.encode())
    if not allowed:
        with pytest.raises(ValueError, match='material date'):
            select_published_material(raw, '1229.TW', as_of_epoch=AS_OF, company_name='聯華')
    else:
        value = select_published_material(raw, '1229.TW', as_of_epoch=AS_OF, company_name='聯華')
        assert value['material_file_date'] == '2026-10-14'
        assert value['event_date'] == '2026-09-30'
