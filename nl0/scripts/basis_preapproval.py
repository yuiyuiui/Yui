"""Review and decide residual assumptions before dispatching unpaid basis proofs."""
from copy import deepcopy
from pathlib import Path
import re

import basis_native
import basis_review
import ir
import local_helpers
from controller_common import bind, verify_bindings, write


def plan_identity(candidate):
    shape=deepcopy(candidate)
    for row in shape['dependencies']:
        if row['category']!=4:row['lean']['proof']=None
    return local_helpers.digest(shape)


def projection(candidate):
    value=deepcopy(candidate)
    value['plan_identity']=plan_identity(value)
    for row in value['dependencies']:
        if row['category']!=4:row['lean']=None
    return value


def approve(stage,candidate):
    import basis
    from role_sessions import Sessions
    from execution_state import Cancelled
    from case_outcomes import verify_basis_decision
    selected=projection(candidate)
    key=selected['plan_identity']
    directory=stage.validator.out/'plans'/key
    completed=directory/'approval.json'
    residual=[r for r in selected['dependencies'] if r['category']==4]
    if not residual:return
    if not completed.is_file():
        attempt=directory
        source, checks = basis_native.type_probes(selected['lean_header'], residual)
        write(attempt/'stage/accepted.json',selected)
        write(attempt/'planning-author.json',{'thread_id':stage.thread_id,
            'manifest':bind(stage.logs/'execution-manifest.json'),
            'candidate':bind(stage.validator.out/'candidates'/f'{stage.validator.attempt:04d}'/'basis.json')})
        nativepath=attempt/'native/check.json'
        if not nativepath.exists():
            checked=basis_native.check(source,checks,[c[1] for c in checks],attempt/'native')
        else:checked=basis_native.verify(nativepath)
        if not checked['passed']:
            raise ValueError('Residual type checks failed. Repair the plan: '+str(checked['errors']))
        inputs=stage.validator.out/'inputs'
        ctx={'basis':bind(attempt/'stage/accepted.json'),'native':bind(nativepath),
             'original_inputs':[bind(inputs/r['path']) for r in ir.load(inputs/'inputs.json')['inputs']],
             'evidence':basis.evidence_bindings(candidate,inputs,stage.logs)}
        report=attempt/'review/report.json'
        if report.exists():
            findings=basis_review.verify(bind(report),ctx,selected,require_pass=False)
        else:
            sessions=Sessions()
            with stage.budget.suspended():
                _,findings=basis_review.assess(attempt,ctx,selected,sessions,stage.budget,{})
            sessions.close_all('BASIS_PREPARED',[report])
        if findings:raise ValueError('Repair the residual source/type/application: '+str(findings))
        ctx['semantic_review']=bind(report)
        write(attempt/'context.json',ctx)
        chosen=basis.decision(directory,selected,stage.budget,planning=True)
        write(completed,chosen)
    decision=ir.load(completed)
    receipt=bind(directory/'decision/error-incidents'/(decision['incident']+'.json'))
    action=decision['control']['action']
    if decision!=verify_basis_decision(stage.validator.out.parents[1],receipt,action):
        raise RuntimeError('Changed foundation planning decision')
    if action=='stop':
        stage.validator.early_stop=receipt
        raise Cancelled('Operator stopped the foundation plan before proof dispatch')
    if action=='continue':
        raise ValueError('The operator selected further reduction. Revise the remaining class 4 route.')
    if action!='accept-conditional':
        raise RuntimeError('Unknown foundation planning decision')


def existing(revision,candidate):
    root=Path(revision)/'plans'/plan_identity(candidate)
    file=root/'approval.json'
    if not file.is_file():return None
    event=ir.load(file)
    ir.need(event['control']['action']=='accept-conditional','The plan has no approval to retain these assumptions')
    return event


def verify(revision,candidate,event):
    from case_outcomes import verify_basis_decision
    directory=Path(revision)/'plans'/plan_identity(candidate)
    selected=ir.load(directory/'stage/accepted.json')
    ir.need(selected==projection(candidate),'Residual approval does not cover this target and route')
    ctx=ir.load(directory/'context.json')
    verify_bindings([ctx['basis'],ctx['native'],ctx['semantic_review'],*ctx['original_inputs'],*ctx['evidence']])
    ir.need(ctx['basis']==bind(directory/'stage/accepted.json') and ctx['semantic_review']==bind(directory/'review/report.json'),
            'Changed residual comparison authority')
    basis_native.verify(ctx['native']['path'])
    basis_review.verify(ctx['semantic_review'],ctx,selected)
    incident=event['incident']
    ir.need(isinstance(incident,str) and re.fullmatch(r'[0-9a-f]{32}',incident),'Invalid early decision incident')
    receipt=bind(directory/'decision/error-incidents'/(incident+'.json'))
    ir.need(event==verify_basis_decision(Path(revision).parents[1],receipt,'accept-conditional'),'Changed early approval')
