import pytest
from test_official_financial_claim_binding import projected, checked

@pytest.mark.parametrize('text', [
 '台積電2026-06-30總負債／權益：66.67%',
 '未知公司2026-06-30總負債／權益：66.67%',
 '本公司合併2026-06-30總負債／權益：66.67%',
 '未來2026-06-30總負債／權益：66.67%',
 '預測2026-06-30總負債／權益：66.67%',
 '2025-06-30與2026-06-30總負債／權益：66.67%',
 '2026-06-30借款不含租賃負債／權益：46.67%',
 '2026-06-30借款扣除租賃負債／權益：46.67%',
 '2026-06-30總負債／權益：66.67%（美元）',
])
def test_ratio_scope(text):
 from evidence_official_financial_claims import official_ratio_claim
 amount=46.67 if '46.67' in text else 66.67
 c={'label':text.partition('：')[0], 'unit':'%', 'reported_value':amount,'raw_text':text}
 r=official_ratio_claim(c, {'data':projected()},1.0)
 assert r['status']=='unverifiable',r

@pytest.mark.parametrize('prefix,status', [
 ('本公司合併TTM', 'unverifiable'), ('本集團TTM', 'unverifiable'),
 ('2026-06-30TTM', 'verified'), ('TTM2025-07-01', 'unverifiable'),
 ('本公司官方個別TTM', 'verified')])
def test_fcf_scope_and_date(prefix,status):
 result=checked(prefix+'自由現金流為0.0885億元。')
 assert len(result)==1 and result[0]['status']==status,result

@pytest.mark.parametrize('text', [
 '台積電2026-06-30總負債／權益：66.67%',
 '未來2026-06-30總負債／權益：66.67%',
 '2026-06-30借款不含租賃負債／權益：46.67%'])
def test_real_extracted_ratio(text):
 result=checked(text)
 assert result and all(c['status']=='unverifiable' for c in result),result

@pytest.mark.parametrize('text', [
 '本公司TTM截至2025-07-01自由現金流為0.0885億元。',
 '本公司TTM期間2026-06-30至2025-07-01自由現金流為0.0885億元。',
 '# 預測情境\n本公司TTM自由現金流為0.0885億元。',
 '同業台積電：\n- TTM自由現金流為0.0885億元。',
 '合併財報：\n- TTM自由現金流為0.0885億元。',
 '單位為美元：\n- TTM自由現金流為0.0885億元。',
 '# 同業台積電\n2026-06-30總負債／權益：66.67%',
 '# 預測情境\n2026-06-30總負債／權益：66.67%',
])
def test_real_scope_boundaries(text):
 result=checked(text)
 assert result and all(c['status']=='unverifiable' for c in result), result

@pytest.mark.parametrize('text', [
 '本公司TTM自由現金流為0.0885億元（合併財報）。',
 '台積電，2026-06-30總負債／權益：66.67%',
 '2026-06-30總負債／權益：66.67%，此為台積電資料',
])
def test_postfix_or_prior_owner(text):
 result=checked(text)
 assert result and all(c['status']=='unverifiable' for c in result), result


def test_positive_official_cashflow_cannot_be_verified_as_outflow():
 result=checked('本公司TTM自由現金流為0.0885億元（淨流出）。')
 assert result and all(c['status']=='mismatch' for c in result),result
