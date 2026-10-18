"""Public boundary checks. Original private-data replay cases remain local."""

def test_verification_observation_fields_only_admit_fixed_enums():
    from provider_observation_details import observation_details
    assert observation_details({'verification_status': 'rejected', 'verification_stage': 'native_material', 'verification_reason': 'parser_timeout'}) == {'verification_status': 'rejected', 'verification_stage': 'native_material', 'verification_reason': 'parser_timeout'}
    assert observation_details({'verification_status': 'cookie=secret', 'verification_stage': '/private/file', 'verification_reason': 'raw document'}) == {}
