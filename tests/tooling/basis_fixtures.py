"""Small basis controls; source/reviewer metadata is synthetic, never certification."""
from pathlib import Path

import basis
import basis_native
import basis_review
import ir
from controller_common import bind, write, manifest

TARGET='For natural numbers a and b, if a=b, then a+0=b.'


def dependency(key='B001', category=1, *, port=None, compatibility=None, typ='∀ n : ℕ, n + 0 = n', proof='intro n; exact Nat.add_zero n'):
    compatibility=compatibility or {1:'native',2:'adapted',3:'internal',4:'unresolved'}[category]
    if category in {2,3,4} or compatibility=='adapted':port=port or 'E'+key[1:]
    return {'id':key,'category':category,'statement':'For every natural number n, n+0=n.',
        'origin':{'kind':{1:'mathlib',2:'lean-library',3:'derivation',4:'textbook'}[category],
            'reference':'SYNTHETIC attribution control; the actual native proof is elementary.',
            'revision':'SYNTHETIC fixture version','evidence':[{'input':'problem.md'}] if category in {2,4} else []},
        'compatibility':compatibility,'uses':['B001'] if category==3 else [],'port':port,
        'lean':{'type':typ,'proof':None if category==4 else 'exact YuiBasis.B001' if category==3 else proof},
        'justification':'Software fixture only; source and semantic classifications are not independently certified.'}


def artifact(*rows):
    return active_artifact({'version':basis.VERSION,'full_target':TARGET,
        'proof':'From a=b and the additive identity a+0=a, obtain a+0=b.',
        'dependencies':list(rows),'replacements':[],'lean_header':'import Mathlib\n'})


def active_artifact(value):
    """Build the current graph schema from an elementary, synthetic proof."""
    from copy import deepcopy
    v=deepcopy(value);v['version']=basis.VERSION
    graph=ir.load(Path(__file__).resolve().parents[1]/'fixtures/closed-addition/nl0.json')
    add_external_applications(graph,v,[])
    v['global_graph']={'propositions':[{k:r[k] for k in ('id','statement')} for r in graph['propositions']],
        'inferences':[{**{k:r[k] for k in ('id','inputs','output')},'basis':[
            b['id'] for b in v['dependencies'] if b['port'] in r['inputs'] or
            (b['port'] is None and b['category']==1 and r['output']=='P')]} for r in graph['inferences']]}
    return v


def checked_context(root, value, *, approved=False, documents=None):
    root=Path(root)
    if approved:
        import jobs
        from harness_support import PROFILES
        import target_selection
        root.mkdir(parents=True)
        problem=root/'proof.md';problem.write_text(TARGET)
        job=jobs.prepare(problem,track='full',formalization='unconditional',profiles=PROFILES,
            target=target_selection.resolve(problem,requested=TARGET))
        root=Path(job['root'])/'2basis/0001'
    inputs=root/'inputs';inputs.mkdir(parents=True)
    if documents:
        import shutil
        originals=[bind(Path(documents)/r['path']) for r in ir.load(Path(documents)/'inputs.json')['inputs']]
        for row in originals:shutil.copyfile(row['path'],inputs/Path(row['path']).name)
    else:
        (inputs/'problem.md').write_text(TARGET+'\nSYNTHETIC source fixture, not a publication.\n')
        originals=[bind(inputs/'problem.md')]
    manifest(inputs);write(root/'stage/accepted.json',value)
    declarations,checks,roots=basis.declarations(value)
    native=basis_native.check(value['lean_header']+declarations,checks,roots,root/'native')
    if not native['passed']:raise AssertionError(ir.load(root/'native/compiler.json'))
    residual=sorted(r['id'] for r in value['dependencies'] if r['category']==4)
    context={'version':basis.CONTEXT_VERSION,'formalization':'unconditional','full_target':value['full_target'],
        'basis':bind(root/'stage/accepted.json'),'native':bind(root/'native/check.json'),
        'original_inputs':originals,
        'evidence':basis.evidence_bindings(value,inputs,root),'approval':None,'residual_class4':residual}
    from clean_stage import ArtifactStage
    from role_sessions import Sessions
    from unittest.mock import patch
    sessions=Sessions()
    with patch.object(ArtifactStage,'_execute',synthetic_review):
        context['semantic_review'],findings=basis_review.assess(root,context,value,sessions,None,{})
    assert not findings
    if approved:
        import fault_control
        from unittest.mock import patch
        pause=fault_control.Gate.pause
        def decide(gate,error,**kw):
            gate.notify=lambda *_:{'status':'QUEUED'}
            gate.wait=lambda _:fault_control.final_decision(gate.root,gate.state['incident'],'accept-conditional')
            return pause(gate,error,**kw)
        with patch.object(fault_control.Gate,'pause',decide):
            context['approval']=basis.decision(root,value,None)
    sessions.close_all('BASIS_PREPARED',[root/'review/report.json'])
    return context


def reviewed_value(stage, verdicts=None):
    packet=ir.load(stage.logs.parent/'inputs'/basis_review.PACKET)
    items={}
    for key in packet['required']:
        items[key]={'verdict':(verdicts or {}).get(key,'PASS'),
            'notes':'Synthetic located operator/quantifier comparison for software testing.',
            'locations':['/items/'+key+'/statement','/items/'+key+'/actual_type'],
            'source':'Synthetic fixture declaration; no research-source verdict.',
            'application':'Synthetic additive-identity application at the displayed natural number.'}
        if (packet.get('revision_objection') or {}).get('basis_id')==key:
            items[key]['resolution']='The revised universal statement agrees with the additive identity at a.'
    return {'items':items,'coverage':{'/items/'+key:'assessed' for key in items}}


def synthetic_review(stage, verdicts=None, saved_via=None):
    from run_resources import retention
    value=reviewed_value(stage,verdicts)
    if saved_via=='check':
        assert stage.dispatch('check_draft',{'artifact':value})['accepted']
    elif saved_via=='record':
        for key,row in value['items'].items():
            assert stage.dispatch('record_review_item',{'pointer':'/items/'+key,'coverage':'assessed','judgment':row})['recorded']
    if saved_via:value={'from_saved_review':True,'summary':{}}
    result=stage.dispatch('submit_draft',{'artifact':value})
    if not result.get('stage_complete'):raise AssertionError(result)
    stage.submission_closed=True
    stage.workspace_retention=retention(stage.work,getattr(stage,'workspace_owner_logs',stage.logs))
    exposure={'status':'NATIVE-CODEX-CONTEXT-CHECK-PASSED','configured_model':stage.model,'errors':[]}
    record={'status':'ACCEPTED','execution_health':'NO_RECORDED_FAULT','usage':{'complete':False},
        'temporary_workspace_removed':False,'workspace_retention':stage.workspace_retention,
        'role_session':stage.role_session,'model':stage.model,'exposure':exposure}
    for name,data in [('accepted.json',stage.accepted),('result.json',record),('exposure-audit.json',exposure)]:
        write(stage.logs/name,data)
    return record,stage.accepted


def add_external_applications(graph,value,evidence):
    for row in value['dependencies']:
        if not row['port'] or not row['port'].startswith('E'):continue
        contract={k:'SYNTHETIC metadata and source review control only.' for k in (
            'author','title','version','identifier','locator','notation_map','errata','source_kind',
            'origin','retrieved_at','source_statement','context','qualification','version_check')}
        contract.update(statement=row['statement'],evidence=evidence,primary_evidence=evidence,hypotheses=[])
        graph['propositions'].insert(0,{'id':row['port'],'kind':'external','statement':row['statement'],
            'definitions':[],'binders':[],'objects':[],'source':contract})
        r=graph['inferences'][-1];r['inputs'].append(row['port'])
        r['argument'][0]['uses'].append(row['port'])
        r['applications'].append({'id':'A'+row['id'][1:],'input':row['port'],'at':'S001',
            'bindings':'Apply the universally quantified natural-number identity at a.','hypothesis_checks':[]})
