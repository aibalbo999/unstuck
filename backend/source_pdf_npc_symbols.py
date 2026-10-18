"""Exact embedded bullet mappings qualified from complete NPC/PCB/FPC originals.

Only standalone symbols are decoded. Program+CMap+CID identity bind the
qualified profiles; numeric characters, unknown fonts and raw PDF bytes stay intact.
"""
from hashlib import sha256
import re
from source_pdf_txc_symbols import FIELDS

PROFILES = ({'policy': 'nanyapcb-native-square-v1', 'font': 'Wingdings', 'program_bytes': 29116, 'program_sha256': 'ad699482de3b3a7aeebf7550eccc3d01d7f5a9c565560b26b5c29deeb1327ed4', 'cmap_bytes': 337, 'cmap_sha256': 'a72b13422dcdb7859b0aecf68e41a698a006dca27b962a55536e5b0f907926a4', 'mapping': {'\uf06e': '■'}}, {'policy': 'npc-native-square-v1', 'font': 'Wingdings-Regular', 'program_bytes': 6147, 'program_sha256': '52eed74dee11b1b6f44040a1fd7640b701b2581d325402e89136b180aeea8bd0', 'cmap_bytes': 338, 'cmap_sha256': '9d114188767913cf159c59c35d7788b06ee2f9a7b90849be9ff7d6f805c72cea', 'mapping': {'\uf06e': '■'}}, {'policy': 'npc-native-square-diamond-v1', 'font': 'Wingdings-Regular', 'program_bytes': 6207, 'program_sha256': '8ff46dab152fa665d934faf621dd7b04bb504c39e7edc1bb883030e93239bc8c', 'cmap_bytes': 352, 'cmap_sha256': '2a4e92219c192e0dbf76e2b73cf74e043a5dc825969fd23047a4b4f09bfe7df6', 'mapping': {'\uf06e': '■', '\uf075': '◆'}})
# FPC's complete original uses the identical Nanya PCB program and CMap;
# only the published BaseFont alias differs. This does not admit other bytes.
PROFILES += ({**PROFILES[0], 'policy':'fpc-native-square-alias-v1',
              'font':'Wingdings-Regular'},)
POLICIES=frozenset(p['policy']for p in PROFILES)
MAPPING={'\uf06e':'\u25a0','\uf075':'\u25c6'}

def _object(value):return value.get_object()if hasattr(value,'get_object')else value

def _verified_profile(font):
    try:
        name=str(font.get('/BaseFont'))
        if font.get('/Type')!='/Font'or font.get('/Subtype')!='/Type0'or font.get('/Encoding')!='/Identity-H':return None
        children=_object(font.get('/DescendantFonts'))
        if not isinstance(children,list)or len(children)!=1:return None
        child=_object(children[0])
        if child.get('/Type')!='/Font'or child.get('/Subtype')!='/CIDFontType2'or child.get('/BaseFont')!=name or child.get('/CIDToGIDMap')!='/Identity':return None
        system=_object(child.get('/CIDSystemInfo'))
        if system.get('/Registry')!='Adobe'or system.get('/Ordering')!='Identity'or system.get('/Supplement')!=0 or isinstance(system.get('/Supplement'),bool):return None
        descriptor=_object(child.get('/FontDescriptor'))
        if descriptor.get('/FontName')!=name:return None
        cmap=_object(font.get('/ToUnicode')).get_data()
        matches=[p for p in PROFILES if re.fullmatch(r'/[A-Z]{6}\+'+re.escape(p['font']),name)
                 and len(cmap)==p['cmap_bytes']and sha256(cmap).hexdigest()==p['cmap_sha256']]
        if len(matches)!=1:return None
        profile=matches[0];program=_object(descriptor.get('/FontFile2')).get_data()
        return profile if len(program)==profile['program_bytes']and sha256(program).hexdigest()==profile['program_sha256']else None
    except (AttributeError,KeyError,TypeError,ValueError,OverflowError):return None

def normalize_fragment(fragment,font,page_number,font_cache):
    source=fragment.strip()
    if font is None or source not in MAPPING:return fragment,[]
    key=('npc-pcb-native',id(font))
    if key not in font_cache:font_cache[key]=_verified_profile(font)
    profile=font_cache[key]
    if not profile or source not in profile['mapping']:return fragment,[]
    target=profile['mapping'][source]
    return fragment.replace(source,target),[{'policy':profile['policy'],'page_number':page_number,
        'font_program_sha256':profile['program_sha256'],'cmap_sha256':profile['cmap_sha256'],
        'source_font':profile['font'],'source_character':f'U+{ord(source):04X}',
        'replacement_character':f'U+{ord(target):04X}','occurrences':1}]

def valid_evidence(evidence,pages):
    if not isinstance(evidence,list)or not evidence or len(evidence)>4*len(pages):return False
    seen=[];totals={};by={p['policy']:p for p in PROFILES}
    for row in evidence:
        if not isinstance(row,dict)or set(row)!=FIELDS:return False
        page,count=row['page_number'],row['occurrences'];policy=row['policy']
        if not isinstance(policy,str)or policy not in by:return False
        p=by[policy];mapping={f'U+{ord(s):04X}':f'U+{ord(t):04X}'for s,t in p['mapping'].items()}
        source,target=row['source_character'],row['replacement_character']
        if (type(page)is not int or not 1<=page<=len(pages)or type(count)is not int or count<=0
                or row['font_program_sha256']!=p['program_sha256']or row['cmap_sha256']!=p['cmap_sha256']
                or row['source_font']!=p['font']or not isinstance(source,str)or mapping.get(source)!=target):return False
        key=(page,target);totals[key]=totals.get(key,0)+count
        if totals[key]>pages[page-1]['text'].count(chr(int(target[2:],16))):return False
        seen.append((page,policy,source))
    return seen==sorted(set(seen))
