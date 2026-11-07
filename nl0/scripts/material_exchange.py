"""An operator answer supplies source bytes to the exact requesting role and incident."""
import fcntl
import json
from pathlib import Path
import tempfile
import uuid

from controller_common import bind, write
from staging_storage import copy_input


def received(logs, incident, job):
    directory=Path(logs)/'attachments'/incident
    receipt=json.loads((directory/'receipt.json').read_text())
    if receipt['incident']!=incident or receipt['job']!=job:
        raise ValueError('Attachment belongs to another request')
    for field in ('original','readback'):
        item=receipt[field]
        path=directory/item['name']
        if Path(item['name']).name!=item['name'] or path.is_symlink() or bind(path)['sha256']!=item['sha256']:
            raise ValueError('Attachment bytes have changed')
    return receipt


def supply(root, incident, attachment=None):
    import execution_state
    import fault_control
    import jobs
    root=Path(root).resolve()
    rows=[r for r in fault_control.pending(root) if r['incident']==incident and r['stage']=='source-material']
    if len(rows)!=1: raise ValueError('Select the current source-material incident')
    row=rows[0]
    logs=Path(row['logs']).resolve()
    if Path(row['root'])!=root or not logs.is_relative_to(root) or not execution_state.same_process(row['owner_process']):
        raise ValueError('Material request owner is no longer live')
    fault_control.validate_context(root,row['job_binding'],True)
    if attachment is None:
        return {'status':'WAITING_FOR_ATTACHMENT','incident':incident,'description':row['checkpoint']['required_material']}
    if Path(attachment).expanduser().is_dir():
        raise ValueError('Supply the actual attached file for this incident')
    source=jobs.input_file(attachment)
    directory=logs/'attachments'/incident
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'.submission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        digest=bind(source)['sha256']
        if (directory/'receipt.json').exists():
            receipt=received(logs,incident,row['job_binding'])
            if receipt['original']['sha256']!=digest: raise ValueError('A different attachment already satisfies this incident')
        else:
            with tempfile.TemporaryDirectory(dir=directory) as raw:
                tmp=Path(raw)
                name='source'+source.suffix.lower()
                copy_input(source,tmp/name)
                if bind(tmp/name)['sha256']!=digest: raise ValueError('Source changed during attachment transfer')
                jobs.stage_document(tmp/name,tmp/'readback.txt')
                if not (tmp/'readback.txt').read_text().strip(): raise ValueError('The received attachment has no readable text')
                receipt={'incident':incident,'job':row['job_binding'],'description':row['checkpoint']['required_material'],
                         'original':{'name':name,'sha256':digest},'readback':{'name':'readback.txt','sha256':bind(tmp/'readback.txt')['sha256']}}
                for file in tmp.iterdir():file.replace(directory/file.name)
                write(directory/'receipt.json',receipt)
        received(logs,incident,row['job_binding'])
        control=logs/'error-control'/(incident+'.json')
        if not control.exists():
            execution_state.atomic(control,{'incident':incident,'action':'resume','id':uuid.uuid4().hex})
    return {'status':'ATTACHMENT_RECEIVED','incident':incident,'sha256':digest}


def request(stage, description):
    import fault_control
    gate=fault_control.Gate(stage.logs/'material-request',recorder=stage.execution,task=stage.execution_task,stage='source-material')
    state=gate.pause({'code':'workflow_blocked','message':description},resumable=True,checkpoint={'required_material':description})
    row=received(gate.logs,state['incident'],state['job_binding'])
    directory=gate.logs/'attachments'/state['incident']
    base=stage.validator.directory if stage.artifact_kind=='nl0' else stage.logs
    target=base/'external-sources'/('attachment-'+state['incident'])
    target.mkdir(parents=True,exist_ok=True)
    refs={}
    for key in ('original','readback'):
        name=row[key]['name']
        copy_input(directory/name,target/name)
        refs[key]={'path':str((target/name).relative_to(base)),'sha256':row[key]['sha256']}
    text=(target/row['readback']['name']).read_text()
    stage.supplied_materials[state['incident']]=text
    return {'status':'ATTACHMENT_RECEIVED','stage_complete':False,'incident':state['incident'],'evidence':refs,
            'preview':text[:1600],'instruction':'Read remaining lines with read_supplied_material and verify that this source addresses the request.'}
