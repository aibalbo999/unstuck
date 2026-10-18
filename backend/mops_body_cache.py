"""Advisory body-discovery hints; these never substitute for original proofs."""
import math
import re
import time
from cache_store import get_cache_json, set_cache_json
from mops_material_originals import RAW_TTL
from mops_previous_year import POLICY as PREVIOUS_POLICY
from mops_qualified_role_pages import QUALIFIED, POLICY as ROLE_POLICY

PREFIX='mops-body-ready:v2:'
POLICY='mops-body-discovery-hint-v2'
DISCOVERY_TTL=6*60*60


def supported(ticker):
    return isinstance(ticker,str) and ticker in QUALIFIED


def _finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def publish_body_hint(value):
    """Called only after verification; store no pages, quotes or archive paths.

    Cache I/O failure loses this optimization, never rejects valid evidence.
    The ordinary provider still replays every original when a hint is used.
    """
    try:
        ticker=value['ticker']
        if not supported(ticker):return False
        proof=value['mops_material_receipt'];doc=value['documents'][0];now=time.time()
        if proof['ticker']!=ticker or doc['ticker']!=ticker:return False
        keys=('master','index','material')+(('absence_current_index',)if proof['policy']==PREVIOUS_POLICY else ())
        expiries=[]
        for key in keys:
            receipt=proof[key];stamp=receipt['retrieved_at']
            expiry=receipt.get('fresh_until_epoch',stamp+RAW_TTL)
            if (not _finite(stamp) or not _finite(expiry)
                    or not 0<stamp<=now<expiry<=stamp+RAW_TTL):return False
            expiries.append(expiry)
        expiry=min(expiries)
        digest=doc['content_sha256']
        if expiry-now<1 or not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest):return False
        marker={'policy':POLICY,'ticker':ticker,'observed_at_epoch':now,
                'valid_until_epoch':expiry,'discovery_until_epoch':now+DISCOVERY_TTL,
                'content_sha256':digest}
        set_cache_json(PREFIX+ticker,marker,ttl_seconds=DISCOVERY_TTL)
        return True
    except Exception:
        return False


def _discovery_marker(ticker):
    if not supported(ticker):return False
    try:
        marker=get_cache_json(PREFIX+ticker);now=time.time()
        if not isinstance(marker,dict) or set(marker)!={'policy','ticker','observed_at_epoch','valid_until_epoch','discovery_until_epoch','content_sha256'}:
            return False
        stamp,expiry,end=marker['observed_at_epoch'],marker['valid_until_epoch'],marker['discovery_until_epoch']
        valid=(marker['policy']==POLICY and marker['ticker']==ticker
                and _finite(stamp) and _finite(expiry) and _finite(end)
                and 0<stamp<=now<end<=stamp+DISCOVERY_TTL and stamp<expiry<=stamp+RAW_TTL
                and isinstance(marker['content_sha256'],str)
                and re.fullmatch(r'[0-9a-f]{64}',marker['content_sha256']) is not None)
        return marker if valid else False
    except Exception:
        return False


def body_ready(ticker):
    marker=_discovery_marker(ticker)
    return bool(marker and time.time()<marker['valid_until_epoch'])


def body_discovered(ticker):
    """Schedule ordinary revalidation, including after original proof expiry."""
    return bool(_discovery_marker(ticker))


def originals_due(value,ticker):
    """Only schedule reassembly; actual acceptance remains in the provider."""
    from data_fetch.market_sources.mops_presentation import supports as material_supported, is_marked, _originals_current_at_handoff, POLICY as MATERIAL_POLICY, STATIC_POLICY
    if not material_supported(ticker) or not is_marked(value):return False
    try:
        proof=value['mops_material_receipt'];doc=value['documents'][0]
        return (value['ticker']!=ticker or proof['ticker']!=ticker or doc['ticker']!=ticker
                or proof.get('policy') not in (MATERIAL_POLICY,STATIC_POLICY,PREVIOUS_POLICY)
                or supported(ticker) and (doc.get('role_projection_policy')!=ROLE_POLICY
                    or not isinstance(doc.get('role_page_allowlist'),dict))
                or not _originals_current_at_handoff(proof))
    except (KeyError,IndexError,TypeError,ValueError,AttributeError,OverflowError):
        return True
