"""One exact employer's numeric zero on PhilJobNet, never a global hiring count."""
from datetime import datetime
import math
import re
import time
import unicodedata

from bs4 import BeautifulSoup
from news_record_utils import clean_text
from .philjobnet_medtecs_transport import CONTACT, PROFILE, PROVIDER, PhilJobNetHttp
from .tdr_mops_history import (TICKER, SHORT, LEGAL, TAIPEI, _master, _master_anchor,
                               _original, _archived_original, _check_deadline)

POLICY = 'medtecs-philjobnet-portal-count-v1'
ENGLISH = 'Medtecs International Corporation Limited'
NOTE = '取得當時該菲律賓政府入口的雇主清單明示未列職缺；只代表此入口，全球職缺數未知，不能推定招募縮減。'


def _soup(raw):
    text = raw.decode('utf-8-sig')
    if not re.search(r'</html>\s*$',text,re.I):
        raise ValueError('incomplete_html_original')
    return BeautifulSoup(text,'html.parser')


def _one(root, selector):
    elements = root.select(selector)
    if len(elements) != 1:
        raise ValueError('employer_structure_unverified')
    return elements[0]


def _contact(raw):
    soup = _soup(raw)
    for suffix, country, tab in [('1313','Philippines','3'),('1316','Bermuda','6')]:
        title_id, panel_id = 'elementor-tab-title-'+suffix, 'elementor-tab-content-'+suffix
        title, panel = _one(soup,'#'+title_id), _one(soup,'#'+panel_id)
        paragraphs = panel.find_all('p',recursive=False)
        if (title.get_text(' ',strip=True) != country or title.get('role') != 'tab'
                or title.get('aria-controls') != panel_id or title.get('data-tab') != tab
                or panel.get('role') != 'tabpanel' or panel.get('aria-labelledby') != title_id
                or panel.get('data-tab') != tab or not paragraphs
                or paragraphs[0].get_text(' ',strip=True) != ENGLISH):
            raise ValueError('official_country_legal_name_unverified')


def _profile(raw):
    soup = _soup(raw)
    main = _one(soup,'main#main section#portfolio-details')
    title, description = _one(main,'.companydetails-title'), _one(main,'#description')
    jobs, employer, table = (_one(soup,'#jobs'),_one(soup,'#ctl00_BodyContentPlaceHolder_empid'),
                             _one(soup,'#ctl00_BodyContentPlaceHolder_GridView1'))
    if (title.get_text(' ',strip=True) != "MEDTECS INT'L CORP. LTD"
            or not description.get_text(' ',strip=True).startswith(ENGLISH+' is ')
            or jobs not in main.descendants or jobs.get('role') != 'tabpanel'
            or jobs.get('aria-labelledby') != 'jobs-tab' or employer not in jobs.descendants
            or employer.get('type') != 'hidden' or employer.get('value') != '2912'
            or table not in jobs.descendants or len(table.find_all('tr')) != 1
            or len(table.find_all('td')) != 1 or table.find('th') is not None
            or table.get_text(' ',strip=True) != 'No job vacancies'
            or jobs.get_text(' ',strip=True) != 'No job vacancies'
            or jobs.find('a') is not None or jobs.find('script') is not None):
        raise ValueError('portal_numeric_zero_unverified')
    # The separate review tab's "Coming soon" is not the job listing.
    if re.search(r'coming soon|loading|error|unavailable|next|previous',jobs.get_text(' ',strip=True),re.I):
        raise ValueError('portal_listing_incomplete')


def _build(anchor, contact_sha, contact_stamp, profile_sha, profile_stamp):
    return {'status':'success','ticker':TICKER,'source':PROVIDER,'source_url':PROFILE,
            'employer_id':'2912','employer_legal_name':ENGLISH,
            'query_scope':'single_philjobnet_employer_listing','portal_job_count':0,
            'global_job_count':None,'job_postings':[],
            'coverage_status':'single_portal_numeric_observation','coverage_note':NOTE,
            'fetched_at_epoch':profile_stamp,'philjobnet_employer_receipt':{
                'policy':POLICY,'issuer_master':anchor,'contact_response_sha256':contact_sha,
                'contact_fetched_at_epoch':contact_stamp,'profile_response_sha256':profile_sha,
                'profile_fetched_at_epoch':profile_stamp}}


def verified_philjobnet_observation(value, data, *, require_fresh=False):
    """Rebuild from three archived originals; false/unknown/changed schemas fail closed."""
    try:
        identity = data.get('company_identity')
        if identity is None:
            identity = {}
        if (data.get('ticker') != TICKER or not isinstance(identity,dict)
                or identity.get('ticker') not in (None,'',TICKER)
                or identity.get('official_name') not in (None,'',SHORT)
                or identity.get('legal_name') not in (None,'',LEGAL)):
            return False
        forbidden = identity.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple)) or any(
                unicodedata.normalize('NFKC',clean_text(x)).strip().strip('*').strip().casefold()
                in {SHORT.casefold(),LEGAL.casefold()} for x in forbidden):
            return False
        receipt = value['philjobnet_employer_receipt']
        if receipt['policy'] != POLICY:
            return False
        for key in ('contact_fetched_at_epoch','profile_fetched_at_epoch'):
            stamp = receipt[key]
            if (type(stamp) not in (int,float) or not math.isfinite(stamp)
                    or not 0 < stamp <= time.time()+300
                    or require_fresh and time.time()-stamp > 86400):
                return False
        anchor = receipt['issuer_master']
        rebuilt_anchor = _master_anchor(_archived_original(anchor['master_response_sha256'],2500000),
            anchor['master_fetched_at_epoch'],datetime.now(TAIPEI),require_fresh=require_fresh)
        if anchor != rebuilt_anchor:
            return False
        _contact(_archived_original(receipt['contact_response_sha256'],600000))
        _profile(_archived_original(receipt['profile_response_sha256'],600000))
        rebuilt = _build(anchor,receipt['contact_response_sha256'],receipt['contact_fetched_at_epoch'],
                         receipt['profile_response_sha256'],receipt['profile_fetched_at_epoch'])
        return type(value.get('portal_job_count')) is int and all(value.get(k)==v for k,v in rebuilt.items())
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,OSError,EOFError):
        return False


def fetch_philjobnet_observation(ticker, *, get=None):
    audit = {'source':'alternative_data','provider':PROVIDER,'status':'unavailable',
             'record_count':0,'cache_hit':False,'stale':False,'http_request_count':0}
    if ticker != TICKER:
        return None,{**audit,'reason_code':'issuer_unverified','http_request_sent':False}
    deadline = time.monotonic()+20.
    transport = PhilJobNetHttp(deadline) if get is None else None
    get = get or transport.get
    value = None
    try:
        anchor = _master(datetime.now(TAIPEI),get,deadline)
        raw_contact, contact = _original(get(CONTACT),CONTACT,600000,deadline); _contact(raw_contact)
        raw_profile, profile = _original(get(PROFILE),PROFILE,600000,deadline); _profile(raw_profile)
        value = _build(anchor,contact['raw_response_sha256'],contact['retrieved_at'],
                       profile['raw_response_sha256'],profile['retrieved_at'])
        if not verified_philjobnet_observation(value,{'ticker':ticker},require_fresh=True):
            raise ValueError('saved_original_verification_failed')
        _check_deadline(deadline)
        audit.update(status='success',record_count=1,fetched_at_epoch=value['fetched_at_epoch'],
                     coverage_status=value['coverage_status'],message=NOTE)
    except Exception as exc:
        value = None
        audit.update(status='error',error_kind=getattr(exc,'error_kind',type(exc).__name__),
                     http_status=getattr(getattr(exc,'response',None),'status_code',getattr(exc,'status_code',None)),
                     message='尚未取得可驗證的單一雇主入口數值；全球職缺數未知。')
    if transport:
        audit.update(http_request_count=transport.http_request_count,
                     http_request_sent=bool(transport.http_request_count),components=transport.components)
    return value,audit
