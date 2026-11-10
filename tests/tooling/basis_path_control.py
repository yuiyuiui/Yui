"""Genuine frozen case, local native clients and Lean. Only model replies and operator choices are scripted."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
import time
import subprocess
import sys
from unittest.mock import patch

job = json.loads(Path(sys.argv[1]).read_text())
run = Path(job['root'])
mode = sys.argv[2]
read_strategies = mode.endswith('+reference')
mode = mode.removesuffix('+reference')
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
    evidence=[r for r in stage.validator.expected_inputs if r['path']=='inputs/problem.md']
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
                    return call('report_graph_issue',inference='R002',related_propositions=['E003','E002'],
                                explanation='The checked E002 suffices at this use. Drop the redundant assumption E003.')
            if stage.mode==fg.LOCAL or 'prior-global.json' in stage.task_inputs:
                registry['dependencies']=[r for r in registry['dependencies'] if r['port']!='E003']
        add_external_applications(graph,registry,evidence)
    if mode=='direct-external':
        add_external_applications(graph,artifact(dependency(category=2)),evidence)
    if mode=='local-gap' and stage.mode==fg.LOCAL:
        return call('report_obstacle',status='SUBSTANTIVE_GAP',location='R002 last implication',
            basis='The supplied statements do not imply the requested implication.',
            explanation='The obligations conflict at the last inference even after consulting all available roots.',
            partial_progress='The earlier symmetry node can still be retained.')
    if mode in {'local-edge','first-pass-edge','relabel-closed','relabel-residual'}:
        if stage.mode==fg.LOCAL:
            current=json.loads(stage.task_inputs[fg.ASSIGNED])['graph']
            if 'H001' not in next(r for r in current['inferences'] if r['id']=='R002')['inputs']:
                return (call('report_graph_issue',inference='R999',related_propositions=['H001'],explanation='Wrong node.')+
                        call('report_graph_issue',inference='R002',related_propositions=['H999'],explanation='Unknown input.')+
                        call('report_graph_issue',inference='R002',related_propositions=['H001'],
                             explanation='The chosen last equality uses the original equality directly as well as its symmetric form.'))
        graph['inferences'][-1]['inputs'].append('H001')
        last=graph['inferences'][-1]['argument'][-1]
        last['uses'].append('H001')
        last['text']+=' Compose the original equality, its symmetric equality and the original equality to obtain the last equality.'
    if stage.mode==fg.BASIS and 'prior-global.json' in stage.task_inputs and mode!='stalled-graph':
        if mode=='local-edge':
            # The graph protocol accepts omitted H/P aliases copied from their original specification.
            for prop in graph['propositions']:
                if prop['kind'] in ('target','hypothesis'):
                    del prop['statement']
        renames={'rename_foundations':{'B001':'E014'}} if mode.startswith('relabel-') else {}
        return call('submit_draft',artifact={'spec':spec,**fg.shape(graph),**renames})
    if stage.mode==fg.BASIS:
        return call('submit_draft',artifact={'spec':spec,
            'proposition_details':{p['id']:{k:v for k,v in p.items() if k not in ('id','statement')} for p in graph['propositions']},
            'inference_definitions':{r['id']:r['definitions'] for r in graph['inferences']}})
    if stage.mode==fg.DIRECT:
        return call('submit_draft',artifact={'spec':spec,**fg.shape(graph)})
    draft=({'local_proofs':[{k:r[k] for k in ('id',*fg.BODY_FIELDS)} for r in graph['inferences']]}
           if stage.mode==fg.LOCAL else {'spec':spec,'graph':graph})
    code=call('check_draft',artifact=draft)
    for row in graph['inferences']:
        code+=call('read_author_packet',candidate=1,inference=row['id'])
    repaired=json.loads(stage.task_inputs.get('repair-obligations.json','{"issues":[]}'))
    resolutions=[{'id':i['id'],'location':i['location'],'note':'The revised N001 is the symmetric equality.'} for i in repaired['issues']]
    code+=call('record_author_checks',candidate=1,readiness='no_known_issue',open_issues=[],resolutions=resolutions,
        original_context_note=NOTE,output_notes=[{'id':row['id'],'note':NOTE} for row in graph['propositions']
                                                if row['kind'] in {'internal','target'}],
        inference_notes=[{'id':row['id'],'dependency_and_local_assumption_check':NOTE,
            'source_application_check':NOTE,'declaration_check':NOTE} for row in graph['inferences']])
    return code+call('submit_draft',artifact={'accept_candidate':1})


def review_value(stage):
    contract=stage.validator;value=deepcopy(contract.base)
    for pointer in contract.required:
        row={'verdict':'PASS','notes':NOTE}
        if stage.mode.startswith('interface-'):
            row['locations']=[{'document':'spec.json','pointer':'/full_target'},
                              {'document':'contract.json','pointer':'/conclusion/type'}]
        elif stage.mode=='audit-a-global':
            row['locations']=['spec.json#/full_target' if pointer=='/target_review' else 'nl0.json#/inferences']
            if pointer=='/structure_review' and mode in {'global-revision','stalled-graph'}:
                props=json.loads(stage.task_inputs['nl0.json'])['propositions']
                bad=next((i for i,p in enumerate(props) if p['statement']=='Both numbers vanish.'),None)
                if bad is not None:row.update(verdict='FAIL',notes='Equality does not imply both numbers vanish.',locations=[f'nl0.json#/propositions/{bad}/statement'])
            if pointer.startswith('/source_reviews/'):
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
        wants_residual=mode in {'stop','accept-conditional','continue','deadline-decision','relabel-residual'} and revision=='0001'
        cat=4 if wants_residual else 2
        row=dependency(category=cat)
        if mode=='universe-use':
            row['statement']='In an additive structure with zero, adding zero on the right preserves each element.'
            row['lean']={'type':'∀ (A : Type*) [AddZeroClass A] (x : A), x + 0 = x',
                         'proof':'intro A _ x; exact add_zero x'}
        if mode in {'mismatch','first-pass','late','late-proof'} and revision=='0001':
            row['statement']='There exists one natural number n such that every natural number equals n.'
        if mode=='evidence-repair' and requests[stage.logs]==1:
            row['origin']['evidence']=[{'path':'external-sources/misspelled.pdf','sha256':'0'*64}]
        if mode.startswith('planned-'):
            base=dependency(category=2);base['port']=None
            derived=dependency('B002',3)
            rows=[base,derived]
            if mode!='planned-closed' and (mode!='planned-continue' or requests[stage.logs]==1):
                rows.append(dependency('B003',4,port='E003'))
            value=active_artifact(artifact(*rows))
            target=value['dependencies'][1]
            target['lean']['proof']=None
            frontier=''
            if mode=='planned-closed':
                frontier=call('investigate_basis_frontier',obligations=[
                    {'id':r['id'],'statement':r['statement'],'consumers':[{'id':'R002','required_use':NOTE}]}
                    for r in value['dependencies']])
            return frontier+call('submit_draft',artifact=value)
        value=active_artifact(artifact(row))
        if mode=='stalled-graph' or (mode=='global-revision' and revision=='0001'):
            next(p for p in value['global_graph']['propositions'] if p['id']=='N001')['statement']='Both numbers vanish.'
        return call('submit_draft',artifact=value)
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
        if mode=='local-edge' or mode.startswith('relabel-'):value['steps'][-1]['inputs'].append('H001')
        from basis import problem_inputs
        registry=problem_inputs(job)/'basis-registry.json'
        rows=ir.load(registry)['dependencies'] if registry.is_file() else [dependency(category=2)] if mode=='direct-external' else []
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
        if mode=='universe-use' and stage.step in ('T003','T002'):
            proof='intro A _ x; exact h_E001 A x' if stage.step=='T003' else 'exact (h_T003 ℕ a).trans h_T001.symm'
            return call('submit_transition',proof=proof)
        if mode.startswith('relabel-') and stage.step=='T002':
            return call('submit_transition',proof='exact (h_E014 a).trans (h_H001.trans (h_T001.trans h_H001))')
        if ir.contract(stage.cpath)['id']=='PrivateProof':
            if stage.plan['steps'][0]['statement'] in {'a = a','b = b'}:return call('submit_transition',proof='rfl')
            doc=next(iter(stage.private_sources))
            return call('read_private_source',id=doc,start=1,end=4)+call('check_auxiliary',statement='∀ n : ℕ, n + 0 = n',proof='exact h_H001')+call('submit_transition',proof='exact @yui_aux_0001 h_H001')
        if mode=='local-edge' and stage.step=='T002':
            return call('submit_transition',proof='exact (h_E001 a).trans (h_H001.trans (h_T001.trans h_H001))')
        if mode=='late-proof' and stage.step=='T002':
            return call('check_transition',proof='exact True.intro')+call('report_proof_obstruction',layer='interface',
                explanation='The supplied basis statement differs from its formal premise.',locations=['/target'],
                candidates=[{'kind':'proof','candidate':1}])
        if mode=='planned-closed' and stage.step=='T001':
            return call('prove_independent_helpers',obligations=[{'statement':s,'explanation':'Equality reflexivity.'} for s in ('a = a','b = b')])+call('submit_transition',proof='have _ := @yui_aux_0001 a b h_H001\nhave _ := @yui_aux_0002 a b h_H001\nexact h_H001.symm')
        if mode.startswith('planned-') and stage.step=='T002':
            return call('submit_transition',proof='simpa only [h_E002 a] using h_T001.symm')
        return call('submit_transition',proof='exact h_H001.symm' if stage.step=='T001'
                    else 'simpa only [h_E001 a] using h_T001.symm' if job['formalization']=='unconditional' or mode=='direct-external' else 'simpa using h_T001.symm')
    raise AssertionError('Unexpected stage '+stage.mode)


def respond(f,handler,number,payload):
    stage=f.stage;requests[stage.logs]+=1
    try:
        if requests[stage.logs]>2:
            detail=(stage.logs/'tools.jsonl').read_text()[-12000:] if (stage.logs/'tools.jsonl').exists() else ''
            raise AssertionError('Repeated fixture request: '+stage.mode+' '+detail)
        code=scripted(stage)
        if read_strategies:
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
    f.code(handler,number,code)


if __name__ == '__main__':
    with NativeFixture(run/'fixture', responder=respond) as fixture:
        fixture.stage.release_resources('USER_CANCELLED')
        execute=model_pilot.Stage._execute
        pause=fault_control.Gate.pause
        def dispatch(stage):
            prior=fixture.stage;fixture.stage=stage
            try:return execute(stage)
            finally:fixture.stage=prior
        unexpected=[]
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
                          'deadline-decision':'UNFINISHED','stalled-graph':'NL0_GRAPH_REVISION_UNRESOLVED','local-gap':'SUBSTANTIVE_GAP','first-pass-edge':'NL0_GRAPH_REVISION_REQUIRED'}
                if status!=expected.get(mode) or mode not in expected:
                    unexpected.append((gate.stage,str(error)[:3000]))
                def cancel(_):
                    count=len(fixture.calls)
                    time.sleep(.15)
                    assert count==len(fixture.calls)
                    queue_controller.cancel_batch([run])
                gate.wait=cancel
            return pause(gate,error,**options)
        with patch.object(model_pilot.Stage,'_execute',dispatch),patch.object(fault_control.Gate,'pause',decide), \
             patch.object(execution_state.Recorder,'register_process',registered):
            result=case_runner.execute(job)
    if unexpected or fixture.failures or result['status']=='CANCELLED' and mode not in {'late','late-proof','first-pass','deadline-decision','cancel-native','cancel-review','stalled-graph','local-gap','first-pass-edge'}:
        print('Fixture failures:',unexpected,fixture.failures,'result:',result,flush=True)
        raise SystemExit(2)
    raise SystemExit(0 if result['completion']['workflow_completed'] else 1)
