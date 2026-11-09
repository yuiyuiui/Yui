"""Optional operator breakpoints between accepted public stages."""
import json
import os
from pathlib import Path
import tempfile
import uuid

from controller_common import bind, verify_bindings, write
import execution_state


def allowed(track, formalization):
    return {'2basis','nl0','nl02lean'} if track=='full' and formalization=='unconditional' else {'nl0','nl02lean'} if track=='full' else {'nl0'} if track=='nl0' else set()


def verify(record):
    import basis
    import source_preparation
    from source_qualification import usable
    verify_bindings([record['job'],record['artifact']])
    job=json.loads(Path(record['job']['path']).read_text())
    path=Path(record['artifact']['path'])
    if not path.is_relative_to(Path(job['root'])) or record['stage']!=job.get('stop_after'):
        raise ValueError('Checkpoint differs from the authorized stage')
    if record['stage']=='2basis':
        basis.verify_foundations(job,record['artifact'])
    elif record['stage']=='nl0':
        if not usable(source_preparation.read_source(**json.loads(path.read_text()))[0][0]):
            raise ValueError('No actual Audit A acceptance')
    elif record['stage']=='nl02lean':
        import final_acceptance
        result=json.loads(path.read_text())
        final_acceptance.validate_receipt(result['audit_b']['receipt_path'])
    else: raise ValueError('Unknown stage checkpoint')


def resume(root, identifier):
    root=Path(root).resolve()
    path=root/'stage-checkpoint.json'
    row=json.loads(path.read_text())
    if (row['id']!=identifier or row['job']!=bind(root/'job.json')
            or row['status']!='WAITING' or not execution_state.same_process(row['owner'])):
        raise ValueError('Select the current waiting checkpoint of a live case')
    verify(row)
    control=root/'stage-controls'/identifier
    control.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=control.parent) as tmp:
        source=Path(tmp)/'control'
        write(source,{'checkpoint':bind(path),'id':identifier})
        try:os.link(source,control)
        except FileExistsError:
            if source.read_bytes()!=control.read_bytes():raise ValueError('Conflicting checkpoint control')
    return {'status':'RESUME_REQUESTED','id':identifier}


def stop_at(session, stage, artifact):
    if session.job.get('stop_after')!=stage:return
    root=session.root
    path=root/'stage-checkpoint.json'
    row={'id':uuid.uuid4().hex,'status':'WAITING','stage':stage,'artifact':artifact,
         'job':bind(root/'job.json'),'owner':session.recorder.state['controller']}
    verify(row)
    write(path,row)
    session.progress(session.job['case'],'PAUSED_AT_CHECKPOINT',stage=stage,artifact=artifact,
                     checkpoint=str(path),resume_id=row['id'])
    control=root/'stage-controls'/row['id']
    expected=bind(path)
    while not control.exists():
        session.recorder.check()
        session.recorder.done.wait(.5)
    if json.loads(control.read_text())!={'id':row['id'],'checkpoint':expected} or bind(path)!=expected:
        raise ValueError('Checkpoint control refers to different evidence')
    verify(row)
    write(path,{**row,'status':'RESUMED','control':bind(control)})
