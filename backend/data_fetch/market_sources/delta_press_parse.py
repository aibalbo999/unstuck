"""Pure replay of one full Delta streamed page and its full inline document.

This parser never evaluates JavaScript, fetches assets, or declares a live
acquisition/cache owner. The exact published React mounting protocol is pinned.
"""
from datetime import date,timedelta
from hashlib import sha256
from urllib.parse import urljoin
import re
from bs4 import BeautifulSoup

INDEX='https://www.deltaww.com/en-US/press'
STREAM_PREFIX_SHA='7a3c441a297b4368e7168f53d44323873b11a160d3567f2d4695187785c22646'
MOUNT='$RC("B:0","S:0")'


def _one(values,reason):
    if len(values)!=1:raise ValueError(reason)
    return values[0]


def _full(raw,limit=1000000):
    if not isinstance(raw,bytes)or not 100<=len(raw)<=limit:raise ValueError('delta_complete_document_size')
    text=raw.decode('utf-8','strict')
    if (len(re.findall(r'<html(?:\s|>)',text,re.I))!=1
            or len(re.findall(r'</html\s*>',text,re.I))!=1
            or not re.search(r'</html>\s*$',text,re.I)):
        raise ValueError('delta_complete_document_root')
    page=BeautifulSoup(text,'html.parser')
    if len(page.find_all('html'))!=1 or len(page.find_all('head'))!=1 or len(page.find_all('body'))!=1:
        raise ValueError('delta_complete_document_structure')
    return page


def _mounted(page,url):
    if page.html.get('lang')!='en-US':raise ValueError('delta_document_language')
    canonical=_one(page.select('link[rel="canonical"]'),'delta_canonical_count')
    ogurl=_one(page.select('meta[property="og:url"]'),'delta_og_url_count')
    if canonical.get('href')!=url or ogurl.get('content')!=url:raise ValueError('delta_canonical_identity')
    _one(page.find_all('main'),'delta_main_count')
    template=_one(page.find_all('template',id='B:0'),'delta_main_template_count')
    if template.find_parent('main')is None:raise ValueError('delta_unbound_main_template')
    slot=_one(page.find_all(id='S:0'),'delta_slot_count')
    if slot.name!='div'or not slot.has_attr('hidden')or slot.parent!=page.body:
        raise ValueError('delta_unverified_stream_slot')
    calls=[x.get_text()for x in page.find_all('script')if MOUNT in x.get_text()]
    script=_one(calls,'delta_mount_count')
    if (not script.endswith(MOUNT)or script.count(MOUNT)!=1
            or sha256(script[:-len(MOUNT)].encode()).hexdigest()!=STREAM_PREFIX_SHA):
        raise ValueError('delta_stream_mount_protocol_changed')
    if template.find_all()or len(page.find_all(id='B:0'))!=1:raise ValueError('delta_template_identity')
    return slot


def index_cards(raw):
    page=_full(raw);slot=_mounted(page,INDEX);records={}
    if _one(page.find_all('h1'),'delta_index_h1_count').get_text(' ',strip=True)!='Press':
        raise ValueError('delta_index_title')
    for link in slot.find_all('a',href=True):
        url=urljoin(INDEX,link['href'])
        if not re.fullmatch(r'https://www\.deltaww\.com/en-US/press/[1-9]\d{0,7}',url):continue
        spans=link.select('span.whitespace-pre-line')
        title=_one(spans,'delta_index_card_title').get_text(' ',strip=True)
        dates=[s.get_text(strip=True)for s in link.find_all('span')if re.fullmatch(r'\d{2}/\d{2}/\d{4}',s.get_text(strip=True))]
        stamp=_one(dates,'delta_index_card_date');month,day,year=map(int,stamp.split('/'));published=date(year,month,day)
        category=[s.get_text(' ',strip=True).replace('|','').strip()for s in link.select('div.text-tag > span')]
        if not category or category[-1]!=stamp or not title or len(title)>300 or url in records:
            raise ValueError('delta_index_card_ambiguous')
        records[url]={'title':title,'published_on':published.isoformat(),'categories':category[:-1]}
    if not 1<=len(records)<=16:raise ValueError('delta_index_card_scope')
    return records


def parse_article(index_raw,article_raw,url,*,today):
    if type(today)is not date:raise ValueError('delta_asof_day')
    cards=index_cards(index_raw)
    if url not in cards:raise ValueError('delta_action_not_published')
    card=cards[url]
    # No timezone or clock is invented. Stay at least two days from either
    # boundary so a date-only source cannot silently cross a 30-day cutoff.
    age=(today-date.fromisoformat(card['published_on'])).days
    if not 2<=age<=28:raise ValueError('delta_date_only_window_ambiguous_or_stale')
    if card['categories']!=['Corporate']:raise ValueError('delta_unsupported_publisher_role')
    page=_full(article_raw);slot=_mounted(page,url)
    container=_one(slot.find_all(recursive=False),'delta_article_container')
    if container.name!='div'or container.get('style')!='max-width:800px':raise ValueError('delta_article_layout')
    h1=_one(page.find_all('h1'),'delta_article_h1_count')
    title=h1.get_text(' ',strip=True)
    if h1 not in container.descendants or title!=card['title']:
        raise ValueError('delta_article_title_mismatch')
    og=_one(page.select('meta[property="og:title"]'),'delta_og_title_count')
    if og.get('content')!='Press Center - '+title+' - Delta':raise ValueError('delta_og_title_mismatch')
    sources=[x for x in container.find_all('span')if x.get_text(' ',strip=True).startswith('News Source:')]
    source=_one(sources,'delta_publisher_source_count')
    if source.get_text(' ',strip=True)!='News Source: Brand and Communications':
        raise ValueError('delta_publisher_department_unverified')
    date_spans=[s.get_text(strip=True)for s in source.parent.find_all('span')if re.fullmatch(r'\d{2}/\d{2}/\d{4}',s.get_text(strip=True))]
    stamp=_one(date_spans,'delta_primary_date_count');month,day,year=map(int,stamp.split('/'))
    if date(year,month,day).isoformat()!=card['published_on']:raise ValueError('delta_publication_date_conflict')
    frame=_one(container.find_all('iframe'),'delta_inline_body_count')
    if frame.get('src')or not isinstance(frame.get('srcdoc'),str)or frame.get('scrolling')!='no':
        raise ValueError('delta_non_inline_body')
    raw=frame['srcdoc'].encode('utf-8');inner=_full(raw,100000)
    if inner.find_all(['iframe','object','embed']):raise ValueError('delta_nested_body_document_unverified')
    paragraphs=inner.body.find_all('p',recursive=False)
    if len(paragraphs)!=1 or any(x.get_text(' ',strip=True)for x in inner.body.find_all(recursive=False)if x.name not in('p','script')):
        raise ValueError('delta_body_text_layout_changed')
    text=paragraphs[0].get_text(' ',strip=True)
    if not 1000<=len(text)<=12000 or not text.startswith('Delta, a global leader in power management and smart green solutions,'):
        raise ValueError('delta_inline_article_text_unverified')
    return {'ticker':'2308.TW','title':title,'source_url':url,'published_on':card['published_on'],
        'publication_precision':'day','publication_clock_and_timezone':None,'publisher':'Delta official Brand and Communications',
        'source_role':'issuer_statement','independent_editorial_verified':False,'catalyst_assessment':'not_assessed',
        'text':text,'text_truncated':False,'body_source':'complete_inline_srcdoc_bound_to_main_stream_slot',
        'content_coverage':'inline_article_text_only','rendered_visibility_independently_verified':False,
        'gallery_images_verified':False,'full30day_history_verified':False,
        'original_sha256':{'index':sha256(index_raw).hexdigest(),'article':sha256(article_raw).hexdigest(),'embedded_srcdoc':sha256(raw).hexdigest()},
        'new_source_acquisition':False,'native_owner_and_production_admission':'not established by this pure parser'}

TTL=1800

def contract(url):
    if url!=INDEX and (not isinstance(url,str)or not re.fullmatch(r'https://www\.deltaww\.com/en-US/press/[1-9]\d{0,7}',url)):
        raise ValueError('delta_url_not_qualified')
    return 1000000,{'text/html'}

def select_article(raw,today):
    cards=index_cards(raw)
    eligible=[(url,c)for url,c in cards.items()if c['categories']==['Corporate']and 2<=(today-date.fromisoformat(c['published_on'])).days<=28]
    if not eligible:raise ValueError('delta_no_qualified_recent_statement')
    eligible.sort(key=lambda x:(x[1]['published_on'],x[0]),reverse=True)
    if sum(c['published_on']==eligible[0][1]['published_on']for _,c in eligible)>1:
        raise ValueError('delta_newest_statement_ambiguous')
    return eligible[0][0]
