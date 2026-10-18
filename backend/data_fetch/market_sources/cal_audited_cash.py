"""Three exact English consolidated books supplement one missing cash fact."""
from hashlib import sha256
import re
from cal_annual_pdf_reader import extract_cal_book,SELECTED,PAGE_COUNTS
from .syntec_audited_book import _rows,_amount,_compact
from .official_xbrl_financial import FilingError

POLICY='cal-audited-cash-native-annual-columns.v1'
LABELS={'CashFlowsFromUsedInOperatingActivities':'Net cash generated from operating activities',
        'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities':'Payments for property, plant and equipment',
        'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities':'Increase in other intangible assets'}
DATES={2022:'March 9, 2023',2024:'March 10, 2025',2025:'March 11, 2026'}
def _bad(reason):raise FilingError('China Airlines audited cash '+reason)
def parse_positioned_book(value,year):
    if (type(year)is not int or year not in PAGE_COUNTS or not isinstance(value,dict)
            or value.get('page_count')!=PAGE_COUNTS[year]or value.get('selected_full_physical_pages')!=list(SELECTED)
            or value.get('extraction_mode')!='native_show_operation_coordinates'or value.get('coverage_status')!='selected_native_text_complete'):_bad('profile invalid')
    pages={p['page_number']:{**p,'rows':_rows(p)} for p in value['pages']}
    if len(value['pages'])!=len(SELECTED)or set(pages)!=set(SELECTED):_bad('selected pages invalid')
    text={n:_compact(p['text'])for n,p in pages.items()}
    if (_compact(f'China Airlines, Ltd. and Subsidiaries Consolidated Financial Statements for the Years Ended December 31, {year} and {year-1} and Independent Auditors’ Report')not in text[1]
            or not all(_compact(k)in text[3]for k in ['INDEPENDENT AUDITORS’ REPORT','We have audited','China Airlines, Ltd.',f'December 31, {year} and {year-1}','consolidated cash flows'])
            or not all(_compact(k)in text[6]for k in ['Deloitte & Touche',DATES[year],'translated into English from the original Chinese','the Chinese-language independent auditors’ report and consolidated financial statements shall prevail.'])):_bad('audited issuer period or translation basis invalid')
    heads={}
    for n in(11,12,13):
        if not all(_compact(k)in text[n]for k in ['CHINA AIRLINES, LTD. AND SUBSIDIARIES','CONSOLIDATED STATEMENTS OF CASH FLOWS',f'FOR THE YEARS ENDED DECEMBER 31, {year} AND {year-1}','(In Thousands of New Taiwan Dollars)']):_bad('cash scope year or unit invalid')
        matches=[r for r in pages[n]['rows']if _compact(r['text'])==str(year)+str(year-1)]
        if len(matches)!=1:_bad('annual cash header not unique')
        h=matches[0];spans=h['spans']
        if len(spans)!=2 or [_compact(s['text'])for s in spans]!=[str(year),str(year-1)]or spans[0]['end_x']>=spans[1]['x']:_bad('cash year positions invalid')
        heads[n]=h
    facts={year:{},year-1:{}};proof=[]
    for tag,original_label in LABELS.items():
        label='Payments for other intangible assets'if year==2022 and tag.startswith('PurchaseOfIntangible')else original_label
        hits=[(n,r)for n in(11,12,13)for r in pages[n]['rows']if _compact(r['text']).startswith(_compact(label))]
        if len(hits)!=1:_bad('cash row missing or duplicated')
        n,row=hits[0];h=heads[n];columns=h['spans'];split=(columns[0]['end_x']+columns[1]['x'])/2
        # Labels are left of both monetary columns. Reject any extra field,
        # crossing cell or swapped physical column rather than infer order.
        parts=row['spans'];labels=[s for s in parts if s['end_x']<columns[0]['x']-15]
        cells=[s for s in parts if s not in labels]
        if (_compact(' '.join(s['text']for s in labels))!=_compact(label)or len(cells)!=2
                or not row['y']<h['y'] or not columns[0]['x']-45<=cells[0]['x']<=cells[0]['end_x']<split
                or not split<cells[1]['x']<=cells[1]['end_x']<=columns[1]['end_x']+45):_bad('cash monetary columns invalid')
        tokens=[_compact(s['text'])for s in cells];amounts=[_amount(s)for s in tokens]
        if tag.startswith('PurchaseOf')and any(a>0 for a in amounts):_bad('cash purchase sign invalid')
        facts[year][tag]=amounts[0];facts[year-1][tag]=amounts[1]
        proof.append({'fact':tag,'label':label,'page':n,'original_row':row['text'],'y':row['y'],
                      'header_original':h['text'],'header_y':h['y'],'monetary_cells':tokens,'values_TWD':amounts})
    return {'facts':facts,'physical_fact_basis':proof,'source_unit':'TWD_thousand','unit_multiplier':1000,
            'currency':'TWD','report_scope':'consolidated','source_language':'en','Chinese_original_prevails':True,
            'auditor_report_date':DATES[year],'policy':POLICY,'selected_full_physical_pages':list(SELECTED),'whole_book_text_coverage_claimed':False}

def parse_book(raw,year,*,timeout_seconds=10):
    result=parse_positioned_book(extract_cal_book(raw,year,timeout_seconds=timeout_seconds),year)
    return {**result,'complete_original_sha256':sha256(raw).hexdigest()}
