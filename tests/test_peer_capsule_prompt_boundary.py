"""Private transport manifests must not enter a model's financial input."""
from copy import deepcopy
from dataclasses import dataclass
import json

import pytest
from pydantic import BaseModel

from prompt_evidence import prompt_evidence_copy


@pytest.mark.parametrize('key', ['native_http_manifest', '_native_http_manifest',
                                'NATIVE_HTTP_MANIFEST'])
def test_capsule_metadata_removed_while_public_values_and_input_stay_exact(key):
    value = {'peer_discovery_results': [{'counterparty': {'ticker': '2723.TW'},
                                        'business_comparability_verified': False}],
             'source_audit': [{'raw_http_receipt': {
                 'raw_response_sha256': 'a' * 64,
                 'source_url': 'https://tw.stock.yahoo.com/quote/2727.TW/compare',
                 key: {'evidence_kind': 'private_acquisition_manifest',
                       'raw_response_sha256': 'b' * 64,
                       'raw_response_path': '/private/local/manifest.gz'}}}],
             'financial_value': {'value': 123.45, 'currency': 'TWD'}}
    before = deepcopy(value)
    projected = prompt_evidence_copy(value)
    receipt = projected['source_audit'][0]['raw_http_receipt']
    assert key not in receipt
    assert 'private_acquisition_manifest' not in json.dumps(projected)
    assert receipt['raw_response_sha256'] == 'a' * 64
    assert receipt['source_url'] == before['source_audit'][0]['raw_http_receipt']['source_url']
    assert projected['peer_discovery_results'] == before['peer_discovery_results']
    assert projected['financial_value'] == before['financial_value']
    assert value == before


@pytest.mark.parametrize('wrapper', ['model', 'dataclass', 'tuple'])
def test_capsule_removed_across_existing_supported_prompt_containers(wrapper):
    class Model(BaseModel):
        native_http_manifest: dict
        observed_value: int

    @dataclass
    class Record:
        native_http_manifest: dict
        observed_value: int

    data = {'native_http_manifest': {'evidence_kind': 'private_acquisition_manifest'},
            'observed_value': 7}
    value = Model(**data) if wrapper == 'model' else Record(**data) if wrapper == 'dataclass' else (data,)
    result = prompt_evidence_copy(value)
    assert 'native_http_manifest' not in json.dumps(result)
    assert (result[0] if wrapper == 'tuple' else result)['observed_value'] == 7
