"""Exact qualified Getac original, independently published through MOPS.

No issuer-host bridge is inferred. Changed documents require new qualification;
all original pages remain, but only the original four whole pages enter roles.
"""
from hashlib import sha256
from .getac_conference import KNOWN_SHA,PAGE_TEXT_SHA256,ROLE_PAGES


def _pages(pages):
    if (not isinstance(pages,list) or len(pages)!=21
            or any(not isinstance(p,dict) or type(p.get('page_number')) is not int
                   or p['page_number']!=n or not isinstance(p.get('text'),str)
                   or sha256(p['text'].encode()).hexdigest()!=PAGE_TEXT_SHA256[n-1]
                   for n,p in enumerate(pages,1))):
        raise ValueError('Getac original whole-page qualification changed')


def qualify_native(raw,native,selected):
    expected={'ticker':'3005.TW','symbol':'3005','company_name':'神基',
              'event_date':'2026-08-14','event_end_date':'2026-08-14',
              'material_file_date':'2026-08-13','filename':'300520260813E001.pdf',
              'format':'pdf','language':'en'}
    if (any(selected.get(k)!=v for k,v in expected.items())
            or not isinstance(raw,bytes) or sha256(raw).hexdigest()!=KNOWN_SHA
            or native.get('content_sha256')!=KNOWN_SHA
            or native.get('coverage_status')!='complete'
            or type(native.get('page_count')) is not int or native['page_count']!=21
            or native.get('empty_pages')!=[] or native.get('garbled_pages')!=[]):
        raise ValueError('Getac MOPS original identity/period/coverage unqualified')
    _pages(native.get('pages'))
    return '2026H1'


def qualified_projection(pages):
    _pages(pages)
    return {'role_projection_policy':'mops-qualified-whole-pages-v1',
            'role_page_allowlist':{str(role):list(ROLE_PAGES) for role in (3,5,12)},
            'projection_excluded_pages':[n for n in range(1,22) if n not in ROLE_PAGES]}
