"""Offline private child: exact original/cursor only, generic guards unchanged."""
from hashlib import sha256
import time
from pathlib import Path
import sys
sys.path.append(str(Path.cwd()))
from pcsc_presentation_pdf_reader import ORIGINAL_SHA256,qualify_xref
import source_pdf_worker as common

_GENERIC_EXTRACT=common._extract

def extract(raw,deadline):
    if sha256(raw).hexdigest()!=ORIGINAL_SHA256:raise common._Failure('invalid_pdf')
    import pypdf
    original=pypdf.PdfReader;proof=None
    class QualifiedReader(original):
        def __init__(self,stream,*args,**kwargs):
            nonlocal proof
            if kwargs.get('strict') is not True or stream.getvalue()!=raw:raise common._Failure('invalid_pdf')
            self._offsets,proof=qualify_xref(raw,deadline)
            super().__init__(stream,*args,**kwargs)
        def read_object_header(self,stream):
            if time.monotonic()>=deadline:raise common._Failure('timeout')
            offset=stream.tell()
            if offset not in self._offsets or stream.read(1)!=b'\n':raise common._Failure('invalid_pdf')
            actual=super().read_object_header(stream)
            if actual!=self._offsets[offset]:raise common._Failure('invalid_pdf')
            return actual
    try:
        pypdf.PdfReader=QualifiedReader
        result=_GENERIC_EXTRACT(raw,deadline)
    finally:pypdf.PdfReader=original
    if time.monotonic()>=deadline:raise common._Failure('timeout')
    if proof is None or result['page_count']!=22:raise common._Failure('invalid_pdf')
    proof.pop('object_entries')
    result['xref_validation_evidence']=proof
    return result

if __name__=='__main__':
    common._extract=extract
    raise SystemExit(common.main())
