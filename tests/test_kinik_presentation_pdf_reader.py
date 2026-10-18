"""Public boundary checks. Original private-data replay cases remain local."""

def test_glyph_contract_is_fresh_and_not_shared_mutable_state():
    import kinik_presentation_pdf_reader as module
    value = module.glyph_evidence()
    value['source_cids']['U+F06C'] = 0
    value['occurrences_by_page']['4']['U+F06C'] = 999
    assert module.glyph_evidence()['source_cids']['U+F06C'] == 122
    assert module.glyph_evidence()['occurrences_by_page']['4']['U+F06C'] == 5
