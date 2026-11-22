"""Independent case processes, each writing only its own explicitly owned run."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from contextlib import ExitStack

from controller_common import write, bind, final_write
import case_outcomes
import jobs as job_contract
from execution_state import (LaunchBlocked, finish_launch, identity, launch_intent, observe_launched_child,
                             request_cancel, terminate_owned, unregistered_group_exited)


def validate_job(value):
    return job_contract.validate(value)


def cancel_saved_pause(root, record, request):
    incident=case_outcomes.saved_pause(root,record)
    if incident is None:return
    result={**record['result'],'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED'}
    path=root/'execution-status.json'
    state=json.loads(path.read_text())
    state['result']={'status':'CANCELLED','outcome':result}
    write(path,state)
    write(root/'case-result.json',{**record,'result':result})
    # Keep the archived incident and its binding intact for later recovery.
    write(root/'logs/controller-errors/error-state.json',
          {**incident,'state':'CANCELLED','cancelled_at_utc':request['requested_at_utc']})


def cancel_batch(directories):
    for directory in directories:
        root=Path(directory).resolve()
        if not (root/job_contract.MARKER).is_file():raise ValueError('Unknown owned run')
        write(root/'cancel-request.json',{'external_cancel':True})
        if (root/'execution-status.json').is_file():
            request=request_cancel(root)
            try:record=json.loads((root/'case-result.json').read_text())
            except (OSError,ValueError):continue  # The live owner still has the cancellation request.
            cancel_saved_pause(root,record,request)


def launch_case(job_file,out):
    import runtime_snapshot
    job=json.loads(Path(job_file).read_text())
    snapshot=runtime_snapshot.validate(job)
    script=Path(snapshot['root'])/'nl0/scripts/case_runner.py'
    out=Path(out);(out/'logs').mkdir(exist_ok=True)
    with (out/'logs/controller.log').open('w') as log:
        return subprocess.Popen([sys.executable,'-u','-B',str(script),
            '--job',str(job_file)],stdout=log,stderr=log,start_new_session=True,
            env=runtime_snapshot.environment(job,snapshot=snapshot))


def case_exit(root, process, record):
    """Report an exited child without suspending the other batch slots."""
    from execution_state import Cancelled
    from fault_control import Gate
    retained = record.get('result') if isinstance(record, dict) else None
    error = {'code':'harness_bug','message':'Case process exited without task completion or user cancellation',
             'exit_code':process.returncode, 'retained_case_outcome':retained,
             'read_error':record.get('read_error') if isinstance(record, dict) else 'Invalid result envelope'}
    try:
        Gate(root/'logs/batch-errors',stage='case-process-exited').pause(error,resumable=False,wait_for_control=False)
    except Cancelled:
        return {'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED','retained_case_outcome':retained}
    return {'status':'EXECUTION_FAULT','error':error['message'], 'exit_code':error['exit_code'],
            'retained_case_outcome':retained,'read_error':error['read_error']}


def serve(jobs,*,case_concurrency=None,report_progress=False):
    jobs=list(jobs)
    for job in jobs:validate_job(job)
    return _serve_admitted(jobs,case_concurrency=case_concurrency,report_progress=report_progress)


def _serve_admitted(jobs,*,case_concurrency=None,report_progress=False):
    if len({j['root'] for j in jobs})!=len(jobs) or len({j['problem'] for j in jobs})!=len(jobs):
        raise ValueError('Duplicate case input/output in one batch')
    count=len(jobs) if case_concurrency is None else case_concurrency
    if type(count) is not int or count<1:raise ValueError('Positive concurrent-case count required')
    pending=list(jobs);active={};outcomes={};stopping=False;previous={};uncertain_groups=[]
    owner=identity(os.getpid())
    if owner is None:raise RuntimeError('Cannot establish batch controller identity')
    for job in jobs:
        root=Path(job['root'])
        write(root/'batch.json',{'controller':owner,'concurrent_cases':count,
            'case_run_roots':[j['root'] for j in jobs],'case':job['case'],
            'scope':'Controller metadata only; never a model input'})
        finish_launch(root, 'batch-launch-pending.json', os.environ.get('YUI_BATCH_LAUNCH_TOKEN'))
    def stop(*_):
        nonlocal stopping
        stopping=True;cancel_batch([j['root'] for j in jobs])
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT,signal.SIGTERM):previous[sig]=signal.signal(sig,stop)
    reports=ExitStack()
    try:
        if report_progress:
            from owner_reports import controller_reports
            reports.enter_context(controller_reports([Path(job['root']) for job in jobs]))
        while pending or active:
            for job in list(pending):
                root=Path(job['root'])
                if (root/'cancel-request.json').exists():
                    outcomes[job['id']]={'status':'CANCELLED','model_worker_called':False}
                    write(root/'case-result.json',{'job':bind(root/'job.json'),'result':outcomes[job['id']]})
                    pending.remove(job)
            while pending and len(active)<count and not stopping:
                job=pending.pop(0);root=Path(job['root'])
                if (root/'cancel-request.json').exists():
                    outcomes[job['id']]={'status':'CANCELLED','model_worker_called':False}
                    write(root/'case-result.json',{'job':bind(root/'job.json'),'result':outcomes[job['id']]});continue
                try:
                    with launch_intent([root], 'case-launch-pending.json') as token:
                        process=launch_case(root/'job.json',root)
                        active[job['id']]={'job':job,'process':process,'identity':None,'cancel_at':None,
                                           'launch_token':token,'identity_attempts':0}
                except LaunchBlocked as error:
                    if (root/'cancel-request.json').is_file():
                        outcomes[job['id']]={'status':'CANCELLED','model_worker_called':False}
                        write(root/'case-result.json',{'job':bind(root/'job.json'),'result':outcomes[job['id']]})
                    else:
                        outcomes[job['id']]={'status':'EXECUTION_FAULT','error':str(error)}
            if stopping:
                for job in pending:
                    outcomes[job['id']]={'status':'CANCELLED','model_worker_called':False}
                    write(Path(job['root'])/'case-result.json',{'job':bind(Path(job['root'])/'job.json'),'result':outcomes[job['id']]})
                pending.clear()
            for key,row in list(active.items()):
                root=Path(row['job']['root']);process=row['process']
                if row['identity'] is None and row['identity_attempts'] < 2:
                    row['identity_attempts']+=1
                    who=observe_launched_child(process,lookup=identity)
                    if who is not None:
                        row['identity']=who
                        write(root/'case-process.json',{'schema_version':'yui-owned-process-1','process':who,'kind':'case-controller'})
                        finish_launch(root,'case-launch-pending.json',row['launch_token'])
                if (root/'cancel-request.json').exists() and process.poll() is None:
                    row['cancel_at']=row['cancel_at'] or time.monotonic()
                    if (root/'execution-status.json').is_file():request_cancel(root)
                    if time.monotonic()-row['cancel_at']>35 and row['identity']:terminate_owned(process,row['identity'])
                if process.poll() is None:continue
                if row['identity'] is None:
                    if unregistered_group_exited(process):
                        finish_launch(root,'case-launch-pending.json',row['launch_token'])
                    else:
                        uncertain_groups.append(process.pid)
                result=root/'case-result.json'
                try:record=json.loads(result.read_text())
                except (OSError,ValueError) as error:record={'read_error':str(error)}
                value=record.get('result') if isinstance(record,dict) else None
                paused=case_outcomes.saved_pause(root,record)
                if paused and (root/'cancel-request.json').exists():
                    cancel_saved_pause(root,record,request_cancel(root))
                bound_stop=(not isinstance(value,dict) or value.get('status') not in {'STOPPED_BY_USER','UNFINISHED_LEAN_DEPENDENCY'}
                            or record.get('job')==bind(root/'job.json'))
                if not bound_stop or not (paused or case_outcomes.terminal(root,value)):
                    write(result,{'job':bind(root/'job.json'),'result':case_exit(root,process,record)})
                outcomes[key]=json.loads(result.read_text())['result'];del active[key]
            if pending or active:time.sleep(.1)
    except Exception as error:
        from fault_control import Gate
        from execution_state import Cancelled
        for job in jobs:
            if job['id'] in outcomes:continue
            root=Path(job['root'])
            try:
                Gate(root/'logs/batch-errors',stage='batch-controller').pause(error,resumable=False,wait_for_control=False)
                outcomes[job['id']]={'status':'EXECUTION_FAULT','error':str(error)}
            except Cancelled:
                outcomes[job['id']]={'status':'CANCELLED','task_outcome':'EXTERNAL_CANCELLED'}
    finally:
        reports.close()
        for row in active.values():
            root=Path(row['job']['root'])
            if (stopping or (root/'cancel-request.json').is_file()) and (root/'execution-status.json').exists():request_cancel(root)
        for row in active.values():
            if not stopping and not (Path(row['job']['root'])/'cancel-request.json').is_file():continue
            try:row['process'].wait(timeout=35)
            except subprocess.TimeoutExpired:
                if row['identity']:terminate_owned(row['process'],row['identity'])
        unresolved=uncertain_groups+[row['process'].pid for row in active.values()
                                     if row['process'].poll() is None
                                     or (row['identity'] is None and not unregistered_group_exited(row['process']))]
        for sig,handler in previous.items():signal.signal(sig,handler)
        for job in jobs:
            if not Path(job['root']).is_dir():continue
            final_write(Path(job['root'])/'batch-result.json',{'children_exited':not unresolved,'unconfirmed_pids':unresolved,
                'status':'CANCELLED' if stopping else 'BATCH_FINISHED',
                'outcomes':outcomes,'all_cases_accepted':len(outcomes)==len(jobs) and all(
                    r.get('status') in case_outcomes.PASSED for r in outcomes.values()),
                'scope':'Executor completion does not imply mathematical acceptance'})
        if report_progress and not unresolved and not stopping:
            from owner_reports import send_report
            for job in jobs:
                status=outcomes.get(job['id'],{}).get('status')
                if status and status not in {'CANCELLED','PAUSED_ERROR'}:
                    send_report(Path(job['root']),result_status=status)
    return outcomes


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job',type=Path,action='append',required=True)
    parser.add_argument('--case-concurrency',type=int)
    parser.add_argument('--controller-reports',action='store_true');args=parser.parse_args()
    results=serve([json.loads(p.read_text()) for p in args.job],case_concurrency=args.case_concurrency,
                  report_progress=args.controller_reports)
    raise SystemExit(0 if len(results)==len(args.job) and all(
        r.get('completion',{}).get('acceptance_target_satisfied') for r in results.values()) else 1)
