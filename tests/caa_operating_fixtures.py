"""Small synthetic public-format documents; never production HTTP receipts."""
import io,json,zipfile,xml.etree.ElementTree as E
from data_fetch.market_sources.caa_operating_ods import T,O,LABELS
from data_fetch.market_sources.caa_operating_identity import PROFILES,NATIONAL

def ods(months=9,year=2026,mutate=None):
    root=E.Element(O+'document-content');body=E.SubElement(root,O+'body');sheet=E.SubElement(body,O+'spreadsheet')
    for month in range(months,0,-1):
        table=E.SubElement(sheet,T+'table',{T+'name':f'{year-1911}{month:02d}'})
        values={}
        for offset,heading,title in((0,'總計','表18國籍航空公司全球航線客貨運概況'),(11,'國內航線','表18國籍航空公司全球航線客貨運概況(續1)'),(22,'國際及兩岸航線','表18國籍航空公司全球航線客貨運概況(續完)')):
            values[4,offset]=title;values[5,offset]='中華民國八十五年三月';values[6,offset]=f'中華民國{year-1911}年{month}月份';values[7,offset+1]=heading
            values[10,offset]='本月';values[22,offset]=f'1-{month}月'
            for col,text in((3,'載客人數(人)'),(6,'載客率(%)'),(7,'貨運噸數(公噸)'),(10,'載貨率(%)')):values[9,col+offset]=text
            for base,frequency in((11,1),(23,month)):
                for n,label in enumerate(LABELS):
                    values[base+n,offset]='累計'if base==23 and n==0 else label
                    for col in(3,6,7,10):values[base+n,col+offset]=str((28 if n==0 else n)*frequency)if col==3 else '50.00'if col in(6,10)else'100'
        values[32,0]='資料來源：各國籍航空公司。中華航空自100年5月份起不含濕租予華信航空。貨運噸數包含郵件、貨物及行李。'
        for ri in range(36):
            row=E.SubElement(table,T+'table-row')
            for ci in range(33):
                text=values.get((ri,ci),'');cell=E.SubElement(row,T+'table-cell')
                if text:
                    numeric=(ri in range(11,19)or ri in range(23,31))and ci%11 in(3,6,7,10)
                    if numeric:cell.set(O+'value-type','float');cell.set(O+'value',text)
                    else:cell.set(O+'value-type','string')
                    E.SubElement(cell,'p').text=text
        if mutate:mutate(table,month)
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED)as book:
        book.writestr('mimetype',b'application/vnd.oasis.opendocument.spreadsheet');book.writestr('content.xml',E.tostring(root))
    return output.getvalue()

def directory():
    rows=''.join(f'<tr><td>{name}</td><td>國籍</td><td>not used</td></tr>'for name in sorted(NATIONAL))
    rows+=''.join(f'<tr><td>foreign{i}</td><td>其他</td><td>not used</td></tr>'for i in range(60))
    return ('<html><body><div class="content" id="content"><h2>本局及航空公司旅客諮詢服務電話</h2><table><tr><th>航空公司</th><th>區域別</th><th>服務電話</th></tr>'+rows+'</table><table></table></div></body></html>').encode()

def master():
    rows=[{'公司代號':str(8000+i),'公司名稱':f'合成樣本{i}股份有限公司','填補欄位':'x'*120}for i in range(800)]
    for ticker,(label,full,code,legal,ubn,short)in PROFILES.items():rows.append({'公司代號':ticker.split('.')[0],'公司名稱':legal,'營利事業統一編號':ubn,'公司簡稱':short,'產業別':'15'})
    return json.dumps(rows,ensure_ascii=False).encode()
