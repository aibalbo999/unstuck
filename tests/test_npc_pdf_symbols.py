"""Recover only native standalone bullets from three verified embedded fonts."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import pytest
from source_pdf_reader import extract_pdf_pages, _validate_result, SourcePdfError
from source_pdf_symbols import normalize_verified_symbols, valid_symbol_evidence

D=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261015'
FOLDERS={'8046':'nanya8046-new-originals','1303':'nanya1303-conference-originals'}
def original(company):return (D/FOLDERS[company]/'conference.body').read_bytes()

@pytest.mark.parametrize('company,count,pages', [('8046',37,14),('1303',27,15)])
def test_complete_original_recovers_only_demonstrated_bullets(company,count,pages):
    raw=original(company);result=extract_pdf_pages(raw)
    assert result['coverage_status']=='complete' and result['garbled_pages']==[]
    before=json.loads((D/FOLDERS[company]/'conference-native-text.json').read_text())
    expected=[{**p,'text':p['text'].replace('\uf06e','■').replace('\uf075','◆')}for p in before['pages']]
    assert result['pages']==expected and result['page_count']==pages
    assert result['content_sha256']==sha256(raw).hexdigest()
    evidence=result['symbol_mapping_evidence']
    assert sum(r['occurrences']for r in evidence)==count
    assert valid_symbol_evidence(evidence,result['pages'])

@pytest.fixture(params=[('8046','/ABCDEE+Wingdings'),('1303','/VEPZIC+Wingdings-Regular'),('1303','/GPOHTC+Wingdings-Regular')])
def font(request):
    from pypdf import PdfReader
    company,name=request.param;reader=PdfReader(BytesIO(original(company)),strict=True);found=[]
    for page in reader.pages:
        page.extract_text(visitor_text=lambda text,ctm,tm,f,size:found.append(f)if f and f.get('/BaseFont')==name and '\uf06e'in text else None)
    assert found
    return found[0]

@pytest.mark.parametrize('text',['\uf06e123','A\uf075','\uf06e\uf06e','\uf099','\uf06e1,078M','\uf0fc'])
def test_mixed_unknown_or_unqualified_character_is_unchanged(font,text):
    assert normalize_verified_symbols(text,[(text,font)],3,{})==(text,[])

def test_exact_fragment_preserves_numbers_order_and_whitespace(font):
    fragments=[('2026 1,078M ',None),(' \uf06e\n',font),(' 135M ',None)]
    text=''.join(t for t,f in fragments);out,evidence=normalize_verified_symbols(text,fragments,3,{})
    assert out==text.replace('\uf06e','■') and len(evidence)==1
    assert valid_symbol_evidence(evidence,[{'page_number':n,'text':out if n==3 else 'text'}for n in range(1,4)])

@pytest.mark.parametrize('change',['name','program','cmap','CID','GID','descriptor','missing'])
def test_font_identity_needs_all_original_evidence(font,change):
    from pypdf.generic import NameObject,TextStringObject,DecodedStreamObject
    f=deepcopy(font);child=f['/DescendantFonts'][0].get_object()
    if change=='name':f[NameObject('/BaseFont')]=NameObject('/ABCDEF+Other')
    elif change in {'program','cmap'}:
        stream=DecodedStreamObject();stream.set_data(b'changed')
        if change=='program':child['/FontDescriptor'][NameObject('/FontFile2')]=stream
        else:f[NameObject('/ToUnicode')]=stream
    elif change=='CID':child['/CIDSystemInfo'][NameObject('/Ordering')]=TextStringObject('Other')
    elif change=='GID':child[NameObject('/CIDToGIDMap')]=NameObject('/Wrong')
    elif change=='descriptor':child['/FontDescriptor'][NameObject('/FontName')]=NameObject('/ABCDEF+Other')
    else:f=None
    assert normalize_verified_symbols('\uf06e',[('\uf06e',f)],3,{})==('\uf06e',[])

def test_fragments_must_reconstruct_exact_page(font):
    assert normalize_verified_symbols('\uf06e',[('changed',font)],3,{})==('\uf06e',[])

@pytest.mark.parametrize('change',['program','cmap','policy','target','count','page','duplicate'])
def test_saved_symbol_evidence_tampering_is_rejected(change):
    value=extract_pdf_pages(original('1303'));row=value['symbol_mapping_evidence'][0]
    if change=='program':row['font_program_sha256']='0'*64
    elif change=='cmap':row['cmap_sha256']='0'*64
    elif change=='policy':row['policy']='unknown'
    elif change=='target':row['replacement_character']='U+0030'
    elif change=='count':row['occurrences']=True
    elif change=='page':row['page_number']=True
    else:value['symbol_mapping_evidence'].append(deepcopy(row))
    with pytest.raises(SourcePdfError):_validate_result(value,value['content_sha256'])
