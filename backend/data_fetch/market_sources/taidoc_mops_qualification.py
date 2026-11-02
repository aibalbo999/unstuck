"""Exact historical TaiDoc original; image tables and unresolved glyphs stay partial."""
from hashlib import sha256

KNOWN_SHA = 'e489286a31501f333a8d40e0a7d81f38606a724a2c32650ebde68ddfa68b11de'
PAGE_TEXT_SHA256 = ('c422c5dca5655258a361d0fbf03bac2a90adff7da2686fbb135e936ff5e071b6', '3fd229d7ec1ad64eb8995a6a2383cb9b0742e59af4fad1b41f444ea33d1534e6', '56eb4af5111ec5d3d9df7836e98448341ee66168eab8a18626efae53bcb3d32b', '5e0073a669e62b52af1b4a5da1ce98d668b335f8292fa7dade32c96f0d783eae', '2aec6b57a2e506dd99198828608e898e4b964009c518c9ae9e269df128dfd61c', '28a913781242de3c9359e333ce5c4875e20b82ae0d3d23dae9b0fac8e409c8f2', '103c6e489f0536029f6c12f4a74b39e21c8aa4b28f010d135349dfbb2807c024', '93fdfa4ffc49bb9c0781deb5767d7c65bbc29af6175ac679951a48088872d487', '600727d0eb170d68e56d11aa44e185aed2eb875dda461821e4fd85eec571dc7b', '701ce3b64156a2c944f3e695ed1ad86c28262296464db2fcd3b41baa14aec3c6', '11589bec8e0174b7ec82d307669075cff07886df5f46e186697cde6681650027', '7b08b190f16fb16f051ede5234a8f74ee281434e9b47df32f0f76b12c95a0448', 'abad47cd963026e8fa6878a97400fb8a1ff8f038d124b74cab4a98d8cc295fd8', '4ae516e9f8c946a5f3cfc824c6deeeceabf8f2fa2e6d21c38cac8b2753c11bab', 'f1f491b6ce93febc183d4b01c3a266c38dbd4628ef25519a2c04f99c21407948', '0413dff3b8e56449119b10c630a038d792497c2123b74f42b564498d54e40b67', '5993ba5df982e4b7bc64e542167257345c23a5b2e8bc1aafe8fe91df9da02a0e', '12e34035093d2ca322b216c9697d66b955a36523191205c33d7aa3684d29f8e0', 'dff2e37b9f9a9b5528f9ce93e446ea8a93590b395236f2594e230b50bfbfadc1', 'd1da216f836cb002677221b0e462521167967a9c91bf07e9912ae08320e167c8', 'c3a135ec0a5cd8183cbe0e595f16a31b0634e364a01566f2c2b13ae89b620042', 'b9c350f65d45fe8784dd44fd82957a7d226fc4ab934c1338ffed707b03c30de7', 'f3d4a1cd2fed8b70cd94bb019958c0ff0d6a9ee76604c7eb401e05f0f9898265')
ROLE_PAGES = {3: (1, 3, 11), 5: (1, 3, 8, 9, 11), 12: (1, 3, 11)}
NOTE = '泰博2025年11月21日MOPS英文準備簡報，只作歷史材料，不代表當前營運、逐字稿或已核實會議發生。23頁原件完整保存，原生文字仍為partial；第14頁私用區項目符號及原文43/14頁碼均保留，不映射字形且整頁不進角色。第5–7頁財報主表是影像，原生文字只有標題，不由影像、視讀或OCR填入財務事實；本簡報不是完整查核財報。第5頁影像同列2025/3rd單季及2025/01/01–2025/09/30累計，金額新台幣百萬元但EPS為新台幣元；因未有合格原生表格，角色完全排除此頁。第8–9頁2024為全年比較，2025.01~09為一至九月累計占比，非Q3單季、完整2025年度或目前TTM；占比合計不等於100%，不自動補正、不推定誤差原因，也不推導絕對金額或成長率。第10頁歷年EPS/股利不是目前估值輸入，整頁排除。第11頁CGM明列In Clinical Trials，不能推定已核准、上市、形成訂單或收入；第16–18頁行銷敘述不供角色使用。第4頁歷史員工數與廣泛FDA/CE陳述不當當年度人力或個別產品許可。公司產品/通路/優勢陳述非獨立證實。角色3/12只用1/3/11頁；角色5另用8/9頁，全部完整頁保留聲明及試驗中資格。第22頁Q&A只是章節標題，沒有問答逐字稿。首次發布日未知，未驗證商業重用授權；展望不視為已實現成果。'


def _pages(pages):
    if (not isinstance(pages, list) or len(pages) != 23
            or any(not isinstance(p, dict) or type(p.get('page_number')) is not int
                   or p['page_number'] != n or not isinstance(p.get('text'), str)
                   or sha256(p['text'].encode()).hexdigest() != PAGE_TEXT_SHA256[n - 1]
                   for n, p in enumerate(pages, 1))):
        raise ValueError('TaiDoc whole-page qualification changed')


def qualify_native(raw, native, selected):
    expected = {'ticker': '4736.TW', 'symbol': '4736', 'company_name': '泰博',
                'event_date': '2025-11-21', 'event_end_date': '2025-11-21', 'event_time': '14:30',
                'material_file_date': '2025-11-21', 'filename': '473620251121E001.pdf',
                'format': 'pdf', 'language': 'en'}
    if (not isinstance(selected, dict) or not isinstance(native, dict)
            or any(selected.get(k) != v for k, v in expected.items())
            or not isinstance(raw, bytes) or sha256(raw).hexdigest() != KNOWN_SHA
            or native.get('content_sha256') != KNOWN_SHA or native.get('coverage_status') != 'partial'
            or type(native.get('page_count')) is not int or native['page_count'] != 23
            or native.get('empty_pages') != [] or native.get('garbled_pages') != [14]):
        raise ValueError('TaiDoc identity/period/format/native coverage unqualified')
    _pages(native.get('pages'))
    return '2025Q3'


def qualified_projection(pages):
    _pages(pages)
    used = {n for numbers in ROLE_PAGES.values() for n in numbers}
    return {'role_projection_policy': 'mops-qualified-whole-pages-v1',
            'role_page_allowlist': {str(role): list(numbers) for role, numbers in ROLE_PAGES.items()},
            'projection_excluded_pages': [n for n in range(1, 24) if n not in used]}
