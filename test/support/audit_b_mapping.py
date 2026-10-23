#!/usr/bin/env python3
"""Author an Audit B mapping with actual native build/dependency feedback."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from audit_a_campaign import CORE, bind, write, manifest
sys.path.insert(0,str(CORE/'scripts'))
sys.path.insert(0,str(CORE/'translation/scripts'))
import ir
import audit_b
import workflow
import concurrency
from clean_stage import ArtifactStage


PROMPT='''Complete the actual Audit B mapping for the frozen, assembled proof.
Read all supplied source inventory, original graph/spec, contract/plan, completed
proof bodies, initial mapping and relevant Yui Audit B rules. Submit the complete
mapping object, preserving its version/source_inventory_sha256 and exact source
entry IDs. For each source H/E/M/N/P/D supply the actual selector and complete
expected Lean type, with all parameters and conditional input binders in order.
H/E selectors remain premise:ID; P is decl:AuditBExport.P; N uses its actual
decl:Translation.Tddd from the frozen source-output mapping. For each source M
also provide its complete library_type and a real Lean tactic-body library_term
discharging that intermediate root from the named pinned declaration, retaining
all hypotheses. No sorry, admit, extra axiom or changed theorem is permitted.
calculation_links may map actual imported proof names only to genuinely matching
explicit original logic.calculations indices. Do not classify substantive
mathematics as arithmetic, add a new calculation policy or silently use an
unlisted theorem. A truly additional mathematical source requires a new source
revision/review; it cannot be approved by this mapping stage. check_draft gives
real clean compiler, full-type and actual dependency feedback, not automatic
semantic approval. Correct legitimate implementation/mapping errors. No
performance result or final Audit B pass is implied by a successful build.
'''


def prepare(directory,out):
    directory,out=[Path(p).resolve() for p in (directory,out)]
    frozen=workflow.bound(directory)
    if ir.load(directory/'proof-run/report.json')['status']!='FRAGMENT_ASSEMBLED':raise ValueError('Actual assembled proof required')
    if not (directory/'audit-b').exists():workflow.prepare_audit(directory)
    out.mkdir(parents=True,exist_ok=False);inputs=out/'inputs';inputs.mkdir()
    for name in ['mapping.json','source-inventory.json']:
        shutil.copyfile(directory/'audit-b'/name,inputs/name)
    for name,path in [('contract.json',directory/'proof-run/inputs/contract.json'),
                      ('plan.json',directory/'proof-run/inputs/plan.json'),
                      ('proofs.json',directory/'proof-run/proofs.json'),
                      ('spec.json',Path(frozen['authority']['spec'])),
                      ('nl0.json',Path(frozen['authority']['graph']))]:shutil.copyfile(path,inputs/name)
    write(inputs/'source-outputs.json',frozen['source_outputs'])
    manifest(inputs);(out/'prompt.txt').write_text(PROMPT)
    write(out/'authority.json',{'workflow':str(directory),'manifest':bind(directory/'manifest.json')})
    shutil.copyfile(__file__,out/'controller.py.snapshot.txt')


class MappingContract:
    def __init__(self,out):self.out=Path(out).resolve();self.attempt=0

    def __call__(self,value):
        authority=ir.load(self.out/'authority.json');directory=Path(authority['workflow'])
        frozen=workflow.bound(directory)
        cpath=directory/'proof-run/inputs/contract.json';ppath=directory/'proof-run/inputs/plan.json'
        c=ir.contract(cpath);inventory=ir.load(directory/'audit-b/source-inventory.json')
        if value.get('source_inventory_sha256')!=ir.digest(directory/'audit-b/source-inventory.json'):raise ValueError('Map the exact original inventory')
        audit_b.validate_mapping(c,inventory,value)
        self.attempt+=1;candidate=self.out/'candidates'/str(self.attempt).zfill(4)
        audit_b.prepare(cpath,ppath,directory/'proof-run/proofs.json',candidate,**{k:Path(v) if v else None for k,v in frozen['authority'].items()})
        write(candidate/'mapping.json',value)
        result=audit_b.build(candidate)
        if result['status']!='AUDIT-B-MECHANICAL-PASSED':
            compiler=ir.load(candidate/'compiler.json')
            raise ValueError('Actual Audit B build/dependency feedback: '+json.dumps(result,ensure_ascii=False)[:10000]+
                             '\nCompiler:\n'+compiler['stdout'][:12000]+compiler['stderr'][:1000])
        write(self.out/'accepted-mapping-path.json',{'candidate':str(candidate),'mapping':bind(candidate/'mapping.json'),
            'status':'MECHANICAL_ONLY_FRESH_SEMANTIC_AUDIT_REQUIRED'})
        return result


def run(out,timeout=1800,budget=None):
    out=Path(out).resolve();stage=ArtifactStage(out/'stage',(out/'prompt.txt').read_text(),phase='audit-b-mapping',
        inputs=out/'inputs/inputs.json',library=True,timeout=timeout,validator=MappingContract(out),
        budget=budget or concurrency.Budget(concurrency.resolve()))
    return stage.execute()[0]


def adopt(out):
    out=Path(out).resolve();result=ir.load(out/'stage/result.json')
    if result.get('status')!='ACCEPTED' or result.get('exposure',{}).get('status')!='TRANSMITTED-EXPOSURE-CHECK-PASSED':
        raise ValueError('Actual submitted, exposure-qualified mapping required')
    choice=ir.load(out/'accepted-mapping-path.json');candidate=Path(choice['candidate'])
    if ir.load(out/'stage/accepted.json')!=ir.load(candidate/'mapping.json'):raise ValueError('Candidate differs from actual final mapping')
    directory=Path(ir.load(out/'authority.json')['workflow']);workflow.bound(directory)
    if (directory/'audit-b.initial-pending').exists():raise ValueError('Preserve prior adopted audit; use a new workflow')
    (directory/'audit-b').rename(directory/'audit-b.initial-pending')
    shutil.copytree(candidate,directory/'audit-b')
    audit_b.bound_inputs(directory/'audit-b')
    return {'status':'ACTUAL_BUILD_READY_FOR_FRESH_SEMANTIC_AUDIT','audit':str(directory/'audit-b')}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run','adopt']);p.add_argument('--out',required=True);p.add_argument('--workflow');p.add_argument('--timeout-seconds',type=int,default=1800)
    args=p.parse_args();result=prepare(args.workflow,args.out) if args.command=='prepare' else run(args.out,args.timeout_seconds) if args.command=='run' else adopt(args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))
