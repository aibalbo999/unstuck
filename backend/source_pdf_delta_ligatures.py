"""Decode four visually qualified embedded glyphs in one exact Delta original.

The PDF's native ToUnicode maps ft/tf/ti to U+FFFD and tt to a single t.
Original glyph outlines and the rendered page were independently retained in
delta-transcript-integration evidence. No spelling inference or OCR is used.
Unknown document, font program or CMap bytes remain untouched.
"""
from hashlib import sha256

POLICY='delta-2q26-embedded-ligatures-v1'
DOCUMENT_SHA256='1d3cf7fb34d23713300c694b86e0af732115eb937b24996b649591aad107916b'
DECODED_CMAPS={'/BHHLUL+Calibri':'096e26e734c4d10fe623eca7447d8fb70a2ec4db34f23d966a58d648e6fb424e',
               '/OYVLUL+Calibri-Bold':'0c13e06fec816ebdf1792b7f8c17c0b73a2171a0f57aa89928908f6029ae311e'}
FONTS={
    '/OYVLUL+Calibri-Bold':('99560502c3a069d719b2bfaebc76a45196e20e1caefb48e2f6b08f1241d1556e','e4b55f0d2a5b5d2e5a40716451512d2df334a4a5bbf3ee75f114c73cfbd41b16',83998,((415,'FFFD','00740069'),)),
    '/BHHLUL+Calibri':('5d82c81469da31a2bff6401ceabaefc7dd08faaf7ba1fa811706675918463616','3960aa1f5b840ec7a2aa7a8a9813d394ce43e311268e9e9eb0be7f0ddfa67861',100457,((332,'FFFD','00660074'),(414,'FFFD','00740066'),(415,'FFFD','00740069'),(425,'0074','00740074'))),
}

def _evidence(name,cmap):
    program,before,_,mappings=FONTS[name]
    return {'policy':POLICY,'source_pdf_sha256':DOCUMENT_SHA256,'source_font':name,
            'font_program_sha256':program,'original_cmap_sha256':before,
            'decoded_cmap_sha256':sha256(cmap).hexdigest(),
            'mappings':[{'cid':cid,'original_unicode_hex':old,'decoded_unicode_hex':new}for cid,old,new in mappings]}

def qualify_embedded_ligatures(document,raw_digest):
    if raw_digest!=DOCUMENT_SHA256:return []
    pending={}
    for page in document.pages:
        for ref in page['/Resources']['/Font'].values():
            font=ref.get_object();name=str(font.get('/BaseFont'))
            if name not in FONTS:continue
            program_hash,cmap_hash,length,mappings=FONTS[name]
            if (font.get('/Type')!='/Font'or font.get('/Subtype')!='/Type0'or font.get('/Encoding')!='/Identity-H'
                    or '/DescendantFonts' not in font or len(font['/DescendantFonts'])!=1):return []
            child=font['/DescendantFonts'][0].get_object();descriptor=child.get('/FontDescriptor',{}).get_object()
            if (child.get('/Subtype')!='/CIDFontType2'or child.get('/CIDToGIDMap')!='/Identity'
                    or child.get('/BaseFont')!=name or descriptor.get('/FontName')!=name):return []
            program=descriptor['/FontFile2'].get_object().get_data();cmap=font['/ToUnicode'].get_object().get_data()
            if len(program)!=length or sha256(program).hexdigest()!=program_hash or sha256(cmap).hexdigest()!=cmap_hash:return []
            if name in pending:
                if pending[name][0] is not font:return []
                continue
            for cid,old,new in mappings:
                token=f'<{cid:04X}> <{old}>'.encode()
                if cmap.count(token)!=1:return []
                cmap=cmap.replace(token,f'<{cid:04X}> <{new}>'.encode())
            pending[name]=(font,cmap)
    if set(pending)!=set(FONTS):return []
    from pypdf.generic import NameObject,DecodedStreamObject
    evidence=[]
    for name in sorted(pending):
        font,cmap=pending[name];stream=DecodedStreamObject();stream.set_data(cmap)
        font[NameObject('/ToUnicode')]=stream;evidence.append(_evidence(name,cmap))
    return evidence

def valid_evidence(evidence,digest):
    if digest!=DOCUMENT_SHA256 or not isinstance(evidence,list)or len(evidence)!=2:return False
    names=[]
    fields={'policy','source_pdf_sha256','source_font','font_program_sha256','original_cmap_sha256','decoded_cmap_sha256','mappings'}
    for row in evidence:
        if not isinstance(row,dict)or set(row)!=fields:return False
        name=row.get('source_font')
        if name not in FONTS:return False
        program,cmap,_,mapping=FONTS[name]
        if (row['policy']!=POLICY or row['source_pdf_sha256']!=digest or row['font_program_sha256']!=program
                or row['original_cmap_sha256']!=cmap or row['mappings']!=[{'cid':c,'original_unicode_hex':o,'decoded_unicode_hex':n}for c,o,n in mapping]
                or row['decoded_cmap_sha256']!=DECODED_CMAPS[name]):return False
        names.append(name)
    return names==sorted(FONTS)
