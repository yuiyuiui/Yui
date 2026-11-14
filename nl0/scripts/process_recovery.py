"""Owner-AI diagnosis of an in-place native cleanup checkpoint.

The live owner retains the Popen handle. Advice can request another verified
cleanup attempt, never substitute for ownership/exit evidence or proof checks.
"""
from copy import deepcopy
from pathlib import Path
import fcntl
import json
import os
import shlex
import subprocess
import sys
import time
import traceback
import uuid

from controller_common import bind, verify_bindings, write
import execution_state as execution
import process_queries

VERSION='yui-process-recovery-1'
FAULT='NATIVE_CLEANUP_UNCONFIRMED'
IDENTITY='PROCESS_IDENTITY_UNCONFIRMED'
AUTO_RECHECK_SECONDS=60
TAKEOVER_SECONDS=60


def _active(root, incident):
    if not isinstance(incident,str) or len(incident)!=32 or any(c not in '0123456789abcdef' for c in incident):
        raise ValueError('Use the exact process incident ID')
    root=Path(root).resolve()
    found=list((root/'logs/process-recovery').glob('*/error-state.json'))
    matches=[p for p in found if json.loads(p.read_text()).get('incident')==incident]
    if len(matches)!=1:raise ValueError('Unknown process incident')
    path=matches[0];state=json.loads(path.read_text())
    if path.is_symlink() or state.get('root')!=str(root) or state.get('state')!='PAUSED_ERROR':
        raise ValueError('Process incident is stale or belongs to another run')
    from fault_control import validate_context
    validate_context(root,state['job_binding'],True)
    checkpoint=state['checkpoint']
    verify_bindings([checkpoint['binding']])
    value=json.loads(Path(checkpoint['binding']['path']).read_text())
    if value.get('version')!=VERSION or value.get('fault_code') not in {FAULT,IDENTITY}:
        raise ValueError('Unknown process recovery checkpoint')
    verify_bindings(value['bindings'])
    verify_bindings([value['current_source']])
    return path,state,value


def diagnose(root, incident):
    """Bounded read-only probes; their output is advice, never exit authority."""
    path,state,checkpoint=_active(root,incident)
    probes=[];until=time.monotonic()+30
    pid=checkpoint['process']['pid']
    for name,command in [('observer',['ps','-p',str(os.getpid()),'-o','pid=,pgid=,stat=,lstart=']),
                         ('target',['ps','-p',str(pid),'-o','pid=,pgid=,stat=,lstart=']),
                         ('table',['ps','-ax','-o','pid=,pgid=,stat=,lstart='])]:
        remaining=until-time.monotonic()
        if remaining<=0:probes.append({'probe':name,'status':'BUDGET_EXHAUSTED'});continue
        begin=time.monotonic()
        try:
            result=subprocess.run(command,capture_output=True,text=True,timeout=min(10,remaining),env=dict(os.environ,LC_ALL='C'))
            probes.append({'probe':name,'exit_code':result.returncode,'output':result.stdout[:24000],
                           'stderr':result.stderr[:2000],'output_truncated':len(result.stdout)>24000,
                           'elapsed_seconds':time.monotonic()-begin})
        except (OSError,subprocess.SubprocessError) as error:
            probes.append({'probe':name,'status':type(error).__name__,'error':str(error),'elapsed_seconds':time.monotonic()-begin})
    _active(root,incident)  # A resolution or source change racing a probe rejects publication.
    result={'version':VERSION,'incident':incident,'checkpoint_sha256':state['checkpoint']['binding']['sha256'],
            'at_utc':execution.now(),'parent_observation':state['checkpoint'].get('parent_observation'),
            'probes':probes,'scope':'Read-only diagnostic observations; no proof, signal or cleanup acceptance.'}
    file=path.parent/'diagnosis-observation.json';write(file,result)
    return {'status':'PROCESS_DIAGNOSIS_PREPARED','observation':bind(file),**result}


def decide(root, incident, report):
    """Accept located owner advice for this exact still-open checkpoint."""
    path,state,checkpoint=_active(root,incident)
    value=process_queries.decision(json.loads(Path(report).read_text()))
    observation=path.parent/'diagnosis-observation.json'
    if (value['incident']!=incident or value['checkpoint_sha256']!=state['checkpoint']['binding']['sha256']
            or not observation.is_file() or value['observation_sha256']!=bind(observation)['sha256']):
        raise ValueError('Diagnosis does not match the current incident/checkpoint/observation')
    saved=path.parent/'owner-decisions'/(uuid.uuid4().hex+'.json')
    control=path.parent/'error-control'/(incident+'.json')
    with (path.parent/'.decision.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        _active(root,incident)
        used=path.parent/'owner-decisions'/('observation-'+value['observation_sha256']+'.json')
        if control.exists() or used.exists():raise ValueError('Decision already queued; collect a fresh observation before another action')
        write(saved,value)
        write(used,bind(saved))
        write(control,{'incident':incident,'id':saved.stem,'action':value['action'],'diagnosis':bind(saved)})
    return {'status':'PROCESS_DECISION_QUEUED','incident':incident,'action':value['action'],'diagnosis':bind(saved)}


class Recovery:
    def __init__(self, process, owner, work, source, native, recorder, task, confirm, *, clock=None):
        self.process,self.owner,self.work=process,deepcopy(owner),Path(work)
        self.source,self.native,self.recorder,self.task,self.confirm=Path(source),native,recorder,task,confirm
        self.clock=clock or time.monotonic
        self.auto_due=self.clock()+AUTO_RECHECK_SECONDS
        self.auto_done=False;self.directed_due=None;self.seen=set()
        self.takeover_due=self.clock()+TAKEOVER_SECONDS;self.takeover_reminded=False

    @staticmethod
    def notify(owner, message):
        from fault_control import queue_notification
        return queue_notification(owner,message,resume=True)

    def dispatch_started(self, gate):
        if 'owner_takeover' in gate.state:return
        observation=gate.logs/'diagnosis-observation.json'
        gate.state['owner_takeover']={'status':'AWAITING_ACKNOWLEDGEMENT',
            'previous_observation_sha256':bind(observation)['sha256'] if observation.is_file() else None,
            'meaning':'Queue/resume success is not evidence that diagnosis has started.'}

    def observe_takeover(self, gate):
        observation=gate.logs/'diagnosis-observation.json';status=gate.state['owner_takeover']
        if not observation.is_file():return
        try:
            binding=bind(observation)
            if binding['sha256'] in {status.get('previous_observation_sha256'),status.get('observation',{}).get('sha256')}:return
            _active(gate.root,gate.state['incident'])
            value=json.loads(observation.read_text())
            if (observation.is_symlink() or value.get('version')!=VERSION
                    or value.get('incident')!=gate.state['incident']
                    or value.get('checkpoint_sha256')!=gate.state['checkpoint']['binding']['sha256']):
                raise ValueError('Stale or foreign diagnosis acknowledgement')
            if status.pop('attention_required',False):gate.state['needs_user_decision']=False
            status.update(status='ACKNOWLEDGED',observation=binding,at_utc=execution.now())
            gate.persist()
        except (OSError,ValueError,KeyError,TypeError) as error:
            status['error']=str(error);gate.persist()

    def takeover_timeout(self, gate):
        if (self.takeover_reminded or self.clock()<self.takeover_due
                or gate.state['owner_takeover']['status']=='ACKNOWLEDGED'):return False
        self.takeover_reminded=True
        gate.state['owner_takeover'].update(status='UNACKNOWLEDGED',at_utc=execution.now(),attention_required=True,
            reason='No bound process-diagnose execution was observed within 60 seconds; owner takeover is unconfirmed.')
        gate.state['needs_user_decision']=True
        gate.state['notification']={'status':'PENDING'};gate.notification_attempts=0;gate.report()
        return True

    def bind(self, gate):
        job=gate.root/'job.json'
        current_source=bind(self.source)
        stable=Path(self.native.get('source_path',''))
        if not stable.is_file():
            stable=gate.logs/'native-source.lean';stable.write_bytes(self.source.read_bytes())
        retained_source=bind(stable)
        if retained_source['sha256']!=current_source['sha256']:
            raise ValueError('Native checkpoint source differs from the compiled input')
        code=IDENTITY if self.native.get('phase')=='child-identity' else FAULT
        checkpoint={'version':VERSION,'fault_code':code,'process':self.owner,'workspace':str(self.work),
                    'native_result':{k:v for k,v in self.native.items() if k not in {'stdout','stderr'}},
                    'bindings':[bind(job),retained_source],'current_source':current_source,
                    'queries':[r for r in process_queries.history()
                               if r.get('run_id')==self.recorder.state['run_id'] and r.get('task')==self.task],
                    'scope':'Resume cleanup and remaining checks only; no proof rewrite or acceptance.'}
        native_path=self.native.get('_record_path')
        if native_path and Path(native_path).is_file():checkpoint['bindings'].append(bind(native_path))
        else:
            retained=gate.logs/'native-result.json';write(retained,self.native)
            checkpoint['bindings'].append(bind(retained))
        file=gate.logs/'native-checkpoint.json';write(file,checkpoint)
        gate.state['checkpoint']={'binding':bind(file),'parent_observation':self.observation(),
                                  'automatic_recheck_pending':True,'fault_code':code}
        if self.recorder and self.task:self.recorder.task(self.task,activity='WAITING_FOR_PROCESS_DIAGNOSIS')

    def observation(self):
        try:load=list(os.getloadavg())
        except (OSError,AttributeError):load=None
        with self.recorder.lock:
            registered=deepcopy(self.recorder.state['processes'].get(str(self.process.pid),{}))
        return {'at_utc':execution.now(),'parent_handle_exit_code':self.process.poll(),'load_average':load,
                'registered_process':registered,
                'meaning':'Parent exit alone does not confirm group exit; load does not establish a cause.'}

    def notice(self, gate):
        entry=Path(__file__).with_name('yui.py')
        args=[sys.executable,'-B',str(entry)]
        return ('[Yui PROCESS DIAGNOSIS REQUEST] Owning AI: take responsibility for this incident.\n'
            'The native operation is suspended in place with its Popen handle; unrelated work must be preserved.\n'
            'Run: '+str(gate.root)+'\nIncident: '+gate.state['incident']+'\nState: '+str(gate.path)+'\n'
            'Read '+str(Path(__file__).parents[1]/'references/process-recovery.md')+'.\n'
            'Collect observations: '+shlex.join([*args,'process-diagnose',str(gate.root),'--incident',gate.state['incident']])+'\n'
            'Submit diagnosis: '+shlex.join([*args,'process-decision',str(gate.root),'--incident',gate.state['incident'],'--report','<diagnosis.json>'])+'\n'
            'Write a located diagnosis and submit it using process-decision --report FILE. Choose recheck, wait, or escalate.\n'
            'Diagnose and use already-authorized safe repairs before asking the user. A busy-system hypothesis is not exit evidence. '
            'Never edit frozen runtime/proof inputs, kill unidentified processes, cancel the case or declare PASS. '
            'If a repair exceeds authority or cannot safely attach to this live checkpoint, present concrete options in the owning desktop chat.\n'
            'Checkpoint: '+json.dumps(gate.state['checkpoint'])+'\n'
            'Latest owner diagnosis: '+json.dumps(gate.state.get('owner_diagnosis'))+'; user decision required: '+str(gate.state.get('needs_user_decision',False))+'\n'
            'Owner takeover: '+json.dumps(gate.state.get('owner_takeover'))+'\n'
            'One delayed native recheck is scheduled. AI advice never replaces actual cleanup and remaining trust checks.')

    def tick(self, gate):
        if self.recorder and self.recorder.deadline is not None:self.recorder.check(self.task)
        self.observe_takeover(gate)
        control=gate.logs/'error-control'/(gate.state['incident']+'.json')
        if control.is_file():
            try:
                request=json.loads(control.read_text())
                if request.get('id') not in self.seen:
                    self.seen.add(request.get('id'));_active(gate.root,gate.state['incident'])
                    verify_bindings([request['diagnosis']])
                    report=process_queries.decision(json.loads(Path(request['diagnosis']['path']).read_text()))
                    observation=gate.logs/'diagnosis-observation.json'
                    if (request['incident']!=gate.state['incident'] or report['incident']!=request['incident']
                            or report['checkpoint_sha256']!=gate.state['checkpoint']['binding']['sha256']
                            or report['observation_sha256']!=bind(observation)['sha256'] or request['action']!=report['action']):
                        raise ValueError('Stale or altered process diagnosis')
                    gate.state['owner_diagnosis']=request['diagnosis']
                    self.auto_done=True
                    if report['action']=='escalate':
                        gate.state['needs_user_decision']=True
                        gate.state['notification']={'status':'PENDING'};gate.notification_attempts=0;gate.report()
                    else:self.directed_due=self.clock()+report['delay_seconds']
                control.unlink()
            except (OSError,ValueError,KeyError,TypeError) as error:
                gate.state['decision_rejected']=str(error)
            gate.persist()
        due=(self.directed_due is not None and self.clock()>=self.directed_due)
        automatic=not self.auto_done and self.clock()>=self.auto_due
        if not due and not automatic:
            self.takeover_timeout(gate)
            return False
        self.directed_due=None;self.auto_done=True
        try:
            _active(gate.root,gate.state['incident'])
            confirmed=self.confirm()
        except (execution.Cancelled,execution.CaseDeadlineExceeded):raise
        except Exception as error:
            confirmed=False;gate.state['recheck_error']=type(error).__name__+': '+str(error)
            gate.state['recheck_traceback']=traceback.format_exc()
        gate.check_cancel()
        gate.state['checkpoint'].update(parent_observation=self.observation(),automatic_recheck_pending=False)
        gate.state.setdefault('cleanup_rechecks',[]).append({'at_utc':execution.now(),'confirmed':bool(confirmed),'automatic':automatic})
        if confirmed:
            resolution=('FRESH_NATIVE_IDENTITY_CONFIRMED' if self.native.get('phase')=='child-identity'
                        else 'FRESH_NATIVE_CLEANUP_CONFIRMED')
            gate.state.update(state='RESOLVED',resolved_at_utc=execution.now(),resolution=resolution)
            if self.recorder and self.task:self.recorder.task(self.task,state='RUNNING',activity=resolution)
        else:
            if not self.takeover_timeout(gate):
                gate.state['notification']={'status':'PENDING'};gate.notification_attempts=0;gate.report()
        gate.persist()
        return bool(confirmed)


def recover(process, owner, work, source, native, recorder, task, confirm):
    """Only a live owned case has an AI/decision checkpoint; standalone callers retain uncertainty."""
    if (recorder is None or not (recorder.root/'.yui-run.json').is_file()
            or recorder.cancelled(task) or not owner):return False
    from fault_control import Gate
    logs=recorder.root/'logs/process-recovery'/uuid.uuid4().hex
    code=IDENTITY if native.get('phase')=='child-identity' else FAULT
    gate=Gate(logs,recorder=recorder,task=task,stage='native-process-identity' if code==IDENTITY else 'native-process-cleanup')
    operation=Recovery(process,owner,work,source,native,recorder,task,confirm)
    gate.pause({'code':code,'message':'Native process state needs owner-AI diagnosis'},
               resumable=False,operation=operation)
    return gate.state['state']=='RESOLVED'
