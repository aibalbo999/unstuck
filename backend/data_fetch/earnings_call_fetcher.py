"""Optional earnings-call data fetchers."""

from __future__ import annotations

import os
import re
import time
from datetime import date, datetime
from typing import Any

from config import FMP_API_KEY, FMP_BASE_URL
from external_http_client import log_http_warning, sync_json_get


FMP_LEGACY_TRANSCRIPT_URL = "https://financialmodelingprep.com/api/v3/earning_call_transcript"
FREE_EARNINGS_CALL_PROVIDER_NAME = "MOPS investor conference"
FREE_EARNINGS_CALL_COVERAGE_NOTE = "MOPS/TWSE 免費來源提供法說會資訊、簡報或影音連結；未提供完整逐字稿。"
DEFAULT_FMP_TRANSCRIPT_RESTRICTED_COOLDOWN_SECONDS = 6 * 60 * 60
FMP_TRANSCRIPT_RESTRICTED_STATUS_CODES = {401, 402, 403}
_sync_json_get = sync_json_get
_fmp_transcript_cooldown_until = 0.0


def fetch_free_earnings_call_context(ticker: str, *, diagnostics: dict | None = None,
                                    use_cache: bool = True, force_refresh: bool = False,
                                    source_context: dict | None = None) -> dict:
    """Prefer verified issuer content; retain the existing index fallback."""
    from .market_sources.taiwanmobile_conference import supports as supports_twm, fetch_context as fetch_twm
    if supports_twm(ticker):
        return fetch_twm(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from company_conference_content import fetch_company_conference, supports_company, AGGREGATE_MESSAGE
    from official_cathay_conference import fetch_cathay_conference_context, supports_cathay
    from search_provider_runtime import SourceResponseError

    diagnostics = diagnostics if diagnostics is not None else {}
    index_options = ({'force_refresh':True} if force_refresh else {})
    if not use_cache:index_options['use_cache']=False
    from .market_sources.jentech_conference import (
        supports_jentech, fetch_jentech_context, PROVIDER as JENTECH_PROVIDER,
    )
    if supports_jentech(ticker):
        from .market_sources.mops_presentation import supports as supports_material, fetch_presentation_context
        if supports_material('3653.TW'):
            # Independently published and qualified government original, not a
            # retry after the issuer host's timeout or admission block.
            return fetch_presentation_context('3653.TW', diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
        jentech_details = {}
        primary_error = None
        try:
            value = fetch_jentech_context(
                ticker, diagnostics=jentech_details,
                force_refresh=force_refresh, use_cache=use_cache,
            )
            if value:
                diagnostics.update(jentech_details)
                return value
        except SourceResponseError as exc:
            primary_error = exc
            jentech_details.update(exc.diagnostic)
            if exc.error_kind in {
                'lease_lost', 'timeout', 'single_flight_busy',
                'guard_storage_unavailable', 'context_unverified',
            }:
                diagnostics.update(jentech_details)
                raise

        official_details = {}
        def include_attempt_metrics(target):
            primary_count = jentech_details.get('http_request_count')
            fallback_count = official_details.get('http_request_count')
            primary_count = primary_count if type(primary_count) is int and primary_count >= 0 else 0
            fallback_count = fallback_count if type(fallback_count) is int and fallback_count >= 0 else 0
            target['http_request_count'] = primary_count + fallback_count
            target['http_request_sent'] = (
                jentech_details.get('http_request_sent') is True
                or official_details.get('http_request_sent') is True
            )

        try:
            value = _fetch_official_index_context(
                ticker, diagnostics=official_details, **index_options,
            )
        except SourceResponseError as exc:
            components = dict(official_details.get('component_statuses') or {})
            fallback_components = exc.diagnostic.get('component_statuses')
            if isinstance(fallback_components, dict):
                components.update(fallback_components)
            elif official_details:
                components['official_index'] = {
                    **official_details,
                    'status': 'error',
                    'error_kind': exc.error_kind,
                }
            components[JENTECH_PROVIDER] = jentech_details
            exc.diagnostic['component_statuses'] = components
            include_attempt_metrics(exc.diagnostic)
            diagnostics.update(exc.diagnostic)
            raise

        components = dict(official_details.get('component_statuses') or {})
        components[JENTECH_PROVIDER] = jentech_details
        if value:
            diagnostics.update(
                official_details,
                actual_provider=(official_details.get('actual_provider')
                                 or value.get('source')
                                 or FREE_EARNINGS_CALL_PROVIDER_NAME),
                component_statuses=components,
                fallback_reason=jentech_details.get('error_kind') or 'valid_empty',
                message='Jentech 官網來源未取得可用簡報；已回退官方 MOPS／TWSE 法說索引，並保留兩路來源狀態。',
            )
            include_attempt_metrics(diagnostics)
            return value

        if primary_error is not None:
            primary_error.diagnostic['component_statuses'] = {
                JENTECH_PROVIDER: jentech_details,
                'official_index': official_details,
            }
            include_attempt_metrics(primary_error.diagnostic)
            diagnostics.update(primary_error.diagnostic)
            raise primary_error

        official_details['component_statuses'] = components
        diagnostics.update(official_details)
        include_attempt_metrics(diagnostics)
        return {}
    from .market_sources.eclat_conference import supports_eclat, fetch_eclat_context
    if supports_eclat(ticker):
        primary = {}; started = time.monotonic()
        try:
            return fetch_eclat_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable', 'context_unverified', 'original_expired'}:
                raise
            primary.update(diagnostics, **exc.diagnostic)
            from search_provider_runtime import record_observation
            from .market_sources.eclat_conference import PROVIDER as ECLAT_PROVIDER
            record_observation(ECLAT_PROVIDER, started, outcome='failure', source='earnings_call',
                               details=primary, sent=primary.get('http_request_sent') is True)
        diagnostics.clear()
        fallback = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=fallback, **index_options)
        except SourceResponseError as exc:
            fallback.update(exc.diagnostic)
            exc.diagnostic['component_statuses'] = {'issuer_content': primary, 'official_index': dict(fallback)}
            diagnostics.update(exc.diagnostic)
            raise
        diagnostics.update(fallback, component_statuses={'issuer_content': primary, 'official_index': dict(fallback)},
                           actual_provider=fallback.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME)
        diagnostics['http_request_count'] = sum(row.get('http_request_count', 0) for row in (primary, fallback)
            if type(row.get('http_request_count')) is int and row['http_request_count'] >= 0)
        diagnostics['http_request_sent'] = any(row.get('http_request_sent') is True for row in (primary, fallback))
        return value
    from .market_sources.pcsc_conference import supports_pcsc, fetch_pcsc_context
    if supports_pcsc(ticker):
        return fetch_pcsc_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.guc_conference import supports_guc, fetch_guc_context
    if supports_guc(ticker):
        return fetch_guc_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.seec_conference import supports_seec, fetch_seec_context
    if supports_seec(ticker):
        return fetch_seec_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.kingslide_conference import supports_kingslide, fetch_kingslide_context
    if supports_kingslide(ticker):
        return fetch_kingslide_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.promate_conference import supports_promate, fetch_promate_context
    if supports_promate(ticker):
        return fetch_promate_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.zdt_conference import supports_zdt, fetch_zdt_context
    if supports_zdt(ticker):
        return fetch_zdt_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.getac_conference import supports_getac
    if supports_getac(ticker):
        # Independently qualified government publisher; no failure-triggered
        # retry of the issuer host or a second route after an admission block.
        from .market_sources.mops_presentation import fetch_presentation_context
        return fetch_presentation_context('3005.TW', diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.npc_conference import supports_npc, fetch_npc_context
    if supports_npc(ticker):
        return fetch_npc_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.sinbon_conference import supports_sinbon, fetch_sinbon_context
    if supports_sinbon(ticker):
        return fetch_sinbon_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.fubon_conference import supports_fubon, fetch_fubon_context
    if supports_fubon(ticker):
        return fetch_fubon_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.voltronic_conference import supports_voltronic, fetch_voltronic_context
    if supports_voltronic(ticker):
        return fetch_voltronic_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.macronix_conference import supports_macronix, fetch_macronix_context
    if supports_macronix(ticker):
        return fetch_macronix_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.tecom_conference import supports_tecom, fetch_tecom_context
    if supports_tecom(ticker):
        return fetch_tecom_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.eikei_conference import supports_eikei, fetch_eikei_context
    if supports_eikei(ticker):
        return fetch_eikei_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.nanyapcb_conference import supports_nanyapcb, fetch_nanyapcb_context
    if supports_nanyapcb(ticker):
        return fetch_nanyapcb_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.wahlee_conference import supports_wahlee, fetch_wahlee_context
    if supports_wahlee(ticker):
        return fetch_wahlee_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.chroma_conference import supports_chroma, fetch_chroma_context
    if supports_chroma(ticker):
        return fetch_chroma_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.chb_conference import supports_chb, fetch_chb_context
    if supports_chb(ticker):
        return fetch_chb_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.innocare_conference import supports_innocare, fetch_innocare_context
    if supports_innocare(ticker):
        return fetch_innocare_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.walsin_conference import supports_walsin, fetch_walsin_context
    if supports_walsin(ticker):
        return fetch_walsin_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.lienhwa_conference import supports_lienhwa, fetch_lienhwa_context
    if supports_lienhwa(ticker):
        # A separate issuer endpoint; never retry or clear the MOPS guard here.
        return fetch_lienhwa_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.mops_presentation import supports as supports_material, fetch_presentation_context
    if supports_material(ticker):
        return fetch_presentation_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)
    from .market_sources.cht_conference import supports_cht, fetch_cht_context
    if supports_cht(ticker):
        issuer_details = {}
        try:
            value = fetch_cht_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'CHT_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'CHT_presentation': issuer_details})
        return value
    from .market_sources.allis_conference import supports_allis, fetch_allis_context
    if supports_allis(ticker):
        issuer_details = {}
        try:
            value = fetch_allis_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'Allis_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'Allis_presentation': issuer_details})
        return value
    from .market_sources.gce_conference import supports_gce, fetch_gce_context
    if supports_gce(ticker):
        issuer_details = {}
        try:
            value = fetch_gce_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'GCE_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'GCE_presentation': issuer_details})
        return value
    from .market_sources.hiwin_conference import supports_hiwin, fetch_hiwin_context
    if supports_hiwin(ticker):
        issuer_details = {}
        try:
            value = fetch_hiwin_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'HIWIN_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'HIWIN_presentation': issuer_details})
        return value
    from .market_sources.kinik_conference import supports_kinik, fetch_kinik_context
    if supports_kinik(ticker):
        issuer_details = {}
        try:
            value = fetch_kinik_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'KINIK_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'KINIK_presentation': issuer_details})
        return value
    from .market_sources.csc_conference import supports_csc, fetch_csc_context
    if supports_csc(ticker):
        issuer_details = {}
        try:
            value = fetch_csc_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'CSC_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'CSC_presentation': issuer_details})
        return value
    from .market_sources.sti_conference import supports_sti, fetch_sti_context
    if supports_sti(ticker):
        issuer_details = {}
        try:
            value = fetch_sti_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'STI_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'STI_presentation': issuer_details})
        return value
    from .market_sources.sigurd_conference import supports_sigurd, fetch_sigurd_context
    if supports_sigurd(ticker):
        issuer_details = {}
        try:
            value = fetch_sigurd_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'Sigurd_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'Sigurd_presentation': issuer_details})
        return value
    from .market_sources.winbond_conference import supports_winbond, fetch_winbond_context
    if supports_winbond(ticker):
        issuer_details = {}
        try:
            value = fetch_winbond_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'Winbond_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'Winbond_presentation': issuer_details})
        return value
    from .market_sources.chipmos_conference import supports_chipmos, fetch_chipmos_context
    if supports_chipmos(ticker):
        issuer_details = {}
        try:
            value = fetch_chipmos_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'ChipMOS_transcript': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'ChipMOS_transcript': issuer_details})
        return value
    from .market_sources.unitech_conference import supports_unitech, fetch_unitech_context
    if supports_unitech(ticker):
        issuer_details = {}
        try:
            value = fetch_unitech_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'Unitech_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'Unitech_presentation': issuer_details})
        return value
    from .market_sources.tewc_conference import supports_tewc, fetch_tewc_context
    if supports_tewc(ticker):
        issuer_details = {}
        try:
            value = fetch_tewc_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'TEWC_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'TEWC_presentation': issuer_details})
        return value
    from .market_sources.delta_conference import supports_delta, fetch_delta_context
    if supports_delta(ticker):
        issuer_details = {}
        try:
            value = fetch_delta_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'Delta_transcript': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
                           component_statuses={**(components if isinstance(components, dict) else {}), 'Delta_transcript': issuer_details})
        return value
    from .market_sources.auras_conference import supports_auras, fetch_auras_context
    if supports_auras(ticker):
        issuer_details = {}
        try:
            value = fetch_auras_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'Auras_presentation': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, component_statuses={**(components if isinstance(components, dict) else {}), 'Auras_presentation': issuer_details})
        return value
    from .market_sources.tcfhc_conference import supports_tcfhc, fetch_tcfhc_context
    if supports_tcfhc(ticker):
        issuer_details = {}
        try:
            value = fetch_tcfhc_context(ticker, diagnostics=issuer_details, force_refresh=force_refresh, use_cache=use_cache)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            components = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(components if isinstance(components, dict) else {}), 'TCFHC_QA': issuer_details}
            raise
        components = secondary.get('component_statuses')
        diagnostics.update(secondary, component_statuses={**(components if isinstance(components, dict) else {}), 'TCFHC_QA': issuer_details})
        return value
    from .market_sources.psc_conference import supports_psc, fetch_psc_context
    if supports_psc(ticker):
        issuer_details = {}
        try:
            value = fetch_psc_context(ticker, diagnostics=issuer_details)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            existing = exc.diagnostic.get('component_statuses')
            exc.diagnostic['component_statuses'] = {**(existing if isinstance(existing, dict) else {}), 'PSC': issuer_details}
            raise
        diagnostics.update(secondary, component_statuses={'PSC': issuer_details, 'official_index': dict(secondary)})
        return value
    from .market_sources.honhai_conference import supports_honhai, enrich_honhai_context, validate_context as validate_honhai
    if supports_honhai(ticker):
        deadline = time.monotonic() + 20.
        if source_context is not None:
            if not validate_honhai(source_context, str(ticker).strip().upper()):
                exc=SourceResponseError('context_unverified')
                from .market_sources.honhai_conference import PROVIDER as HONHAI_PROVIDER
                exc.diagnostic.update(actual_provider=HONHAI_PROVIDER,honhai_transcript_workflow=True,http_request_sent=False,http_request_count=0)
                raise exc
            value = source_context['earnings_call']
        else:
            value = _fetch_official_index_context(ticker, diagnostics=diagnostics, **index_options)
        return enrich_honhai_context(ticker, value, diagnostics=diagnostics, deadline=deadline)
    from .market_sources.txc_conference import supports_txc, fetch_txc_context
    if supports_txc(ticker):
        issuer_details = {}
        try:
            value = fetch_txc_context(ticker, diagnostics=issuer_details)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            existing = exc.diagnostic.get('component_statuses')
            components = dict(existing) if isinstance(existing, dict) else {}
            components['TXC'] = issuer_details
            exc.diagnostic['component_statuses'] = components
            raise
        existing = secondary.get('component_statuses')
        components = dict(existing) if isinstance(existing, dict) else {}
        components['TXC'] = issuer_details
        diagnostics.update(secondary, component_statuses=components)
        return value
    from .market_sources.nanya_mops_presentation import supports_nanya, enrich_nanya_context
    if supports_nanya(ticker):
        deadline = time.monotonic() + 20.
        value = _fetch_official_index_context(ticker, diagnostics=diagnostics, **index_options)
        return enrich_nanya_context(ticker, value, diagnostics=diagnostics, deadline=deadline) if value else value
    from .market_sources.uk_conference import supports_uk, fetch_uk_context
    if supports_uk(ticker):
        issuer_details = {}
        try:
            value = fetch_uk_context(ticker, diagnostics=issuer_details)
            if value:
                diagnostics.update(issuer_details)
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic, error_kind=exc.error_kind)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            existing = exc.diagnostic.get('component_statuses')
            components = dict(existing) if isinstance(existing, dict) else {}
            components['Universal'] = issuer_details
            exc.diagnostic['component_statuses'] = components
            raise
        existing = secondary.get('component_statuses')
        components = dict(existing) if isinstance(existing, dict) else {}
        components['Universal'] = issuer_details
        diagnostics.update(secondary, component_statuses=components)
        return value
    if supports_cathay(ticker):
        issuer_details = {}
        try:
            value = fetch_cathay_conference_context(ticker, diagnostics=issuer_details)
            if value:
                diagnostics.update(issuer_details, coverage_status='partial',
                                   message='僅取得國泰金官方法說活動與資料連結，未取得簡報內容或逐字稿。')
                return value
        except SourceResponseError as exc:
            if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
                raise
            issuer_details.update(exc.diagnostic)
        secondary = {}
        try:
            value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
        except SourceResponseError as exc:
            exc.diagnostic['component_statuses'] = {
                'cathay_ir': issuer_details, 'official_index': {**secondary, **exc.diagnostic}}
            raise
        diagnostics.update(secondary, coverage_status='partial',
                           component_statuses={'cathay_ir': issuer_details,
                                               'official_index': dict(secondary)})
        return value
    if not supports_company(ticker):
        return _fetch_official_index_context(ticker, diagnostics=diagnostics, **index_options)
    try:
        value = fetch_company_conference(ticker, diagnostics=diagnostics)
        if value:
            return value
    except SourceResponseError as exc:
        if exc.error_kind in {'lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'}:
            raise
        diagnostics.update(exc.diagnostic)
    issuer_details = dict(diagnostics)
    secondary = {}
    try:
        value = _fetch_official_index_context(ticker, diagnostics=secondary, **index_options)
    except SourceResponseError as exc:
        exc.diagnostic['component_statuses'] = {
            'issuer_content': issuer_details, 'official_index': {**secondary, **exc.diagnostic}}
        raise
    diagnostics.clear()
    diagnostics.update(secondary, actual_provider=secondary.get('actual_provider') or value.get('source') or FREE_EARNINGS_CALL_PROVIDER_NAME,
        coverage_status='partial', message=AGGREGATE_MESSAGE,
        component_statuses={'issuer_content': issuer_details, 'official_index': dict(secondary)})
    return value


def _fetch_twse_iih_notice_fallback(ticker: str, diagnostics: dict, *, components: dict | None = None,
                                    use_cache: bool = True, force_refresh: bool = False) -> dict:
    """Recover official notice text and its exact-month MOPS material index."""
    from .market_sources.twse_iih_conference_notice import (
        PROVIDER as IIH_PROVIDER, fetch_twse_iih_conference_notice,
    )
    from search_provider_runtime import SourceResponseError

    details = {}
    statuses = dict(components or {})
    try:
        context = fetch_twse_iih_conference_notice(ticker, diagnostics=details)
    except SourceResponseError as exc:
        details.update(exc.diagnostic, status="error", error_kind=exc.error_kind)
        statuses["TWSE_IIH_MOPS_notice"] = details
        diagnostics.update(component_statuses=statuses)
        return {}
    statuses["TWSE_IIH_MOPS_notice"] = details
    diagnostics.update(component_statuses=statuses)
    if not context:
        return {}
    if context.get("materials"):
        diagnostics.update(details,
                           actual_provider=details.get("actual_provider") or IIH_PROVIDER,
                           coverage_status=context.get("coverage_status") or "official_notice_text_only",
                           message="已由 TWSE IIH 找到 MOPS 精確月份場次頁及同場簡報連結；僅有索引與連結，未下載或解析簡報內容，也沒有逐字稿。")
        return context
    monthly_details = {"actual_provider": "MOPS investor conference monthly query",
                       "source_query_month": None, "status": "unavailable",
                       "http_request_sent": False, "http_request_count": 0}
    event_date = str(context.get("date") or "")
    try:
        parsed_event_date = datetime.strptime(event_date, "%Y-%m-%d").date()
    except ValueError:
        monthly_details.update(error_kind="invalid_event_date",
                               message="IIH 事件日期格式不符；未查詢 MOPS 月頁。")
    else:
        monthly_details.update(event_date=event_date, source_query_year=parsed_event_date.year,
                               source_query_month=parsed_event_date.month)
        try:
            from official_financials import fetch_mops_investor_conference_events
            monthly_events = fetch_mops_investor_conference_events(
                ticker, year=parsed_event_date.year, month=parsed_event_date.month,
                limit=3, use_cache=use_cache, force_refresh=force_refresh,
                diagnostics=monthly_details,
            )
            code = str(ticker or "").strip().upper().removesuffix(".TW")
            event = next((row for row in monthly_events
                          if isinstance(row, dict)
                          and str(row.get("ticker") or "").strip().upper().removesuffix(".TW") == code
                          and str(row.get("date") or "") == event_date), None)
            materials = event.get("materials") if isinstance(event, dict) else None
            verified_materials = []
            for material in materials if isinstance(materials, list) else []:
                if not isinstance(material, dict):
                    continue
                url = str(material.get("url") or "")
                if re.fullmatch(
                    rf"https://mopsov\.twse\.com\.tw/nas/STR/{re.escape(code)}\d{{8}}[ME]\d{{3}}\.pdf",
                    url,
                ):
                    verified_materials.append({"label": str(material.get("label") or "官方簡報檔案"), "url": url})
            if event and verified_materials:
                context = dict(context)
                context["materials"] = verified_materials
                monthly_details.update(status="success", matched_event_date=event_date,
                                       presentation_link_count=len(verified_materials),
                                       message="已由 MOPS 對應月份核對同公司、同場次的官方簡報連結；未下載或解析簡報內容。")
            elif event:
                monthly_details.update(status="degraded_enrichment", matched_event_date=event_date,
                                       presentation_link_count=0,
                                       message="MOPS 月頁有同場次資料，但未提供可核對的官方 PDF 連結。")
            else:
                monthly_details.update(status=monthly_details.get("status") or "degraded_enrichment",
                                       matched_event_date=None, presentation_link_count=0,
                                       message="MOPS 對應月份未列出同公司、同場次資料；保留已核對的公告文字。")
        except SourceResponseError as exc:
            monthly_details.update(exc.diagnostic, status="error", error_kind=exc.error_kind)
        except Exception as exc:
            monthly_details.update(status="error", error_kind=type(exc).__name__)
    statuses["MOPS_event_month"] = monthly_details
    diagnostics.update(component_statuses=statuses)
    diagnostics.update(details, actual_provider=IIH_PROVIDER,
                       coverage_status="official_notice_text_only",
                       message="MOPS 年度索引未提供可用內容；已由 TWSE IIH 核對公告正文，並以場次日期查詢 MOPS 月頁補取簡報連結（若有）。未宣稱取得逐字稿或簡報全文。")
    return context


def _fetch_irengage_fallback(ticker: str, context: dict, diagnostics: dict, *,
                             use_cache: bool = True, force_refresh: bool = False) -> dict:
    """Use the public IR Engage listing to fill event materials after index gaps."""
    from search_provider_runtime import SourceResponseError
    from official_financials_irengage_conference import (
        PROVIDER as IR_ENGAGE_PROVIDER,
        TAIPEI as IR_ENGAGE_TIMEZONE,
        fetch_irengage_conference_context,
    )

    current_year = datetime.now(IR_ENGAGE_TIMEZONE).year
    observations = []
    candidate = {}
    for year in (current_year, current_year - 1):
        details = {}
        try:
            candidate = fetch_irengage_conference_context(
                ticker, year=year, diagnostics=details,
                use_cache=use_cache, force_refresh=force_refresh,
            )
        except SourceResponseError as exc:
            details.update(exc.diagnostic, status='error', error_kind=exc.error_kind,
                           actual_provider=IR_ENGAGE_PROVIDER)
            candidate = {}
        observations.append({'year': year, **details})
        if candidate or details.get('status') not in {'valid_empty', 'success'}:
            break

    details = dict(observations[-1]) if observations else {}
    request_count = sum(item.get('http_request_sent') is True for item in observations)
    details.update(
        years_checked=[item['year'] for item in observations],
        year_observations=observations,
        http_request_count=request_count,
        http_request_sent=request_count > 0,
        actual_provider=IR_ENGAGE_PROVIDER,
    )

    statuses = dict(diagnostics.get('component_statuses') or {})
    statuses['IR_Engage'] = details
    previous_sent = diagnostics.get('source_http_request_sent', diagnostics.get('http_request_sent')) is True
    current_sent = request_count > 0
    diagnostics['component_statuses'] = statuses
    diagnostics['source_http_request_sent'] = previous_sent or current_sent
    diagnostics['http_request_sent'] = previous_sent or current_sent
    diagnostics['http_request_count'] = int(diagnostics.get('http_request_count') or 0) + request_count

    if not candidate:
        return context or {}

    selected = context or {}
    selected_date = str(selected.get('date') or '')
    candidate_date = str(candidate.get('date') or '')
    selected_materials = selected.get('materials') if isinstance(selected.get('materials'), list) else []
    candidate_materials = candidate.get('materials') if isinstance(candidate.get('materials'), list) else []
    prefer_candidate = not selected
    if selected and candidate_date and selected_date:
        prefer_candidate = candidate_date > selected_date

    if prefer_candidate:
        selected = dict(candidate)
    elif selected and candidate_date == selected_date and candidate_materials:
        selected = dict(selected)
        selected['materials'] = candidate_materials
        selected['source'] = IR_ENGAGE_PROVIDER
        selected['source_url'] = candidate.get('source_url') or selected.get('source_url')
        selected['upstream_source'] = candidate.get('upstream_source')
        selected['coverage_status'] = candidate.get('coverage_status')
        selected['coverage_notes'] = list(dict.fromkeys(
            list(selected.get('coverage_notes') or []) + list(candidate.get('coverage_notes') or [])
        ))
        if not selected.get('summary'):
            selected['summary'] = candidate.get('summary') or ''

    if selected.get('source') == IR_ENGAGE_PROVIDER:
        diagnostics.update(
            actual_provider=IR_ENGAGE_PROVIDER,
            coverage_status=selected.get('coverage_status') or 'metadata_only',
            fetched_at_epoch=details.get('fetched_at_epoch'),
            message='MOPS 索引資料不足；IR Engage 補回公開法說活動資料與可用簡報連結，未宣稱取得逐字稿。',
        )
    return selected


def _fetch_tpex_infohub_fallback(ticker: str, diagnostics: dict, *,
                                components: dict | None = None,
                                now: datetime | None = None) -> dict:
    """Recover a TPEx conference invitation from its InfoHub index and MOPS original."""
    if not re.fullmatch(r"[1-9]\d{3,5}\.TWO", str(ticker or "").strip().upper()):
        return {}
    from .market_sources.tpex_infohub import (
        PROVIDER as INFOHUB_PROVIDER, fetch_tpex_infohub_earnings_call,
    )

    details = {}
    started = time.monotonic()
    try:
        context, details = fetch_tpex_infohub_earnings_call(ticker, now=now)
    except Exception as exc:
        details.update(status="error", error_kind=getattr(exc, "error_kind", type(exc).__name__),
                       provider=INFOHUB_PROVIDER, actual_provider=INFOHUB_PROVIDER)
        context = {}
    if not details.get("observation_recorded"):
        from search_provider_runtime import record_observation
        record_observation(INFOHUB_PROVIDER, started,
                          outcome="results" if context else "failure",
                          count=1 if context else 0, details=details,
                          source="earnings_call",
                          sent=details.get("http_request_sent") is True)
        details["observation_recorded"] = True
    statuses = dict(components or diagnostics.get("component_statuses") or {})
    statuses["TPEx_InfoHub"] = details
    diagnostics.update(component_statuses=statuses,
                       tpex_infohub_fallback_status=details.get("status"))
    if context:
        diagnostics.update(details, actual_provider=INFOHUB_PROVIDER,
                           coverage_status="official_notice_text_only",
                           component_statuses=statuses)
        return context
    return {}


def _fetch_official_index_context(ticker: str, *, diagnostics: dict | None = None,
                                  use_cache: bool = True, force_refresh: bool = False) -> dict:
    """Return free official investor-conference context for Taiwan tickers."""
    from official_financials import fetch_mops_investor_conference_events

    from official_financials_webpro_conference import fetch_webpro_conference_context, taiwan_company_symbol
    from search_provider_runtime import SourceResponseError

    if not taiwan_company_symbol(ticker):
        return {}
    diagnostics = diagnostics if diagnostics is not None else {}
    year_observations = []
    def fetch_year(year=None):
        details = {}
        options = {'use_cache': True, 'force_refresh': force_refresh, 'diagnostics': details} if use_cache else {}
        value = fetch_mops_investor_conference_events(ticker, limit=1, **({'year':year} if year is not None else {}), **options)
        if details:year_observations.append(details)
        return value
    try:
        events = fetch_year()
        if not events:
            events = fetch_year(date.today().year - 1)
    except SourceResponseError as primary_error:
        primary = {"provider": FREE_EARNINGS_CALL_PROVIDER_NAME, "status": "error", **primary_error.diagnostic}
        diagnostics.update(fallback_reason=primary_error.error_kind, component_statuses={"MOPS": primary})
        from systex_conference_index import supports_systex, fetch_systex_conference_context
        if supports_systex(ticker) and primary_error.error_kind in {'server_error', 'timeout', 'transport_error', 'rate_limited', 'cooldown'}:
            issuer = {}
            try:
                context = fetch_systex_conference_context(ticker, diagnostics=issuer)
                if context:
                    diagnostics.update(issuer, component_statuses={'MOPS': primary, 'SYSTEX': dict(issuer)})
                    return context
            except SourceResponseError as issuer_error:
                issuer.update(issuer_error.diagnostic, status='error')
                diagnostics['component_statuses']['SYSTEX'] = issuer
        if str(ticker or "").strip().upper().endswith(".TWO"):
            context = _fetch_tpex_infohub_fallback(
                ticker, diagnostics, components=diagnostics.get("component_statuses"))
            if context:
                return context
            details = (diagnostics.get("component_statuses") or {}).get("TPEx_InfoHub", {})
            diagnostics.update(
                actual_provider=details.get("actual_provider") or "TPEx Market InfoHub company disclosures",
                coverage_status="partial",
                message="MOPS 法說索引未取得；TPEx InfoHub 備援也沒有可核對的會議原文。",
            )
            return {}
        if primary_error.error_kind in {'server_error', 'timeout', 'transport_error', 'rate_limited', 'cooldown'}:
            if not str(ticker or "").strip().upper().endswith(".TWO"):
                iih_context = _fetch_twse_iih_notice_fallback(
                    ticker, diagnostics, components=diagnostics.get("component_statuses"),
                    use_cache=use_cache, force_refresh=force_refresh)
                if iih_context:
                    return _fetch_irengage_fallback(
                        ticker, iih_context, diagnostics,
                        use_cache=use_cache, force_refresh=force_refresh,
                    )
        secondary = {}
        try:
            context = fetch_webpro_conference_context(ticker, diagnostics=secondary)
        except SourceResponseError as secondary_error:
            secondary.update(secondary_error.diagnostic, status="error")
            diagnostics["component_statuses"]["WebPro"] = secondary
            recovered = _fetch_irengage_fallback(
                ticker, {}, diagnostics, use_cache=use_cache, force_refresh=force_refresh,
            )
            if recovered:
                return recovered
            raise
        secondary["status"] = "degraded_enrichment"
        components = dict(diagnostics.get("component_statuses") or {})
        components["WebPro"] = dict(secondary)
        diagnostics.update(secondary, coverage_status="partial", component_statuses=components)
        if context and primary_error.error_kind in {
            'server_error', 'timeout', 'transport_error', 'rate_limited', 'cooldown',
        }:
            # WebPro gives a verified company/date candidate. Query only that
            # exact MOPS month so a failed, oversized annual response can still
            # recover the official event record and its material links.
            monthly_details = {
                'actual_provider': 'MOPS investor conference monthly query',
                'status': 'unavailable', 'http_request_sent': False,
                'http_request_count': 0,
            }
            event_date = str(context.get('date') or '')
            try:
                selected_day = datetime.strptime(event_date, '%Y-%m-%d').date()
            except ValueError:
                monthly_details.update(error_kind='invalid_event_date')
            else:
                monthly_details.update(source_query_year=selected_day.year,
                                       source_query_month=selected_day.month,
                                       event_date=event_date)
                try:
                    monthly_events = fetch_mops_investor_conference_events(
                        ticker, year=selected_day.year, month=selected_day.month,
                        limit=3, use_cache=use_cache, force_refresh=force_refresh,
                        diagnostics=monthly_details,
                    )
                    symbol = taiwan_company_symbol(ticker)
                    matched = next((row for row in monthly_events
                                    if isinstance(row, dict)
                                    and taiwan_company_symbol(row.get('ticker')) == symbol
                                    and row.get('date') == event_date
                                    and row.get('source') == FREE_EARNINGS_CALL_PROVIDER_NAME), None)
                    if matched:
                        native_success = (monthly_details.get('status') == 'success'
                                          and monthly_details.get('http_request_sent') is True)
                        cached_success = (monthly_details.get('cache_hit') is True
                                          and monthly_details.get('stale') is False)
                        if native_success or cached_success:
                            parent_status = 'success' if native_success else 'skipped_fresh_cache'
                            monthly_details.update(status=parent_status, matched_event_date=event_date,
                                                   message='MOPS 月頁與 WebPro 所列公司及場次日期一致。')
                            components['MOPS_event_month'] = dict(monthly_details)
                            diagnostics.update(
                                status=parent_status,
                                actual_provider=FREE_EARNINGS_CALL_PROVIDER_NAME,
                                coverage_status='official_event_record',
                                message='optional 外部來源 MOPS 月份法說資訊彙總；原生請求與快取另列觀測。',
                                component_statuses=components,
                                fetched_at_epoch=monthly_details.get('fetched_at_epoch'),
                                http_request_sent=monthly_details.get('http_request_sent') is True,
                                http_request_count=int(monthly_details.get('http_request_count') or 0),
                                cache_hit=monthly_details.get('cache_hit') is True,
                                stale=monthly_details.get('stale') is True,
                            )
                            return _mops_conference_event_context(ticker, matched)
                    monthly_details.update(status=monthly_details.get('status') or 'degraded_enrichment',
                                           matched_event_date=None,
                                           message='MOPS 對應月份沒有同公司、同日期的官方場次。')
                except SourceResponseError as monthly_error:
                    monthly_details.update(monthly_error.diagnostic, status='error',
                                           error_kind=monthly_error.error_kind)
            components['MOPS_event_month'] = dict(monthly_details)
            diagnostics['component_statuses'] = components
        if not context:
            diagnostics["message"] = "MOPS 未取得資料；WebPro 此頁索引未列可用的已完成場次，不能據此判定公司沒有法說會。"
        else:
            diagnostics["message"] = "MOPS 未取得資料；WebPro 僅補回法說會日期與連結，未取得內容或逐字稿。"
        return _fetch_irengage_fallback(
            ticker, context, diagnostics, use_cache=use_cache, force_refresh=force_refresh,
        )
    if year_observations:
        stamps=[row['fetched_at_epoch'] for row in year_observations if row.get('fetched_at_epoch') is not None]
        diagnostics.update(cache_hit=all(row.get('cache_hit') for row in year_observations),
                           http_request_sent=any(row.get('http_request_sent') for row in year_observations),
                           http_request_count=sum(row.get('http_request_count',0) for row in year_observations),
                           fetched_at_epoch=min(stamps) if stamps else None,
                           mops_year_observations=year_observations)
        # Each native/cache year has its own observation. This parent only
        # assembles them and must not count cached old events as a new success.
        diagnostics['message']='optional 外部來源 MOPS 年度法說資訊彙總；各年度實際請求與快取另列觀測。'
        if events and year_observations[-1].get('cache_hit') and diagnostics['http_request_count']:
            diagnostics.update(coverage_status='partial',
                               acquisition_status='partial_acquisition_with_cached_records')
    if not events:
        is_tpex = str(ticker or "").strip().upper().endswith(".TWO")
        components = {"MOPS": {"provider": FREE_EARNINGS_CALL_PROVIDER_NAME,
                               "status": "valid_empty", "year_observations": year_observations}}
        if is_tpex:
            tpex_context = _fetch_tpex_infohub_fallback(
                ticker, diagnostics,
                components=components)
            if tpex_context:
                return tpex_context
            components = dict(diagnostics.get("component_statuses") or components)

        # MOPS can return a valid empty annual query even when the official
        # WebPro company index already lists a completed event. Use its exact
        # company-code feed before weaker secondary listings; keep a true empty
        # empty when the official index also has no usable event.
        from official_financials_webpro_conference import (
            PROVIDER as WEBPRO_PROVIDER, fetch_webpro_conference_context,
        )
        webpro_details = {}
        try:
            webpro_context = fetch_webpro_conference_context(ticker, diagnostics=webpro_details)
        except SourceResponseError as webpro_error:
            webpro_details.update(webpro_error.diagnostic, status="error",
                                  error_kind=webpro_error.error_kind,
                                  actual_provider=WEBPRO_PROVIDER)
            webpro_context = {}
        webpro_details.setdefault("status", "success" if webpro_context else "valid_empty")
        components["WebPro"] = dict(webpro_details)
        if webpro_context:
            from .webpro_month_recovery import recover_event_month, request_count as observed_requests
            monthly_event = recover_event_month(
                ticker, webpro_context, diagnostics, components=components,
                year_observations=year_observations,
                use_cache=use_cache, force_refresh=force_refresh)
            if monthly_event is not None:
                value = _mops_conference_event_context(ticker, monthly_event)
                value['coverage_status'] = 'official_event_record'
                if webpro_context.get('recency_comparison_complete') is False:
                    value.update(selection_status='partial', recency_comparison_complete=False,
                                 incomplete_categories=webpro_context.get('incomplete_categories', []))
                return value
            mops_request_count = sum(
                int(row.get("http_request_count") or 0)
                for row in year_observations if isinstance(row, dict)
            )
            webpro_request_count = observed_requests(webpro_details)
            monthly_request_count = observed_requests(components.get('MOPS_event_month', {}))
            request_count = mops_request_count + webpro_request_count + monthly_request_count
            mops_cache_hit = bool(year_observations) and all(
                row.get("cache_hit") is True for row in year_observations if isinstance(row, dict)
            )
            webpro_cache_hit = webpro_details.get("cache_hit") is True
            diagnostics.update(
                webpro_details,
                actual_provider=WEBPRO_PROVIDER,
                coverage_status=webpro_context.get("coverage_status") or "metadata_only",
                fallback_reason="mops_valid_empty",
                mops_year_observations=year_observations,
                component_statuses=components,
                cache_hit=mops_cache_hit and webpro_cache_hit,
                stale=any(row.get("stale") is True for row in year_observations
                          if isinstance(row, dict)) or webpro_details.get("stale") is True,
                source_http_request_sent=request_count > 0,
                http_request_sent=request_count > 0,
                http_request_count=request_count,
                message="MOPS 年度索引沒有可用場次；TWSE WebPro 公司索引補回官方場次日期與連結，未宣稱取得逐字稿。",
            )
            return webpro_context

        diagnostics["component_statuses"] = components
        if is_tpex:
            return _fetch_irengage_fallback(
                ticker, {}, diagnostics, use_cache=use_cache, force_refresh=force_refresh)
        iih_context = _fetch_twse_iih_notice_fallback(
            ticker, diagnostics,
            components=components,
            use_cache=use_cache, force_refresh=force_refresh)
        return _fetch_irengage_fallback(
            ticker, iih_context, diagnostics, use_cache=use_cache, force_refresh=force_refresh,
        )

    event = events[0]
    return _mops_conference_event_context(ticker, event)


def _mops_conference_event_context(ticker: str, event: dict) -> dict:
    summary = str(event.get("summary") or "").strip() or FREE_EARNINGS_CALL_COVERAGE_NOTE
    return {
        "ticker": str(event.get("ticker") or ticker).strip().upper(),
        "date": str(event.get("date") or date.today().isoformat()),
        "period": str(event.get("date") or ""),
        "title": str(event.get("title") or "").strip(),
        "summary": summary,
        "transcript_excerpt": "",
        "transcript_available": False,
        "materials": list(event.get("materials") or []),
        "source": FREE_EARNINGS_CALL_PROVIDER_NAME,
        "source_url": str(event.get("source_url") or ""),
        "coverage_notes": [FREE_EARNINGS_CALL_COVERAGE_NOTE],
    }


def fetch_latest_earnings_call(ticker: str, *, max_chars: int = 12_000) -> dict:
    """Return the latest available transcript excerpt or an empty mapping."""
    if not FMP_API_KEY:
        return {}
    if _fmp_transcript_cooldown_active():
        return {}

    symbol = str(ticker or "").strip().upper()
    if not symbol:
        return {}
    candidates = [
        (f"{FMP_BASE_URL}/earning-call-transcript", {"symbol": symbol, "limit": 1, "apikey": FMP_API_KEY}),
        (f"{FMP_LEGACY_TRANSCRIPT_URL}/{symbol}", {"apikey": FMP_API_KEY}),
    ]
    for url, params in candidates:
        try:
            payload = _sync_json_get(url, params)
        except Exception as exc:
            log_http_warning("FMP", "earnings call transcript", exc)
            if _is_restricted_fmp_response(exc):
                _mark_fmp_transcript_cooldown()
                break
            continue
        record = _latest_record(payload)
        if record:
            return _normalize_record(symbol, record, max_chars=max_chars)
    return {}


def _latest_record(payload: Any) -> dict:
    if isinstance(payload, dict):
        for key in ("data", "transcripts", "results"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        return {}
    rows = [row for row in payload if isinstance(row, dict) and str(row.get("content") or row.get("transcript") or "").strip()]
    return max(rows, key=lambda row: str(row.get("date") or ""), default={})


def _normalize_record(symbol: str, record: dict, *, max_chars: int) -> dict:
    content = str(record.get("content") or record.get("transcript") or "").strip()
    year = record.get("year")
    quarter = record.get("quarter")
    period = f"{year}Q{quarter}" if year and quarter else str(record.get("period") or "")
    return {
        "ticker": symbol,
        "date": str(record.get("date") or date.today().isoformat()),
        "period": period,
        "transcript_excerpt": content[:max(int(max_chars), 1)],
        "source": "FMP earnings call transcript",
        "source_url": str(record.get("url") or ""),
    }


def _now() -> float:
    return time.time()


def _restricted_cooldown_seconds() -> float:
    try:
        configured = os.getenv(
            "FMP_TRANSCRIPT_RESTRICTED_COOLDOWN_SECONDS",
            str(DEFAULT_FMP_TRANSCRIPT_RESTRICTED_COOLDOWN_SECONDS),
        )
        return max(float(configured), 0.0)
    except ValueError:
        return float(DEFAULT_FMP_TRANSCRIPT_RESTRICTED_COOLDOWN_SECONDS)


def _fmp_transcript_cooldown_active() -> bool:
    return _now() < _fmp_transcript_cooldown_until


def _mark_fmp_transcript_cooldown() -> None:
    global _fmp_transcript_cooldown_until
    cooldown_seconds = _restricted_cooldown_seconds()
    if cooldown_seconds <= 0:
        return
    _fmp_transcript_cooldown_until = max(_fmp_transcript_cooldown_until, _now() + cooldown_seconds)


def clear_fmp_transcript_cooldown() -> None:
    global _fmp_transcript_cooldown_until
    _fmp_transcript_cooldown_until = 0.0


def _is_restricted_fmp_response(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    try:
        return int(status_code) in FMP_TRANSCRIPT_RESTRICTED_STATUS_CODES
    except (TypeError, ValueError):
        return False


def apply_earnings_call_audit(result: dict, diagnostic: dict) -> None:
    """Keep partial fallback provenance in the report's existing source audit."""
    audit = result["audit"]
    audit.update({key: value for key, value in diagnostic.items()
                  if key not in {"event_kind", "http_request_sent"}})
    audit["event_kind"] = "aggregate"
    if diagnostic.get('taiwanmobile_transcript_workflow'):
        verified = diagnostic.get('taiwanmobile_originals_verified') is True and bool(result.get('value'))
        audit.update(record_count=int(verified), http_request_sent=diagnostic.get('http_request_sent') is True)
        if verified and diagnostic.get('cache_hit'):
            audit.update(status='skipped_fresh_cache', cache_hit=True)
    if diagnostic.get('eclat_presentation_workflow'):
        audit['http_request_sent'] = diagnostic.get('http_request_sent') is True
        audit['record_count'] = int(diagnostic.get('eclat_originals_verified') is True and bool(result.get('value')))
        if diagnostic.get('eclat_originals_verified') is True and diagnostic.get('cache_hit'):
            audit.update(status='skipped_fresh_cache', cache_hit=True)
    if diagnostic.get('jentech_presentation_workflow') or diagnostic.get('pcsc_presentation_workflow') or diagnostic.get('guc_presentation_workflow') or diagnostic.get('seec_presentation_workflow') or diagnostic.get('kingslide_presentation_workflow') or diagnostic.get('promate_presentation_workflow') or diagnostic.get('tcfhc_qa_workflow') or diagnostic.get('auras_presentation_workflow') or diagnostic.get('delta_transcript_workflow') or diagnostic.get('tewc_presentation_workflow') or diagnostic.get('unitech_presentation_workflow') or diagnostic.get('chipmos_transcript_workflow') or diagnostic.get('winbond_presentation_workflow') or diagnostic.get('sigurd_presentation_workflow') or diagnostic.get('sti_presentation_workflow') or diagnostic.get('mops_material_workflow') or diagnostic.get('csc_presentation_workflow') or diagnostic.get('cht_presentation_workflow') or diagnostic.get('allis_presentation_workflow') or diagnostic.get('gce_presentation_workflow') or diagnostic.get('hiwin_presentation_workflow') or diagnostic.get('kinik_presentation_workflow') or diagnostic.get('lienhwa_presentation_workflow') or diagnostic.get('walsin_presentation_workflow') or diagnostic.get('innocare_presentation_workflow') or diagnostic.get('chb_qa_workflow') or diagnostic.get('chroma_presentation_workflow') or diagnostic.get('getac_presentation_workflow') or diagnostic.get('npc_presentation_workflow') or diagnostic.get('sinbon_presentation_workflow') or diagnostic.get('fubon_presentation_workflow') or diagnostic.get('voltronic_presentation_workflow') or diagnostic.get('macronix_presentation_workflow') or diagnostic.get('tecom_presentation_workflow') or diagnostic.get('eikei_presentation_workflow') or diagnostic.get('nanyapcb_presentation_workflow') or diagnostic.get('wahlee_presentation_workflow') or diagnostic.get('zdt_presentation_workflow'):
        # One source acquisition, not one success per index/master/PDF request.
        # Revalidating an index with cached QA must not become new body data.
        audit['http_request_sent'] = diagnostic.get('http_request_sent') is True
        audit['record_count'] = 1 if (diagnostic.get('jentech_originals_verified') or diagnostic.get('pcsc_originals_verified') or diagnostic.get('guc_originals_verified') or diagnostic.get('seec_originals_verified') or diagnostic.get('kingslide_originals_verified') or diagnostic.get('promate_originals_verified') or diagnostic.get('tcfhc_originals_verified') or diagnostic.get('auras_originals_verified') or diagnostic.get('delta_originals_verified') or diagnostic.get('tewc_originals_verified') or diagnostic.get('unitech_originals_verified') or diagnostic.get('chipmos_originals_verified') or diagnostic.get('winbond_originals_verified') or diagnostic.get('sigurd_originals_verified') or diagnostic.get('sti_originals_verified') or diagnostic.get('mops_material_originals_verified') or diagnostic.get('csc_originals_verified') or diagnostic.get('cht_originals_verified') or diagnostic.get('allis_originals_verified') or diagnostic.get('gce_originals_verified') or diagnostic.get('hiwin_originals_verified') or diagnostic.get('kinik_originals_verified') or diagnostic.get('lienhwa_originals_verified') or diagnostic.get('walsin_originals_verified') or diagnostic.get('innocare_originals_verified') or diagnostic.get('chb_originals_verified') or diagnostic.get('chroma_originals_verified') or diagnostic.get('getac_originals_verified') or diagnostic.get('npc_originals_verified') or diagnostic.get('sinbon_originals_verified') or diagnostic.get('fubon_originals_verified') or diagnostic.get('voltronic_originals_verified') or diagnostic.get('macronix_originals_verified') or diagnostic.get('tecom_originals_verified') or diagnostic.get('eikei_originals_verified') or diagnostic.get('nanyapcb_originals_verified') or diagnostic.get('wahlee_originals_verified') or diagnostic.get('zdt_originals_verified')) and result.get('value') else 0
        if (diagnostic.get('jentech_originals_verified') or diagnostic.get('pcsc_originals_verified') or diagnostic.get('guc_originals_verified') or diagnostic.get('seec_originals_verified') or diagnostic.get('kingslide_originals_verified') or diagnostic.get('promate_originals_verified') or diagnostic.get('tcfhc_originals_verified') or diagnostic.get('auras_originals_verified') or diagnostic.get('delta_originals_verified') or diagnostic.get('tewc_originals_verified') or diagnostic.get('unitech_originals_verified') or diagnostic.get('chipmos_originals_verified') or diagnostic.get('winbond_originals_verified') or diagnostic.get('sigurd_originals_verified') or diagnostic.get('sti_originals_verified') or diagnostic.get('mops_material_originals_verified') or diagnostic.get('csc_originals_verified') or diagnostic.get('cht_originals_verified') or diagnostic.get('allis_originals_verified') or diagnostic.get('gce_originals_verified') or diagnostic.get('hiwin_originals_verified') or diagnostic.get('kinik_originals_verified') or diagnostic.get('lienhwa_originals_verified') or diagnostic.get('walsin_originals_verified') or diagnostic.get('innocare_originals_verified') or diagnostic.get('chb_originals_verified') or diagnostic.get('chroma_originals_verified') or diagnostic.get('getac_originals_verified') or diagnostic.get('npc_originals_verified') or diagnostic.get('sinbon_originals_verified') or diagnostic.get('fubon_originals_verified') or diagnostic.get('voltronic_originals_verified') or diagnostic.get('macronix_originals_verified') or diagnostic.get('tecom_originals_verified') or diagnostic.get('eikei_originals_verified') or diagnostic.get('nanyapcb_originals_verified') or diagnostic.get('wahlee_originals_verified') or diagnostic.get('zdt_originals_verified')) and diagnostic.get('cache_hit'):
            audit.update(status='skipped_fresh_cache', cache_hit=True)
    if diagnostic.get('honhai_transcript_workflow'):
        audit['http_request_sent']=False
        audit['source_http_request_sent']=diagnostic.get('http_request_sent')is True
    if diagnostic.get('nanya_presentation_workflow'):
        from .market_sources.nanya_mops_presentation import AGGREGATE_MESSAGE as NANYA_AGGREGATE_MESSAGE
        audit['message'] = NANYA_AGGREGATE_MESSAGE
        audit['http_request_sent'] = False
        audit['source_http_request_sent'] = diagnostic.get('http_request_sent') is True
    if diagnostic.get('mops_year_observations'):
        # This is a workflow HTTP summary, not another tracked native request.
        audit['source_http_request_sent'] = diagnostic.get('http_request_sent') is True
    if diagnostic.get('mops_year_observations') and diagnostic.get('http_request_sent') is False:
        audit['http_request_sent'] = False
    if diagnostic.get('uk_originals_verified') or diagnostic.get('txc_originals_verified') or diagnostic.get('honhai_originals_verified') or diagnostic.get('psc_originals_verified'):
        audit['record_count'] = 1 if result.get('value') else 0
        audit['http_request_sent'] = False
        audit['source_http_request_sent'] = diagnostic.get('http_request_sent') is True
        if diagnostic.get('http_request_sent') is False:
            audit.update(http_request_sent=False, status='skipped_fresh_cache', cache_hit=True)
    actual = diagnostic.get("actual_provider") or FREE_EARNINGS_CALL_PROVIDER_NAME
    audit["provider"] = actual
    from .market_sources.psc_conference import PROVIDER as PSC_PROVIDER
    if actual == PSC_PROVIDER:
        audit['message'] = 'optional 外部來源統一證券法說原件彙總；每份原件實際請求與快取另列觀測。'
        audit['http_request_sent'] = False
        audit['source_http_request_sent'] = diagnostic.get('http_request_sent') is True
    if "component_statuses" in diagnostic:
        audit.pop("http_status", None)
    if diagnostic.get("coverage_status") == "partial":
        audit["status"] = "degraded_enrichment"
        audit["record_count"] = 1 if result.get("value") else 0
    if diagnostic.get("fetched_at_epoch") is not None:
        from datetime import datetime, timezone
        audit["fetched_at"] = datetime.fromtimestamp(diagnostic["fetched_at_epoch"], timezone.utc).isoformat()
