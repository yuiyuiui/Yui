"""Explicit final-only continuation after an exited basis-closure failure.

Reuse checked basis and Audit B artifacts without calling any author/reviewer.
The old run is immutable; a fresh normal owned job records the new native check.
"""
from pathlib import Path

from controller_common import bind, write, verify_bindings
import ir

VERSION='yui-basis-closure-recovery-1'


def qualify(previous):
    import basis
    import basis_native
    import final_acceptance
    import jobs
    import owner_observation
    import workflow
    root=Path(previous).resolve()
    old=jobs.validate(ir.load(root/'job.json'),verify_runtime=False)
    if basis.mode(old)!='unconditional' or old['policy']!='normal' or old['time_budget_seconds'] is not None:
        raise ValueError('Final-only recovery requires an unlimited normal unconditional job')
    observed=owner_observation.snapshot([root])
    if not observed['all_process_exits_verified'] or not observed['all_terminal']:
        raise ValueError('Cancel the prior run and verify all owned exits and resolved incidents first')
    result=ir.load(root/'case-result.json')['result']
    failure=result.get('retained_error',{}) if result.get('status')=='CANCELLED' else result
    if failure.get('status')!='BASIS_FINAL_CLOSURE_FAILED' or failure.get('phase')!='basis-final-closure':
        raise ValueError('Only an actual final basis closure failure is eligible')
    check=root/'b2lean/check.json'
    if Path(failure.get('evidence','')).resolve()!=check or (check.parent/'report.json').exists():
        raise ValueError('Missing original failed closure evidence or an existing successful delivery')
    native=ir.load(check);verify_bindings(native['bindings'])
    problems=basis_native.errors(ir.load(check.parent/'compiler.json'),ir.load(check.parent/'elaborated.json'),
        native['checks'],native['roots'])
    if native['passed'] is not False or not problems or native['errors']!=problems or failure.get('errors')!=problems:
        raise ValueError('Changed or inconsistent final closure failure')
    prior_resume=old.get('resume') or {}
    candidates=([Path(prior_resume['workflow'])/'manifest.json'] if prior_resume.get('mode')=='basis-final-closure'
        else list((root/'nl0-to-lean').glob('*/workflow/manifest.json')))
    if len(candidates)!=1:raise ValueError('An unambiguous accepted frozen workflow is required')
    directory=candidates[0].parent;frozen=workflow.bound(directory)
    context=frozen['basis_context'];basis.verify_context(context)
    if prior_resume.get('mode')!='basis-final-closure' and ir.load(basis.problem_inputs(old)/basis.CONTEXT)!=context:
        raise ValueError('Final closure does not use the original active basis')
    receipt_path=directory/'audit-b/machine-acceptance.json'
    receipt=final_acceptance.validate_receipt(receipt_path)
    if receipt['freeze_deviation'] or Path(receipt['workflow']).resolve()!=directory.resolve():
        raise ValueError('Final-only recovery requires the exact frozen interface')
    intermediate=ir.load(directory/'report.json');verify_bindings(intermediate['bindings'])
    if (intermediate['status'] not in {'WORKFLOW-PASSED','WORKFLOW-CONDITIONAL'}
            or intermediate['audit_b']['receipt_path']!=str(receipt_path)
            or intermediate['audit_b']['receipt_sha256']!=ir.digest(receipt_path)):
        raise ValueError('Changed shared workflow acceptance')
    files={root/'job.json',root/'case-result.json',root/'execution-status.json',check,
        directory/'manifest.json',directory/'freeze-seal.json',directory/'report.json',receipt_path}
    files.update(Path(row['path']) for row in [*native['bindings'],*receipt['bindings'],
        *frozen['bindings'],*frozen['frozen_input_bindings'],*basis.recovery_bindings(old)])
    descriptor={'version':VERSION,'mode':'basis-final-closure','prior_run':str(root),
        'workflow':str(directory),'source_authority':frozen['authority']}
    return old,descriptor,[bind(p) for p in sorted(files)]


def validate_descriptor(job):
    if Path(job['root']).resolve()==Path(job['resume']['prior_run']).resolve():
        raise ValueError('Preserve the prior run; final closure needs a fresh output')
    old,expected,files=qualify(job['resume']['prior_run'])
    if job['resume']!=expected or job['track']!='full':raise ValueError('Changed final closure recovery scope')
    for key in ('case','profiles','max_concurrency','policy','target_selection','formalization','time_budget_seconds'):
        if job.get(key)!=old.get(key):raise ValueError('Recovery changed '+key)
    if job['documents'][0]['sha256']!=old['documents'][0]['sha256']:
        raise ValueError('Recovery changed the original problem')
    if not all(row in job['authority_bindings'] for row in files):
        raise ValueError('Missing bound final closure evidence')


def prepare(previous):
    import jobs
    old,descriptor,bindings=qualify(previous)
    problem=Path(old['problem']);materials=[]
    for row in old['documents'][1:]:
        p=Path(row['original']['path'])
        if row['id']!='target-selection.json' and p!=problem and p not in materials:materials.append(p)
    job=jobs.prepare(problem,track='full',profiles=old['profiles'],max_concurrency=old['max_concurrency'],
        policy=old['policy'],materials=materials,source=Path(descriptor['source_authority']['graph']).parent,
        resume=descriptor,resume_bindings=bindings,target=old['target_selection'],formalization='unconditional')
    validate_descriptor(job)
    return job


def run(job, progress):
    import b2lean
    import jobs
    import workflow
    jobs.validate(job)
    directory=Path(job['resume']['workflow']);root=Path(job['root'])
    frozen=workflow.bound(directory)
    # Retain the prepared context for ordinary ownership, readback and possible
    # further final-only continuation; never re-run basis authoring.
    import basis
    from controller_common import manifest
    active=root/'active-inputs';active.mkdir()
    write(active/basis.CONTEXT,frozen['basis_context']);manifest(active)
    write(root/'basis-selection.json',{'context':bind(active/basis.CONTEXT),'inputs':bind(active/'inputs.json')})
    progress(job['case'],'BASIS_FINAL_CLOSURE',workflow=str(directory),new_proof_or_semantic_model_calls=False,
             timeout_diagnosis_on_native_timeout=True)
    # Check the job again immediately before publication, including the old
    # failure, authority bindings and confirmed process exits.
    result=b2lean.finish(directory,root/'b2lean',context=frozen['basis_context'],
        intermediate=ir.load(directory/'report.json'),before_publish=lambda:jobs.validate(job))
    provenance={'version':VERSION,'prior_run':job['resume']['prior_run'],
        'prior_case_result':bind(Path(job['resume']['prior_run'])/'case-result.json'),
        'job':bind(root/'job.json'),'new_model_calls':result.get('timeout_diagnostic_model_called',False),
        'prior_costs_preserved':True}
    write(root/'closure-recovery.json',provenance)
    return {**result,'recovery':provenance}
