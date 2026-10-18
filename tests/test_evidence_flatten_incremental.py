from pathlib import Path
FIXTURES = Path(__file__).parent / 'fixtures'
"""Public boundary checks. Original private-data replay cases remain local."""
import copy, random
import evidence_exit_gate as gate
from evidence_claim_boundaries import with_match_normalization_cache
namespace = dict(vars(gate))
exec((FIXTURES / 'evidence_flatten_preoptimization.py.txt').read_text(), namespace)
legacy = namespace['flatten_snapshot_numbers']

@with_match_normalization_cache
def compare(snapshot):
    before = copy.deepcopy(snapshot)
    expected = legacy(snapshot, eligible_only=True)
    actual = gate.flatten_snapshot_numbers(snapshot, eligible_only=True)
    assert actual == expected and snapshot == before
    assert gate.flatten_snapshot_numbers(snapshot) == legacy(snapshot)

def test_complex_keys_boundaries_dates_and_unicode_do_not_bypass_exclusions():
    snapshot = {'data': {'year': 2026, 'Year': 123, 'dates': [1, 2], 'a.timestamp.amount': 10, 'generated_at': [2, 3], 'checked_at_extra': 8, '技術': {'日均值': 12}, 'as_of.extra': 5, 'x': {'confidence': {'score': 3}}, 'foo[0].date': 3, 'source_record_archive': {'nested': [1, 2]}, 'price_history': {'dates': ['2026-10-01', '2026-10-02'], 'prices': [3, 4]}}, 'oos_evaluation_inputs': {'data': {'financial': {'amount': 123}}}}
    compare(snapshot)

def test_generated_nested_key_paths_match_without_evidence_cache():
    random.seed(42)
    keys = ['price', 'data', 'timestamp', 'TimeStamp', 'year', 'years', 'a.b', 'a[0]', '_confidence', 'confidence', 'as_of', '股數', 'source', 'archive', 'foo-bar']

    def build(depth):
        if depth == 0:
            return random.choice([None, True, 1, 3.25, '12.5 TWD'])
        return {random.choice(keys): [build(depth - 1), build(depth - 1)] for _ in range(3)}
    for _ in range(20):
        compare(build(3))
