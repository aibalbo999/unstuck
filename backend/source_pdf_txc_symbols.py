"""Three visually qualified markers from one exact embedded native font.

The complete TXC original's CID132/CID139 are filled four-corner square and
diamond outlines; CID57 is the check outline. No numeric glyph is decoded.
The raw PDF, all other characters, native ordering and whitespace remain.
"""
from hashlib import sha256
import re

POLICY='txc-native-square-diamond-check-v1'
PROGRAM_SHA256='662ad837d1e0ea80aba0ef145f0cd804f821c66c3a8c51402e7a2c697811995f'
CMAP_SHA256='9c4448b6e10b7a52f142190d2e1c934ba8c9ad7e19e4dec5e9a422040d6064bc'
FONT_NAME=re.compile(r'/[A-Z]{6}\+Wingdings-Regular')
MAPPING={'\uf06e':'\u25a0','\uf075':'\u25c6','\uf0fc':'\u2713'}
FIELDS={'policy','page_number','font_program_sha256','cmap_sha256','source_font',
        'source_character','replacement_character','occurrences'}

def _object(value):return value.get_object()if hasattr(value,'get_object')else value

def _verified_font(font):
    try:
        name=str(font.get('/BaseFont'))
        if not FONT_NAME.fullmatch(name)or font.get('/Type')!='/Font'or font.get('/Subtype')!='/Type0'or font.get('/Encoding')!='/Identity-H':return False
        children=_object(font.get('/DescendantFonts'))
        if not isinstance(children,list)or len(children)!=1:return False
        child=_object(children[0])
        if child.get('/Type')!='/Font'or child.get('/Subtype')!='/CIDFontType2'or child.get('/BaseFont')!=name or child.get('/CIDToGIDMap')!='/Identity':return False
        system=_object(child.get('/CIDSystemInfo'))
        if system.get('/Registry')!='Adobe'or system.get('/Ordering')!='Identity'or system.get('/Supplement')!=0 or isinstance(system.get('/Supplement'),bool):return False
        descriptor=_object(child.get('/FontDescriptor'))
        if descriptor.get('/FontName')!=name:return False
        cmap=_object(font.get('/ToUnicode')).get_data()
        if len(cmap)!=365 or sha256(cmap).hexdigest()!=CMAP_SHA256:return False
        program=_object(descriptor.get('/FontFile2')).get_data()
        return len(program)==29320 and sha256(program).hexdigest()==PROGRAM_SHA256
    except (AttributeError,KeyError,TypeError,ValueError,OverflowError):return False

def normalize_fragment(fragment,font,page_number,font_cache):
    source=fragment.strip()
    if font is None or source not in MAPPING:return fragment,[]
    key=('txc-native',id(font))
    if key not in font_cache:font_cache[key]=_verified_font(font)
    if not font_cache[key]:return fragment,[]
    target=MAPPING[source]
    return fragment.replace(source,target),[{'policy':POLICY,'page_number':page_number,
        'font_program_sha256':PROGRAM_SHA256,'cmap_sha256':CMAP_SHA256,
        'source_font':'Wingdings-Regular','source_character':f'U+{ord(source):04X}',
        'replacement_character':f'U+{ord(target):04X}','occurrences':1}]

def valid_evidence(evidence,pages):
    if not isinstance(evidence,list)or not evidence or len(evidence)>3*len(pages):return False
    seen=[]
    mapping={f'U+{ord(s):04X}':f'U+{ord(t):04X}'for s,t in MAPPING.items()}
    for row in evidence:
        if not isinstance(row,dict)or set(row)!=FIELDS:return False
        page,count=row['page_number'],row['occurrences'];source=row['source_character'];target=row['replacement_character']
        if (type(page)is not int or not 1<=page<=len(pages)or type(count)is not int or not 0<count
                or row['policy']!=POLICY or row['font_program_sha256']!=PROGRAM_SHA256
                or row['cmap_sha256']!=CMAP_SHA256 or row['source_font']!='Wingdings-Regular'
                or source not in mapping or target!=mapping[source]):return False
        if count>pages[page-1]['text'].count(chr(int(target[2:],16))):return False
        seen.append((page,source))
    return seen==sorted(set(seen))
