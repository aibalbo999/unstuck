"""Private exact-font symbol mapping; raw pages/covered text and generic guards retained."""
from __future__ import annotations
import hashlib,time
import source_pdf_worker as common
from lienhwa_presentation_pdf_reader import ORIGINAL_SHA256,glyph_evidence


def _object(value):return value.get_object() if hasattr(value,'get_object') else value

def _verified_font(font):
    try:
        proof=glyph_evidence();name='/'+proof['source_font']
        if (font.get('/BaseFont')!=name or font.get('/Type')!='/Font'
                or font.get('/Subtype')!='/Type0' or font.get('/Encoding')!='/Identity-H'):return False
        children=_object(font.get('/DescendantFonts'))
        if not isinstance(children,list) or len(children)!=1:return False
        child=_object(children[0]);system=_object(child.get('/CIDSystemInfo'))
        if (child.get('/Type')!='/Font' or child.get('/Subtype')!='/CIDFontType2'
                or child.get('/BaseFont')!=name or child.get('/CIDToGIDMap')!='/Identity'
                or system.get('/Registry')!='Adobe' or system.get('/Ordering')!='Identity'
                or type(system.get('/Supplement')) is not int and not isinstance(system.get('/Supplement'),int)
                or isinstance(system.get('/Supplement'),bool) or system.get('/Supplement')!=0):return False
        descriptor=_object(child.get('/FontDescriptor'))
        if descriptor.get('/FontName')!=name:return False
        cmap=_object(font.get('/ToUnicode'));program=_object(descriptor.get('/FontFile2'))
        for stream,prefix in [(cmap,'cmap'),(program,'font_program')]:
            if stream.get('/Filter')!='/FlateDecode':return False
            encoded=stream._data;decoded=stream.get_data()
            if (not isinstance(encoded,bytes) or len(encoded)!=proof[prefix+'_encoded_bytes']
                    or hashlib.sha256(encoded).hexdigest()!=proof[prefix+'_encoded_sha256']
                    or len(decoded)!=proof[prefix+'_bytes'] or hashlib.sha256(decoded).hexdigest()!=proof[prefix+'_sha256']):return False
        return True
    except (AttributeError,KeyError,TypeError,ValueError,OverflowError):return False


def _normalize(text,fragments,page_number,font_cache):
    if page_number!=15 or fragments is None or ''.join(f for f,_ in fragments)!=text:return text,0
    result=[];count=0
    for fragment,font in fragments:
        if font is not None and fragment.strip()=='\uf06c':
            key=('lienhwa-circle',id(font))
            if key not in font_cache:font_cache[key]=_verified_font(font)
            if font_cache[key]:fragment=fragment.replace('\uf06c','●');count+=1
        result.append(fragment)
    return ''.join(result),count


_GENERIC_EXTRACT=common._extract

def _extract(raw,deadline):
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL_SHA256:raise common._Failure('invalid_pdf')
    import source_pdf_symbols
    normalizer=source_pdf_symbols.normalize_verified_symbols;counts={}
    def specific(text,fragments,number,font_cache):
        if time.monotonic()>=deadline:raise common._Failure('timeout')
        text,count=_normalize(text,fragments,number,font_cache)
        if count:counts[number]=count
        return text,[]
    try:
        source_pdf_symbols.normalize_verified_symbols=specific
        result=_GENERIC_EXTRACT(raw,deadline)
    finally:source_pdf_symbols.normalize_verified_symbols=normalizer
    if time.monotonic()>=deadline:raise common._Failure('timeout')
    if (counts!={15:3} or result['page_count']!=30 or result['coverage_status']!='partial'
            or result['empty_pages']!=[2,3,6,11,12,21] or result['garbled_pages']):raise common._Failure('invalid_pdf')
    result['lienhwa_glyph_evidence']=glyph_evidence()
    return result

if __name__=='__main__':
    common._extract=_extract
    common.main()
