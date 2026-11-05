from datetime import date
import pytest
from data_fetch.market_sources.caa_operating_parse import select_dataset
from data_fetch.market_sources.caa_operating_parse import parse_dataset
from data_fetch.market_sources.caa_operating_ods import replay,T,O
from caa_operating_fixtures import ods,directory,master,index_page

def test_exact_newest_dataset_and_publication_date():
    result=select_dataset(index_page(),date(2026,11,5))
    assert result is not None
    assert result['url']=='https://www.caa.gov.tw/FileAtt.ashx?lang=1&id=41753'
    assert result['year']==2026 and result['published_date']=='2026-10-27'

def test_published_XLS_sibling_does_not_hide_the_exact_ODS():
    # Actual complete CAA index has .xls, .ods and .pdf; only ODS is downloaded.
    raw=index_page().replace(b'</td></tr>',b'<a class="download-filebase" title="115\xe5\xb9\xb4.xls" href="../FileAtt.ashx?lang=1&amp;id=41755">XLS not consumed</a></td></tr>')
    assert select_dataset(raw,date(2026,11,5))['url'].endswith('id=41753')

@pytest.mark.parametrize('raw',[index_page(116),index_page(113),index_page(115,False),index_page(published='2026/11/06'),index_page(published='2025/10/27'),index_page()+index_page(),index_page().replace('國籍航空公司全球航線客貨運概況'.encode(),b'financial membership'),index_page().replace(b'../FileAtt.ashx',b'https://evil.example/FileAtt.ashx')])
def test_invalid_latest_or_scope_has_no_old_fallback(raw):
    with pytest.raises(ValueError):select_dataset(raw,date(2026,11,5))

def test_dataset_separates_named_operator_monthly_YTD_and_numeric_units():
    v=parse_dataset(index_page(),ods(),directory(),master(),'2610.TW',date(2026,11,5))
    assert v['ticker']=='2610.TW'and v['issuer']['legal_name']=='中華航空股份有限公司'
    assert len(v['monthly_history'])==9 and v['latest_month']==9
    assert v['monthly_history'][0]['values']['passengers']['native_numeric_string']=='1'
    assert v['year_to_date']['values']['passengers']['native_numeric_string']=='9'
    assert v['year_to_date']['values']['cargo_tonnes']['unit']=='公噸'
    assert v['coverage_status']=='named_carrier_operating_metrics_only'
    assert not any('job_count'in str(r)for r in v['monthly_history'])

@pytest.mark.parametrize('today,months,year',[(date(2026,11,5),8,2026),(date(2027,1,20),11,2026),(date(2027,3,20),2,2027)])
def test_calendar_and_complete_gapless_months(today,months,year):
    rows=replay(ods(months,year),year,today)
    assert len(rows)==months*16 and {r['year']for r in rows}=={year}

@pytest.mark.parametrize('today,months',[(date(2026,11,5),12),(date(2026,11,5),6)])
def test_future_or_over90day_source_rejected(today,months):
    with pytest.raises(ValueError):replay(ods(months),2026,today)

def test_month_hole_does_not_fallback():
    def change(table,month):
        if month==8:table.set(T+'name','11507')
    with pytest.raises(ValueError):replay(ods(mutate=change),2026,date(2026,11,5))

@pytest.mark.parametrize('kind',['period','units','operator','dash','display','repeated','total'])
def test_corrupted_cells_remain_rejected(kind):
    def change(table,month):
        if month!=9:return
        rows=table.findall(T+'table-row')
        ri,ci,text={'period':(6,0,'中華民國114年9月份'),'units':(9,3,'載客人數(千人)'),'operator':(12,11,'華信'),'dash':(12,3,'-'),'display':(12,3,'99'),'total':(11,3,'99')}.get(kind,(12,3,'1'))
        cell=list(rows[ri])[ci]
        if kind=='repeated':cell.set(T+'number-columns-repeated','2');return
        next(cell.iter('p')).text=text
        if kind=='dash':cell.set(O+'value','0')
        if kind=='total':cell.set(O+'value','99')
    with pytest.raises(ValueError):replay(ods(mutate=change),2026,date(2026,11,5))
