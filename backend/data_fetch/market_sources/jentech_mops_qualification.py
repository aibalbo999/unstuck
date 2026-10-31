"""Exact whole-page qualification for independently published Jentech MOPS PDF.

This is a distinct English original, not a byte bridge from the issuer's Chinese
PDF. All24 pages and partial/garbled state remain; only7 reviewed whole pages
enter roles. The generic document reader and all other issuers stay unchanged.
"""
from hashlib import sha256

KNOWN_SHA = 'd4af5ffc92ac562b7008fdef792c3a91c248526ef8528a057b038f52a6e394d8'
PAGE_TEXT_SHA256 = ('ed7310445f5873292fdc52fc0fb10bacaa7ffcdae13597634e9db2b4174566b6', 'e9a4a1413fa58dcb41e3cc4b0d93ad616508e5ccf0c88453012add37fb6dbc9c', 'a29f2c9605a53f727c737586b14d3295e307c10d3bd85ed264ffbf090c8089e4', '551cce53d681b85f2e14e07635c1f72ac2b8d02db9793054f65e2bc42385d87c', '039ca5a630138ac2887c81f8e887d9e3b5d3ee9547fbea9145124a7979956fcd', 'ff433e241c77725dfe522bb8ed3072c10bf25a07b3d685172b50b9a0df7fe7c5', 'd9ef0ddb6f2aeaddf2156bf18f3d5805e7907464d3f3be5480f62a7d2544e8a5', '933cc236aff6111a98bed53ee1f4ee7bede787f72152eff428a8b333bc775c32', 'dbb5ff3e4c45017aac41d67562f0da330c3cf9896d7704f695b4e4b7872c6fc6', 'c467b857d6ec9ea7a87f1fe6b86548eb60e2957d77187fe2f5c19b09ad56bb3d', 'd511d55fdad57234ed15116c04b6d0f8ce9f91dd226779b56635c587918f7085', 'dae4acdead28ccbab964450ad63886d88ac1779f8fab198fcc51bafbdfd1c1f1', '53e1a4a96d20427dc42ad9fb7070d3cf388d5d3acead65b0bfb5869e669e1aec', '9c68ff32083e2908f5d5ca4849e3417a01ca73405e5e7f78c6250aa52a937bcd', '979abee453468cb31c585bd17868c63d4a3f53f2c13cdeb68d855703e8935dd3', 'f01b31ea24f8fe76be8dab55427d522fa8d29e518f241a77a5f2a111d04b339c', '202833c8560346cde705f7eaf76c5f4f31248180915125046eccefad5ee2aa86', 'ec56742e9c08f53cd5e4ab6b77407e76f2b67e694eea764e2a700df15b74899f', '77b63c5d798a7ccfb3e8730cd6322fee362bb2c2ee698ef4379cb71a0131d673', 'e6ad197c3a96d869c257152b90fe3ca571184a74c697375c424b3f17d912f893', '0802e4d434874f36420c5e7f01fadff6e49ac815f7afbb60279ef6fb79417f10', '4a4a04587a504f7bd8ab7c7e2831e0c29aa8a4219a6a46801542adcf31164977', '9773aa4db4bee54585166c063aaf0186e123fcd80f37686c139846616487a00a', 'd9e8ed55a7bcb7352995b3aa37bf3679c15965de8a8f5be68e6be8b42e317ea0')
ROLE_PAGES = (1, 5, 6, 7, 8, 11, 21)
GARBLED_PAGES = (2,3,4,14,15,16,17)
NOTE = '健策2025年11月28日MOPS英文準備簡報，非逐字稿，亦非已核驗事件發生紀錄；只限歷史材料，不代表目前營運。原件24頁完整保留，原生文字仍為partial；第2、3、4、14–17頁亂碼保留且不作角色輸入，不映射私用區字形。僅第1、5、6、7、8、11、21整頁供角色使用；其他圖表與閱讀順序未完整綁定，整頁排除。第2頁聲明財務數字含未經查核及核閱資料，預測為公司當時估計且未承諾更新；不得當成經查核年報或當前已實現結果。第5–8頁廠房面積為m²，土地與廠房面積分開，37,488+保持加號；Q1 2026／Q1 2027是文件當時預計完工，未核實實際完工或新增產能。第11頁僅公司產品應用陳述，不證明訂單、營收或市佔。第21頁2024Q1–2025Q3各欄為單季；金額為NT$千元，Basic EPS例外為NT$，不得年化或推算目前TTM／本益比／目標價。原件Confidential及禁止未經許可複製、散布或編輯聲明保留；未驗證商業重用授權。'


def _pages(pages):
    if (not isinstance(pages,list) or len(pages)!=24
            or any(not isinstance(p,dict) or type(p.get('page_number')) is not int
                   or p['page_number']!=n or not isinstance(p.get('text'),str)
                   or sha256(p['text'].encode()).hexdigest()!=PAGE_TEXT_SHA256[n-1]
                   for n,p in enumerate(pages,1))):
        raise ValueError('Jentech English whole-page qualification changed')


def qualify_native(raw,native,selected):
    expected={'ticker':'3653.TW','symbol':'3653','company_name':'健策',
              'event_date':'2025-11-28','event_end_date':'2025-11-28',
              'event_time':'15:30','material_file_date':'2025-11-28',
              'filename':'365320251128E001.pdf','format':'pdf','language':'en'}
    if (not isinstance(selected,dict) or not isinstance(native,dict)
            or any(selected.get(k)!=v for k,v in expected.items())
            or not isinstance(raw,bytes) or sha256(raw).hexdigest()!=KNOWN_SHA
            or native.get('content_sha256')!=KNOWN_SHA
            or native.get('coverage_status')!='partial'
            or type(native.get('page_count')) is not int or native['page_count']!=24
            or native.get('empty_pages')!=[] or native.get('garbled_pages')!=list(GARBLED_PAGES)):
        raise ValueError('Jentech MOPS identity/period/format/native coverage unqualified')
    _pages(native.get('pages'))
    return '2025Q3'


def qualified_projection(pages):
    _pages(pages)
    return {'role_projection_policy':'mops-qualified-whole-pages-v1',
            'role_page_allowlist':{str(role):list(ROLE_PAGES) for role in (3,5,12)},
            'projection_excluded_pages':[n for n in range(1,25) if n not in ROLE_PAGES]}
