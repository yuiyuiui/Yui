#!/usr/bin/env python3
"""Clean typed-interface authoring adapter for the selected exercise tests.

The model chooses every representation/type/plan. The controller copies exact
accepted source paragraphs, binds metadata and returns real Lean type feedback.
Successful elaboration is not semantic review, proof acceptance or Audit B.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from copy import deepcopy

from audit_a_campaign import ROOT,CORE,write,bind,manifest
sys.path.insert(0,str(CORE/'scripts'))
sys.path.insert(0,str(CORE/'translation/scripts'))
import ir
import nl0
import source_preparation
import concurrency
from clean_stage import ArtifactStage
import model_pilot as pilot
from artifact_validation import expand_submission


def expand_interface(value,documents,drafts):
    """Reuse the validated data-edit engine without executing model code."""
    if not any(key in value for key in ['base_input','base_candidate','accept_candidate']):
        return deepcopy(value),None
    wrapped={}
    for key,text in documents.items():
        try:row=json.loads(text)
        except (ValueError,TypeError):continue
        if isinstance(row,dict) and 'conclusion_type' in row:
            wrapped[key]=json.dumps({'spec':row,'graph':{}},ensure_ascii=False)
    own={n:json.dumps({'spec':v,'graph':{}},ensure_ascii=False) for n,v in drafts.items()}
    command=deepcopy(value)
    for change in command.get('patches',[]):
        if not isinstance(change,dict) or not isinstance(change.get('path'),str) or not change['path'].startswith('/'):
            raise ValueError('Edit an existing interface field with an absolute JSON pointer')
        change['path']='/spec'+change['path']
    result,receipt=expand_submission(command,wrapped,own)
    return result['spec'],receipt


PROMPT='''Author the actual Lean interface and local typed plan for the exact
accepted NL0, preserving its mathematical content and proof route. Read every
task input and relevant Yui translation/architecture/Audit B rules. No earlier
Lean proof, hidden reference type or external project is available. Only the
explicit accepted source, task and pinned Mathlib are mathematical inputs.
Submit JSON with exactly header,parameters,premise_types,conclusion_type,
representation,objects,steps,terminal,source_outputs. header starts with import
Mathlib and contains only mathematical definitions/notation/structures needed
for the representation, never a proved/assumed conclusion, helper axiom,
opaque declaration, executable metaprogram, placeholder or result hidden in a
structure field. Mathematical proof lemmas belong in typed steps for workers.
parameters is a list of {name,type,binder_kind?} defining a coherent Lean context;
optional binder_kind is explicit (default), implicit or instance. Use instance
for legitimate typeclass data such as Field K instead of broken ordinary binders.
Include
every legitimate object/field/structure prerequisite explicitly and do not
introduce stronger assumptions than source H. premise_types maps exactly each
source root H/E/M ID to its complete faithful Lean type. conclusion_type is the
full exact target, not a surrogate standard-basis/special-case problem. All
definitions, original assumptions and changes of representation must match
NL0; if equivalent representations are used, include explicit planned typed
conversion steps for workers, rather than new assumptions. Their proof bodies
are required during final assembly/Audit B, not this interface phase. In particular arbitrary admissible lattices,
the scalar-extension construction, characteristic 2 and lambda=0 cannot be
discarded in the Lie exercise. Full source paragraphs and allowed root IDs
are in source-map.json. The controller copies them into the contract exactly.
steps is a list of {id:Tddd,statement:<Lean Prop>,inputs:[root/T IDs],
source_steps:[the supplied distinct S IDs],explanation:<specific implementation
route>}; include useful small closed obligations following those paragraphs.
Inspect concentration before freeze: isolate useful independent subarguments
and representation bridges, without forcing a fixed node count or rewriting NL0.
Every retained step reaches terminal; cover every source paragraph and realize
each N/P source output in source_outputs:{sourceID:TID}. The terminal type is
exactly conclusion_type. objects is a list of optional v2 object/view records
as in Yui architecture; an empty list is permitted if no special views are used.
representation is a detailed string explaining actual domains, scalar fields,
objects, and encodings, not a claim of semantic approval. check_artifact returns
real structural/type elaboration feedback in the isolated Lean sandbox. Repair
typing mistakes without changing the theorem or assuming missing results.
Build and check the representation incrementally: search actual Mathlib APIs,
then use check_lean_types on an incomplete definition header and selected
parameter/type expressions before submitting the whole interface. This probe
never accepts an interface, proves a lemma, or adds a premise. Do not wait until
the whole lattice/tensor encoding is perfected before trying concrete types.
No Lean proof is required in this authoring stage; every mathematical step is
an unproved obligation for later workers. A type-check pass requires an actual
separate source-fidelity/interface review before freeze and proof execution.
'''


def prepare(case,problem,out):
    case,problem,out=[Path(p).resolve() for p in (case,problem,out)]
    data=nl0.validate(case/'nl0.json',case/'spec.json',case/'audit-a.json')
    if not data[0]['current_standard_receipt_valid']:raise ValueError('Accepted current Audit A is required before interface authoring')
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(__file__,out/'controller.py.snapshot.txt')
    inputs=out/'inputs';inputs.mkdir()
    for f in ['spec.json','nl0.json']:shutil.copyfile(case/f,inputs/f)
    for f in ['problem.md','source-context.md','frozen-target.md']:
        if (problem/f).exists():shutil.copyfile(problem/f,inputs/f)
    paragraphs=[];mapping={}
    for rid,r in data[4].items():
        for s in r['argument']:
            identifier='S'+str(len(paragraphs)+1).zfill(3)
            paragraphs.append({'id':identifier,'text':s['text']})
            mapping[identifier]={'inference':rid,'paragraph':s['id']}
    source_map={'source_steps':paragraphs,'paragraph_mapping':mapping,
        'roots':[{'id':p['id'],'kind':p['kind'],'statement':p['statement']} for p in data[3].values() if p['kind'] in {'hypothesis','external','mathlib'}],
        'source_outputs':{r['output']:data[3][r['output']]['statement'] for r in data[4].values()},
        'direct_boundaries':{rid:{'inputs':r['inputs'],'output':r['output']} for rid,r in data[4].items()}}
    write(inputs/'source-map.json',source_map)
    manifest(inputs);(out/'prompt.txt').write_text(PROMPT)
    write(out/'authority.json',{'case':str(case),'graph':bind(case/'nl0.json'),'spec':bind(case/'spec.json'),'audit_a':bind(case/'audit-a.json')})
    inventory=source_preparation.inventory(case/'nl0.json',case/'spec.json',case/'audit-a.json')
    write(out/'source-inventory.json',inventory)
    write(out/'source-selection.json',{'selected_graph':bind(case/'nl0.json'),'shared_extraction':'NONE_SELECTED',
        'basis':'Inspect existing source consumers before interface work. No cross-inference repeated derivation is selected in this test preparation; no NL0 rewrite or inherited audit is claimed.'})


class InterfaceContract:
    def __init__(self,out):
        self.out=Path(out).resolve();self.attempt=0
        self.spec=json.loads((self.out/'inputs/spec.json').read_text())
        self.graph=json.loads((self.out/'inputs/nl0.json').read_text())
        self.source=json.loads((self.out/'inputs/source-map.json').read_text())
        self.documents={p.name:p.read_text() for p in (self.out/'inputs').iterdir() if p.is_file() and p.name!='inputs.json'}
        self.drafts={}

    def __call__(self,value):
        expanded,edits=expand_interface(value,self.documents,self.drafts)
        value.clear();value.update(expanded)
        expected={'header','parameters','premise_types','conclusion_type','representation','objects','steps','terminal','source_outputs'}
        if not expected<=set(value) or not set(value)<=expected|{'shared_obligations'}:raise ValueError('Expected '+', '.join(sorted(expected))+'; optional shared_obligations')
        header=value['header']
        # This screens candidate definitions before isolated elaboration; a
        # separate actual semantic reviewer still decides whether they are faithful.
        if not isinstance(header,str) or not header.startswith('import Mathlib\n'):
            raise ValueError('Header must start with import Mathlib followed by a newline')
        if re.search(r'\b(sorry|admit|axiom|opaque|unsafe|run_meta|run_elab|run_tac|native_decide|initialize|elab|macro|syntax|theorem|lemma|set_option)\b|(^|\n)\s*#',header):
            raise ValueError('Candidate header may define mathematical objects, not execute code or supply mathematical proof/result declarations')
        if set(value['premise_types'])!={p['id'] for p in self.source['roots']}:
            raise ValueError('Provide exactly the complete permitted H/E/M root types')
        if set(value['source_outputs'])!=set(self.source['source_outputs']):
            raise ValueError('Map exactly every source N/P to its primary typed T')
        self.attempt+=1;directory=self.out/'candidates'/f'{self.attempt:04d}';directory.mkdir(parents=True)
        self.drafts[self.attempt]=deepcopy(value)
        write(directory/'artifact.json',value)
        if edits is not None:write(directory/'explicit-edits.json',edits)
        shutil.copyfile(self.out/'inputs/nl0.json',directory/'nl0.json')
        contract={'version':2,'id':self.spec['case_id'].replace('-','_'),
            'source':{'path':'nl0.json','sha256':ir.digest(directory/'nl0.json')},
            'source_steps':self.source['source_steps'],'pins':self.spec['pins'],
            'header':header,'parameters':value['parameters'],
            'premises':[{**p,'type':value['premise_types'][p['id']]} for p in self.source['roots']],
            'conclusion':{'statement':self.graph['propositions'][next(i for i,p in enumerate(self.graph['propositions']) if p['id']=='P')]['statement'],'type':value['conclusion_type']},
            'representation':value['representation'],'objects':value['objects'],'shared_obligations':value.get('shared_obligations',[]),
            'review':{'mode':'development_owner_review','status':'PENDING_ACTUAL_SEMANTIC_REVIEW','disclosure':'Candidate generated in a clean selected-model context; only syntax/types are checked by this adapter.'}}
        write(directory/'contract.json',contract)
        plan={'version':2,'contract_sha256':ir.digest(directory/'contract.json'),
              'representation_notes':value['representation'],'steps':value['steps'],'terminal':value['terminal']}
        write(directory/'plan.json',plan)
        ir.validate(directory/'contract.json',plan)
        decomposition=ir.decomposition(directory/'contract.json',plan)
        write(directory/'decomposition.json',decomposition)
        result=ir.check(directory/'contract.json',plan,types_only=True,out=directory/'types',timeout=120)
        if result['exit_code']!=0:
            raise ValueError('Actual Lean type check failed:\n'+result['stdout'][:14000]+result['stderr'][:2000])
        write(self.out/'accepted-interface-paths.json',{'contract':str(directory/'contract.json'),
            'plan':str(directory/'plan.json'),'author_output':str(self.out/'stage/accepted.json'),
            'paragraph_mapping':self.source['paragraph_mapping'],'source_outputs':value['source_outputs'],
            'status':'IR_TYPES_CHECKED_SEMANTIC_REVIEW_REQUIRED'})
        return {'status':'IR-TYPES-CHECKED','candidate':self.attempt,'mathematical_acceptance':False,
                'decomposition':decomposition,
                'scope':'Actual full source correspondence/interface review and all proofs remain required.'}


class InterfaceStage(ArtifactStage):
    """A scratch expression compiler, with the same filesystem/network sandbox."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.type_probes=0
        self.input_prompt+=('\nYou may revise an explicit frozen prior-interface.json through '
            '{"base_input":"prior-interface.json","patches":[{"op":"replace","path":"/header","value":"complete replacement header"}]}. '
            'The result is fully expanded and checked; this never supplies missing mathematics. After a full '
            'candidate exists, preserve it with base_candidate:N and explicit patches, or submit '
            '{"accept_candidate":N} only when that actual candidate is complete and faithful. '
            'read_interface_draft kind=index lists your own actual full candidates and partial type probes; '
            'kind=candidate reads a JSON pointer of a full candidate, kind=probe reads its own actual partial '
            'header/types. After context reset, inspect this index rather than starting from a vacuous True '
            'template. A placeholder is not a translation. Choose useful closed obligations; a large worker limit cannot accelerate a monolithic job. '
            'Optional shared_obligations must use the existing v2 schema and describe only existing NL0 lemmas or implementation extraction, with explicit inputs and route. They remain pending actual semantic review; new mathematics returns to NL0.')
        self.tools.append(pilot.carrier.tool('read_interface_draft','Read only own current-stage typed candidates or partial type probes; index lists them. No other stage files are accessible.',
            {'kind':{'type':'string','enum':['index','candidate','probe']},'candidate':{'type':'integer'},'pointer':{'type':'string'}},['kind','candidate','pointer']))
        self.tools.append(pilot.carrier.tool('check_lean_types',
            'Compile a partial mathematical definition header and selected Lean type or ordinary API term expressions with explicit parameters. Never accepts a final interface or adds a proved premise.',
            {'header':{'type':'string'},'parameters':{'type':'array','items':{'type':'object'}},
             'types':{'type':'array','items':{'type':'string'}}},['header','parameters','types']))
        self.tool_names={t['name'] for t in self.tools}

    def dispatch(self,name,args):
        if name=='read_interface_draft':
            try:
                if args['kind']=='index':result={'candidates':sorted(self.validator.drafts),'type_probes':list(range(1,self.type_probes+1))}
                else:
                    number=args['candidate'];ir.need(type(number) is int and number>0,'Use a positive own-stage draft number')
                    if args['kind']=='candidate':row=self.validator.drafts[number]
                    elif args['kind']=='probe':row=ir.load(self.logs/'type-probes'/f'{number:04d}'/'input.json')
                    else:raise ValueError('Unknown own-stage draft kind')
                    value=nl0.closure.resolve(row,args['pointer']);ir.need(len(json.dumps(value,ensure_ascii=False))<=20000,'Choose a narrower JSON pointer')
                    result={'value':value,'scope':'Own actual current-stage draft only; not semantic acceptance'}
            except (ValueError,KeyError,TypeError,OSError) as error:result={'error':str(error),'accepted':False}
            pilot.carrier.append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,'wall_seconds':0});return result
        if name!='check_lean_types':return super().dispatch(name,args)
        start=time.monotonic()
        try:
            if self.accepted is not None:raise ValueError('Stage is already complete')
            header=args['header'];parameters=args['parameters'];types=args['types']
            if not isinstance(header,str) or not header.startswith('import Mathlib\n'):raise ValueError('Start the header with import Mathlib and newline')
            if re.search(r'\b(sorry|admit|axiom|opaque|unsafe|run_meta|run_elab|run_tac|native_decide|initialize|elab|macro|syntax|theorem|lemma|set_option)\b|(^|\n)\s*#',header):
                raise ValueError('Type probes allow mathematical definitions, not proof/result declarations or executable commands')
            if not isinstance(parameters,list) or not isinstance(types,list) or not types:raise ValueError('Supply parameters and at least one type')
            names=[]
            for p in parameters:
                if not set(p)<={'name','type','binder_kind'} or not {'name','type'}<=set(p) or not ir.IDENTIFIER.fullmatch(p['name']):raise ValueError('Use a valid typed parameter')
                ir.type_text(p['type']);names.append(p['name'])
            if len(set(names))!=len(names):raise ValueError('Duplicate parameter name')
            binders=' '.join(ir.parameter_text(p) for p in parameters)
            source=header+'\nset_option autoImplicit false\n'
            for expression in types:
                ir.type_text(expression)
                source+='#check ('+('fun '+binders+' => ' if binders else '')+expression+')\n'
            self.type_probes+=1;work=Path(tempfile.mkdtemp(prefix='yui-interface-types-'))
            (work/'input').mkdir();(work/'output').mkdir();file=work/'output/Types.lean';file.write_text(source)
            from run_resources import register_workspace
            register_workspace(work, self.logs)
            try:
                native=ir.run_lean(file,work,timeout=self.lean_timeout());self.lean_calls+=1
                destination=self.logs/'type-probes'/str(self.type_probes).zfill(4);destination.mkdir(parents=True)
                write(destination/'input.json',args)
                shutil.copyfile(file,destination/'Types.lean');write(destination/'compiler.json',native)
            finally:
                shutil.rmtree(work)
            result={'stage_complete':False,'scope':'EXPRESSION_ELABORATION_ONLY_NO_PROOF_OR_INTERFACE_ACCEPTANCE',
                'types_checked':native['exit_code']==0,'exit_code':native['exit_code'],
                'stdout':native['stdout'][:16000],'stderr':native['stderr'][:1500]}
        except (ValueError,KeyError,TypeError) as error:result={'stage_complete':False,'types_checked':False,'error':str(error)}
        pilot.carrier.append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,'wall_seconds':time.monotonic()-start})
        return result


def run(out,timeout,budget=None):
    out=Path(out).resolve();validator=InterfaceContract(out)
    stage=InterfaceStage(out/'stage',(out/'prompt.txt').read_text(),phase='interface-authoring',
        inputs=out/'inputs/inputs.json',timeout=timeout,validator=validator,
        budget=concurrency.serial_budget(budget))
    return stage.execute()[0]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare');p.add_argument('--case',required=True);p.add_argument('--problem',required=True);p.add_argument('--out',required=True)
    p=commands.add_parser('run');p.add_argument('--out',required=True);p.add_argument('--timeout-seconds',type=int,default=1800)
    args=parser.parse_args()
    result=prepare(args.case,args.problem,args.out) if args.command=='prepare' else run(args.out,args.timeout_seconds)
    print(json.dumps(result,indent=2))
