"""A proven embedded program/CMap remains the same symbol under its real alias."""
from pathlib import Path
from io import BytesIO
from copy import deepcopy
import gzip,json
from hashlib import sha256
from source_pdf_reader import extract_pdf_pages
from source_pdf_symbols import normalize_verified_symbols,valid_symbol_evidence
ROOT=Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261017/mops-industrial-entries'


def original():
    return gzip.decompress((ROOT/'1301.TW.material.gz').read_bytes())


def font():
    from pypdf import PdfReader
    reader=PdfReader(BytesIO(original()),strict=True);found=[]
    for p in reader.pages:
        p.extract_text(visitor_text=lambda t,cm,tm,f,size:found.append(f)if f and '\uf06e'in t else None)
    return found[0]


def test_real_fpc_font_alias_recovers_bullets_without_changing_financial_text():
    raw=original();before=json.loads((ROOT/'1301.TW.native.json').read_text())
    result=extract_pdf_pages(raw)
    assert result['coverage_status']=='complete' and result['garbled_pages']==[]
    assert result['content_sha256']==sha256(raw).hexdigest()
    expected=[{**p,'text':p['text'].replace('\uf06e','■')}for p in before['pages']]
    assert result['pages']==expected
    evidence=result['symbol_mapping_evidence']
    assert sum(r['occurrences']for r in evidence)==6
    assert valid_symbol_evidence(evidence,result['pages'])


def test_alias_still_requires_exact_program_cmap_and_standalone_fragment():
    from pypdf.generic import DecodedStreamObject,NameObject
    f=font()
    assert normalize_verified_symbols('\uf06e123',[('\uf06e123',f)],2,{})==('\uf06e123',[])
    assert normalize_verified_symbols('\uf070',[('\uf070',f)],2,{})==('\uf070',[])
    for kind in ('program','cmap'):
        changed=deepcopy(f)
        if kind=='program':
            descriptor=changed['/DescendantFonts'][0].get_object()['/FontDescriptor'].get_object()
            stream=DecodedStreamObject();stream.set_data(b'changed')
            descriptor[NameObject('/FontFile2')]=stream
        else:
            stream=DecodedStreamObject();stream.set_data(b'changed')
            changed[NameObject('/ToUnicode')]=stream
        assert normalize_verified_symbols('\uf06e',[('\uf06e',changed)],2,{})==('\uf06e',[])
