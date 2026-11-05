"""Pure complete-original parser; this does not prove HTTP or current ownership."""
from datetime import date
from hashlib import sha256
from urllib.parse import urljoin
import json,re
from bs4 import BeautifulSoup

INDEX='https://www.caa.gov.tw/article.aspx?a=1738&lang=1'
DIRECTORY='https://www.caa.gov.tw/article.aspx?a=277'
TITLE='國籍航空公司全球航線客貨運概況'
TTL=1800
MAX_PERIOD_AGE_DAYS=90

def contract(url):
    if url in(INDEX,DIRECTORY):return 500000,{'text/html','application/xhtml+xml'}
    if re.fullmatch(r'https://www\.caa\.gov\.tw/FileAtt\.ashx\?lang=1&id=[1-9]\d{0,7}',url):
        return 100000,{'application/octet-stream','application/vnd.oasis.opendocument.spreadsheet'}
    raise ValueError('caa_unpublished_or_noncanonical_URL')

def select_dataset(raw, today):
    if type(today)is not date or not isinstance(raw,bytes)or not 100<=len(raw)<=500000:raise ValueError('caa_index_input')
    text=raw.decode('utf-8',errors='strict')
    if len(re.findall(r'<html(?:\s|>)',text,re.I))!=1 or len(re.findall(r'</html\s*>',text,re.I))!=1:raise ValueError('caa_index_root_shape')
    page=BeautifulSoup(text,'html.parser');contents=page.select('div.content#content')
    if len(contents)!=1:raise ValueError('caa_index_business_scope')
    content=contents[0];headings=content.find_all('h2')
    if len(headings)!=1 or headings[0].get_text(strip=True)!=TITLE:raise ValueError('caa_index_title')
    periods=[]
    for row in content.find_all('tr'):
        first=row.find('td',recursive=False)
        if first is None:continue
        years=set(re.findall(r'(?<!\d)(\d{2,3})年(?!第)',first.get_text()))
        if len(years)>1:raise ValueError('caa_index_ambiguous_year')
        if years:periods.append((int(next(iter(years))),row))
    if not 1<=len(periods)<=150:raise ValueError('caa_index_year_scope')
    newest=max(y for y,_ in periods);year=newest+1911
    if not today.year-1<=year<=today.year:raise ValueError('caa_latest_year_stale_or_future')
    latest_rows=[row for y,row in periods if y==newest]
    if len(latest_rows)!=1:raise ValueError('caa_latest_year_duplicate')
    row=latest_rows[0];links=row.select('a.download-filebase[title][href]')
    for link in links:
        if not re.fullmatch(re.escape(str(newest))+r'年\.(ods|xls|xlsx|pdf)',link['title']):raise ValueError('caa_latest_attachment_year_or_format')
    selected=[a for a in links if a['title']==f'{newest}年.ods']
    if len(selected)!=1:raise ValueError('caa_latest_ods_missing_or_ambiguous')
    link=selected[0];url=urljoin(INDEX,link['href']);contract(url)
    published=re.findall(r'最後更新日期[：:]\s*(\d{4}/\d{2}/\d{2})',link.get_text(' ',strip=True))
    if len(published)!=1:raise ValueError('caa_publication_date_missing_or_ambiguous')
    stamp=date.fromisoformat(published[0].replace('/','-'))
    if stamp>today or stamp.year<year:raise ValueError('caa_publication_date_invalid')
    return {'url':url,'year':year,'published_date':stamp.isoformat(),'index_sha256':sha256(raw).hexdigest()}

def parse_dataset(index_raw,ods_raw,directory_raw,master_raw,ticker,today):
    from .caa_operating_identity import bind,PROFILES
    from .caa_operating_ods import replay
    if ticker not in PROFILES or not isinstance(master_raw,bytes)or not 100000<=len(master_raw)<=2500000:raise ValueError('caa_master_or_ticker_input')
    master=json.loads(master_raw)
    if not isinstance(master,list)or len(master)<800:raise ValueError('caa_complete_listed_master_required')
    selected=select_dataset(index_raw,today);identities=bind(directory_raw,master)
    rows=replay(ods_raw,selected['year'],today);identity=identities[ticker]
    target=[r for r in rows if r['source_operator_label']==identity['source_operator_label']]
    latest=max(r['month']for r in target)
    return {'observation_kind':'caa_airline_operating_metrics','ticker':ticker,'issuer':identity,
        'status':'partial','coverage_status':'named_carrier_operating_metrics_only',
        'source_url':INDEX,'attachment_url':selected['url'],'publisher_identity_url':DIRECTORY,
        'published_date':selected['published_date'],'year':selected['year'],'latest_month':latest,
        'monthly_history':[r for r in target if r['frequency']=='monthly'],
        'year_to_date':next(r for r in target if r['frequency']=='year_to_date'and r['month']==latest),
        'original_sha256':{'index':sha256(index_raw).hexdigest(),'ods':sha256(ods_raw).hexdigest(),'directory':sha256(directory_raw).hexdigest(),'master':sha256(master_raw).hexdigest()},
        'coverage_notes':['僅為具名航空公司營運資料，非集團合併資料；未推定職缺、人數、財報或投資結論。',
          '本月與年初累計分開；全球總計含國內、國際及兩岸航線。',
          '貨運噸數含原註解之郵件、貨物及行李，不當成純付費貨物噸數；華航資料不含濕租予華信航空。',
          '原始數字及顯示精度均保留；歷史身分PIT與現行執照生效日未核實。']}
