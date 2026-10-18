"""Adopt only exact native, embedded and standalone nonnumeric symbols."""
from pathlib import Path
import gzip,json
from copy import deepcopy
import pytest
from source_pdf_reader import extract_pdf_pages,SourcePdfError,_validate_result
from source_pdf_symbols import normalize_verified_symbols,valid_symbol_evidence

F=Path(__file__).parent/'fixtures/source_acquisition'
def original():return gzip.decompress((F/'txc3042_conference219_complete_20260910.pdf.gz').read_bytes())
def test_complete_original_native_text_is_recovered_with_three_exact_markers_only():
    raw=original();result=extract_pdf_pages(raw)
    assert result['page_count']==15 and result['garbled_pages']==[] and result['coverage_status']=='complete'
    original_pages=json.loads(gzip.decompress((F/'txc3042_conference219_original_pages_20261012.json.gz').read_bytes()))
    assert result['pages']==[{**p,'text':p['text'].replace('\uf06e','■').replace('\uf075','◆').replace('\uf0fc','✓')}for p in original_pages['pages']]
    assert result['pages'][1]['text'].count('■')==3 and result['pages'][12]['text'].count('◆')==4 and result['pages'][12]['text'].count('✓')==11
    assert result['content_sha256']==__import__('hashlib').sha256(raw).hexdigest()
    assert valid_symbol_evidence(result['symbol_mapping_evidence'],result['pages'])

@pytest.fixture
def font():
    from io import BytesIO
    from pypdf import PdfReader
    r=PdfReader(BytesIO(original()),strict=True);found=[]
    r.pages[1].extract_text(visitor_text=lambda text,ctm,tm,f,size:found.append(f)if '\uf06e'in text else None)
    assert found;return found[0]

@pytest.mark.parametrize('text',['\uf06e123','A\uf075','\uf0fc\uf0fc','unknown\uf099','\uf06e1,078M'])
def test_mixed_numeric_text_or_unknown_symbol_is_not_changed(font,text):
    out,evidence=normalize_verified_symbols(text,[(text,font)],2,{})
    assert out==text and not evidence

def test_exact_standalone_fragments_preserve_every_other_character(font):
    fragments=[('before 1,078M ',None),(' \uf06e ',font),('2026 135M ',None),('\uf075',font),(' body ',None),('\uf0fc',font)]
    text=''.join(t for t,f in fragments);out,evidence=normalize_verified_symbols(text,fragments,13,{})
    assert out==text.replace('\uf06e','■').replace('\uf075','◆').replace('\uf0fc','✓')
    assert len(evidence)==3 and valid_symbol_evidence(evidence,[{'page_number':n,'text':out if n==13 else 'other'}for n in range(1,16)])

@pytest.mark.parametrize('change',['wrong_name','wrong_program','wrong_cmap','nonidentity_GID','invalid_CID_system'])
def test_font_label_without_exact_embedded_proof_cannot_decode(font,change):
    from pypdf.generic import NameObject,TextStringObject,DecodedStreamObject
    f=deepcopy(font);child=f['/DescendantFonts'][0].get_object()
    if change=='wrong_name':f[NameObject('/BaseFont')]=NameObject('/ABCDEF+Other')
    elif change in {'wrong_program','wrong_cmap'}:
        stream=DecodedStreamObject();stream.set_data(b'changed')
        if change=='wrong_program':child['/FontDescriptor'][NameObject('/FontFile2')]=stream
        else:f[NameObject('/ToUnicode')]=stream
    elif change=='nonidentity_GID':child[NameObject('/CIDToGIDMap')]=NameObject('/Wrong')
    else:child['/CIDSystemInfo'][NameObject('/Ordering')]=TextStringObject('Wrong')
    out,evidence=normalize_verified_symbols('\uf06e',[('\uf06e',f)],2,{})
    assert out=='\uf06e' and not evidence

def test_source_fragments_must_reconstruct_the_exact_page(font):
    assert normalize_verified_symbols('\uf06e',[('changed',font)],2,{})==('\uf06e',[])

@pytest.mark.parametrize('field',['program','cmap','policy','target','count','page','duplicate'])
def test_saved_symbol_evidence_tampering_is_refused(field):
    value=extract_pdf_pages(original());row=value['symbol_mapping_evidence'][0]
    if field=='program':row['font_program_sha256']='0'*64
    elif field=='cmap':row['cmap_sha256']='0'*64
    elif field=='policy':row['policy']='unknown'
    elif field=='target':row['replacement_character']='U+0030'
    elif field=='count':row['occurrences']=True
    elif field=='page':row['page_number']=True
    else:value['symbol_mapping_evidence'].append(deepcopy(row))
    with pytest.raises(SourcePdfError):_validate_result(value,value['content_sha256'])
