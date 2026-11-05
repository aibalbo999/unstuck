"""A published annex-only correction needs its own full, bound original."""
from datetime import date
from bs4 import BeautifulSoup
import pytest
from test_peer_reference_income import index_body
from data_fetch.market_sources.peer_reference_income import parse_calendar_index

ACTION='http://mopsov.twse.com.tw/mops/web/t56sb31_q1?step=2&colorchg=1&TYPEK=sii&kind=&CID=2723&YEAR_SEASON=202504&RID=4&DTYPE=I1&SKEY=1&firstin=1'

def corrected_index():
    text=index_body(2025,[2,4]).decode('big5').replace('6230','2723').replace('尼得科超眾','美食-KY');s=BeautifulSoup(text,'html.parser');last=s.table.find_all('tr')[-1].find_all('td')[-1];last.clear();button=s.new_tag('input',type='button',value='詳細資料');button['onclick']="location.href='"+ACTION+"';";last.append(button);return str(s).encode('big5')

def notice_body():
    rows=[['年度季別','11404','財報類別','合併'],['','','資料說明','IFRSs合併財報'],['更（補）正內容','附表一-資金貸與他人數值有誤'],['更（補）正項目','1.財務報表─四大報表','無變動'],['2.財報附註','無變動'],['3.其他','附表一'],['4.附件','<a href="/nas/t56sa23/202504/t56sa23_2723_202504_4_1_I1.pdf">t56sa23_2723_202504_4_1_I1.pdf</a>']]
    return ('<html><body><div id="table01"><td class="compName">公司代號：2723 公司名稱：美食-KY</td><table class="hasBorder">'+''.join('<tr>'+''.join('<td>'+v+'</td>'for v in row)+'</tr>'for row in rows)+'</table></div></body></html>').encode()

def test_full_index_rejection_identifies_exact_published_missing_original_after_schema_checks():
    with pytest.raises(ValueError)as raised:parse_calendar_index(corrected_index(),2025,[2,4],date(2026,11,4),issuer_ticker='2723.TW')
    assert type(raised.value).__name__=='CorrectionRequired'
    assert raised.value.published_action==ACTION and raised.value.year==2025 and raised.value.quarter==4


def test_complete_annex_only_notice_does_not_suppress_original_correction_marker():
    result=parse_calendar_index(corrected_index(),2025,[2,4],date(2026,11,4),issuer_ticker='2723.TW',correction_originals={(2025,4):notice_body()})
    assert result[4]['correction_notice_sha256']
    assert result[4]['correction_scope']=='annex_only_four_statements_and_notes_unchanged'

@pytest.mark.parametrize('change',['income_changed','notes_changed','annex_changed','wrong_issuer','wrong_period','missing_line','duplicate_identity','truncated'])
def test_changed_or_ambiguous_correction_never_qualifies(change):
    from data_fetch.market_sources.gourmet_correction_notice import parse_notice
    raw=notice_body()
    if change=='income_changed':raw=raw.replace('無變動'.encode(),'損益有變動'.encode(),1)
    if change=='notes_changed':raw=raw.replace('2.財報附註</td><td>無變動'.encode(),'2.財報附註</td><td>有變動'.encode())
    if change=='annex_changed':raw=raw.replace('附表一'.encode(),'附表二'.encode())
    if change=='wrong_issuer':raw=raw.replace(b'2723',b'6558')
    if change=='wrong_period':raw=raw.replace(b'11404',b'11504')
    if change=='missing_line':raw=raw.replace('<tr><td>2.財報附註</td><td>無變動</td></tr>'.encode(),b'')
    if change=='duplicate_identity':raw=raw.replace(b'<table',b'<td class="compName">duplicate</td><table',1)
    if change=='truncated':raw=raw[:-7]
    with pytest.raises(ValueError):parse_notice(raw)

@pytest.mark.parametrize('damage',['issuer','action','extra_query','wrong_scope','truncated_index','duplicate_quarter'])
def test_index_must_be_fully_qualified_before_requesting_any_notice(damage):
    raw=corrected_index()
    if damage=='issuer':raw=raw.replace(b'2723',b'6558')
    if damage=='action':raw=raw.replace(b'SKEY=1',b'SKEY=2')
    if damage=='extra_query':raw=raw.replace(b'firstin=1',b'firstin=1&unexpected=1')
    if damage=='wrong_scope':raw=raw.replace('IFRSs合併財報'.encode('big5'),'IFRSs個別財報'.encode('big5'))
    if damage=='truncated_index':raw=raw.replace(b'</html>',b'')
    if damage=='duplicate_quarter':
        s=BeautifulSoup(raw.decode('big5'),'html.parser');s.table.append(BeautifulSoup(str(s.table.find_all('tr')[-1]),'html.parser').tr);raw=str(s).encode('big5')
    with pytest.raises(ValueError)as raised:parse_calendar_index(raw,2025,[2,4],date(2026,11,4),issuer_ticker='2723.TW')
    assert type(raised.value).__name__!='CorrectionRequired'


def test_correction_spec_is_exact_published_action_and_cannot_cross_issuer_subject():
    from data_fetch.market_sources import peer_reference_transport as t
    request=t.spec('correction',year=2025,quarter=4,peer_ticker='2723.TW',published_action=ACTION)
    assert request['method']=='GET'and request['url']==ACTION.replace('http://','https://',1)
    assert t.canonical_spec(request)==request
    for ticker in ['6230.TW','6558.TW','2646.TW']:
        with pytest.raises(ValueError):t.PeerIncomeHttp(peer_ticker=ticker)._bound_request(request)
    for change in [{'year':2026},{'quarter':2},{'peer_ticker':'6558.TW'},{'published_action':ACTION+'&x=1'}]:
        args=dict(year=2025,quarter=4,peer_ticker='2723.TW',published_action=ACTION);args.update(change)
        with pytest.raises(ValueError):t.spec('correction',**args)


def test_observed_legacy_inner_closing_fragment_keeps_whole_original_not_sliced():
    from data_fetch.market_sources.gourmet_correction_notice import parse_notice
    raw=notice_body().replace(b'</div></body></html>',b'</center></body></html></div></body></html>')
    assert parse_notice(raw)['scope']=='annex_only_four_statements_and_notes_unchanged'
    with pytest.raises(ValueError):parse_notice(notice_body().replace(b'</div></body></html>',b'</html></div></body></html>'))
    with pytest.raises(ValueError):parse_notice(raw+b'</html>')
