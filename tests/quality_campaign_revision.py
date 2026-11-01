"""One externally reviewed S1 repair; never rebase or replace the fixed roster.

The immutable revision maps every still-unused candidate slot to new backend
code while retaining inputs/profiles/runtime/harness. Old jobs keep old bytes.
The ledger records the exact revision reference before it can affect dispatch.
No model call, key read, automatic retry or budget refund occurs here.
"""
import copy

import quality_campaign_protocol as protocol
from quality_campaign_acceptance import _known_failure, early_stop, validate_evidence
from quality_campaign_runner import REFERENCES
from quality_campaign_wire import ReplayAbort


def binding_id(job_id):
    return 'revision2:' + protocol.sha(job_id.encode())[:40]


def _review(session, value, state):
    review = protocol.referenced(value['review'])
    failed = state['jobs'].get(value['failed_job_id'])
    protocol.require(failed is not None, 'Unknown revision failure')
    protocol.require(review.get('schema') == 'campaign.repair_review.v1'
        and review.get('decision') == 'approved' and isinstance(review.get('reviewer'), str)
        and bool(review['reviewer'].strip()), 'Identified external repair review required')
    expected = {'failed_job_id': value['failed_job_id'],
        'failure_review_sha256': state['reviews'].get(value['failed_job_id']),
        'old_candidate_code_sha256': failed['actual_hashes']['code_sha256'],
        'new_candidate_code_sha256': value['new_candidate_code_sha256'],
        'rubric_sha256': session.protocol['rubric_sha256']}
    protocol.require(expected['failure_review_sha256'] is not None
        and all(review.get(k) == v for k, v in expected.items()), 'Repair review failure/version/rubric mismatch')
    protocol.require(isinstance(review.get('root_cause'), str) and bool(review['root_cause'].strip()), 'Reviewed failure cause required')
    for name in ('repair_reproduction', 'full_non_live_regression', 'required_integration_lanes', 'independent_review'):
        check = review.get('checks', {}).get(name, {})
        protocol.require(check.get('status') == 'passed' and isinstance(check.get('evidence'), list)
            and bool(check['evidence']), 'Repair required check incomplete: ' + name)
        for ref in check['evidence']:
            protocol.reference(ref)
            protocol.require(protocol.sha(protocol.regular_bytes(ref['path'])) == ref['sha256'], 'Repair check evidence changed')
    return review


def _plans(session, value, *, verify):
    """Validate pinned manifests; execution verification only at registration.

    Historical candidate backends need not remain the current working tree.
    Their original manifest bytes and source/profile identities still must.
    """
    result = {}
    rows = {r['job_id']: r for r in session.protocol['samples']}
    protocol.require(isinstance(value['plans'], dict) and value['plans'], 'Complete repaired candidate mapping required')
    for job_id, ref in value['plans'].items():
        protocol.require(job_id in rows and rows[job_id]['role'] == 'candidate', 'Only original candidate slots may be revised')
        original = protocol.referenced(rows[job_id]['manifest'])
        frozen = protocol.referenced(ref)
        allowed = {'dev', 'code_files', 'binding_id'}
        protocol.require({k: v for k, v in frozen.items() if k not in allowed}
            == {k: v for k, v in original.items() if k not in allowed},
            'Repair changed frozen source/profile/harness/runtime/role')
        protocol.require(all(f in frozen for f in REFERENCES)
            and frozen['binding_id'] == binding_id(job_id), 'Explicit deterministic repair binding required')
        if verify:
            actual = protocol.FrozenJob(ref['path'], ref['sha256']).verify()
            protocol.require(protocol.frozen_mode_roles(frozen) == rows[job_id]['required_roles'], 'Repair changed required mode roles')
        else:
            actual = {'code_sha256': value['new_candidate_code_sha256'],
                'source_sha256': rows[job_id]['source_sha256'], 'route_sha256': rows[job_id]['route_sha256']}
        protocol.require(actual == {'code_sha256': value['new_candidate_code_sha256'],
            'source_sha256': rows[job_id]['source_sha256'], 'route_sha256': rows[job_id]['route_sha256']},
            'Repair must use exactly one new code and the original source/routes')
        result[binding_id(job_id)] = {'parent_binding_id': job_id, **actual}
    return result


def _header(session, value):
    protocol.require(set(value) == {'schema', 'campaign_id', 'failed_job_id', 'original_protocol_sha256',
        'new_candidate_code_sha256', 'plans', 'review'}, 'Explicit complete candidate revision required')
    protocol.require(value['schema'] == 'campaign.candidate_revision.v1'
        and value['campaign_id'] == session.protocol['campaign_id']
        and value['original_protocol_sha256'] == protocol.sha(protocol.encoded(session.protocol)),
        'Candidate revision belongs to another campaign/protocol')
    protocol.identifier(value['failed_job_id'])
    protocol.digest(value['new_candidate_code_sha256'])


def load_revision(session):
    """Every resume validates the original immutable pointer and ledger binding."""
    state = session.ledger.snapshot()
    event = state['candidate_revision']
    pointer = session.root / 'candidate-revision.json'
    if event is None and not pointer.exists() and not pointer.is_symlink(): return None
    protocol.require(event is not None, 'Unbound candidate revision needs verified recovery; no automatic adoption')
    protocol.private_path(pointer)
    ref = protocol.read_json(protocol.regular_bytes(pointer))
    protocol.reference(ref)
    protocol.require(ref['sha256'] == event['repair_evidence_sha256'], 'Candidate revision pointer differs from ledger')
    value = protocol.referenced(ref)
    _header(session, value)
    protocol.require(value['failed_job_id'] == event['failed_job_id'], 'Repaired failure identity changed')
    protocol.require(_plans(session, value, verify=False) == event['revisions'], 'Durable repair mapping differs from evidence')
    # Reconstruct the roster at registration, not the current unused set: new
    # version jobs legitimately become spent after this event. A low-level
    # append of one matching binding is not whole-campaign repair authority.
    spent_before = set()
    for item in session.ledger.events():
        if item['kind'] == 's1_candidate_revision': break
        if item['kind'] == 'job_reserve': spent_before.add(item['payload']['job_id'])
    remaining = [r for r in session.protocol['samples'] if r['role'] == 'candidate' and r['job_id'] not in spent_before]
    protocol.require(set(value['plans']) == {r['job_id'] for r in remaining}
        and sum(r['stage'] == 'S1' and r['expected'] == 'qualified' for r in remaining) >= 2,
        'Durable repair must map the whole remaining candidate roster')
    repair = _review(session, value, state)
    failed_id = value['failed_job_id']
    original = next((r for r in session.protocol['samples'] if r['job_id'] == failed_id), None)
    protocol.require(failed_id in spent_before and original is not None and original['stage'] == 'S1'
        and state['jobs'][failed_id]['binding_id'] == failed_id, 'Repair failure must belong to the original S1 candidate')
    pointer = session.root / ('review-' + failed_id + '.json')
    protocol.private_path(pointer)
    raw = protocol.regular_bytes(pointer)
    protocol.require(protocol.sha(raw) == state['reviews'].get(failed_id), 'Original failure review binding changed')
    observed = session._result(failed_id, protocol.referenced(protocol.read_json(raw)), sample=original)
    protocol.require(not validate_evidence(session.protocol['samples'], {failed_id: observed})
        and observed['failure_review']['complete'] and _known_failure(original, observed)
        and observed['root_cause'] == repair['root_cause'], 'Durable revision lacks genuine reviewed failure evidence')
    return value


def effective_sample(session, original):
    row = copy.deepcopy(original)
    # Public operations refresh this once under the anchor lock (results also
    # refreshes for standalone reads), avoiding O(roster^2) file verification.
    value = session._revision
    if value is not None and row['job_id'] in value['plans']:
        row['manifest'] = copy.deepcopy(value['plans'][row['job_id']])
        row['binding_id'] = binding_id(row['job_id'])
    return row


def register_revision(session, ref):
    """Caller holds original anchor lock. Partial durable writes fail closed."""
    try:
        session._s0_review()
        session.ledger.check()
        state = session.ledger.snapshot()
        protocol.require(load_revision(session) is None, 'Only one repaired candidate version is permitted')
        protocol.require(state['stage'] == 'S1' and state['stages'].get('S1') == 'open'
            and not any(j['status'] == 'active' for j in state['jobs'].values())
            and not any(b['ended_ms'] is None for b in state['batches'].values()), 'Repair requires cleaned up open S1')
        value = protocol.referenced(ref)
        _header(session, value)
        results = session.results()
        protocol.require(set(state['jobs']).issubset(results), 'All spent jobs require complete external review before repair')
        stops = early_stop(session.protocol['samples'], results)
        if stops:
            session.ledger.stop('acceptance_safety_stop', evidence_sha256=protocol.sha(protocol.encoded(stops)))
            raise ReplayAbort('Repair cannot bypass campaign safety stop')
        failed = state['jobs'].get(value['failed_job_id'])
        observed = results.get(value['failed_job_id'])
        original = session._sample(value['failed_job_id'])
        protocol.require(failed is not None and failed['stage'] == 'S1' and failed['status'] in ('failed', 'completed')
            and observed is not None and observed['failure_review']['complete']
            and _known_failure(original, observed), 'Repair needs genuine externally reviewed S1 failure')
        remaining = [r for r in session.protocol['samples'] if r['role'] == 'candidate' and r['job_id'] not in state['jobs']]
        protocol.require(sum(r['stage'] == 'S1' and r['expected'] == 'qualified' for r in remaining) >= 2,
            'Insufficient original S1 qualified slots for two consecutive second-version results')
        protocol.require(isinstance(value['plans'], dict) and set(value['plans']) == {r['job_id'] for r in remaining},
            'Repair must map every and only unused candidate slot across S1-S4')
        review = _review(session, value, state)
        protocol.require(review['root_cause'] == observed['root_cause'], 'Repair cause differs from failed report review')
        protocol.require(value['new_candidate_code_sha256'] not in
            {v['code_sha256'] for v in state['effective_bindings'].values()}, 'Repair requires one distinct new code version')
        revisions = _plans(session, value, verify=True)
        # The reference must be present before the ledger can authorize dispatch.
        # A crash between the two writes leaves evidence, never an implicit reset.
        protocol.exclusive_json(session.root / 'candidate-revision.json', ref)
        session.ledger.register_s1_candidate_revision(revisions=revisions,
            failed_job_id=value['failed_job_id'], repair_evidence_sha256=ref['sha256'],
            reviewed_quality_failure_sha256=state['reviews'][value['failed_job_id']])
        session._revision = load_revision(session)
        return copy.deepcopy(value)
    except (KeyError, TypeError, ValueError) as error:
        raise ReplayAbort('Invalid repaired candidate evidence: ' + type(error).__name__) from None
