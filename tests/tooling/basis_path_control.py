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
tests = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(tests), str(run/'runtime/nl0/scripts'), str(run/'runtime/nl02lean/scripts'),
                str(tests.parent/'nl0/scripts'),str(tests.parent/'nl02lean/scripts')]
import harness_support
from native_fixture import NativeFixture
from basis_fixtures import artifact, dependency, reviewed_value, add_external_applications
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
    add_external_applications(graph,json.loads(stage.task_inputs['basis-registry.json']),evidence)
    code=call('check_draft',artifact={'spec':spec,'graph':graph})
    for row in graph['inferences']:
        code+=call('read_author_packet',candidate=1,inference=row['id'])
    code+=call('record_author_checks',candidate=1,readiness='no_known_issue',open_issues=[],
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
        wants_residual=mode in {'stop','accept-conditional','continue','deadline-decision'} and revision=='0001'
        cat=4 if wants_residual else 2
        row=dependency(category=cat)
        if mode in {'mismatch','first-pass','late','late-proof'} and revision=='0001':
            row['statement']='There exists one natural number n such that every natural number equals n.'
        if mode=='evidence-repair' and requests[stage.logs]==1:
            row['origin']['evidence']=[{'path':'external-sources/misspelled.pdf','sha256':'0'*64}]
        return call('submit_draft',artifact=artifact(row))
    if stage.mode=='basis-semantic-review':
        reject=mode in {'mismatch','first-pass'} and stage.logs.parents[1].name=='0001'
        review=reviewed_value(stage,{'B001':'FAIL'} if reject else {})
        if mode=='evidence-repair':
            return call('check_draft',artifact=review)+call('submit_draft',artifact={'from_saved_review':True,'summary':{}})
        return call('submit_draft',artifact=review)
    if stage.mode=='nl0-authoring':return author_code(stage)
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
        row=ir.load(run/'active-inputs/basis-registry.json')['dependencies'][0]
        value['premise_types'][row['port']]=row['lean']['type']
        value['steps'][-1]['inputs'].append(row['port'])
        value['endpoint_correspondence'][row['port']]={'mode':'direct','explanation':NOTE}
        return call('submit_draft',artifact=value)
    if stage.mode=='proof':
        if mode=='late-proof' and stage.step=='T002':
            return call('check_transition',proof='exact True.intro')+call('report_proof_obstruction',layer='interface',
                explanation='The supplied basis statement differs from its formal premise.',locations=['/target'],
                candidates=[{'kind':'proof','candidate':1}])
        return call('submit_transition',proof='exact h_H001.symm' if stage.step=='T001'
                    else 'simpa only [h_E001 a] using h_T001.symm')
    raise AssertionError('Unexpected stage '+stage.mode)


def respond(f,handler,number,payload):
    stage=f.stage;requests[stage.logs]+=1
    try:
        if requests[stage.logs]>2:
            detail=(stage.logs/'tools.jsonl').read_text()[-12000:] if (stage.logs/'tools.jsonl').exists() else ''
            raise AssertionError('Repeated fixture request: '+stage.mode+' '+detail)
        code=scripted(stage)
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
            fixture.stage=stage
            return execute(stage)
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
                        subprocess.run(gate.state['decisions'][mode],check=True,capture_output=True,timeout=15)
                gate.wait=choose
            else:
                status=error.get('outcome',{}).get('status') if isinstance(error,dict) else None
                expected={'late':'BASIS_REVISION_REQUIRED','late-proof':'BASIS_REVISION_REQUIRED','first-pass':'BASIS_SEMANTIC_NONPASS',
                          'deadline-decision':'UNFINISHED'}
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
    if unexpected or fixture.failures or result['status']=='CANCELLED' and mode not in {'late','late-proof','first-pass','deadline-decision','cancel-native','cancel-review'}:
        print('Fixture failures:',unexpected,fixture.failures,'result:',result,flush=True)
        raise SystemExit(2)
    raise SystemExit(0 if result['completion']['workflow_completed'] else 1)
