"""One published 2723 annex-only correction, not a generic corrected-file waiver."""
from hashlib import sha256
import re
from bs4 import BeautifulSoup

PUBLISHED_ACTION=('http://mopsov.twse.com.tw/mops/web/t56sb31_q1?step=2&colorchg=1&TYPEK=sii&kind='
                  '&CID=2723&YEAR_SEASON=202504&RID=4&DTYPE=I1&SKEY=1&firstin=1')
URL=PUBLISHED_ACTION.replace('http://','https://',1)
KEY='correction:2025Q4'


class CorrectionRequired(ValueError):
    def __init__(self):
        self.year=2025;self.quarter=4;self.published_action=PUBLISHED_ACTION
        super().__init__('complete published annex-only correction original required')


def request_url(action,ticker,year,quarter):
    if (ticker!='2723.TW' or type(year)is not int or year!=2025
            or type(quarter)is not int or quarter!=4 or action!=PUBLISHED_ACTION):
        raise ValueError('unqualified correction action or issuer period')
    return URL


def published_action(cell,ticker,year,quarter):
    request_url(PUBLISHED_ACTION,ticker,year,quarter)
    inputs=cell.find_all('input')
    if (cell.get_text(' ',strip=True) or len(inputs)!=1 or cell.find_all('a')
            or set(inputs[0].attrs)!={'type','value','onclick'}
            or inputs[0].get('type')!='button' or inputs[0].get('value')!='詳細資料'
            or inputs[0].get('onclick')!="location.href='"+PUBLISHED_ACTION+"';"):
        raise ValueError('unverified published correction action')
    return PUBLISHED_ACTION


def parse_notice(raw):
    if (not isinstance(raw,bytes)or not 0<len(raw)<=250000
            or not raw.rstrip().lower().endswith(b'</html>')or b'<!ENTITY'in raw.upper()):
        raise ValueError('complete correction notice original required')
    text=raw.decode('utf8','strict')
    closings=list(re.finditer(r'</html\s*>',text,re.I))
    if (len(re.findall(r'<html(?:\s[^<>]*)?>',text,re.I))!=1
            or len(closings)not in(1,2)):
        raise ValueError('ambiguous correction notice document')
    # This exact legacy endpoint embeds a center/body closing fragment before
    # its outer footer. Keep the entire response; do not slice or reconstruct
    # it. Arbitrary extra closers, extra roots and duplicate content still fail.
    if len(closings)==2 and not re.search(r'</center>\s*</body>\s*\Z',text[:closings[0].start()],re.I):
        raise ValueError('unrecognized legacy correction wrapper')
    soup=BeautifulSoup(text,'html.parser');roots=soup.select('#table01')
    if len(soup.find_all('html'))!=1:raise ValueError('multiple correction document roots')
    if len(roots)!=1:raise ValueError('correction notice content ambiguous')
    names=roots[0].select('.compName')
    if (len(names)!=1 or ''.join(names[0].get_text(' ',strip=True).split())
            !='公司代號：2723公司名稱：美食-KY'):
        raise ValueError('correction notice issuer mismatch')
    tables=roots[0].select('table.hasBorder')
    if len(tables)!=1:raise ValueError('correction notice table ambiguous')
    rows=tables[0].find_all('tr',recursive=False)
    values=[[c.get_text(' ',strip=True)for c in row.find_all(['td','th'],recursive=False)]for row in rows]
    expected=[['年度季別','11404','財報類別','合併'],['','','資料說明','IFRSs合併財報'],
              ['更（補）正內容','附表一-資金貸與他人數值有誤'],
              ['更（補）正項目','1.財務報表─四大報表','無變動'],['2.財報附註','無變動'],
              ['3.其他','附表一'],['4.附件','t56sa23_2723_202504_4_1_I1.pdf']]
    if values!=expected:raise ValueError('financial statements, notes or correction scope changed')
    links=rows[-1].find_all('a',href=True)
    if (len(links)!=1 or ''.join(links[0]['href'].split())
            !='/nas/t56sa23/202504/t56sa23_2723_202504_4_1_I1.pdf'):
        raise ValueError('correction annex action changed')
    return {'sha256':sha256(raw).hexdigest(),
            'scope':'annex_only_four_statements_and_notes_unchanged'}
