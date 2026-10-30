"""Recover one optional source through the existing audited provider service."""
from copy import deepcopy
from datetime import datetime, timezone
import math
import re
import time

from fastapi import HTTPException

from data_fetch import FetchRequest


def validate_refresh_source(source):
    if source not in (None, 'instrument_identity', 'financial_statements', 'annual_workforce', 'earnings_call', 'recent_catalysts', 'issuer_news', 'tdr_announcements', 'official_announcements', 'philjobnet_jobs', 'dynamic_peer_metrics', 'institutional_trading', 'alternative_data'):
        raise HTTPException(status_code=400, detail='不支援此指定來源刷新')


async def fetch_report_source_data(previous_snapshot, source, refresh_service):
    validate_refresh_source(source)
    ticker = str(previous_snapshot.get('ticker') or '').strip().upper()
    old_data = previous_snapshot.get('data')
    old_audits = previous_snapshot.get('source_audit')
    honhai_recovery = False
    peer_refresh_policy = None
    mops_material = False
    if source == 'earnings_call':
        from data_fetch.market_sources.mops_presentation import supports as supports_material
        mops_material = supports_material(ticker)
    if (not re.fullmatch(r'\d{4,6}\.TW(?:O)?', ticker)
            or not isinstance(old_data, dict) or old_data.get('ticker') != ticker
            or not isinstance(old_audits, list) or not old_audits
            or any(not isinstance(row, dict) for row in old_audits)):
        raise HTTPException(status_code=400, detail='原快照缺少可保留的資料或來源憑據')
    if source == 'tdr_announcements' and ticker != '9103.TW':
        raise HTTPException(status_code=400, detail='此公告入口尚未驗證此股票')
    if source == 'official_announcements':
        from official_announcement_source_refresh import supports as supports_ordinary
        if supports_ordinary(ticker):
            from official_announcement_source_refresh import validate_context as validate_json_context
        else:
            from data_fetch.market_sources.mops_json_company_history import validate_json_context
        try:
            validate_json_context(old_data, ticker)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail='此新版公告入口或股票身分尚未通過核對') from exc
    if source == 'philjobnet_jobs' and (ticker != '9103.TW'
            or ('alternative_data' in old_data and not isinstance(old_data['alternative_data'],dict))):
        raise HTTPException(status_code=400, detail='此雇主入口或原補充資料格式尚未通過核對')
    if source == 'financial_statements':
        from annual_financial_source_refresh import validate_annual_refresh_context
        validate_annual_refresh_context(old_data, ticker, old_audits)
    if source == 'alternative_data':
        from alternative_source_refresh import validate_alternative_refresh_context
        validate_alternative_refresh_context(old_data, ticker)
    if source == 'institutional_trading':
        from institutional_source_refresh import validate_institutional_refresh_context, institutional_refresh_session
        validate_institutional_refresh_context(old_data, ticker)
        institutional_refresh_session(ticker)
    if source == 'dynamic_peer_metrics':
        from peer_source_refresh import validate_peer_refresh_context
        peer_refresh_policy = validate_peer_refresh_context(old_data, ticker)
    if source == 'recent_catalysts':
        from recent_catalyst_source_refresh import validate_recent_refresh_context
        validate_recent_refresh_context(old_data, ticker)
    if source == 'issuer_news' and ticker == '5880.TW':
        from data_fetch.market_sources.tcfhc_issuer_news import validate_context as validate_tcfhc_news_context
        if not validate_tcfhc_news_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定合庫金控新聞須有一致的母公司身分；原快照保持')
    if source == 'issuer_news' and ticker == '2206.TW':
        from data_fetch.market_sources.sym_issuer_news import validate_context as validate_sym_news_context
        if not validate_sym_news_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定三陽新聞須有一致的股票與公司身分；原快照保持')
    if source == 'issuer_news' and ticker in {'2201.TW', '2464.TW', '2886.TW'}:
        from data_fetch.market_sources.registered_issuer_articles import validate_context
        if not validate_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='發行人原文入口須有一致的股票與公司身分；原快照保持')
    if source == 'issuer_news' and ticker in {'8069.TWO', '6669.TW', '2412.TW', '3443.TW', '2353.TW', '2360.TW', '3042.TW', '8150.TW', '2884.TW'}:
        from source_applicability import instrument_type
        if (instrument_type(old_data) != 'EQUITY'
                or old_data.get('instrument_type') not in (None, '', 'EQUITY')
                or ticker in {'2412.TW', '3443.TW', '2353.TW', '2360.TW', '3042.TW', '8150.TW', '2884.TW'} and any(old_data.get(key) not in (None, '', 'EQUITY')
                                             for key in ('quote_type', 'quoteType'))):
            raise HTTPException(status_code=400, detail='發行人原文入口須有一致的股票身分；原快照保持')
    if source == 'instrument_identity':
        from report_security_identity_refresh import validate_identity_refresh_context
        validate_identity_refresh_context(old_data, ticker, old_audits)
    if source == 'earnings_call' and ticker == '3042.TW':
        from data_fetch.market_sources.txc_conference import validate_context as validate_txc_context
        if not validate_txc_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定晶技簡報須有一致的台股股票身分；原快照保持')
    if mops_material:
        from data_fetch.market_sources.mops_presentation import validate_context as validate_material_context
        if not validate_material_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定 MOPS 簡報須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '4958.TW':
        from data_fetch.market_sources.zdt_conference import validate_context as validate_zdt_context
        if not validate_zdt_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定臻鼎簡報官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '3005.TW':
        from data_fetch.market_sources.getac_conference import validate_context as validate_getac_context
        if not validate_getac_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定神基簡報官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '1303.TW':
        from data_fetch.market_sources.npc_conference import validate_context as validate_npc_context
        if not validate_npc_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定南亞簡報官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '3023.TW':
        from data_fetch.market_sources.sinbon_conference import validate_context as validate_sinbon_context
        if not validate_sinbon_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定信邦公開申報簡報法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2881.TW':
        from data_fetch.market_sources.fubon_conference import validate_context as validate_fubon_context
        if not validate_fubon_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定富邦金公開申報簡報法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '6409.TW':
        from data_fetch.market_sources.voltronic_conference import validate_context as validate_voltronic_context
        if not validate_voltronic_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定旭隼公開申報簡報法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2337.TW':
        from data_fetch.market_sources.macronix_conference import validate_context as validate_macronix_context
        if not validate_macronix_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定旺宏簡報官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2321.TW':
        from data_fetch.market_sources.tecom_conference import validate_context as validate_tecom_context
        if not validate_tecom_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定東訊簡報官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '6924.TW':
        from data_fetch.market_sources.eikei_conference import validate_context as validate_eikei_context
        if not validate_eikei_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定榮惠簡報官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '8046.TW':
        from data_fetch.market_sources.nanyapcb_conference import validate_context as validate_nanyapcb_context
        if not validate_nanyapcb_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定南電簡報官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '3010.TW':
        from data_fetch.market_sources.wahlee_conference import validate_context as validate_wahlee_context
        if not validate_wahlee_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定華立簡報官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2360.TW':
        from data_fetch.market_sources.chroma_conference import validate_context as validate_chroma_context
        if not validate_chroma_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定致茂簡報官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2801.TW':
        from data_fetch.market_sources.chb_conference import validate_context as validate_chb_context
        if not validate_chb_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定彰銀問答官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '6861.TW':
        from data_fetch.market_sources.innocare_conference import validate_context as validate_innocare_context
        if not validate_innocare_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定睿生光電官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '1605.TW':
        from data_fetch.market_sources.walsin_conference import validate_context as validate_walsin_context
        if not validate_walsin_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定華新官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '1229.TW':
        from data_fetch.market_sources.lienhwa_conference import validate_context as validate_lienhwa_context
        if not validate_lienhwa_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定聯華官網法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2412.TW':
        from data_fetch.market_sources.cht_conference import validate_context as validate_cht_context
        if not validate_cht_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定中華電法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '1514.TW':
        from data_fetch.market_sources.allis_conference import validate_context as validate_allis_context
        if not validate_allis_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定亞力法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2368.TW':
        from data_fetch.market_sources.gce_conference import validate_context as validate_gce_context
        if not validate_gce_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定金像電法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2049.TW':
        from data_fetch.market_sources.hiwin_conference import validate_context as validate_hiwin_context
        if not validate_hiwin_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定上銀法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '1560.TW':
        from data_fetch.market_sources.kinik_conference import validate_context as validate_kinik_context
        if not validate_kinik_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定中砂法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2002.TW':
        from data_fetch.market_sources.csc_conference import validate_context as validate_csc_context
        if not validate_csc_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定中鋼法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2480.TW':
        from data_fetch.market_sources.sti_conference import validate_context as validate_sti_context
        if not validate_sti_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定敦陽科法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '6257.TW':
        from data_fetch.market_sources.sigurd_conference import validate_context as validate_sigurd_context
        if not validate_sigurd_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定矽格法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2344.TW':
        from data_fetch.market_sources.winbond_conference import validate_context as validate_winbond_context
        if not validate_winbond_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定華邦電法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '8150.TW':
        from data_fetch.market_sources.chipmos_conference import validate_context as validate_chipmos_context
        if not validate_chipmos_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定南茂法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2367.TW':
        from data_fetch.market_sources.unitech_conference import validate_context as validate_unitech_context
        if not validate_unitech_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定燿華法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '1623.TW':
        from data_fetch.market_sources.tewc_conference import validate_context as validate_tewc_context
        if not validate_tewc_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定大東電法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2308.TW':
        from data_fetch.market_sources.delta_conference import validate_context as validate_delta_context
        if not validate_delta_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定台達電逐字稿須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2855.TW':
        from data_fetch.market_sources.psc_conference import validate_context as validate_psc_context
        if not validate_psc_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定統一證券簡報須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '3653.TW':
        from data_fetch.market_sources.jentech_conference import validate_context as validate_jentech_context
        if not validate_jentech_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定健策法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2912.TW':
        from data_fetch.market_sources.pcsc_conference import validate_context as validate_pcsc_context
        if not validate_pcsc_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定統一超商法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '3443.TW':
        from data_fetch.market_sources.guc_conference import validate_context as validate_guc_context
        if not validate_guc_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定創意法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '1476.TW':
        from data_fetch.market_sources.eclat_conference import validate_context as validate_eclat_context
        if not validate_eclat_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定儒鴻法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '1503.TW':
        from data_fetch.market_sources.seec_conference import validate_context as validate_seec_context
        if not validate_seec_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定士電法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2059.TW':
        from data_fetch.market_sources.kingslide_conference import validate_context as validate_kingslide_context
        if not validate_kingslide_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定川湖法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '6189.TW':
        from data_fetch.market_sources.promate_conference import validate_context as validate_promate_context
        if not validate_promate_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定豐藝法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '3324.TWO':
        from data_fetch.market_sources.auras_conference import validate_context as validate_auras_context
        if not validate_auras_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定雙鴻法說須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '5880.TW':
        from data_fetch.market_sources.tcfhc_conference import validate_context as validate_tcfhc_context
        if not validate_tcfhc_context(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定合庫問答須有一致的股票身分；原快照保持')
    if source == 'earnings_call' and ticker == '2317.TW':
        from data_fetch.market_sources.honhai_conference import EVENT_DATE, validate_context as validate_honhai, validate_identity as validate_honhai_identity
        if not validate_honhai_identity(old_data, ticker):
            raise HTTPException(status_code=400, detail='指定鴻海法說資料須有一致的股票身分；原快照保持')
        call=old_data.get('earnings_call')
        honhai_recovery=isinstance(call,dict)and call.get('date')==EVENT_DATE
        if honhai_recovery and not validate_honhai(old_data,ticker):
            raise HTTPException(status_code=400, detail='指定鴻海逐字稿的原場次或股票身分不一致；原快照保持')
    # A custom full-payload fetcher is outside the source-only contract.
    if (not callable(getattr(refresh_service, 'fetch_source_async', None))
            or getattr(refresh_service, '_fetcher', None) is not None):
        raise HTTPException(status_code=503, detail='資料服務不支援指定來源刷新')
    if source in {'issuer_news','tdr_announcements','official_announcements'}:
        for key in ('recent_catalysts','additional_recent_catalysts','historical_catalysts',
                    'unverified_catalysts','identity_rejected_catalysts','source_record_archive'):
            if key in old_data and (not isinstance(old_data[key], list)
                    or any(not isinstance(row, dict) for row in old_data[key])):
                raise HTTPException(status_code=400, detail='原新聞或原件封存格式無法安全保留')
    # Existing successful core observations need their original acquisition
    # time; a newly generated snapshot must not freshen an undated old quote.
    for audit in old_audits:
        if (audit.get('source') not in {'market_data', 'financial_statements'}
                or audit.get('status') != 'success'):
            continue
        if _timestamp(audit) is None:
            raise HTTPException(status_code=400, detail='原核心資料取得時間缺漏、無效或互相矛盾')
    # Institutional caches already separate the expected session and cutoff
    # phase. Reuse valid all-market originals when repairing different reports.
    request = FetchRequest.from_ticker(ticker, force_refresh=source not in {'institutional_trading', 'alternative_data'} and peer_refresh_policy != 'ncc', record_provider_sla=True)
    try:
        if honhai_recovery:
            result = await refresh_service.fetch_source_async(request, source, context={'data':old_data,'source_only_recovery':True})
        elif mops_material or source in {'financial_statements', 'recent_catalysts', 'official_announcements', 'dynamic_peer_metrics', 'institutional_trading', 'alternative_data'} or source == 'earnings_call' and ticker in {'2855.TW', '5880.TW', '3324.TWO', '2308.TW', '1623.TW', '2367.TW', '8150.TW', '2344.TW', '6257.TW', '2480.TW', '2330.TW', '1229.TW', '2002.TW', '2412.TW', '1514.TW', '2368.TW', '2049.TW', '1560.TW', '3023.TW'} or source == 'issuer_news' and ticker in {'2201.TW', '5880.TW', '2206.TW'}:
            result = await refresh_service.fetch_source_async(request, source, context={'data': old_data})
        else:
            result = await refresh_service.fetch_source_async(request, source)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail='指定來源未取得合格資料；原快照保持') from exc
    payload = getattr(result, 'data', None)
    if not isinstance(payload, dict) or payload.get('ticker') != ticker:
        raise HTTPException(status_code=502, detail='指定來源股票身分不一致')
    canonical_source = 'recent_catalysts' if source in {'issuer_news','tdr_announcements','official_announcements'} else source
    if source in {'philjobnet_jobs', 'instrument_identity'}:
        canonical_source = 'alternative_data'
        if source == 'instrument_identity':
            canonical_source = 'taiwan_open_data'
    value, audits = payload.get(canonical_source), getattr(result, 'source_audit', None)
    if source == 'earnings_call' and ticker == '2317.TW':
        from data_fetch.market_sources.honhai_conference import verify_context as verify_honhai, is_marked as honhai_marked, PROVIDER as HONHAI_PROVIDER
        needs_honhai_verification=(honhai_recovery or honhai_marked(value)or isinstance(audits,list)and any(isinstance(a,dict)and a.get('provider')==HONHAI_PROVIDER for a in audits))
        try:
            verified = not needs_honhai_verification or verify_honhai(value, ticker, deadline=time.monotonic()+2.)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail='指定鴻海逐字稿原件核對未完成；原快照保持') from exc
        if not verified:
            raise HTTPException(status_code=502, detail='指定鴻海逐字稿原件與場次未通過核對；原快照保持')
    if source == 'earnings_call' and isinstance(value, dict):
        material_verified = False
        from data_fetch.market_sources.mops_presentation import PROVIDER as MATERIAL_PROVIDER, is_marked as material_marked, verify_context as verify_material
        if material_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == MATERIAL_PROVIDER for a in audits):
            material_audits = [a for a in (audits or []) if isinstance(a, dict) and a.get('provider') == MATERIAL_PROVIDER]
            failed = next((a for a in material_audits if a.get('status') not in {'success','skipped_fresh_cache'}), None)
            if failed is not None:
                reason = {'timeout':'來源逾時','rate_limited':'來源流量限制','access_denied':'來源拒絕存取'}.get(failed.get('error_kind'),'來源未取得可驗證內容')
                raise HTTPException(status_code=502, detail=f'指定 MOPS 簡報{reason}；原快照保持')
            try:
                verified = verify_material(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定 MOPS 簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定 MOPS 簡報的公司、場次或原件未通過核對；原快照保持')
            material_verified = True
        from data_fetch.market_sources.zdt_conference import PROVIDER as ZDT_PROVIDER, is_marked as zdt_marked, verify_context as verify_zdt
        if zdt_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == ZDT_PROVIDER for a in audits):
            try:
                verified = verify_zdt(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定臻鼎簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定臻鼎簡報的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.getac_conference import PROVIDER as GETAC_PROVIDER, is_marked as getac_marked, verify_context as verify_getac
        if getac_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == GETAC_PROVIDER for a in audits):
            try:
                verified = verify_getac(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定神基簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定神基簡報的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.npc_conference import PROVIDER as NPC_PROVIDER, is_marked as npc_marked, verify_context as verify_npc
        if npc_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == NPC_PROVIDER for a in audits):
            try:
                verified = verify_npc(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定南亞簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定南亞簡報的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.sinbon_conference import PROVIDER as SINBON_PROVIDER, is_marked as sinbon_marked, verify_context as verify_sinbon
        if sinbon_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == SINBON_PROVIDER for a in audits):
            try:
                verified = verify_sinbon(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定信邦簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定信邦簡報的公司、場次或原件未通過核對；原快照保持')
            # This separately replayed MOPS attachment shares its index URL
            # with Sigurd; the URL alone must not select a different issuer.
            material_verified = True
        from data_fetch.market_sources.fubon_conference import PROVIDER as FUBON_PROVIDER, is_marked as fubon_marked, verify_context as verify_fubon
        if fubon_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == FUBON_PROVIDER for a in audits):
            try:
                verified = verify_fubon(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定富邦金簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定富邦金簡報的公司、場次或原件未通過核對；原快照保持')
            # This separately replayed MOPS attachment shares its index URL
            # with Sigurd; the URL alone must not select a different issuer.
            material_verified = True
        from data_fetch.market_sources.voltronic_conference import PROVIDER as VOLTRONIC_PROVIDER, is_marked as voltronic_marked, verify_context as verify_voltronic
        if voltronic_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == VOLTRONIC_PROVIDER for a in audits):
            try:
                verified = verify_voltronic(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定旭隼簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定旭隼簡報的公司、場次或原件未通過核對；原快照保持')
            # This separately replayed MOPS attachment shares its index URL
            # with Sigurd; the URL alone must not select a different issuer.
            material_verified = True
        from data_fetch.market_sources.macronix_conference import PROVIDER as MACRONIX_PROVIDER, is_marked as macronix_marked, verify_context as verify_macronix
        if macronix_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == MACRONIX_PROVIDER for a in audits):
            try:
                verified = verify_macronix(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定旺宏簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定旺宏簡報的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.tecom_conference import PROVIDER as TECOM_PROVIDER, is_marked as tecom_marked, verify_context as verify_tecom
        if tecom_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == TECOM_PROVIDER for a in audits):
            try:
                verified = verify_tecom(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定東訊簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定東訊簡報的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.eikei_conference import PROVIDER as EIKEI_PROVIDER, is_marked as eikei_marked, verify_context as verify_eikei
        if eikei_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == EIKEI_PROVIDER for a in audits):
            try:
                verified = verify_eikei(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定榮惠簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定榮惠簡報的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.nanyapcb_conference import PROVIDER as NANYAPCB_PROVIDER, is_marked as nanyapcb_marked, verify_context as verify_nanyapcb
        if nanyapcb_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == NANYAPCB_PROVIDER for a in audits):
            try:
                verified = verify_nanyapcb(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定南電簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定南電簡報的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.wahlee_conference import PROVIDER as WAHLEE_PROVIDER, is_marked as wahlee_marked, verify_context as verify_wahlee
        if wahlee_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == WAHLEE_PROVIDER for a in audits):
            try:
                verified = verify_wahlee(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定華立簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定華立簡報的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.chroma_conference import PROVIDER as CHROMA_PROVIDER, is_marked as chroma_marked, verify_context as verify_chroma
        if chroma_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == CHROMA_PROVIDER for a in audits):
            try:
                verified = verify_chroma(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定致茂簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定致茂簡報的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.chb_conference import PROVIDER as CHB_PROVIDER, is_marked as chb_marked, verify_context as verify_chb
        if chb_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == CHB_PROVIDER for a in audits):
            try:
                verified = verify_chb(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定彰銀問答原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定彰銀問答的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.innocare_conference import PROVIDER as INNOCARE_PROVIDER, is_marked as innocare_marked, verify_context as verify_innocare
        if innocare_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == INNOCARE_PROVIDER for a in audits):
            try:
                verified = verify_innocare(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定睿生光電法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定睿生光電法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.walsin_conference import PROVIDER as WALSIN_PROVIDER, is_marked as walsin_marked, verify_context as verify_walsin
        if walsin_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == WALSIN_PROVIDER for a in audits):
            try:
                verified = verify_walsin(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定華新法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定華新法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.lienhwa_conference import PROVIDER as LIENHWA_PROVIDER, is_marked as lienhwa_marked, verify_context as verify_lienhwa
        if lienhwa_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == LIENHWA_PROVIDER for a in audits):
            try:
                verified = verify_lienhwa(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定聯華法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定聯華法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.cht_conference import PROVIDER as CHT_PROVIDER, is_marked as cht_marked, verify_context as verify_cht
        if cht_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == CHT_PROVIDER for a in audits):
            try:
                verified = verify_cht(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定中華電法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定中華電法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.allis_conference import PROVIDER as ALLIS_PROVIDER, is_marked as allis_marked, verify_context as verify_allis
        if allis_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == ALLIS_PROVIDER for a in audits):
            try:
                verified = verify_allis(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定亞力法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定亞力法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.gce_conference import PROVIDER as GCE_PROVIDER, is_marked as gce_marked, verify_context as verify_gce
        if gce_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == GCE_PROVIDER for a in audits):
            try:
                verified = verify_gce(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定金像電法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定金像電法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.hiwin_conference import PROVIDER as HIWIN_PROVIDER, is_marked as hiwin_marked, verify_context as verify_hiwin
        if hiwin_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == HIWIN_PROVIDER for a in audits):
            try:
                verified = verify_hiwin(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定上銀法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定上銀法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.kinik_conference import PROVIDER as KINIK_PROVIDER, is_marked as kinik_marked, verify_context as verify_kinik
        if kinik_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == KINIK_PROVIDER for a in audits):
            try:
                verified = verify_kinik(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定中砂法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定中砂法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.csc_conference import PROVIDER as CSC_PROVIDER, is_marked as csc_marked, verify_context as verify_csc
        if csc_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == CSC_PROVIDER for a in audits):
            try:
                verified = verify_csc(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定中鋼法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定中鋼法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.sti_conference import PROVIDER as STI_PROVIDER, is_marked as sti_marked, verify_context as verify_sti
        if sti_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == STI_PROVIDER for a in audits):
            try:
                verified = verify_sti(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定敦陽科法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定敦陽科法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.sigurd_conference import PROVIDER as SIGURD_PROVIDER, is_marked as sigurd_marked, verify_context as verify_sigurd
        # MOPS index URLs are shared by issuers; a fully replayed material
        # receipt identifies this row independently of the Sigurd URL marker.
        if (not material_verified and sigurd_marked(value)) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == SIGURD_PROVIDER for a in audits):
            try:
                verified = verify_sigurd(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定矽格法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定矽格法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.winbond_conference import PROVIDER as WINBOND_PROVIDER, is_marked as winbond_marked, verify_context as verify_winbond
        if winbond_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == WINBOND_PROVIDER for a in audits):
            try:
                verified = verify_winbond(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定華邦電法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定華邦電法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.chipmos_conference import PROVIDER as CHIPMOS_PROVIDER, is_marked as chipmos_marked, verify_context as verify_chipmos
        if chipmos_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == CHIPMOS_PROVIDER for a in audits):
            try:
                verified = verify_chipmos(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定南茂法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定南茂法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.unitech_conference import PROVIDER as UNITECH_PROVIDER, is_marked as unitech_marked, verify_context as verify_unitech
        if unitech_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == UNITECH_PROVIDER for a in audits):
            try:
                verified = verify_unitech(value, ticker, deadline=time.monotonic() + 2.)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定燿華法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定燿華法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.tewc_conference import PROVIDER as TEWC_PROVIDER, is_marked as tewc_marked, verify_context as verify_tewc
        if tewc_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == TEWC_PROVIDER for a in audits):
            try:
                verified = verify_tewc(value, ticker, deadline=time.monotonic() + 2.)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定大東電法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定大東電法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.delta_conference import PROVIDER as DELTA_PROVIDER, is_marked as delta_marked, verify_context as verify_delta
        if delta_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == DELTA_PROVIDER for a in audits):
            try:
                verified = verify_delta(value, ticker, deadline=time.monotonic() + 2.)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定台達逐字稿原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定台達逐字稿的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.jentech_conference import PROVIDER as JENTECH_PROVIDER, is_marked as jentech_marked, verify_context as verify_jentech
        if jentech_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == JENTECH_PROVIDER for a in audits):
            try:
                verified = verify_jentech(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定健策法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定健策法說公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.pcsc_conference import PROVIDER as PCSC_PROVIDER, is_marked as pcsc_marked, verify_context as verify_pcsc
        if pcsc_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == PCSC_PROVIDER for a in audits):
            try:
                verified = verify_pcsc(value, ticker, deadline=time.monotonic() + 10., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定統一超商法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定統一超商法說公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.guc_conference import PROVIDER as GUC_PROVIDER, is_marked as guc_marked, verify_context as verify_guc
        if guc_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == GUC_PROVIDER for a in audits):
            try:
                verified = verify_guc(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定創意法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定創意法說公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.eclat_conference import PROVIDER as ECLAT_PROVIDER, is_marked as eclat_marked, verify_context as verify_eclat
        if eclat_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == ECLAT_PROVIDER for a in audits):
            try:
                verified = verify_eclat(value, ticker, deadline=time.monotonic()+2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定儒鴻法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定儒鴻法說公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.seec_conference import PROVIDER as SEEC_PROVIDER, is_marked as seec_marked, verify_context as verify_seec
        if seec_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == SEEC_PROVIDER for a in audits):
            try:
                verified = verify_seec(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定士電法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定士電法說公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.kingslide_conference import PROVIDER as KINGSLIDE_PROVIDER, is_marked as kingslide_marked, verify_context as verify_kingslide
        if kingslide_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == KINGSLIDE_PROVIDER for a in audits):
            try:
                verified = verify_kingslide(value, ticker, deadline=time.monotonic() + 2., max_age=1800)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定川湖法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定川湖法說公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.promate_conference import PROVIDER as PROMATE_PROVIDER, is_marked as promate_marked, verify_context as verify_promate
        if promate_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == PROMATE_PROVIDER for a in audits):
            try:
                verified = verify_promate(value, ticker, deadline=time.monotonic() + 2.)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定豐藝法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定豐藝法說公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.auras_conference import PROVIDER as AURAS_PROVIDER, is_marked as auras_marked, verify_context as verify_auras
        if auras_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == AURAS_PROVIDER for a in audits):
            try:
                verified = verify_auras(value, ticker, deadline=time.monotonic() + 2.)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定雙鴻法說原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定雙鴻法說的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.tcfhc_conference import PROVIDER as TCFHC_PROVIDER, is_marked as tcfhc_marked, verify_context as verify_tcfhc
        if tcfhc_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == TCFHC_PROVIDER for a in audits):
            try:
                verified = verify_tcfhc(value, ticker, deadline=time.monotonic() + 2.)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定合庫問答原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定合庫問答的公司、場次或原件未通過核對；原快照保持')
        from data_fetch.market_sources.psc_conference import PROVIDER as PSC_PROVIDER, is_marked as psc_marked, verify_context as verify_psc
        if psc_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == PSC_PROVIDER for a in audits):
            try:
                verified = verify_psc(value, ticker, deadline=time.monotonic() + 2.)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定統一證券簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定統一證券簡報原件與來源身分未通過核對；原快照保持')
        from data_fetch.market_sources.txc_conference import PROVIDER as TXC_PROVIDER, is_marked as txc_marked, verify_context as verify_txc
        if txc_marked(value) or isinstance(audits, list) and any(isinstance(a, dict) and a.get('provider') == TXC_PROVIDER for a in audits):
            try:
                verified = verify_txc(value, ticker, deadline=time.monotonic() + 2.)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail='指定晶技簡報原件核對未完成；原快照保持') from exc
            if not verified:
                raise HTTPException(status_code=502, detail='指定晶技簡報原件與來源身分未通過核對；原快照保持')
        from data_fetch.market_sources.nanya_mops_presentation import is_marked as nanya_marked, verify_context as verify_nanya
        if nanya_marked(value, ticker) and not verify_nanya(value, ticker, deadline=time.monotonic() + 2.):
            raise HTTPException(status_code=502, detail='指定法說簡報的原件或公司身分未通過核對；原快照保持')
        from data_fetch.market_sources.uk_conference import PROVIDER as UK_PROVIDER, INDEX_URL as UK_URL, verify_context
        from data_fetch.market_sources.uk_conference_transport import presentation_url
        uk_documents = value.get('documents')
        uk_documents = uk_documents if isinstance(uk_documents, list) else []
        uk_marked = (value.get('source') == UK_PROVIDER or value.get('source_url') == UK_URL
                     or 'uk_conference_receipt' in value
                     or any(isinstance(doc, dict) and (doc.get('source') == UK_PROVIDER
                            or presentation_url(doc.get('url')))
                            for doc in uk_documents))
        if uk_marked and not verify_context(value, ticker, deadline=time.monotonic() + 2.):
            raise HTTPException(status_code=502, detail='指定法說簡報的原件或公司身分未通過核對；原快照保持')
    if source == 'instrument_identity':
        from report_security_identity_refresh import merge_security_identity
        return merge_security_identity(old_data, old_audits, value, audits, ticker)
    if source == 'financial_statements':
        from annual_financial_source_refresh import merge_annual_financial_source
        return merge_annual_financial_source(old_data, old_audits, value, audits, ticker)
    if source == 'annual_workforce':
        return _merge_annual_workforce(old_data, old_audits, value, audits, ticker)
    if source == 'institutional_trading':
        from institutional_source_refresh import merge_institutional_source
        return merge_institutional_source(old_data, old_audits, value, audits, ticker)
    if source == 'dynamic_peer_metrics':
        from peer_source_refresh import merge_peer_source
        return merge_peer_source(old_data, old_audits, value, audits, ticker)
    if source == 'recent_catalysts':
        from recent_catalyst_source_refresh import merge_recent_source
        return merge_recent_source(old_data, old_audits, value, audits, ticker)
    if source == 'alternative_data':
        from alternative_source_refresh import merge_alternative_source
        return merge_alternative_source(old_data, old_audits, value, audits, ticker)
    if source == 'philjobnet_jobs':
        return _merge_philjobnet(old_data,old_audits,value,audits,ticker)
    if source == 'issuer_news':
        return _merge_issuer_news(old_data, old_audits, value, audits, ticker)
    if source == 'tdr_announcements':
        return _merge_issuer_news(old_data, old_audits, value, audits, ticker, tdr=True)
    if source == 'official_announcements':
        from official_announcement_source_refresh import supports as supports_ordinary
        if supports_ordinary(ticker):
            from official_announcement_source_refresh import merge_source
            return merge_source(old_data, old_audits, value, audits, ticker)
        return _merge_issuer_news(old_data, old_audits, value, audits, ticker, ordinary=True)
    if (not isinstance(value, dict) or not value
            or str(value.get('ticker') or '').strip().upper() not in {ticker, ticker.split('.')[0]}
            or not isinstance(audits, list) or not audits
            or any(not isinstance(row, dict) or row.get('source') != source
                   or row.get('status') != 'success' or not row.get('fetch_id') for row in audits)):
        raise HTTPException(status_code=502, detail='指定來源憑據或公司身分未通過核對')
    merged = deepcopy(old_data)
    merged[source] = deepcopy(value)
    merged['source_audit'] = [deepcopy(row) for row in old_audits if row.get('source') != source] + deepcopy(audits)
    _reassess_original_freshness(merged, ticker, source, audits)
    return merged


def _merge_annual_workforce(old_data, old_audits, value, audits, ticker):
    from data_trust import source_record_count
    from data_trust import finalize_data_trust
    from data_fetch.annual_workforce_provider import PROVIDER as WORKFORCE_PROVIDER
    from data_fetch.annual_occupational_safety import (
        PROVIDER as SAFETY_PROVIDER, verified_occupational_safety_observation,
    )

    if (not isinstance(value, dict) or value.get('ticker') != ticker
            or source_record_count('annual_workforce', {'ticker': ticker, 'annual_workforce': value}) != 1
            or not isinstance(audits, list) or len(audits) != 2
            or any(not isinstance(row, dict) or not row.get('fetch_id') for row in audits)):
        raise HTTPException(status_code=502, detail='年度人力來源憑據或公司身分未通過核對；原快照保持')
    workforce_rows = [row for row in audits if row.get('source') == 'annual_workforce']
    safety_rows = [row for row in audits if row.get('source') == 'esg_occupational_safety']
    workforce_audit, = workforce_rows if len(workforce_rows) == 1 else (None,)
    safety_audit, = safety_rows if len(safety_rows) == 1 else (None,)
    safety_value = value.get('esg_occupational_safety')
    safety_count = source_record_count('esg_occupational_safety', {
        'ticker': ticker, 'annual_workforce': value,
    })
    if (workforce_audit is None or safety_audit is None
            or workforce_audit.get('provider') != WORKFORCE_PROVIDER
            or workforce_audit.get('status') != 'success'
            or type(workforce_audit.get('record_count')) is not int
            or workforce_audit.get('record_count') != 1
            or safety_audit.get('provider') != SAFETY_PROVIDER
            or safety_audit.get('status') not in {'success', 'degraded_enrichment', 'error', 'unavailable'}
            or type(safety_audit.get('record_count')) is not int
            or safety_audit.get('record_count') != safety_count
            or safety_count not in {0, 1}
            or safety_count and not verified_occupational_safety_observation(safety_value, ticker)
            or safety_value and not safety_count
            or workforce_audit.get('fetch_id') != safety_audit.get('fetch_id')):
        raise HTTPException(status_code=502, detail='年度人力或職安衛資料未通過品質核對；原快照保持')

    merged = deepcopy(old_data)
    merged_value = deepcopy(value)
    if safety_count == 0:
        previous_workforce = old_data.get('annual_workforce') if isinstance(old_data, dict) else None
        previous_safety = previous_workforce.get('esg_occupational_safety') if isinstance(previous_workforce, dict) else None
        if verified_occupational_safety_observation(previous_safety, ticker):
            previous_safety = deepcopy(previous_safety)
            previous_safety['status'] = 'stale'
            merged_value['esg_occupational_safety'] = previous_safety
            merged_value['coverage_status'] = 'partial'
            notes = merged_value.get('coverage_notes')
            notes = list(notes) if isinstance(notes, list) else []
            notes.append('本次職安衛刷新未取得有效資料；保留原觀察並標記為過期。')
            merged_value['coverage_notes'] = list(dict.fromkeys(notes))
    merged['annual_workforce'] = merged_value
    merged['source_audit'] = [deepcopy(row) for row in old_audits
                              if row.get('source') not in {'annual_workforce', 'esg_occupational_safety'}]
    merged['source_audit'].extend(deepcopy(audits))
    if safety_count:
        _reassess_original_freshness(merged, ticker, 'annual_workforce', [workforce_audit])
        _reassess_original_freshness(merged, ticker, 'esg_occupational_safety', [safety_audit])
    else:
        # A zero-record or failed safety fetch is evidence of an attempted
        # refresh, not a fresh occupational-safety observation. Keep any prior
        # source timestamp and exclude only this failure receipt while rebuilding
        # freshness; then restore it to the audit trail unchanged.
        merged['source_audit'] = [row for row in merged['source_audit']
                                  if row.get('source') != 'esg_occupational_safety']
        _reassess_original_freshness(merged, ticker, 'annual_workforce', [workforce_audit])
        merged['source_audit'].append(deepcopy(safety_audit))
        finalize_data_trust(merged)
    return merged


def _merge_philjobnet(old_data, old_audits, value, audits, ticker):
    from data_fetch.market_sources.philjobnet_medtecs import PROVIDER, NOTE, verified_philjobnet_observation
    observation = value.get('job_openings_philjobnet') if isinstance(value,dict) else None
    if (not verified_philjobnet_observation(observation,old_data,require_fresh=True)
            or not isinstance(audits,list) or len(audits) != 1
            or audits[0].get('source') != 'alternative_data' or audits[0].get('provider') != PROVIDER
            or audits[0].get('status') != 'success' or not audits[0].get('fetch_id')
            or type(audits[0].get('record_count')) is not int or audits[0]['record_count'] != 1
            or _timestamp(audits[0]) != observation['fetched_at_epoch']):
        raise HTTPException(status_code=502,detail='指定雇主元件原件、身分或憑據未通過核對；原快照保持')
    merged = deepcopy(old_data)
    alternative = merged.setdefault('alternative_data',{})
    # Retain unknown 104/1111 values and every original failure audit.
    alternative['job_openings_philjobnet'] = deepcopy(observation)
    notes = alternative.get('coverage_notes',[])
    if not isinstance(notes,list) or any(not isinstance(x,str) for x in notes):
        raise HTTPException(status_code=400,detail='原補充來源限制說明無法安全保留')
    alternative['coverage_notes'] = [*notes] if NOTE in notes else [*notes,NOTE]
    alternative['philjobnet_coverage_status'] = observation['coverage_status']
    merged['source_audit'] = deepcopy(old_audits)+deepcopy(audits)
    _reassess_original_freshness(merged,ticker,'alternative_data',audits)
    return merged


def _merge_issuer_news(old_data, old_audits, value, audits, ticker, *, tdr=False, ordinary=False):
    from source_content_selection import select_company_records
    from data_fetch.market_sources.issuer_news import verified_issuer_news
    from news_freshness_policy import apply_news_freshness
    from news_record_utils import canonical_link
    if tdr:
        from data_fetch.market_sources.tdr_mops_history import verified_tdr_record, announcement_link_identity
    if ordinary:
        from data_fetch.market_sources.mops_json_company_history import verified_json_record, announcement_link_identity
    provider = 'TWSE company announcement history' if tdr or ordinary else 'Verified issuer news'

    sym_bundle = False
    if ticker == '2206.TW' and not tdr and not ordinary:
        from data_fetch.market_sources.sanyang_news_bundle import POLICY, guard_bundle
        from data_fetch.market_sources.sym_issuer_news import is_marked
        if (isinstance(audits, list) and any(isinstance(row, dict) and
                (row.get('selection_policy') == POLICY or row.get('parser_version') == POLICY
                 or any(key in row for key in ('component_audits', 'component_records', 'record_bindings', 'bundle_error_kind')))
                for row in audits)
                or isinstance(value, list) and any(is_marked(row) for row in value)):
            if not isinstance(audits, list) or len(audits) != 1 or not guard_bundle(value, audits[0], old_data):
                raise HTTPException(status_code=502, detail='三陽新聞元件與原文憑據未通過核對')
            sym_bundle = True

    if (not isinstance(value, list) or not 1 <= len(value) <= (64 if ordinary else 10 if tdr else 5)
            or any(not isinstance(row, dict) for row in value)
            or not isinstance(audits, list) or not audits
            or any(not _usable_issuer_audit(row, len(value), provider=provider, allow_partial=tdr or ordinary or sym_bundle) for row in audits)):
        raise HTTPException(status_code=502, detail='指定新聞元件未取得合格原文或憑據')
    context = {k: deepcopy(old_data[k]) for k in ('ticker','company_name','company_identity','instrument_type','quote_type','quoteType') if k in old_data}
    cutoff = time.time()
    accepted, _ = select_company_records(value, context, cutoff=cutoff)
    verifier = verified_json_record if ordinary else verified_tdr_record if tdr else verified_issuer_news
    if len(accepted) != len(value) or any(not verifier(row, context) for row in accepted):
        raise HTTPException(status_code=502, detail='指定新聞元件的公司、日期或轉載歸屬未通過核對')
    buckets = ('recent_catalysts','additional_recent_catalysts','historical_catalysts','unverified_catalysts','identity_rejected_catalysts')
    previous = [row for key in buckets for row in (old_data.get(key) or []) if isinstance(row, dict)]
    merged = deepcopy(old_data)
    def link_identity(row):
        return (announcement_link_identity(row) if tdr or ordinary else None) or canonical_link(row.get('link') or row.get('url'))
    incoming_links = {link_identity(row) for row in accepted}
    incoming_titles = {str(row.get('title') or '').strip().casefold() for row in accepted} if tdr or ordinary else set()
    archive = deepcopy(merged.get('source_record_archive') or [])
    for row in previous:
        title_duplicate = ((tdr or ordinary) and str(row.get('title') or '').strip().casefold() in incoming_titles
                           and (not ordinary or not verified_json_record(row, context)))
        if link_identity(row) in incoming_links or title_duplicate:
            entry = {'source':'recent_catalysts','reason':'duplicate_mops_json_original' if ordinary else 'duplicate_tdr_original' if tdr else 'duplicate_issuer_republication','record':deepcopy(row)}
            if entry not in archive:
                archive.append(entry)
    if archive:
        merged['source_record_archive'] = archive
    # Only this news projection is reselected. The generic news helper also
    # reselects social samples, so never call it on the entire saved payload.
    apply_news_freshness(context, records=[*accepted,*previous], cutoff=cutoff)
    for key in (*buckets,'news_selection'):
        merged[key] = deepcopy(context[key])
    merged['source_audit'] = [deepcopy(row) for row in old_audits
                            if not (row.get('source') == 'recent_catalysts' and row.get('provider') == provider)] + deepcopy(audits)
    _reassess_original_freshness(merged, ticker, 'recent_catalysts', audits)
    return merged


def _usable_issuer_audit(row, count, *, provider='Verified issuer news', allow_partial=False):
    if (not isinstance(row, dict) or row.get('source') != 'recent_catalysts'
            or row.get('provider') != provider or not row.get('fetch_id')):
        return False
    if allow_partial and (type(row.get('record_count')) is not int or row['record_count'] != count):
        return False
    if row.get('status') == 'success':
        return True
    if allow_partial and row.get('status') == 'degraded_enrichment':
        return True
    if row.get('status') != 'skipped_fresh_cache':
        return False
    try:
        return (row.get('cache_hit') is True and row.get('stale') is False
                and row.get('http_request_sent') is False and type(row.get('http_request_count')) is int
                and row['http_request_count'] == 0 and row.get('event_kind') == 'cache_hit'
                and type(row.get('record_count')) is int and row['record_count'] == count
                and _timestamp(row) is not None)
    except (OverflowError, ValueError, TypeError):
        return False


def _timestamp(entry: dict) -> float | None:
    value = entry.get('fetched_at_epoch')
    if value is not None:
        if type(value) not in (int, float):
            return None
        try:
            value = float(value)
        except (ValueError, TypeError, OverflowError):
            return None
        if not math.isfinite(value):
            return None
    iso_stamp = None
    if entry.get('fetched_at') is not None:
        try:
            parsed = datetime.fromisoformat(entry['fetched_at'])
            if parsed.tzinfo is None:
                return None
            iso_stamp = parsed.timestamp()
        except (ValueError, TypeError, OverflowError):
            return None
    if value is None:
        value = iso_stamp
    elif iso_stamp is not None and (type(value) not in (int, float)
            or not math.isfinite(value) or abs(value - iso_stamp) >= 1):
        # Epoch and second-resolution ISO representations must refer to the
        # same original observation. Neither may conceal an older timestamp.
        return None
    return float(value) if type(value) in (int, float) and math.isfinite(value) and 0 < value <= time.time() else None


def _reassess_original_freshness(data: dict, ticker: str, source: str, audits: list[dict]) -> None:
    from data_freshness import build_source_freshness, build_source_freshness_entry, build_data_freshness, source_timestamp_epoch
    from data_freshness_policy import SOURCE_FRESHNESS_SOURCES
    from data_trust import finalize_data_trust

    original = data.get('source_freshness') if isinstance(data.get('source_freshness'), dict) else {}
    retained = {name: deepcopy(entry) for name, entry in original.items()
                if name != source and isinstance(entry, dict)}
    if source != 'twse_official' and 'twse_official' in original and 'twse_official' not in retained:
        # An explicit unknown/invalid entry is not a missing observation.
        retained['twse_official'] = {}
    # Missing saved derived timestamps may use the original audit timestamp,
    # never this optional refresh time or a shared cache generation time.
    for entry in data['source_audit']:
        name = entry.get('source')
        if name != source and name in SOURCE_FRESHNESS_SOURCES and name not in retained:
            retained[name] = deepcopy(entry)
        elif name in {'market_data', 'financial_statements'} and name in retained:
            stamp, audit_stamp = _timestamp(retained[name]), _timestamp(entry)
            if stamp is not None and audit_stamp is not None and audit_stamp < stamp:
                # Workflow-level freshness can be stamped after the provider
                # finishes. Use the earlier original core observation without
                # changing either saved audit or the original market fields.
                retained[name].update(fetched_at_epoch=audit_stamp,
                    fetched_at=datetime.fromtimestamp(audit_stamp, timezone.utc).isoformat())
    refreshed_stamp = _timestamp(audits[-1])
    if refreshed_stamp is None:
        raise HTTPException(status_code=502, detail='指定來源缺少可核對的原取得時間')
    retained[source] = deepcopy(audits[-1])
    now = time.time()

    def retained_stamp(name, entry):
        if name == 'twse_official':
            return source_timestamp_epoch({'source_freshness': {name: entry}}, name, now_epoch=now)
        return _timestamp(entry)

    data['source_freshness'] = {
        name: {'fetched_at_epoch': retained_stamp(name, entry)} for name, entry in retained.items()
    }
    rebuilt = build_source_freshness(data, ticker, cache_hit=False, now_epoch=now)
    for name, entry in retained.items():
        if name in rebuilt and rebuilt[name].get('status') != 'not_applicable':
            rebuilt[name] = build_source_freshness_entry(name, ticker, retained_stamp(name, entry),
                cache_hit=entry.get('cache_hit') is True, now_epoch=now, source_data=data.get(name))
    data['source_freshness'] = rebuilt
    market = rebuilt.get('market_data', {})
    data['data_freshness'] = build_data_freshness(ticker, market.get('fetched_at_epoch'),
        cache_hit=market.get('cache_hit') is True, now_epoch=now)
    finalize_data_trust(data)
