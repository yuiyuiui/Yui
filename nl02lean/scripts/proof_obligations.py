"""Schedule independent private proofs and return source that the consumer can recheck."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import nullcontext
from contextvars import copy_context
from pathlib import Path
import re
import time

import execution_state
import private_handoff as handoff

import concurrency
import ir
import local_helpers
from controller_common import bind, write


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
        from role_sessions import independent
        with independent():
            if not recorder:return work(item,budget)
            key='private-'+local_helpers.digest([str(owner.logs),role,item])[:24]
            recorder.task(key,parent_task=parent_task,role=role)
            with activate(recorder,key):
                recorder.check(key)
                return work(item,budget)
    with parent.suspended() if parent else nullcontext():
        expansion=budget.private_batch(len(items)) if budget is parent else nullcontext(limit)
        with expansion as width, ThreadPoolExecutor(max_workers=width) as pool:
            futures = [pool.submit(copy_context().run,run,item) for item in items]
            return [f.result() for f in futures]


def complete_private(stage, receipt):
    from execution_state import now
    write(stage.logs/'role-completion.json',{'boundary':'PRIVATE_WORK_DELIVERED','role':stage.mode,
          'submission':bind(stage.logs/'accepted.json'),'evidence':[bind(receipt)]})
    stage.release_resources('ROLE_COMPLETED')
    if getattr(stage,'execution',None):
        stage.execution.task(stage.execution_task,state='FINISHED',role_state='CLOSED',activity='PRIVATE_WORK_DELIVERED',finished_at_utc=now())


def publish_result(req, number, status, files):
    result=req.root/f'result-{number:03d}.json'
    record={'schema':handoff.wire.RESULT,'request':handoff.wire.reference(req.root,req.path),
            'attempt':number,'status':status,'files':{k:handoff.wire.reference(req.root,path) for k,path in files.items()}}
    handoff.wire.validate_result(record,result,req.path)
    handoff.publish(result,record)
    return result


def problem_result(req, attempt, number, status, **fields):
    field=handoff.wire.OUTCOMES[status][0]
    path=attempt/(field+'.json')
    records={}
    names=('worker/result.json','worker/accepted.json','worker/proof-repair-request.json','worker/tools.jsonl',
           'worker/usage.json','declaration-error.json','native-error.json','proof.json','check.json')
    material=[*(attempt/name for name in names),*sorted((attempt/'worker/lean-drafts').glob('*.json'))]
    for file in material:
        if file.is_file():
            ir.need(file.resolve()==file,'Linked private proof diagnostic evidence')
            records[file.relative_to(attempt).as_posix()]=handoff.wire.reference(attempt,file)
    handoff.publish(path,{'request_sha256':ir.digest(req.path),'attempt':number,'records':records,**fields})
    return publish_result(req,number,status,{field:path})


def start_worker(req, attempt, budget):
    import model_pilot
    import proof_diagnosis
    stage=model_pilot.Stage(attempt/'worker',req.contract,'proof',None,req.plan,'T001',
                            budget=budget,private_worker=True,private_sources=req.documents)
    stage.diagnose_obstruction=lambda author,request,out:proof_diagnosis.run_private(author,request,out,budget=budget)
    return stage


def finish_checked(req, attempt, number, stage):
    """The proof and check each survive a failure at the following publication."""
    import lean_timeout_policy
    proof_path=attempt/'proof.json'
    proof=handoff.read_proof(req,number,proof_path)
    check=attempt/'check.json'
    if not check.exists():
        with lean_timeout_policy.stage_scope(stage,'transition') if stage is not None else nullcontext():
            native=ir.check(req.contract,req.plan,{'T001':proof},only='T001')
        if not ir.native_succeeded(native):
            write(attempt/'native-error.json',native)
            return problem_result(req,attempt,number,'execution_error',step='complete-source check',
                                  error_type=native.get('error_kind') or native['status'],message=ir.compiler_feedback(native) or native['status'])
        handoff.validate_native(req,native,proof)
        handoff.publish(check,{'request_sha256':ir.digest(req.path),'attempt':number,'proof_sha256':ir.digest(proof_path),'native':native})
    files={'proof':proof_path,'check':check}
    handoff.checked_body(req,number,files)
    return publish_result(req,number,'checked',files)


def finish_role(req, number, result, stage, budget):
    worker=req.root/f'attempt-{number:03d}'/'worker'
    if not (worker/'accepted.json').is_file():
        return
    if stage is None:
        recorder=getattr(budget,'execution',None)
        stage=next((s for s,_ in getattr(recorder,'retained_stages',[]) if Path(s.logs).resolve()==worker),None)
    if stage is not None and not getattr(stage,'_resources_released',False):
        complete_private(stage,result)
    elif not (worker/'role-completion.json').exists():
        # An offline readback has no live stage to release. The normal case cleanup owns any retained workspace.
        write(worker/'role-completion.json',{'boundary':'PRIVATE_WORK_DELIVERED','role':'proof',
              'submission':bind(worker/'accepted.json'),'evidence':[bind(result)]})


def worker_outcome(req, attempt, number, report, selected):
    from execution_health import require_review_execution, StageFailure, record_qualification
    if report.get('repair_request') and record_qualification(report)['record_context_qualified']:
        repair=report['repair_request']
        return problem_result(req,attempt,number,'needs_parent_repair',
                              location=', '.join(repair['locations']),required_change=repair['explanation'])
    if report.get('status') in {'CANCELLED','REPAIR_WAIT'} or (report.get('status')=='UNFINISHED' and
            not report.get('execution_fault') and report.get('execution_health')!='FAULT'):
        return problem_result(req,attempt,number,'unfinished',reason=report.get('stop_reason') or report['status'])
    try:
        require_review_execution(report,attempt/'worker/result.json',phase='private-proof')
    except StageFailure as error:
        if error.result['status']=='EXECUTION_UNQUALIFIED':
            return problem_result(req,attempt,number,'execution_error',step='worker qualification',
                                  error_type=error.result['status'],message=str(error))
        return problem_result(req,attempt,number,'unfinished',reason=error.result['status'])
    if not isinstance(selected,dict) or 'proof' not in selected:
        return problem_result(req,attempt,number,'execution_error',step='read accepted submission',
                              error_type='MISSING_PROOF',message='The qualified worker supplied no proof.')
    handoff.publish(attempt/'proof.json',{'request_sha256':ir.digest(req.path),'attempt':number,'proof':selected['proof']})
    return None


def run_attempt(req, attempt, number, budget):
    from execution_state import Cancelled, CaseDeadlineExceeded
    stage=None
    # The outcome detail can survive a failure writing its manifest, just like a native check.
    for status in handoff.DETAILS:
        key=handoff.wire.OUTCOMES[status][0];detail=attempt/(key+'.json')
        if detail.exists():
            return publish_result(req,number,status,{key:detail})
    types=req.root/'declaration-check.json'
    if not types.exists():
        native=ir.check(req.contract,req.plan,types_only=True)
        if not ir.native_succeeded(native):
            write(attempt/'declaration-error.json',native)
            if native.get('timed_out') or native.get('error_kind'):
                return problem_result(req,attempt,number,'execution_error',step='declaration check',
                    error_type=native.get('error_kind') or 'NATIVE_TIMEOUT',message=ir.compiler_feedback(native) or native['status'])
            return problem_result(req,attempt,number,'needs_parent_repair',location='/files/contract/conclusion/type',
                                  required_change=ir.compiler_feedback(native) or 'Correct the private declaration.')
        handoff.validate_native(req,native)
        handoff.publish(types,native)
    handoff.validate_native(req,ir.load(types))
    proof=attempt/'proof.json'
    legacy=req.root/'legacy-candidate.json'
    if not proof.exists() and legacy.exists() and number==1:
        prior=ir.load(legacy)
        ir.need(prior['request_sha256']==ir.digest(req.path),'Legacy source belongs to another request')
        handoff.publish(proof,{'request_sha256':ir.digest(req.path),'attempt':number,'proof':prior['proof']})
    if not proof.exists():
        logs=attempt/'worker'
        if not (logs/'result.json').exists():
            if logs.exists():
                return problem_result(req,attempt,number,'unfinished',reason='WORKER_INTERRUPTED_BEFORE_RESULT')
            try:
                stage=start_worker(req,attempt,budget)
                stage.execute()
            except (Cancelled,CaseDeadlineExceeded):
                raise
            except Exception as error:
                return problem_result(req,attempt,number,'execution_error',step='worker execution',
                                      error_type=type(error).__name__,message=str(error) or type(error).__name__)
            if not (logs/'result.json').is_file():
                return problem_result(req,attempt,number,'execution_error',step='read worker result',
                                      error_type='MISSING_RESULT',message='Worker returned without a persisted result.')
        report=handoff.wire.read(logs/'result.json')
        selected=handoff.wire.read(logs/'accepted.json') if (logs/'accepted.json').is_file() else None
        result=worker_outcome(req,attempt,number,report,selected)
        if result is not None:
            return result
    result=finish_checked(req,attempt,number,stage)
    if ir.load(result)['status']=='checked':
        finish_role(req,number,result,stage,budget)
    return result


def recover_checked_work(req, previous, attempt, number):
    """Rebind a retained proof after a controller fault, keeping issued attempts immutable."""
    proof_path=previous/'proof.json'
    if not proof_path.is_file() or (previous/'native-error.json').exists():
        return
    proof=handoff.read_proof(req,number-1,proof_path)
    check=previous/'check.json'
    if check.is_file():
        handoff.checked_body(req,number-1,{'proof':proof_path,'check':check})
    new=attempt/'proof.json'
    handoff.publish(new,{'request_sha256':ir.digest(req.path),'attempt':number,'proof':proof})
    if check.is_file():
        handoff.publish(attempt/'check.json',{'request_sha256':ir.digest(req.path),'attempt':number,
                        'proof_sha256':ir.digest(new),'native':ir.load(check)['native']})


def recorded_result(result):
    from execution_state import current, now
    recorder,task=current()
    if recorder is not None and task and task.startswith('private-'):
        status=ir.load(result)['status']
        state={'checked':'FINISHED','needs_parent_repair':'FINISHED','unfinished':'UNFINISHED','execution_error':'UNFINISHED'}[status]
        activity='PRIVATE_WORK_DELIVERED' if status=='checked' else 'PRIVATE_'+status.upper()
        recorder.task(task,state=state,activity=activity,private_result=bind(result),finished_at_utc=now())
    return result


def deliver(request, budget):
    """The worker accepts only an issued request and returns only a result manifest path."""
    from execution_state import Cancelled, CaseDeadlineExceeded
    req=handoff.read_request(request)
    with handoff.locked(req.root,'.worker.lock'):
        numbers=[int(match[1]) for path in req.root.iterdir() if (match:=re.fullmatch(r'attempt-([0-9]+)',path.name))]
        number=max(numbers,default=1)
        result=req.root/f'result-{number:03d}.json'
        previous=None
        if result.exists():
            row,_=handoff.read_result(req.path,result)
            if row['status']=='checked':
                finish_role(req,number,result,None,budget)
                return recorded_result(result)
            if row['status']=='needs_parent_repair':
                return recorded_result(result)
            if row['status']=='execution_error':
                previous=req.root/f'attempt-{number:03d}'
            number+=1
        attempt=req.root/f'attempt-{number:03d}'
        ir.need(not attempt.is_symlink(),'Linked private proof attempt')
        attempt.mkdir(exist_ok=True)
        if previous is None and number>1 and not (attempt/'check.json').exists():
            earlier=req.root/f'result-{number-1:03d}.json'
            if earlier.is_file() and handoff.read_result(req.path,earlier)[0]['status']=='execution_error':
                previous=req.root/f'attempt-{number-1:03d}'
        if previous is not None:
            recover_checked_work(req,previous,attempt,number)
        try:
            result=run_attempt(req,attempt,number,budget)
        except (Cancelled,CaseDeadlineExceeded) as error:
            problem_result(req,attempt,number,'unfinished',reason=type(error).__name__+': '+str(error))
            raise
        except (OSError,RuntimeError,NameError) as error:
            if (req.root/f'result-{number:03d}.json').exists():
                raise
            step='prepare private request'
            if (attempt/'check.json').is_file():
                step='publish result manifest'
            elif (attempt/'proof.json').is_file():
                step='save complete-source check'
            elif (attempt/'worker/result.json').is_file():
                step='save submitted proof'
            result=problem_result(req,attempt,number,'execution_error',step=step,
                                  error_type=type(error).__name__,message=str(error) or type(error).__name__)
        return recorded_result(result)


def restore_private_work(request, previous_stage):
    """Bring only a matching child's durable proof/check into an explicitly continued case."""
    req=handoff.read_request(request)
    previous=Path(previous_stage).resolve()
    old=previous/'private-proofs'/req.root.name
    if previous==req.root.parent.parent or handoff.run_id(previous)!=req.record['run_id'] or not (old/'request.json').is_file():
        return
    ir.need(old.resolve()==old,'Linked prior private proof directory')
    with handoff.locked(old,'.worker.lock'):
        issued=handoff.read_request(old/'request.json')
        ir.need(ir.digest(issued.path)==ir.digest(req.path),'Prior private request differs from the issued task')
        attempts=sorted((p for p in old.iterdir() if re.fullmatch(r'attempt-[0-9]+',p.name)),
                        key=lambda p:int(p.name.split('-')[1]),reverse=True)
        if not attempts:
            return
        saved=attempts[0];number=int(saved.name.split('-')[1])
        ir.need(saved.resolve()==saved,'Linked prior private attempt')
        result=old/f'result-{number:03d}.json'
        if result.exists():
            row,_=handoff.read_result(issued.path,result)
            if row['status'] not in {'checked','execution_error'}:
                return
        proof=saved/'proof.json';check=saved/'check.json'
        if not proof.is_file() or (saved/'native-error.json').exists():
            return
        proof_value=handoff.read_proof(issued,number,proof)
        if check.is_file():
            handoff.checked_body(issued,number,{'proof':proof,'check':check})
        with handoff.locked(req.root,'.worker.lock'):
            attempt=req.root/'attempt-001'
            if (attempt/'worker').exists() or (req.root/'result-001.json').exists():
                return
            attempt.mkdir(exist_ok=True)
            types=old/'declaration-check.json'
            if types.exists():
                native=ir.load(types);handoff.validate_native(req,native)
                handoff.publish(req.root/types.name,native)
            target=attempt/'proof.json'
            handoff.publish(target,{'request_sha256':ir.digest(req.path),'attempt':1,'proof':proof_value})
            if check.is_file():
                handoff.publish(attempt/'check.json',{'request_sha256':ir.digest(req.path),'attempt':1,
                                'proof_sha256':ir.digest(target),'native':ir.load(check)['native']})


def receive_foundation(request, result):
    """Foundation intake reads the checked file before adding dependency binders."""
    row,body=handoff.read_result(request,result)
    if row['status']!='checked':
        raise_outcome(row,body,result)
    handoff.publish(request.parent/'checked.json',{'schema':'yui-foundation-private-input-1',
        'request':handoff.wire.reference(request.parent,request),'result':handoff.wire.reference(request.parent,result)})
    return body


def raise_outcome(row, detail, result):
    from execution_state import Cancelled
    status=row['status']
    if status=='unfinished' and detail['reason'] in {'CANCELLED','EXTERNAL_CANCEL'}:
        raise Cancelled('Private proof cancelled: '+str(result))
    if status=='execution_error':
        raise RuntimeError(detail['step']+': '+detail['message']+' ('+str(result)+')')
    raise ValueError('Private proof '+status+': '+detail.get('required_change',detail.get('reason',''))+' ('+str(result)+')')


def receive(stage, result, *, expected_request=None, raise_failures=True):
    result=Path(result)
    root=stage.logs.resolve()/'private-proofs'
    ir.need(result.parent.parent==root and result.parent.resolve()==result.parent,'Result belongs to another parent node')
    request=result.parent/'request.json' if expected_request is None else Path(expected_request)
    req=handoff.read_request(request)
    ir.need(req.record['run_id']==handoff.run_id(stage.logs) and req.record['parent_node']==stage.step
            and req.record['parent_context_sha256']==local_helpers.context(stage.cpath,stage.plan,stage.step)
            and req.root.parent==stage.logs.resolve()/'private-proofs','Request belongs to another parent node or context')
    row,body=handoff.read_result(request,result)
    ref=handoff.wire.reference(stage.logs.resolve(),result)
    if row['status']!='checked':
        if raise_failures and (row['status']=='execution_error' or
                row['status']=='unfinished' and body['reason'] in {'CANCELLED','EXTERNAL_CANCEL'}):
            raise_outcome(row,body,result)
        return {'accepted':False,'status':row['status'],'result':ref,
                **{key:body[key] for key in handoff.DETAILS[row['status']]}}
    statement=req.source['type']
    with handoff.locked(stage.logs,'.private-receive.lock'):
        registry=stage.logs/'local-helpers.json'
        rows=ir.load(registry) if registry.is_file() else stage.local_helpers
        local_helpers.validate(stage.cpath,stage.plan,stage.step,rows)
        stage.local_helpers=rows
        receipt=req.root/'checked.json'
        prior=ir.load(receipt) if receipt.is_file() else None
        helper=next((r for r in rows if r['statement']==statement and r['proof']==body
                     and (prior is None or r['name']==prior['helper'])),None)
        if prior is not None:
            ir.need(helper is not None,'Parent registration no longer matches the received proof')
        if helper is None:
            response=stage.dispatch('check_auxiliary',{'statement':statement,'proof':body})
            if not response.get('helper'):
                return {k:response[k] for k in ('accepted','error','stdout','stderr') if k in response}
            name=response['helper']['name']
            helper=next(r for r in stage.local_helpers if r['name']==name)
        check=req.root/'parent-check.json'
        handoff.publish(check,{'name':helper['name'],'context_sha256':helper['context_sha256'],
                              'helper_sha256':helper['sha256'],'native':helper['check']})
        handoff.publish(receipt,{'schema':'yui-private-proof-received-1','request':handoff.wire.reference(req.root,request),
            'result':handoff.wire.reference(req.root,result),'helper':helper['name'],'parent_check':handoff.wire.reference(req.root,check)})
        return {'accepted':True,'status':'checked','helper':local_helpers.callable_helper(stage,helper),'result':ref}


def helper_tools():
    from native_carrier import tool
    tools = {
        'dispatch_helpers': 'After the latest check_transition fails, send independent private Lean goals. '
            'Name the concrete gap, how each result will be used, and the parent source step IDs to pass. '
            'Returns task IDs immediately. Continue work or use wait_for_helpers.',
        'helper_status': 'List your issued helper task IDs and their current state.',
        'collect_helper': 'Collect one ready helper, recheck it with your exact inputs and return its application.',
        'wait_for_helpers': 'When there is no other work, ask to resume on the first selected result. '
            'Finish this turn after the acknowledgement so the controller can release your model slot.',
    }
    return [tool(name, description, schema['properties'],schema['required'])
            for name,description in tools.items() for schema in [helper_schema(name)]]


def helper_schema(name):
    import artifact_protocol as p
    ids = p.array(p.TEXT, uniqueItems=True)
    return p.obj({
        'dispatch_helpers': {'candidate': {'type':'integer','minimum':1},
            'obligations': p.array(p.obj({'statement':p.TEXT,'gap':p.TEXT,'use':p.TEXT,'source_steps':ids}), minItems=1)},
        'helper_status': {},
        'collect_helper': {'task_id':p.TEXT},
        'wait_for_helpers': {'task_ids': {**ids,'minItems':1}},
    }[name])


class HelperWork:
    """Own one bounded set of asynchronous private requests for this author."""
    def __init__(self, stage):
        self.stage = stage
        self.budget = stage.budget
        self.recorder = self.budget.execution
        self.pool = None
        self.jobs = {}
        self.received = set()
        self.wait_ids = ()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.pool is None:
            return
        active = []
        for key, _, future in self.jobs.values():
            if future.cancel():
                self.recorder.task(key,state='CANCELLED',activity='PARENT_FINISHED',finished_at_utc=execution_state.now())
            elif not future.done():
                active.append(key)
        if active:
            self.recorder.flush(force=True)
            for key in active:
                execution_state.request_cancel(self.recorder.root,key)
        self.pool.shutdown()

    def dispatch(self, name, args):
        import artifact_protocol as protocol
        protocol.validate(args,helper_schema(name))
        if name=='dispatch_helpers':
            ids=self.issue(args['candidate'],args['obligations'])
            return {'task_ids':ids}
        if name=='helper_status':
            return {'tasks':[{'task_id':sid,'status':self.status(job[2])} for sid,job in self.jobs.items()]}
        if name=='collect_helper':
            return self.collect(args['task_id'])
        ids=args['task_ids']
        futures=[self.job(sid)[2] for sid in ids]
        self.wait_ids=tuple(ids) if not any(future.done() for future in futures) else ()
        return {'wait_registered':bool(self.wait_ids)}

    @staticmethod
    def status(future):
        if future.done():
            return 'ready'
        return 'running' if future.running() else 'queued'

    def job(self, sid):
        ir.need(sid in self.jobs,'Unknown helper task for this parent')
        return self.jobs[sid]

    def issue(self, candidate, items):
        stage=self.stage
        rows=stage.own_lean_drafts['proof']
        check=rows.get(candidate,{}).get('check',{})
        attempt=stage.logs/'lean-drafts'/f'proof-{candidate:04d}.json'
        ir.need(candidate==max(rows,default=0) and check.get('status')=='LEAN-CHECK-FAILED'
                and not check.get('timed_out') and not check.get('error_kind')
                and attempt.is_file() and ir.load(attempt)==rows[candidate],
                'Dispatch requires the latest saved failed check of the complete target')
        packet=stage.bound_packet
        source={row['id']:row['text'] for row in packet['source_steps']}
        for item in items:
            ir.type_text(item['statement'])
            ir.need(set(item['source_steps'])<=source.keys(),'Helper source step is outside the parent task')
        params=packet['parameters']+[{'name':p['binder'],'type':p['type']} for p in packet['inputs']]
        context=local_helpers.context(stage.cpath,stage.plan,stage.step)
        ids=[]
        for item in items:
            evidence=[]
            for sid in sorted(item['source_steps']):
                name=sid if re.fullmatch(r'S[0-9]+',sid) else local_helpers.digest(sid)
                path=stage.logs/'private-sources'/(name+'.txt')
                path.parent.mkdir(exist_ok=True)
                ir.need(not path.is_symlink(),'Linked private helper source')
                text=source[sid].encode('utf-8')
                if not path.exists():
                    path.write_bytes(text)
                ir.need(path.read_bytes()==text,'Changed private helper source')
                evidence.append(bind(path))
            evidence.sort(key=lambda row:row['path'])
            route='Gap: '+item['gap']+'\nUse at parent: '+item['use']
            request=handoff.issue(stage.logs/'private-proofs',identity=local_helpers.digest([item['statement'],route])[:16],
                parent_node=stage.step,parent_context=context,header=packet['header'],parameters=params,premises=[],
                target=item['statement'],statement=item['gap'],route=route,evidence=evidence)
            sid=request.parent.name
            if sid not in self.jobs:
                if self.pool is None:
                    self.pool=ThreadPoolExecutor(max_workers=min(2,self.budget.configuration['effective']))
                key='private-'+local_helpers.digest([str(stage.logs),sid])[:24]
                self.recorder.task(key,parent_task=stage.execution_task,role='proof',activity='QUEUED',
                    helper_id=sid,private_request=bind(request),parent_attempt=bind(attempt))
                future=self.pool.submit(copy_context().run,self.run,key,request)
                self.jobs[sid]=(key,request,future)
            ids.append(sid)
        return list(dict.fromkeys(ids))

    def run(self, key, request):
        from role_sessions import independent
        import lean_timeout_policy
        try:
            with independent(),execution_state.activate(self.recorder,key),lean_timeout_policy.scope(
                    request.parent/'lean-timeouts',self.budget):
                self.recorder.check(key)
                self.recorder.task(key,state='RUNNING',activity='PREPARING_PRIVATE_PROOF')
                previous=getattr(self.stage,'previous_private_stage',None)
                if previous is not None:
                    restore_private_work(request,previous)
                return deliver(request,self.budget)
        except Exception as error:
            status='CANCELLED' if isinstance(error,execution_state.Cancelled) else 'UNFINISHED'
            self.recorder.task(key,state=status,activity=status,error=str(error),finished_at_utc=execution_state.now())
            raise

    def collect(self, sid):
        _,request,future=self.job(sid)
        if not future.done():
            return {'task_id':sid,'status':self.status(future)}
        try:
            result=future.result()
        except execution_state.Cancelled:
            return {'task_id':sid,'status':'unfinished','reason':'CANCELLED'}
        received=receive(self.stage,result,expected_request=request,raise_failures=False)
        if sid not in self.received and 'result' in received:
            self.recorder.task(self.stage.execution_task,last_helper_result={
                'at_utc':execution_state.now(),'task_id':sid,'status':received['status'],
                'helper':received.get('helper',{}).get('name')})
            self.received.add(sid)
        return {'task_id':sid,**received}

    def after_turn(self):
        ids,self.wait_ids=self.wait_ids,()
        futures=[self.job(sid)[2] for sid in ids]
        if not futures or any(future.done() for future in futures):
            return
        stage=self.stage
        checkpoint={'thread_id':stage.thread_id,'turn_id':stage.active_turn_id,'task_ids':ids}
        path=stage.logs/'helper-wait.json'
        write(path,{'status':'WAITING',**checkpoint})
        with self.budget.suspended(resume_on_error=False):
            self.recorder.task(stage.execution_task,activity='WAITING_FOR_HELPER',helper_wait=str(path),
                waiting_for_helpers=[self.job(sid)[0] for sid in ids])
            self.recorder.flush(force=True)
            while not wait(futures,timeout=.2,return_when=FIRST_COMPLETED).done:
                stage.check_runtime_state()
                if stage.timeout is not None and time.monotonic()>=stage.started+stage.timeout:
                    raise TimeoutError('Local proof deadline expired while waiting for a private proof')
        write(path,{'status':'RESUMED',**checkpoint,'ready':[sid for sid in ids if self.job(sid)[2].done()]})
        self.recorder.task(stage.execution_task,activity='MODEL_RUNNING',waiting_for_helpers=[])
