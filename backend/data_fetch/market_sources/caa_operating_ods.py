"""Offline qualification; source operator labels are deliberately not tickers."""
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from datetime import date
import calendar
import io,re,zipfile,xml.etree.ElementTree as ET
T='{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
O='{urn:oasis:names:tc:opendocument:xmlns:office:1.0}'
LABELS=('總計','中華','華信','長榮','立榮','台灣虎航','星宇','德安')

def compact(s):return re.sub(r'\s+','',s)

def grid(table):
    result=[]
    for row in table.findall(T+'table-row'):
        cells={};pos=0;nonempty=False
        for cell in row:
            if cell.tag not in(T+'table-cell',T+'covered-table-cell'):raise ValueError('unexpected_cell')
            text=compact(''.join(cell.itertext()));repeat=int(cell.get(T+'number-columns-repeated','1'))
            if repeat<1:raise ValueError('bad_repeat')
            if text:
                nonempty=True
                if repeat!=1 or pos>=33:raise ValueError('nonempty_repeat_or_outside_table')
                cells[pos]={'text':text,'value':cell.get(O+'value'),'type':cell.get(O+'value-type'),'formula':cell.get(T+'formula')}
            pos+=repeat
        if nonempty and row.get(T+'number-rows-repeated','1')!='1':raise ValueError('repeated_nonempty_row')
        result.append(cells)
    if len(result)!=36:raise ValueError('row_shape_changed')
    return result

def number(cell,kind):
    text=cell['text'];raw=cell['value']
    if text in('-','--','N/A','')or cell['type']!='float':raise ValueError('unknown_not_zero')
    if not re.fullmatch(r'\d+(?:\.\d+)?',raw or''):raise ValueError('bad_numeric')
    try:value=Decimal(raw);shown=Decimal(text.replace(',',''))
    except InvalidOperation:raise ValueError('bad_display')from None
    if not value.is_finite()or not shown.is_finite()or not 0<=value<=10**12:raise ValueError('numeric_range')
    places=2 if kind=='percent'else 0
    if kind=='percent'and not 0<=value<=100:raise ValueError('percentage_range')
    if kind=='persons'and value!=value.to_integral_value():raise ValueError('person_not_integer')
    if value.quantize(Decimal(10)**-places,rounding=ROUND_HALF_UP)!=shown:raise ValueError('display_value_disagreement')
    return {'native_numeric_string':raw,'native_display':text,'unit':{'percent':'%','persons':'人','tonnes':'公噸'}[kind],'no_binary_float_or_calculation_substitution':True}

def parse_table(table,year):
    roc=year-1911
    name=table.get(T+'name','');match=re.fullmatch(re.escape(str(roc))+r'(0[1-9]|1[0-2])',name)
    if not match:raise ValueError('unsupported_sheet')
    month=int(match[1]);rows=grid(table)
    for offset,heading,title in((0,'總計','表18國籍航空公司全球航線客貨運概況'),(11,'國內航線','表18國籍航空公司全球航線客貨運概況(續1)'),(22,'國際及兩岸航線','表18國籍航空公司全球航線客貨運概況(續完)')):
        if rows[4].get(offset,{}).get('text')!=title or rows[6].get(offset,{}).get('text')!=f'中華民國{roc}年{month}月份':raise ValueError('actual_period_or_title_mismatch')
        if rows[7].get(offset+1,{}).get('text')!=heading:raise ValueError('route_scope_mismatch')
        if rows[10].get(offset,{}).get('text')!='本月'or rows[22].get(offset,{}).get('text')!=f'1-{month}月':raise ValueError('monthly_YTD_mismatch')
    expected={3:'載客人數(人)',6:'載客率(%)',7:'貨運噸數(公噸)',10:'載貨率(%)'}
    if any(rows[9].get(col+offset,{}).get('text')!=label for offset in(0,11,22)for col,label in expected.items()):raise ValueError('unit_or_metric_header_mismatch')
    result=[]
    for frequency,base in(('monthly',11),('year_to_date',23)):
        for index,label in enumerate(LABELS):
            row=rows[base+index]
            if any(row.get(offset,{}).get('text')!=('累計'if frequency=='year_to_date'and label=='總計'else label)for offset in(0,11,22)):raise ValueError('operator_panels_mismatch')
            values={key:number(row[col],kind)for key,col,kind in(('passengers',3,'persons'),('passenger_load_factor',6,'percent'),('cargo_tonnes',7,'tonnes'),('cargo_load_factor',10,'percent'))}
            result.append({'source_operator_label':label,'year':year,'month':month,'frequency':frequency,'route_scope':'global_total_including_domestic_international_cross_strait','values':values,'original_sheet':name,'original_row_zero_based':base+index,'original_columns_zero_based':[3,6,7,10]})
        group=result[-8:]
        if sum(Decimal(r['values']['passengers']['native_numeric_string'])for r in group[1:])!=Decimal(group[0]['values']['passengers']['native_numeric_string']):raise ValueError('passenger_total_reconciliation')
    footer=rows[32].get(0,{}).get('text','')
    if not all(x in footer for x in('資料來源：各國籍航空公司','中華航空自100年5月份起','不含濕租予華信航空','郵件、貨物及行李')):raise ValueError('coverage_notes_missing')
    return result

def replay(raw,year,today):
    if type(year)is not int or type(today)is not date or not today.year-1<=year<=today.year:raise ValueError('ods_year_input')
    if not isinstance(raw,bytes)or not 100<=len(raw)<=100000:raise ValueError('ods_size')
    with zipfile.ZipFile(io.BytesIO(raw))as book:
        infos=book.infolist();names=[x.filename for x in infos]
        if len(infos)>40 or len(names)!=len(set(names))or sum(x.file_size for x in infos)>8000000 or any(x.flag_bits&1 for x in infos)or names.count('content.xml')!=1 or names.count('mimetype')!=1 or any(n.startswith(('/','\\'))or'..'in n.split('/')for n in names):raise ValueError('container')
        if book.read('mimetype')!=b'application/vnd.oasis.opendocument.spreadsheet'or book.testzip()is not None:raise ValueError('mimetype_or_CRC')
        content=book.read('content.xml')
    if b'<!DOCTYPE'in content.upper()or b'<!ENTITY'in content.upper():raise ValueError('DTD_entity')
    root=ET.fromstring(content);tables=root.findall('.//'+T+'table')
    names=[x.get(T+'name')for x in tables]
    if not 1<=len(tables)<=12:raise ValueError('monthly_sheet_count')
    latest=len(tables);roc=year-1911
    if names!=[f'{roc}{m:02d}'for m in range(latest,0,-1)]:raise ValueError('monthly_sheet_coverage_changed')
    period_end=date(year,latest,calendar.monthrange(year,latest)[1])
    if not 0<=(today-period_end).days<=90:raise ValueError('latest_period_stale_or_future')
    result=[r for table in tables for r in parse_table(table,year)]
    if any('ticker'in r for r in result):raise ValueError('unproved_ticker_binding')
    return result
