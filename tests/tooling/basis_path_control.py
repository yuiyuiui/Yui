"""Genuine frozen case, local native clients and Lean. Only model replies and operator choices are scripted."""
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import json
import hashlib
import time
import subprocess
import sys
from unittest.mock import patch

job = json.loads(Path(sys.argv[1]).read_text())
run = Path(job['root'])
options=sys.argv[2].split('+');mode=options[0]
read_strategies='reference' in options[1:]
imported_code='imported-lean' in options[1:]
ported_code='port' in options[1:]
graph_continuation='graph-continuation' in options[1:]
stop_before_revision='stop-before-revision' in options[1:]
tests = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(tests), str(run/'runtime/nl0/scripts'), str(run/'runtime/nl02lean/scripts'),
                str(tests.parent/'nl0/scripts'),str(tests.parent/'nl02lean/scripts')]
import harness_support
from native_fixture import NativeFixture
from basis_fixtures import active_artifact, artifact, dependency, reviewed_value, add_external_applications
from final_acceptance_fixtures import addition_interface
from review_contract import put
import audit_a_campaign
import case_runner
import fault_control
import ir
import execution_state
import queue_controller
import model_pilot

NOTE = 'Synthetic controller test on equality and addition of natural numbers.'
requests = Counter()


def call(name, **arguments):
    return 'text(await tools.'+name+'('+json.dumps(arguments)+'));'


def author_code(stage):
    folder = tests/'fixtures/closed-addition'
    spec=ir.load(folder/'spec.json');graph=ir.load(folder/'nl0.json')
    spec['case_id']=graph['case_id']=job['case']
    spec['hypotheses'][0]['origin']='problem.md:1'
    reference='material-001.lean' if graph_continuation else 'problem.md'
    evidence=[r for r in stage.validator.expected_inputs if r['path']=='inputs/'+reference]
    import frozen_graph as fg
    if 'basis-registry.json' in stage.task_inputs:
        registry=json.loads(stage.task_inputs['basis-registry.json'])
        if mode.startswith('relabel-'):
            spec.pop('case_id')
            evidence=[{'input':'problem.md'}]
            if stage.mode==fg.LOCAL:
                current=json.loads(stage.task_inputs[fg.ASSIGNED])['graph']
                registry['dependencies'][0]['port']=current['foundation_ports']['labels']['B001']
        if mode=='planned-unused-residual':
            if stage.mode==fg.LOCAL:
                assigned=json.loads(stage.task_inputs[fg.ASSIGNED])['graph']
                if any(p['id']=='E003' for p in assigned['propositions']):
                    return call('report_graph_issue',findings=[{'inference':'R002','kind':'wrong_input','subject':'E003',
                                'explanation':'The checked E002 suffices at this use. Drop the redundant assumption E003.'}])
            if stage.mode==fg.LOCAL or 'prior-global.json' in stage.task_inputs:
                registry['dependencies']=[r for r in registry['dependencies'] if r['port']!='E003']
        add_external_applications(graph,registry,evidence)
        if mode=='native-source':
            row=registry['dependencies'][0]
            graph['propositions'].append({'id':'M001','kind':'mathlib','statement':row['statement'],
                'definitions':[],'binders':[],'objects':[]})
            step=graph['inferences'][-1];step['inputs'].append('M001')
            step['argument'][-1]['uses'].append('M001')
            step['applications'].append({'id':'A001','input':'M001','at':step['argument'][-1]['id'],
                'bindings':'Specialize the displayed division identity at a, 1 and 1.','hypothesis_checks':[]})
    if mode=='direct-external':
        add_external_applications(graph,artifact(dependency(category=2)),evidence)
    if mode=='serial-graph' and stage.mode in (fg.DIRECT,fg.LOCAL):
        assigned=json.loads(stage.task_inputs.get('prior-global.json',stage.task_inputs.get(fg.ASSIGNED,'{}')))
        earlier={r['id']:r for r in assigned.get('graph',{}).get('inferences',[])}
        if stage.mode==fg.LOCAL and 'R003' not in earlier:
            report={'inference':'R002','kind':'wrong_input','subject':'N001',
                    'explanation':'The consumer still lacks the needed derivation of the additive step.',
                    'source_spans':[{'from_task':'problem.md','start_line':1,'end_line':1}]}
            first=graph['inferences'][0]
            body={} if 'H001' in earlier['R002']['inputs'] else {
                'local_proofs':[{k:first[k] for k in ('id',*fg.BODY_FIELDS)}]}
            invalid={**report,'source_spans':[{'from_task':'problem.md','start_line':1,'end_line':2}]}
            return call('report_graph_issue',findings=[invalid])+call('report_graph_issue',findings=[report],**body)
        if earlier:
            last=graph['inferences'][-1]
            last['inputs'].append('H001')
            last['argument'][-1]['uses'].append('H001')
            if 'H001' in earlier['R002']['inputs']:
                split=harness_support.addition_split(graph)
                graph['propositions']+=split['propositions']
                graph['inferences'][1:]=split['inferences']
    if mode=='local-gap' and stage.mode==fg.LOCAL:
        return call('report_obstacle',status='SUBSTANTIVE_GAP',location='R002 last implication',
            basis='The supplied statements do not imply the requested implication.',
            explanation='The obligations conflict at the last inference even after consulting all available roots.',
            partial_progress='The earlier symmetry node can still be retained.')
    if graph_continuation or mode in {'local-edge','first-pass-edge','relabel-closed','relabel-residual'}:
        if stage.mode==fg.LOCAL:
            current=json.loads(stage.task_inputs[fg.ASSIGNED])['graph']
            if 'H001' not in next(r for r in current['inferences'] if r['id']=='R002')['inputs']:
                report={'inference':'R002','kind':'missing_input','subject':'H001',
                        'explanation':'The chosen last equality uses the original equality directly as well as its symmetric form.'}
                first=next(r for r in graph['inferences'] if r['id']=='R001')
                if graph_continuation:
                    report['source_spans']=[{'from_task':'problem.md','start_line':1,'end_line':1}]
                    return call('report_graph_issue',findings=[report],
                                local_proofs=[{k:first[k] for k in ('id',*fg.BODY_FIELDS)}])
                return (call('report_graph_issue',findings=[{**report,'inference':'R999'}])+
                        call('report_graph_issue',findings=[{**report,'subject':'H999'}])+
                        call('report_graph_issue',findings=[report],
                             local_proofs=[{k:first[k] for k in ('id',*fg.BODY_FIELDS)}]))
        graph['inferences'][-1]['inputs'].append('H001')
        last=graph['inferences'][-1]['argument'][-1]
        last['uses'].append('H001')
        last['text']+=' Compose the original equality, its symmetric equality and the original equality to obtain the last equality.'
    if stage.mode==fg.BASIS and 'prior-global.json' in stage.task_inputs:
        first=''
        if mode=='stalled-graph':
            previous=json.loads(stage.task_inputs['prior-global.json'])
            outline=harness_support.elementary_outline(previous['graph']['inferences'])
            first=call('submit_draft',artifact={'spec':spec,**fg.shape(previous['graph']),'proof_outline':outline})
        if mode=='local-edge':
            # The graph protocol accepts omitted H/P aliases copied from their original specification.
            for prop in graph['propositions']:
                if prop['kind'] in ('target','hypothesis'):
                    del prop['statement']
        renames={'rename_foundations':{'B001':'E014'}} if mode.startswith('relabel-') else {}
        outline = harness_support.elementary_outline(graph['inferences'])
        if renames:
            ports = {label: key for key, label in stage.validator.labels.items()}
            for entry in outline.values():
                step = entry['steps'][0]
                step['uses'] = [ports.get(pid,pid) for pid in step['uses']]
        return first+call('submit_draft',artifact={'spec':spec,**fg.shape(graph),**renames,
                    'proof_outline':outline})
    if stage.mode==fg.BASIS:
        seed = stage.validator.seed['inferences']
        outline = harness_support.elementary_outline(seed)
        for row in seed:
            # Address roots by B identity so the same outline works after relabeling.
            uses = outline[row['id']]['steps'][0]['uses']
            uses[:] = [p for p in uses if p not in stage.validator.labels.values()] + row['basis']
        return call('submit_draft',artifact={'spec':spec,
            'proposition_details':{p['id']:{k:v for k,v in p.items() if k not in ('id','statement')} for p in graph['propositions']},
            'inference_definitions':{r['id']:r['definitions'] for r in graph['inferences']},
            'proof_outline':outline})
    if stage.mode==fg.DIRECT:
        outline = harness_support.elementary_outline(graph['inferences'])
        if mode=='direct-refinement':
            outline['R002']['steps'] = [
                {'conclusion':'a+0=a.', 'uses':[], 'source_spans':[]},
                {'conclusion':'a+0=b.', 'uses':['S001','N001'], 'source_spans':[]},
            ]
        return call('submit_draft',artifact={'spec':spec,**fg.shape(graph),
                    'proof_outline':outline})
    draft=({'local_proofs':[{k:r[k] for k in ('id',*fg.BODY_FIELDS)} for r in graph['inferences']]}
           if stage.mode==fg.LOCAL else {'spec':spec,'graph':graph})
    if (mode=='local-edge' or graph_continuation) and stage.mode==fg.LOCAL:
        feedback=json.loads(stage.task_inputs['global-findings.json'])
        if not feedback['blockers'] or [r['id'] for r in feedback['local_proofs']]!=['R001']:
            raise AssertionError('The revised local assignment needs the blocker and the unaffected earlier draft')
        draft['local_proofs']=[row for row in draft['local_proofs'] if row['id']!='R001']
    if mode=='serial-graph' and stage.mode==fg.LOCAL:
        draft['local_proofs']=[row for row in draft['local_proofs'] if row['id']!='R001']
    candidate=1
    if mode=='direct-refinement' and stage.mode==fg.LOCAL:
        code=call('check_draft',artifact={'local_proofs':draft['local_proofs'][:1]})
        code+=call('check_draft',artifact={'local_proofs':draft['local_proofs'][1:]})
        code+=call('submit_draft',artifact={'accept_candidate':1})
        split=harness_support.addition_split(graph)
        code+=call('check_draft',artifact={'refine_candidate':2,'splits':[split]})
        graph['propositions']+=split['propositions']
        graph['inferences'][1:]=split['inferences']
        candidate=3
    else:
        code=call('check_draft',artifact=draft)
    for row in graph['inferences']:
        code+=call('read_author_packet',candidate=candidate,inference=row['id'])
    repaired=json.loads(stage.task_inputs.get('repair-obligations.json','{"issues":[]}'))
    resolutions=[{'id':i['id'],'location':i['location'],'note':'The revised N001 is the symmetric equality.'} for i in repaired['issues']]
    code+=call('record_author_checks',candidate=candidate,readiness='no_known_issue',open_issues=[],resolutions=resolutions,
        original_context_note=NOTE,output_notes=[{'id':row['id'],'note':NOTE} for row in graph['propositions']
                                                if row['kind'] in {'internal','target'}],
        inference_notes=[{'id':row['id'],'dependency_and_local_assumption_check':NOTE,
            'source_application_check':NOTE,'declaration_check':NOTE} for row in graph['inferences']])
    return code+call('submit_draft',artifact={'accept_candidate':candidate})


def review_value(stage):
    contract=stage.validator;value=deepcopy(contract.base)
    for pointer in contract.required:
        row={'verdict':'PASS','notes':NOTE}
        if stage.mode.startswith('interface-'):
            row['locations']=[{'document':'spec.json','pointer':'/full_target'},
                              {'document':'contract.json','pointer':'/conclusion/type'}]
            if pointer=='/checks/statements_and_local_plans' and 'local-tasks.json' in stage.task_inputs:
                row['locations'] += [{'document':'local-tasks.json','pointer':'/'+sid}
                    for sid in json.loads(stage.task_inputs['local-tasks.json'])]
        elif stage.mode=='audit-a-global':
            row['locations']=['spec.json#/full_target' if pointer=='/target_review' else 'nl0.json#/inferences']
            if pointer=='/structure_review' and mode in {'global-revision','stalled-graph'}:
                props=json.loads(stage.task_inputs['nl0.json'])['propositions']
                bad=next((i for i,p in enumerate(props) if p['statement']=='Both numbers vanish.'),None)
                if bad is not None:row.update(verdict='FAIL',notes='Equality does not imply both numbers vanish.',locations=[f'nl0.json#/propositions/{bad}/statement'])
            if pointer.startswith('/source_reviews/E'):
                row['citation_checks']={k:deepcopy(row) for k in audit_a_campaign.nl0.EXTERNAL_CHECKS}
        else:
            row['locations']=['/inference/argument']
            if pointer.startswith('/external_applications/'):
                apps=json.loads(stage.task_inputs['packet.json'])['inference']['applications']
                app=next(r for r in apps if r['id']==pointer.split('/')[-1])
                row.update(input=app['input'],bindings_review=deepcopy(row),hypothesis_reviews=[],
                           conclusion_review=deepcopy(row),bridges=[])
        put(value,pointer,row)
    if stage.mode=='audit-a-packet-replay':value.update(verdict='PASS',notes=NOTE)
    value['findings']=[];value['coverage']={p:'assessed' for p in contract.required}
    return value


def scripted(stage):
    if stage.mode=='basis-authoring':
        revision=stage.logs.parent.name
        if mode=='dependency-repair':
            spec=ir.load(run.parent/'dependency-fixture.json')
            def source_call(module):
                pin={'repository':spec['remote'],'revision':spec['revision'],
                     'source_path':module.replace('.','/')+'.lean','module':module}
                return call('read_external_source',git=pin)
            value=active_artifact(artifact(dependency(category=2)))
            turn=requests[stage.logs]
            if turn==1:
                route=deepcopy(value)
                for row in route['dependencies']:row['lean']['proof']=None
                return (call('save_basis_draft',artifact=route)
                        +call('prepare_basis_graph',candidate=stage.validator.attempt+1,prove=False)
                        +call('check_imported_lean',source={'document':'material-001.lean'},publish=True)
                        +source_call('Budget.Blocked')+source_call('Dep.Base'))
            if turn==5:
                return call('submit_draft',artifact=value)
            calls=[json.loads(line) for line in (stage.logs/'tools.jsonl').read_text().splitlines()]
            if turn==2:
                sources={row['arguments']['git']['module']:row['result']['primary_evidence_candidates'][0]
                         for row in calls if row['tool']=='read_external_source'}
                return ''.join(call('check_imported_lean',source={'evidence':sources[module]},bind_public=True)
                               for module in ('Budget.Blocked','Dep.Base','Budget.Blocked'))
            failed=next((row['result']['public_library'] for row in reversed(calls)
                         if row['result'].get('public_library',{}).get('failure_origin')),None)
            assert failed is not None, [(row['tool'], row['result'].get('status'), row['result'].get('error'),
                                         row['result'].get('diagnostics')) for row in calls]
            assert failed['failed_module']=='Budget.Blocked',failed
            edit={'source':{'failure':failed['receipt']},'bind_public':True}
            if turn==4:
                return call('check_imported_lean',**edit,candidate='import Dep.Base\nexample : True := True.intro')
            repeated='import Dep.Base\nexample : True := by exact missingCandidate'
            return ''.join(call('check_imported_lean',**edit,candidate=code)
                        for code in [repeated,repeated,repeated+'Two',repeated+'Three',repeated+'Four'])
        wants_residual=mode in {'stop','accept-conditional','continue','deadline-decision','relabel-residual'} and revision=='0001'
        cat=4 if wants_residual else 2
        row=dependency(category=cat)
        if mode=='native-source':
            row=dependency(category=1,compatibility='native',
                typ='∀ a b c : ℕ, a / b / c = a / c / b',
                proof='intro a b c; exact Nat.div_right_comm a b c')
            row['port']=None;row['origin']['declaration']='Nat.div_right_comm'
            row['statement']='For all natural numbers a, b and c, a / b / c = a / c / b.'
        if mode=='universe-use':
            row['statement']='In an additive structure with zero, adding zero on the right preserves each element.'
            row['lean']={'type':'∀ (A : Type*) [AddZeroClass A] (x : A), x + 0 = x',
                         'proof':'intro A _ x; exact add_zero x'}
        if mode in {'mismatch','first-pass','late','late-proof'} and revision=='0001':
            row['statement']='There exists one natural number n such that every natural number equals n.'
        if mode=='evidence-repair' and requests[stage.logs]==1:
            row['origin']['evidence']=[{'path':'external-sources/misspelled.pdf','sha256':'0'*64}]
        if mode.startswith('planned-'):
            base=dependency(category=2)
            if not graph_continuation:base['port']=None
            prefix=''
            if graph_continuation:
                module='FixtureLib.Leaf'
                base['lean']['proof']='intro n; exact (fun _ : True => Nat.add_zero n) FixtureLib.witness'
                base['origin'].update(reference='material-001.lean: FixtureLib.witness',
                                      evidence=[{'input':'material-001.lean'}])
            if imported_code:
                source=stage.task_inputs['material-001.lean']
                module='YuiImported'+hashlib.sha256(source.encode()).hexdigest()[:24]
                base['lean']['proof']='exact ImportedExample.add_zero'
                base['origin'].update(reference='material-001.lean: ImportedExample.add_zero',
                                      evidence=[{'input':'material-001.lean'}])
                prefix=call('check_imported_lean',source={'document':'material-001.lean'},publish=True)
            if ported_code:
                module='Lib.Consumer'
                base['lean']['proof']='exact Lib.consumer'
            derived=dependency('B002',3)
            rows=[base] if graph_continuation else [base,derived]
            if mode!='planned-closed' and (mode!='planned-continue' or requests[stage.logs]==1):
                rows.append(dependency('B003',4,port='E003'))
            value=active_artifact(artifact(*rows))
            if graph_continuation or imported_code or ported_code:value['lean_header']='import Mathlib\nimport '+module+'\n'
            if not ported_code and not graph_continuation:value['dependencies'][1]['lean']['proof']=None
            frontier=''
            if mode=='planned-closed' and not ported_code and not graph_continuation:
                frontier=call('investigate_basis_frontier',obligations=[
                    {'id':r['id'],'statement':r['statement'],'consumers':[{'id':'R002','required_use':NOTE}]}
                    for r in value['dependencies']])
            route=deepcopy(value)
            for row in route['dependencies']:
                if row['category']!=4:row['lean']['proof']=None
            return prefix+frontier+call('save_basis_draft',artifact=route)+call('prepare_basis_graph',candidate=stage.validator.attempt+1,prove=False)+call('submit_draft',artifact=value)
        value=active_artifact(artifact(row))
        if mode=='stalled-graph' or (mode=='global-revision' and revision=='0001'):
            next(p for p in value['global_graph']['propositions'] if p['id']=='N001')['statement']='Both numbers vanish.'
        route=deepcopy(value)
        for row in route['dependencies']:
            if row['category']!=4:row['lean']['proof']=None
        if mode=='evidence-repair' and requests[stage.logs]==1:
            return call('save_basis_draft',artifact=route)+call('prepare_basis_graph',candidate=stage.validator.attempt+1,prove=False)
        return call('save_basis_draft',artifact=route)+call('prepare_basis_graph',candidate=stage.validator.attempt+1,prove=False)+call('submit_draft',artifact=value)
    if stage.mode=='basis-frontier':
        item=json.loads(stage.task_inputs['frontier-item.json'])
        return call('submit_draft',artifact={'route':'derivation','statement':item['statement'],'argument':NOTE,
            'source':'Synthetic fixture only','consumer_uses':[{'id':'R002','application':NOTE}],'evidence':[]})
    if stage.mode=='basis-semantic-review':
        reject=mode in {'mismatch','first-pass'} and stage.logs.parents[1].name=='0001'
        review=reviewed_value(stage,{'B001':'FAIL'} if reject else {})
        if mode=='evidence-repair':
            return call('check_draft',artifact=review)+call('submit_draft',artifact={'from_saved_review':True,'summary':{}})
        return call('submit_draft',artifact=review)
    if stage.mode in {'nl0-authoring','nl0-global','nl0-global-from-basis','nl0-local-authoring'}:return author_code(stage)
    if (stage.mode,mode) in {('interface-semantic-review','late'),('interface-proof-diagnosis','late-proof')}:
        row=json.loads(stage.task_inputs['basis-registry.json'])['dependencies'][0]
        finding={'basis_id':'B001','field':'statement','frozen_value':row['statement'],
            'source_id':'problem.md','source_quote':'if a=b, then a+0=b.',
            'use_id':'basis-proof.md','use_pointer':'','use_quote':'the additive identity a+0=a',
            'explanation':'Existence of a common integer does not express the additive identity needed at a.',
            'correction':'Use the universal natural-number addition identity as the basis statement.'}
        return call('report_basis_defect',**{**finding,'basis_id':'B999'})+call('report_basis_defect',**finding)
    if stage.mode in {'interface-semantic-review','audit-a-global','audit-a-packet-replay'}:
        return call('submit_draft',artifact=review_value(stage))
    if stage.mode=='translation-source-preparation':
        return call('submit_draft',artifact={'status':'NO_CHANGE','reason':NOTE})
    if stage.mode=='interface-authoring':
        value=addition_interface()
        if graph_continuation:
            value['steps'][-1]['inputs'].append('H001')
        if mode=='local-edge' or mode.startswith('relabel-'):value['steps'][-1]['inputs'].append('H001')
        if mode=='native-source':
            value['premise_types']['M001']='∀ a b c : ℕ, a / b / c = a / c / b'
            value['steps'][-1]['inputs'].append('M001')
        from basis import problem_inputs
        registry=problem_inputs(job)/'basis-registry.json'
        rows=ir.load(registry)['dependencies'] if registry.is_file() else [dependency(category=2)] if mode=='direct-external' else []
        if graph_continuation or imported_code or ported_code:value['header']=ir.load(registry)['lean_header']
        for row in rows:
            if mode.startswith('relabel-'):row['port']='E014'
            if not row['port'] or (mode=='planned-unused-residual' and row['port']=='E003'):continue
            value['premise_types'][row['port']]=row['lean']['type']
            value['steps'][-1]['inputs'].append(row['port'])
            value['endpoint_correspondence'][row['port']]={'mode':'direct','explanation':NOTE}
        if mode=='universe-use':
            consumer=value['steps'][-1]
            consumer['inputs']=['T001','T003']
            consumer['input_instances']={'T003':[{'levels':['0'],'uses':[{'args':['ℕ','a']}]}]}
            value['steps'].insert(1,{'id':'T003','statement':'∀ (A : Type u) [AddZeroClass A] (x : A), x + 0 = x',
                'source_steps':['S002'],'inputs':['E001'],'explanation':'Apply the frozen right identity at the current type.',
                'universe_params':['u'],'input_instances':{'E001':[{'levels':['u'],'uses':[{
                    'parameters':[{'name':'A','type':'Type u'},{'name':'inst','type':'AddZeroClass A','binder_kind':'instance'},
                                  {'name':'x','type':'A'}],'args':['A','x'],'expected':'x + 0 = x'}]}]}})
        return call('submit_draft',artifact=value)
    if stage.mode=='proof':
        if graph_continuation:
            proof='exact h_H001.symm' if stage.step=='T001' else 'simpa only [h_E001 a] using h_T001.symm'
            return call('submit_transition',proof=proof)
        if mode=='native-source' and stage.step=='T002':
            return call('submit_transition',proof='have _ := h_M001 a 1 1\nsimpa only [Nat.add_zero] using h_T001.symm')
        if mode=='universe-use' and stage.step in ('T003','T002'):
            proof='intro A _ x; exact h_E001 A x' if stage.step=='T003' else 'exact (h_T003 ℕ a).trans h_T001.symm'
            return call('submit_transition',proof=proof)
        if mode.startswith('relabel-') and stage.step=='T002':
            return call('submit_transition',proof='exact (h_E014 a).trans (h_H001.trans (h_T001.trans h_H001))')
        if ir.contract(stage.cpath)['id']=='PrivateProof':
            if stage.plan['steps'][0]['statement'] in {'a = a','b = b'}:return call('submit_transition',proof='rfl')
            if mode in {'planned-conditional','planned-continue','planned-unused-residual'}:
                return call('submit_transition',proof='exact h_H001')
            doc=next(iter(stage.private_sources))
            return call('read_private_source',id=doc,start=1,end=4)+call('check_auxiliary',statement='∀ n : ℕ, n + 0 = n',proof='exact h_H001')+call('submit_transition',proof='exact @yui_aux_0001 h_H001')
        if mode=='local-edge' and stage.step=='T002':
            return call('submit_transition',proof='exact (h_E001 a).trans (h_H001.trans (h_T001.trans h_H001))')
        if mode=='late-proof' and stage.step=='T002':
            return call('check_transition',proof='exact True.intro')+call('report_proof_obstruction',layer='interface',
                explanation='The supplied basis statement differs from its formal premise.',locations=['/target'],
                candidates=[{'kind':'proof','candidate':1}])
        if mode=='planned-closed' and not ported_code and stage.step=='T001':
            work=stage.helper_work
            if not work.jobs:
                return call('check_transition',proof='exact Nat.zero')+call('dispatch_helpers',candidate=1,
                    obligations=[{'statement':s,'gap':'Establish the reflexive equalities used by this draft.',
                        'use':'Use in the local proof before applying symmetry.','source_steps':[]} for s in ('a = a','b = b')])
            if work.wait_ids:
                return None
            pending=[sid for sid,(_,_,future) in work.jobs.items() if not future.done()]
            if pending:
                return call('wait_for_helpers',task_ids=pending)
            return ''.join(call('collect_helper',task_id=sid) for sid in work.jobs)+call('submit_transition',
                proof='have _ := @yui_aux_0001 a b h_H001\nhave _ := @yui_aux_0002 a b h_H001\nexact h_H001.symm')
        if mode.startswith('planned-') and stage.step=='T002':
            return call('submit_transition',proof='simpa only [h_E002 a] using h_T001.symm')
        return call('submit_transition',proof='exact h_H001.symm' if stage.step=='T001'
                    else 'simpa only [h_E001 a] using h_T001.symm' if job['formalization']=='unconditional' or mode=='direct-external' else 'simpa using h_T001.symm')
    if stage.mode=='audit-b-assembly' and mode=='native-source':
        mapping=json.loads(stage.task_inputs['mapping.json'])
        mapping['library_terms']['M001']='exact @Nat.div_right_comm'
        return call('submit_draft',artifact=mapping)
    raise AssertionError('Unexpected stage '+stage.mode)


def respond(f,handler,number,payload):
    stage=f.stage;requests[stage.logs]+=1
    try:
        helper_turns=(mode=='planned-closed' and not ported_code
                      and getattr(stage,'helper_work',None) is not None and stage.step=='T001')
        basis_repair=mode in ('dependency-repair','planned-continue') and stage.mode=='basis-authoring'
        if requests[stage.logs]>(10 if helper_turns else 5 if basis_repair else 2):
            rows=[json.loads(line) for line in (stage.logs/'tools.jsonl').read_text().splitlines()] if (stage.logs/'tools.jsonl').exists() else []
            detail=json.dumps([{'tool':r['tool'],**{key:r['result'][key] for key in
                        ('status','error','stage_complete','candidate','diagnostics') if key in r['result']}}
                               for r in rows][-15:])[-5000:]
            raise AssertionError('Repeated fixture request: '+stage.mode+' '+detail)
        # The HTTP fixture is a separate server thread, not a Yui proof worker.
        # Read its oracle's contract under the declared job environment. Actual
        # worker manifests below still independently expose inherited settings.
        from runtime_config import use_environment, use_profiles
        import lean_libraries
        with use_environment(job.get('lean_environment')), use_profiles(job['profiles']), lean_libraries.use(job.get('lean_libraries',[])), \
                lean_libraries.generated(run/'imported-lean'):
            code=scripted(stage)
        if read_strategies and code is not None and (not helper_turns or not stage.helper_work.jobs):
            selected = {'basis-authoring': ('basis','ST021'), 'basis-frontier': ('basis','ST024'),
                        'interface-authoring': ('basis','ST022'), 'proof': ('lean','ST026')}
            if stage.mode in selected:
                bank, sid = selected[stage.mode]
                code = call('consult_strategy', bank=bank)+call('consult_strategy', bank=bank, ids=[sid])+code
    except Exception as error:
        print(repr(error),flush=True)
        queue_controller.cancel_batch([run])
        raise
    if mode=='cancel-review' and stage.mode=='basis-semantic-review':
        queue_controller.cancel_batch([run])
    if code is None:f.message(handler,number,'Waiting for the requested helper result.')
    else:f.code(handler,number,code)


if __name__ == '__main__':
    with NativeFixture(run/'fixture', responder=respond) as fixture:
        fixture.stage.release_resources('USER_CANCELLED')
        execute=model_pilot.Stage._execute
        pause=fault_control.Gate.pause
        def dispatch(stage):
            if stop_before_revision and 'prior-global.json' in getattr(stage,'task_inputs',{}):
                queue_controller.cancel_batch([run])
                raise execution_state.Cancelled('Stop at the recorded local graph return')
            prior=fixture.stage;fixture.stage=stage
            try:return execute(stage)
            finally:fixture.stage=prior
        unexpected=[]
        import workflow_checkpoint
        save_checkpoint=workflow_checkpoint.write
        def operator_checkpoint(path,record):
            save_checkpoint(path,record)
            if mode=='evidence-repair' and record.get('status')=='WAITING' and record['stage']=='nl0':
                queue_controller.cancel_batch([run])
        register=execution_state.Recorder.register_process
        def registered(recorder,process,kind,*args,**kw):
            result=register(recorder,process,kind,*args,**kw)
            if mode=='cancel-native' and kind=='lean' and fixture.stage.mode=='basis-authoring':
                queue_controller.cancel_batch([run])
            return result
        def decide(gate,error,**options):
            if gate.stage=='basis-decision':
                def choose(_):
                    if mode=='deadline-decision':
                        # Simulate elapsed wall clock only after the real residual decision is retained.
                        gate.recorder.deadline=time.monotonic()-.1
                    else:
                        action={'planned-conditional':'accept-conditional','planned-unused-residual':'accept-conditional',
                                'relabel-residual':'accept-conditional','planned-stop':'stop','planned-continue':'continue'}.get(mode,mode)
                        subprocess.run(gate.state['decisions'][action],check=True,capture_output=True,timeout=15)
                gate.wait=choose
            else:
                status=error.get('outcome',{}).get('status') if isinstance(error,dict) else None
                expected={'late':'BASIS_REVISION_REQUIRED','late-proof':'BASIS_REVISION_REQUIRED','first-pass':'BASIS_SEMANTIC_NONPASS',
                          'deadline-decision':'UNFINISHED','local-gap':'SUBSTANTIVE_GAP','first-pass-edge':'NL0_GRAPH_REVISION_REQUIRED'}
                if status!=expected.get(mode) or mode not in expected:
                    unexpected.append((gate.stage,str(error)[:3000]))
                def cancel(_):
                    count=len(fixture.calls)
                    time.sleep(.15)
                    assert count==len(fixture.calls)
                    queue_controller.cancel_batch([run])
                gate.wait=cancel
            return pause(gate,error,**options)
        with ExitStack() as dependencies, patch.object(model_pilot.Stage,'_execute',dispatch),patch.object(fault_control.Gate,'pause',decide), \
             patch.object(execution_state.Recorder,'register_process',registered), \
             patch.object(workflow_checkpoint,'write',operator_checkpoint):
            if mode=='dependency-repair':
                import test_imported_lean
                spec=ir.load(run.parent/'dependency-fixture.json')
                repository=(spec['remote'],Path(spec['checkout']),spec['revision'])
                _,transport=test_imported_lean.ImportedLeanTests().local_git_transport(repository)
                dependencies.enter_context(transport)
                dependencies.enter_context(patch('source_access.public_url',side_effect=AssertionError('Fixed source used web access')))
            result=case_runner.execute(job)
            if result['status']=='PAUSED_ERROR' and not unexpected:
                queue_controller.cancel_batch([run])
                result=ir.load(run/'case-result.json')['result']
    if unexpected or fixture.failures or result['status']=='CANCELLED' and not stop_before_revision and mode not in {'late','late-proof','first-pass','deadline-decision','cancel-native','cancel-review','stalled-graph','local-gap','first-pass-edge','evidence-repair'}:
        print('Fixture failures:',unexpected,fixture.failures,'result:',result,flush=True)
        raise SystemExit(2)
    raise SystemExit(0 if result['completion']['workflow_completed'] else 1)
