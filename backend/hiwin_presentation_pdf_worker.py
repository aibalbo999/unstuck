"""Private exact-original cursor/glyph adapter; generic limits/warnings retained."""
from __future__ import annotations
import hashlib
import time
import source_pdf_worker as common
from hiwin_presentation_pdf_reader import (ORIGINAL_SHA256,PROGRAM_SHA256,ENCODED_PROGRAM_SHA256,
    CMAP_SHA256,SOURCE,TARGET,OCCURRENCES,glyph_evidence,_qualify_xref)


def _object(value):
    return value.get_object() if hasattr(value,'get_object') else value


def _verified_font(font):
    try:
        name='/CIDFont+F4'
        if (font.get('/BaseFont')!=name or font.get('/Type')!='/Font'
                or font.get('/Subtype')!='/Type0' or font.get('/Encoding')!='/Identity-H'):return False
        children=_object(font.get('/DescendantFonts'))
        if not isinstance(children,list) or len(children)!=1:return False
        child=_object(children[0])
        if (child.get('/Type')!='/Font' or child.get('/Subtype')!='/CIDFontType2'
                or child.get('/BaseFont')!=name or child.get('/CIDToGIDMap')!='/Identity'):return False
        system=_object(child.get('/CIDSystemInfo'));supplement=system.get('/Supplement')
        if (_object(system.get('/Registry'))!='Adobe' or _object(system.get('/Ordering'))!='Identity'
                or not isinstance(supplement,int) or isinstance(supplement,bool) or supplement!=0):return False
        descriptor=_object(child.get('/FontDescriptor'))
        if descriptor.get('/FontName')!=name:return False
        cmap=_object(font.get('/ToUnicode'));cmap_data=cmap.get_data()
        if cmap.get('/Filter') is not None or len(cmap_data)!=338 or hashlib.sha256(cmap_data).hexdigest()!=CMAP_SHA256:return False
        program=_object(descriptor.get('/FontFile2'));encoded=program._data;decoded=program.get_data()
        return (program.get('/Filter')=='/FlateDecode' and isinstance(encoded,bytes) and len(encoded)==12429
                and hashlib.sha256(encoded).hexdigest()==ENCODED_PROGRAM_SHA256
                and len(decoded)==27576 and hashlib.sha256(decoded).hexdigest()==PROGRAM_SHA256)
    except (AttributeError,KeyError,TypeError,ValueError,OverflowError):return False


def _normalize(text,fragments,page_number,font_cache):
    if str(page_number) not in OCCURRENCES or fragments is None or ''.join(f for f,_ in fragments)!=text:return text,{}
    result=[];count=0
    for fragment,font in fragments:
        if font is not None and fragment.strip()==SOURCE:
            key=('hiwin-circle',id(font))
            if key not in font_cache:font_cache[key]=_verified_font(font)
            if font_cache[key]:fragment=fragment.replace(SOURCE,TARGET);count+=1
        result.append(fragment)
    return ''.join(result),({'U+F06C':count} if count else {})


def _extract(raw,deadline):
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL_SHA256:raise common._Failure('invalid_pdf')
    import pypdf
    import source_pdf_symbols
    base=pypdf.PdfReader;normalizer=source_pdf_symbols.normalize_verified_symbols;proof=None;counts={}
    class QualifiedReader(base):
        def __init__(self,stream,*args,**kwargs):
            nonlocal proof
            if kwargs.get('strict') is not True or stream.getvalue()!=raw:raise common._Failure('invalid_pdf')
            self._offsets,proof=_qualify_xref(raw,deadline)
            super().__init__(stream,*args,**kwargs)
        def read_object_header(self,stream):
            if time.monotonic()>=deadline:raise common._Failure('timeout')
            offset=stream.tell()
            if offset not in self._offsets or stream.read(1)!=b'\n':raise common._Failure('invalid_pdf')
            actual=super().read_object_header(stream)
            if actual!=self._offsets[offset]:raise common._Failure('invalid_pdf')
            return actual
    def specific(text,fragments,number,font_cache):
        if time.monotonic()>=deadline:raise common._Failure('timeout')
        text,count=_normalize(text,fragments,number,font_cache)
        if count:counts[str(number)]=count
        if time.monotonic()>=deadline:raise common._Failure('timeout')
        return text,[]
    try:
        pypdf.PdfReader=QualifiedReader;source_pdf_symbols.normalize_verified_symbols=specific
        result=_GENERIC_EXTRACT(raw,deadline)
    finally:
        pypdf.PdfReader=base;source_pdf_symbols.normalize_verified_symbols=normalizer
    if time.monotonic()>=deadline:raise common._Failure('timeout')
    if proof is None or result['page_count']!=13 or result['coverage_status']!='complete' or counts!=OCCURRENCES:
        raise common._Failure('invalid_pdf')
    result['hiwin_glyph_evidence']=glyph_evidence();result['xref_validation_evidence']=proof
    return result


_GENERIC_EXTRACT=common._extract
if __name__=='__main__':
    common._extract=_extract
    common.main()
