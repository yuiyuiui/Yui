#!/usr/bin/env python3
"""Clean typed-interface authoring adapter for explicit accepted NL0 sources.

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

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'nl0/scripts'))
from controller_common import CORE,write,bind,manifest
sys.path.insert(0,str(CORE/'nl0/scripts'))
sys.path.insert(0,str(CORE/'nl02lean/scripts'))
import ir
import nl0
import source_preparation
import background
import background_inputs
import correspondence
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


PROMPT='''Translate the accepted NL0 into a small, usable Lean interface and local
proof plan. Start with source-map.json and the problem/specification; read
individual NL0 definitions or paragraphs when needed. Yui translation rules
are available on demand. Do not read every rule or background note at startup.
The controller retains all accepted paragraphs and attaches each step's own
Audit A note index. Notes are optional implementation references, not new
premise ports: do not give every note a Lean type or add it to premise_types.
Keep the original H/E project inputs and every N/P output. The pinned Mathlib
environment is freely available without registration. Prefer direct library use
to M premise ports; omit M roots unless an intermediate port is useful. Choose a
coherent Lean representation preserving domains, assumptions, quantifiers and
the full target. Definitions cannot hide unproved results or stronger assumptions.
Use typed steps for mathematical obligations; no proof bodies are required yet.

Submit an object with header, parameters, premise_types, conclusion_type,
representation, objects, steps, terminal, source_outputs, endpoint_correspondence.
endpoint_correspondence maps exactly every E ID and P to
{mode:direct|equivalent, explanation:<concise mathematical account>}. Explain
why each external statement and the WHOLE target (parameters, quantifiers,
hypotheses, conclusion) has the original meaning. Direct translations need only
a short account. For equivalent encodings, state the identification and why it
works in both directions under the actual assumptions. Do not invent a second
Lean representation just to prove an unnecessary conversion. If the proof
actually crosses two Lean representations, plan a checked conversion. These
notes are author guidance for independent Audit B, not approval. header starts with
"import Mathlib\n" and contains only object definitions/notation/structures,
no axioms, proof declarations, placeholders or executable metaprogramming.
parameters: [{name,type,binder_kind?}], where binder_kind is explicit (default),
implicit or instance. premise_types maps every H/E root and any retained M
port to its Lean proposition. Mathlib references are not a permission list. source_outputs maps every N/P to a distinct step Tddd. steps:
[{id,statement,inputs:[root/T IDs],source_steps:[S IDs],explanation}]. Each step
is a closed conditional obligation; include useful independent subarguments or
representation bridges when they reduce work. Every step must reach terminal;
cover all source paragraphs. terminal's type equals conclusion_type. objects
may be [] when special representation views are unnecessary. representation
explains the chosen encoding; it is not a semantic approval.

Save incomplete work with save_interface_draft; revise it with base_candidate
and explicit JSON-pointer patches. Use check_lean_types for uncertain APIs or
small type fragments, and check_draft when the full interface is ready. A full
check runs real Lean type elaboration and source-boundary checks. Continue from
your saved candidate after errors. Do not stop just to report ordinary progress.
At acceptance, proof workers start; final Audit B independently checks semantic
faithfulness and the assembled proof. A type check is never a semantic PASS.
'''


def prepare(case,problem,out,*,authority=None,prior_interface=None,diagnostics=None):
    case,problem,out=[Path(p).resolve() for p in (case,problem,out)]
    authority=authority or {'graph':str(case/'nl0.json'),'spec':str(case/'spec.json'),'audit_a':str(case/'audit-a.json')}
    data,source_files=source_preparation.read_source(**authority)
    from source_qualification import usable
    if not usable(data[0]):raise ValueError('Accepted current Audit A is required before interface authoring')
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(__file__,out/'controller.py.snapshot.txt')
    inputs=out/'inputs';inputs.mkdir()
    props,inferences=background_inputs.effective(data)
    supplement=data[0].get('background_supplement')
    if supplement:write(inputs/'background-supplement.json',supplement)
    for f in ['spec.json','nl0.json']:shutil.copyfile(case/f,inputs/f)
    from controller_common import copy_problem_documents
    copy_problem_documents(problem,inputs)
    paragraphs=[];mapping={}
    for rid,r in inferences.items():
        for s in r['argument']:
            identifier='S'+str(len(paragraphs)+1).zfill(3)
            paragraphs.append({'id':identifier,'text':s['text']})
            mapping[identifier]={'inference':rid,'paragraph':s['id']}
    source_map={'background_mode':background_inputs.REFERENCE_ONLY,'source_steps':paragraphs,'paragraph_mapping':mapping,
        'roots':[{'id':p['id'],'kind':p['kind'],'statement':p['statement'],**({'source':p['source']} if 'source' in p else {})} for p in props.values() if p['kind'] in {'hypothesis','external','mathlib'}],
        'source_outputs':{r['output']:data[3][r['output']]['statement'] for r in data[4].values()},
        'direct_boundaries':{rid:{'inputs':r['inputs'],'output':r['output'],
            'background_notes':[rid+'.'+n['id'] for n in data[0].get('background_notes',{}).get(rid,[])]}
            for rid,r in inferences.items()}}
    write(inputs/'source-map.json',source_map)
    prompt=PROMPT
    if prior_interface:
        shutil.copyfile(prior_interface,inputs/'prior-interface.json')
        write(inputs/'repair-diagnostics.json',diagnostics)
        prompt+='\nThis is a disclosed repair after actual Audit B. Read prior-interface.json and repair-diagnostics.json; patch the responsible encoding while preserving the accepted source. Never resubmit the unchanged rejected interface or strengthen its assumptions.'
    manifest(inputs);(out/'prompt.txt').write_text(prompt)
    write(out/'authority.json',{'case':str(case),'graph':bind(case/'nl0.json'),'spec':bind(case/'spec.json'),
        'source_authority':authority,'source_bindings':[bind(p) for p in source_files]})
    inventory=source_preparation.inventory(**authority)
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
        authority=json.loads((self.out/'authority.json').read_text());case=Path(authority['case'])
        self.source_data=source_preparation.read_source(**authority.get('source_authority',{
            'graph':str(case/'nl0.json'),'spec':str(case/'spec.json'),'audit_a':str(case/'audit-a.json')}))[0]
        from source_qualification import usable
        if not usable(self.source_data[0]):
            raise ValueError('Interface authoring requires current accepted Audit A')
        self.source_bindings=authority.get('source_bindings') or [authority[k] for k in ('graph','spec','audit_a')]

    def save(self, value):
        expanded, edits = expand_interface(value, self.documents, self.drafts)
        if not isinstance(expanded, dict):
            raise ValueError('An interface draft must be a JSON object')
        self.attempt += 1
        directory = self.out/'candidates'/f'{self.attempt:04d}'
        directory.mkdir(parents=True)
        self.drafts[self.attempt] = deepcopy(expanded)
        write(directory/'artifact.json', expanded)
        if edits is not None:
            write(directory/'explicit-edits.json', edits)
        return expanded, directory

    def __call__(self,value):
        expanded,directory = self.save(value)
        value.clear();value.update(expanded)
        try:
            return self.check(value,directory)
        except (ValueError,KeyError,TypeError) as error:
            raise ValueError(f'Candidate {self.attempt} saved; repair it with base_candidate. {error}') from error

    def check(self,value,directory):
        expected={'header','parameters','premise_types','conclusion_type','representation','objects','steps','terminal','source_outputs','endpoint_correspondence'}
        if not expected<=set(value) or not set(value)<=expected|{'shared_obligations'}:raise ValueError('Expected '+', '.join(sorted(expected))+'; optional shared_obligations')
        header=value['header']
        if not isinstance(header,str) or not header.startswith('import Mathlib\n'):
            raise ValueError('Header must start with import Mathlib followed by a newline')
        if re.search(r'\b(sorry|admit|axiom|opaque|unsafe|run_meta|run_elab|run_tac|native_decide|initialize|elab|macro|syntax|theorem|lemma|set_option)\b|(^|\n)\s*#',header):
            raise ValueError('Candidate header may define mathematical objects, not proof/result declarations or executable commands')
        required={p['id'] for p in self.source['roots'] if p['kind']!='mathlib'}
        available={p['id'] for p in self.source['roots']}
        if not required <= set(value['premise_types']) <= available:
            raise ValueError('Provide all original H/E roots; original M ports are optional')
        correspondence.validate_notes(value['endpoint_correspondence'],
            [p['id'] for p in self.source['roots'] if p['kind']=='external']+['P'])
        if set(value['source_outputs'])!=set(self.source['source_outputs']):
            raise ValueError('Map exactly every source N/P to its primary typed T')
        shutil.copyfile(self.out/'inputs/nl0.json',directory/'nl0.json')
        contract={'version':2,'id':self.spec['case_id'].replace('-','_'),
            'source':{'path':'nl0.json','sha256':ir.digest(directory/'nl0.json'),
                      'background_mode':background_inputs.REFERENCE_ONLY},
            'source_steps':self.source['source_steps'],'pins':self.spec['pins'],
            'header':header,'parameters':value['parameters'],
            'premises':[{**p,'type':value['premise_types'][p['id']]} for p in self.source['roots'] if p['id'] in value['premise_types']],
            'endpoint_correspondence':value['endpoint_correspondence'],
            'conclusion':{'statement':self.graph['propositions'][next(i for i,p in enumerate(self.graph['propositions']) if p['id']=='P')]['statement'],'type':value['conclusion_type']},
            'representation':value['representation'],'objects':value['objects'],'shared_obligations':value.get('shared_obligations',[]),
            'review':{'mode':'deferred_semantic_review','status':'PENDING_AUDIT_B','disclosure':'Candidate generated in a clean selected-model context; only syntax/types and source boundaries are checked by this adapter.'}}
        supplement_file=self.out/'inputs/background-supplement.json'
        if supplement_file.is_file():
            supplement=json.loads(supplement_file.read_text())
            contract['source'].update(background_supplement=supplement,
                background_supplement_sha256=supplement['sha256'])
        write(directory/'contract.json',contract)
        plan={'version':2,'contract_sha256':ir.digest(directory/'contract.json'),
              'representation_notes':value['representation'],'steps':background_inputs.attach_notes(value['steps'],self.source,
                  json.loads(supplement_file.read_text()) if supplement_file.is_file() else None),
              'terminal':value['terminal']}
        write(directory/'plan.json',plan)
        ir.validate(directory/'contract.json',plan)
        from execution_state import current
        import workflow
        for bound in self.source_bindings:
            if ir.digest(bound['path'])!=bound['sha256']:raise ValueError('Source changed during interface authoring')
        workflow.check_source_boundary(self.source_data,contract,plan,
            self.source['paragraph_mapping'],value['source_outputs'])
        decomposition=ir.decomposition(directory/'contract.json',plan)
        write(directory/'decomposition.json',decomposition)
        result=ir.check(directory/'contract.json',plan,types_only=True,out=directory/'types',timeout=current()[0].remaining() if current()[0] else None)
        if result['exit_code']!=0:
            raise ValueError('Actual Lean type check failed:\n'+result['stdout'][:14000]+result['stderr'][:2000])
        write(self.out/'accepted-interface-paths.json',{'contract':str(directory/'contract.json'),
            'plan':str(directory/'plan.json'),'author_output':str(self.out/'stage/accepted.json'),
            'paragraph_mapping':self.source['paragraph_mapping'],'source_outputs':value['source_outputs'],
            'source_graph_sha256':contract['source']['sha256'],
            'contract_sha256':ir.digest(directory/'contract.json'),'plan_sha256':ir.digest(directory/'plan.json'),
            'status':'IR_TYPES_CHECKED_SEMANTIC_REVIEW_PENDING_AUDIT_B'})
        return {'status':'IR-TYPES-CHECKED','candidate':self.attempt,'mathematical_acceptance':False,
                'decomposition':decomposition,
                'scope':'Source-boundary and types checked; semantic correspondence and all proofs remain subject to final Audit B.'}


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
        self.tools.append(pilot.carrier.tool('save_interface_draft','Save incomplete own-stage interface JSON without accepting it or invoking Lean. Later revise via base_candidate.',
            {'artifact':{'type':'object','additionalProperties':True}},['artifact']))
        self.tools.append(pilot.carrier.tool('read_interface_draft','Read only own current-stage typed candidates or partial type probes; index lists them. No other stage files are accessible.',
            {'kind':{'type':'string','enum':['index','candidate','probe']},'candidate':{'type':'integer'},'pointer':{'type':'string'}},['kind','candidate','pointer']))
        self.tools.append(pilot.carrier.tool('check_lean_types',
            'Compile a partial mathematical definition header and selected Lean type or ordinary API term expressions with explicit parameters. Never accepts a final interface or adds a proved premise.',
            {'header':{'type':'string'},'parameters':{'type':'array','items':{'type':'object'}},
             'types':{'type':'array','items':{'type':'string'}}},['header','parameters','types']))
        self.tool_names={t['name'] for t in self.tools}

    def dispatch(self,name,args):
        if name=='save_interface_draft':
            try:
                if self.accepted is not None:raise ValueError('Stage is already complete')
                self.validator.save(args['artifact'])
                result={'candidate':self.validator.attempt,'saved':True,'stage_complete':False,'semantic_acceptance':False}
            except (ValueError,KeyError,TypeError,OSError) as error:result={'error':str(error),'accepted':False}
            pilot.carrier.append(self.logs/'tools.jsonl',{'tool':name,'arguments':args,'result':result,'wall_seconds':0})
            return result
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


def run(out,timeout=None,budget=None):
    out=Path(out).resolve();validator=InterfaceContract(out)
    stage=InterfaceStage(out/'stage',(out/'prompt.txt').read_text(),phase='interface-authoring',
        inputs=out/'inputs/inputs.json',timeout=timeout,validator=validator,
        budget=concurrency.serial_budget(budget))
    return stage.execute()[0]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare');p.add_argument('--case',required=True);p.add_argument('--problem',required=True);p.add_argument('--out',required=True)
    p=commands.add_parser('run');p.add_argument('--out',required=True);p.add_argument('--timeout-seconds',type=int,default=None)
    args=parser.parse_args()
    result=prepare(args.case,args.problem,args.out) if args.command=='prepare' else run(args.out,args.timeout_seconds)
    print(json.dumps(result,indent=2))
