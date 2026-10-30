"""Native final-gate fixtures; all supplied review judgments are synthetic controls."""
from copy import deepcopy
from pathlib import Path
import shutil

from audit_a_fixtures import synthetic_stage
import audit_a_campaign as campaign
import audit_b
import interface_review
import ir
import translation_author
import workflow


def qualified_artifact(stage,artifact):
    exposure={'status':'TRANSMITTED-EXPOSURE-CHECK-PASSED','actual_model_ids':[__import__('run_pilot').MODEL],'standard_tier_verified':True}
    for name,value in [('accepted.json',artifact),('exposure-audit.json',exposure),
        ('execution-manifest.json',{'fixture':'SYNTHETIC review execution; not an actual mathematical audit'}),
        ('result.json',{'status':'ACCEPTED','model':__import__('run_pilot').MODEL,
            'execution_health':'NO_RECORDED_FAULT','temporary_workspace_removed':True,
            'usage':{'complete':False},'exposure':exposure})]:ir.write(Path(stage)/name,value)


def frozen_case(root):
    import harness_support
    root=Path(root);source=root/'source'
    shutil.copytree(harness_support.CORE/'tests/fixtures/closed-addition',source)
    (source/'audit-a.json').unlink()
    campaign.prepare(source,source,root/'audit-a')
    for job in ir.load(root/'audit-a/campaign.json')['jobs']:synthetic_stage(root/'audit-a'/job['id'])
    assert campaign.collect(root/'audit-a',None)['full_acceptance']
    author=root/'author';translation_author.prepare(source,source,author)
    validator=translation_author.InterfaceContract(author)
    payload={'header':'import Mathlib\n','parameters':[{'name':k,'type':'ℕ'} for k in ('a','b')],
        'premise_types':{'H001':'a = b'},'conclusion_type':'a + 0 = b',
        'representation':'The same natural numbers and equality.','objects':[],
        'steps':[{'id':'T001','statement':'b = a','inputs':['H001'],'source_steps':['S001'],'explanation':'Equality symmetry.'},
                 {'id':'T002','statement':'a + 0 = b','inputs':['T001'],'source_steps':['S002','S003'],'explanation':'Additive identity and symmetry.'}],
        'terminal':'T002','source_outputs':{'N001':'T001','P':'T002'},
        'endpoint_correspondence':{'P':{'mode':'direct','explanation':'Natural-number equality with the original a=b hypothesis.'}}}
    validator(payload);qualified_artifact(author/'stage',payload)
    reviewed=root/'interface-review';interface_review.prepare(author,reviewed)
    checks={key:{'verdict':'PASS','notes':'SYNTHETIC known propositional/natural-number fixture; no actual semantic model called.',
        'locations':[{'document':'spec.json','pointer':'/full_target'},{'document':'contract.json','pointer':'/conclusion/type'}]} for key in workflow.INTERFACE_CHECKS}
    qualified_artifact(reviewed/'stage',{'checks':checks,'findings':[]});interface_review.collect(reviewed)
    paths=ir.load(author/'accepted-interface-paths.json');out=root/'workflow'
    manifest=workflow.freeze(source/'nl0.json',source/'spec.json',paths['contract'],paths['plan'],reviewed/'review.json',out,
        audit_a=source/'audit-a.json',max_concurrency=1)
    proof=out/'proof-run';proof.mkdir()
    import run_graph
    cp,_=run_graph.package(Path(manifest['contract']),Path(manifest['plan']),proof)
    bodies={'T001':'exact h_H001.symm','T002':'simpa only [Nat.add_zero] using h_T001.symm'}
    ir.write(proof/'proofs.json',{'contract_sha256':ir.digest(cp),'plan_sha256':ir.digest(proof/'inputs/plan.json'),'proofs':bodies})
    ir.write(proof/'report.json',{'status':'FRAGMENT_ASSEMBLED','concurrency':{'requested':1},'runner_wall_seconds':0})
    return out


def build(out,variant='normal'):
    out=Path(out);frozen=workflow.bound(out);selected=workflow.proof_run(out)
    if variant=='normal':workflow.prepare_audit(out)
    else:
        changed=out/'deliberately-drifted-fixture';changed.mkdir()
        c=ir.contract(frozen['contract']);plan=ir.load(frozen['plan']);proofs=ir.load(selected/'proofs.json')
        c['conclusion']['type']='(a + 0 = b) ∧ True' if variant=='faithful' else 'True'
        plan['steps'][-1]['statement']=c['conclusion']['type']
        proofs['proofs']['T002']=('exact ⟨by simpa only [Nat.add_zero] using h_T001.symm, True.intro⟩'
            if variant=='faithful' else 'exact True.intro')
        ir.write(changed/'contract.json',c);plan['contract_sha256']=ir.digest(changed/'contract.json')
        ir.write(changed/'plan.json',plan);shutil.copyfile(Path(frozen['contract']).parent/c['source']['path'],changed/c['source']['path'])
        proofs.update(contract_sha256=ir.digest(changed/'contract.json'),plan_sha256=ir.digest(changed/'plan.json'))
        ir.write(changed/'proofs.json',proofs)
        audit_b.prepare(changed/'contract.json',changed/'plan.json',changed/'proofs.json',out/'audit-b',**frozen['authority'])
    return audit_b.build(out/'audit-b',frozen_contract=frozen['contract'])
