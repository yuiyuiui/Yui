#!/usr/bin/env python3
"""Author an Audit B mapping with actual native build/dependency feedback."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'nl0/scripts'))
from controller_common import CORE, bind, write, manifest
sys.path.insert(0,str(CORE/'nl0/scripts'))
sys.path.insert(0,str(CORE/'nl02lean/scripts'))
import ir
import audit_b
import workflow
import concurrency
from clean_stage import ArtifactStage, read_page
import model_pilot as pilot


PROMPT='''Act as the single postprocessing/assembly author after all required local
proofs have been checked. Read nl02lean/references/assembly.md. Close the
dependency graph using the actual frozen proof bodies; complete any retained M
library discharges and source-facing export through the checked assembly tool.
You are not the independent Audit B reviewer. Do not rerun local proof authors,
reconstruct NL0, change a frozen interface, add assumptions or declare a PASS.
Your submission is the complete mapping object used to build the proof, not a
progress report. The tool first compiles standalone Proof.lean, then separately
inspects actual kernel signatures/dependencies. Normal final acceptance is a
machine check inheriting frozen pre-proof semantics; only proof-valid interface
drift may open B-final. Routine correctable mapping,
library application or diagnostic issues are local implementation work.
Preserve your draft and use the exact candidate number in feedback. The
read_assembly_feedback tool pages your own generated source and complete
compiler/mechanical records; do not stop merely because a short excerpt ends.
Complete endpoint correspondence and the standalone proof export for the frozen
proof. Read the source inventory, contract/plan and initial mapping; consult
original definitions and relevant proof bodies when needed. Preserve the
version, policy and source_inventory_sha256. entries contains exactly every E
and P, not H/M/N/D rows. E selectors are premise:ID; P is decl:AuditBExport.P.
Supply each complete expected Lean type and {mode:direct|equivalent,
explanation:<concise account>} in its correspondence field. Reuse the interface
author's notes, correcting inaccurate explanations against the actual encoding.
The target means the whole theorem, including parameters and hypotheses.
For a direct encoding a short explanation is enough. For equivalent encodings,
explain the identification, assumptions and both directions; do not invent a
duplicate formal representation solely to make a literal-name match. Actual
cross-representation steps in the proof must have checked conversions.

library_terms contains a Lean tactic body for each intermediate M port still
in the contract; discharge it using the pinned Mathlib environment. Any pinned
library theorem is available: no name whitelist, library_type copy, source M
matching or calculation_links is required. Audit A notes are optional local
references. They neither restrict library use nor add assumptions. Do not
restate or retype every note. No sorry, admit, unproved local axiom, changed
frozen theorem or extra project premise is permitted. check_draft returns real
standalone compilation and endpoint type/kernel-closure feedback. Passing it
is not the independent semantic Audit B. Preserve and repair your own mapping
and assembly candidates after actual feedback.
Optional proof_patches maps existing T IDs to replacement internal tactic bodies.
Prove helpers inside those bodies as needed; do not change E/P, the frozen plan,
definitions determining their meaning, or replace a missing producer by a premise.
'''


def prepare(directory,out):
    directory,out=[Path(p).resolve() for p in (directory,out)]
    frozen=workflow.bound(directory)
    selected=workflow.proof_run(directory)
    if ir.load(selected/'report.json')['status'] not in {'FRAGMENT_ASSEMBLED','GRAPH_ASSEMBLY_REPAIR_REQUIRED'}:raise ValueError('All actual local proof bodies required')
    if not (directory/'audit-b').exists():workflow.prepare_audit(directory)
    out.mkdir(parents=True,exist_ok=False);inputs=out/'inputs';inputs.mkdir()
    for name in ['mapping.json','source-inventory.json']:
        shutil.copyfile(directory/'audit-b'/name,inputs/name)
    for name,path in [('contract.json',selected/'inputs/contract.json'),
                      ('plan.json',selected/'inputs/plan.json'),
                      ('proofs.json',selected/'proofs.json'),
                      ('spec.json',Path(frozen['authority']['spec'])),
                      ('nl0.json',Path(frozen['authority']['graph']))]:shutil.copyfile(path,inputs/name)
    write(inputs/'source-outputs.json',frozen['source_outputs'])
    manifest(inputs);(out/'prompt.txt').write_text(PROMPT)
    write(out/'authority.json',{'workflow':str(directory),'manifest':bind(directory/'manifest.json')})
    shutil.copyfile(__file__,out/'controller.py.snapshot.txt')


class MappingContract:
    def __init__(self,out):
        self.out=Path(out).resolve();self.attempt=0;self.checked={}
        for name in ('drafts','feedback'):(self.out/name).mkdir(parents=True,exist_ok=True)

    def __call__(self,value):
        authority=ir.load(self.out/'authority.json');directory=Path(authority['workflow'])
        frozen=workflow.bound(directory)
        selected=workflow.proof_run(directory)
        cpath=selected/'inputs/contract.json';ppath=selected/'inputs/plan.json'
        c=ir.contract(cpath);inventory=ir.load(directory/'audit-b/source-inventory.json')
        self.attempt+=1;candidate=self.out/'candidates'/str(self.attempt).zfill(4)
        write(self.out/'drafts'/f'{self.attempt:04d}.json',value)
        patches=value.get('proof_patches',{})
        value={k:v for k,v in value.items() if k!='proof_patches'}
        try:
            ir.need(isinstance(patches,dict),'Internal proof patches must be an object')
            bundle=ir.load(selected/'proofs.json')
            ir.need(set(patches)<=set(bundle['proofs']),'Connection repair cannot create a missing node or change its interface')
            for body in patches.values():ir.proof_text(body)
            bundle['proofs'].update(patches)
            if value.get('source_inventory_sha256')!=ir.digest(directory/'audit-b/source-inventory.json'):
                raise ValueError('Map the exact original inventory')
            audit_b.validate_mapping(c,inventory,value)
            key=hashlib.sha256(json.dumps([value,patches,bundle],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            cached=self.checked.get(key)
            if cached:
                old=Path(cached['candidate']);audit_b.bound_inputs(old)
                mechanical=ir.load(old/'mechanical.json')
                if (ir.load(old/'mapping.json')==value and mechanical['passed']
                        and all(ir.digest(old/name)==sha for name,sha in mechanical['artifacts'].items())):
                    candidate=old;result={**cached['result'],'reused_exact_native_check':True}
                else:
                    cached=None
            if not cached:
                bpath=self.out/'proof-bundles'/f'{self.attempt:04d}.json';write(bpath,bundle)
                audit_b.prepare(cpath,ppath,bpath,candidate,**{k:Path(v) if v else None for k,v in frozen['authority'].items()})
                write(candidate/'mapping.json',value)
                result=audit_b.build(candidate,frozen_contract=frozen['contract'])
            if result['status']!='AUDIT-B-MECHANICAL-PASSED':
                from final_acceptance import proof_integrity
                proof_integrity(candidate)
                result.update(interface_deviation_requires_b_final=True)
        except (ValueError,KeyError,TypeError) as error:
            report={'candidate':self.attempt,'error':str(error),'native_candidate':str(candidate) if candidate.exists() else None}
            write(self.out/'feedback'/f'{self.attempt:04d}.json',report)
            raise ValueError(f'Candidate {self.attempt}: {error}\n'+diagnostics(candidate)+
                f'\nRead complete own feedback with read_assembly_feedback(candidate={self.attempt}, kind=..., start=1, end=250).') from error
        self.checked[key]={'candidate':str(candidate),'result':result}
        write(self.out/'feedback'/f'{self.attempt:04d}.json',{'candidate':self.attempt,'native_candidate':str(candidate),'result':result})
        write(self.out/'accepted-mapping-path.json',{'candidate':str(candidate),'mapping':bind(candidate/'mapping.json'),
            'status':'PROOF_INTEGRITY_CHECKED_FINAL_INTERFACE_GATE_REQUIRED',
            'proof_patches':patches})
        return result


def diagnostics(candidate):
    """Put actual errors ahead of long printed signatures; preserve full files."""
    import re
    excerpts=[]
    for name in ('assembly-compiler.json','compiler.json'):
        path=Path(candidate)/name
        if not path.exists():continue
        compiler=ir.load(path);lines=compiler.get('stdout','').splitlines();selected=[]
        positions=[i for i,line in enumerate(lines) if re.search(r':\d+:\d+: error',line)]
        for i in positions[:8]:selected.extend(lines[max(0,i-1):i+20])
        if not positions:selected=lines[-35:]
        excerpts.append(name+':\n'+'\n'.join(selected)[:12000]+'\n'+compiler.get('stderr','')[:2000])
    return '\n'.join(excerpts)[:24000]


class AssemblyStage(ArtifactStage):
    """One author thread with read-only access to its own assembly feedback."""
    FILES={'proof_source':'Proof.lean','audit_source':'Audit.lean','assembly_inputs':'AssemblyInputs.lean',
           'mechanical':'mechanical.json','assembly':'assembly.json','inspection':'inspection.json',
           'compiler_stdout':'compiler.json','compiler_stderr':'compiler.json',
           'assembly_stdout':'assembly-compiler.json','assembly_stderr':'assembly-compiler.json'}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.tools.append(pilot.carrier.tool('read_assembly_feedback',
            'Read only this author stage\'s saved candidate, generated proof or full native diagnostics. Positive candidate ID; inclusive line bounds. No other case or arbitrary path is accessible.',
            {'candidate':{'type':'integer'},'kind':{'type':'string','enum':['mapping','feedback',*self.FILES]},
             'start':{'type':'integer'},'end':{'type':'integer'},'column':{'type':'integer'}},['candidate','kind','start','end']))
        self.tool_names={t['name'] for t in self.tools}

    def dispatch(self,name,args):
        if name!='read_assembly_feedback':return super().dispatch(name,args)
        if not hasattr(self.validator,'attempt'):
            return {'accepted':False,'error':'This assignment is connection diagnosis; read its declared inputs before reporting the repair route.'}
        try:
            number=args['candidate'];kind=args['kind']
            if type(number) is not int or not 1<=number<=self.validator.attempt:
                raise ValueError('Read an existing positive own candidate number')
            out=self.validator.out
            if kind in {'mapping','feedback'}:
                path=out/('drafts' if kind=='mapping' else 'feedback')/f'{number:04d}.json'
                text=path.read_text()
            else:
                feedback=ir.load(out/'feedback'/f'{number:04d}.json')
                native=Path(feedback.get('native_candidate') or out/'candidates'/f'{number:04d}')
                if not native.resolve().is_relative_to((out/'candidates').resolve()):raise ValueError('Invalid own native candidate binding')
                path=native/self.FILES[kind]
                text=(ir.load(path)['stdout' if kind.endswith('stdout') else 'stderr']
                      if kind.endswith(('stdout','stderr')) else path.read_text())
            result=read_page(text,args['start'],args['end'],column=args.get('column',0),metadata={'candidate':number,'kind':kind})
        except (OSError,ValueError,KeyError,TypeError) as error:
            result={'accepted':False,'error':str(error)}
        pilot.carrier.append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,'wall_seconds':0})
        return result


def run(out,timeout=None,budget=None):
    out=Path(out).resolve();stage=AssemblyStage(out/'stage',(out/'prompt.txt').read_text(),phase='audit-b-assembly',
        inputs=out/'inputs/inputs.json',library=True,timeout=timeout,validator=MappingContract(out),
        budget=concurrency.serial_budget(budget))
    return stage.execute()[0]


def adopt(out):
    out=Path(out).resolve();result=ir.load(out/'stage/result.json')
    if result.get('status')!='ACCEPTED' or not __import__('execution_health').record_qualification(result)['submitted_record_qualified']:
        raise ValueError('Actual submitted, exposure-qualified mapping required')
    choice=ir.load(out/'accepted-mapping-path.json');candidate=Path(choice['candidate'])
    actual=ir.load(out/'stage/accepted.json');actual.pop('proof_patches',None)
    if actual!=ir.load(candidate/'mapping.json'):raise ValueError('Candidate differs from actual final mapping')
    directory=Path(ir.load(out/'authority.json')['workflow']);workflow.bound(directory)
    if (directory/'audit-b.initial-pending').exists():raise ValueError('Preserve prior adopted audit; use a new workflow')
    (directory/'audit-b').rename(directory/'audit-b.initial-pending')
    shutil.copytree(candidate,directory/'audit-b')
    if choice.get('proof_patches'):
        write(directory/'assembly-proof-patches.json',{'patches':choice['proof_patches'],
            'actual_author_submission':bind(out/'stage/accepted.json'),'compiled_proof':bind(directory/'audit-b/Proof.lean')})
    audit_b.bound_inputs(directory/'audit-b')
    return {'status':'ACTUAL_BUILD_READY_FOR_FRESH_SEMANTIC_AUDIT','audit':str(directory/'audit-b')}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run','adopt']);p.add_argument('--out',required=True);p.add_argument('--workflow');p.add_argument('--timeout-seconds',type=int,default=None)
    args=p.parse_args();result=prepare(args.workflow,args.out) if args.command=='prepare' else run(args.out,args.timeout_seconds) if args.command=='run' else adopt(args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))
