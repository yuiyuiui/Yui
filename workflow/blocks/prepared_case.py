"""Delegate an externally started protocol to one ordinary, snapshotted Yui owner."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def invoke(ctx, data):
    from wfcore import storage
    from wfcore.engine import Run
    path=Path(data['job']['path']).resolve()
    if path.name!='job.json' or hashlib.sha256(path.read_bytes()).hexdigest()!=data['job']['sha256']:
        raise ValueError('Supply the actual prepared job.json and its digest')
    job=json.loads(path.read_bytes())
    root=Path(job['root']).resolve()
    if path.parent!=root or job.get('workflow_protocol')!='yui-workflow-1':
        raise ValueError('Expected a new prepared Yui public job')
    expected='audit' if job['track']=='nl0' else job['formalization']
    if ctx.node.startswith('request-'):
        captured=root/'runtime/workflow/workflow.json'
        outer=Path(__file__).resolve().parents[1]/'workflow.json'
        if not captured.is_file() or json.loads(captured.read_bytes())!=json.loads(outer.read_bytes()):
            raise ValueError('Use this prepared case\'s snapshotted workflow CLI. Its route differs from the selected package.')
        if ctx.node!='request-'+expected:
            raise ValueError('The requested entry differs from the prepared goal')
        return {'port':'selected','data':{**data,'goal':expected}}
    if data['goal']!=expected:
        raise ValueError('The selected goal changed after admission')
    run=root/'protocol'
    if not run.is_dir():
        # Two bridge callers may arrive while the native owner is still starting.
        with (root/'.protocol-launch.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if not run.is_dir():
                if ctx.node not in ('basis/reduce','outline') or (root/'execution-status.json').exists():
                    raise ValueError('Preserve the existing owner and its checkpoint')
                installed=Path(os.environ.get('YUI_SKILL_ROOT',Path(sys.argv[0]).resolve().parents[2]))
                sys.path.insert(0,str(installed/'nl0/scripts'))
                import jobs
                import runtime_snapshot
                jobs.validate(job)
                log=root/'logs/protocol-launch.log'
                log.parent.mkdir(exist_ok=True)
                with log.open('a') as stream:
                    subprocess.run([sys.executable,'-B',str(runtime_snapshot.root_for(job)/'nl0/scripts/case_runner.py'),
                                    '--job',str(path)],env=runtime_snapshot.environment(job),stdout=stream,
                                   stderr=subprocess.STDOUT,check=False)
    with storage.lock(run):
        inner=Run(run,read_only=True)
        if inner.s['status']!='completed':
            raise ValueError('Prepared case has no terminal delivery: '+str(inner.s['error']))
        row=next((r for r in inner.s['trace'] if r['node']==ctx.node and r['input']==data),None)
        if row is None:
            raise ValueError('No matching transition on the actual prepared case')
        output=dict(row['data'])
        if 'inventory' in output:
            output['inventory']=ctx.put_file(storage.read_blob(run,output['inventory']))
        return {'port':row['port'],'data':output}
