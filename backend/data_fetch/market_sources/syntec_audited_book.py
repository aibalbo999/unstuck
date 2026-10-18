"""Position-bound 2022/2021 facts in Syntec's published audited consolidated book."""
from datetime import datetime
from hashlib import sha256
import math,re
from zoneinfo import ZoneInfo
from .official_xbrl_financial import FIELDS,FilingError
from syntec_annual_pdf_reader import extract_syntec_book,SELECTED
POLICY='syntec-audited-2022-book-native-positioned.v1'
LEGAL='新代科技股份有限公司'
MONEY=re.compile(r'\$?(?:\(\d{1,3}(?:,\d{3})*\)|\(\d+\)|\d{1,3}(?:,\d{3})*|\d+|-)\Z')
def _compact(s):return re.sub(r'\s+','',s)
def _bad(reason):raise FilingError('Syntec audited book '+reason)
def _rows(page):
    groups=[]
    for s in sorted(page['segments'],key=lambda x:(-x['y'],x['x'])):
        if not s['text'].strip():continue
        group=next((g for g in groups if abs(g['y']-s['y'])<=1.5),None)
        if group is None:group={'y':s['y'],'parts':[]};groups.append(group)
        group['parts'].append(s)
    for group in groups:
        spans=[]
        for s in sorted(group['parts'],key=lambda x:x['x']):
            if spans and s['x']-spans[-1]['end_x']<=max(1.5,min(s['font_height'],spans[-1]['font_height'])/2):
                spans[-1]['text']+=s['text'];spans[-1]['end_x']=s['end_x']
            else:spans.append({k:s[k]for k in ('text','x','end_x','font_height')})
        group.update(spans=spans,text=' '.join(s['text']for s in spans))
    return groups
def _amount(s):
    if not isinstance(s,str)or len(s)>25 or not MONEY.fullmatch(s):_bad('monetary value invalid')
    s=s.removeprefix('$')
    if s=='-':return 0  # An explicit monetary dash is the reported zero.
    n=int(s.strip('()').replace(',',''));return (-n if s.startswith('(')else n)*1000
def _numbers(row):return [v for s in row['spans']for v in s['text'].split()if MONEY.fullmatch(v)]
def _header(pages,page,labels):
    matches=[r for r in pages[page]['rows']if all(k in _compact(r['text'])for k in labels)]
    if len(matches)!=1:_bad('annual header not unique')
    row=matches[0];positions=[_compact(row['text']).index(k)for k in labels]
    if positions!=sorted(positions):_bad('physical annual column order invalid')
    return row
def _money_row(pages,headers,page,code,label,width,percent):
    matches=[r for r in pages[page]['rows']if _compact(r['text']).startswith(code+label)]
    if len(matches)!=1:_bad('required financial row missing or duplicated')
    row=matches[0];tokens=_numbers(row)
    if code.isdigit():
        if not tokens or tokens.pop(0)!=code:_bad('financial code alignment invalid')
    if len(tokens)!=width*(2 if percent else 1)or row['y']>=headers[page]['y']:_bad('financial columns invalid')
    amounts=[_amount(v)for v in tokens[::2]if percent]if percent else[_amount(v)for v in tokens]
    basis={'page':page,'code':code,'label':label,'y':row['y'],'original_row':row['text'],'monetary_cells':tokens,
           'header_y':headers[page]['y'],'header_original':headers[page]['text']}
    return amounts,basis
def parse_positioned_book(value):
    """Only consume the private reader's validated full selected native pages."""
    if (not isinstance(value,dict)or value.get('page_count')!=104 or value.get('selected_full_physical_pages')!=list(SELECTED)
            or value.get('coverage_status')!='selected_native_text_complete'or value.get('extraction_mode')!='native_show_operation_coordinates'
            or not isinstance(value.get('pages'),list)or len(value['pages'])!=len(SELECTED)):_bad('native extraction profile invalid')
    pages={p['page_number']:{**p,'rows':_rows(p)}for p in value['pages']}
    if set(pages)!=set(SELECTED):_bad('selected native pages invalid')
    text={n:_compact(p['text'])for n,p in pages.items()}
    if (LEGAL+'及子公司合併財務報表暨會計師查核報告民國一一一年度及民國一一○年度'not in text[1]
            or not all(k in text[4]for k in ('會計師查核報告','查核意見',LEGAL+'及其子公司民國一一一年十二月三十一日及民國一一○年','合併財務狀況','合併財務績效及合併現金流量'))
            or not all(k in text[6]for k in ('安永聯合會計師事務所','中華民國一一三年三月十八日'))):_bad('issuer audited consolidated period invalid')
    for n in (7,8,9,11):
        if LEGAL+'及子公司'not in text[n]or '單位：新台幣千元'not in text[n]:_bad('issuer or statement currency unit invalid')
    if '合併資產負債表'not in text[7]or '合併資產負債表'not in text[8]or '合併綜合損益表'not in text[9]or '合併現金流量表'not in text[11]:_bad('statement role invalid')
    headers={n:_header(pages,n,['一一一年十二月三十一日','一一○年十二月三十一日','一一○年一月一日']if n in(7,8)else['一一一年度','一一○年度'])for n in(7,8,9,11)}
    specs=[(7,'1xxx','資產總計',3,True,'Assets'),(8,'3xxx','權益總計',3,True,'EquityAttributableToOwnersOfParent'),
           (9,'4000','營業收入',2,True,'Revenue'),(9,'5900','營業毛利',2,True,'GrossProfit'),(9,'6900','營業利益',2,True,'ProfitLossFromOperatingActivities'),
           (11,'AAAA','營業活動之淨現金流入(出)',2,False,'CashFlowsFromUsedInOperatingActivities'),
           (11,'B02700','取得不動產、廠房及設備',2,False,'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'),
           (11,'B04500','取得無形資產',2,False,'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities')]
    facts={2022:{},2021:{}};basis=[]
    for n,code,label,width,percent,tag in specs:
        amounts,proof=_money_row(pages,headers,n,code,label,width,percent)
        if tag.startswith('PurchaseOf')and any(v>0 for v in amounts):_bad('purchase sign invalid')
        facts[2022][tag]=amounts[0];facts[2021][tag]=amounts[1];basis.append({**proof,'fact':tag,'values_TWD':amounts})
    # Parent equity must be the only declared equity group. Ordinary-holder
    # EPS cannot silently substitute for a preferred or noncontrolling scope.
    eq=pages[8]['rows'];owner=[r for r in eq if _compact(r['text'])=='歸屬於母公司業主之權益']
    if (len(owner)!=1 or len([r for r in eq if _compact(r['text'])=='3100股本'])!=1
            or any(k in text[8]for k in ('特別股','優先股','非控制權益'))):_bad('parent ordinary-only equity scope unverified')
    capital,capital_basis=_money_row(pages,headers,8,'3110','普通股股本',3,True)
    if any(v<=0 for v in capital)or owner[0]['y']<=basis[1]['y']:_bad('parent equity hierarchy invalid')
    if ('當年度歸屬於母公司普通股持有人之淨利'not in text[62]
            or '(金額除另予註明外，均以新台幣千元為單位)'not in text[63]):_bad('EPS parent numerator definition or unit unverified')
    numerators=[r for r in pages[63]['rows']if _compact(r['text']).startswith('本期淨利(千元)')]
    if len(numerators)!=2:_bad('EPS numerator rows invalid')
    eps=[]
    for ordinal,row in enumerate(sorted(numerators,key=lambda r:-r['y']),1):
        heads=[h for h in pages[63]['rows']if all(k in _compact(h['text'])for k in ('111年度','110年度'))and 0<h['y']-row['y']<70]
        if len(heads)!=1:_bad('EPS annual header invalid')
        h=heads[0];ht=_compact(h['text']);label=f'({ordinal})'+('基本每股盈餘'if ordinal==1 else'稀釋每股盈餘')
        if (ht.index('111年度')>=ht.index('110年度')or len([q for q in pages[63]['rows']if _compact(q['text'])==label and h['y']>q['y']>row['y']])!=1):_bad('EPS period or section alignment invalid')
        tokens=_numbers(row)
        if len(tokens)!=2:_bad('EPS monetary columns invalid')
        amounts=[_amount(v)for v in tokens];eps.append(amounts)
        basis.append({'page':63,'label':label+'母公司普通股持有人淨利','y':row['y'],'row_original':row['text'],'header_original':h['text'],'values_TWD':amounts})
    total,total_basis=_money_row(pages,headers,9,'8200','本期淨利',2,True)
    if eps[0]!=eps[1]or eps[0]!=total:_bad('parent EPS basic diluted or total crosscheck mismatch')
    facts[2022]['ProfitLossAttributableToOwnersOfParent']=eps[0][0];facts[2021]['ProfitLossAttributableToOwnersOfParent']=eps[0][1]
    if any(set(r)!=set(FIELDS)or any(type(v)is not int for v in r.values())for r in facts.values()):_bad('all nine annual facts incomplete')
    return {'facts':facts,'physical_fact_basis':basis,'ordinary_capital_basis':capital_basis,'parent_equity_heading_y':owner[0]['y'],
            'source_unit':'TWD_thousand','currency':'TWD','report_scope':'consolidated','unit_multiplier':1000,
            'parent_profit_basis':'explicit_EPS_parent_ordinary_holder_definition_and_numerator_in_declared_ordinary_only_parent_equity',
            'PL_total_crosscheck_only_not_parent_profit_substitution':True,'opening_balance_column_not_used_for_annual_history':True,
            'audited_on':'2024-03-18','selected_full_physical_pages':list(SELECTED),'whole_book_text_coverage_claimed':False,'policy':POLICY}
def parse_audited_book(raw,*,timeout_seconds=10):
    value=extract_syntec_book(raw,timeout_seconds=timeout_seconds)
    result=parse_positioned_book(value);result['complete_original_sha256']=sha256(raw).hexdigest()
    return result
