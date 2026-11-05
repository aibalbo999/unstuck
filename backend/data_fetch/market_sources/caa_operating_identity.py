"""Exact current issuer / national operator / curated source-label bridge."""
import re
from bs4 import BeautifulSoup
PROFILES={
 '2610.TW':('中華','中華航空','CI','中華航空股份有限公司','11145904','華航'),
 '2618.TW':('長榮','長榮航空','BR','長榮航空股份有限公司','23225229','長榮航'),
 '2646.TW':('星宇','星宇航空','JX','星宇航空股份有限公司','51712072','星宇航空'),
 '6757.TW':('台灣虎航','台灣虎航','IT','台灣虎航股份有限公司','54381049','台灣虎航'),
}
NATIONAL={'中華航空(CI)','長榮航空(BR)','華信航空(AE)','立榮航空(B7)','台灣虎航(IT)','星宇航空(JX)'}
def directory(raw):
    if not isinstance(raw,bytes)or not 100<=len(raw)<=500000:raise ValueError('directory_size')
    text=raw.decode('utf-8',errors='strict')
    if len(re.findall(r'<html(?:\s|>)',text,re.I))!=1 or len(re.findall(r'</html\s*>',text,re.I))!=1:raise ValueError('HTML_root_shape')
    page=BeautifulSoup(text,'html.parser');contents=page.select('div.content#content')
    if len(contents)!=1:raise ValueError('business_scope')
    content=contents[0];titles=content.find_all('h2')
    if len(titles)!=1 or titles[0].get_text(strip=True)!='本局及航空公司旅客諮詢服務電話':raise ValueError('business_title')
    tables=content.find_all('table')
    if len(tables)!=2:raise ValueError('business_tables')
    rows=tables[0].find_all('tr')
    if not 60<=len(rows)<=120:raise ValueError('directory_rows')
    if [c.get_text(strip=True)for c in rows[0].find_all(['th','td'],recursive=False)]!=['航空公司','區域別','服務電話']:raise ValueError('directory_header')
    names=[]
    for row in rows[1:]:
        cells=row.find_all(['th','td'],recursive=False)
        if len(cells)!=3:raise ValueError('directory_row_shape')
        if cells[1].get_text(strip=True)=='國籍':names.append(cells[0].get_text(strip=True))
    if len(names)!=6 or set(names)!=NATIONAL:raise ValueError('national_operator_scope')
    return names

def bind(raw,master_rows):
    names=directory(raw);result={}
    if not isinstance(master_rows,list):raise ValueError('master_shape')
    for ticker,p in PROFILES.items():
        label,full,code,legal,ubn,short=p
        rows=[r for r in master_rows if isinstance(r,dict)and r.get('公司代號')==ticker.split('.')[0]]
        if len(rows)!=1:raise ValueError('master_identity_ambiguous')
        row=rows[0]
        if any(row.get(k)!=v for k,v in {'公司名稱':legal,'營利事業統一編號':ubn,'公司簡稱':short,'產業別':'15'}.items()):raise ValueError('master_exact_legal_UBN_industry_mismatch')
        if legal!=full+'股份有限公司'or names.count(full+'('+code+')')!=1:raise ValueError('publisher_current_legal_bridge')
        result[ticker]={'ticker':ticker,'source_operator_label':label,'CAA_full_operator_name':full,'CAA_IATA_code':code,'legal_name':legal,'UBN':ubn,'official_short_name':short,'binding_basis':'Closed source-label profile plus exact CAA national operator/full name/IATA and independent complete current TWSE master legal name/UBN/ticker. CAA does not publish stock codes in this table.','scope':'Named airline operating entity, never consolidated group or subsidiary aggregation.','historical_point_in_time_verified':False,'current_license_effective_date_verified':False}
    return result
