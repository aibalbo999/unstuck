"""Date new prompt catalogs at their verified frozen input boundary.

Historical catalogs and output bindings are never reconstructed by this helper.
This verifies saved identity, not source truth, freshness or historical PIT.
"""
from datetime import datetime,date
from zoneinfo import ZoneInfo
import hashlib,json,re


def catalog_day(data, *, as_of=None):
    now=datetime.now(ZoneInfo('Asia/Taipei'))
    if not isinstance(data,dict) or not any(key in data for key in ('analysis_input_cutoff','analysis_input_hash','_analysis_input_evidence')):
        return as_of or now.date()
    from data_trust_snapshot_sanitizer import sanitize_for_snapshot
    from report_analysis_evidence import validate_analysis_evidence, MAX_ANALYSIS_EVIDENCE_BYTES
    try:
        stamp=data['analysis_input_cutoff'];digest=data['analysis_input_hash'];encoded=data['_analysis_input_evidence']
        if not isinstance(stamp,str) or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest) or not isinstance(encoded,str):
            raise ValueError('Frozen input identity missing')
        if len(encoded.encode('utf-8')) > MAX_ANALYSIS_EVIDENCE_BYTES:
            raise ValueError('Frozen receipt exceeds existing evidence budget')
        cutoff=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if cutoff.tzinfo is None or cutoff>now:
            raise ValueError('Frozen cutoff is unknown or future')
        packet=validate_analysis_evidence(json.loads(encoded))
        if (packet.get('capture_boundary')!='analysis_start' or packet.get('input_verification')!='hash_verified'
                or packet.get('analysis_input_hash')!=digest or packet.get('analysis_input_cutoff')!=stamp):
            raise ValueError('Original frozen receipt mismatch')
        clean=sanitize_for_snapshot({k:v for k,v in data.items() if k not in {'analysis_input_cutoff','analysis_input_hash'}})
        current=hashlib.sha256(json.dumps(clean,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if current!=digest:
            raise ValueError('Frozen input changed')
        day=cutoff.astimezone(ZoneInfo('Asia/Taipei')).date()
        if as_of is not None:
            if type(as_of) is not date or as_of>day:
                raise ValueError('Projection day exceeds frozen input')
            return as_of
        return day
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        raise ValueError('Trade source catalog requires a verified frozen cutoff') from exc
