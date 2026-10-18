"""Exact PCSC PDF cursor qualification; all text order and PUA remain native."""
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time

import math
ORIGINAL_SHA256='4a99ce841273bce48194429a6c7465fd720df0d615a784a2046dbc34305296bf'
POLICY='pcsc-2026h1-classic-xref-leading-lf-v1'
SIZE=1853789
XREF_OFFSET=1849603
XREF_SIZE=205


def qualify_xref(raw,deadline):
    def check():
        if time.monotonic()>=deadline:raise ValueError('deadline')
    check()
    if not isinstance(raw,bytes) or len(raw)!=SIZE:raise ValueError('original_size')
    if not raw.startswith(b'%PDF-1.7\n'):raise ValueError('pdf_header')
    endings=list(re.finditer(rb'(?m)^startxref\n(\d+)\n%%EOF\n',raw))
    if len(endings)!=1 or endings[0].end()!=len(raw) or int(endings[0][1])!=XREF_OFFSET:raise ValueError('terminal_startxref')
    if [m.start() for m in re.finditer(rb'(?m)^xref\n',raw)]!=[XREF_OFFSET]:raise ValueError('classic_xref_count')
    prefix=b'xref\n0 205\r\n';start=XREF_OFFSET
    if raw[start:start+len(prefix)]!=prefix:raise ValueError('xref_subsection')
    table_start=start+len(prefix);entries=[];offsets={}
    for object_id in range(XREF_SIZE):
        check();entry=raw[table_start+20*object_id:table_start+20*(object_id+1)]
        match=re.fullmatch(rb'(\d{10}) (\d{5}) ([fn])\r\n',entry)
        if not match:raise ValueError('xref_entry_shape')
        offset,generation,kind=int(match[1]),int(match[2]),match[3]
        entries.append({'object_id':object_id,'offset':offset,'generation':generation,'state':kind.decode(),'xref_entry_hex':entry.hex()})
        if object_id==0:
            if (offset,generation,kind)!=(0,65535,b'f'):raise ValueError('free_head')
            continue
        if kind!=b'n' or generation!=0 or offset in offsets or not 0<offset<start:raise ValueError('object_map')
        header=f'\n{object_id} 0 obj\n'.encode()
        if raw[offset:offset+len(header)]!=header:raise ValueError('exact_header_offset')
        entries[-1]['header_hex']=header.hex();offsets[offset]=(object_id,generation)
    trailer=(b'trailer\n<<\n/Info 204 0 R\n/Root 1 0 R\n/Size 205\n>>\nstartxref\n1849603\n%%EOF\n')
    if raw[table_start+20*XREF_SIZE:]!=trailer:raise ValueError('trailer')
    actual=list(re.finditer(rb'(?m)^(\d+) (\d+) obj\n',raw))
    if len(actual)!=204 or {(m.start()-1,int(m[1]),int(m[2])) for m in actual}!={(o,*v) for o,v in offsets.items()}:
        raise ValueError('unindexed_or_duplicate_object')
    sorted_offsets=sorted(offsets)
    for i,offset in enumerate(sorted_offsets):
        check();end=sorted_offsets[i+1] if i+1<len(sorted_offsets) else start
        block=raw[offset:end]
        if not block.endswith(b'endobj' if i+1<len(sorted_offsets) else b'endobj\n'):raise ValueError('object_end_boundary')
        entries[offsets[offset][0]].update(object_bytes=end-offset,object_span_sha256=sha256(block).hexdigest())
    mapping=[[o,*offsets[o]] for o in sorted_offsets]
    proof={'policy':POLICY,'complete_original_sha256':sha256(raw).hexdigest(),'bytes':len(raw),
        'classic_xref_offset':start,'xref_size':XREF_SIZE,'in_use_objects':204,'free_objects':[0],
        'startxref_count':1,'classic_xref_count':1,'subsections':[[0,205]],'trailer_root':[1,0],
        'trailer_info':[204,0],'trailer_size':205,'trailer_hex':trailer.hex(),
        'trailer_sha256':sha256(trailer).hexdigest(),'incremental_prev_or_xrefstm':False,
        'verified_offsets_sha256':sha256(json.dumps(mapping,separators=(',',':')).encode()).hexdigest(),
        'cursor_delta_bytes':1,'prefix_hex':'0a','raw_bytes_rewritten':False,'xref_table_rewritten':False,
        'other_parser_warnings_fatal':True,'object_entries':entries}
    check();return offsets,proof



PAGE_TEXT_SHA256 = ('54c6ce61209ce7d634d5839647ce020af227b57ef2bac831fade853f5a4368ff', '1bd4c5a7b2244614c2b3e5ddcbc24123e89c501199b9c8c627ab8566d3dca39d', '412fe82c1a2799a22568d46844595c514509a942d3c682b2ffa36efd5166d3d0', '18c77d57bf1a65010567430439a8f5bab83435ef9622e39ec74da197f53ce2a5', '4b61436fcc4c6c8e9282a053208ab0d9995dbd85b03f6866cc3899b8ccd5608e', 'b9584ac13b987ae9d0dd12db7b70825841a54aba819cefa9c35a93b977a25b0b', '5c95baa13e946c0033474bc8cf447db1e7f7810f216a926021aa5680ef58fdbe', 'e31ddeebb3eb6549a2f488b091f0bf0746474832bf1d3df68c03d32466bce7c8', '5a182dbe89511cff292178efabcc1ad64936a810cc66e8eb274878a89d54c1cb', 'e346e25715972ca469f15ab7e2726830748a82e1306c3876bdaa0a918646e02f', 'e71aaa897b7d926b26023ad1a0c2c3523f57fede9ee5833ae67b46f752f5cad4', '7b8a3c8d774215421d83f77dca5ebd10fc0e8d3c9f0a229ad152d8f6e0edda57', '23b2802c83d12b095ef027d40cf64c49781b821ff2fe986349a1bf3f4804681d', '8c179678dabd995eccec01dcf37d7f7b544ff2a7240937ca93868b0ce9cbc60f', '83d6d44e0397e4cd33ef199976b5af891db672e6b781f8d60c614dbecd0bbb04', '79739dd0669ccd3f8359aef3416fb9a26d02336304be7ff580d6a881e923eafd', 'aa9351576540d57ae92ddb91e057afb7e868cc4314d60023c7f041f37b06c2ba', '12e9a63bfd45c143e8c86dedd0ee1e020e86f92289e9c4be89cdb5f292af6357', '8187d5d6b3031fd68a2963863c6b7dc90b15effe3cdb306af11ac0da0f9f523e', '2073d61814b38586b5463074c879189528e5e0884d3dff0b996086aa871ee3e8', '1e7f262fdfbd9330d4752456b95477bf572121ff213f986bfab0453bbf1a1423', 'e281a146da57f4017b9af109b4ae730c1472a5b38418177b976c32b8625d3901')

_XREF = {'policy': 'pcsc-2026h1-classic-xref-leading-lf-v1', 'complete_original_sha256': '4a99ce841273bce48194429a6c7465fd720df0d615a784a2046dbc34305296bf', 'bytes': 1853789, 'classic_xref_offset': 1849603, 'xref_size': 205, 'in_use_objects': 204, 'free_objects': [0], 'startxref_count': 1, 'classic_xref_count': 1, 'subsections': [[0, 205]], 'trailer_root': [1, 0], 'trailer_info': [204, 0], 'trailer_size': 205, 'trailer_hex': '747261696c65720a3c3c0a2f496e666f20323034203020520a2f526f6f742031203020520a2f53697a65203230350a3e3e0a7374617274787265660a313834393630330a2525454f460a', 'trailer_sha256': '1c51434b8ea3173ff2295379f1d60113f653c1ee3ffb07021dafe87d9e6d763b', 'incremental_prev_or_xrefstm': False, 'verified_offsets_sha256': '9c4277cb363b2c153557d4e0c741c19f8b8fe7757ad5b0d38b2f809c8af6d275', 'cursor_delta_bytes': 1, 'prefix_hex': '0a', 'raw_bytes_rewritten': False, 'xref_table_rewritten': False, 'other_parser_warnings_fatal': True}

def xref_evidence():
    return json.loads(json.dumps(_XREF))

def extract_pcsc_presentation_pages(raw, *, timeout_seconds=10):
    from source_pdf_reader import _run_worker, _validate_result, SourcePdfError
    if not isinstance(raw,bytes) or not 0 < len(raw) <= 8*1024*1024:
        raise SourcePdfError('invalid_input')
    if type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 10:
        raise SourcePdfError('invalid_timeout')
    deadline=time.monotonic()+timeout_seconds
    digest=sha256(raw).hexdigest()
    if digest != ORIGINAL_SHA256:raise SourcePdfError('invalid_pdf',content_sha256=digest)
    try:
        command=[sys.executable,'-B',str(Path(__file__).with_name('pcsc_presentation_pdf_worker.py')),str(deadline)]
        output=_run_worker(raw,deadline,worker_command=command)
        if time.monotonic()>=deadline:raise SourcePdfError('timeout')
        value=json.loads(output)
        if isinstance(value,dict) and set(value)=={'error'}:_validate_result(value,digest)
        if not isinstance(value,dict):raise SourcePdfError('invalid_worker_result')
        xref=value.pop('xref_validation_evidence',None)
        _,expected=qualify_xref(raw,deadline);expected.pop('object_entries')
        canonical=lambda v:json.dumps(v,sort_keys=True,allow_nan=False,separators=(',',':'))
        if canonical(xref)!=canonical(expected) or canonical(expected)!=canonical(xref_evidence()):
            raise SourcePdfError('invalid_worker_result')
        result=_validate_result(value,digest)
        if (result['page_count']!=22 or result['coverage_status']!='partial'
                or result['empty_pages']!=[] or result['garbled_pages']!=[3,4]
                or tuple(sha256(p['text'].encode()).hexdigest() for p in result['pages'])!=PAGE_TEXT_SHA256):
            raise SourcePdfError('invalid_worker_result')
        result['xref_validation_evidence']=expected
        if time.monotonic()>=deadline:raise SourcePdfError('timeout')
        return result
    except SourcePdfError:raise
    except (ValueError,TypeError,KeyError,OSError,OverflowError):
        raise SourcePdfError('invalid_worker_result',content_sha256=digest) from None
