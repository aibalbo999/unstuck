"""Verified, whole-page views for staged issuer presentation layouts."""
import re

POLICY = 'mops-qualified-whole-pages-v1'
QUALIFIED = {'5314.TWO', '3653.TW', '3005.TW', '6282.TW', '9945.TW', '2441.TW', '6669.TW', '2606.TW'}


def _qualified(value):
    return isinstance(value,str) and value in QUALIFIED


def projection(ticker, pages):
    if not _qualified(ticker):
        return {}
    if ticker == '5314.TWO':
        from data_fetch.market_sources.myson_mops_qualification import qualified_projection
        return qualified_projection(pages)
    if ticker == '3653.TW':
        from data_fetch.market_sources.jentech_mops_qualification import qualified_projection
        return qualified_projection(pages)
    if ticker == '3005.TW':
        from data_fetch.market_sources.getac_mops_qualification import qualified_projection
        return qualified_projection(pages)
    normalized={p['page_number']:re.sub(r'\s+',' ',p['text']).strip() for p in pages}
    def matches(predicate):
        return [p['page_number'] for p in pages
                if len(p['text']) >= 200 and predicate(normalized[p['page_number']])]
    if ticker == '6669.TW':
        disclaimer=matches(lambda t:'This presentation is being delivered to the recipient.' in t)
        cover=matches(lambda t:'Copyright & Confidentiality Notice' in t and 'Wiwynn Corporation' in t)
        if len(cover)!=1:raise ValueError('issuer copyright cover absent or ambiguous')
        financial=matches(lambda t:'Income Statement' in t or 'Balance Sheet' in t)
        if len(financial)!=3:raise ValueError('issuer financial sections absent or ambiguous')
        cores={3:cover+financial,5:cover,12:cover}
    elif ticker == '2606.TW':
        disclaimer=matches(lambda t:'This presentation contains forward-looking statements.' in t)
        cores={3:matches(lambda t:bool(re.search(r'20\d{2}Q2 results highlights',t))),
               5:matches(lambda t:'Vessel Type Owned Managed JV' in t and 'Overall Group' in t),
               12:matches(lambda t:'SoH closed' in t and 'SoH open' in t
                          or '基準情境' in t and '下行風險' in t and '上行動能' in t)}
    elif ticker == '6282.TW':
        disclaimer=matches(lambda t:'Safe Harbor Notice' in t)
        financial=matches(lambda t:bool(re.search(r'[1-4]Q\d{2} Results Overview|20\d{2} 01-06 Results Overview',t))
                          or 'Cash Flow NT$ Million' in t)
        business=matches(lambda t:'About Acbel' in t or 'Product Offering' in t)
        cores={3:financial,5:business,12:business}
    elif ticker == '9945.TW':
        disclaimer=matches(lambda t:'Disclaimer' in t)
        cores={3:matches(lambda t:'RUENTEX DEVELOPMENT Consolidated I/S' in t),
               5:matches(lambda t:'Name：Ruentex Development(9945)' in t or 'Current Main Selling Projects' in t),
               12:matches(lambda t:'Vision of the Future' in t and '1.Property Development' in t)}
    else:
        disclaimer=matches(lambda t:'These forward-looking statements are based on information' in t)
        cores={3:matches(lambda t:'Statements of Comprehensive Income' in t and 'Comparison' in t
                         or 'Consolidated Balance Sheet' in t),
               5:matches(lambda t:'Greatek Business Overview' in t),
               12:matches(lambda t:'and Onward Business Outlook' in t and 'expected to' in t)}
    if len(disclaimer)!=1 or any(not v for v in cores.values()):
        raise ValueError('qualified role sections absent or ambiguous')
    roles={str(role):sorted(set(disclaimer+numbers))for role,numbers in cores.items()}
    for numbers in roles.values():
        if sum(len(p['text'])for p in pages if p['page_number'] in numbers)>6000:
            raise ValueError('qualified whole pages exceed role budget')
    used=set(n for numbers in roles.values()for n in numbers)
    return {'role_projection_policy':POLICY,'role_page_allowlist':roles,
            'projection_excluded_pages':[p['page_number']for p in pages if p['page_number']not in used]}


def needs_projection(context):
    if not isinstance(context,dict):return False
    proof=context.get('mops_material_receipt')
    documents=context.get('documents')
    if _qualified(context.get('ticker')) or isinstance(proof,dict) and _qualified(proof.get('ticker')):
        return True
    return isinstance(documents,list) and any(isinstance(d,dict) and
        (_qualified(d.get('ticker')) or d.get('role_projection_policy')==POLICY)for d in documents)


def verified_role_pages(context, role):
    from data_fetch.market_sources.mops_presentation import verify_context
    if not isinstance(context,dict):return []
    ticker=context.get('ticker')
    if not _qualified(ticker) or type(role) is not int or role not in (3,5,12) or not verify_context(context,ticker):
        return []
    document=context['documents'][0]
    # Recompute after full original verification; never trust a supplied list.
    allowed=projection(ticker,document['pages'])['role_page_allowlist'][str(role)]
    return [p for p in document['pages']if p['page_number']in allowed]
