"""An individual issuer must never borrow the parent-income contract."""
from datetime import date
import json
import pytest
from data_fetch.market_sources import starair_reference_income as p


def income(year=2026,quarter=2,*,scope='個別',label='本期淨利（淨損）',value='-345,520',company='2646 星宇航空 (上市航運業)',unit='金額單位：新台幣仟元'):
    return (f'<div>{unit}</div><input name="yearseason" value="{year}Q{quarter}"><input name="year" value="{year}"><input name="season" value="{quarter}">'
            f'<table><tbody><tr><td>{label}</td></tr></tbody></table><table><thead><tr><th>{scope}</th><th>{company}</th></tr></thead><tbody><tr><td>{value}</td></tr></tbody></table>').encode()


def index(*,kind='IFRSs個別財報',filename='202502_2646_AI2.pdf',correction='無',calendar='曆年制',stamp='114/08/14 11:00:21'):
    head=''.join('<th>'+v+'</th>'for v in p.INDEX_FIELDS)
    values=['2646','114 年 第二季','財務報告書','','',kind,'',f'<a href=\'javascript:readfile2("A","2646","{filename}");\'>{filename}</a>','580,611',stamp,correction]
    return ('<html><body>公司名稱：星宇航空 會計期間：'+calendar+'<table><tr>'+head+'</tr><tr>'+''.join('<td>'+v+'</td>'for v in values)+'</tr></table></body></html>').encode('big5')


def test_disjoint_individual_income_matches_real_case_arithmetic():
    values={(2026,2):p.parse_cumulative_income(income(),2026,2),(2025,2):p.parse_cumulative_income(income(2025,2,value='923,243'),2025,2),(2025,4):p.parse_cumulative_income(income(2025,4,value='272,608'),2025,4)}
    result=p.derive_nonpositive_income(2026,2,values)
    assert result['net_income_twd']==-996155000
    assert result['basis']=='reported_cumulative_individual_income'
    assert result['period_start']=='2025-07-01'and result['period_end']=='2026-06-30'


@pytest.mark.parametrize('kwargs',[{'scope':'合併'},{'scope':'個體'},{'label':'母公司業主（淨利∕損）'},{'company':'6230 尼得科超眾 (上市電腦及週邊設備業)'},{'company':'26460 星宇航空 (上市航運業)'},{'company':'2646 子公司 (上市航運業)'},{'unit':'金額單位：美元仟元'},{'value':'-'},{'value':'NaN'},{'value':'1e3'}])
def test_scope_identity_unit_and_unknown_do_not_relax(kwargs):
    with pytest.raises(ValueError):p.parse_cumulative_income(income(**kwargs),2026,2)


def test_mother_or_NCI_rows_cannot_be_ignored_in_individual_statement():
    raw=income().decode().replace('</tbody></table>', '<tr><td>母公司業主（淨利∕損）</td></tr></tbody></table>',1)
    raw=raw.replace('<td>-345,520</td></tr>','<td>-345,520</td></tr><tr><td>-345,520</td></tr>')
    with pytest.raises(ValueError):p.parse_cumulative_income(raw.encode(),2026,2)


def test_period_duplicate_or_truncated_table_rejects():
    with pytest.raises(ValueError):p.parse_cumulative_income(income(),2025,2)
    with pytest.raises(ValueError):p.parse_cumulative_income(income()+b'<input name="year" value="2026">',2026,2)
    with pytest.raises(ValueError):p.parse_cumulative_income(income().replace(b'</table>',b'',1),2026,2)


def test_filing_index_is_explicit_individual_AI2_and_calendar():
    result=p.parse_calendar_index(index(),2025,[2],date(2026,11,3))
    assert result[2]['filename']=='202502_2646_AI2.pdf'and result[2]['scope']=='individual'


@pytest.mark.parametrize('kwargs',[{'kind':'IFRSs合併財報'},{'kind':'IFRSs個體財報'},{'filename':'202502_2646_AI1.pdf'},{'correction':'有'},{'calendar':'非曆年制'},{'stamp':'115/11/03 11:00:21'}])
def test_other_report_type_revision_calendar_or_future_not_admitted(kwargs):
    with pytest.raises(ValueError):p.parse_calendar_index(index(**kwargs),2025,[2],date(2026,11,3))


def test_positive_unknown_and_mixed_period_arithmetic_do_not_explain_PE():
    for values in ({(2026,2):100,(2025,2):50,(2025,4):500},{(2026,2):None,(2025,2):50,(2025,4):500},{(2026,2):False,(2025,2):50,(2025,4):500},{(2026,2):-1,(2025,2):50,(2024,4):500}):
        with pytest.raises(ValueError):p.derive_nonpositive_income(2026,2,values)


def reference(*,pe='-',short='星宇航空'):
    rows=[[str(10000+n),'test','1','0',114,'10','1','115/2']for n in range(800)]
    rows.append(['2646',short,'19.65','0',114,pe,'1.92','115/2'])
    return json.dumps({'stat':'OK','date':'20261103','fields':p.FIELDS,'selectType':'ALL','total':len(rows),'data':rows},ensure_ascii=False).encode()


def test_exact_reference_quarter_and_issuer_must_be_available():
    assert p.parse_reference(reference(),date(2026,11,3))['quarter']==2
    for raw in(reference(pe='20'),reference(short='其他公司')):
        with pytest.raises(ValueError):p.parse_reference(raw,date(2026,11,3))
    with pytest.raises(ValueError):p.parse_reference(reference(),date(2026,11,4))
