"""Guarded frozen-interface continuation after an exited native-cleanup fault."""
from pathlib import Path
import json

from controller_common import bind
import execution_state

from jobs import prior_context

VERSION='yui-native-cleanup-recovery-1'
FAULT='RuntimeError: Native process cleanup could not be confirmed'


@prior_context
def qualify(previous):
    import full_workflow
    import ir
    import jobs
    root=Path(previous).resolve();old=jobs.validate(ir.load(root/'job.json'),verify_runtime=False)
    state=ir.load(root/'execution-status.json')
    if execution_state.same_process(state['controller']):
        raise ValueError('Prior controller is still live; do not start a competing continuation')
    for row in state['processes'].values():
        if execution_state.same_process(row):raise ValueError('Prior owned process is still live')
    from owner_observation import snapshot
    ownership=snapshot([root])
    if not ownership['all_process_exits_verified']:
        raise ValueError('Prior owned process-group exit is not verified')
    result=ir.load(root/'case-result.json').get('result',{})
    if result.get('status')!='PROOF_UNFINISHED' or old['policy']!='normal' or old['time_budget_seconds'] is not None:
        raise ValueError('Only an unlimited normal-policy stopped proof queue is supported')
    tasks=[t for t in state['tasks'].values() if t.get('role')=='proof']
    failed=[t for t in tasks if t['state']!='LOCAL_CHECKED']
    if not failed:raise ValueError('No failed native-cleanup proof task')
    files={root/'job.json',root/'case-result.json',root/'execution-status.json'}
    for task in failed:
        stage=Path(task['log_path']).resolve()
        if not stage.is_relative_to(root):raise ValueError('Proof stage escapes its case')
        report=ir.load(stage/'result.json')
        if (task['state']!='UNFINISHED' or report.get('execution_fault')!=FAULT
                or not report.get('identity_and_input_boundary_verified')
                or report.get('isolation_violation') is not False
                or report.get('temporary_workspace_removed') is not True):
            raise ValueError('A non-cleanup failure is not eligible for automatic continuation')
        files.update([stage/'result.json',stage/'prompt.txt'])
        files.update((stage/'lean-drafts').glob('*.json'))
        files.update(p for p in [stage/'native-cleanup-source.lean',stage/'native-cleanup-checkpoint.json'] if p.exists())
    workflows=list((root/'nl0-to-lean').glob('*/workflow/manifest.json'))
    if len(workflows)!=1:raise ValueError('An unambiguous frozen proof interface is required')
    directory=workflows[0].parent;manifest=full_workflow.workflow.bound(directory)
    prior=directory/'proof-run';report=ir.load(prior/'report.json')
    if report['status']!='GRAPH_UNFINISHED':raise ValueError('Preserve the actual partial proof-queue outcome')
    expected={sid for t in tasks if t['state']=='LOCAL_CHECKED' for sid in t.get('consumers',[t['id']])}
    if set(report['proofs'])!=expected:raise ValueError('Partial proofs do not match actual checked node coverage')
    interface=Path(manifest['interface_binding']).parent
    files.update([directory/'manifest.json',directory/'freeze-seal.json',prior/'report.json',
                  prior/'inputs/contract.json',prior/'inputs/plan.json',interface/'accepted-interface-paths.json'])
    files.update(p for p in (prior/'inputs').rglob('*') if p.is_file())
    files.update(Path(row['path']) for row in manifest['bindings']+manifest['frozen_input_bindings'])
    descriptor={'version':VERSION,'mode':'native-proof-cleanup','prior_run':str(root),
        'workflow':str(directory),'interface':str(interface),'prior_proof_run':str(prior),
        'failed_steps':sorted(t['id'] for t in failed),'source_authority':manifest['authority']}
    return old,descriptor,[bind(p) for p in sorted(files)]


def validate_descriptor(job):
    if job.get('root') and Path(job['resume']['prior_run']).resolve()==Path(job['root']).resolve():
        raise ValueError('A proof continuation must name a different prior run')
    old,expected,files=qualify(job['resume']['prior_run'])
    if job['resume']!=expected or job['track']!='translate':raise ValueError('Changed native cleanup recovery scope')
    for key in ('case','profiles','max_concurrency','policy','target_selection'):
        if job.get(key)!=old.get(key):raise ValueError('Recovery changed '+key)
    if job.get('formalization','conditional')!=old.get('formalization','conditional'):
        raise ValueError('Recovery changed formalization goal')
    if job['documents'][0]['sha256']!=old['documents'][0]['sha256']:
        raise ValueError('Recovery changed the original problem')
    if not {r['path'] for r in files}<={r['path'] for r in job['authority_bindings']}:
        raise ValueError('Missing bound partial proof or own-draft evidence')


@prior_context
def prepare(previous):
    import jobs
    old,descriptor,bindings=qualify(previous)
    problem=Path(old['problem']);materials=jobs.resume_materials(old)
    job=jobs.prepare(problem,track='translate',profiles=old['profiles'],
        max_concurrency=old['max_concurrency'],policy=old['policy'],materials=materials,
        source=Path(descriptor['source_authority']['graph']).parent,resume=descriptor,resume_bindings=bindings,
        target=old.get('target_selection'),formalization=old.get('formalization','conditional'))
    validate_descriptor(job)
    return job
