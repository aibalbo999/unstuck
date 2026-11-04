"""Publication metadata never substitutes for complete financial JSON facts."""
from pathlib import Path
import time

import pytest


def html(year=2025,*,change=''):
    choices={y:str(100+y)for y in range(2021,2027)}
    options='<option value="">請選擇年度</option>'+''.join(
        f'<option value="{v}"'+(' selected'if y==year else'')+f'>{y-1911}年度</option>'for y,v in choices.items())
    annual=''if year==2026 else f'<a href="/upload/38/{year}031616464943765.pdf">兆豐金控{year-1911}年度IFRSs合併財報</a>'
    raw=(f'<html><head><title>兆豐金控</title></head><body><form action="./investors_1.aspx?trclassify={choices[year]}" method="post">'
        '<div id="download_box">兆豐金控會計師查核(核閱)財務報告'
        '<select name="ctl00$ContentPlaceHolder1$classifyID">'+options+'</select>'+annual+'</div></form>'
        '<footer>兆豐金融控股股份有限公司</footer></body></html>')
    if change=='truncated':raw=raw.replace('</html>','')
    elif change=='issuer':raw=raw.replace('兆豐金融控股股份有限公司','兆豐國際商業銀行股份有限公司')
    elif change=='selected':raw=raw.replace(' selected','')
    elif change=='quarter':raw=raw.replace(f'{year-1911}年度IFRSs',f'{year-1911}年第3季IFRSs')
    elif change=='foreign_url':raw=raw.replace('/upload/38/','https://other.example/upload/38/')
    elif change=='duplicate':raw=raw.replace(annual,annual+annual)
    elif change=='option':raw=raw.replace('value="2125"','value="2126"')
    return raw.encode()


def test_complete_catalogue_yields_only_explicit_year_and_published_document():
    from data_fetch.market_sources.mega_annual_catalog import parse_page
    p=parse_page(html(),time.time(),year=2025)
    assert p['selected_year']==2025 and p['annual_document']['title']=='兆豐金控114年度IFRSs合併財報'
    assert 'facts'not in p and 'values'not in p
    assert parse_page(html(2026),time.time(),year=2026)['annual_document']is None


@pytest.mark.parametrize('change',['truncated','issuer','selected','foreign_url','duplicate','option'])
def test_catalogue_identity_completeness_and_selection_refusals(change):
    from data_fetch.market_sources.mega_annual_catalog import parse_page
    with pytest.raises(ValueError):parse_page(html(change=change),time.time(),year=2025)


def test_quarter_is_an_empty_annual_catalogue_and_not_a_financial_report():
    from data_fetch.market_sources.mega_annual_catalog import parse_page
    assert parse_page(html(change='quarter'),time.time(),year=2025)['annual_document']is None


def test_wrong_year_annual_is_not_proof_of_annual_absence():
    from data_fetch.market_sources.mega_annual_catalog import parse_page
    raw=html().replace('兆豐金控114年度IFRSs'.encode(),'兆豐金控113年度IFRSs'.encode())
    with pytest.raises(ValueError):parse_page(raw,time.time(),year=2025)


def test_same_published_pdf_cannot_establish_five_distinct_annual_publications():
    from data_fetch.market_sources.mega_annual_catalog import publication_window
    stamp=time.time();pages=[]
    for year in range(2021,2027):
        raw=html(year).replace((str(year)+'031616464943765').encode(),b'2025031616464943765')
        pages.append({'year':year,'raw':raw,'retrieved_at':stamp})
    with pytest.raises(ValueError):publication_window(html(2026),stamp,pages)


def test_window_requires_every_contiguous_year_and_five_actual_annual_publications():
    from data_fetch.market_sources.mega_annual_catalog import publication_window
    root=html(2026);stamp=time.time()-1;pages=[{'year':y,'raw':html(y),'retrieved_at':time.time()}
        for y in range(2026,2020,-1)]
    result=publication_window(root,stamp,pages)
    assert result['years']==[2021,2022,2023,2024,2025]and result['annual_absence_years']==[2026]
    for bad in(pages[:-1],pages+[pages[-1]],pages[1:]):
        with pytest.raises(ValueError):publication_window(root,stamp,bad)
    bad=[dict(p,raw=html(p['year'],change='quarter'))if p['year']==2023 else p for p in pages]
    with pytest.raises(ValueError):publication_window(root,stamp,bad)


def test_saved_native_catalogues_replay_without_HTTP_or_financial_numeric_promotion():
    from data_fetch.market_sources.mega_annual_catalog import publication_window
    folder=Path('/Volumes/X10 Pro Mac/stock-agent-archives/continuation-20261104-mega-official-catalog-discovery')
    if not folder.exists():pytest.skip('Private native research is unavailable; synthetic contracts remain active')
    import json
    window=json.loads((folder/'annual-window/research-result.json').read_text())
    rows=[]
    for c in window['catalogues']:
        if c['fiscal_year']==2025:p=folder/'observed-response-1.bin'
        else:
            match=next(p for p in (folder/'annual-window').glob('observed-response-*.json')
                if json.loads(p.read_text())['raw_sha256']==c['original_sha256'])
            p=Path(json.loads(match.read_text())['raw_path'])
        rows.append({'year':c['fiscal_year'],'raw':p.read_bytes(),'retrieved_at':c['receipt']['retrieved_at']})
    root=rows[0]['raw'];stamp=rows[0]['retrieved_at']
    assert publication_window(root,stamp,rows)['years']==[2021,2022,2023,2024,2025]
