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

from controller_common import write, bind
import jobs as job_contract
from execution_state import identity, terminate_owned, request_cancel


def validate_job(value):
    return job_contract.validate(value)


def cancel_batch(directories):
    for directory in directories:
        root=Path(directory).resolve()
        if not (root/job_contract.MARKER).is_file():raise ValueError('Unknown owned run')
        write(root/'cancel-request.json',{'external_cancel':True})
        if (root/'execution-status.json').is_file():request_cancel(root)


def launch_case(job_file,out):
    out=Path(out);(out/'logs').mkdir(exist_ok=True)
    with (out/'logs/controller.log').open('w') as log:
        return subprocess.Popen([sys.executable,'-u','-B',str(Path(__file__).with_name('case_runner.py')),
            '--job',str(job_file)],stdout=log,stderr=log,start_new_session=True)


def serve(jobs,*,case_concurrency=None):
    jobs=list(jobs)
    for job in jobs:validate_job(job)
    if len({j['root'] for j in jobs})!=len(jobs) or len({j['problem'] for j in jobs})!=len(jobs):
        raise ValueError('Duplicate case input/output in one batch')
    count=len(jobs) if case_concurrency is None else case_concurrency
    if type(count) is not int or count<1:raise ValueError('Positive concurrent-case count required')
    pending=list(jobs);active={};outcomes={};stopping=False;previous={}
    owner=identity(os.getpid())
    if owner is None:raise RuntimeError('Cannot establish batch controller identity')
    for job in jobs:
        write(Path(job['root'])/'batch.json',{'controller':owner,'concurrent_cases':count,
            'case_run_roots':[j['root'] for j in jobs],'case':job['case'],
            'scope':'Controller metadata only; never a model input'})
    def stop(*_):
        nonlocal stopping
        stopping=True;cancel_batch([j['root'] for j in jobs])
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT,signal.SIGTERM):previous[sig]=signal.signal(sig,stop)
    try:
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
                process=launch_case(root/'job.json',root);who=identity(process.pid)
                if who is None and process.poll() is None:raise RuntimeError('Missing case process identity')
                if who:write(root/'case-process.json',{'schema_version':'yui-owned-process-1','process':who,'kind':'case-controller'})
                active[job['id']]={'job':job,'process':process,'identity':who,'cancel_at':None}
            if stopping:
                for job in pending:
                    outcomes[job['id']]={'status':'CANCELLED','model_worker_called':False}
                    write(Path(job['root'])/'case-result.json',{'job':bind(Path(job['root'])/'job.json'),'result':outcomes[job['id']]})
                pending.clear()
            for key,row in list(active.items()):
                root=Path(row['job']['root']);process=row['process']
                if (root/'cancel-request.json').exists() and process.poll() is None:
                    row['cancel_at']=row['cancel_at'] or time.monotonic()
                    if (root/'execution-status.json').is_file():request_cancel(root)
                    if time.monotonic()-row['cancel_at']>35 and row['identity']:terminate_owned(process,row['identity'])
                if process.poll() is None:continue
                result=root/'case-result.json'
                if not result.is_file():
                    write(result,{'job':bind(root/'job.json'),'result':{'status':'EXECUTION_FAULT','exit_code':process.returncode,'cleanup':'UNKNOWN'}})
                outcomes[key]=json.loads(result.read_text())['result'];del active[key]
            if pending or active:time.sleep(.1)
    finally:
        for row in active.values():
            root=Path(row['job']['root'])
            if (root/'execution-status.json').exists():request_cancel(root)
        for row in active.values():
            try:row['process'].wait(timeout=35)
            except subprocess.TimeoutExpired:
                if row['identity']:terminate_owned(row['process'],row['identity'])
        unresolved=[row['process'].pid for row in active.values() if row['process'].poll() is None]
        for sig,handler in previous.items():signal.signal(sig,handler)
        for job in jobs:
            if not Path(job['root']).is_dir():continue
            write(Path(job['root'])/'batch-result.json',{'children_exited':not unresolved,'unconfirmed_pids':unresolved,
                'status':'CANCELLED' if stopping else 'BATCH_FINISHED',
                'outcomes':outcomes,'all_cases_accepted':len(outcomes)==len(jobs) and all(
                    r.get('status') in {'DRAFT-AUDIT-PASSED','WORKFLOW-PASSED','AUDIT-B-PASSED'} for r in outcomes.values()),
                'scope':'Executor completion does not imply mathematical acceptance'})
    return outcomes


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job',type=Path,action='append',required=True)
    parser.add_argument('--case-concurrency',type=int);args=parser.parse_args()
    results=serve([json.loads(p.read_text()) for p in args.job],case_concurrency=args.case_concurrency)
    raise SystemExit(0 if all(r.get('completion',{}).get('acceptance_target_satisfied') for r in results.values()) else 1)
