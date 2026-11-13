"""Explicit exited-queue recovery after ENOSPC, never an acceptance receipt.

Old runs remain read-only. A fresh full/unconditional job inherits its checked
basis/source/interface, rechecks every saved body, and gives each unfinished
author only its own bound drafts and completed local diagnostic advice.
"""
from pathlib import Path
from copy import deepcopy
import json
import os
import shutil
import tempfile

from controller_common import bind, write, verify_bindings

from jobs import prior_context

VERSION = 'yui-proof-io-recovery-1'
MODE = 'native-proof-io'


def enospc(value):
    """Match actual structured I/O diagnostics, never mathematical/tool prose."""
    error = value.get('error', {})
    if error.get('exception_type') == 'OSError':
        return '[Errno 28] No space left on device' in error.get('message', '')
    outcome = error.get('outcome', {})
    return ('[Errno 28] No space left on device' in outcome.get('execution_fault', '')
            and 'carrier message reader failed' in outcome.get('execution_fault', ''))


def candidate_context(result):
    """Eligibility for unaccepted own text only, never historical acceptance.

    A dead retained workspace cannot pass the ordinary live/released-role gate.
    We do not override that gate: no old verdict is inherited. Exact input
    readback plus a new kernel check/fresh semantic review supplies new evidence.
    """
    return (result.get('status') == 'ACCEPTED'
            and result.get('identity_and_input_boundary_verified') is True
            and result.get('isolation_violation') is False
            and not result.get('execution_fault')
            and isinstance(result.get('submission_completion'), dict))


@prior_context
def qualify(previous):
    import jobs
    import ir
    import full_workflow
    import native_client
    from owner_observation import snapshot

    root = Path(previous).resolve()
    old = jobs.validate(ir.load(root/'job.json'))
    if (old['track'] != 'full' or old.get('formalization') != 'unconditional'
            or old['policy'] != 'normal' or old['time_budget_seconds'] is not None):
        raise ValueError('Only an unlimited normal full/unconditional proof checkpoint is supported')
    ownership = snapshot([root])
    if not ownership['all_process_exits_verified']:
        raise ValueError('All prior owned processes and groups must have exited')
    if (root/'case-result.json').exists():
        raise ValueError('Use the supported terminal-outcome recovery for an exited finalized case')
    state = ir.load(root/'execution-status.json')
    if state['phase'] != 'proof':
        raise ValueError('Only the frozen local proof phase is eligible')
    workflows = list((root/'nl0-to-lean').glob('*/workflow/manifest.json'))
    if len(workflows) != 1:
        raise ValueError('An unambiguous frozen proof interface is required')
    directory = workflows[0].parent
    manifest = full_workflow.workflow.bound(directory)
    prior = directory/'proof-run'
    if (prior/'report.json').exists():
        raise ValueError('Do not replace an actual completed queue report')
    plan = ir.load(prior/'inputs/plan.json')
    cpath = prior/'inputs/contract.json'
    ir.validate(cpath, plan)
    steps = {row['id'] for row in plan['steps']}
    tasks = {t['id']: t for t in state['tasks'].values() if t.get('role') == 'proof' and t['id'] in steps}
    for task in state['tasks'].values():
        if task.get('role') == 'proof' and task['id'] not in steps:
            if task.get('stage') != 'interface-proof-diagnosis' or task.get('state') != 'WAITING_REVIEW':
                raise ValueError('Unknown incomplete role in the old proof queue')
    # This route deliberately excludes alias/shared-node reconstruction.
    if set(tasks) != steps or any(t.get('consumers', [sid]) != [sid] for sid, t in tasks.items()):
        raise ValueError('Recovery requires exact one-worker-per-node coverage')
    files = {root/'job.json', root/'execution-status.json', directory/'manifest.json',
             directory/'freeze-seal.json', root/'logs/controller.log'}
    files.update(p for p in (prior/'inputs').rglob('*') if p.is_file())
    files.update(Path(r['path']) for r in manifest['bindings'] + manifest['frozen_input_bindings'])
    completed, unfinished, incidents = [], [], []
    for sid, task in sorted(tasks.items()):
        stage = prior/'workers'/sid
        if stage.is_symlink() or Path(task['log_path']).resolve() != stage.resolve():
            raise ValueError('Prior worker scope changed')
        if any((stage/n).exists() for n in ['tool-provenance-rejections.jsonl', 'isolation-violations.jsonl']):
            raise ValueError('A provenance or isolation failure cannot supply a recovery checkpoint')
        packet = ir.load(stage/'prompt.txt')['packet']
        from types import SimpleNamespace
        from model_pilot import Stage
        metadata = ir.load(stage/'execution-manifest.json') if (stage/'execution-manifest.json').exists() else {}
        expected_packet = Stage.proof_packet(SimpleNamespace(cpath=cpath, plan=plan, step=sid,
            background_note_policy=metadata.get('background_note_policy')))
        if packet != expected_packet:
            raise ValueError('Saved own-node packet changed')
        native = ir.load(stage/'native-client.json')
        profile = native['profile']
        expected = old['profiles']['lean']
        if any(profile.get(k) != expected.get(k) for k in ['id', 'reasoning_effort', 'speed']):
            raise ValueError('Prior own-node profile changed')
        # Read back incomplete stages without altering their historical receipts.
        exposure = native_client.audit(stage, write_receipt=False)
        if exposure['status'] != 'NATIVE-CODEX-CONTEXT-CHECK-PASSED':
            raise ValueError('Prior native context is not intact: '+sid)
        names = ['prompt.txt', 'native-client.json', 'effective-config.toml', 'system.txt',
                 'tools.json', 'client.jsonl', 'execution-manifest.json', 'local-helpers.json',
                 'proof-progress-actions.json']
        files.update(stage/n for n in names if (stage/n).is_file())
        for path in (stage/'lean-drafts').glob('*.json'):
            if path.is_symlink():
                raise ValueError('Unsafe own-draft link')
            row = ir.load(path)
            if not isinstance(row.get('proof'), str) or not isinstance(row.get('statement'), str):
                raise ValueError('Incomplete own-draft file: '+str(path))
            files.add(path)
        for review in stage.glob('diagnosis-requests/*/review'):
            accepted = review/'stage/accepted.json'
            if accepted.exists():
                import proof_diagnosis
                proof_diagnosis.validate(ir.load(accepted), review)
                result = ir.load(review/'stage/result.json')
                if not candidate_context(result) or result.get('execution_health') != 'NO_RECORDED_FAULT':
                    raise ValueError('Prior diagnostic advice has no intact submitted context')
                route = ir.load(accepted)['route']
                if route not in {'LOCAL_PROOF_REPAIR', 'UNRESOLVED'}:
                    raise ValueError('Preserve the actual diagnostic route before recovery: '+route)
                files.update(p for p in review.rglob('*') if p.is_file())
        result_path = stage/'result.json'
        if task['state'] == 'LOCAL_CHECKED':
            result = ir.load(result_path)
            if not candidate_context(result):
                raise ValueError('Completed body has no intact submitted candidate: '+sid)
            ir.render(cpath, plan, {sid: ir.load(stage/'accepted.json')['proof']}, only=sid)
            files.update([result_path, stage/'accepted.json'])
            completed.append(sid)
        else:
            if task['state'] not in {'RUNNING', 'PAUSED_ERROR', 'WAITING_REVIEW'} or result_path.exists():
                raise ValueError('Do not replay a completed nonpass or unknown worker outcome')
            if (stage/'error-state.json').exists():
                fault = ir.load(stage/'error-state.json')
                if fault.get('state') == 'PAUSED_ERROR':
                    if fault.get('fault', {}).get('category') != 'harness_bug' or not enospc(fault):
                        raise ValueError('A non-ENOSPC incident requires its own recovery route')
                    incidents.append({'step': sid, 'incident': fault['incident']})
                files.add(stage/'error-state.json')
            unfinished.append(sid)
    if not incidents or not unfinished:
        raise ValueError('No actual unfinished ENOSPC checkpoint')
    if '[Errno 28] No space left on device' not in (root/'logs/controller.log').read_text():
        raise ValueError('The controller has no actual ENOSPC evidence')
    for path in files:
        if path.is_symlink():
            raise ValueError('Unsafe recovery evidence link')
    interface = Path(manifest['interface_binding']).parent
    files.add(interface/'accepted-interface-paths.json')
    descriptor = {'version': VERSION, 'mode': MODE, 'prior_run': str(root),
                  'workflow': str(directory), 'interface': str(interface),
                  'prior_proof_run': str(prior), 'source_authority': manifest['authority'],
                  'completed_steps': completed, 'unfinished_steps': unfinished, 'incidents': incidents}
    return old, descriptor, [bind(p) for p in sorted(files)]


def validate_descriptor(job):
    old, expected, files = qualify(job['resume']['prior_run'])
    if Path(job['root']).resolve() == Path(old['root']).resolve() or job['resume'] != expected:
        raise ValueError('Recovery must use a fresh run with the exact checkpoint')
    for key in ['case', 'track', 'formalization', 'profiles', 'max_concurrency', 'policy',
                'target_selection', 'documents', 'time_budget_seconds']:
        if job.get(key) != old.get(key):
            raise ValueError('Recovery changed '+key)
    if any(row not in job['authority_bindings'] for row in files):
        raise ValueError('Recovery omitted actual retained evidence')


@prior_context
def prepare(previous):
    import jobs
    old, descriptor, bindings = qualify(previous)
    materials = jobs.resume_materials(old)
    job = jobs.prepare(old['problem'], track='full', formalization='unconditional',
                       profiles=old['profiles'], max_concurrency=old['max_concurrency'],
                       policy=old['policy'], materials=materials,
                       source=Path(descriptor['source_authority']['graph']).parent,
                       resume=descriptor, resume_bindings=bindings, target=old['target_selection'])
    # Verify real writable storage before dispatch. No disk-space forecast is claimed.
    with tempfile.TemporaryFile(dir=job['root']) as stream:
        stream.write(b'Yui recovery write check\n'); stream.flush(); os.fsync(stream.fileno())
    validate_descriptor(job)
    return job


def stage_checkpoint(job):
    """A candidate view, explicitly distinct from a historical proof-run report."""
    validate_descriptor(job)
    target = Path(job['root'])/'retained-proof-candidates'
    prior = Path(job['resume']['prior_proof_run'])
    shutil.copytree(prior/'inputs', target/'inputs')
    write(target/'io-recovery.json', {'version': VERSION, 'checkpoint': job['resume'],
          'origins': job['authority_bindings'], 'job': bind(Path(job['root'])/'job.json'),
          'scope': 'Candidate recovery only; no synthetic queue result or accepted proof'})
    return target


def view(previous):
    import ir
    previous = Path(previous).resolve()
    value = ir.load(previous/'io-recovery.json')
    if value.get('version') != VERSION:
        raise ValueError('Unknown I/O recovery view')
    expected = bind(previous.parent/'job.json')
    job = ir.load(expected['path'])
    marker = ir.load(previous.parent/'.yui-run.json')
    if (value.get('job') != expected or marker.get('job') != expected
            or job.get('root') != str(previous.parent)
            or value['checkpoint'] != job.get('resume')
            or value['origins'] != job.get('authority_bindings')):
        raise ValueError('Recovery candidate view changed from its owned frozen job')
    verify_bindings(value['origins'])
    return value['checkpoint']


def candidate(previous, cpath, plan, step):
    import ir
    from proof_reuse import same_port
    checkpoint = view(previous)
    if step not in checkpoint['completed_steps']:
        return None
    prior = Path(checkpoint['prior_proof_run'])
    if not same_port(prior/'inputs/contract.json', ir.load(prior/'inputs/plan.json'), cpath, plan, step):
        raise ValueError('Recovered completed obligation changed')
    path = prior/'workers'/step/'accepted.json'
    body = ir.load(path)['proof']
    if ir.render(prior/'inputs/contract.json', ir.load(prior/'inputs/plan.json'), {step: body}, only=step) != ir.render(cpath, plan, {step: body}, only=step):
        raise ValueError('Recovered local Lean program changed')
    return {'body': body, 'previous_run': str(prior),
            'previous_proofs_sha256': ir.digest(path),
            'scope': 'Actual prior own submission only; current native recheck required'}


def restore_drafts(stage, previous):
    import ir
    import local_helpers
    from proof_reuse import same_port
    checkpoint = view(previous)
    if stage.step not in checkpoint['unfinished_steps']:
        return None
    prior = Path(checkpoint['prior_proof_run']); old = prior/'workers'/stage.step
    if (not same_port(prior/'inputs/contract.json', ir.load(prior/'inputs/plan.json'),
                      stage.cpath, stage.plan, stage.step)
            or ir.load(old/'prompt.txt')['packet'] != json.loads(stage.prompt())['packet']):
        raise ValueError('Recovered own-node obligation changed')
    helpers = old/'local-helpers.json'
    if helpers.exists():
        rows = ir.load(helpers)
        local_helpers.validate(stage.cpath, stage.plan, stage.step, rows)
        stage.local_helpers = rows
        ir.write(stage.logs/'local-helpers.json', rows)
    restored = []
    for kind in ['proof', 'auxiliary']:
        for path in sorted((old/'lean-drafts').glob(kind+'-*.json')):
            row = deepcopy(ir.load(path)); number = int(path.stem.split('-')[-1])
            row['previous_check'] = row.get('check')
            row['check'] = {'status': 'RETAINED_UNACCEPTED_CANDIDATE',
                            'scope': 'Prior I/O-interrupted attempt only; current checking required'}
            stage.own_lean_drafts[kind][number] = row
            ir.write(stage.logs/'lean-drafts'/path.name, row)
            restored.append(bind(path))
    advice = []
    for path in sorted(old.glob('diagnosis-requests/*/review/stage/accepted.json')):
        advice.append({'diagnosis': ir.load(path), 'origin': bind(path)})
    actions = old/'proof-progress-actions.json'
    if actions.exists():
        stage.proof_progress.seen.update(ir.load(actions)['actions'])
    stage.proof_progress.last_turn_revision = stage.proof_progress.revision
    receipt = {'previous_stage': str(old), 'restored_files': restored,
               'acceptance': 'NONE; new isolated context and current Lean checks required'}
    ir.write(stage.logs/'own-io-recovery.json', receipt)
    stage.system += (' This is a disclosed warm operational continuation after an exited ENOSPC incident. '
                     'Only your exact own-node drafts and helper declarations were restored; inspect read_lean_draft. '
                     'Past checks are diagnostic evidence, not current acceptance. Prior faults and costs remain retained.')
    if advice:
        stage.system += '\nCompleted prior own-node diagnostics (advice only, no new premise):\n'+json.dumps(advice)
    return receipt
