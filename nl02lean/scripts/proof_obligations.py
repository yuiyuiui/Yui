"""Schedule independent private proofs and return source that the consumer can recheck."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
import tempfile

import concurrency
import ir
import local_helpers
from controller_common import bind, write, verify_bindings


def parallel(owner, items, work, *, requested='auto', role='foundation'):
    if not items:
        return []
    parent = getattr(owner,'budget',None)
    # Release the parent's slot while it waits. Nested local jobs use the very
    # same quota as their siblings; never resize an active lane.
    if role=='proof' and parent is not None and parent.role=='proof':
        budget = parent
    else:
        budget = concurrency.Budget(concurrency.resolve(requested,node_count=len(items)),
                                    execution=getattr(parent,'execution',None),role=role)
    limit = min(len(items),budget.configuration['effective'])
    recorder=budget.execution
    parent_task=getattr(owner,'execution_task',None)
    def run(item):
        from execution_state import activate
        if not recorder:return work(item,budget)
        key='private-'+local_helpers.digest([str(owner.logs),role,item])[:24]
        recorder.task(key,parent_task=parent_task,role=role,state='PENDING')
        with activate(recorder,key):
            recorder.check(key)
            return work(item,budget)
    with parent.suspended() if parent else nullcontext():
        expansion=budget.private_batch(len(items)) if budget is parent else nullcontext(limit)
        with expansion as width, ThreadPoolExecutor(max_workers=width) as pool:
            futures = [pool.submit(run,item) for item in items]
            return [f.result() for f in futures]


def complete_private(stage, receipt):
    from execution_state import now
    write(stage.logs/'role-completion.json',{'boundary':'PRIVATE_WORK_DELIVERED','role':stage.mode,
          'submission':bind(stage.logs/'accepted.json'),'evidence':[bind(receipt)]})
    stage.release_resources('ROLE_COMPLETED')
    if getattr(stage,'execution',None):
        stage.execution.task(stage.execution_task,state='FINISHED',role_state='CLOSED',activity='PRIVATE_WORK_DELIVERED',finished_at_utc=now())


def private_proof(directory, *, identity, header, parameters, premises, target, statement, route, budget, evidence=()):
    """Run the normal Lean author on exactly the selected conditional statement."""
    import model_pilot
    packet={'identity':identity,'header':header,'parameters':parameters,'premises':premises,
            'type':target,'statement':statement,'route':route,'evidence':list(evidence),'pins':ir.load_lock()['mathlib']['rev']}
    directory=Path(directory)/local_helpers.digest(packet)
    directory.mkdir(parents=True,exist_ok=True)
    receipt=directory/'checked.json'
    if receipt.is_file():
        prior=ir.load(receipt)
        verify_bindings([prior['source'],prior['result']])
        ir.need(ir.load(prior['source']['path'])==packet,'Private proof authority changed')
        result=ir.load(prior['result']['path'])
        ir.need(result['exit_code']==0 and result['proof_sha256']==local_helpers.digest(prior['proof']),
                'Private proof result changed')
        return prior['proof']
    attempt=Path(tempfile.mkdtemp(prefix='attempt-',dir=directory))
    source=attempt/'source.json';write(source,packet)
    steps=[{'id':'S001','text':route}]
    cpath=attempt/'contract.json'
    write(cpath,{'version':1,'id':'PrivateProof','source':{'path':source.name,'sha256':ir.digest(source)},
        'source_steps':steps,'pins':{'lean_version':'4.32.2','mathlib_commit':packet['pins']},
        'header':header,'parameters':parameters,'premises':premises,'conclusion':{'statement':statement,'type':target},
        'representation':{'scope':'Private conditional proof under the listed ports'},
        'review':{'mode':'development_owner_review','scope':'Local implementation; full parent acceptance required'}})
    plan={'version':1,'contract_sha256':ir.digest(cpath),'representation_notes':'Use the exact enclosing types and binders.',
          'steps':[{'id':'T001','statement':target,'inputs':[p['id'] for p in premises],
                    'source_steps':['S001'],'explanation':route}],'terminal':'T001'}
    from jobs import stage_document
    docs={}
    verify_bindings(evidence)
    for index,ref in enumerate(evidence,1):
        path=Path(ref['path']);view=attempt/f'source-{index:03d}.txt'
        stage_document(path,view);docs[f'S{index:03d} '+path.name]=bind(view)
    stage=model_pilot.Stage(attempt/'worker',cpath,'proof',None,plan,'T001',budget=budget,private_worker=True,
                            private_sources=docs)
    result,selected=stage.execute()
    from execution_health import require_review_execution, StageFailure
    try:require_review_execution(result,stage.logs/'result.json',phase='private-proof')
    except StageFailure as error:
        if error.result['status']=='EXECUTION_UNQUALIFIED':raise RuntimeError(str(error)) from error
        raise
    if not selected or 'proof' not in selected:
        raise RuntimeError('Private proof worker did not deliver checked source: '+str(attempt/'worker/result.json'))
    value=selected['proof']
    # A stored worker handoff still needs an independent complete-source check.
    import lean_timeout_policy
    with lean_timeout_policy.stage_scope(stage, 'transition'):
        native=ir.check(cpath,plan,{'T001':value},only='T001')
    if native['exit_code']:
        raise ValueError('Private proof failed complete-source check: '+ir.compiler_feedback(native))
    body=local_helpers.as_tactic(value,ir.local_packet(cpath,plan,'T001'))
    body=local_helpers.NAME.sub(lambda m:'yui_nested_'+identity+'_'+m[0][8:],body)
    native['proof_sha256']=local_helpers.digest(body)
    write(attempt/'complete.json',native)
    write(receipt,{'source':bind(source),'result':bind(attempt/'complete.json'),'proof':body})
    complete_private(stage,receipt)
    return body


def helper_batch(stage, args):
    import artifact_protocol as p
    p.validate(args,batch_schema())
    items=args['obligations']
    if len({item['statement'] for item in items})!=len(items):
        raise ValueError('Repeated private goal; request each independent obligation once')
    packet=ir.local_packet(stage.cpath,stage.plan,stage.step)
    # Original local binders (including upstream T ports) remain explicit.
    params=packet['parameters']+[{'name':port['binder'],'type':port['type']} for port in packet['inputs']]
    def solve(item,budget):
        ir.type_text(item['statement'])
        return private_proof(stage.logs/'private-proofs',identity=local_helpers.digest(item)[:16],
            header=packet['header'],parameters=params,premises=[],target=item['statement'],
            statement=item['explanation'],route=item['explanation'],budget=budget)
    bodies=parallel(stage,items,solve,role='proof')
    results=[]
    for item,body in zip(items,bodies):
        # Register through the same native API as every hand-written local helper.
        result=stage.dispatch('check_auxiliary',{'statement':item['statement'],'proof':body})
        results.append({k:result[k] for k in ('accepted','helper','error','stdout','stderr') if k in result})
    return {'accepted':all(r.get('helper') for r in results),'helpers':results,'stage_complete':False}


def batch_schema():
    import artifact_protocol as p
    return p.obj({'obligations':p.array(p.obj({'statement':p.TEXT,'explanation':p.TEXT}),minItems=1)})
