"""Fixed campaign roster and create-once/resume-existing coordinator boundary.

The caller must keep the originally approved anchor path. This does not defend
against the host owner deleting all evidence or deliberately choosing a new
authority/anchor. No source/billing approval is fabricated, no stage passes from
hash presence, and imports/create/resume make no model or service calls.
"""
import ast
import copy
from contextlib import contextmanager
from datetime import date
import fcntl
import os
from pathlib import Path
import re
import stat
import subprocess
import canary_release_policy

from quality_campaign_budget import CampaignBudget, manifest_identity
from quality_campaign_runner import (FrozenJob, encoded, exclusive_json, ledger_pin,
    read_json, regular_bytes, reopen_ledger, sha, execute_reserved_job, reserved_job_storage, private_artifacts_match)
from quality_campaign_wire import ReplayAbort

BASELINE_REVISION = '758242290e795146520f58f68ffa113cac35e52c'
MODES = ('v1', 'v2', 'v3', 'v4')
STAGES = ('S1', 'S2', 'S3', 'S4')
COUNTS = {'S1': 4, 'S2': 24, 'S3': 120, 'S4': 4}


def rubric_digest():
    # Bind executable rules, not a label that stays unchanged when rules drift.
    return sha(regular_bytes(Path(__file__).resolve().with_name('quality_campaign_acceptance.py')))


def require(condition, message):
    if not condition: raise ReplayAbort(message)


def digest(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'Explicit SHA256 required')
    return value


def identifier(value):
    require(isinstance(value, str) and re.fullmatch('[A-Za-z0-9_.:-]{1,160}', value)
            and value not in ('.', '..'), 'Explicit safe identifier required')
    return value


def reference(value):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'Pinned file reference required')
    require(isinstance(value['path'], str) and Path(value['path']).is_absolute()
            and '..' not in Path(value['path']).parts, 'Absolute reference required')
    digest(value['sha256'])
    return value


def referenced(value):
    reference(value)
    raw = regular_bytes(value['path'])
    require(sha(raw) == value['sha256'], 'Referenced evidence changed')
    return read_json(raw)


def validate_protocol(value):
    """Validate the complete roster BEFORE observations, not after good results."""
    try:
        require(value['schema'] == 'campaign.protocol.v1', 'Unknown campaign protocol')
        identifier(value['campaign_id'])
        require(value['baseline_revision'] == BASELINE_REVISION, 'Unapproved baseline revision')
        require(value['rubric_sha256'] == rubric_digest(), 'Acceptance rubric changed')
        rows = value['samples']
        require(isinstance(rows, list) and len(rows) == 152, 'All 152 fixed slots must be preregistered')
        require(len({r['job_id'] for r in rows}) == len(rows), 'Duplicate job identity')
        for row in rows:
            for field in ('job_id', 'sample_id', 'ticker'): identifier(row[field])
            require(row['stage'] in STAGES and row['mode'] in MODES, 'Invalid stage or mode')
            require(row['role'] in ('candidate', 'baseline'), 'Invalid code role')
            require(row['expected'] in ('qualified', 'limited', 'diagnostic', 'reject'), 'Invalid expected disposition')
            require(type(row['financial']) is bool and type(row['fulltext_review']) is bool, 'Explicit boolean cohort labels required')
            roles = row['required_roles']
            require(isinstance(roles, list) and roles and all(type(r) is int and 1 <= r <= 99 for r in roles)
                    and len(set(roles)) == len(roles), 'Frozen required-role list required')
            require(isinstance(row['industry'], str) and bool(row['industry'].strip()), 'Reviewed industry required')
            require(date.fromisoformat(row['cutoff']).isoformat() == row['cutoff'], 'ISO data cutoff required')
            for field in ('source_sha256', 'route_sha256'): digest(row[field])
            reference(row['manifest'])
            require(row['stage'] == 'S2' or row['role'] == 'candidate', 'Baseline only belongs to S2')
            require(row['stage'] != 'S1' or row['mode'] == 'v4', 'S1 only v4')
            require(row['stage'] not in ('S3', 'S4') or row['expected'] == 'qualified', 'S3/S4 require qualified inputs')
            require(not row['fulltext_review'] or row['stage'] == 'S3', 'Fulltext sample selection only belongs to S3')
        require([r['stage'] for r in rows] == [s for s in STAGES for _ in range(COUNTS[s])], 'Fixed stage counts and order required')
        groups = {s: [r for r in rows if r['stage'] == s] for s in STAGES}
        require(sum(r['expected'] == 'qualified' for r in groups['S1']) >= 2, 'Two prequalified S1 inputs required')
        require(len({(r['ticker'], r['cutoff']) for r in groups['S1'] if r['expected'] == 'qualified'}) >= 2,
                'S1 needs two distinct prequalified inputs')
        s2 = groups['S2']
        require(len({r['sample_id'] for r in s2}) == 12, 'Twelve fixed original S2 pairs required')
        for i in range(0, 24, 2):
            left, right = s2[i:i+2]
            require({left['role'], right['role']} == {'baseline', 'candidate'}, 'Adjacent interleaved S2 pair required')
            for field in ('sample_id', 'mode', 'ticker', 'cutoff', 'industry', 'financial',
                          'source_sha256', 'route_sha256', 'expected'):
                require(left[field] == right[field], 'S2 pair source/profile/disposition mismatch')
        excluded = {(r['ticker'], r['cutoff']) for r in groups['S1'] + s2}
        for mode in MODES:
            require(sum(r['mode'] == mode for r in s2) == 6, 'S2 needs three pairs per mode')
            cohort = [r for r in groups['S3'] if r['mode'] == mode]
            require(len(cohort) == 30 and len({(r['ticker'], r['cutoff']) for r in cohort}) == 30,
                    'S3 needs 30 distinct ticker/cutoff pairs per mode')
            require(len({r['sample_id'] for r in cohort}) == 30, 'Duplicate S3 sample identity')
            require(not excluded.intersection((r['ticker'], r['cutoff']) for r in cohort), 'S1/S2 input cannot enter S3')
            require(len({r['ticker'] for r in cohort}) >= 10 and len({r['cutoff'] for r in cohort}) >= 3,
                    'Insufficient S3 ticker/date diversity')
            require(len({r['industry'].strip().casefold() for r in cohort}) >= 5 and {r['financial'] for r in cohort} == {True, False},
                    'Insufficient S3 reviewed industry coverage')
            require(sum(r['fulltext_review'] for r in cohort) == 5, 'Five predetermined fulltext reviews per mode required')
            require(sum(r['mode'] == mode for r in groups['S4']) == 1, 'S4 one canary per mode required')
        return copy.deepcopy(value)
    except (KeyError, TypeError, ValueError) as error:
        raise ReplayAbort('Invalid preregistration: ' + type(error).__name__) from None


def baseline_checkout(dev):
    """Read-only provenance, never switch/modify/start the formal checkout."""
    dev = Path(dev)
    require(dev != Path('/Volumes/X10 Pro Mac/stock-agent'), 'Use an isolated baseline, never formal checkout')
    def git(*args):
        return subprocess.run(['/usr/bin/git', '-C', str(dev), *args], check=True,
            capture_output=True, env={'PATH': '/usr/bin:/bin', 'GIT_OPTIONAL_LOCKS': '0'}, timeout=10).stdout.decode().strip()
    require(Path(git('rev-parse', '--show-toplevel')).resolve() == dev,
            'Baseline must be the actual isolated checkout root')
    require(git('rev-parse', 'HEAD') == BASELINE_REVISION, 'Baseline revision mismatch')
    require(not git('status', '--porcelain', '--untracked-files=all', '--', 'backend'), 'Baseline backend is not clean')


def frozen_mode_roles(frozen):
    """Read a literal contract from exact frozen bytes without executing code."""
    relative = 'backend/pipeline_modes.py'
    raw = regular_bytes(Path(frozen['dev']) / relative)
    require(sha(raw) == frozen['code_files'].get(relative), 'Frozen mode contract changed')
    try:
        tree = ast.parse(raw)
        values = [ast.literal_eval(node.value) for node in tree.body if
            isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == 'PIPELINE_DEFINITIONS'
            or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PIPELINE_DEFINITIONS' for t in node.targets)]
        require(len(values) == 1, 'Single literal frozen mode registry required')
        return list(values[0][frozen['mode']]['agents'])
    except (KeyError, TypeError, ValueError, SyntaxError):
        raise ReplayAbort('Frozen mode registry cannot be read as a literal contract') from None


def verify_plans(value):
    bindings, versions, baseline_roots = {}, {'candidate': set(), 'baseline': set()}, set()
    paired = {}
    for row in value['samples']:
        ref = row['manifest']
        plan = FrozenJob(ref['path'], ref['sha256'])
        actual, frozen = plan.verify(), plan.manifest
        for field in ('campaign_id',):
            require(frozen[field] == value[field], 'Frozen campaign identity mismatch')
        require(frozen['binding_id'] == row['job_id'], 'Each planned job needs its own immutable binding')
        for field in ('stage', 'mode', 'role'):
            require(frozen[field] == row[field], 'Frozen job role/scope mismatch')
        require(frozen['purpose'] == ('qualification' if row['expected'] == 'qualified' else 'diagnostic'), 'Source purpose mismatch')
        require(frozen_mode_roles(frozen) == row['required_roles'], 'Preregistered roles differ from frozen mode contract')
        require(all(actual[f] == row[f] for f in ('source_sha256', 'route_sha256')), 'Frozen sample identity mismatch')
        source = referenced(frozen['source_review'])
        for field in ('ticker', 'cutoff', 'industry', 'financial'):
            require(source.get(field) == row[field] and type(source.get(field)) is type(row[field]), 'Reviewed source cohort metadata missing/mismatched')
        require(isinstance(source.get('evidence_refs'), list) and source['evidence_refs'], 'Source/PIT/industry evidence required')
        for ref in source['evidence_refs']:
            reference(ref)
            require(sha(regular_bytes(ref['path'])) == ref['sha256'], 'Source qualification evidence changed')
        if row['role'] == 'baseline' and frozen['dev'] not in baseline_roots:
            baseline_checkout(frozen['dev'])
            baseline_roots.add(frozen['dev'])
        if row['stage'] == 'S2':
            # Pairing cannot silently change environment, quotas or generation policy.
            pair_profile = {f: frozen[f]['sha256'] for f in ('routes', 'environment', 'billing_review', 'reservation_review', 'policies')}
            old = paired.setdefault(row['sample_id'], pair_profile)
            require(old == pair_profile, 'S2 resources/generation profile differs between versions')
        bindings[row['job_id']] = actual
        versions[row['role']].add(actual['code_sha256'])
    require(all(len(v) == 1 for v in versions.values()), 'One initial candidate and one baseline code identity required')
    require(versions['candidate'] != versions['baseline'], 'Baseline/candidate must be distinct reviewed versions')
    return bindings


def private_path(path, *, directory=False):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path, 'Absolute nonsymlink campaign path required')
    info = path.lstat()
    require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == (0o700 if directory else 0o600)
            and (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1),
            'Owned private campaign file/directory required')
    return {'device': info.st_dev, 'inode': info.st_ino}


def implementation_digest():
    return sha(encoded({name: sha(regular_bytes(Path(__file__).resolve().with_name(name))) for name in
        ('quality_campaign_protocol.py', 'quality_campaign_acceptance.py',
         'quality_campaign_revision.py', 'quality_campaign_statistics.py')}))


class Campaign:
    """Create once, then only reopen that durable anchor. No automatic reset."""
    @classmethod
    def create(cls, anchor, root, value):
        canary_release_policy.require_canary_enabled()
        anchor, root = Path(anchor), Path(root)
        require(anchor.is_absolute() and anchor.parent.resolve() == anchor.parent
                and root.is_absolute() and root.parent.resolve() == root.parent,
                'Existing absolute nonsymlink parent required')
        require(not anchor.exists() and not anchor.is_symlink() and not root.exists() and not root.is_symlink(),
                'Campaign bootstrap is create-once; use original anchor to resume')
        protocol = validate_protocol(value)
        bindings = verify_plans(protocol)  # No root/anchor consumed for incomplete prerequisites.
        claim = {'schema': 'campaign.anchor.v1', 'campaign_id': protocol['campaign_id'],
                 'root': str(root), 'protocol_sha256': sha(encoded(protocol)),
                 'implementation_sha256': implementation_digest()}
        try:
            exclusive_json(anchor, claim)  # Permanent claim BEFORE ledger creation.
            root.mkdir(mode=0o700)
            root_pin = private_path(root, directory=True)
            exclusive_json(root / 'protocol.json', protocol)
            ledger = CampaignBudget(root / 'campaign.sqlite3', manifest_identity(protocol['campaign_id'], bindings), allowed_bindings=bindings)
            exclusive_json(root / 'bootstrap.json', {'anchor_sha256': sha(regular_bytes(anchor)),
                'anchor_pin': private_path(anchor), 'root_pin': root_pin, 'ledger_pin': ledger_pin(ledger)})
        except OSError as error:
            raise ReplayAbort('Bootstrap incomplete; original claim is retained: ' + type(error).__name__) from None
        return cls.resume(anchor)

    @classmethod
    def resume(cls, anchor):
        try:
            self = cls()
            self.anchor = Path(anchor)
            pin = private_path(self.anchor)
            raw = regular_bytes(self.anchor)
            claim = read_json(raw)
            require(claim['schema'] == 'campaign.anchor.v1', 'Unknown campaign anchor')
            self.root = Path(claim['root'])
            root_pin = private_path(self.root, directory=True)
            private_path(self.root / 'bootstrap.json')
            boot = read_json(regular_bytes(self.root / 'bootstrap.json'))
            require(boot['anchor_sha256'] == sha(raw) and boot['anchor_pin'] == pin
                    and boot['root_pin'] == root_pin, 'Campaign anchor or root identity drift')
            require(claim['implementation_sha256'] == implementation_digest(), 'Preregistered controller/rubric changed')
            private_path(self.root / 'protocol.json')
            raw = regular_bytes(self.root / 'protocol.json')
            require(sha(raw) == claim['protocol_sha256'], 'Preregistered roster changed')
            self.protocol = validate_protocol(read_json(raw))
            require(self.protocol['campaign_id'] == claim['campaign_id'], 'Campaign identity mismatch')
            self.ledger = reopen_ledger(boot['ledger_pin'])
            require(self.ledger.identity['campaign_id'] == claim['campaign_id'], 'Wrong campaign ledger')
            from quality_campaign_revision import load_revision
            self._revision = load_revision(self)
            return self
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise ReplayAbort('Existing campaign cannot resume: ' + type(error).__name__) from None

    @contextmanager
    def lock(self):
        """Serialize coordinators on the original immutable anchor inode."""
        fd = os.open(self.anchor, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise ReplayAbort('Another campaign coordinator holds the anchor') from None
            require((os.fstat(fd).st_dev, os.fstat(fd).st_ino) ==
                    (self.anchor.stat().st_dev, self.anchor.stat().st_ino), 'Anchor changed during lock')
            refreshed = self.resume(self.anchor)
            self.ledger, self.protocol, self._revision = refreshed.ledger, refreshed.protocol, refreshed._revision
            yield
        finally:
            os.close(fd)

    def _s0_review(self):
        ref = self.protocol.get('s0_review')
        require(ref is not None, 'S0 review and original regression evidence are not complete')
        review = referenced(ref)
        require(review.get('schema') == 'campaign.s0_review.v1' and review.get('decision') == 'approved', 'S0 not approved by evidence review')
        require(review.get('roster_sha256') == sha(encoded(self.protocol['samples']))
                and review.get('rubric_sha256') == self.protocol['rubric_sha256'], 'S0 review applies to another roster/rubric')
        candidates = {v['code_sha256'] for k, v in self.ledger.bindings.items()
                      if next(r for r in self.protocol['samples'] if r['job_id'] == k)['role'] == 'candidate'}
        require(candidates == {review.get('candidate_code_sha256')}, 'S0 candidate mismatch')
        checks = review.get('checks', {})
        for name in ('full_non_live_regression', 'required_integration_lanes', 'skips_classified',
                     'independent_review', 'maintenance_isolation'):
            check = checks.get(name, {})
            require(check.get('status') == 'passed' and isinstance(check.get('evidence'), list)
                    and bool(check['evidence']), 'S0 required check not established: ' + name)
            for evidence in check['evidence']:
                reference(evidence)
                require(sha(regular_bytes(evidence['path'])) == evidence['sha256'], 'S0 verification evidence changed')
        originals = review.get('original_regression')
        expected = [{'mode': r['mode'], 'source_sha256': r['source_sha256']} for r in self.protocol['samples']
                    if r['stage'] == 'S2' and r['role'] == 'baseline']
        require(originals == expected, 'Original 12 regression sources not independently confirmed')
        return review

    def _sample(self, job_id):
        rows = [r for r in self.protocol['samples'] if r['job_id'] == job_id]
        require(len(rows) == 1, 'Unregistered job')
        from quality_campaign_revision import effective_sample
        return effective_sample(self, rows[0])

    def register_candidate_revision(self, revision_ref):
        with self.lock():
            from quality_campaign_revision import register_revision
            return register_revision(self, revision_ref)

    def _result(self, job_id, review, *, sample=None):
        """Bind trusted external content assessment to actual private artifacts.

        Content truth is NOT inferred from these boolean review fields. The
        independent reviewer must inspect the cited source/report positions.
        Mechanical execution/usage/model facts cannot be overwritten by review.
        """
        row = self._sample(job_id) if sample is None else sample
        state = self.ledger.snapshot()
        job = state['jobs'].get(job_id)
        require(job is not None and job['status'] != 'active', 'Review requires terminal owned job')
        output = self.root / job_id
        parent_raw = regular_bytes(output / 'parent-receipt.json')
        parent = read_json(parent_raw)
        require(parent.get('job_id') == job_id and parent.get('manifest_sha256') == row['manifest']['sha256']
                and parent.get('formal_publication') is False and parent.get('qualified_for_campaign') is False,
                'Parent receipt does not belong to this frozen private job')
        cleanup_raw = regular_bytes(output / ('watchdog-' + job_id + '.cleanup.json'))
        cleanup = read_json(cleanup_raw)
        require(sha(cleanup_raw) == parent.get('cleanup_sha256')
                and cleanup.get('job_id') == job_id and cleanup.get('ledger_binding_sha256') == self.ledger.binding
                and cleanup.get('deadline_ms') == job['deadline_ms'] and cleanup.get('guardian_reaped') is True
                and cleanup.get('process_group_absent') is True, 'Owned cleanup evidence mismatch')
        outcome_path = output / 'outcome.json'
        outcome_raw = regular_bytes(outcome_path) if outcome_path.exists() else None
        require((sha(outcome_raw) if outcome_raw else None) == parent.get('outcome_sha256'), 'Outcome evidence changed')
        outcome = read_json(outcome_raw) if outcome_raw else {}
        require(not outcome or outcome.get('job_id') == job_id and outcome.get('mode') == row['mode'], 'Wrong outcome identity')
        artifact_verified = private_artifacts_match(output, outcome)
        if parent.get('status') == 'private_pipeline_completed' and not artifact_verified:
            self.ledger.stop('artifact_integrity_risk', evidence_sha256=sha(parent_raw))
            raise ReplayAbort('Previously completed artifact bytes changed')
        completed = (job['status'] == 'completed' and parent.get('status') == 'private_pipeline_completed'
                     and outcome.get('status') == 'published' and artifact_verified)
        # Partially persisted files are not proof of complete success, but they
        # DO defeat a claim that a must-reject case produced no publication.
        reports = output / 'reports'
        published = outcome.get('status') == 'published' or reports.exists() and any(p.is_file() for p in reports.rglob('*'))
        require(review.get('schema') == 'campaign.content_review.v1' and review.get('job_id') == job_id
                and isinstance(review.get('reviewer'), str) and bool(review['reviewer'].strip()), 'External identified content review required')
        prompt_path = output / 'prompts.jsonl'
        prompt_raw = regular_bytes(prompt_path) if prompt_path.exists() else None
        if ('prompts_sha256' not in parent
                or parent['prompts_sha256'] != (sha(prompt_raw) if prompt_raw is not None else None)):
            self.ledger.stop('configuration_evidence_integrity_risk', evidence_sha256=sha(parent_raw))
            raise ReplayAbort('Generation configuration evidence differs from terminal parent receipt')
        require(review.get('evidence') == {'source_sha256': row['source_sha256'],
            'parent_receipt_sha256': sha(parent_raw), 'outcome_sha256': parent.get('outcome_sha256'),
            'artifacts_sha256': sha(encoded(outcome.get('artifacts'))),
            'prompts_sha256': sha(prompt_raw) if prompt_raw is not None else None,
            'rubric_sha256': self.protocol['rubric_sha256']}, 'Content review does not bind these source/report bytes')
        assessment = copy.deepcopy(review.get('assessment', {}))
        require(isinstance(assessment, dict), 'Content assessment required')
        # The external reviewer cites byte ranges, not arbitrary URL labels or
        # a self-reported "reviewed" flag. Source is the lossless canonical JSON
        # view of data_snapshot ONLY, never old analyses in database-job.json.
        # This verifies locations/integrity, not semantic judgement.
        frozen = referenced(row['manifest'])
        source_ref = frozen['source']
        require(source_ref['sha256'] == row['source_sha256'], 'Reviewed source is not the preregistered input')
        source_raw = regular_bytes(source_ref['path'])
        if sha(source_raw) != row['source_sha256']:
            self.ledger.stop('source_integrity_risk', evidence_sha256=sha(source_raw))
            raise ReplayAbort('Reviewed source bytes changed; campaign stopped')
        source_data = read_json(source_raw).get('data_snapshot')
        require(isinstance(source_data, dict) and bool(source_data), 'Frozen source data_snapshot missing')
        documents = {'source': encoded(source_data), 'outcome': outcome_raw or parent_raw}
        if artifact_verified:
            for key, item in outcome['artifacts'].items():
                documents[key] = regular_bytes(output / 'reports' / item['key'])
        positions = review.get('positions')
        require(isinstance(positions, dict) and bool(positions), 'Concrete source/report review positions required')
        cited = set()
        for label, position in positions.items():
            identifier(label)
            require(isinstance(position, dict) and set(position) == {'document', 'start', 'end', 'sha256'}, 'Explicit reviewed byte range required')
            data = documents.get(position['document'])
            require(data is not None and type(position['start']) is int and type(position['end']) is int
                    and 0 <= position['start'] < position['end'] <= len(data), 'Review position is outside original evidence')
            require(sha(data[position['start']:position['end']]) == position['sha256'], 'Reviewed excerpt bytes changed')
            cited.add(position['document'])
        if assessment.get('source_decision_reviewed') is True:
            require('source' in cited and (not published or bool({'html_key', 'md_key', 'data_key'} & cited)),
                    'Source and published decision positions must both be cited')
        for name in ('independent_review', 'failure_review'):
            item = assessment.get(name, {})
            if item.get('complete') is not True: continue
            refs = item.get('evidence_refs')
            lists = list(refs.values()) if name == 'independent_review' and isinstance(refs, dict) else [refs]
            require(bool(lists) and all(isinstance(refs, list) and refs and all(label in positions for label in refs)
                    for refs in lists), 'Completed review references unknown evidence positions')
        attempts = [a for a in state['attempts'].values() if a['job_id'] == job_id and a['http']]
        tokens = sum(a['actual_tokens'] for a in attempts) if attempts and all(a['final_tokens'] and a['actual_tokens'] is not None for a in attempts) else None
        events = self.ledger.events()
        start = next(e['at_ms'] for e in events if e['kind'] == 'job_reserve' and e['payload']['job_id'] == job_id)
        end = next(e['at_ms'] for e in events if e['kind'] == 'job_finish' and e['payload']['job_id'] == job_id)
        prompts = {}
        if prompt_raw is not None:
            for line in prompt_raw.splitlines():
                item = read_json(line)
                prompts[item['attempt_id']] = item.get('config')
        calls = {r['attempt_id']: r for r in outcome.get('provider_transport_calls', [])}
        if row['expected'] == 'qualified':
            logical = {key for key, a in state['attempts'].items() if a['job_id'] == job_id and a['transport']}
            physical = {key for key, a in state['attempts'].items() if a['job_id'] == job_id and a['http']}
            completed_calls = {http['attempt_id'] for http in outcome.get('http_attempts', [])
                if http.get('http_id') in physical and http.get('attempt_id') in logical
                and http.get('response_complete') is True}
            completed_roles = {call.get('agent_num') for key, call in calls.items()
                if key in completed_calls and call.get('completed_response') is True and call.get('status') == 'completed'
                and type(call.get('agent_num')) is int}
            assessment['required_roles_valid'] = (assessment.get('required_roles_valid') is True
                and set(row['required_roles']).issubset(completed_roles))
        models = []
        for http in outcome.get('http_attempts', []):
            call = calls.get(http.get('attempt_id'), {})
            config = prompts.get(http.get('attempt_id'))
            # Schema/prompt content may intentionally differ between baseline
            # and candidate. Compare only the actual generation knobs here.
            knobs = {k: config[k] for k in ('temperature', 'top_p', 'top_k', 'max_output_tokens',
                'thinking_config', 'seed', 'response_mime_type') if isinstance(config, dict) and k in config}
            role = call.get('agent_num')
            models.append({'role': str(role) if type(role) is int else 'unobserved',
                'requested': http.get('model'), 'returned': http.get('provider_model_version'),
                'knobs': knobs if type(role) is int else {}})
        publication = outcome.get('publication')
        classification = (publication.get('publication_class', 'unknown') if isinstance(publication, dict) else 'unknown') if published else assessment.get('classification', 'failed')
        if not published and classification not in ('rejected', 'failed', 'cancelled', 'unknown'):
            classification = 'failed'
        assessment.update(job_id=job_id, code_sha256=job['actual_hashes']['code_sha256'],
            completed=completed, artifact_verified=artifact_verified, published=bool(published),
            classification=classification, actual_models=models, duration_ms=end-start, tokens=tokens,
            started_at_ms=start, finished_at_ms=end)
        return assessment

    def results(self):
        return self._reviewed_results()

    def _reviewed_results(self, *, skip_unbound_job_id=None):
        from quality_campaign_revision import load_revision
        self._revision = load_revision(self)
        results = {}
        bound = self.ledger.snapshot()['reviews']
        for row in self.protocol['samples']:
            pointer = self.root / ('review-' + row['job_id'] + '.json')
            if row['job_id'] == skip_unbound_job_id and row['job_id'] not in bound:
                continue  # Explicit recovery revalidates this exact pointer separately.
            if row['job_id'] in bound or pointer.exists():
                private_path(pointer)
                raw = regular_bytes(pointer)
                require(bound.get(row['job_id']) == sha(raw), 'Original external review reference changed or is not durably bound')
                results[row['job_id']] = self._result(row['job_id'], referenced(read_json(raw)))
        return results

    def statistics(self, *, cutoff_ms=None):
        """Read-only summary of exact original roster and reverified evidence.

        Cutoff refers to execution completion, not the time the external review
        was first known. Historical snapshots with later usage remain unverified.
        This does not pass a stage, write artifacts or start a live calendar.
        """
        with self.lock():
            from quality_campaign_statistics import campaign_statistics
            results = self.results()
            state = self.ledger.snapshot()
            return campaign_statistics(self.protocol['samples'], results,
                cutoff_ms=state['last_ms'] if cutoff_ms is None else cutoff_ms, ledger_snapshot=state)

    def _prepare_review(self, job_id, review_ref, *, recover_unbound=False):
        from quality_campaign_acceptance import early_stop, validate_evidence
        result = self._result(job_id, referenced(review_ref))
        current = self._reviewed_results(skip_unbound_job_id=job_id if recover_unbound else None)
        current[job_id] = result
        require(not validate_evidence(self.protocol['samples'], current), 'Incomplete/invalid external review schema; not recorded')
        row = self._sample(job_id)
        require(not result['published'] or result['source_decision_reviewed'], 'Published source/decision review is still pending; not recorded')
        require(row['expected'] != 'reject' or result['source_decision_reviewed'], 'Rejection source/decision review is still pending; not recorded')
        if row['stage'] == 'S2' and result['published'] or row['fulltext_review']:
            require(result['independent_review']['complete'], 'Required independent fulltext review is still pending; not recorded')
        expected_classes = {'qualified': {'verified_research', 'verified_no_action'},
            'limited': {'research_with_limitations'}, 'diagnostic': {'diagnostic_no_action'}, 'reject': {'rejected'}}
        if (result['warnings'] or not result['completed'] or result['major_error'] or result['unsafe']
                or result['contradiction'] or not result['important_claims_verified']
                or not all(result[f] for f in ('required_roles_valid', 'generation_passed', 'audit_passed'))
                or result['classification'] not in expected_classes[row['expected']]):
            require(result['failure_review']['complete'], 'Required failure/warning review is still pending; not recorded')
        return result, early_stop(self.protocol['samples'], current)

    def _persist_review_stop(self, reasons, review_ref):
        if reasons:
            self.ledger.stop('acceptance_safety_stop', evidence_sha256=sha(encoded({'reasons': reasons, 'review': review_ref})))

    def record_review(self, job_id, review_ref):
        with self.lock():
            result, reasons = self._prepare_review(job_id, review_ref)
            review_sha = exclusive_json(self.root / ('review-' + identifier(job_id) + '.json'), review_ref)
            self.ledger.bind_review(job_id, review_ref_sha256=review_sha)
            self._persist_review_stop(reasons, review_ref)
            return result

    def recover_review_binding(self, job_id):
        """Explicitly finish an interrupted bind, never replace its pointer.

        Rechecks the full normal review contract. No process/transport launch,
        budget refund, stage promotion or clearing of existing stop state.
        """
        with self.lock():
            pointer = self.root / ('review-' + identifier(job_id) + '.json')
            private_path(pointer)
            raw = regular_bytes(pointer)
            ref, bound = read_json(raw), self.ledger.snapshot()['reviews'].get(job_id)
            require(bound is None or bound == sha(raw), 'Cannot recover a replaced bound review')
            result, reasons = self._prepare_review(job_id, ref, recover_unbound=True)
            require(regular_bytes(pointer) == raw, 'Pending review pointer changed during recovery')
            if bound is None: self.ledger.bind_review(job_id, review_ref_sha256=sha(raw))
            self._persist_review_stop(reasons, ref)
            return result

    def recover_terminal_batch(self, batch_id):
        """Close only a reviewed terminal single-job batch with original proof.

        Active jobs, missing parent/cleanup receipts and host/guardian loss are
        NOT recovered here. Never infer ownership from an absent PID, synthesize
        success, send signals or rerun a spent slot. Elapsed batch time continues
        through this explicit recovery; an expired ledger remains stopped.
        """
        with self.lock():
            from quality_campaign_runner import check_claim
            state = self.ledger.snapshot()
            batch = state['batches'].get(identifier(batch_id))
            require(batch is not None and batch['ended_ms'] is None and batch['stage'] in ('S1', 'S2', 'S3'),
                'Only an open private campaign batch can be recovered')
            jobs = [(key, value) for key, value in state['jobs'].items() if value['batch_id'] == batch_id]
            require(len(jobs) == 1 and jobs[0][1]['status'] != 'active', 'Original terminal single job required')
            job_id, job = jobs[0]
            require(job_id in self.results(), 'Complete the original external review before terminal batch recovery')
            check_claim(self.ledger, job_id, job)
            parent = read_json(regular_bytes(self.root / job_id / 'parent-receipt.json'))
            self.ledger.finish_batch(batch_id, cleanup_evidence_sha256=parent['cleanup_sha256'])
            return {'batch_id': batch_id, 'job_id': job_id, 'status': 'terminal_batch_closed',
                    'cleanup_sha256': parent['cleanup_sha256'], 'job_reexecuted': False}

    def _stage_acceptance(self, stage):
        from quality_campaign_acceptance import evaluate_stage, early_stop
        results = self.results()
        reasons = early_stop(self.protocol['samples'], results)
        if reasons:
            self.ledger.stop('acceptance_safety_stop', evidence_sha256=sha(encoded({'reasons': reasons, 'results': results})))
            raise ReplayAbort('Campaign stopped by fixed acceptance rules')
        return evaluate_stage(stage, self.protocol['samples'], results)

    def pass_stage(self, stage):
        with self.lock():
            require(stage in ('S1', 'S2', 'S3'), 'Formal S4 evidence is not implemented; no release')
            decision = self._stage_acceptance(stage)
            require(decision.get('decision') == 'passed', 'Stage acceptance is not passed')
            # Keep the exact external input/receipt references in the immutable
            # acceptance receipt, not merely an untraceable passed scalar.
            reviews = {r['job_id']: read_json(regular_bytes(self.root / ('review-' + r['job_id'] + '.json')))
                for r in self.protocol['samples'] if r['stage'] == stage
                and (self.root / ('review-' + r['job_id'] + '.json')).exists()}
            receipt = {'stage': stage, 'protocol_sha256': sha(encoded(self.protocol)),
                       'decision': decision, 'reviews': reviews}
            path = self.root / ('acceptance-' + stage + '.json')
            if path.exists(): require(read_json(regular_bytes(path)) == receipt, 'Prior acceptance receipt changed')
            else: exclusive_json(path, receipt)
            self.ledger.pass_stage(stage, acceptance_evidence_sha256=sha(regular_bytes(path)))
            return decision

    def run_next(self, *, storage_budget=None):
        """One fresh owned job, in fixed order. Never resume/relaunch a spent job.

        Single-job batches are within the approved maxima (12 total/3 per mode)
        and close after proved cleanup, before potentially lengthy review. Two
        simultaneous jobs are permitted, not required. This coordinator is
        deliberately serial; independent child calls still share the ledger.
        """
        canary_release_policy.require_canary_enabled()
        with self.lock():
            self._s0_review()
            state = self.ledger.snapshot()
            require(not any(j['status'] == 'active' for j in state['jobs'].values())
                    and not any(b['ended_ms'] is None for b in state['batches'].values()),
                    'Interrupted job/batch requires verified recovery; no automatic replay')
            results = self.results()
            require(set(state['jobs']).issubset(results), 'Complete the pending external job review before new admission')
            # A raw ledger pass_stage(hash) call is not an acceptance authority.
            # Reopen verifies every promoted stage against original receipt bytes
            # AND the same external review/artifact inputs before new dispatch.
            for event in self.ledger.events():
                if event['kind'] != 'stage_pass': continue
                passed = event['payload']['stage']
                path = self.root / ('acceptance-' + passed + '.json')
                require(path.exists(), 'Passed stage has no verified acceptance receipt')
                receipt_raw = regular_bytes(path)
                receipt = read_json(receipt_raw)
                require(sha(receipt_raw) == event['payload']['acceptance_evidence_sha256']
                        and receipt.get('protocol_sha256') == sha(encoded(self.protocol))
                        and receipt.get('stage') == passed, 'Passed stage receipt identity changed')
                decision = self._stage_acceptance(passed)
                require(decision['decision'] == 'passed' and receipt.get('decision') == decision,
                        'Passed stage no longer matches reviewed evidence')
                reviews = {r['job_id']: read_json(regular_bytes(self.root / ('review-' + r['job_id'] + '.json')))
                    for r in self.protocol['samples'] if r['stage'] == passed and r['job_id'] in results}
                require(receipt.get('reviews') == reviews, 'Passed stage external review references changed')
            stage = next((s for s in STAGES if state['stages'].get(s) != 'passed'), None)
            require(stage in ('S1', 'S2', 'S3'), 'Formal canary requires separate verified deployment isolation')
            decision = self._stage_acceptance(stage)
            require(decision.get('decision') != 'failed', 'Fixed stage acceptance failed')
            require(decision.get('decision') != 'passed', 'Persist stage acceptance before proceeding')
            pending = [r for r in self.protocol['samples'] if r['stage'] == stage and r['job_id'] not in state['jobs']]
            require(bool(pending), 'No unspent preregistered slot; no replacement samples')
            row = self._sample(pending[0]['job_id'])
            binding_id = row.get('binding_id', row['job_id'])
            plan = FrozenJob(row['manifest']['path'], row['manifest']['sha256'])
            actual = plan.verify()
            require(actual == state['effective_bindings'].get(binding_id), 'Frozen job differs from preregistration')
            if stage in ('S2', 'S3') and row['role'] == 'candidate':
                winner = self._stage_acceptance('S1')['metrics'].get('accepted_code_sha256')
                require(actual['code_sha256'] == winner, 'Candidate differs from the accepted S1 version')
            # Both review and the shared claim precede live calendar/job slots.
            # The same bound claim is held through execution and batch closure.
            with reserved_job_storage(plan, self.ledger, row['job_id'], storage_budget) as prepared:
                self.ledger.check()
                if state['stage'] != stage: self.ledger.start_stage(stage)
                batch_id = 'batch-' + row['job_id']
                self.ledger.start_batch(batch_id, stage)
                self.ledger.reserve_job(row['job_id'], batch_id, binding_id=binding_id, actual_hashes=actual)
                receipt = execute_reserved_job(plan, self.ledger, row['job_id'],
                    storage_budget=storage_budget, _storage=prepared)
                self.ledger.finish_batch(batch_id, cleanup_evidence_sha256=receipt['cleanup_sha256'])
                return receipt
