"""Explicit same-case reuse of an identical local Lean program, checked again."""
from pathlib import Path
import ir


def candidate(previous, cpath, plan, step):
    if previous is None:return None
    previous=Path(previous).resolve()
    oldc=previous/'inputs/contract.json';oldp=previous/'inputs/plan.json'
    report=ir.load(previous/'report.json');proofs=ir.load(previous/'proofs.json')
    oldplan=ir.load(oldp);oldcontract=ir.contract(oldc);current=ir.contract(cpath)
    ir.need(report['status']=='FRAGMENT_ASSEMBLED'
            and report['contract_sha256']==proofs['contract_sha256']==ir.digest(oldc)
            and proofs['plan_sha256']==ir.digest(oldp),'Stale prior proof-run evidence')
    if oldcontract['pins']!=current['pins'] or step not in proofs['proofs']:return None
    body=proofs['proofs'][step]
    try:
        oldtext=ir.render(oldc,oldplan,{step:body},only=step)
        newtext=ir.render(cpath,plan,{step:body},only=step)
    except ValueError:return None
    if oldtext!=newtext:return None
    return {'body':body,'previous_run':str(previous),'previous_proofs_sha256':ir.digest(previous/'proofs.json'),
            'scope':'Identical local Lean source and pins only; requires current native recheck'}
