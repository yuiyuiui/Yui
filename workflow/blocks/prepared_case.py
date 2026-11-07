"""Direct flow.py CLI delegates one prepared job to its ordinary frozen Yui owner."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def invoke(ctx, data):
    from wfcore import storage
    from wfcore.engine import Run
    path = Path(data['job']['path']).resolve()
    if path.name != 'job.json' or hashlib.sha256(path.read_bytes()).hexdigest() != data['job']['sha256']:
        raise ValueError('Supply the actual prepared job.json and its digest')
    job = json.loads(path.read_bytes())
    root = Path(job['root']).resolve()
    if path.parent != root or job.get('workflow_protocol') != 'yui-workflow-1':
        raise ValueError('Expected a new prepared Yui public job')
    run = root/'protocol'
    if not run.exists():
        if not ctx.node.startswith('request-') or (root/'execution-status.json').exists():
            raise ValueError('Preserve the existing owner and its checkpoint')
        installed = Path(os.environ.get('YUI_SKILL_ROOT',Path(sys.argv[0]).resolve().parents[2]))
        scripts = installed/'nl0/scripts'
        sys.path.insert(0,str(scripts))
        import jobs
        import runtime_snapshot
        jobs.validate(job)
        expected = 'audit' if job['track']=='nl0' else job['formalization']
        if ctx.node != 'request-'+expected:
            raise ValueError('The requested entry differs from the prepared goal')
        subprocess.run([sys.executable,'-B',str(runtime_snapshot.root_for(job)/'nl0/scripts/case_runner.py'),
                        '--job',str(path)],env=runtime_snapshot.environment(job),check=False)
    with storage.lock(run):
        inner = Run(run,read_only=True)
        if inner.s['status'] != 'completed':
            raise ValueError('Prepared case has no terminal delivery: '+str(inner.s['error']))
        row = next((r for r in inner.s['trace'] if r['node']==ctx.node and r['input']==data),None)
        if row is None:
            raise ValueError('No matching transition on the actual prepared case')
        output = dict(row['data'])
        if 'inventory' in output:
            output['inventory']=ctx.put_file(storage.read_blob(run,output['inventory']))
        return {'port':row['port'],'data':output}
