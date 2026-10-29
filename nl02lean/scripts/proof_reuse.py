"""Explicit same-case reuse of an identical local Lean program, checked again."""
from pathlib import Path
import hashlib
import json
import shutil
import textwrap
import ir


def candidate(previous, cpath, plan, step):
    if previous is None:return None
    previous=Path(previous).resolve()
    oldc=previous/'inputs/contract.json';oldp=previous/'inputs/plan.json'
    report=ir.load(previous/'report.json')
    oldplan=ir.load(oldp);oldcontract=ir.contract(oldc);current=ir.contract(cpath)
    if report['status']=='FRAGMENT_ASSEMBLED':
        proofs=ir.load(previous/'proofs.json')
        ir.need(report['contract_sha256']==proofs['contract_sha256']==ir.digest(oldc)
                and proofs['plan_sha256']==ir.digest(oldp),'Stale prior proof-run evidence')
        evidence=previous/'proofs.json'
    else:
        import shared_lemmas
        ir.need(report['status']=='GRAPH_UNFINISHED'
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
    if oldtext!=newtext:return None
    return {'body':body,'previous_run':str(previous),'previous_proofs_sha256':ir.digest(evidence),
            'scope':'Identical local Lean source and pins only; requires current native recheck'}


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
