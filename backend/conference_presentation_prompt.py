"""Bounded page excerpts, kept separate from management call transcripts."""
from __future__ import annotations

import hashlib

KEYWORDS = {
    3: ('營收', '毛利', '營業利益', '現金流', '財務', '資本'),
    5: ('競爭', '市場', '客戶', '技術', '產品', '合作'),
    12: ('策略', '展望', '佈局', '投資', '發展', '風險'),
}
PREPARED_KEYWORDS = {
    3: ('revenue', 'gross margin', 'operating', 'cash', 'capital', 'income', 'capex'),
    5: ('market', 'product', 'technology', 'customer', 'dram'),
    12: ('outlook', 'strategy', 'future', 'investment', 'risk'),
}


def without_presentation_documents(context):
    """Keep real transcript/meta while excluding the new presentation records."""
    if not isinstance(context, dict):
        return context
    result = dict(context)
    documents = result.get('documents')
    if isinstance(documents, list):
        from conference_transcript_prompt import marked as transcript_marked
        kept = [row for row in documents if not isinstance(row, dict) or row.get('document_kind') not in {'presentation', 'issuer_qa_summary'} and not transcript_marked(row)]
        if kept:
            result['documents'] = kept
        else:
            result.pop('documents', None)
    return result


def presentation_prompt_context(context: dict, agent_num: int) -> dict:
    if agent_num not in KEYWORDS or not isinstance(context, dict):
        return {}
    from data_fetch.market_sources.eclat_conference import is_marked as eclat_marked, prompt_context as eclat_prompt_context
    if eclat_marked(context):
        return eclat_prompt_context(context, agent_num)
    documents = context.get('documents')
    if not isinstance(documents, list):
        return {}
    from conference_transcript_prompt import marked as transcript_marked, transcript_prompt_context
    if documents and transcript_marked(documents[0]):
        return transcript_prompt_context(context, agent_num)
    projected = []
    for document in documents[:1]:
        if not isinstance(document, dict) or document.get('document_kind') not in {'presentation', 'issuer_qa_summary'}:
            continue
        pages = document.get('pages')
        if not isinstance(pages, list):
            continue
        pages = [page for page in pages if isinstance(page, dict) and isinstance(page.get('text'), str)
                 and page['text'].strip() and type(page.get('page_number')) is int]
        from data_fetch.market_sources.jentech_conference import is_marked as jentech_marked
        jentech = jentech_marked(context)
        if jentech:
            from data_fetch.market_sources.jentech_conference import role_pages as jentech_role_pages, verify_context as verify_jentech
            try:
                if not verify_jentech(context, '3653.TW'):
                    continue
            except RuntimeError:
                continue
            pages = jentech_role_pages(document)
            if not pages:
                continue
        from data_fetch.market_sources.pcsc_conference import is_marked as pcsc_marked
        pcsc = pcsc_marked(context)
        if pcsc:
            from data_fetch.market_sources.pcsc_conference import role_pages as pcsc_role_pages, verify_context as verify_pcsc
            try:
                if not verify_pcsc(context, '2912.TW'):
                    continue
            except RuntimeError:
                continue
            pages = pcsc_role_pages(document)
            if not pages:
                continue
        from data_fetch.market_sources.guc_conference import is_marked as guc_marked
        guc = guc_marked(context)
        if guc:
            from data_fetch.market_sources.guc_conference import role_pages as guc_role_pages, verify_context as verify_guc
            try:
                if not verify_guc(context, '3443.TW'):
                    continue
            except RuntimeError:
                continue
            pages = guc_role_pages(document)
            if not pages:
                continue
        from data_fetch.market_sources.seec_conference import is_marked as seec_marked
        seec = seec_marked(context)
        if seec:
            from data_fetch.market_sources.seec_conference import role_pages as seec_role_pages, verify_context as verify_seec
            try:
                if not verify_seec(context, '1503.TW'):
                    continue
            except RuntimeError:
                continue
            pages = seec_role_pages(document)
            if not pages:
                continue
        kingslide = document.get('source') == 'KingSlide official conference presentation'
        if kingslide:
            from data_fetch.market_sources.kingslide_conference import role_pages as kingslide_role_pages, verify_context as verify_kingslide
            try:
                if not verify_kingslide(context, '2059.TW'):
                    continue
            except RuntimeError:
                continue
            pages = kingslide_role_pages(document)
            if not pages:
                continue
        promate = document.get('source') == 'Promate official conference presentation'
        if promate:
            from data_fetch.market_sources.promate_conference import role_pages as promate_role_pages
            pages = promate_role_pages(document)
            if not pages:
                continue
        from data_fetch.market_sources.feib_presentation_qualification import marked as feib_marked, role_pages as feib_role_pages
        feib = feib_marked(document)
        if feib:
            pages = feib_role_pages(document)
            if not pages:
                continue
        gce = document.get('source') == 'GCE official conference presentation'
        if gce and (document.get('projection_policy') != 'gce-presentation-role-v1'
                or document.get('content_sha256') != '5cf45269fd71405896244573487fff93966ca6b68514d611993bfb7e8cfe315d'):
            continue
        hiwin = document.get('source') == 'HIWIN official conference presentation'
        if hiwin:
            if (document.get('projection_policy') != 'hiwin-presentation-role-v1'
                    or document.get('content_sha256') != 'ebb6150526e26f75787f30db984ecac363ee95997770c905530491eaf078affb'):
                continue
            # These native strings are absent from the rendered original.
            # Keep originals unchanged; omit whole affected pages from roles.
            pages = [page for page in pages if page['page_number'] not in {2,3,7,8,12}]
        zdt = document.get('source') == 'ZDT official conference presentation'
        if zdt:
            from data_fetch.market_sources.zdt_conference import role_pages as zdt_role_pages
            pages = zdt_role_pages(document)
            if not pages:
                continue
        getac = document.get('source') == 'Getac official conference presentation'
        if getac:
            from data_fetch.market_sources.getac_conference import role_pages as getac_role_pages
            pages = getac_role_pages(document)
            if not pages:
                continue
        npc = document.get('source') == 'NPC official conference presentation'
        if npc:
            from data_fetch.market_sources.npc_conference import role_pages as npc_role_pages
            pages = npc_role_pages(document)
            if not pages:
                continue
        sinbon = document.get('source') == 'Sinbon published conference presentation'
        if sinbon:
            from data_fetch.market_sources.sinbon_conference import role_pages as sinbon_role_pages
            pages = sinbon_role_pages(document)
            if not pages:
                continue
        fubon = document.get('source') == 'Fubon published conference presentation'
        if fubon:
            from data_fetch.market_sources.fubon_conference import role_pages as fubon_role_pages
            pages = fubon_role_pages(document)
            if not pages:
                continue
        voltronic = document.get('source') == 'Voltronic published conference presentation'
        if voltronic:
            from data_fetch.market_sources.voltronic_conference import role_pages as voltronic_role_pages
            pages = voltronic_role_pages(document)
            if not pages:
                continue
        from data_fetch.market_sources.macronix_conference import is_marked as macronix_marked
        macronix = macronix_marked(context)
        if macronix:
            from data_fetch.market_sources.macronix_conference import role_pages as macronix_role_pages
            if document.get('projection_policy') == 'macronix-presentation-role-v2':
                from data_fetch.market_sources.macronix_dynamic_presentation import verify_for_projection
                if not verify_for_projection(context):
                    continue
            pages = macronix_role_pages(document)
            if not pages:
                continue
        tecom = document.get('source') == 'Tecom official conference presentation'
        if tecom:
            from data_fetch.market_sources.tecom_conference import role_pages as tecom_role_pages
            pages = tecom_role_pages(document)
            if not pages:
                continue
        eikei = document.get('source') == 'Eikei official conference presentation'
        if eikei:
            from data_fetch.market_sources.eikei_conference import role_pages as eikei_role_pages
            pages = eikei_role_pages(document)
            if not pages:
                continue
        nanyapcb = document.get('source') == 'NanyaPCB official conference presentation'
        if nanyapcb:
            from data_fetch.market_sources.nanyapcb_conference import role_pages as nanyapcb_role_pages
            pages = nanyapcb_role_pages(document)
            if not pages:
                continue
        wahlee = document.get('source') == 'Wahlee official conference presentation'
        if wahlee:
            from data_fetch.market_sources.wahlee_conference import role_pages as wahlee_role_pages
            pages = wahlee_role_pages(document)
            if not pages:
                continue
        chroma = document.get('source') == 'Chroma official conference presentation'
        if chroma:
            from data_fetch.market_sources.chroma_conference import role_pages as chroma_role_pages
            pages = chroma_role_pages(document)
            if not pages:
                continue
        chb = document.get('source') == 'CHB official investor QA summary'
        if chb:
            from data_fetch.market_sources.chb_conference import role_pages as chb_role_pages
            pages = chb_role_pages(document)
            if not pages:
                continue
        innocare = document.get('source') == 'InnoCare official conference presentation'
        if innocare:
            from data_fetch.market_sources.innocare_conference import role_pages
            pages = role_pages(document)
            if not pages:
                continue
        walsin = document.get('source') == 'Walsin official conference presentation'
        if walsin:
            if (document.get('projection_policy') != 'walsin-presentation-role-v1'
                    or document.get('content_sha256') != '8cd60978a0130763166c32c4854e697575445b7c8891f20c7f12bd9cd2534dcd'):
                continue
            # Original p4 contradicts itself; p5–7 charts are not qualified.
            # Preserve all raw pages; never trust the incoming allowlist.
            pages = [page for page in pages if page['page_number'] in {1, 2, 3, 8, 9, 10}]
        lienhwa = document.get('source') == 'Lien Hwa official conference presentation'
        if lienhwa:
            if (document.get('projection_policy') != 'lienhwa-presentation-role-v1'
                    or document.get('content_sha256') != 'a265012e09c64c1e890600fe3fd4151c819b9bf869f7f78dea88ec58ff73e268'):
                continue
            # Exact revision visual checks qualify these pages only. In particular,
            # p15 has covered native strings; do not trust a caller-supplied allowlist.
            pages = [page for page in pages if page['page_number'] in {1, 22, 24, 25}]
        kinik = document.get('source') == 'KINIK official conference presentation'
        if kinik:
            if (document.get('projection_policy') != 'kinik-presentation-role-v1'
                    or document.get('content_sha256') != '4490a76682ab9655cbe78c30736ede3749c31577c35eaa95ef187f7af8511d4c'):
                continue
            # Exact revision visual check: page18 has no native body; the
            # page36 image covers this footer. Preserve all raw saved pages.
            pages = [{**page, 'text': page['text'].replace(
                'Copyright©  KINIK COMPANY , All Rights Reserved.', '')}
                if page['page_number'] == 36 else page
                for page in pages if page['page_number'] != 18]
        cht = document.get('source') == 'CHT official conference presentation'
        if cht:
            # Only this visually checked revision has qualified page exclusions.
            # Keep every raw page in the saved original; omit draft-bearing pages
            # from the role view, including otherwise visible text on those pages.
            if (document.get('projection_policy') != 'cht-presentation-role-v1'
                    or document.get('content_sha256') != 'c4b36eac7005add9f41d65f563e867dffb0c2cca3c5acc476c6a7bcc1ae1f62f'):
                continue
            pages = [page for page in pages if page['page_number'] not in {4, 14}]
        from mops_qualified_role_pages import needs_projection, verified_role_pages
        qualified_mops = document.get('source') == 'MOPS published presentation' and needs_projection(context)
        if qualified_mops:
            pages=verified_role_pages(context,agent_num)
            if not pages:continue
        prepared = (document.get('source') == 'MOPS Nanya prepared presentation'
                    and document.get('projection_policy') == 'nanya-prepared-role-v1')
        english = document.get('source') in {'TEWC official English conference presentation', 'Sigurd official conference presentation', 'MOPS published presentation', 'CSC official conference presentation', 'CHT official conference presentation', 'GCE official conference presentation', 'HIWIN official conference presentation', 'Walsin official conference presentation'}
        terms = KEYWORDS[agent_num]
        if prepared:
            from data_fetch.market_sources.nanya_mops_presentation import PALETTE, PALETTES
            # Retain raw pages in the snapshot; omit only the exact observed
            # template prefix in this bounded, non-mutating role view.
            pages = [{**page, 'text': page['text'][len(PALETTE):]} for page in pages
                     if page['text'].startswith(PALETTES)]
            terms += PREPARED_KEYWORDS[agent_num]
        elif english or kinik:
            terms += PREPARED_KEYWORDS[agent_num]
        # Select by the role's visible terms, with stable page order on ties.
        ranked = sorted(pages, key=lambda page: (
            -sum(term in (page['text'].casefold() if prepared or english or kinik else page['text']) for term in terms), page['page_number']))
        if qualified_mops or chb or chroma or zdt or wahlee or npc or nanyapcb or eikei or tecom or sinbon or fubon or voltronic or macronix or getac or feib or promate or kingslide or jentech or pcsc or guc or seec:
            # Qualified complete pages fit the existing budget.
            # Exact seven-page QA fits the existing budget. Keep cross-page
            # questions/answers together, including their original sequence.
            ranked = pages
        budget, excerpts, word_budget = (1200 if prepared else 6000), [], 200
        if (qualified_mops or getac or macronix or voltronic or fubon or feib or promate or kingslide or jentech or pcsc or guc or seec) and sum(len(page['text']) for page in ranked) > budget:
            # The qualified pages must stay whole: page8 ends with the
            # ownership boundary. Never omit that footnote to fit a budget.
            continue
        for page in ranked[:12]:
            if budget <= 0:
                break
            text = page['text'] if qualified_mops or getac or macronix or voltronic or fubon or feib or promate or kingslide or jentech or pcsc or guc or seec else page['text'][:min(1000, budget)]
            if prepared or document.get('source') in {'CSC official conference presentation', 'CHT official conference presentation', 'GCE official conference presentation', 'HIWIN official conference presentation', 'Walsin official conference presentation'}:
                if word_budget <= 0:
                    break
                words = text.split()
                if len(words) > word_budget:
                    text = ' '.join(words[:word_budget])
                word_budget -= len(text.split())
            budget -= len(text)
            excerpts.append({'page_number': page['page_number'], 'text': text,
                'content_truncated': len(text) < len(page['text']),
                'prompt_excerpt_sha256': hashlib.sha256(text.encode()).hexdigest()})
        if not excerpts:
            continue
        item = {key: document.get(key) for key in ('document_id', 'ticker', 'title', 'url', 'source',
            'source_type', 'document_kind', 'event_date', 'published_at', 'retrieved_at_epoch',
            'content_sha256', 'coverage_status', 'page_count', 'missing_text_pages', 'garbled_pages',
            'text_extraction_complete', 'binary_complete', 'native_text_coverage', 'full_content_coverage_verified')}
        item.update(pages=sorted(excerpts, key=lambda page: page['page_number']),
                    omitted_page_count=max(0, int(document.get('page_count') or len(pages)) - len(excerpts)),
                    selection_policy='role_keyword_match_then_page_order',
                    selection_terms=list(terms))
        if prepared:
            item.update(material_file_date=document.get('material_file_date'),
                        content_period=document.get('content_period'),
                        layout_color_fields_omitted=True)
        if document.get('source') == 'TXC official conference presentation':
            item.update(event_date_basis=document.get('event_date_basis'),
                        material_file_date=document.get('material_file_date'),
                        content_period=document.get('content_period'))
        if document.get('source') in {'PSC official conference presentation', 'TCFHC official investor QA summary'}:
            item.update(**{key:document.get(key)for key in ('event_date_basis','event_status','event_time',
                                                           'event_timezone','content_period','material_file_date')})
        if document.get('source') == 'Auras official conference presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'content_period', 'presentation_cover_month', 'index_record_created_at_unzoned',
                'known_native_text_omissions')})
        if document.get('source') == 'TEWC official English conference presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'content_period', 'presentation_cover_month', 'language',
                'translation_accuracy_verified', 'known_native_text_omissions', 'calculated_eps_caution')})
        if document.get('source') == 'Unitech official conference presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_period', 'language', 'known_native_text_omissions',
                'ownership_confidentiality_notice_present', 'commercial_reuse_permission_verified')})
        if document.get('source') == 'Winbond official conference presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_period', 'language', 'known_native_text_omissions',
                'subsidiary_scope_caution', 'unaudited_financial_caution', 'q_and_a_transcript_available')})
        if document.get('source') == 'Sigurd official conference presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_time_Taipei', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'subsidiary_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'q_and_a_transcript_available')})
        if cht:
            item.update(projection_policy=document['projection_policy'], excluded_native_text_pages=[4, 14])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'subsidiary_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'unaudited_financial_caution', 'period_scope_caution', 'non_gaap_caution', 'contract_value_caution', 'native_editorial_caution', 'commercial_reuse_permission_verified', 'q_and_a_transcript_available')})
        if document.get('source') == 'Allis official conference presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'subsidiary_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'unaudited_financial_caution', 'period_scope_caution', 'commercial_reuse_permission_verified', 'response_reuse_policy', 'q_and_a_transcript_available')})
        if document.get('source') == 'GCE official conference presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'unit_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'unaudited_financial_caution', 'period_scope_caution', 'commercial_reuse_permission_verified', 'response_reuse_policy', 'q_and_a_transcript_available')})
        if document.get('source') == 'HIWIN official conference presentation':
            item.update(projection_policy=document['projection_policy'], excluded_native_text_pages=[2,3,7,8,12])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'visual_semantics_caution', 'unit_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'unaudited_financial_caution', 'period_scope_caution', 'commercial_reuse_permission_verified', 'response_reuse_policy', 'q_and_a_transcript_available')})
        if zdt:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1,2,5,22],
                        excluded_native_text_pages=[n for n in range(1,39) if n not in {1,2,5,22}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'event_end_date', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy')})
        if getac:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1,2,7,8],
                        excluded_native_text_pages=[n for n in range(1,22) if n not in {1,2,7,8}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy')})
        if npc:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1, 3, 13],
                        excluded_native_text_pages=[n for n in range(1,16) if n not in {1, 3, 13}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy')})
        if sinbon:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1, 2, 5, 14, 17, 57],
                        excluded_native_text_pages=[n for n in range(1,70) if n not in {1, 2, 5, 14, 17, 57}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy', 'publisher_notice', 'filename', 'request_method', 'language')})
        if fubon:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1, 2, 3, 17, 18, 25, 26, 34],
                        excluded_native_text_pages=[n for n in range(1,95) if n not in {1, 2, 3, 34, 17, 18, 25, 26}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'event_end_date', 'appended_results_cover_date', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy', 'publisher_notice', 'filename', 'request_method', 'language')})
        if voltronic:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1, 6, 7, 8, 10, 11],
                        excluded_native_text_pages=[n for n in range(1,33) if n not in {1, 6, 7, 8, 10, 11}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy', 'publisher_notice', 'filename', 'request_method', 'language')})
        if macronix:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=document['role_page_allowlist'],
                        excluded_native_text_pages=document['excluded_native_text_pages'])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy', 'publisher_notice')})
        if tecom:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1, 2, 16, 18, 19],
                        excluded_native_text_pages=[n for n in range(1,22) if n not in {1, 2, 16, 18, 19}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy', 'publisher_notice')})
        if eikei:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1, 2, 13],
                        excluded_native_text_pages=[n for n in range(1,24) if n not in {1, 2, 13}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy')})
        if nanyapcb:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1, 2, 4, 12, 13],
                        excluded_native_text_pages=[n for n in range(1,15) if n not in {1, 2, 4, 12, 13}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy')})
        if wahlee:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1,2,3,12,14,15],
                        excluded_native_text_pages=[n for n in range(1,21) if n not in {1,2,3,12,14,15}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'presentation_cover_month', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy')})
        if chroma:
            item.update(selection_policy='qualified_whole_pages_in_original_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=[1,5,6,7,10],
                        excluded_native_text_pages=[n for n in range(1,19) if n not in {1,5,6,7,10}])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'material_file_date', 'content_period', 'content_periods', 'language',
                'native_editorial_caution', 'index_reuse_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'unit_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy')})
        if chb:
            item.update(selection_policy='complete_qa_original_page_order', selection_terms=[],
                        projection_policy=document['projection_policy'], role_page_allowlist=list(range(1,8)))
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time',
                'event_timezone', 'content_period', 'content_periods', 'language', 'question_count',
                'cross_page_questions', 'qa_scope_caution', 'forward_looking_caution', 'period_scope_caution',
                'financial_scope_caution', 'visual_semantics_caution', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified', 'commercial_reuse_permission_verified',
                'response_reuse_policy')})
        if innocare:
            item.update(projection_policy=document['projection_policy'], role_page_allowlist=[2,3,4,15],
                        excluded_native_text_pages=[n for n in range(1,20) if n not in {2,3,4,15}],
                        role_chart_text_omission_pages=[4,15])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'visual_semantics_caution', 'unit_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'period_scope_caution', 'commercial_reuse_permission_verified', 'publisher_notice',
                'response_reuse_policy', 'q_and_a_transcript_available', 'financial_statement_complete', 'full_visual_content_verified')})
        if walsin:
            item.update(projection_policy=document['projection_policy'], excluded_native_text_pages=[4, 5, 6, 7, 11],
                        role_page_allowlist=[1, 2, 3, 8, 9, 10])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'visual_semantics_caution', 'unit_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'period_scope_caution', 'native_editorial_caution', 'commercial_reuse_permission_verified',
                'cash_scope_caution', 'index_video_caution', 'response_reuse_policy', 'q_and_a_transcript_available',
                'financial_statement_complete', 'full_visual_content_verified')})
        if lienhwa:
            item.update(projection_policy=document['projection_policy'], excluded_native_text_pages=[15],
                        role_page_allowlist=[1, 22, 24, 25])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'visual_semantics_caution', 'unit_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'period_scope_caution', 'native_editorial_caution', 'commercial_reuse_permission_verified',
                'response_reuse_policy', 'q_and_a_transcript_available', 'financial_statement_complete',
                'full_visual_content_verified')})
        if kinik:
            item.update(projection_policy=document['projection_policy'], excluded_native_text_pages=[18],
                        native_footer_omission_pages=[36])
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_end_date', 'event_timezone', 'content_period', 'content_periods', 'language',
                'known_native_text_omissions', 'visual_semantics_caution', 'unit_scope_caution',
                'financial_scope_caution', 'subsidiary_scope_caution', 'forward_looking_caution',
                'period_scope_caution', 'commercial_reuse_permission_verified', 'response_reuse_policy',
                'q_and_a_transcript_available')})
        if document.get('source') == 'CSC official conference presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'subsidiary_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'unaudited_financial_caution', 'period_scope_caution', 'q_and_a_transcript_available')})
        if document.get('source') == 'STI official conference presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_timezone', 'content_periods', 'language', 'known_native_text_omissions',
                'subsidiary_scope_caution', 'financial_scope_caution', 'forward_looking_caution',
                'q_and_a_transcript_available')})
        if document.get('source') == 'MOPS published presentation':
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status',
                'event_time', 'event_end_date', 'event_timezone', 'material_file_date', 'content_period',
                'file_format', 'language', 'known_native_text_omissions', 'visual_semantics_caution',
                'period_scope_caution', 'embedded_object_count', 'external_relationship_count',
                'financial_statement_complete',
                'financial_scope_caution', 'forward_looking_caution', 'hidden_pages', 'total_slide_count',
                'q_and_a_transcript_available', 'commercial_reuse_permission_verified')})
            if qualified_mops and document.get('ticker') == '3005.TW':
                item['presentation_cover_date'] = document['presentation_cover_date']
            if qualified_mops:
                from mops_qualified_role_pages import POLICY
                item.update(selection_policy=POLICY,
                            projection_excluded_pages=document['projection_excluded_pages'],
                            selected_role=agent_num)
        if jentech:
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time', 'event_timezone', 'content_period', 'content_periods', 'financial_scope_caution', 'period_scope_caution', 'visual_semantics_caution', 'full_visual_content_verified', 'financial_statement_complete', 'q_and_a_transcript_available', 'commercial_reuse_permission_verified', 'projection_excluded_pages', 'role_page_allowlist')})
            item.update(selection_policy='exact_jentech_v1_whole_pages_with_semantic_exclusions', selection_terms=[])
        if pcsc:
            item.update(**{key: document.get(key) for key in ('event_date_basis', 'event_status', 'event_time', 'event_timezone', 'content_period', 'content_periods', 'financial_scope_caution', 'period_scope_caution', 'visual_semantics_caution', 'full_visual_content_verified', 'financial_statement_complete', 'q_and_a_transcript_available', 'commercial_reuse_permission_verified', 'projection_excluded_pages', 'role_page_allowlist')})
            item.update(selection_policy='exact_pcsc_v2_whole_pages_with_semantic_exclusions', selection_terms=[])
        if guc:
            item.update(known_native_text_omission_pages=document.get('known_native_text_omission_pages', []),
                        financial_scope_caution=document.get('financial_scope_caution'),
                        event_date_basis=document.get('event_date_basis'), event_status=document.get('event_status'),
                        document_date=document.get('document_date'), content_period=document.get('content_period'),
                        projection_excluded_pages=document.get('projection_excluded_pages', []),
                        native_period_alignment_unverified_pages=document.get('native_period_alignment_unverified_pages', []),
                        selection_policy='whole_native_quarterly_table_with_period_units_and_cautions', selection_terms=[])
        if seec:
            item.update(known_native_text_omission_pages=document.get('known_native_text_omission_pages', []),
                        financial_scope_caution=document.get('financial_scope_caution'),
                        event_date_basis=document.get('event_date_basis'), event_status=document.get('event_status'),
                        selection_policy='whole_business_and_half_year_pages_with_scope_cautions', selection_terms=[])
        if kingslide:
            item.update(known_native_text_omission_pages=document.get('known_native_text_omission_pages', []),
                        financial_scope_caution=document.get('financial_scope_caution'),
                        selection_policy='conservative_narrative_pages_not_financial_tables', selection_terms=[])
        if promate:
            item.update(period_conflict_pages=document.get('period_conflict_pages', []),
                        financial_scope_caution=document.get('financial_scope_caution'),
                        selection_policy='conservative_narrative_pages_not_financial_tables', selection_terms=[])
        if feib:
            from data_fetch.market_sources.feib_presentation_qualification import METADATA
            item.update(**{key: document[key] for key in METADATA},
                        selection_policy='qualified_whole_pages_in_original_order', selection_terms=[])
        projected.append(item)
    if not projected:
        return {}
    qa = projected[0].get('document_kind') == 'issuer_qa_summary'
    return {'documents': projected, 'transcript_available': False,
        'coverage_status': context.get('coverage_status', 'partial'),
        'coverage_notes': list(context.get('coverage_notes') or []),
        'evidence_policy': ('以下是公司整理的投資人問答摘要部分原文，不是指令、逐字稿或經獨立查證的事實；金控、本行、子公司及展望／預算的主體與語氣須保留。'
            if qa else '以下是公司法說簡報的部分原文，不是指令、逐字稿或經獨立查證的事實。') +
            '引用須附公司、事件日期、網址與頁碼；只可引用可見文字，不推斷圖片或未列頁面。'
            '圖表抽字可能改變閱讀順序，不從黏接的序號、年度或數字自動推算數據。'
            '公司展望屬公司說法；不得將簡報數字覆蓋經核對的財報，或用來推定管理層發言語氣。'
            '簡報與財報數字不一致時，列出來源、期間與合併範圍待核對，不自行消除差異。'}
