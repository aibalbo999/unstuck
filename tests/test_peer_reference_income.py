"""Synthetic protocol scaffolding; real full originals are replayed separately."""
from datetime import date
import json
import pytest

DAY=date(2026,11,4)


def reference_body(*, pe='-', quarter='115/2'):
    rows=[[str(1000+i),'fixture issuer','10.00','0.00',114,'10.00','1.00','115/2']for i in range(800)]
    rows.append(['6230','尼得科超眾','99.00','0.00',114,pe,'1.47',quarter])
    return json.dumps({'stat':'OK','date':'20261104','selectType':'ALL','total':len(rows),'fields':['證券代號','證券名稱','收盤價','殖利率(%)','股利年度','本益比','股價淨值比','財報年/季'],'data':rows},ensure_ascii=False).encode()


def index_body(year, quarters):
    heads=['證券代號','資料年度','資料類型','結案類型','性質','資料細節說明','備註','電子檔案','檔案大小','上傳日期','財務報告更(補)正']
    rows=[]
    for q in quarters:
        filename=f'{year}{q:02d}_6230_AI1.pdf'
        upload=f'{year-1911}/08/12 15:01:11'if q==2 else f'{year-1910}/03/13 14:00:04'
        cells=['6230',f'{year-1911} 年 第'+{1:'一',2:'二',3:'三',4:'四'}[q]+'季','財務報告書','','','IFRSs合併財報','fixture consolidated filing',f'<a href=\'javascript:readfile2("A","6230","{filename}");\'>{filename}</a>','1,000,000',upload,'無']
        rows.append('<tr>'+''.join('<td>'+x+'</td>'for x in cells)+'</tr>')
    return ('<html><body>公司名稱：尼得科超眾 會計期間：曆年制<table><tr>'+''.join('<td>'+x+'</td>'for x in heads)+'</tr>'+''.join(rows)+'</table></body></html>').encode('big5')


def income_body(year, quarter, income):
    # Cumulative amounts; this is not a synthetic native acquisition.
    labels=['營業收入合計','營業毛利（毛損）淨額','營業利益（損失）','本期淨利（淨損）','母公司業主（淨利∕損）']
    values=['4,678,093','812,056','31,860',f'{income:,}',f'{income:,}']
    return ('<div>金額單位：新台幣仟元</div><table><thead><tr><th>報表類別</th></tr><tr><th>會計科目</th></tr></thead><tbody>'+''.join('<tr><td>'+x+'</td></tr>'for x in labels)+'</tbody></table><table><thead><tr><th>合併</th></tr><tr><th>6230 尼得科超眾 (上市電腦及週邊設備業)</th></tr></thead><tbody>'+''.join('<tr><td>'+x+'</td></tr>'for x in values)+'</tbody></table>'+f'<input name="yearseason" value="{year}Q{quarter}"/><input name="year" value="{year}"/><input name="season" value="{quarter}"/>').encode()


def test_official_reference_binds_missing_pe_to_a_closed_specific_quarter():
    from data_fetch.market_sources.peer_reference_income import parse_reference
    value=parse_reference(reference_body(),DAY)
    assert value['year']==2026 and value['quarter']==2 and value['raw_pe']=='-'


def test_complete_calendar_index_binds_both_needed_annual_and_prior_ytd_filings():
    from data_fetch.market_sources.peer_reference_income import parse_calendar_index
    value=parse_calendar_index(index_body(2025,[2,4]),2025,[2,4],DAY)
    assert set(value)=={2,4} and value[4]['filename']=='202504_6230_AI1.pdf'


def test_cumulative_income_uses_parent_money_and_never_single_quarter_eps():
    from data_fetch.market_sources.peer_reference_income import parse_cumulative_income
    assert parse_cumulative_income(income_body(2026,2,-156827),2026,2)==-156827000


@pytest.mark.parametrize('change',['positive_pe','blank_pe','future_quarter','stale_quarter','wrong_name','wrong_day','duplicate','incomplete_roster','wrong_total','subset'])
def test_reference_does_not_turn_unqualified_missing_values_into_loss(change):
    from data_fetch.market_sources.peer_reference_income import parse_reference
    v=json.loads(reference_body())
    if change=='positive_pe':v['data'][-1][5]='12.00'
    elif change=='blank_pe':v['data'][-1][5]=''
    elif change=='future_quarter':v['data'][-1][7]='115/4'
    elif change=='stale_quarter':v['data'][-1][7]='113/4'
    elif change=='wrong_name':v['data'][-1][1]='another company'
    elif change=='wrong_day':v['date']='20261103'
    elif change=='duplicate':v['data'].append(v['data'][-1])
    elif change=='wrong_total':v['total']+=1
    elif change=='subset':v['selectType']='25'
    else:v['data']=v['data'][-1:]
    with pytest.raises(ValueError):parse_reference(json.dumps(v,ensure_ascii=False).encode(),DAY)


@pytest.mark.parametrize('change',['non_calendar','corrected','wrong_action','wrong_year','same_day_upload','truncated','duplicate'])
def test_index_requires_complete_correctly_dated_calendar_scope_and_actions(change):
    from data_fetch.market_sources.peer_reference_income import parse_calendar_index
    raw=index_body(2025,[2,4]).decode('big5')
    if change=='non_calendar':raw=raw.replace('曆年制','非曆年制')
    elif change=='corrected':raw=raw.replace('<td>無</td>','<td>財報更正</td>')
    elif change=='wrong_action':raw=raw.replace('readfile2("A","6230"','readfile2("A","2330"')
    elif change=='wrong_year':raw=raw.replace('114 年','113 年')
    elif change=='same_day_upload':raw=raw.replace('115/03/13','115/11/04')
    elif change=='truncated':raw=raw.replace('</html>','')
    else:
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(raw,'html.parser');soup.table.append(BeautifulSoup(str(soup.table.find_all('tr')[-1]),'html.parser').tr);raw=str(soup)
    with pytest.raises(ValueError):parse_calendar_index(raw.encode('big5'),2025,[2,4],DAY)


@pytest.mark.parametrize('change',['wrong_period','duplicate_period','wrong_scope','wrong_issuer','wrong_unit','total_parent_conflict','missing_parent','duplicate_parent'])
def test_income_keeps_unknown_scope_period_unit_and_parent_claims_rejected(change):
    from data_fetch.market_sources.peer_reference_income import parse_cumulative_income
    raw=income_body(2026,2,-156827)
    if change=='wrong_period':raw=raw.replace(b'value="2026Q2"',b'value="2025Q2"')
    elif change=='duplicate_period':raw+=b'<input name="yearseason" value="2026Q2"/>'
    elif change=='wrong_scope':raw=raw.replace('合併'.encode(),'個體'.encode())
    elif change=='wrong_issuer':raw=raw.replace(b'6230',b'2330')
    elif change=='wrong_unit':raw=raw.replace('新台幣仟元'.encode(),'美元仟元'.encode())
    else:
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(raw,'html.parser');left,right=soup.find_all('table');labels=left.select('tbody tr');values=right.select('tbody tr')
        k,v=next((k,v)for k,v in zip(labels,values)if k.get_text(' ',strip=True)=='母公司業主（淨利∕損）')
        if change=='total_parent_conflict':v.td.string='-10'
        elif change=='missing_parent':k.decompose();v.decompose()
        else:left.tbody.append(BeautifulSoup(str(k),'html.parser').tr);right.tbody.append(BeautifulSoup(str(v),'html.parser').tr)
        raw=str(soup).encode()
    with pytest.raises(ValueError):parse_cumulative_income(raw,2026,2)


def test_negative_single_period_or_missing_prior_ytd_does_not_establish_nonpositive_ttm():
    from data_fetch.market_sources.peer_reference_income import derive_nonpositive_income
    with pytest.raises(ValueError):derive_nonpositive_income(2026,2,{(2026,2):-100})
    with pytest.raises(ValueError):derive_nonpositive_income(2026,2,{(2026,2):-100,(2025,2):200,(2025,4):1000})
    value=derive_nonpositive_income(2026,2,{(2026,2):-156827000,(2025,2):69020000,(2025,4):-210560000})
    assert value['net_income_twd']==-436407000 and value['period_start']=='2025-07-01'and value['period_end']=='2026-06-30'
    assert derive_nonpositive_income(2025,4,{(2025,4):0})['net_income_twd']==0


def test_rule_does_not_infer_loss_from_missing_pe_or_from_changed_publisher_methodology():
    from data_fetch.market_sources.peer_reference_income import parse_methodology
    for raw in [b'<html><body>missing</body></html>',
        '<html><body><li>本益比空白就是虧損</li></body></html>'.encode()]:
        with pytest.raises(ValueError):parse_methodology(raw)


def test_published_nested_rule_is_one_leaf_but_duplicate_leaf_rules_are_rejected():
    from data_fetch.market_sources.peer_reference_income import parse_methodology
    clause=('本益比=收盤價／每股參考稅後純益，其中每股參考稅後純益=該公司稅後參考純益／發行參考股數，'
        '當每股參考稅後純益為0或負數時，則不計算本益比。近滿4季財務報告為計算基礎')
    parse_methodology(('<html><body><li>基礎<ul><li>'+clause+'</li></ul></li></body></html>').encode())
    with pytest.raises(ValueError):
        parse_methodology(('<html><body><ul><li>'+clause+'</li><li>'+clause+'</li></ul></body></html>').encode())
