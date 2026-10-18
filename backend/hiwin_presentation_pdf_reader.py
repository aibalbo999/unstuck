"""One exact HIWIN presentation: qualified native text, not chart semantics.

Only its proven xref cursor and embedded filled-circle glyph are handled.
Original bytes, all other characters/order and generic parser guards remain.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
from source_pdf_reader import SourcePdfError,_run_worker,_validate_result

ORIGINAL_SHA256='ebb6150526e26f75787f30db984ecac363ee95997770c905530491eaf078affb'
PROGRAM_SHA256='c889284ec9a7cdfbd422ab8c31b3487e3f435c4952de1aed8e6aeb7bc561277c'
ENCODED_PROGRAM_SHA256='f8fdc7cf731695e25a3687e3d3ceab1e35d18eddb4710c8efab3d501a16e9f6c'
CMAP_SHA256='4496b5ddbd0ff39e81044ad0dcd566c9aa398fc6e66332c295b34cdf72d5b6db'
OUTLINE_SHA256='f2e0c2f4c354ef96ce6662965f1ca3c46103504bafafb94dfd1afdcbb321931b'
POLICY='hiwin-2026q1-exact-native-filled-circle.v1'
XREF_POLICY='hiwin-2026q1-exact-xref-lf.v1'
INPUT_LIMIT=8*1024*1024
SOURCE='\uf06c'
TARGET='\u25cf'
OCCURRENCES={str(n):{'U+F06C':1} for n in range(2,13)}
PAGE_TEXT_SHA256=(
    '1591d2a24cdfd68303ac1da17ee9f86149ae68d111046c0f7e824298a763c200',
    '81de3e3dd82ad9dbdcaaccd64cb8646c1aef0c356734d02cb417c43921819c70',
    '86ef16024fdf9cb6c0b1acd312fb787fd263db120f710d7d8fdace95f1c66994',
    '653ed3d6198e1fe315c25609751e43a364d51ba7fe82e9a23e57cd7b18ce68a1',
    '76bd17b709b50c8e83b5c42d9d5ce3e01e366cee0730a8d85bebce4d11474fdc',
    '46b915fdde4cb98449caf483ae6e58f56383da7978d32824254a0bc0c79ad094',
    'ccb47d00d6c9f85a8ba9dcdba321df5af05cfdd3ff4155ff665d3ee6afef9039',
    '51d20a43a44059cec80ab9ddad7d2303d531f0059b42c78fedd239de963457d9',
    '9df0a7b07177b02674805b150e096085523b74c7f90108007d943a2b33e89726',
    '1ecdfe52d3b9b76c3eaede08ae1411cbcefdcaf0471ac2756386498e1f9b9fa0',
    '384110cacd4901de050f5dfa0a389efb54e39419e09b72634628a5bbd9407558',
    '1fc0d57291937b59ca05e372193d1f66b4d6ab69a69f4f602211719c10c4233b',
    '2034ce6155036f8a009ef33985209e889731617692c823f09e6acb5cf8b1b888',
)


def glyph_evidence():
    return {'policy':POLICY,'complete_original_sha256':ORIGINAL_SHA256,
        'font_program_sha256':PROGRAM_SHA256,'font_program_bytes':27576,
        'encoded_font_program_sha256':ENCODED_PROGRAM_SHA256,'encoded_font_program_bytes':12429,
        'cmap_sha256':CMAP_SHA256,'cmap_bytes':338,'decomposed_outline_sha256':OUTLINE_SHA256,
        'source_font':'CIDFont+F4','encoding':'Identity-H','cid_to_gid_map':'Identity','source_cid':122,'glyph_id':122,
        'source_character':'U+F06C','replacement_character':'U+25CF',
        'occurrences_by_page':{p:dict(c) for p,c in OCCURRENCES.items()},
        'raw_bytes_rewritten':False,'other_characters_and_native_order_preserved':True,
        'other_parser_warnings_fatal':True,'visual_semantics_verified':False}


def xref_evidence():
    """Pinned research-qualified proof for source-layer exact receipt replay.

    Returning this contract does not validate caller bytes. Extraction still
    checks the original digest and every entry/header against the actual bytes.
    """
    return {'policy':XREF_POLICY,'complete_original_sha256':ORIGINAL_SHA256,
        'classic_xref_offset':975922,'xref_size':118,'in_use_objects':117,
        'verified_offsets_sha256':'6bf3312c135650e76c4f1bceea8df079b58e9ca2aabb077a230fc819828560f4',
        'trailer_sha256':'5dbf56210946600f22e55ceb1656a093250ae60fb233aaa4163939a61cd34357',
        'cursor_delta_bytes':1,'prefix_hex':'0a','raw_bytes_rewritten':False,
        'xref_table_rewritten':False,'other_parser_warnings_fatal':True}


def _deadline(deadline):
    if time.monotonic()>=deadline:raise SourcePdfError('timeout')


def _qualify_xref(raw,deadline):
    """Check every classic entry/header and exact trailer before moving a cursor."""
    _deadline(deadline)
    if not isinstance(raw,bytes) or len(raw)!=978367:raise ValueError('original_size')
    endings=list(re.finditer(rb'(?m)^startxref\n(\d+)\n%%EOF\n',raw))
    if len(endings)!=1 or endings[0].end()!=len(raw) or int(endings[0][1])!=975922:raise ValueError('trailer_shape')
    start=975922;prefix=b'xref\n0 118\r\n'
    if raw[:9]!=b'%PDF-1.7\n' or raw[start:start+len(prefix)]!=prefix:raise ValueError('classic_xref_profile')
    if [m.start() for m in re.finditer(rb'(?m)^xref\n',raw)]!=[start]:raise ValueError('classic_xref_count')
    block=raw[start+len(prefix):];entries=[]
    for object_id in range(118):
        _deadline(deadline)
        match=re.fullmatch(rb'(\d{10}) (\d{5}) ([fn])\r\n',block[object_id*20:(object_id+1)*20])
        if not match:raise ValueError('xref_entry_shape')
        entries.append((int(match[1]),int(match[2]),match[3]))
    trailer=b'trailer\n<<\n/Info 117 0 R\n/Root 1 0 R\n/Size 118\n>>\nstartxref\n975922\n%%EOF\n'
    if block[118*20:]!=trailer or entries[0]!=(0,65535,b'f'):raise ValueError('trailer_profile')
    offsets={}
    for object_id,(offset,generation,kind) in enumerate(entries[1:],1):
        _deadline(deadline)
        if kind!=b'n' or generation!=0 or offset in offsets or not 0<offset<start:raise ValueError('object_map')
        header=f'\n{object_id} 0 obj\n'.encode('ascii')
        if raw[offset:offset+len(header)]!=header:raise ValueError('object_header_offset')
        offsets[offset]=(object_id,generation)
    actual=list(re.finditer(rb'(?m)^(\d+) (\d+) obj\n',raw))
    if len(actual)!=117 or {(m.start()-1,int(m[1]),int(m[2])) for m in actual}!={(o,*v) for o,v in offsets.items()}:
        raise ValueError('unindexed_or_duplicate_header')
    ordered=sorted(offsets)
    for i,offset in enumerate(ordered):
        _deadline(deadline);end=ordered[i+1] if i+1<len(ordered) else start
        if not raw[offset:end].endswith(b'endobj' if i+1<len(ordered) else b'endobj\n'):raise ValueError('object_end_boundary')
    mapping=[[o,*offsets[o]] for o in ordered]
    proof={'policy':XREF_POLICY,'complete_original_sha256':hashlib.sha256(raw).hexdigest(),
        'classic_xref_offset':start,'xref_size':118,'in_use_objects':117,
        'verified_offsets_sha256':hashlib.sha256(json.dumps(mapping,separators=(',',':')).encode()).hexdigest(),
        'trailer_sha256':hashlib.sha256(trailer).hexdigest(),'cursor_delta_bytes':1,'prefix_hex':'0a',
        'raw_bytes_rewritten':False,'xref_table_rewritten':False,'other_parser_warnings_fatal':True}
    _deadline(deadline);return offsets,proof


def extract_hiwin_presentation_pages(raw,*,timeout_seconds=10):
    """Return every native page; hidden strings/chart geometry remain unqualified."""
    if not isinstance(raw,bytes) or not raw or len(raw)>INPUT_LIMIT:raise SourcePdfError('invalid_input')
    if type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 0<timeout_seconds<=10:
        raise SourcePdfError('invalid_timeout')
    deadline=time.monotonic()+float(timeout_seconds);digest=hashlib.sha256(raw).hexdigest()
    try:
        _deadline(deadline)
        if digest!=ORIGINAL_SHA256:raise SourcePdfError('invalid_pdf')
        command=[sys.executable,'-B',str(Path(__file__).with_name('hiwin_presentation_pdf_worker.py')),str(deadline)]
        output=_run_worker(raw,deadline,worker_command=command);_deadline(deadline)
        value=json.loads(output)
        if isinstance(value,dict) and set(value)=={'error'}:_validate_result(value,digest)
        if not isinstance(value,dict):raise SourcePdfError('invalid_worker_result')
        glyph=value.pop('hiwin_glyph_evidence',None);xref=value.pop('xref_validation_evidence',None)
        _,expected_xref=_qualify_xref(raw,deadline);expected_glyph=glyph_evidence()
        if (json.dumps(expected_xref,sort_keys=True)!=json.dumps(xref_evidence(),sort_keys=True)
                or json.dumps(glyph,sort_keys=True)!=json.dumps(expected_glyph,sort_keys=True)
                or json.dumps(xref,sort_keys=True)!=json.dumps(expected_xref,sort_keys=True)):
            raise SourcePdfError('invalid_worker_result')
        result=_validate_result(value,digest)
        if (result['page_count']!=13 or result['coverage_status']!='complete'
                or tuple(hashlib.sha256(p['text'].encode()).hexdigest() for p in result['pages'])!=PAGE_TEXT_SHA256):
            raise SourcePdfError('invalid_worker_result')
        result['hiwin_glyph_evidence']=expected_glyph;result['xref_validation_evidence']=expected_xref
        _deadline(deadline);return result
    except SourcePdfError as exc:
        exc.content_sha256=digest;raise
    except (OSError,ValueError,TypeError,OverflowError):
        raise SourcePdfError('invalid_worker_result',content_sha256=digest) from None
