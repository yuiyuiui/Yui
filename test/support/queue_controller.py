#!/usr/bin/env python3
"""Finite case batch with independent processes and per-case model-stage budgets.

Jobs are explicit test inputs, not instructions from the model. Fresh workers
never receive this queue, other cases, or owner history. Failed jobs stop for
actual diagnosis; they are not automatically rewritten until they pass.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import threading
import time

import audit_a_campaign as a

CASES={'geometry-product-dimension','lie-module-irreducibility','wave-map-energy'}


def validate_job(value):
    common={'id','kind','case'}
    if 'time_budget_seconds' in value:
        if value['time_budget_seconds'] is not None and (type(value['time_budget_seconds']) is not int or value['time_budget_seconds']<1):
            raise ValueError('The whole-case wall budget must be null (unlimited) or a positive integer number of seconds')
        common.add('time_budget_seconds')
    if 'stop_after' in value:
        if value['stop_after']!='audit_a' or value.get('kind') not in {'nl0','audit_source'}:
            raise ValueError('stop_after=audit_a requires an NL0/Audit A job')
        common.add('stop_after')
    else:common|={'interface','workflow'}
    if 'audit_controls' in value:
        if value.get('kind') not in {'nl0','audit_source'}:raise ValueError('Audit controls require an Audit A job')
        common.add('audit_controls')
    if 'max_concurrency' in value:
        a.concurrency.resolve(value['max_concurrency']);common.add('max_concurrency')
    if 'reuse_audits' in value and value.get('kind') in {'nl0','audit_source'}:
        common.add('reuse_audits')
        if not isinstance(value['reuse_audits'],list):raise ValueError('reuse_audits must be explicit prior campaign names')
        for name in value['reuse_audits']:
            if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9-]*',name) or not (a.ROOT/'test/results'/name/'campaign.json').is_file():
                raise ValueError('Use an existing explicit same-case audit campaign name')
    if 'review' in value and value.get('kind') in {'checked_interface','submitted_interface'}:
        common.add('review')
    expected=common|({'run','audit'} if value.get('kind')=='nl0' else {'source','audit'} if value.get('kind')=='audit_source' else {'source'} if value.get('kind') in {'translate','submitted_interface'} else {'source','candidate'} if value.get('kind')=='checked_interface' else set())
    if value.get('kind') not in {'nl0','audit_source','translate','checked_interface','submitted_interface'} or set(value)!=expected:raise ValueError('Invalid explicit job schema')
    if value['kind']=='checked_interface' and (type(value['candidate']) is not int or value['candidate']<1):raise ValueError('Select an actual positive candidate number')
    if value['case'] not in CASES:raise ValueError('Only the three frozen exercise IDs are permitted')
    for key in ['id',*[k for k in ['interface','workflow','review','audit','run','audit_controls'] if k in value]]:
        if not isinstance(value[key],str) or not re.fullmatch(r'[a-z][a-z0-9-]*',value[key]):raise ValueError('Use a plain unique job/run identifier')
    if 'source' in value:
        path=(a.ROOT/'test/results'/value['source']).resolve()
        if not path.is_relative_to((a.ROOT/'test/results').resolve()) or not (path/'spec.json').is_file() or not (path/'nl0.json').is_file():raise ValueError('Source must be an exact staged case under test/results')


def launch_case(job_file,out):
    import subprocess,sys
    out.mkdir(parents=True,exist_ok=False)
    log=(out/'controller.log').open('w')
    try:
        return subprocess.Popen([sys.executable,'-u','-B',str(Path(__file__).with_name('case_runner.py')),
            '--job',str(job_file),'--out',str(out/'nl0-to-lean')],stdout=log,stderr=log,start_new_session=True)
    finally:log.close()


def cancel_batch(directory):
    from execution_state import atomic
    atomic(Path(directory)/'control/stop.json',{'requested_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})


def serve(queue,wait_for=None,*,case_concurrency=3):
    from execution_state import atomic,identity,terminate_owned,request_cancel
    from run_resources import check_cleanup_lock
    check_cleanup_lock(queue)
    queue=Path(queue).resolve();queue.mkdir(parents=True,exist_ok=True)
    for name in ['pending','records','results','cases']:(queue/name).mkdir(exist_ok=True)
    if (queue/'batch.json').exists():raise ValueError('Preserve the previous finite batch; use a new queue directory')
    shutil.copyfile(__file__,queue/'controller.py.snapshot.txt')
    if wait_for and not Path(wait_for).is_file():
        raise ValueError('Previous controller has not finalized; do not wait indefinitely or overlap ownership')
    if type(case_concurrency) is not int or case_concurrency<1:raise ValueError('Positive case concurrency required')
    jobs=[];case_ids=set()
    for path in sorted((queue/'pending').glob('*.json')):
        raw=path.read_bytes();job=json.loads(raw);validate_job(job)
        if job['case'] in case_ids:raise ValueError('Duplicate active case ID in one batch')
        case_ids.add(job['case']);record=queue/'records'/(job['id']+'.json')
        if record.exists():raise ValueError('Preserve the completed job record')
        record.write_bytes(raw);a.write(record.with_suffix('.binding.json'),{'sha256':hashlib.sha256(raw).hexdigest()})
        jobs.append((job,record));path.unlink()
    atomic(queue/'batch.json',{'controller':identity(__import__('os').getpid()),'case_concurrency':case_concurrency,'per_case_concurrency':'Independent auto|N budgets; no global model-stage semaphore',
        'cases':{job['id']:{'case':job['case'],'execution_root':str(queue/'cases'/job['id']/'nl0-to-lean')} for job,_ in jobs}})
    active={};states={};stopping=False
    last_progress=None;last_write=0.
    import signal
    previous={}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT,signal.SIGTERM):
            previous[sig]=signal.getsignal(sig);signal.signal(sig,lambda *_:cancel_batch(queue))
    try:
        while jobs or active:
            stopping=stopping or (queue/'control/stop.json').exists() or (queue/'stop-after-current.json').exists()
            if stopping:
                for job,record in jobs:
                    states[job['id']]={'case':job['case'],'stage':'CANCELLED','model_worker_called':False}
                    atomic(queue/'results'/(job['id']+'.json'),{'job':job,'result':{'status':'CANCELLED'}})
                jobs.clear()
            while jobs and len(active)<case_concurrency and not stopping:
                job,record=jobs.pop(0);out=queue/'cases'/job['id'];process=launch_case(record,out)
                owner=identity(process.pid)
                if owner is None and process.poll() is None:raise RuntimeError('Cannot establish case process ownership')
                if owner:atomic(out/'case-process.json',{'schema_version':'yui-owned-process-1','kind':'case-controller','process':owner})
                active[job['id']]={'job':job,'process':process,'identity':owner,'out':out,'stop_started':None}
                states[job['id']]={'case':job['case'],'stage':'STARTING','controller':owner}
            for key,row in list(active.items()):
                job,process,out=row['job'],row['process'],row['out'];root=out/'nl0-to-lean';snapshot=root/'execution-status.json'
                if stopping and process.poll() is None:
                    if row['stop_started'] is None:row['stop_started']=time.monotonic()
                    if snapshot.exists():request_cancel(root)
                    elif time.monotonic()-row['stop_started']>2 and row['identity']:terminate_owned(process,row['identity'])
                    if time.monotonic()-row['stop_started']>35 and row['identity']:
                        terminate_owned(process,row['identity'])
                if snapshot.exists():
                    value=json.loads(snapshot.read_text());states[key]={'case':job['case'],'stage':value['phase'],
                        'state':value['controller']['state'],'status_file':str(snapshot),'counts':value['counts']}
                if process.poll() is None:continue
                result_path=root/'case-result.json'
                result=json.loads(result_path.read_text()) if result_path.exists() else {'job':job,'result':{'status':'EXECUTION_FAULT','exit_code':process.returncode,'cleanup':'UNKNOWN'}}
                atomic(queue/'results'/(key+'.json'),result)
                states[key]={'case':job['case'],'stage':result['result']['status'],'status_file':str(snapshot)}
                del active[key]
            progress=json.dumps(states,sort_keys=True)
            mono=time.monotonic()
            if progress!=last_progress and (last_progress is None or mono-last_write>=1 or stopping or not (jobs or active)):
                atomic(queue/'progress.json',states)
                last_progress=progress;last_write=mono
            if jobs or active:time.sleep(.1)
    finally:
        for row in active.values():
            root=row['out']/'nl0-to-lean'
            if (root/'execution-status.json').exists():request_cancel(root)
        for row in active.values():
            try:row['process'].wait(timeout=35)
            except __import__('subprocess').TimeoutExpired:
                if row['identity']:terminate_owned(row['process'],row['identity'])
        for sig,handler in previous.items():signal.signal(sig,handler)
        atomic(queue/'progress.json',states)
        outcomes={}
        for path in (queue/'results').glob('*.json'):
            value=json.loads(path.read_text()).get('result',{})
            outcomes[path.stem]={'status':value.get('status'),
                'accepted':value.get('status') in {'DRAFT-AUDIT-PASSED','WORKFLOW-PASSED'}}
        atomic(queue/'final-concurrency.json',{'case_concurrency':case_concurrency,'active_case_processes':0,
            'case_budgets':'INDEPENDENT','status':'CANCELLED' if stopping else 'FINITE_BATCH_FINISHED',
            'case_outcomes':outcomes,'all_cases_accepted':bool(outcomes) and all(x['accepted'] for x in outcomes.values()) and len(outcomes)==len(states),
            'scope':'No mathematical or execution acceptance inferred from controller termination.'})



if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',required=True);p.add_argument('--wait-for');p.add_argument('--case-concurrency',type=int,default=3);p.add_argument('--cancel',action='store_true');args=p.parse_args();cancel_batch(args.queue) if args.cancel else serve(args.queue,args.wait_for,case_concurrency=args.case_concurrency)
