"""Exact published employer links and portal update dates, never job totals."""
from datetime import datetime
from pathlib import Path
import json

import pytest

D = Path('/Volumes/X10 Pro Mac/stock-agent-archives/continuation-20261104-tigerair-yes123-research')


def synthetic_protocol():
    """Public CI contract fixture; never an actual employer vacancy or HTTP."""
    from data_fetch.market_sources.tigerair_yes123 import PAGE, PROFILE, PID, LEGAL
    title='合成測試工程職務';ident='20261103084009_11555084'
    url='https://www.yes123.com.tw/wk_index/job.asp?p_id='+PID+'&job_id='+ident
    content='這是合成測試的完整職務說明，用於證明文字與結構化內容一致。'
    job={'@context':'http://schema.org','@type':'JobPosting','title':title,'datePosted':'2026-11-3','validThrough':'2027-11-4',
         'description':content,'hiringOrganization':{'@type':'Organization','name':LEGAL,'sameAs':PROFILE}}
    body=('<html><head></head><body><h1>'+title+'</h1><a href="'+PROFILE+'">'+LEGAL+'</a><h2>職缺更新：昨天</h2>'
        '<span class="left_title">工作內容：</span><span class="right_main">'+content+'</span>'
        '<span class="left_title">需求人數：</span><span class="right_main">1人</span>'
        '<a href="/admin/sel_job_to_apply.asp?todo=mail2&amp;fancy=yes&amp;sel_id='+ident+'">我要應徵</a>'
        '<script type="application/ld+json">'+json.dumps(job,ensure_ascii=False)+'</script></body></html>').encode()
    listing=('<html><head></head><body><h1>'+LEGAL+'</h1><a href="https://www.tigerairtw.com">官網</a>'
        '<span>第1/1頁</span><div class="Job_opening"><a class="Job_opening_block" href="'+url+'">'
        '<div class="Job_opening_item_title"><h4>'+title+'</h4></div></a></div></body></html>').encode()
    page=('<html><head><meta name="og:url" content="'+PAGE+'"></head><body></body></html>').encode()
    parent={'data':{'attributes':{'slug':'about-tigerair'}}}
    attrs={'title':'加入台灣虎航','type':'page','slug':'join-us',
           'contents':[{'__typename':'ComponentContentRichtext','richtext':'[yes123]('+PROFILE+')'}],
           'footerNavigatorL2':{'data':{'attributes':{'footerNavigatorL1':parent}}}}
    article=json.dumps({'data':{'articles':{'data':[{'id':'34','attributes':attrs}]}}},ensure_ascii=False).encode()
    return page,article,listing,body,{'url':url,'title':title}


def test_public_synthetic_contract_runs_without_private_native_corpus():
    from data_fetch.market_sources.tigerair_yes123 import parse_mapping,parse_listing,parse_detail
    page,article,listing,body,candidate=synthetic_protocol()
    assert parse_mapping(page,article)['profile_url']
    assert parse_listing(listing)['selected']==[candidate]
    at=datetime.fromisoformat('2026-11-04T23:38:00+08:00').timestamp()
    value=parse_detail(body,candidate,observed_at=at,now=at)
    assert value['declared_demand_text']=='1人'and value['employer_application_deadline']is None


def test_native_weekday_label_requires_exact_json_date_and_recent_observation():
    from data_fetch.market_sources.tigerair_yes123 import parse_detail
    D2=Path('/Volumes/X10 Pro Mac/stock-agent-archives/normal-free-tigerair-yes123-6757-20261105')
    if not(D2/'failure-replay.json').exists():pytest.skip('Private post-midnight source original intentionally not published')
    receipts=json.loads((D2/'failed-native-receipts.json').read_text())
    # Private external snapshots already copied by the audited source replay.
    row={'url':receipts[6]['url'],'title':'聯管中心助理簽派員/簽派員'}
    raw=(D2/'detail-4.body').read_bytes();at=receipts[6]['fetched_at_epoch']
    value=parse_detail(raw,row,observed_at=at,now=at)
    assert value['last_updated_date']=='2026-11-03' and value['first_publication_date']is None
    assert value['employer_application_deadline']is None


@pytest.mark.parametrize('damage',['different_weekday','older_week','today','yesterday','future'])
def test_weekday_label_cannot_select_another_week_or_override_json_date(damage):
    from data_fetch.market_sources.tigerair_yes123 import parse_detail
    _,_,_,raw,row=synthetic_protocol()
    raw=raw.replace('職缺更新：昨天'.encode(),'職缺更新：星期二'.encode())
    at=datetime.fromisoformat('2026-11-05T01:10:00+08:00').timestamp()
    if damage=='different_weekday':raw=raw.replace('星期二'.encode(),'星期三'.encode())
    elif damage=='older_week':raw=raw.replace(b'2026-11-3',b'2026-10-27')
    elif damage=='today':raw=raw.replace(b'2026-11-3',b'2026-11-5')
    elif damage=='yesterday':raw=raw.replace(b'2026-11-3',b'2026-11-4')
    else:raw=raw.replace(b'2026-11-3',b'2026-11-10')
    with pytest.raises(ValueError):parse_detail(raw,row,observed_at=at,now=at)


def test_public_weekday_protocol_and_midnight_replay():
    from data_fetch.market_sources.tigerair_yes123 import parse_detail
    _,_,_,raw,row=synthetic_protocol()
    raw=raw.replace('職缺更新：昨天'.encode(),'職缺更新：星期二'.encode())
    at=datetime.fromisoformat('2026-11-05T01:10:00+08:00').timestamp()
    value=parse_detail(raw,row,observed_at=at,now=at+5)
    assert value['last_updated_date']=='2026-11-03'and value['date_basis']=='portal_update_not_original_first_publication'


@pytest.mark.parametrize('damage',['wrong_employer','wrong_title','body_mismatch','relative_date','expiry','foreign_action','wrong_profile','truncated','duplicate_json'])
def test_public_synthetic_rejections_do_not_depend_on_private_files(damage):
    from data_fetch.market_sources.tigerair_yes123 import parse_detail,LEGAL
    _,_,_,body,candidate=synthetic_protocol()
    if damage=='wrong_employer':body=body.replace(LEGAL.encode(),'其他航空股份有限公司'.encode())
    elif damage=='wrong_title':candidate['title']='不相符職務'
    elif damage=='body_mismatch':body=body.replace('這是合成測試的完整職務說明'.encode(),'未經結構化內容核對的不同職務'.encode(),1)
    elif damage=='relative_date':body=body.replace('職缺更新：昨天'.encode(),'職缺更新：今天'.encode())
    elif damage=='expiry':body=body.replace(b'2027-11-4',b'2026-11-2')
    elif damage=='foreign_action':body=body.replace(b'/admin/sel_job_to_apply.asp',b'https://foreign.example/apply')
    elif damage=='wrong_profile':body=body.replace(b'20140325092151_Y201403028',b'20140325092151_Y201403029')
    elif damage=='truncated':body=body.replace(b'</html>',b'')
    else:body=body.replace(b'"datePosted":',b'"datePosted":"2026-11-3","datePosted":')
    at=datetime.fromisoformat('2026-11-04T23:38:00+08:00').timestamp()
    with pytest.raises(ValueError):parse_detail(body,candidate,observed_at=at,now=at)


def originals():
    if not (D / 'five-detail-selection.json').exists():
        pytest.skip('Private native originals intentionally not published')
    selection = json.loads((D / 'five-detail-selection.json').read_text())['selected_first_five']
    bodies = {}
    for i, row in enumerate(selection):
        name = 'published-job' if i == 3 else 'selected-detail-' + str(i + 1)
        bodies[row['url']] = (D / (name + '.body')).read_bytes()
    return selection, bodies


def test_complete_native_official_mapping_and_five_portal_postings():
    from data_fetch.market_sources.tigerair_yes123 import parse_mapping, parse_listing, parse_detail
    selected, bodies = originals()
    assert parse_mapping((D / 'official-page.body').read_bytes(), (D / 'official-article.body').read_bytes())
    listing = parse_listing((D / 'published-company.body').read_bytes())
    assert listing['selected'] == [{'url': r['url'], 'title': r['title'].split(' 月薪')[0].split(' 薪資面議')[0]} for r in selected]
    assert listing['page_count'] == 2 and listing['all_company_job_count'] is None
    for row in listing['selected']:
        observed = datetime.fromisoformat('2026-11-04T23:38:00+08:00').timestamp()
        job = parse_detail(bodies[row['url']], row, observed_at=observed, now=observed)
        assert job['company_name'] == '台灣虎航股份有限公司'
        assert job['first_publication_date'] is None and job['employer_application_deadline'] is None
        assert job['date_basis'] == 'portal_update_not_original_first_publication'
        assert job['portal_valid_through'] == '2027-11-04'


@pytest.mark.parametrize('damage', ['employer', 'profile', 'title', 'posted_future', 'expiry_past', 'duplicate_json', 'no_apply', 'truncated', 'content', 'relative_mismatch'])
def test_wrong_identity_dates_or_missing_body_cannot_become_a_posting(damage):
    from data_fetch.market_sources.tigerair_yes123 import parse_detail
    selected, bodies = originals(); row = {'url': selected[3]['url'], 'title': '聯管中心助理簽派員/簽派員'}
    raw = bodies[row['url']]
    if damage == 'employer': raw = raw.replace('台灣虎航股份有限公司'.encode(), '其他航空股份有限公司'.encode())
    elif damage == 'profile': raw = raw.replace(b'20140325092151_Y201403028', b'20140325092151_Y201403029')
    elif damage == 'title': row['title'] = '其他職缺'
    elif damage == 'posted_future': raw = raw.replace(b'2026-11-3', b'2026-11-5')
    elif damage == 'expiry_past': raw = raw.replace(b'2027-11-4', b'2026-11-2')
    elif damage == 'duplicate_json': raw = raw.replace(b'"datePosted":', b'"datePosted":"2026-11-3","datePosted":')
    elif damage == 'no_apply': raw = raw.replace(b'sel_job_to_apply.asp', b'closed.asp')
    elif damage == 'truncated': raw = raw.replace(b'</html>', b'')
    elif damage == 'content':
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(raw.decode(), 'html.parser')
        node=next(v for v in soup.select('.left_title') if v.get_text(strip=True)=='工作內容：').find_next_sibling()
        node.clear();node.append('這是未出現在原結構化內容中的不同職務說明，必須拒收。')
        raw=str(soup).encode()
    else: raw = raw.replace('職缺更新：昨天'.encode(), '職缺更新：今天'.encode())
    at = datetime.fromisoformat('2026-11-04T23:38:00+08:00').timestamp()
    with pytest.raises(ValueError): parse_detail(raw, row, observed_at=at, now=at)


def test_relative_date_is_anchored_to_original_retrieval_across_midnight():
    from data_fetch.market_sources.tigerair_yes123 import parse_detail
    selected, bodies = originals(); row = {'url': selected[3]['url'], 'title': '聯管中心助理簽派員/簽派員'}
    observed = datetime.fromisoformat('2026-11-04T23:59:00+08:00').timestamp()
    later = datetime.fromisoformat('2026-11-05T00:01:00+08:00').timestamp()
    assert parse_detail(bodies[row['url']], row, observed_at=observed, now=later)['last_updated_date'] == '2026-11-03'


@pytest.mark.parametrize('damage', ['foreign_mapping', 'wrong_slug', 'wrong_article', 'duplicate_profile', 'wrong_profile_name', 'wrong_stock_link'])
def test_mapping_or_listing_identity_substitution_is_rejected(damage):
    from data_fetch.market_sources.tigerair_yes123 import parse_mapping, parse_listing
    originals(); page=(D/'official-page.body').read_bytes(); article=(D/'official-article.body').read_bytes(); listing=(D/'published-company.body').read_bytes()
    if damage == 'foreign_mapping': article=article.replace(b'20140325092151_Y201403028', b'20140325092151_Y201403029')
    elif damage == 'wrong_slug': article=article.replace(b'"slug":"join-us"', b'"slug":"other"')
    elif damage == 'wrong_article': article=article.replace(b'"id":"34"', b'"id":"35"', 1)
    elif damage == 'duplicate_profile': listing=listing.replace(b'job_id=20261002152036_54316196', b'job_id=20261008102137_69248567')
    elif damage == 'wrong_profile_name': listing=listing.replace('台灣虎航股份有限公司'.encode(), '其他航空股份有限公司'.encode())
    else: listing=listing.replace(b'job.asp?p_id=20140325092151_Y201403028', b'job.asp?p_id=20140325092151_Y201403029', 1)
    with pytest.raises(ValueError):
        if damage in {'foreign_mapping', 'wrong_slug', 'wrong_article'}: parse_mapping(page, article)
        else: parse_listing(listing)
