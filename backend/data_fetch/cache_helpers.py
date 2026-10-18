"""Cache write helpers for data-fetch payloads."""

from __future__ import annotations

import time as time_module
from datetime import datetime, timezone

from cache_store import set_cache_json
from config import FINANCIAL_DATA_PAYLOAD_CACHE_TTL_SECONDS
from data_trust import build_data_trust

from .audit_helpers import _build_data_freshness, _build_source_freshness, _cache_timestamp_epoch


def _contains_allis_no_store(data):
    """Private report evidence must not become a reusable HTTP result payload."""
    pending, seen = [data], set()
    while pending:
        value = pending.pop()
        if not isinstance(value, (dict, list, tuple)) or id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, dict):
            if ('jentech_conference_receipt' in value
                    or value.get('source') == 'Jentech official conference presentation'
                    or value.get('projection_policy') == 'jentech-presentation-role-v1'
                    or isinstance(value.get('url'),str) and (value['url'].startswith('https://www.jentech.com.tw/zh/_files/ugd/') or value['url'].startswith('https://5d4fbe70-bf03-4c9c-9b1d-5e632fda0f7f.filesusr.com/ugd/'))
                    or 'pcsc_conference_receipt' in value
                    or value.get('source') == 'PCSC official conference presentation'
                    or value.get('projection_policy') == 'pcsc-presentation-role-v2'
                    or isinstance(value.get('url'),str) and value['url'].startswith('https://ir.7-11.com.tw/taiwan/2912/events/')
                    or 'allis_conference_receipt' in value or 'allis_glyph_evidence' in value
                    or 'gce_conference_receipt' in value or 'gce_glyph_evidence' in value
                    or value.get('source') == 'GCE official conference presentation'
                    or value.get('projection_policy') == 'gce-presentation-role-v1'
                    or value.get('url') == 'https://www.gce.com.tw/file/%E6%B3%95%E8%AA%AA%E6%9C%8320260828%E8%8B%B1%E6%96%87%E7%89%88.pdf'
                    or 'hiwin_conference_receipt' in value or 'hiwin_glyph_evidence' in value
                    or value.get('source') == 'HIWIN official conference presentation'
                    or value.get('projection_policy') == 'hiwin-presentation-role-v1'
                    or value.get('url') == 'https://www.hiwin.tw/uploadfiles/file/conference/20260508_final_E.pdf'
                    or 'zdt_conference_receipt' in value
                    or value.get('source') == 'ZDT official conference presentation'
                    or value.get('projection_policy') == 'zdt-presentation-role-v1'
                    or value.get('url') == 'https://www.zdtco.com/public/download/upload2026_10_052202610051657040600z5S6a1pdf'
                    or 'getac_conference_receipt' in value
                    or value.get('source') == 'Getac official conference presentation'
                    or value.get('projection_policy') == 'getac-presentation-role-v1'
                    or value.get('url') == 'https://en.getacgroup.com/upload/document_investor_calendar_list_files/a595874cfc02bb78ae85a5d21150c0b0.pdf'
                    or 'npc_conference_receipt' in value
                    or value.get('source') == 'NPC official conference presentation'
                    or value.get('projection_policy') == 'npc-presentation-role-v1'
                    or value.get('url') == 'https://www.npc.com.tw/npcfile/public/report/premat/20261012171625560.pdf'
                    or 'sinbon_conference_receipt' in value
                    or value.get('source') == 'Sinbon published conference presentation'
                    or value.get('projection_policy') == 'sinbon-presentation-role-v1'
                    or (value.get('url') == 'https://mopsov.twse.com.tw/server-java/FileDownLoad' and value.get('filename') == '302320260909E001.pdf')
                    or 'fubon_conference_receipt' in value
                    or value.get('source') == 'Fubon published conference presentation'
                    or value.get('projection_policy') == 'fubon-presentation-role-v1'
                    or (value.get('url') == 'https://mopsov.twse.com.tw/server-java/FileDownLoad' and value.get('filename') == '288120260902E001.pdf')
                    or 'voltronic_conference_receipt' in value
                    or value.get('source') == 'Voltronic published conference presentation'
                    or value.get('projection_policy') == 'voltronic-presentation-role-v1'
                    or (value.get('url') == 'https://mopsov.twse.com.tw/server-java/FileDownLoad' and value.get('filename') == '640920260910E001.pdf')
                    or 'macronix_conference_receipt' in value
                    or value.get('source') == 'Macronix official conference presentation'
                    or value.get('projection_policy') in {'macronix-presentation-role-v1','macronix-presentation-role-v2'}
                    or isinstance(value.get('url'), str) and value['url'].startswith('https://www.macronix.com/Lists/QuarterlyResults/Attachments/')
                    or 'tecom_conference_receipt' in value
                    or value.get('source') == 'Tecom official conference presentation'
                    or value.get('projection_policy') == 'tecom-presentation-role-v1'
                    or value.get('url') == 'https://www.tecom.com.tw/wp-content/uploads/2026/01/%E6%9D%B1%E8%A8%8A_2025%E6%B3%95%E8%AA%AA%E6%9C%83%E8%B3%87%E6%96%99.pdf'
                    or 'eikei_conference_receipt' in value
                    or value.get('source') == 'Eikei official conference presentation'
                    or value.get('projection_policy') == 'eikei-presentation-role-v1'
                    or value.get('url') == 'https://www.ei-kei.com/themes/rainlab-bonjour-child/assets/20260820_Investor_Conference_zh.pdf'
                    or 'nanyapcb_conference_receipt' in value
                    or value.get('source') == 'NanyaPCB official conference presentation'
                    or value.get('projection_policy') == 'nanyapcb-presentation-role-v1'
                    or value.get('url') == 'https://www.nanyapcb.com.tw/nypcb/images/InvestorRelations/FinancialReport/NYPCBCH20260506.pdf'
                    or 'wahlee_conference_receipt' in value
                    or value.get('source') == 'Wahlee official conference presentation'
                    or value.get('projection_policy') == 'wahlee-presentation-role-v1'
                    or value.get('url') == 'https://www.wahlee.com/Files/FinancialPresentation/%E8%8F%AF%E7%AB%8B%E4%B8%AD%E8%8B%B1%E6%96%87%E6%B3%95%E8%AA%AA2026_8%E6%9C%88(%E8%B2%A1%E5%A0%B12026%E5%B9%B46%E6%9C%88_%E7%87%9F%E6%94%B62026%E5%B9%B47%E6%9C%88)v.CN.pdf'
                    or 'chroma_conference_receipt' in value
                    or value.get('source') == 'Chroma official conference presentation'
                    or value.get('projection_policy') == 'chroma-presentation-role-v1'
                    or value.get('url') == 'https://www.chromaate.com/downloads/investors/pdf/quarterly_reports/2026/20260730_Q2_quarterly_reports_presentation_tc.pdf'
                    or 'chb_qa_receipt' in value
                    or value.get('source') == 'CHB official investor QA summary'
                    or value.get('projection_policy') == 'chb-qa-role-v1'
                    or value.get('url') == 'https://www.bankchb.com/chb_2a_resource/leap_do/recording/1790671904915/2026Q2%E6%8A%95%E8%B3%87%E4%BA%BA%E6%8F%90%E5%95%8F%E9%87%8D%E9%BB%9E%E5%BD%99%E6%95%B4.pdf'
                    or 'innocare_conference_receipt' in value
                    or value.get('source') == 'InnoCare official conference presentation'
                    or value.get('projection_policy') == 'innocare-presentation-role-v1'
                    or value.get('url') == 'https://www.innocare-x.com/wp-content/uploads/2026/09/20260910142650_0_e8f3ed.pdf'
                    or 'walsin_conference_receipt' in value
                    or value.get('source') == 'Walsin official conference presentation'
                    or value.get('projection_policy') == 'walsin-presentation-role-v1'
                    or value.get('url') == 'https://www.walsin.com/wp-content/uploads/2026/08/%E3%80%90PBA%E3%80%912026Q2-%E6%B3%95%E8%AA%AA%E6%9C%83%E5%A0%B1%E5%91%8A%E6%AA%94_EN.pdf'
                    or 'lienhwa_conference_receipt' in value or 'lienhwa_glyph_evidence' in value
                    or value.get('source') == 'Lien Hwa official conference presentation'
                    or value.get('projection_policy') == 'lienhwa-presentation-role-v1'
                    or value.get('url') == 'https://www.lhicholdings.com/investors/3newsFile/Investor-Conference-dw-2026Q2_1/'
                    or 'kinik_conference_receipt' in value or 'kinik_glyph_evidence' in value
                    or value.get('source') == 'KINIK official conference presentation'
                    or value.get('projection_policy') == 'kinik-presentation-role-v1'
                    or value.get('url') == 'https://www.kinik.com.tw/upload/Investors/Conference/2026Q2%20KINIK%20%E4%B8%AD%E7%A0%82%E5%85%AC%E5%8F%B8%E6%B3%95%E8%AA%AA%E6%9C%83.pdf'
                    or value.get('source') == 'Allis official conference presentation'
                    or value.get('projection_policy') == 'allis-presentation-role-v1'
                    or value.get('url') == 'https://www.allis.com.tw/zh-tw/download/file/42604'):
                return True
            pending.extend(value.values())
        else:
            pending.extend(value)
    return False


def _cache_financial_data(data: dict, original_ticker: str):
    if not data or "error" in data:
        return
    if _contains_allis_no_store(data):
        return

    cacheable = dict(data)
    cacheable.pop("_cache_hit", None)
    resolved_ticker = cacheable.get("ticker", original_ticker)
    now_epoch = time_module.time()
    market_epoch = _cache_timestamp_epoch(cacheable) or now_epoch
    cacheable["cache_generated_at_epoch"] = now_epoch
    cacheable["cache_generated_at"] = datetime.fromtimestamp(now_epoch, timezone.utc).isoformat()
    cacheable["data_freshness"] = _build_data_freshness(
        str(resolved_ticker or original_ticker),
        market_epoch,
        cache_hit=False,
        now_epoch=now_epoch,
    )
    cacheable["source_freshness"] = _build_source_freshness(
        cacheable,
        str(resolved_ticker or original_ticker),
        cache_hit=False,
        now_epoch=now_epoch,
    )
    cacheable["data_trust"] = build_data_trust(cacheable)
    set_cache_json(f"financial_data:{original_ticker}", cacheable, FINANCIAL_DATA_PAYLOAD_CACHE_TTL_SECONDS)
    if resolved_ticker != original_ticker:
        set_cache_json(f"financial_data:{resolved_ticker}", cacheable, FINANCIAL_DATA_PAYLOAD_CACHE_TTL_SECONDS)
