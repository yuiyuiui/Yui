"""Explicit same-case reuse of an identical local Lean program, checked again."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import shutil
import textwrap
import ir


def same_port(oldc,oldplan,cpath,plan,step):
    old=ir.contract(oldc);new=ir.contract(cpath)
    if old['id']!=new['id'] or old['pins']!=new['pins'] or old['source']['sha256']!=new['source']['sha256']:return False
    before=ir.local_packet(oldc,oldplan,step);after=ir.local_packet(cpath,plan,step)
    return all(before[key]==after[key] for key in ['parameters','inputs','target','source_steps'])


def reviewed_repair(oldc,oldplan,cpath,plan,step,receipt):
    if receipt is None:return False
    import interface_review
    # A changed definition is allowed only after a real independent review of
    # the new interface, and every inherited body still gets current Lean checks.
    ppath=Path(receipt).parent/'inputs/plan.json'
    ir.need(ir.load(ppath)==plan,'Reviewed plan differs from the current program')
    interface_review.verify_receipt(receipt,cpath,ppath,ir.contract(cpath)['source']['sha256'])
    if not same_port(oldc,oldplan,cpath,plan,step):
        context=ir.load(receipt).get('internal_repair')
        if not context or context['contract']['sha256']!=ir.digest(oldc) or ir.load(context['plan']['path'])!=oldplan:
            return False
        if step not in context['affected_steps']:return False
    return True


def candidate(previous, cpath, plan, step, *, reviewed_interface=None, basis_revision=False):
    if previous is None:return None
    previous=Path(previous).resolve()
    oldc=previous/'inputs/contract.json';oldp=previous/'inputs/plan.json'
    report=ir.load(previous/'report.json')
    oldplan=ir.load(oldp);oldcontract=ir.contract(oldc);current=ir.contract(cpath)
    if oldcontract['id']!=current['id']:return None
    if oldcontract['source']['sha256']!=current['source']['sha256'] and not basis_revision:return None
    if report['status']=='FRAGMENT_ASSEMBLED':
        proofs=ir.load(previous/'proofs.json')
        ir.need(report['contract_sha256']==proofs['contract_sha256']==ir.digest(oldc)
                and proofs['plan_sha256']==ir.digest(oldp),'Stale prior proof-run evidence')
        evidence=previous/'proofs.json'
    else:
        import shared_lemmas
        ir.need(report['status'] in {'GRAPH_UNFINISHED','GRAPH_REPAIR_REQUIRED'}
                and report.get('contract_sha256')==ir.digest(oldc)
                and report.get('plan_digest')==shared_lemmas.hashed(oldplan)
                and isinstance(report.get('proofs'),dict),'Stale prior proof-run evidence')
        proofs={'proofs':report['proofs']};evidence=previous/'report.json'
        if step not in proofs['proofs']:return None
        jobs=[j for j in report.get('jobs',[]) if step in j.get('consumers',[j.get('step')])]
        ir.need(len(jobs)==1 and jobs[0]['status']=='LOCAL_PROOFS_CHECKED',
                'Prior partial node has no completed local job')
        job=jobs[0]
        checked=job.get('verification') if job['step']==step else job.get('alias_verification',{}).get(step)
        text=ir.render(oldc,oldplan,{step:proofs['proofs'][step]},only=step)
        ir.need(isinstance(checked,dict) and checked.get('exit_code')==0
                and checked.get('status')=='LOCAL-PROOF-CHECKED'
                and checked.get('scope')==step and checked.get('contract_sha256')==ir.digest(oldc)
                and checked.get('lean_sha256')==hashlib.sha256(text.encode()).hexdigest()
                and set(checked.get('axioms',[]))<={'propext','Classical.choice','Quot.sound'},
                'Prior partial node is not bound to its checked Lean source')
    if oldcontract['pins']!=current['pins'] or step not in proofs['proofs']:return None
    body=proofs['proofs'][step]
    try:
        oldtext=ir.render(oldc,oldplan,{step:body},only=step)
        newtext=ir.render(cpath,plan,{step:body},only=step)
    except ValueError:return None
    changed=oldtext!=newtext
    if basis_revision:
        before=ir.local_packet(oldc,oldplan,step);after=ir.local_packet(cpath,plan,step)
        # Both contracts have independent current source correspondence. Only the same
        # local obligation, use context and rendered Lean program can supply a candidate.
        before.pop('contract_sha256');after.pop('contract_sha256')
        if changed or before!=after:return None
    elif changed and not reviewed_repair(oldc,oldplan,cpath,plan,step,reviewed_interface):return None
    return {'body':body,'previous_run':str(previous),'previous_proofs_sha256':ir.digest(evidence),
            'scope':('Same accepted source/port after independently reviewed interface repair; requires current native recheck'
                     if changed else 'Identical local Lean source and pins only; requires current native recheck')}


def restore_repair_drafts(stage,previous,*,reviewed_interface=None):
    """Only this own node's qualified stopped round; retain failed work, not verdicts."""
    if previous is None:return None
    previous=Path(previous).resolve();old=previous/'workers'/stage.step
    if not (old/'result.json').is_file():return None
    result=ir.load(old/'result.json')
    if result.get('status') not in {'REPAIR_REQUESTED','REPAIR_WAIT'}:return None
    if not (old/'prompt.txt').is_file():return None
    # A sibling may have been retired during startup, before any candidate or
    # model response existed. There is nothing to inherit or qualify in that
    # case; its original runtime/cost record remains retained.
    files=sorted((old/'lean-drafts').glob('*.json'))
    if result.get('status')=='REPAIR_WAIT' and not files:return None
    from execution_health import record_qualification
    ir.need(record_qualification(result)['record_context_qualified'],'Unqualified prior proof-repair context')
    oldc=previous/'inputs/contract.json';oldplan=ir.load(previous/'inputs/plan.json')
    if not same_port(oldc,oldplan,stage.cpath,stage.plan,stage.step) and not reviewed_repair(
            oldc,oldplan,stage.cpath,stage.plan,stage.step,reviewed_interface):return None
    packet=ir.load(old/'prompt.txt')['packet'];current=__import__('json').loads(stage.prompt())['packet']
    if packet!=current and not reviewed_repair(oldc,oldplan,stage.cpath,stage.plan,stage.step,reviewed_interface):return None
    ir.need(result.get('model_selection')==stage.model_selection,'Prior own proof profile changed')
    restored=[]
    helpers=old/'local-helpers.json'
    if packet==current and helpers.is_file():
        import local_helpers
        rows=ir.load(helpers)
        local_helpers.validate(stage.cpath,stage.plan,stage.step,rows)
        stage.local_helpers=rows
        ir.write(stage.logs/'local-helpers.json',rows)
    for kind in ['proof','auxiliary']:
        for file in sorted((old/'lean-drafts').glob(kind+'-*.json')):
            ir.need(not file.is_symlink(),'Untrusted own-draft link')
            row=ir.load(file)
            ir.need(isinstance(row.get('proof'),str) and isinstance(row.get('statement'),str)
                    and isinstance(row.get('check'),dict),'Invalid retained own attempt')
            number=max(stage.own_lean_drafts[kind],default=0)+1
            row={**row,'previous_check':row['check'],'check':{'status':'RETAINED_UNACCEPTED_CANDIDATE',
                 'scope':'Prior diagnostic only; current checking required; no premise added'}}
            stage.own_lean_drafts[kind][number]=row
            ir.write(stage.logs/'lean-drafts'/f'{kind}-{number:04d}.json',row)
            stage.proof_progress.observe('check_transition' if kind=='proof' else 'check_auxiliary',
                {'proof':row['proof'],**({'statement':row['statement']} if kind=='auxiliary' else {})},row['check'],None)
            restored.append({'path':str(file),'sha256':ir.digest(file)})
    # Inherit deduplicated action identities so identical retries and reworded
    # blocker messages cannot create an endless series of diagnostic sessions.
    actions=old/'proof-progress-actions.json'
    if packet==current and actions.is_file():stage.proof_progress.seen.update(ir.load(actions)['actions'])
    stage.proof_progress.last_turn_revision=stage.proof_progress.revision
    receipt={'previous_stage':str(old),'result_sha256':ir.digest(old/'result.json'),
        'restored_files':restored,'scope':'Warm own-node repair, not a fresh attempt or accepted proof'}
    ir.write(stage.logs/'own-repair-draft-recovery.json',receipt)
    stage.system+=' This is a warm repair of this same own obligation. Inspect retained attempts through read_lean_draft. Prior checks are diagnostic only and never new assumptions or acceptance.'
    return receipt


def retain_recheck_failure(stage,candidate,checked):
    """Return an inherited own body and its new failure to the repairing worker."""
    ir.need(checked.get('exit_code')!=0 and isinstance(candidate.get('body'),(str,dict)),
            'Only a failed current recheck needs a repair draft')
    import local_helpers
    helpers,body=local_helpers.unpack(stage.cpath,stage.plan,stage.step,candidate['body'])
    if helpers:
        stage.local_helpers=deepcopy(helpers)
        ir.write(stage.logs/'local-helpers.json',helpers)
    number=max(stage.own_lean_drafts['proof'],default=0)+1
    row={'proof':body,'proof_package':candidate['body'],
        'statement':next(x['statement'] for x in stage.plan['steps'] if x['id']==stage.step),
        'check':checked,'origin':{k:v for k,v in candidate.items() if k!='body'}}
    stage.own_lean_drafts['proof'][number]=row
    ir.write(stage.logs/'lean-drafts'/f'proof-{number:04d}.json',row)
    stage.observe_proof_progress('check_transition',{'proof':row['proof']},checked)
    stage.proof_progress.last_turn_revision=stage.proof_progress.revision
    stage.system+=' An inherited own-node body failed its current native recheck. Read its retained draft and actual failure through read_lean_draft, then repair under the current reviewed interface. No prior proof is accepted in this context.'


def restore_cleanup_drafts(stage, previous):
    """Restore only an exact own obligation stopped by verified native cleanup."""
    if previous is None:return None
    old=Path(previous).resolve()/'workers'/stage.step
    if not (old/'result.json').is_file():return None
    result=ir.load(old/'result.json')
    if result.get('execution_fault')!='RuntimeError: Native process cleanup could not be confirmed':return None
    ir.need(result.get('status')=='UNFINISHED' and result.get('temporary_workspace_removed') is True
            and result.get('isolation_violation') is False
            and result.get('identity_and_input_boundary_verified') is True,
            'The stopped proof stage is not qualified for own-draft recovery')
    ir.need(ir.load(old/'prompt.txt')['packet']==json.loads(stage.prompt())['packet'],
            'Stopped proof packet differs; do not inherit its drafts')
    ir.need(result.get('model')==stage.model and
            result.get('effort')==stage.model_selection['reasoning_effort'],
            'Stopped proof profile differs')
    ir.need(result.get('model_selection',{}).get('speed')==stage.model_selection['speed'],
            'Stopped proof speed differs')
    restored=[]
    target=next(x['statement'] for x in stage.plan['steps'] if x['id']==stage.step)
    for kind in ('proof','auxiliary'):
        for file in sorted((old/'lean-drafts').glob(kind+'-*.json')):
            ir.need(not file.is_symlink(),'Untrusted prior draft link')
            row=ir.load(file);number=int(file.stem.split('-')[-1])
            ir.need(number>0 and isinstance(row.get('proof'),str) and isinstance(row.get('statement'),str),
                    'Invalid own draft record')
            if kind=='proof':ir.need(row['statement']==target,'Own proof draft target changed')
            stage.own_lean_drafts[kind][number]=row
            destination=stage.logs/'lean-drafts'/file.name;destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(file,destination)
            restored.append({'path':str(file),'sha256':ir.digest(file)})
    checkpoint=old/'native-cleanup-checkpoint.json'
    if checkpoint.is_file():
        binding=ir.load(checkpoint);file=old/'native-cleanup-source.lean'
        ir.need(ir.digest(file)==binding['source_sha256'],'Failed native source changed')
        marker='YUI_RECOVERY_BODY_0D2784B0'
        prototype=ir.render(stage.cpath,stage.plan,{stage.step:marker},only=stage.step)
        before,separator,after=prototype.partition('  '+marker+'\n')
        text=file.read_text();kind='proof';statement=target
        if separator and text.startswith(before) and text.endswith(after):
            body=textwrap.dedent(text[len(before):len(text)-len(after)])
            rendered=ir.render(stage.cpath,stage.plan,{stage.step:body},only=stage.step)
        else:
            delimiter=' : yui_aux_type% '
            ir.need(text.count(delimiter)==1,'Failed native source has a different frozen context')
            tail=text.split(delimiter,1)[1];statement,length=json.JSONDecoder().raw_decode(tail)
            prefix=' := by\n';suffix='#check @checked\n#print axioms checked\nend YuiAuxiliary\n'
            tail=tail[length:]
            ir.need(isinstance(statement,str) and tail.startswith(prefix) and tail.endswith(suffix),
                    'Invalid retained auxiliary wrapper')
            body=textwrap.dedent(tail[len(prefix):-len(suffix)])
            rendered=ir.render_auxiliary(stage.cpath,stage.plan,stage.step,statement,body)
            kind='auxiliary'
        ir.need(rendered==text,'Failed native body cannot be restored byte-faithfully')
        number=max(stage.own_lean_drafts[kind],default=0)+1
        row={'proof':body,'statement':statement,'check':{'status':'EXECUTION_FAULT',
             'error':result['execution_fault'],'source_sha256':binding['source_sha256'],
             'scope':'Retained own candidate only; no accepted proof or new premise'}}
        stage.own_lean_drafts[kind][number]=row
        ir.write(stage.logs/'lean-drafts'/f'{kind}-{number:04d}.json',row)
        restored.append({'path':str(file),'sha256':ir.digest(file)})
    receipt={'previous_stage':str(old),'result_sha256':ir.digest(old/'result.json'),
             'restored_files':restored,'acceptance':'NONE; current native checking remains required'}
    ir.write(stage.logs/'own-draft-recovery.json',receipt)
    stage.system+=' This is a disclosed operational continuation of this exact own obligation after a native cleanup fault. Retained own drafts are available through read_lean_draft; inspect its index. No prior candidate is accepted and no premise has been added.'
    return receipt
